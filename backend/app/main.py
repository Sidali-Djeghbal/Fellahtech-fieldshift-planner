"""FastAPI application factory, lifespan configuration, CORS, and X-Request-Id middleware."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.v1 import api_v1_router
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import AsyncRedisLike, create_redis_client
from app.db.session import create_db_engine, create_sessionmaker
from app.ml_client.manager import MLProviderManager

_REQUEST_ID_HEADER = b"x-request-id"
_DEPRECATION_HEADER = b"deprecation"
_SUNSET_HEADER = b"sunset"


class DeprecationHeadersMiddleware:
    """Pure ASGI middleware hook for ADR-7 Deprecation/Sunset headers (# TODO(OQ-8))."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        route_headers: dict[str, tuple[str, str | None]] | None = None,
    ) -> None:
        self.app = app
        # TODO(OQ-8): Populate route -> (Deprecation, Sunset) schedule once ADR-7 window is set.
        self.route_headers = route_headers or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.route_headers:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        deprecation_rule = self.route_headers.get(path)
        if deprecation_rule is None:
            await self.app(scope, receive, send)
            return

        deprecation_val, sunset_val = deprecation_rule

        async def send_with_deprecation(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((_DEPRECATION_HEADER, deprecation_val.encode("latin-1")))
                if sunset_val:
                    headers.append((_SUNSET_HEADER, sunset_val.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_deprecation)


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
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id
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

        owned_redis: AsyncRedisLike | None = None
        if getattr(fastapi_app.state, "redis", None) is None:
            owned_redis = create_redis_client(resolved)
            fastapi_app.state.redis = owned_redis

        owned_engine: AsyncEngine | None = None
        if getattr(fastapi_app.state, "db_engine", None) is None:
            owned_engine = create_db_engine(resolved, role="api")
            fastapi_app.state.db_engine = owned_engine
        if getattr(fastapi_app.state, "db_sessionmaker", None) is None:
            fastapi_app.state.db_sessionmaker = create_sessionmaker(fastapi_app.state.db_engine)

        owned_ml_manager: MLProviderManager | None = None
        if getattr(fastapi_app.state, "ml_provider_manager", None) is None:
            owned_ml_manager = MLProviderManager(
                resolved,
                redis_client=fastapi_app.state.redis,
            )
            fastapi_app.state.ml_provider_manager = owned_ml_manager

        logger = structlog.get_logger("app.startup")
        await logger.ainfo(
            "backend_initialized",
            app_env=resolved.APP_ENV,
            ml_provider_mode=resolved.ML_PROVIDER_MODE,
        )
        try:
            yield
        finally:
            if owned_ml_manager is not None:
                await owned_ml_manager.aclose()
            if owned_redis is not None:
                await owned_redis.aclose()
            if owned_engine is not None:
                await owned_engine.dispose()

    fastapi_app = FastAPI(
        title="FieldShift Planner API",
        version="3.2.0",
        lifespan=lifespan,
    )
    if settings is not None:
        fastapi_app.state.settings = settings

    register_exception_handlers(fastapi_app)

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_app.add_middleware(DeprecationHeadersMiddleware)
    fastapi_app.add_middleware(RequestIdMiddleware)

    fastapi_app.include_router(api_v1_router)

    return fastapi_app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()


__all__ = ["DeprecationHeadersMiddleware", "RequestIdMiddleware", "app", "create_app"]
