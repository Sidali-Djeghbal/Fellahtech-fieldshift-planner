"""FastAPI dependency injection for settings, DB sessions, Redis, Auth, and rate limits."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.rate_limit import (
    AsyncRedisLike,
    build_crud_check,
    build_poll_check,
    check_rate_limits,
)
from app.core.security import decode_access_token, hash_token
from app.ml_client.manager import AsyncRedisStatusStore, MLProviderManager
from app.repositories import user as user_repo


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated request principal representing either a user or a guest session."""

    user_id: int | None = None
    family_id: uuid.UUID | None = None
    guest_token_hash: str | None = None

    @property
    def is_user(self) -> bool:
        return self.user_id is not None

    @property
    def is_guest(self) -> bool:
        return self.guest_token_hash is not None


def get_settings(request: Request) -> Settings:
    """Return initialized Settings instance from FastAPI application state."""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_redis(request: Request) -> AsyncRedisLike | None:
    """Return Redis async client from FastAPI application state."""
    return getattr(request.app.state, "redis", None)


def get_ml_provider_manager(request: Request) -> MLProviderManager:
    """Return initialized MLProviderManager from FastAPI application state."""
    manager = getattr(request.app.state, "ml_provider_manager", None)
    if isinstance(manager, MLProviderManager):
        return manager
    settings = get_settings(request)
    raw_redis = getattr(request.app.state, "redis", None)
    status_redis = raw_redis if isinstance(raw_redis, AsyncRedisStatusStore) else None
    manager = MLProviderManager(settings, redis_client=status_redis)
    request.app.state.ml_provider_manager = manager
    return manager


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession bound to the app sessionmaker with automatic error rollback."""
    sessionmaker = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


SettingsDep = Annotated[Settings, Depends(get_settings)]
RedisDep = Annotated[AsyncRedisLike | None, Depends(get_redis)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
MLProviderManagerDep = Annotated[MLProviderManager, Depends(get_ml_provider_manager)]


def _extract_bearer_token(request: Request) -> str | None:
    raw_header = request.headers.get("authorization")
    if raw_header is None:
        return None
    parts = raw_header.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise FieldShiftError(
            ErrorCode.UNAUTHORIZED,
            "Invalid Authorization header format. Expected Bearer token.",
        )
    return parts[1].strip()


async def authenticate_bearer_user(
    request: Request,
    settings: Settings,
    db: AsyncSession,
) -> Principal:
    """Validate Bearer HS256 JWT and verify user row still exists in PostgreSQL."""
    raw_token = _extract_bearer_token(request)
    if raw_token is None:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Missing Bearer authorization token.")

    claims = decode_access_token(raw_token, settings)
    user = await user_repo.get_user_by_id(db, claims.user_id)
    if user is None:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "User account no longer exists.")

    structlog.contextvars.bind_contextvars(user_id=user.id)
    return Principal(user_id=user.id, family_id=claims.family_id, guest_token_hash=None)


async def authenticate_guest_session(
    request: Request,
    db: AsyncSession,
) -> Principal:
    """Validate `X-Guest-Token` header against unexpired `public.guest_sessions` SHA-256 hash."""
    raw_guest = request.headers.get("x-guest-token")
    if raw_guest is None or not raw_guest.strip():
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Missing X-Guest-Token header.")

    token_hash = hash_token(raw_guest.strip())
    guest = await user_repo.get_active_guest_session(
        db,
        guest_token_hash=token_hash,
        now=datetime.now(UTC),
    )
    if guest is None:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid or expired guest session.")

    structlog.contextvars.bind_contextvars(guest_token_prefix=token_hash[:16])
    return Principal(user_id=None, family_id=None, guest_token_hash=token_hash)


async def enforce_crud_rate_limit(
    *,
    principal: Principal,
    settings: Settings,
    redis_client: AsyncRedisLike | None,
) -> None:
    """Enforce per-minute CRUD bucket (`60` user / `30` guest) with fail-closed Redis."""
    check = build_crud_check(
        settings=settings,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    await check_rate_limits(redis_client, [check], fail_closed=settings.REDIS_FAIL_CLOSED)


async def enforce_poll_rate_limit(
    *,
    principal: Principal,
    settings: Settings,
    redis_client: AsyncRedisLike | None,
) -> None:
    """Enforce dedicated `120 req/min` polling rate limit (`GET /analysis/requests/{id}`)."""
    check = build_poll_check(
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    await check_rate_limits(redis_client, [check], fail_closed=settings.REDIS_FAIL_CLOSED)


async def require_bearer_no_rate_limit(
    request: Request,
    settings: SettingsDep,
    db: DbSessionDep,
) -> Principal:
    """Require valid Bearer JWT without applying the per-minute CRUD throttle."""
    return await authenticate_bearer_user(request, settings, db)


async def require_bearer_user(
    principal: Annotated[Principal, Depends(require_bearer_no_rate_limit)],
    settings: SettingsDep,
    redis_client: RedisDep,
) -> Principal:
    """Require valid Bearer JWT and enforce `RATE_LIMIT_CRUD_PER_MIN`."""
    await enforce_crud_rate_limit(
        principal=principal,
        settings=settings,
        redis_client=redis_client,
    )
    return principal


async def require_guest_no_rate_limit(
    request: Request,
    db: DbSessionDep,
) -> Principal:
    """Require valid `X-Guest-Token` session without applying the CRUD throttle."""
    return await authenticate_guest_session(request, db)


async def require_guest_session(
    principal: Annotated[Principal, Depends(require_guest_no_rate_limit)],
    settings: SettingsDep,
    redis_client: RedisDep,
) -> Principal:
    """Require valid `X-Guest-Token` session and enforce `GUEST_BURST_PER_MIN`."""
    await enforce_crud_rate_limit(
        principal=principal,
        settings=settings,
        redis_client=redis_client,
    )
    return principal


async def require_actor_no_rate_limit(
    request: Request,
    settings: SettingsDep,
    db: DbSessionDep,
) -> Principal:
    """Require either Bearer JWT or `X-Guest-Token` without charging CRUD throttle."""
    if request.headers.get("authorization") is not None:
        return await authenticate_bearer_user(request, settings, db)
    if request.headers.get("x-guest-token") is not None:
        return await authenticate_guest_session(request, db)
    raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Authentication credentials were not provided.")


async def require_actor(
    principal: Annotated[Principal, Depends(require_actor_no_rate_limit)],
    settings: SettingsDep,
    redis_client: RedisDep,
) -> Principal:
    """Require either Bearer JWT or `X-Guest-Token` and enforce actor CRUD throttle."""
    await enforce_crud_rate_limit(
        principal=principal,
        settings=settings,
        redis_client=redis_client,
    )
    return principal


BearerNoRateLimitDep = Annotated[Principal, Depends(require_bearer_no_rate_limit)]
BearerPrincipalDep = Annotated[Principal, Depends(require_bearer_user)]
GuestNoRateLimitDep = Annotated[Principal, Depends(require_guest_no_rate_limit)]
GuestPrincipalDep = Annotated[Principal, Depends(require_guest_session)]
ActorNoRateLimitDep = Annotated[Principal, Depends(require_actor_no_rate_limit)]
ActorPrincipalDep = Annotated[Principal, Depends(require_actor)]
