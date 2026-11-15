"""Worker container Docker healthcheck verifying Postgres & Redis connectivity."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.config import Settings
from app.core.rate_limit import create_redis_client
from app.db.session import create_db_engine


async def check_worker_health(settings: Settings | None = None) -> bool:
    """Verify worker dependencies (`PostgreSQL SELECT 1` and `Redis PING`)."""
    cfg = settings if settings is not None else Settings()
    engine = create_db_engine(cfg, role="api")
    redis_client = create_redis_client(cfg)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        pong = await redis_client.ping()
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
