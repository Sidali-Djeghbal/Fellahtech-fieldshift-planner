"""Unit tests covering ENDPOINTS B.10.4 ML error mapping, 413 payload trimming & Stage 1/SEM-07."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.db.session import calculate_pool_budget
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
)
from app.worker.jobs import (
    PayloadTrimError,
    RetryBudgetState,
    classify_ml_error_policy,
    compute_retry_delay,
    serialize_compact_json,
    trim_analysis_payload_for_size,
    verify_analysis_result_basic,
)

TESTS_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = TESTS_DIR / "fixtures"


def _unit_settings(**overrides: Any) -> Settings:
    params: dict[str, Any] = {
        "_env_file": None,
        "APP_ENV": "test",
        "ML_PROVIDER_MODE": "mock",
        "DATABASE_URL": "postgresql+asyncpg://fieldshift:secret@127.0.0.1:5432/fieldshift",
        "DB_PASSWORD": "secret",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "ML_DATASET_DB_URL": "postgresql://ml_reader:secret2@127.0.0.1:5432/fieldshift",
        "ML_READER_PASSWORD": "secret2",
        "JWT_SECRET_KEY": "unit_test_jwt_secret_32_chars_min!",
        "ML_SERVICE_API_KEY": "unit_test_ml_key",
        "ML_MAX_RETRIES": 1,
        "JOB_LEASE_SECONDS": 90,
        "WORKER_CONCURRENCY": 4,
        "ML_MAX_CONCURRENT_REQUESTS": 8,
    }
    params.update(overrides)
    return Settings(**params)


def test_worker_pool_budget_e4_headroom() -> None:
    """E4 sizing must guarantee pool_size + max_overflow >= concurrency + bulkhead + 4."""
    settings = _unit_settings(WORKER_CONCURRENCY=4, ML_MAX_CONCURRENT_REQUESTS=8)
    pool_size, max_overflow = calculate_pool_budget(settings, role="worker")
    assert pool_size == 12
    assert max_overflow == 6
    assert (pool_size + max_overflow) >= (
        settings.WORKER_CONCURRENCY + settings.ML_MAX_CONCURRENT_REQUESTS + 4
    )


@pytest.mark.parametrize(
    (
        "exc",
        "retries_used",
        "remaining_lease_s",
        "ml_max_retries",
        "expected_action",
        "expected_error",
        "expected_trips_breaker",
        "expected_refundable",
    ),
    [
        (
            MLContractError(),
            RetryBudgetState(),
            85.0,
            1,
            "fail",
            ErrorCode.ML_CONTRACT_ERROR,
            False,
            True,
        ),
        (
            MLAuthError(),
            RetryBudgetState(),
            85.0,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLDatasetVersionUnavailableError(status_code=409),
            RetryBudgetState(),
            85.0,
            1,
            "fail",
            ErrorCode.DATASET_VERSION_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLDatasetVersionUnavailableError(status_code=422),
            RetryBudgetState(),
            85.0,
            1,
            "fail",
            ErrorCode.DATASET_VERSION_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLCatalogVersionMismatchError(),
            RetryBudgetState(catalog_sync_retries_used=0),
            85.0,
            1,
            "retry_catalog_sync",
            ErrorCode.CATALOG_VERSION_MISMATCH,
            False,
            False,
        ),
        (
            MLCatalogVersionMismatchError(),
            RetryBudgetState(catalog_sync_retries_used=1),
            85.0,
            1,
            "fail",
            ErrorCode.CATALOG_VERSION_MISMATCH,
            False,
            False,
        ),
        (
            MLPayloadTooLargeError(),
            RetryBudgetState(payload_trim_retries_used=0),
            85.0,
            1,
            "retry_trim_payload",
            ErrorCode.INTERNAL_ERROR,
            False,
            True,
        ),
        (
            MLPayloadTooLargeError(),
            RetryBudgetState(payload_trim_retries_used=1),
            85.0,
            1,
            "fail",
            ErrorCode.INTERNAL_ERROR,
            False,
            True,
        ),
        (
            MLInsufficientDataError(),
            RetryBudgetState(),
            85.0,
            1,
            "fail",
            ErrorCode.INSUFFICIENT_DATA,
            False,
            False,
        ),
        (
            MLRateLimitError(retry_after_seconds=3),
            RetryBudgetState(rate_limit_retries_used=0),
            85.0,
            1,
            "retry_rate_limit",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLRateLimitError(retry_after_seconds=5),
            RetryBudgetState(rate_limit_retries_used=0),
            85.0,
            1,
            "retry_rate_limit",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLRateLimitError(retry_after_seconds=6),
            RetryBudgetState(rate_limit_retries_used=0),
            85.0,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLRateLimitError(retry_after_seconds=None),
            RetryBudgetState(rate_limit_retries_used=0),
            85.0,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLRateLimitError(retry_after_seconds=4),
            RetryBudgetState(rate_limit_retries_used=0),
            4.5,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLRateLimitError(retry_after_seconds=2),
            RetryBudgetState(rate_limit_retries_used=1),
            85.0,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            False,
            True,
        ),
        (
            MLUpstreamServerError(status_code=500, ml_error_code="INTERNAL_ERROR"),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            1,
            "retry_backoff",
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            MLUpstreamServerError(status_code=503, retry_after_seconds=2),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            1,
            "retry_backoff",
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            MLUpstreamServerError(status_code=503, retry_after_seconds=12),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            MLUpstreamServerError(status_code=503),
            RetryBudgetState(transient_retries_used=1),
            85.0,
            1,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            MLUpstreamServerError(status_code=503),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            0,
            "fail",
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            MLTransportError(),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            1,
            "retry_backoff",
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            MLDatasetError(),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            1,
            "fail",
            ErrorCode.ML_DATASET_ERROR,
            True,
            True,
        ),
        (
            MLTimeoutError(),
            RetryBudgetState(transient_retries_used=0),
            85.0,
            1,
            "retry_backoff",
            ErrorCode.ML_TIMEOUT,
            True,
            True,
        ),
        (
            MLTimeoutError(),
            RetryBudgetState(transient_retries_used=1),
            85.0,
            1,
            "fail",
            ErrorCode.ML_TIMEOUT,
            True,
            True,
        ),
        (
            MLTimeoutError(),
            RetryBudgetState(transient_retries_used=0),
            2.5,
            1,
            "fail",
            ErrorCode.ML_TIMEOUT,
            True,
            True,
        ),
        (
            MLInvalidPayloadError(),
            RetryBudgetState(),
            85.0,
            1,
            "fail",
            ErrorCode.ML_INVALID_RESPONSE,
            False,
            True,
        ),
    ],
)
def test_complete_b10_4_error_mapping_matrix(
    exc: MLClientError,
    retries_used: RetryBudgetState,
    remaining_lease_s: float,
    ml_max_retries: int,
    expected_action: str,
    expected_error: ErrorCode,
    expected_trips_breaker: bool,
    expected_refundable: bool,
) -> None:
    """Every row of ENDPOINTS B.10.4 must map deterministically."""
    settings = _unit_settings(ML_MAX_RETRIES=ml_max_retries)
    decision = classify_ml_error_policy(
        exc,
        settings=settings,
        remaining_lease_seconds=remaining_lease_s,
        retries_used=retries_used,
        jitter_fn=lambda: 0.25,
    )
    assert decision.action == expected_action
    assert decision.backend_error_code == expected_error
    assert decision.trips_breaker is expected_trips_breaker
    assert decision.refundable_for_guest is expected_refundable


def test_compute_retry_delay_bounds() -> None:
    assert compute_retry_delay(None, jitter_fn=lambda: 0.15) == pytest.approx(2.15)
    assert compute_retry_delay(0) == 0.0
    assert compute_retry_delay(5) == 5.0
    assert compute_retry_delay(6) is None
    assert compute_retry_delay(-1) is None


def test_trim_analysis_payload_removes_oldest_first_and_preserves_schema() -> None:
    """Oldest `crop_history` entries must be trimmed while keeping newest + >=1/field."""
    base_input: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    large = copy.deepcopy(base_input)
    template_entry = copy.deepcopy(large["fields"][0]["crop_history"][0])
    expanded_history = []
    for yr in range(2015, 2027):
        entry = copy.deepcopy(template_entry)
        entry["year"] = yr
        entry["season"] = "spring"
        expanded_history.append(entry)
    large["fields"][0]["crop_history"] = expanded_history

    raw_len = len(serialize_compact_json(large))
    target_cap = raw_len - 300
    trimmed = trim_analysis_payload_for_size(large, max_bytes=target_cap)

    assert len(trimmed.raw_bytes) <= target_cap
    assert trimmed.trimmed_entries >= 1
    remaining_years = [int(item["year"]) for item in trimmed.payload["fields"][0]["crop_history"]]
    assert len(remaining_years) >= 1
    # Kept slice must strictly be the newest suffix (oldest years trimmed first).
    assert remaining_years == list(range(2027 - len(remaining_years), 2027))

    # 413 force_shrink keeps at least 1 newest entry, then refuses if already minimal.
    single_entry = copy.deepcopy(base_input)
    single_entry["fields"][0]["crop_history"] = [copy.deepcopy(expanded_history[-1])]
    if len(single_entry["fields"]) > 1:
        for fld in single_entry["fields"][1:]:
            fld["crop_history"] = fld["crop_history"][:1]
    with pytest.raises(PayloadTrimError):
        trim_analysis_payload_for_size(single_entry, force_shrink=True)


@pytest.mark.asyncio
async def test_verify_analysis_result_basic_stage1_and_sem07() -> None:
    base_input: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    base_output: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )

    ok_res = await verify_analysis_result_basic(
        base_output,
        expected_dataset_version=str(base_output["dataset_version_used"]),
        input_snapshot=base_input,
    )
    assert ok_res.valid is True
    assert ok_res.result_status == "ok"

    v51_extra = copy.deepcopy(base_output)
    v51_extra["schema_version"] = "5.1"
    v51_extra["ml_future_field"] = {"experimental": True}
    ext_res = await verify_analysis_result_basic(
        v51_extra,
        expected_dataset_version=str(base_output["dataset_version_used"]),
        input_snapshot=base_input,
    )
    assert ext_res.valid is True

    v60_bad = copy.deepcopy(base_output)
    v60_bad["schema_version"] = "6.0"
    bad_stage1 = await verify_analysis_result_basic(
        v60_bad,
        expected_dataset_version=str(base_output["dataset_version_used"]),
        input_snapshot=base_input,
    )
    assert bad_stage1.valid is False
    assert bad_stage1.result_status == "invalid"
    assert bad_stage1.error_code == ErrorCode.ML_INVALID_RESPONSE

    bad_ds = await verify_analysis_result_basic(
        base_output,
        expected_dataset_version="2099.99-other-v1",
        input_snapshot=base_input,
    )
    assert bad_ds.valid is False
    assert bad_ds.result_status == "invalid"
    assert bad_ds.error_code == ErrorCode.DATASET_VERSION_UNAVAILABLE
