"""Async SQLAlchemy engine sizing and pinned connection helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def calculate_pool_budget(
    settings: Settings,
    *,
    role: Literal["api", "worker"] = "api",
) -> tuple[int, int]:
    """Return `(pool_size, max_overflow)` sized to avoid bulkhead/heartbeat starvation."""
    if role == "worker":
        pool_size = settings.WORKER_CONCURRENCY + settings.ML_MAX_CONCURRENT_REQUESTS
        max_overflow = 6
        assert pool_size + max_overflow >= settings.worker_db_pool_min_total
        return pool_size, max_overflow
    return 10, 10


def create_db_engine(
    settings: Settings,
    *,
    role: Literal["api", "worker"] = "api",
) -> AsyncEngine:
    """Create a configured async SQLAlchemy PostGIS engine using asyncpg."""
    pool_size, max_overflow = calculate_pool_budget(settings, role=role)
    return create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=False,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a non-expiring async sessionmaker for request/worker transactions."""
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def pinned_connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Yield a dedicated connection kept pinned for session-level PostgreSQL advisory locks."""
    conn = await engine.connect()
    try:
        yield conn
    finally:
        await conn.close()
