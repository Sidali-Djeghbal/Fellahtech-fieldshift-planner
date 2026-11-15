"""Canonical ErrorCode enum, FieldShiftError, and FastAPI global exception handlers."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    """Exact 19 canonical backend error codes from openapi.yaml."""

    INVALID_INPUT = "INVALID_INPUT"
    UNAUTHORIZED = "UNAUTHORIZED"
    GUEST_LIMIT_REACHED = "GUEST_LIMIT_REACHED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    CATALOG_VERSION_MISMATCH = "CATALOG_VERSION_MISMATCH"
    OUTSIDE_DEMO_BOUNDARY = "OUTSIDE_DEMO_BOUNDARY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ML_UNAVAILABLE = "ML_UNAVAILABLE"
    ML_INVALID_RESPONSE = "ML_INVALID_RESPONSE"
    ML_CONTRACT_ERROR = "ML_CONTRACT_ERROR"
    DATASET_VERSION_UNAVAILABLE = "DATASET_VERSION_UNAVAILABLE"
    ML_DATASET_ERROR = "ML_DATASET_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    ML_TIMEOUT = "ML_TIMEOUT"
    JOB_TIMEOUT = "JOB_TIMEOUT"


ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_INPUT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.GUEST_LIMIT_REACHED: status.HTTP_403_FORBIDDEN,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.CATALOG_VERSION_MISMATCH: status.HTTP_409_CONFLICT,
    ErrorCode.OUTSIDE_DEMO_BOUNDARY: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.INSUFFICIENT_DATA: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.RATE_LIMIT_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.ML_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.ML_INVALID_RESPONSE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.ML_CONTRACT_ERROR: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.DATASET_VERSION_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.ML_DATASET_ERROR: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.DATASET_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.ML_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    ErrorCode.JOB_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
}


class FieldShiftError(Exception):
    """Domain error carrying canonical ErrorCode, HTTP status, details, and optional headers."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: list[dict[str, Any]] | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details: list[dict[str, Any]] = list(details) if details is not None else []
        self.status_code = status_code if status_code is not None else ERROR_HTTP_STATUS[code]
        self.headers: dict[str, str] = dict(headers) if headers is not None else {}
        super().__init__(message)


def resolve_request_id(request: Request) -> str | None:
    """Resolve current request_id from ASGI state, structlog contextvars, or header."""
    state_id = getattr(request.state, "request_id", None)
    if isinstance(state_id, str) and state_id:
        return state_id

    ctx_id = structlog.contextvars.get_contextvars().get("request_id")
    if isinstance(ctx_id, str) and ctx_id:
        return ctx_id

    header_id = request.headers.get("x-request-id")
    if header_id:
        trimmed = header_id.strip()
        if trimmed and len(trimmed) <= 128:
            return trimmed
    return None


def build_error_payload(
    *,
    code: ErrorCode,
    message: str,
    details: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build strict ErrorEnvelope JSON dict matching openapi.yaml."""
    return {
        "error": {
            "code": code.value,
            "message": message,
            "details": list(details) if details is not None else [],
            "request_id": request_id,
        }
    }


def _error_response(
    request: Request,
    *,
    code: ErrorCode,
    message: str,
    status_code: int,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = resolve_request_id(request)
    response_headers = dict(headers) if headers is not None else {}
    if request_id is not None:
        response_headers.setdefault("X-Request-Id", request_id)
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        ),
        headers=response_headers,
    )


def _format_pydantic_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for err in errors:
        if not isinstance(err, dict):
            details.append({"field": "", "reason": str(err), "type": "validation_error"})
            continue
        loc = err.get("loc", ())
        field = ".".join(str(part) for part in loc) if isinstance(loc, (list, tuple)) else str(loc)
        details.append(
            {
                "field": field,
                "reason": str(err.get("msg", "Invalid input")),
                "type": str(err.get("type", "validation_error")),
            }
        )
    return details


def _map_http_status_to_error_code(status_code: int) -> ErrorCode:
    mapping = {
        status.HTTP_400_BAD_REQUEST: ErrorCode.INVALID_INPUT,
        status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: ErrorCode.GUEST_LIMIT_REACHED,
        status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
        status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
        status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMIT_EXCEEDED,
        status.HTTP_503_SERVICE_UNAVAILABLE: ErrorCode.SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT: ErrorCode.JOB_TIMEOUT,
    }
    if status_code in mapping:
        return mapping[status_code]
    if 400 <= status_code < 500:
        return ErrorCode.INVALID_INPUT
    return ErrorCode.INTERNAL_ERROR


async def fieldshift_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Serialize FieldShiftError into canonical ErrorEnvelope."""
    assert isinstance(exc, FieldShiftError)
    return _error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        headers=exc.headers,
    )


async def request_validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Override FastAPI 422 RequestValidationError with HTTP 400 INVALID_INPUT (Pitfall #3)."""
    assert isinstance(exc, RequestValidationError)
    return _error_response(
        request,
        code=ErrorCode.INVALID_INPUT,
        message="Request validation failed.",
        status_code=status.HTTP_400_BAD_REQUEST,
        details=_format_pydantic_errors(exc.errors()),
    )


async def pydantic_validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map unhandled Pydantic ValidationError raised during request handling to 400."""
    assert isinstance(exc, ValidationError)
    return _error_response(
        request,
        code=ErrorCode.INVALID_INPUT,
        message="Input validation failed.",
        status_code=status.HTTP_400_BAD_REQUEST,
        details=_format_pydantic_errors(exc.errors()),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Serialize framework Starlette HTTPException responses into ErrorEnvelope."""
    assert isinstance(exc, StarletteHTTPException)
    code = _map_http_status_to_error_code(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else "Request error."
    headers = {str(k): str(v) for k, v in exc.headers.items()} if exc.headers else None
    return _error_response(
        request,
        code=code,
        message=message,
        status_code=exc.status_code,
        details=[],
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Mask unhandled server exceptions as 500 INTERNAL_ERROR without leaking stack traces."""
    logger = structlog.get_logger("app.errors")
    request_id = resolve_request_id(request)
    await logger.aexception(
        "unhandled_server_error",
        request_id=request_id,
        exc_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
    )
    return _error_response(
        request,
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal server error occurred.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=[],
    )


def register_exception_handlers(fastapi_app: FastAPI) -> None:
    """Attach canonical global exception handlers onto the FastAPI application."""
    fastapi_app.add_exception_handler(FieldShiftError, fieldshift_error_handler)
    fastapi_app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    fastapi_app.add_exception_handler(ValidationError, pydantic_validation_error_handler)
    fastapi_app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    fastapi_app.add_exception_handler(Exception, unhandled_exception_handler)
