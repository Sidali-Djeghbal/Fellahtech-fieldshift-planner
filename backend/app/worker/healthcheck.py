"""Worker container Docker healthcheck verifying Postgres & Redis connectivity."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.rate_limit import create_redis_client
from app.db.session import create_db_engine

_HEALTHCHECK_TIMEOUT_SECONDS = 3.0


async def _ping_postgres(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def check_worker_health(settings: Settings | None = None) -> bool:
    """Verify worker dependencies (`PostgreSQL SELECT 1` and `Redis PING`)."""
    cfg = settings if settings is not None else Settings()
    engine = create_db_engine(cfg, role="api")
    redis_client = create_redis_client(cfg)
    try:
        await asyncio.wait_for(_ping_postgres(engine), timeout=_HEALTHCHECK_TIMEOUT_SECONDS)
        pong = await asyncio.wait_for(
            redis_client.ping(),
            timeout=_HEALTHCHECK_TIMEOUT_SECONDS,
        )
        return bool(pong)
    finally:
        await redis_client.aclose()
        await engine.dispose()


def main() -> int:
    try:
        healthy = asyncio.run(check_worker_health())
    except Exception:
        return 1
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
