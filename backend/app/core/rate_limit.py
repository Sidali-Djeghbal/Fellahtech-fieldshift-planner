"""Redis Lua sliding-window rate limiter, proxy IP extraction, and guest quota cache sync."""

from __future__ import annotations

import hashlib
import ipaddress
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, cast

import redis.asyncio as redis_async
import structlog
from fastapi import Request
from prometheus_client import Counter
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.models.analysis import AnalysisRequest
from app.models.demo import GuestSession
from app.models.farm import Farm

POLL_RATE_LIMIT_PER_MIN = 120
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_QUARTERS_PER_ANALYSIS = 4
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

REDIS_ERRORS_TOTAL = Counter(
    "redis_errors_total",
    "Total Redis backend failures observed on request or quota sync paths",
    labelnames=("operation",),
)

# Interpolated integer two-bucket sliding window preventing 2x boundary bursts (IMPL-001).
LUA_SLIDING_WINDOW_ACQUIRE = """
local prefix = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now_override = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local now = now_override
if now == nil or now <= 0 then
    local t = redis.call('TIME')
    now = tonumber(t[1])
end

local elapsed = now % window
local curr_bucket = now - elapsed
local prev_bucket = curr_bucket - window
local prev_remaining = window - elapsed

local curr_key = prefix .. ':' .. tostring(curr_bucket)
local prev_key = prefix .. ':' .. tostring(prev_bucket)

local prev_count = tonumber(redis.call('GET', prev_key) or '0')
local curr_count = tonumber(redis.call('GET', curr_key) or '0')

local weighted_scaled = prev_count * prev_remaining + (curr_count + cost) * window
local limit_scaled = limit * window

if weighted_scaled > limit_scaled then
    local wait_s = 1
    if (curr_count + cost) <= limit and prev_count > 0 then
        local excess_scaled = weighted_scaled - limit_scaled
        wait_s = math.floor((excess_scaled + prev_count - 1) / prev_count)
    elseif curr_count > 0 and cost <= limit then
        local needed = curr_count + cost - limit
        local elapsed_next = math.floor((needed * window + curr_count - 1) / curr_count)
        wait_s = prev_remaining + elapsed_next
    else
        wait_s = window
    end
    if wait_s < 1 then
        wait_s = 1
    end
    return {0, curr_key, curr_count, wait_s}
end

local new_val = redis.call('INCRBY', curr_key, cost)
if new_val == cost or redis.call('TTL', curr_key) < 0 then
    redis.call('EXPIRE', curr_key, ttl)
end
return {1, curr_key, new_val, 0}
"""

# EXISTS-guarded clamped DECRBY preserving TTL or deleting at <= 0 (Audit Hardening #3).
LUA_CLAMPED_DECRBY_IF_EXISTS = """
local key = KEYS[1]
local delta = tonumber(ARGV[1])
if delta <= 0 then
    return tonumber(redis.call('GET', key) or '0')
end
if redis.call('EXISTS', key) == 0 then
    return 0
end
local curr = tonumber(redis.call('GET', key) or '0')
local nxt = curr - delta
if nxt <= 0 then
    redis.call('DEL', key)
    return 0
end
redis.call('SET', key, nxt, 'KEEPTTL')
return nxt
"""

LUA_HYDRATE_GUEST_QUOTA = """
local key = KEYS[1]
local val = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
redis.call('SET', key, val, 'EX', ttl, 'NX')
return tonumber(redis.call('GET', key) or tostring(val))
"""

LUA_INCREMENT_GUEST_QUOTA = """
local key = KEYS[1]
local delta = tonumber(ARGV[1])
local fallback_total = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
if redis.call('EXISTS', key) == 1 then
    local nxt = redis.call('INCRBY', key, delta)
    if redis.call('TTL', key) < 0 then
        redis.call('EXPIRE', key, ttl)
    end
    return nxt
end
redis.call('SET', key, fallback_total, 'EX', ttl)
return fallback_total
"""


class AsyncRedisLike(Protocol):
    """Minimal async Redis protocol covering rate limiting and guest quota operations."""

    def get(self, name: str) -> Any: ...

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> Any: ...

    def delete(self, *names: str) -> Any: ...

    def ping(self) -> Any: ...

    def aclose(self) -> Any: ...


class RateLimitBucket(StrEnum):
    """All 6 normative Redis sliding-window rate-limit buckets."""

    GUEST_CREATE_IP = "guest_create_ip"
    GUEST_CRUD = "guest_crud"
    USER_CRUD = "user_crud"
    POLL = "poll"
    ANALYSIS_USER = "analysis_user"
    ANALYSIS_IP = "analysis_ip"


@dataclass(frozen=True, slots=True)
class RateLimitCheck:
    """Single sliding-window rate-limit check specification."""

    bucket: RateLimitBucket
    key_prefix: str
    window_seconds: int
    limit: int
    cost: int = 1


@dataclass(frozen=True, slots=True)
class RateLimitGrant:
    """Exact incremented Redis bucket key returned for non-burning rollback compensation."""

    bucket: RateLimitBucket
    bucket_key: str
    cost: int
    new_count: int


def sha256_hex(value: str) -> str:
    """Return lowercase SHA-256 hex digest of an identifier or IP without keeping raw PII."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_sha256_digest(token_hash: str) -> str:
    if not _SHA256_HEX_RE.match(token_hash):
        raise ValueError("Expected lowercase 64-character SHA-256 hex digest")
    return token_hash


def guest_token_prefix16(guest_token_hash: str) -> str:
    """Return non-PII 16-char digest prefix from a validated 64-char guest token SHA-256."""
    return _validate_sha256_digest(guest_token_hash)[:16]


def guest_quota_key(guest_token_hash: str) -> str:
    """Return Redis key mirroring durable 7-day guest quarter usage."""
    return f"guest_quota:{_validate_sha256_digest(guest_token_hash)}:quarters"


def _parse_ip(raw: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        return parsed.ipv4_mapped
    return parsed


def _is_trusted_proxy(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    trusted_networks: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    return any(addr in net for net in trusted_networks)


def extract_client_ip(
    remote_addr: str | None,
    x_forwarded_for: str | None,
    trusted_networks: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> str:
    """Extract client IP, trusting X-Forwarded-For strictly via trusted CIDR rightmost walk."""
    peer_ip = _parse_ip(remote_addr)
    if peer_ip is None:
        return "0.0.0.0"

    if not trusted_networks or not _is_trusted_proxy(peer_ip, trusted_networks):
        return str(peer_ip)

    if not x_forwarded_for:
        return str(peer_ip)

    hops = [part.strip() for part in x_forwarded_for.split(",") if part.strip()]
    if not hops:
        return str(peer_ip)

    leftmost_valid: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    for raw_hop in reversed(hops):
        hop_ip = _parse_ip(raw_hop)
        if hop_ip is None:
            return str(peer_ip)
        leftmost_valid = hop_ip
        if not _is_trusted_proxy(hop_ip, trusted_networks):
            return str(hop_ip)

    return str(leftmost_valid) if leftmost_valid is not None else str(peer_ip)


def get_client_ip_from_request(request: Request, settings: Settings) -> str:
    """Resolve client IP from FastAPI Request using Settings.trusted_proxy_networks."""
    remote_addr = request.client.host if request.client is not None else None
    forwarded_for = request.headers.get("x-forwarded-for")
    return extract_client_ip(remote_addr, forwarded_for, settings.trusted_proxy_networks)


def build_guest_create_ip_check(client_ip: str, settings: Settings) -> RateLimitCheck:
    """Build per-IP/hour check (`GUEST_CREATE_PER_IP_HOUR`) for POST /auth/guest."""
    return RateLimitCheck(
        bucket=RateLimitBucket.GUEST_CREATE_IP,
        key_prefix=f"rl:guest_create:ip:{sha256_hex(client_ip)}",
        window_seconds=_SECONDS_PER_HOUR,
        limit=settings.GUEST_CREATE_PER_IP_HOUR,
        cost=1,
    )


def build_crud_check(
    *,
    settings: Settings,
    user_id: int | None = None,
    guest_token_hash: str | None = None,
) -> RateLimitCheck:
    """Build per-minute CRUD rate check for registered user (60) or guest session (30)."""
    if (user_id is None) == (guest_token_hash is None):
        raise ValueError("Exactly one of user_id or guest_token_hash must be provided")
    if user_id is not None:
        return RateLimitCheck(
            bucket=RateLimitBucket.USER_CRUD,
            key_prefix=f"rl:crud:u:{user_id}",
            window_seconds=_SECONDS_PER_MINUTE,
            limit=settings.RATE_LIMIT_CRUD_PER_MIN,
            cost=1,
        )
    assert guest_token_hash is not None
    return RateLimitCheck(
        bucket=RateLimitBucket.GUEST_CRUD,
        key_prefix=f"rl:crud:g:{guest_token_prefix16(guest_token_hash)}",
        window_seconds=_SECONDS_PER_MINUTE,
        limit=settings.GUEST_BURST_PER_MIN,
        cost=1,
    )


def build_poll_check(
    *,
    user_id: int | None = None,
    guest_token_hash: str | None = None,
) -> RateLimitCheck:
    """Build dedicated 120 req/min poll check for GET /analysis/requests/{request_id}."""
    if (user_id is None) == (guest_token_hash is None):
        raise ValueError("Exactly one of user_id or guest_token_hash must be provided")
    if user_id is not None:
        actor_key = f"u:{user_id}"
    else:
        assert guest_token_hash is not None
        actor_key = f"g:{guest_token_prefix16(guest_token_hash)}"
    return RateLimitCheck(
        bucket=RateLimitBucket.POLL,
        key_prefix=f"rl:poll:{actor_key}",
        window_seconds=_SECONDS_PER_MINUTE,
        limit=POLL_RATE_LIMIT_PER_MIN,
        cost=1,
    )


def build_analysis_checks(
    *,
    client_ip: str,
    quota_units: int,
    settings: Settings,
    user_id: int | None = None,
) -> list[RateLimitCheck]:
    """Build hourly quarter-weighted rate checks for POST /analysis admission."""
    if quota_units not in (1, _QUARTERS_PER_ANALYSIS):
        raise ValueError(f"Unsupported analysis quota_units={quota_units!r}; expected 1 or 4")

    checks: list[RateLimitCheck] = []
    if user_id is not None:
        checks.append(
            RateLimitCheck(
                bucket=RateLimitBucket.ANALYSIS_USER,
                key_prefix=f"rl:analysis:u:{user_id}",
                window_seconds=_SECONDS_PER_HOUR,
                limit=settings.RATE_LIMIT_ANALYSIS_PER_HOUR * _QUARTERS_PER_ANALYSIS,
                cost=quota_units,
            )
        )
    checks.append(
        RateLimitCheck(
            bucket=RateLimitBucket.ANALYSIS_IP,
            key_prefix=f"rl:analysis:ip:{sha256_hex(client_ip)}",
            window_seconds=_SECONDS_PER_HOUR,
            limit=settings.ANALYSIS_PER_IP_HOUR * _QUARTERS_PER_ANALYSIS,
            cost=quota_units,
        )
    )
    return checks


async def _handle_redis_outage(
    *,
    operation: str,
    bucket_name: str,
    fail_closed: bool,
    exc: RedisError,
) -> None:
    logger = structlog.get_logger("app.rate_limit")
    REDIS_ERRORS_TOTAL.labels(operation=operation).inc()
    if fail_closed:
        await logger.acritical(
            "redis_rate_limit_unavailable",
            operation=operation,
            bucket=bucket_name,
            error_type=type(exc).__name__,
        )
        raise FieldShiftError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Rate limiting service temporarily unavailable.",
            details=[{"reason": "redis_unavailable", "operation": operation}],
            headers={"Retry-After": "5"},
        ) from exc

    await logger.awarning(
        "redis_rate_limit_fail_open",
        operation=operation,
        bucket=bucket_name,
        error_type=type(exc).__name__,
    )


async def decrement_key_if_exists(
    redis_client: AsyncRedisLike,
    *,
    key: str,
    delta: int,
) -> int:
    """Decrement a Redis integer key only if it exists, clamping >= 0 or deleting (no TTL = -1)."""
    if delta <= 0:
        return 0
    result = await redis_client.eval(LUA_CLAMPED_DECRBY_IF_EXISTS, 1, key, str(int(delta)))
    return int(result)


async def rollback_rate_limits(
    redis_client: AsyncRedisLike,
    grants: Sequence[RateLimitGrant],
) -> None:
    """Best-effort rollback of exact bucket keys incremented during aborted admission."""
    if not grants:
        return
    logger = structlog.get_logger("app.rate_limit")
    for grant in reversed(grants):
        try:
            await decrement_key_if_exists(
                redis_client,
                key=grant.bucket_key,
                delta=grant.cost,
            )
        except RedisError as exc:
            REDIS_ERRORS_TOTAL.labels(operation="rollback_rate_limit").inc()
            await logger.awarning(
                "redis_rate_limit_rollback_failed",
                bucket=grant.bucket.value,
                error_type=type(exc).__name__,
            )


async def check_rate_limits(
    redis_client: AsyncRedisLike | None,
    checks: Sequence[RateLimitCheck],
    *,
    fail_closed: bool = True,
    now_override: int | None = None,
) -> list[RateLimitGrant]:
    """Execute atomic sliding-window rate checks, rolling back prior grants on any failure."""
    if not checks:
        return []

    if redis_client is None:
        await _handle_redis_outage(
            operation="rate_limit",
            bucket_name=checks[0].bucket.value,
            fail_closed=fail_closed,
            exc=RedisError("Redis client is not initialized"),
        )
        return []

    grants: list[RateLimitGrant] = []
    override_arg = int(now_override) if now_override is not None and now_override > 0 else 0

    for check in checks:
        if check.cost <= 0 or check.window_seconds <= 0 or check.limit <= 0:
            raise ValueError(f"Invalid rate limit check parameters: {check}")
        ttl_seconds = check.window_seconds * 2 + 60
        try:
            raw_res = await redis_client.eval(
                LUA_SLIDING_WINDOW_ACQUIRE,
                1,
                check.key_prefix,
                str(check.window_seconds),
                str(check.limit),
                str(check.cost),
                str(override_arg),
                str(ttl_seconds),
            )
        except RedisError as exc:
            await rollback_rate_limits(redis_client, grants)
            await _handle_redis_outage(
                operation="rate_limit",
                bucket_name=check.bucket.value,
                fail_closed=fail_closed,
                exc=exc,
            )
            return []

        allowed = int(raw_res[0])
        raw_bucket_key = raw_res[1]
        bucket_key = (
            raw_bucket_key.decode("utf-8")
            if isinstance(raw_bucket_key, bytes)
            else str(raw_bucket_key)
        )
        count_val = int(raw_res[2])
        retry_after = max(1, int(raw_res[3])) if len(raw_res) > 3 else 1

        if allowed != 1:
            await rollback_rate_limits(redis_client, grants)
            raise FieldShiftError(
                ErrorCode.RATE_LIMIT_EXCEEDED,
                "Rate limit exceeded. Retry later.",
                details=[
                    {
                        "bucket": check.bucket.value,
                        "limit": check.limit,
                        "window_seconds": check.window_seconds,
                    }
                ],
                headers={"Retry-After": str(retry_after)},
            )

        grants.append(
            RateLimitGrant(
                bucket=check.bucket,
                bucket_key=bucket_key,
                cost=check.cost,
                new_count=count_val,
            )
        )

    return grants


async def get_or_hydrate_guest_quarters(
    db: AsyncSession,
    redis_client: AsyncRedisLike | None,
    *,
    guest_token_hash: str,
    now: datetime | None = None,
    lock_pg_row: bool = True,
    fail_closed: bool = True,
) -> tuple[int, int]:
    """Read guest quarter usage from Redis or hydrate atomically from PostgreSQL on cache miss.

    Returns `(used_quarters, remaining_ttl_seconds)`.
    Must be called inside an active transaction when `lock_pg_row=True` (serializing quota checks).
    """
    key = guest_quota_key(guest_token_hash)
    current_now = now or datetime.now(UTC)

    guest_stmt = select(GuestSession).where(GuestSession.guest_token == guest_token_hash)
    if lock_pg_row:
        guest_stmt = guest_stmt.with_for_update()
    guest_session = (await db.execute(guest_stmt)).scalar_one_or_none()
    if guest_session is None or guest_session.expires_at <= current_now:
        raise FieldShiftError(
            ErrorCode.UNAUTHORIZED,
            "Invalid or expired guest session.",
        )

    ttl_seconds = max(1, int((guest_session.expires_at - current_now).total_seconds()))

    if redis_client is None:
        await _handle_redis_outage(
            operation="guest_quota_cache",
            bucket_name="guest_quota",
            fail_closed=fail_closed,
            exc=RedisError("Redis client is not initialized"),
        )
    else:
        try:
            raw_cached = await redis_client.get(key)
            if raw_cached is not None:
                return int(raw_cached), ttl_seconds
        except RedisError as exc:
            await _handle_redis_outage(
                operation="guest_quota_cache",
                bucket_name="guest_quota",
                fail_closed=fail_closed,
                exc=exc,
            )

    sum_stmt = (
        select(func.coalesce(func.sum(AnalysisRequest.quota_units), 0))
        .select_from(AnalysisRequest)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(Farm.guest_session_token == guest_token_hash)
    )
    used_pg = int((await db.execute(sum_stmt)).scalar_one())

    if redis_client is None:
        return used_pg, ttl_seconds

    try:
        hydrated = await redis_client.eval(
            LUA_HYDRATE_GUEST_QUOTA,
            1,
            key,
            str(used_pg),
            str(ttl_seconds),
        )
        return int(hydrated), ttl_seconds
    except RedisError as exc:
        await _handle_redis_outage(
            operation="guest_quota_cache",
            bucket_name="guest_quota",
            fail_closed=fail_closed,
            exc=exc,
        )
        return used_pg, ttl_seconds


async def increment_guest_quarters(
    redis_client: AsyncRedisLike,
    *,
    guest_token_hash: str,
    delta: int,
    fallback_total: int,
    ttl_seconds: int,
) -> int:
    """Increment cached guest quarter count after durable PostgreSQL INSERT commits."""
    key = guest_quota_key(guest_token_hash)
    result = await redis_client.eval(
        LUA_INCREMENT_GUEST_QUOTA,
        1,
        key,
        str(int(delta)),
        str(int(fallback_total)),
        str(max(1, int(ttl_seconds))),
    )
    return int(result)


async def refund_guest_quarters(
    redis_client: AsyncRedisLike,
    *,
    guest_token_hash: str,
    delta: int,
) -> int:
    """Clamped EXISTS-guarded decrement for guest quota rollbacks or refunds."""
    key = guest_quota_key(guest_token_hash)
    return await decrement_key_if_exists(redis_client, key=key, delta=delta)


async def sync_guest_quota_after_refund(
    redis_client: AsyncRedisLike | None,
    *,
    guest_token_hash: str,
    delta: int,
) -> None:
    """Best-effort Redis sync after worker commits PostgreSQL `quota_units = 0` (IMPL-001 §5)."""
    if redis_client is None or delta <= 0:
        return
    logger = structlog.get_logger("app.rate_limit")
    try:
        await refund_guest_quarters(
            redis_client,
            guest_token_hash=guest_token_hash,
            delta=delta,
        )
    except RedisError as exc:
        REDIS_ERRORS_TOTAL.labels(operation="worker_quota_sync").inc()
        await logger.awarning(
            "redis_quota_sync_failed",
            error_type=type(exc).__name__,
        )


def create_redis_client(settings: Settings) -> redis_async.Redis:
    """Create lazy async Redis client bound to configured REDIS_URL."""
    return cast(
        "redis_async.Redis",
        redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False),
    )
