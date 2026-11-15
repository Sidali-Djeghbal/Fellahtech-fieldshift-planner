"""Optional ASGI HTTP server wrapping `MockMLAdapter` (`profiles: ["dev", "test"]`, `E2`)."""

from __future__ import annotations

import gzip
import json
import os
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from app.ml_client.base import MLClientError, MLInvalidPayloadError
from app.ml_client.mock_adapter import MockMLAdapter


def _build_error_json_response(exc: MLClientError) -> Response:
    if isinstance(exc, MLInvalidPayloadError) and exc.raw_body is not None:
        return Response(
            content=exc.raw_body,
            status_code=exc.status_code or 200,
            media_type="application/json",
        )
    status_code = exc.status_code if exc.status_code is not None else 503
    headers: dict[str, str] = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.ml_error_code or "INTERNAL_ERROR",
                "message": exc.message,
            }
        },
        headers=headers,
    )


def create_mock_ml_app(
    *,
    accepted_api_keys: Sequence[str] | None = None,
    adapter: MockMLAdapter | None = None,
) -> FastAPI:
    """Create the standalone mock External ML ASGI HTTP application (`ENDPOINTS B.10`)."""
    mock_app = FastAPI(title="FieldShift Mock ML Service", version="2.1.0")

    def _allowed_keys() -> set[str]:
        if accepted_api_keys is not None:
            return {k for k in accepted_api_keys if k}
        keys: set[str] = set()
        for env_name in ("ML_SERVICE_API_KEY", "ML_SERVICE_PREVIOUS_API_KEY"):
            val = os.getenv(env_name, "").strip()
            if val:
                keys.add(val)
        return keys

    mock_app.state.mock_adapter = adapter or MockMLAdapter()
    mock_app.state.accepted_api_keys = accepted_api_keys
    mock_app.state.catalog_page_size = None

    def _require_ml_key(x_ml_api_key: str | None) -> JSONResponse | None:
        allowed = _allowed_keys()
        if not allowed:
            return None
        if not x_ml_api_key or x_ml_api_key not in allowed:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTH_FAILED",
                        "message": "Invalid or missing X-ML-API-Key.",
                    }
                },
            )
        return None

    def _apply_header_fault_if_present(
        ml_adapter: MockMLAdapter,
        fault_header: str | None,
    ) -> JSONResponse | None:
        if fault_header and fault_header.strip():
            mode = fault_header.strip()
            if mode not in ml_adapter.SUPPORTED_FAULT_MODES:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {"code": "INVALID_INPUT", "message": f"Unknown fault {mode}"}
                    },
                )
            ml_adapter.set_fault_mode(mode)
        return None

    @mock_app.post("/v1/analyze")
    async def analyze_endpoint(
        request: Request,
        x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
        idempotency_key: str = Header(default="", alias="Idempotency-Key"),
        content_encoding: str | None = Header(default=None, alias="Content-Encoding"),
        x_mock_fault: str | None = Header(default=None, alias="X-Mock-Fault"),
    ) -> Response:
        auth_err = _require_ml_key(x_ml_api_key)
        if auth_err is not None:
            return auth_err

        ml_adapter: MockMLAdapter = request.app.state.mock_adapter
        header_err = _apply_header_fault_if_present(ml_adapter, x_mock_fault)
        if header_err is not None:
            return header_err

        raw_body = await request.body()
        if content_encoding and "gzip" in content_encoding.lower():
            try:
                raw_body = gzip.decompress(raw_body)
            except OSError:
                return JSONResponse(
                    status_code=400,
                    content={"error": {"code": "INVALID_INPUT", "message": "Invalid gzip body."}},
                )

        try:
            payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_INPUT", "message": "Malformed JSON input."}},
            )

        try:
            result = await ml_adapter.analyze(payload, idempotency_key=idempotency_key)
        except MLClientError as exc:
            return _build_error_json_response(exc)

        return JSONResponse(status_code=200, content=result)

    @mock_app.get("/v1/catalog")
    async def catalog_endpoint(
        request: Request,
        x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
        cursor: str | None = Query(default=None),
        limit: int | None = Query(default=None, ge=1, le=100),
        x_mock_fault: str | None = Header(default=None, alias="X-Mock-Fault"),
    ) -> Response:
        auth_err = _require_ml_key(x_ml_api_key)
        if auth_err is not None:
            return auth_err

        ml_adapter: MockMLAdapter = request.app.state.mock_adapter
        header_err = _apply_header_fault_if_present(ml_adapter, x_mock_fault)
        if header_err is not None:
            return header_err

        try:
            catalog = await ml_adapter.get_catalog()
        except MLClientError as exc:
            return _build_error_json_response(exc)

        # Omit null optional fields (e.g. `synced_at`) and default `has_more` per CropCatalog.
        raw = catalog.model_dump(mode="json", exclude_none=True)
        raw.setdefault("has_more", False)
        raw.setdefault("next_cursor", None)
        configured_page_size: int | None = getattr(
            request.app.state, "catalog_page_size", None
        )
        if limit is not None or cursor is not None or configured_page_size is not None:
            crops = list(raw["crops"])
            offset = int(cursor) if cursor and cursor.isdigit() else 0
            page_size = (
                limit
                if limit is not None
                else (configured_page_size if configured_page_size is not None else len(crops))
            )
            sliced = crops[offset : offset + page_size]
            next_offset = offset + page_size
            has_more = next_offset < len(crops)
            raw["crops"] = sliced if sliced else crops[:1]
            raw["has_more"] = has_more
            raw["next_cursor"] = str(next_offset) if has_more else None
        return JSONResponse(status_code=200, content=raw)

    @mock_app.get("/v1/health")
    async def health_endpoint(
        request: Request,
        x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
        x_mock_fault: str | None = Header(default=None, alias="X-Mock-Fault"),
    ) -> Response:
        auth_err = _require_ml_key(x_ml_api_key)
        if auth_err is not None:
            return auth_err

        ml_adapter: MockMLAdapter = request.app.state.mock_adapter
        header_err = _apply_header_fault_if_present(ml_adapter, x_mock_fault)
        if header_err is not None:
            return header_err

        health = await ml_adapter.get_health()
        status_code = 200 if health.reachable else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "reachable": health.reachable,
                "status": health.status,
                "ml_engine_version": health.ml_engine_version,
                "dataset_versions_supported": list(health.dataset_versions_supported),
            },
        )

    return mock_app


app = create_mock_ml_app()

__all__ = ["app", "create_mock_ml_app"]
