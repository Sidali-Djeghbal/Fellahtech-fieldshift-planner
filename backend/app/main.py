"""FastAPI application factory, lifespan configuration, CORS, and X-Request-Id middleware."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.logging import configure_logging

_REQUEST_ID_HEADER = b"x-request-id"


class RequestIdMiddleware:
    """Pure ASGI middleware propagating or minting X-Request-Id across requests and logs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        incoming_id: str | None = None
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() == _REQUEST_ID_HEADER:
                candidate = raw_value.decode("latin-1").strip()
                if candidate and len(candidate) <= 128:
                    incoming_id = candidate
                break

        request_id = incoming_id or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers = [(k, v) for k, v in headers if k.lower() != _REQUEST_ID_HEADER]
                headers.append((_REQUEST_ID_HEADER, request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            structlog.contextvars.clear_contextvars()


def _resolve_cors_origins(settings: Settings | None) -> list[str]:
    if settings is not None:
        return settings.cors_origins_list
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(
    settings: Settings | None = None,
    *,
    settings_loader: Callable[[], Settings] | None = None,
) -> FastAPI:
    """Create the FastAPI ASGI application with fail-fast startup settings validation."""

    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        resolved = (
            settings
            if settings is not None
            else (settings_loader() if settings_loader is not None else Settings())
        )
        fastapi_app.state.settings = resolved
        logger = structlog.get_logger("app.startup")
        await logger.ainfo(
            "backend_initialized",
            app_env=resolved.APP_ENV,
            ml_provider_mode=resolved.ML_PROVIDER_MODE,
        )
        yield

    fastapi_app = FastAPI(
        title="FieldShift Planner API",
        version="3.2.0",
        lifespan=lifespan,
    )
    if settings is not None:
        fastapi_app.state.settings = settings

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_app.add_middleware(RequestIdMiddleware)

    # M0 scaffold liveness stub; replaced in M11 with full PG/Redis/dataset/breaker probe.
    @fastapi_app.get("/api/v1/health", tags=["System"])
    async def health_liveness_stub(check: str = "live") -> dict[str, str]:
        return {"status": "ok", "check": check, "phase": "m0_scaffold"}

    return fastapi_app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()


__all__ = ["RequestIdMiddleware", "app", "create_app"]
