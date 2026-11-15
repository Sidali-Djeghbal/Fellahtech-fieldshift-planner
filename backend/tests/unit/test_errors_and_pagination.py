"""Unit & FastAPI contract tests for M2 ErrorCode, ErrorEnvelope, 422->400 override, and cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import httpx
import jsonschema
import pytest
import yaml
from fastapi import Depends, Query
from pydantic import BaseModel, Field
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.core.config import Settings
from app.core.errors import ERROR_HTTP_STATUS, ErrorCode, FieldShiftError
from app.core.pagination import (
    PaginationParams,
    decode_cursor,
    encode_cursor,
    get_pagination_params,
    slice_keyset_page,
)
from app.main import DeprecationHeadersMiddleware, create_app
from app.schemas.common import ErrorEnvelope, PaginatedResponse, WarningCode, WarningNotice

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://fieldshift:secret@db:5432/fieldshift",
        DB_PASSWORD="secret",
        ML_DATASET_DB_URL="postgresql://ml_reader:secret2@db:5432/fieldshift",
        ML_READER_PASSWORD="secret2",
        JWT_SECRET_KEY="jwt-secret-key-for-tests-32-chars!!",
        ML_SERVICE_API_KEY="ml-secret-key",
        CORS_ALLOWED_ORIGINS="http://localhost:5173",
    )


def _openapi_error_envelope_validator() -> jsonschema.Draft202012Validator:
    openapi = yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))
    openapi_resource = Resource.from_contents(openapi, default_specification=DRAFT202012)
    registry = Registry().with_resource("openapi.yaml", openapi_resource)
    schema = {"$ref": "openapi.yaml#/components/schemas/ErrorEnvelope"}
    return jsonschema.Draft202012Validator(schema, registry=registry)


class _StrictSecretPayload(BaseModel):
    password: str = Field(min_length=8)
    count: int = Field(ge=1, le=10)


class _DummyPydanticCheck(BaseModel):
    value: int = Field(gt=0)


def test_error_code_enum_and_status_parity_with_openapi() -> None:
    openapi = yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))
    spec_codes = openapi["components"]["schemas"]["ErrorCode"]["enum"]
    assert len(spec_codes) == 19
    assert [c.value for c in ErrorCode] == spec_codes
    assert set(ERROR_HTTP_STATUS.keys()) == set(ErrorCode)
    assert ERROR_HTTP_STATUS[ErrorCode.INVALID_INPUT] == 400
    assert ERROR_HTTP_STATUS[ErrorCode.UNAUTHORIZED] == 401
    assert ERROR_HTTP_STATUS[ErrorCode.GUEST_LIMIT_REACHED] == 403
    assert ERROR_HTTP_STATUS[ErrorCode.NOT_FOUND] == 404
    assert ERROR_HTTP_STATUS[ErrorCode.CONFLICT] == 409
    assert ERROR_HTTP_STATUS[ErrorCode.CATALOG_VERSION_MISMATCH] == 409
    assert ERROR_HTTP_STATUS[ErrorCode.OUTSIDE_DEMO_BOUNDARY] == 422
    assert ERROR_HTTP_STATUS[ErrorCode.INSUFFICIENT_DATA] == 422
    assert ERROR_HTTP_STATUS[ErrorCode.RATE_LIMIT_EXCEEDED] == 429
    assert ERROR_HTTP_STATUS[ErrorCode.INTERNAL_ERROR] == 500
    assert ERROR_HTTP_STATUS[ErrorCode.ML_UNAVAILABLE] == 502
    assert ERROR_HTTP_STATUS[ErrorCode.SERVICE_UNAVAILABLE] == 503
    assert ERROR_HTTP_STATUS[ErrorCode.DATASET_UNAVAILABLE] == 503
    assert ERROR_HTTP_STATUS[ErrorCode.ML_TIMEOUT] == 504
    assert ERROR_HTTP_STATUS[ErrorCode.JOB_TIMEOUT] == 504


def test_warning_notice_and_paginated_response_serialization() -> None:
    notice_without_fields = WarningNotice(
        code=WarningCode.DEMO_PARCEL_UNVERIFIED,
        message="Parcel F1 awaits field survey",
    )
    dumped_no_fields = notice_without_fields.model_dump()
    assert dumped_no_fields == {
        "code": "DEMO_PARCEL_UNVERIFIED",
        "message": "Parcel F1 awaits field survey",
    }

    notice_with_fields = WarningNotice(
        code=WarningCode.MVP_OUTSIDE_COVERAGE,
        message="Outside Guelma",
        fields=["F2"],
    )
    assert notice_with_fields.model_dump() == {
        "code": "MVP_OUTSIDE_COVERAGE",
        "message": "Outside Guelma",
        "fields": ["F2"],
    }

    page = PaginatedResponse[int](items=[1, 2], next_cursor="abc", has_more=True)
    assert page.model_dump() == {"items": [1, 2], "next_cursor": "abc", "has_more": True}


@pytest.mark.asyncio
async def test_all_19_error_codes_and_validation_override_in_fastapi() -> None:
    app = create_app(settings=_test_settings())
    validator = _openapi_error_envelope_validator()

    @app.get("/_test/error/{code}")
    async def raise_code(code: ErrorCode) -> dict[str, str]:
        headers = (
            {"Retry-After": "12"}
            if code in {ErrorCode.RATE_LIMIT_EXCEEDED, ErrorCode.SERVICE_UNAVAILABLE}
            else None
        )
        raise FieldShiftError(
            code,
            f"Triggered {code.value}",
            details=[{"reason": "test_trigger"}],
            headers=headers,
        )

    @app.post("/_test/validate")
    async def validate_body(
        payload: _StrictSecretPayload,
        page: Annotated[PaginationParams, Depends(get_pagination_params)],
        flag: Annotated[int, Query(ge=1)] = 1,
    ) -> dict[str, Any]:
        return {"count": payload.count, "limit": page.limit, "flag": flag}

    @app.get("/_test/pydantic-direct")
    async def direct_pydantic() -> dict[str, Any]:
        _DummyPydanticCheck.model_validate({"value": -5})
        return {"ok": True}

    @app.get("/_test/crash")
    async def crash() -> dict[str, str]:
        raise RuntimeError("sensitive internal db connection failure")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for code in ErrorCode:
            resp = await client.get(
                f"/_test/error/{code.value}",
                headers={"X-Request-Id": f"req-{code.value}"},
            )
            assert resp.status_code == ERROR_HTTP_STATUS[code]
            assert resp.headers["x-request-id"] == f"req-{code.value}"
            if code in {ErrorCode.RATE_LIMIT_EXCEEDED, ErrorCode.SERVICE_UNAVAILABLE}:
                assert resp.headers.get("retry-after") == "12"
            body = resp.json()
            validator.validate(body)
            envelope = ErrorEnvelope.model_validate(body)
            assert envelope.error.code == code
            assert envelope.error.request_id == f"req-{code.value}"

        # FastAPI 422 RequestValidationError MUST become 400 INVALID_INPUT (never 422)
        invalid_resp = await client.post(
            "/_test/validate?limit=101&flag=0",
            json={"password": "pw123", "count": 99},
            headers={"X-Request-Id": "req-val-400"},
        )
        assert invalid_resp.status_code == 400
        assert invalid_resp.headers["x-request-id"] == "req-val-400"
        invalid_json = invalid_resp.json()
        validator.validate(invalid_json)
        assert invalid_json["error"]["code"] == "INVALID_INPUT"
        assert "pw123" not in str(invalid_json["error"]["details"])
        assert len(invalid_json["error"]["details"]) >= 3

        # Direct Pydantic ValidationError inside route -> 400 INVALID_INPUT
        direct_resp = await client.get("/_test/pydantic-direct")
        assert direct_resp.status_code == 400
        validator.validate(direct_resp.json())
        assert direct_resp.json()["error"]["code"] == "INVALID_INPUT"

        # Unknown route -> 404 NOT_FOUND with ErrorEnvelope
        not_found = await client.get("/_test/does-not-exist")
        assert not_found.status_code == 404
        validator.validate(not_found.json())
        assert not_found.json()["error"]["code"] == "NOT_FOUND"
        assert "x-request-id" in not_found.headers

        # Wrong method -> 405 wrapped in ErrorEnvelope
        wrong_method = await client.delete("/api/v1/health")
        assert wrong_method.status_code == 405
        validator.validate(wrong_method.json())
        assert wrong_method.json()["error"]["code"] == "INVALID_INPUT"

        # Unhandled exception -> 500 INTERNAL_ERROR without traceback/secret leak + X-Request-Id
        crash_resp = await client.get(
            "/_test/crash",
            headers={"X-Request-Id": "req-crash-500"},
        )
        assert crash_resp.status_code == 500
        assert crash_resp.headers.get("x-request-id") == "req-crash-500"
        crash_json = crash_resp.json()
        validator.validate(crash_json)
        assert crash_json["error"]["code"] == "INTERNAL_ERROR"
        assert crash_json["error"]["request_id"] == "req-crash-500"
        assert "RuntimeError" not in crash_json["error"]["message"]
        assert "sensitive" not in crash_json["error"]["message"]

        # Unhandled exception without client header still mints UUID in BOTH header and body
        crash_minted = await client.get("/_test/crash")
        assert crash_minted.status_code == 500
        minted_hdr = crash_minted.headers.get("x-request-id")
        assert minted_hdr
        assert crash_minted.json()["error"]["request_id"] == minted_hdr


@pytest.mark.asyncio
async def test_deprecation_middleware_hook_emits_headers_when_configured() -> None:
    inner = create_app(settings=_test_settings())
    wrapped = DeprecationHeadersMiddleware(
        inner,
        route_headers={"/api/v1/health": ("true", "Wed, 31 Dec 2026 23:59:59 GMT")},
    )
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.headers.get("deprecation") == "true"
        assert resp.headers.get("sunset") == "Wed, 31 Dec 2026 23:59:59 GMT"


def test_cursor_encode_decode_and_tamper_rejection() -> None:
    token = encode_cursor({"id": 42, "created_at": "2026-11-15T00:00:00+00:00"})
    decoded = decode_cursor(token, required_keys=("id", "created_at"))
    assert decoded == {"id": 42, "created_at": "2026-11-15T00:00:00+00:00"}

    bad_cursors = [
        "",
        "x" * 513,
        "!!!not-base64!!!",
        "e30=",  # trailing '=' makes it non-canonical unpadded form
        "W10",  # JSON array "[]"
        "e30",  # valid "{}" but missing required_keys
        "bnVsbA",  # JSON null
    ]
    for bad in bad_cursors:
        with pytest.raises(FieldShiftError) as exc_info:
            decode_cursor(bad, required_keys=("id",))
        assert exc_info.value.code == ErrorCode.INVALID_INPUT
        assert exc_info.value.status_code == 400


def test_slice_keyset_page_behavior() -> None:
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    items, next_cursor, has_more = slice_keyset_page(
        rows,
        limit=2,
        cursor_key_fn=lambda row: {"id": row["id"]},
    )
    assert items == [{"id": 1}, {"id": 2}]
    assert has_more is True
    assert next_cursor is not None
    assert decode_cursor(next_cursor, required_keys=("id",)) == {"id": 2}

    exact_items, exact_cursor, exact_more = slice_keyset_page(
        rows[:2],
        limit=2,
        cursor_key_fn=lambda row: {"id": row["id"]},
    )
    assert exact_items == [{"id": 1}, {"id": 2}]
    assert exact_more is False
    assert exact_cursor is None
