"""Abstract MLAdapter contract, health snapshots, and ENDPOINTS B.10.4 error hierarchy."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.core.errors import ErrorCode
from app.schemas.catalog import MLCatalogPayload

ProviderKind = Literal["real_ml", "mock_ml"]

_CONTRACTS_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "schema-v5.0.json"


@lru_cache(maxsize=1)
def _load_schema_validator_bundle() -> tuple[str, Registry[Any]]:
    schema_doc: dict[str, Any] = json.loads(_CONTRACTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_id = str(schema_doc.get("$id", "urn:fieldshift:schema"))
    registry: Registry[Any] = Registry().with_resource(
        schema_id,
        Resource.from_contents(schema_doc, default_specification=DRAFT202012),
    )
    return schema_id, registry


def validate_contract_def(payload: Any, def_name: str) -> list[str]:
    """Validate an arbitrary JSON payload against `schema-v5.0.json#/$defs/<def_name>`."""
    schema_id, registry = _load_schema_validator_bundle()
    validator = jsonschema.Draft202012Validator(
        {"$ref": f"{schema_id}#/$defs/{def_name}"},
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    return [
        f"{'.'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    ]


@dataclass(frozen=True, slots=True)
class MLHealthResult:
    """Health response returned by `MLAdapter.get_health()` (`GET {ML_SERVICE_URL}/v1/health`)."""

    reachable: bool
    status: str
    ml_engine_version: str | None = None
    dataset_versions_supported: tuple[str, ...] = ()
    provider: ProviderKind = "real_ml"
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MLProviderSnapshot:
    """Cross-container provider snapshot persisted under Redis key `ml:provider_status`."""

    provider: ProviderKind
    reachable: bool
    status: str
    ml_engine_version: str | None
    dataset_versions_supported: tuple[str, ...]
    checked_at: datetime


class MLClientError(Exception):
    """Structured exception encoding retryability, breaker impact, and ErrorCode mapping."""

    def __init__(
        self,
        message: str,
        *,
        backend_error_code: ErrorCode,
        status_code: int | None = None,
        ml_error_code: str | None = None,
        retry_after_seconds: int | None = None,
        retryable: bool = False,
        trips_breaker: bool = False,
        raw_body: str | None = None,
    ) -> None:
        self.message = message
        self.backend_error_code = backend_error_code
        self.status_code = status_code
        self.ml_error_code = ml_error_code
        self.retry_after_seconds = retry_after_seconds
        self.retryable = retryable
        self.trips_breaker = trips_breaker
        self.raw_body = raw_body
        super().__init__(message)


class MLContractError(MLClientError):
    """ML 400 INVALID_INPUT -> 502 ML_CONTRACT_ERROR (non-retryable, no breaker trip)."""

    def __init__(
        self,
        message: str = "External ML rejected payload contract.",
        *,
        status_code: int | None = 400,
        ml_error_code: str | None = "INVALID_INPUT",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_CONTRACT_ERROR,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=False,
            trips_breaker=False,
        )


class MLAuthError(MLClientError):
    """ML 401/403 AUTH_FAILED after key-rotation retry -> 502 ML_UNAVAILABLE."""

    def __init__(
        self,
        message: str = "External ML authentication failed.",
        *,
        status_code: int | None = 401,
        ml_error_code: str | None = "AUTH_FAILED",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_UNAVAILABLE,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=False,
            trips_breaker=False,
        )


class MLCatalogVersionMismatchError(MLClientError):
    """ML 409 CATALOG_VERSION_MISMATCH -> retry once after catalog sync, else 409."""

    def __init__(
        self,
        message: str = "ML catalog version does not match request.",
        *,
        status_code: int | None = 409,
        ml_error_code: str | None = "CATALOG_VERSION_MISMATCH",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.CATALOG_VERSION_MISMATCH,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=True,
            trips_breaker=False,
        )


class MLDatasetVersionUnavailableError(MLClientError):
    """ML 409/422 DATASET_VERSION_UNAVAILABLE -> 502 DATASET_VERSION_UNAVAILABLE."""

    def __init__(
        self,
        message: str = "External ML does not support the pinned dataset_version.",
        *,
        status_code: int | None = 422,
        ml_error_code: str | None = "DATASET_VERSION_UNAVAILABLE",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.DATASET_VERSION_UNAVAILABLE,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=False,
            trips_breaker=False,
        )


class MLPayloadTooLargeError(MLClientError):
    """ML 413 PAYLOAD_TOO_LARGE -> M8 trims history and retries once, else 500 INTERNAL_ERROR."""

    def __init__(
        self,
        message: str = "ML analysis input payload exceeds upstream size limit.",
        *,
        status_code: int | None = 413,
        ml_error_code: str | None = "PAYLOAD_TOO_LARGE",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.INTERNAL_ERROR,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=True,
            trips_breaker=False,
        )


class MLInsufficientDataError(MLClientError):
    """ML 422 INSUFFICIENT_DATA -> non-retryable, no breaker trip, 422 INSUFFICIENT_DATA."""

    def __init__(
        self,
        message: str = "Supplied field history or inputs are insufficient for prediction.",
        *,
        status_code: int | None = 422,
        ml_error_code: str | None = "INSUFFICIENT_DATA",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.INSUFFICIENT_DATA,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=False,
            trips_breaker=False,
        )


class MLRateLimitError(MLClientError):
    """ML 429 RATE_LIMITED -> optional Retry-After <= 5s retry, no breaker trip, 502."""

    def __init__(
        self,
        message: str = "External ML service rate-limited the request.",
        *,
        status_code: int | None = 429,
        ml_error_code: str | None = "RATE_LIMITED",
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_UNAVAILABLE,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retry_after_seconds=retry_after_seconds,
            retryable=True,
            trips_breaker=False,
        )


class MLDatasetError(MLClientError):
    """ML 500/502 ML_DATASET_ERROR -> non-retryable, TRIPS breaker (+1), 502 ML_DATASET_ERROR."""

    def __init__(
        self,
        message: str = "External ML failed querying PostgreSQL Schema: dataset.",
        *,
        status_code: int | None = 502,
        ml_error_code: str | None = "ML_DATASET_ERROR",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_DATASET_ERROR,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retryable=False,
            trips_breaker=True,
        )


class MLUpstreamServerError(MLClientError):
    """ML 500/502/503 non-dataset outage -> retryable, TRIPS breaker (+1), 502 ML_UNAVAILABLE."""

    def __init__(
        self,
        message: str = "External ML service returned a server error.",
        *,
        status_code: int | None = 503,
        ml_error_code: str | None = "OVERLOADED",
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_UNAVAILABLE,
            status_code=status_code,
            ml_error_code=ml_error_code,
            retry_after_seconds=retry_after_seconds,
            retryable=True,
            trips_breaker=True,
        )


class MLTimeoutError(MLClientError):
    """Network/HTTP timeout -> retryable, TRIPS breaker (+1), 504 ML_TIMEOUT."""

    def __init__(
        self,
        message: str = "External ML service request timed out.",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_TIMEOUT,
            status_code=None,
            ml_error_code="ML_TIMEOUT",
            retryable=True,
            trips_breaker=True,
        )


class MLTransportError(MLClientError):
    """DNS/connect/transport outage -> retryable, TRIPS breaker (+1), 502 ML_UNAVAILABLE."""

    def __init__(
        self,
        message: str = "External ML service could not be reached.",
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_UNAVAILABLE,
            status_code=None,
            ml_error_code="ML_UNAVAILABLE",
            retryable=True,
            trips_breaker=True,
        )


class MLInvalidPayloadError(MLClientError):
    """200 OK payload failed JSON parsing or contract validation -> no breaker trip, 502."""

    def __init__(
        self,
        message: str = "External ML service returned a malformed JSON payload.",
        *,
        raw_body: str | None = None,
        status_code: int | None = 200,
    ) -> None:
        super().__init__(
            message,
            backend_error_code=ErrorCode.ML_INVALID_RESPONSE,
            status_code=status_code,
            ml_error_code="ML_INVALID_RESPONSE",
            retryable=False,
            trips_breaker=False,
            raw_body=raw_body,
        )


def parse_retry_after_header(raw: str | None) -> int | None:
    """Parse integer Retry-After seconds safely without failing on non-numeric values."""
    if raw is None:
        return None
    stripped = raw.strip()
    if stripped.isdigit():
        return int(stripped)
    return None


def _extract_error_fields(body: Any) -> tuple[str | None, str | None]:
    if isinstance(body, Mapping):
        err_obj = body.get("error")
        if isinstance(err_obj, Mapping):
            raw_code = err_obj.get("code")
            raw_msg = err_obj.get("message")
            return (
                str(raw_code) if isinstance(raw_code, str) and raw_code else None,
                str(raw_msg) if isinstance(raw_msg, str) and raw_msg else None,
            )
        raw_code = body.get("code")
        raw_msg = body.get("message") or body.get("detail")
        return (
            str(raw_code) if isinstance(raw_code, str) and raw_code else None,
            str(raw_msg) if isinstance(raw_msg, str) and raw_msg else None,
        )
    return None, None


def classify_ml_http_error(
    status_code: int,
    *,
    body: Any = None,
    retry_after_header: str | None = None,
) -> MLClientError:
    """Map an upstream ML HTTP error response onto the exact ENDPOINTS B.10.4 hierarchy."""
    ml_code, parsed_msg = _extract_error_fields(body)
    retry_after = parse_retry_after_header(retry_after_header)

    if status_code == 400:
        return MLContractError(
            parsed_msg or "External ML rejected request payload (400 INVALID_INPUT).",
            status_code=400,
            ml_error_code=ml_code or "INVALID_INPUT",
        )
    if status_code in (401, 403):
        return MLAuthError(
            parsed_msg or "External ML authentication failed.",
            status_code=status_code,
            ml_error_code=ml_code or "AUTH_FAILED",
        )
    if status_code == 409:
        if ml_code == "DATASET_VERSION_UNAVAILABLE":
            return MLDatasetVersionUnavailableError(
                parsed_msg or "Pinned dataset_version is unavailable on ML service.",
                status_code=409,
                ml_error_code=ml_code,
            )
        return MLCatalogVersionMismatchError(
            parsed_msg or "Requested catalog_version does not match ML catalog.",
            status_code=409,
            ml_error_code=ml_code or "CATALOG_VERSION_MISMATCH",
        )
    if status_code == 413:
        return MLPayloadTooLargeError(
            parsed_msg or "ML request payload exceeded maximum allowed size.",
            status_code=413,
            ml_error_code=ml_code or "PAYLOAD_TOO_LARGE",
        )
    if status_code == 422:
        if ml_code == "DATASET_VERSION_UNAVAILABLE":
            return MLDatasetVersionUnavailableError(
                parsed_msg or "Pinned dataset_version is unavailable on ML service.",
                status_code=422,
                ml_error_code=ml_code,
            )
        return MLInsufficientDataError(
            parsed_msg or "Field data or cropping history is insufficient for optimization.",
            status_code=422,
            ml_error_code=ml_code or "INSUFFICIENT_DATA",
        )
    if status_code == 429:
        return MLRateLimitError(
            parsed_msg or "External ML rate limit exceeded.",
            status_code=429,
            ml_error_code=ml_code or "RATE_LIMITED",
            retry_after_seconds=retry_after,
        )
    if status_code >= 500:
        if ml_code == "ML_DATASET_ERROR":
            return MLDatasetError(
                parsed_msg or "External ML failed querying Schema: dataset.",
                status_code=status_code,
                ml_error_code=ml_code,
            )
        return MLUpstreamServerError(
            parsed_msg or f"External ML upstream error ({status_code}).",
            status_code=status_code,
            ml_error_code=ml_code or ("OVERLOADED" if status_code == 503 else "INTERNAL_ERROR"),
            retry_after_seconds=retry_after,
        )
    return MLContractError(
        parsed_msg or f"Unexpected upstream ML HTTP status {status_code}.",
        status_code=status_code,
        ml_error_code=ml_code or "CONTRACT_ERROR",
    )


class MLAdapter(ABC):
    """Unified interface separating Backend orchestration from Real/Mock ML providers (`ADR-4`)."""

    @property
    @abstractmethod
    def provider_name(self) -> ProviderKind:
        """Canonical provider identifier (`real_ml` or `mock_ml`)."""

    @abstractmethod
    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        """Execute `POST {ML_SERVICE_URL}/v1/analyze` returning unvalidated result JSON dict."""

    @abstractmethod
    async def get_catalog(self) -> MLCatalogPayload:
        """Fetch master `CropCatalog` from `GET {ML_SERVICE_URL}/v1/catalog`."""

    @abstractmethod
    async def get_health(self) -> MLHealthResult:
        """Probe `GET {ML_SERVICE_URL}/v1/health` returning availability & versions."""

    async def aclose(self) -> None:
        """Release underlying HTTP/network resources when shutting down."""
        return None
