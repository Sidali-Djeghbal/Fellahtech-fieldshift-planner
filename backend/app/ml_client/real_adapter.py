"""HTTP client adapter (`RealMLAdapter`) implementing the External ML service contract (`B.10`)."""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from typing import Any

import httpx
import structlog

from app.core.config import Settings
from app.ml_client.base import (
    MLAdapter,
    MLAuthError,
    MLClientError,
    MLHealthResult,
    MLInvalidPayloadError,
    MLTimeoutError,
    MLTransportError,
    ProviderKind,
    classify_ml_http_error,
    validate_contract_def,
)
from app.schemas.catalog import CropItem, MLCatalogPayload

_MAX_CATALOG_PAGES = 50


def _try_parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except (ValueError, UnicodeDecodeError):
        return None


class RealMLAdapter(MLAdapter):
    """Concrete async HTTP client for External ML (`/v1/analyze`, `/v1/catalog`, `/v1/health`)."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._base_url = settings.ML_SERVICE_URL.rstrip("/")
        self._primary_api_key = settings.ML_SERVICE_API_KEY
        self._previous_api_key = settings.ML_SERVICE_PREVIOUS_API_KEY.strip()
        self._analyze_timeout = float(settings.ML_TIMEOUT_SECONDS)
        self._catalog_timeout = float(settings.ML_CATALOG_TIMEOUT_SECONDS)
        self._health_timeout = float(settings.ML_HEALTH_TIMEOUT_SECONDS)
        self._logger = structlog.get_logger("app.ml_client.real")

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                transport=transport,
            )
            self._owns_client = True

    @property
    def provider_name(self) -> ProviderKind:
        return "real_ml"

    def _resolve_target(self, path: str) -> str:
        if str(self._client.base_url):
            return path
        return f"{self._base_url}{path}"

    async def _request_with_key_rotation(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        target = self._resolve_target(path)

        async def _send(api_key: str) -> httpx.Response:
            req_headers = dict(headers) if headers is not None else {}
            req_headers["X-ML-API-Key"] = api_key
            try:
                return await self._client.request(
                    method,
                    target,
                    headers=req_headers,
                    content=content,
                    params=params,
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise MLTimeoutError(
                    f"External ML request to {path} timed out after {timeout:.1f}s."
                ) from exc
            except httpx.HTTPError as exc:
                raise MLTransportError(
                    f"External ML transport failure on {path}: {type(exc).__name__}"
                ) from exc

        response = await _send(self._primary_api_key)
        if (
            response.status_code in (401, 403)
            and self._previous_api_key
            and self._previous_api_key != self._primary_api_key
        ):
            await self._logger.awarning(
                "ml_api_key_rotation_retry",
                path=path,
                status_code=response.status_code,
            )
            response = await _send(self._previous_api_key)
        return response

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        """POST `{ML_SERVICE_URL}/v1/analyze` with exact JSON bytes and optional gzip."""
        raw_bytes = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        wire_bytes = raw_bytes
        if compress:
            wire_bytes = gzip.compress(raw_bytes)
            headers["Content-Encoding"] = "gzip"

        response = await self._request_with_key_rotation(
            "POST",
            "/v1/analyze",
            timeout=self._analyze_timeout,
            headers=headers,
            content=wire_bytes,
        )
        if response.status_code != 200:
            parsed_err = _try_parse_json(response)
            err = classify_ml_http_error(
                response.status_code,
                body=parsed_err,
                retry_after_header=response.headers.get("retry-after"),
            )
            if isinstance(err, MLAuthError):
                await self._logger.acritical(
                    "ml_authentication_failed",
                    path="/v1/analyze",
                    status_code=response.status_code,
                )
            elif response.status_code == 400:
                await self._logger.acritical(
                    "ml_contract_rejected",
                    path="/v1/analyze",
                    status_code=response.status_code,
                    ml_error_code=err.ml_error_code,
                )
            raise err

        parsed = _try_parse_json(response)
        if not isinstance(parsed, dict):
            raise MLInvalidPayloadError(
                "External ML /v1/analyze returned malformed or non-object JSON.",
                raw_body=response.text[:4096],
                status_code=response.status_code,
            )
        return parsed

    async def get_catalog(self) -> MLCatalogPayload:
        """GET `{ML_SERVICE_URL}/v1/catalog` following cursor pages if present."""
        all_crops: list[CropItem] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        first_page: MLCatalogPayload | None = None

        for _ in range(_MAX_CATALOG_PAGES):
            params = {"cursor": cursor} if cursor is not None else None
            response = await self._request_with_key_rotation(
                "GET",
                "/v1/catalog",
                timeout=self._catalog_timeout,
                headers={"Accept": "application/json"},
                params=params,
            )
            if response.status_code != 200:
                parsed_err = _try_parse_json(response)
                err = classify_ml_http_error(
                    response.status_code,
                    body=parsed_err,
                    retry_after_header=response.headers.get("retry-after"),
                )
                if isinstance(err, MLAuthError):
                    await self._logger.acritical(
                        "ml_authentication_failed",
                        path="/v1/catalog",
                        status_code=response.status_code,
                    )
                raise err

            parsed = _try_parse_json(response)
            if not isinstance(parsed, dict):
                raise MLInvalidPayloadError(
                    "External ML /v1/catalog returned malformed JSON.",
                    raw_body=response.text[:4096],
                    status_code=response.status_code,
                )

            schema_errors = validate_contract_def(parsed, "CropCatalog")
            if schema_errors:
                raise MLInvalidPayloadError(
                    f"External ML /v1/catalog failed schema validation: {schema_errors[0]}",
                    raw_body=response.text[:4096],
                    status_code=response.status_code,
                )

            page = MLCatalogPayload.model_validate(parsed)
            if first_page is None:
                first_page = page
            elif page.catalog_version != first_page.catalog_version:
                raise MLInvalidPayloadError(
                    "External ML /v1/catalog pagination mixed distinct catalog versions.",
                    status_code=response.status_code,
                )
            all_crops.extend(page.crops)

            if not page.has_more or not page.next_cursor:
                break
            if page.next_cursor in seen_cursors:
                raise MLInvalidPayloadError(
                    "External ML /v1/catalog returned repeating pagination cursor.",
                    status_code=response.status_code,
                )
            seen_cursors.add(page.next_cursor)
            cursor = page.next_cursor
        else:
            raise MLInvalidPayloadError(
                "External ML /v1/catalog exceeded maximum pagination page cap.",
                status_code=200,
            )

        assert first_page is not None
        return first_page.model_copy(
            update={"crops": all_crops, "next_cursor": None, "has_more": False}
        )

    async def get_health(self) -> MLHealthResult:
        """GET `{ML_SERVICE_URL}/v1/health` converting transport/HTTP failures safely."""
        try:
            response = await self._request_with_key_rotation(
                "GET",
                "/v1/health",
                timeout=self._health_timeout,
                headers={"Accept": "application/json"},
            )
        except MLClientError as exc:
            await self._logger.awarning(
                "ml_health_probe_failed",
                error_code=exc.ml_error_code,
                message=exc.message,
            )
            return MLHealthResult(
                reachable=False,
                status="unavailable",
                provider="real_ml",
                error=exc.ml_error_code or "ML_UNAVAILABLE",
            )

        if response.status_code != 200:
            err = classify_ml_http_error(
                response.status_code,
                body=_try_parse_json(response),
                retry_after_header=response.headers.get("retry-after"),
            )
            if isinstance(err, MLAuthError):
                await self._logger.acritical(
                    "ml_authentication_failed",
                    path="/v1/health",
                    status_code=response.status_code,
                )
            else:
                await self._logger.awarning(
                    "ml_health_unhealthy_status",
                    status_code=response.status_code,
                    error_code=err.ml_error_code,
                )
            return MLHealthResult(
                reachable=False,
                status="unavailable",
                provider="real_ml",
                error=err.ml_error_code or f"HTTP_{response.status_code}",
            )

        parsed = _try_parse_json(response)
        if not isinstance(parsed, dict):
            return MLHealthResult(
                reachable=False,
                status="invalid_response",
                provider="real_ml",
                error="ML_INVALID_RESPONSE",
            )

        raw_status = str(parsed.get("status", "ok"))
        reachable = bool(parsed.get("reachable", raw_status in {"ok", "healthy", "degraded"}))
        raw_engine = parsed.get("ml_engine_version")
        raw_datasets = parsed.get("dataset_versions_supported", ())
        datasets = (
            tuple(str(item) for item in raw_datasets if isinstance(item, str))
            if isinstance(raw_datasets, list)
            else ()
        )
        return MLHealthResult(
            reachable=reachable,
            status=raw_status,
            ml_engine_version=str(raw_engine) if isinstance(raw_engine, str) else None,
            dataset_versions_supported=datasets,
            provider="real_ml",
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
