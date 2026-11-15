"""Non-blocking Redis worker heartbeat helpers shared by API health probes and WorkerRunner."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.exceptions import RedisError

from app.ml_client.manager import AsyncRedisStatusStore

WORKER_HEARTBEAT_REDIS_PREFIX = "worker:heartbeat:"

_LOGGER = structlog.get_logger(__name__)


async def publish_worker_heartbeat(
    redis_client: Any,
    *,
    worker_id: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> bool:
    """Write expiring Redis worker heartbeat key (`worker:heartbeat:<worker_id>`)."""
    if not isinstance(redis_client, AsyncRedisStatusStore):
        return False
    ts = now if now is not None else datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    key = f"{WORKER_HEARTBEAT_REDIS_PREFIX}{worker_id}"
    try:
        await redis_client.set(key, ts.isoformat().encode("utf-8"), ex=max(5, int(ttl_seconds)))
        return True
    except (RedisError, OSError) as exc:
        await _LOGGER.awarning(
            "worker_heartbeat_publish_failed",
            worker_id=worker_id,
            error_type=type(exc).__name__,
        )
        return False


async def clear_worker_heartbeat(redis_client: Any, *, worker_id: str) -> None:
    """Remove worker heartbeat key immediately on graceful daemon shutdown."""
    delete_fn = getattr(redis_client, "delete", None)
    if delete_fn is None:
        return
    with contextlib.suppress(RedisError, OSError):
        await delete_fn(f"{WORKER_HEARTBEAT_REDIS_PREFIX}{worker_id}")


async def count_active_workers(redis_client: Any) -> int:
    """Count distinct active worker daemons using non-blocking Redis `SCAN`."""
    scan_fn = getattr(redis_client, "scan", None)
    if scan_fn is None:
        return 0
    seen: set[str] = set()
    cursor: int | bytes | str = 0
    try:
        while True:
            cursor, batch = await scan_fn(
                cursor=cursor,
                match=f"{WORKER_HEARTBEAT_REDIS_PREFIX}*",
                count=100,
            )
            for item in batch:
                key = item.decode("utf-8") if isinstance(item, (bytes, bytearray)) else str(item)
                seen.add(key)
            if int(cursor) == 0:
                break
    except (RedisError, OSError, ValueError):
        return 0
    return len(seen)
