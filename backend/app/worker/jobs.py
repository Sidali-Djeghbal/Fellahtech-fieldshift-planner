"""Worker domain logic: ENDPOINTS B.10.4 error policy, 413 history trimming & basic verifier."""

from __future__ import annotations

import copy
import json
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.ml_client.base import (
    MLAuthError,
    MLCatalogVersionMismatchError,
    MLClientError,
    MLContractError,
    MLDatasetError,
    MLDatasetVersionUnavailableError,
    MLInsufficientDataError,
    MLInvalidPayloadError,
    MLPayloadTooLargeError,
    MLRateLimitError,
    MLTimeoutError,
    MLTransportError,
    MLUpstreamServerError,
    validate_contract_def,
)
from app.services.verification import (
    ResultVerificationOutcome as ResultVerificationOutcome,
)
from app.services.verification import (
    ResultVerifier as ResultVerifier,
)

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 2.0
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
MAX_RETRY_JITTER_SECONDS = 0.5
MAX_RATE_LIMIT_RETRY_AFTER_SECONDS = 5
LEASE_BACKOFF_SAFETY_MARGIN_SECONDS = 1.0
GZIP_COMPRESS_THRESHOLD_BYTES = 16384
_RECENT_HISTORY_WINDOW_ITEMS = 4

_SEASON_ORDER_RANK: dict[str, int] = {
    "winter": 0,
    "spring": 1,
    "summer": 2,
    "autumn": 3,
}

# Exact subset of terminal failures eligible for guest quota refunds up to GUEST_MAX_ML_REFUNDS=3.
# Excludes 422 INSUFFICIENT_DATA (domain gap) and 409 CATALOG_VERSION_MISMATCH (IMPL-011).
REFUNDABLE_ML_ERROR_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.ML_UNAVAILABLE,
        ErrorCode.ML_TIMEOUT,
        ErrorCode.ML_INVALID_RESPONSE,
        ErrorCode.ML_CONTRACT_ERROR,
        ErrorCode.DATASET_VERSION_UNAVAILABLE,
        ErrorCode.ML_DATASET_ERROR,
        ErrorCode.INTERNAL_ERROR,
    }
)

RetryAction = Literal[
    "fail",
    "retry_backoff",
    "retry_rate_limit",
    "retry_catalog_sync",
    "retry_trim_payload",
]


@dataclass(slots=True)
class RetryBudgetState:
    """Mutable per-job retry counters enforcing single/bounded retries inside one claim."""

    transient_retries_used: int = 0
    rate_limit_retries_used: int = 0
    catalog_sync_retries_used: int = 0
    payload_trim_retries_used: int = 0


@dataclass(frozen=True, slots=True)
class MLErrorDecision:
    """Structured retry/fail/breaker/refund decision derived from `ENDPOINTS B.10.4`."""

    action: RetryAction
    backend_error_code: ErrorCode
    delay_seconds: float | None = None
    trips_breaker: bool = False
    refundable_for_guest: bool = False
    critical_alert: bool = False


class PayloadTrimError(Exception):
    """Raised when `FarmAnalysisInput` cannot be shrunk safely below byte ceiling."""


@dataclass(frozen=True, slots=True)
class PayloadTrimResult:
    """Trimmed `FarmAnalysisInput` JSON dict, compact UTF-8 bytes, and removal count."""

    payload: dict[str, Any]
    raw_bytes: bytes
    trimmed_entries: int


def serialize_compact_json(payload: Mapping[str, Any]) -> bytes:
    """Serialize `FarmAnalysisInput` identically to `RealMLAdapter.analyze` wire encoding."""
    return json.dumps(
        dict(payload),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def extract_payload_crop_ids(payload: Mapping[str, Any]) -> list[str]:
    """Return sorted unique catalog crop IDs referenced in `priorities`."""
    priorities = payload.get("priorities")
    if not isinstance(priorities, Mapping):
        return []
    crops: set[str] = set()
    for key in ("target_crop_ids", "excluded_crop_ids"):
        raw_list = priorities.get(key)
        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, str) and item:
                    crops.add(item)
    return sorted(crops)


def _history_entry_age_key(entry: Mapping[str, Any], orig_index: int) -> tuple[int, int, int]:
    raw_year = entry.get("year")
    year = int(raw_year) if isinstance(raw_year, int) else 0
    season = str(entry.get("season", "")).lower()
    season_rank = _SEASON_ORDER_RANK.get(season, 0)
    return (year, season_rank, orig_index)


def _remove_single_oldest_history_entry(fields_list: list[Any]) -> bool:
    """Drop the globally oldest `crop_history` entry among fields having >1 items."""
    candidate: tuple[tuple[int, int, int], int, int] | None = None
    for f_idx, field_obj in enumerate(fields_list):
        if not isinstance(field_obj, dict):
            continue
        hist = field_obj.get("crop_history")
        if not isinstance(hist, list) or len(hist) <= 1:
            continue
        for h_idx, item in enumerate(hist):
            age_key = (
                _history_entry_age_key(item, h_idx)
                if isinstance(item, Mapping)
                else (0, 0, h_idx)
            )
            if candidate is None or age_key < candidate[0]:
                candidate = (age_key, f_idx, h_idx)

    if candidate is None:
        return False
    _, target_f_idx, target_h_idx = candidate
    target_hist = fields_list[target_f_idx]["crop_history"]
    target_hist.pop(target_h_idx)
    return True


def _trim_to_recent_window_on_413(fields_list: list[Any]) -> int:
    """Trim each field's `crop_history` down to a smaller recent slice, preserving >=1 newest."""
    removed = 0
    for field_obj in fields_list:
        if not isinstance(field_obj, dict):
            continue
        hist = field_obj.get("crop_history")
        if not isinstance(hist, list) or len(hist) <= 1:
            continue
        target_keep = min(len(hist) - 1, max(1, min(_RECENT_HISTORY_WINDOW_ITEMS, len(hist) // 2)))
        ranked = sorted(
            enumerate(hist),
            key=lambda pair: (
                _history_entry_age_key(pair[1], pair[0])
                if isinstance(pair[1], Mapping)
                else (0, 0, pair[0])
            ),
        )
        drop_count = len(hist) - target_keep
        drop_indices = {idx for idx, _ in ranked[:drop_count]}
        field_obj["crop_history"] = [
            item for idx, item in enumerate(hist) if idx not in drop_indices
        ]
        removed += drop_count
    return removed


def trim_analysis_payload_for_size(
    payload: Mapping[str, Any],
    *,
    max_bytes: int | None = None,
    force_shrink: bool = False,
) -> PayloadTrimResult:
    """Trim oldest `crop_history` entries while preserving >=1 item/field and valid v5 schema."""
    trimmed = copy.deepcopy(dict(payload))
    raw_bytes = serialize_compact_json(trimmed)
    initial_len = len(raw_bytes)
    fields_raw = trimmed.get("fields")
    if not isinstance(fields_raw, list):
        raise PayloadTrimError("FarmAnalysisInput missing 'fields' array.")

    trimmed_entries = 0
    if force_shrink:
        trimmed_entries += _trim_to_recent_window_on_413(fields_raw)
        raw_bytes = serialize_compact_json(trimmed)

    if max_bytes is not None:
        while len(raw_bytes) > max_bytes:
            if not _remove_single_oldest_history_entry(fields_raw):
                break
            trimmed_entries += 1
            raw_bytes = serialize_compact_json(trimmed)

    if max_bytes is not None and len(raw_bytes) > max_bytes:
        raise PayloadTrimError(
            f"Unable to trim payload ({len(raw_bytes)}B) below max_bytes={max_bytes}B."
        )
    if force_shrink and (trimmed_entries == 0 or len(raw_bytes) >= initial_len):
        raise PayloadTrimError(
            "Unable to reduce FarmAnalysisInput payload size after 413 PAYLOAD_TOO_LARGE."
        )

    schema_errors = validate_contract_def(trimmed, "FarmAnalysisInput")
    if schema_errors:
        raise PayloadTrimError(
            f"Trimmed FarmAnalysisInput failed schema-v5.0 validation: {schema_errors[0]}"
        )

    return PayloadTrimResult(
        payload=trimmed,
        raw_bytes=raw_bytes,
        trimmed_entries=trimmed_entries,
    )


def compute_retry_delay(
    retry_after_seconds: int | None,
    *,
    default_base: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    jitter_fn: Callable[[], float] | None = None,
) -> float | None:
    """Compute bounded retry backoff (`Retry-After <= 5s` or `2s + jitter`), None if > 5s."""
    if retry_after_seconds is not None:
        if retry_after_seconds < 0 or retry_after_seconds > MAX_RATE_LIMIT_RETRY_AFTER_SECONDS:
            return None
        return float(retry_after_seconds)
    jitter = (
        random.uniform(0.0, MAX_RETRY_JITTER_SECONDS)
        if jitter_fn is None
        else max(0.0, float(jitter_fn()))
    )
    return float(default_base) + jitter


def classify_ml_error_policy(
    exc: MLClientError,
    *,
    settings: Settings,
    remaining_lease_seconds: float,
    retries_used: RetryBudgetState,
    jitter_fn: Callable[[], float] | None = None,
) -> MLErrorDecision:
    """Map an `MLClientError` onto exact `ENDPOINTS B.10.4` retry/fail/breaker/refund rules."""
    if isinstance(exc, MLContractError):
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.ML_CONTRACT_ERROR,
            trips_breaker=False,
            refundable_for_guest=ErrorCode.ML_CONTRACT_ERROR in REFUNDABLE_ML_ERROR_CODES,
            critical_alert=True,
        )

    if isinstance(exc, MLAuthError):
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.ML_UNAVAILABLE,
            trips_breaker=False,
            refundable_for_guest=ErrorCode.ML_UNAVAILABLE in REFUNDABLE_ML_ERROR_CODES,
            critical_alert=True,
        )

    if isinstance(exc, MLDatasetVersionUnavailableError):
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.DATASET_VERSION_UNAVAILABLE,
            trips_breaker=False,
            refundable_for_guest=(
                ErrorCode.DATASET_VERSION_UNAVAILABLE in REFUNDABLE_ML_ERROR_CODES
            ),
            critical_alert=True,
        )

    if isinstance(exc, MLInsufficientDataError):
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.INSUFFICIENT_DATA,
            trips_breaker=False,
            refundable_for_guest=False,
            critical_alert=False,
        )

    if isinstance(exc, MLDatasetError):
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.ML_DATASET_ERROR,
            trips_breaker=True,
            refundable_for_guest=ErrorCode.ML_DATASET_ERROR in REFUNDABLE_ML_ERROR_CODES,
            critical_alert=True,
        )

    if isinstance(exc, MLInvalidPayloadError):
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.ML_INVALID_RESPONSE,
            trips_breaker=False,
            refundable_for_guest=ErrorCode.ML_INVALID_RESPONSE in REFUNDABLE_ML_ERROR_CODES,
            critical_alert=False,
        )

    if isinstance(exc, MLCatalogVersionMismatchError):
        if retries_used.catalog_sync_retries_used < 1 and remaining_lease_seconds > 2.0:
            return MLErrorDecision(
                action="retry_catalog_sync",
                backend_error_code=ErrorCode.CATALOG_VERSION_MISMATCH,
                trips_breaker=False,
                refundable_for_guest=(
                    ErrorCode.CATALOG_VERSION_MISMATCH in REFUNDABLE_ML_ERROR_CODES
                ),
            )
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.CATALOG_VERSION_MISMATCH,
            trips_breaker=False,
            refundable_for_guest=(
                ErrorCode.CATALOG_VERSION_MISMATCH in REFUNDABLE_ML_ERROR_CODES
            ),
        )

    if isinstance(exc, MLPayloadTooLargeError):
        if retries_used.payload_trim_retries_used < 1 and remaining_lease_seconds > 2.0:
            return MLErrorDecision(
                action="retry_trim_payload",
                backend_error_code=ErrorCode.INTERNAL_ERROR,
                trips_breaker=False,
                refundable_for_guest=ErrorCode.INTERNAL_ERROR in REFUNDABLE_ML_ERROR_CODES,
            )
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.INTERNAL_ERROR,
            trips_breaker=False,
            refundable_for_guest=ErrorCode.INTERNAL_ERROR in REFUNDABLE_ML_ERROR_CODES,
        )

    if isinstance(exc, MLRateLimitError):
        if (
            retries_used.rate_limit_retries_used < 1
            and exc.retry_after_seconds is not None
            and 0 <= exc.retry_after_seconds <= MAX_RATE_LIMIT_RETRY_AFTER_SECONDS
        ):
            rate_delay = float(exc.retry_after_seconds)
            if remaining_lease_seconds > (rate_delay + LEASE_BACKOFF_SAFETY_MARGIN_SECONDS):
                return MLErrorDecision(
                    action="retry_rate_limit",
                    backend_error_code=ErrorCode.ML_UNAVAILABLE,
                    delay_seconds=rate_delay,
                    trips_breaker=False,
                    refundable_for_guest=True,
                )
        return MLErrorDecision(
            action="fail",
            backend_error_code=ErrorCode.ML_UNAVAILABLE,
            trips_breaker=False,
            refundable_for_guest=True,
        )

    # Remaining transient upstream errors: 500/503 (MLUpstreamServerError),
    # Transport (MLTransportError), and Network Timeout (MLTimeoutError).
    backend_code = (
        ErrorCode.ML_TIMEOUT if isinstance(exc, MLTimeoutError) else ErrorCode.ML_UNAVAILABLE
    )
    if (
        isinstance(exc, (MLUpstreamServerError, MLTimeoutError, MLTransportError))
        and retries_used.transient_retries_used < settings.ML_MAX_RETRIES
    ):
        backoff_delay = compute_retry_delay(exc.retry_after_seconds, jitter_fn=jitter_fn)
        if backoff_delay is not None and remaining_lease_seconds > (
            backoff_delay + LEASE_BACKOFF_SAFETY_MARGIN_SECONDS
        ):
            return MLErrorDecision(
                action="retry_backoff",
                backend_error_code=backend_code,
                delay_seconds=backoff_delay,
                trips_breaker=True,
                refundable_for_guest=True,
            )

    return MLErrorDecision(
        action="fail",
        backend_error_code=backend_code,
        trips_breaker=True,
        refundable_for_guest=True,
    )


async def verify_analysis_result_basic(
    result_payload: Mapping[str, Any],
    *,
    expected_dataset_version: str,
    input_snapshot: Mapping[str, Any],
) -> ResultVerificationOutcome:
    """M8 default Stage 1 (`schema-v5.0.json`) + `SEM-07` check before M9 full `SEM-01..06`."""
    del input_snapshot
    schema_errors = validate_contract_def(dict(result_payload), "AnalysisResult")
    if schema_errors:
        return ResultVerificationOutcome(
            valid=False,
            result_status="invalid",
            error_code=ErrorCode.ML_INVALID_RESPONSE,
            validation_errors=[
                {"stage": "stage1_schema", "reason": msg} for msg in schema_errors[:10]
            ],
        )

    dataset_used = result_payload.get("dataset_version_used")
    if dataset_used != expected_dataset_version:
        return ResultVerificationOutcome(
            valid=False,
            result_status="invalid",
            error_code=ErrorCode.DATASET_VERSION_UNAVAILABLE,
            validation_errors=[
                {
                    "stage": "sem_07",
                    "reason": "dataset_version_mismatch",
                    "expected": expected_dataset_version,
                    "actual": dataset_used,
                }
            ],
        )

    raw_status = str(result_payload.get("status", "ok"))
    normalized_status: Literal["ok", "partial"] = "partial" if raw_status == "partial" else "ok"
    return ResultVerificationOutcome(
        valid=True,
        result_status=normalized_status,
        error_code=None,
        validation_errors=[],
    )
