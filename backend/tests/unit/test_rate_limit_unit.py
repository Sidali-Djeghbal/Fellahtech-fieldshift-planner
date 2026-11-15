"""Unit tests for proxy IP extraction, PII-safe 6-bucket keys, and fail-closed outage handling."""

from __future__ import annotations

import ipaddress
from types import SimpleNamespace
from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.rate_limit import (
    POLL_RATE_LIMIT_PER_MIN,
    REDIS_ERRORS_TOTAL,
    RateLimitBucket,
    build_analysis_checks,
    build_crud_check,
    build_guest_create_ip_check,
    build_poll_check,
    check_rate_limits,
    extract_client_ip,
    get_client_ip_from_request,
    guest_quota_key,
    sha256_hex,
    sync_guest_quota_after_refund,
)


def _test_settings(*, trusted_proxy_cidrs: str = "") -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://fieldshift:secret@db:5432/fieldshift",
        DB_PASSWORD="secret",
        ML_DATASET_DB_URL="postgresql://ml_reader:secret2@db:5432/fieldshift",
        ML_READER_PASSWORD="secret2",
        JWT_SECRET_KEY="jwt-secret-key-for-tests-32-chars!!",
        ML_SERVICE_API_KEY="ml-secret-key",
        TRUSTED_PROXY_CIDRS=trusted_proxy_cidrs,
    )


class _BrokenRedisTransport:
    """Minimal broken transport raising RedisConnectionError to verify 503 fail-closed behavior."""

    async def get(self, name: str) -> Any:
        raise RedisConnectionError("connection refused")

    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        raise RedisConnectionError("connection refused")

    async def delete(self, *names: str) -> Any:
        raise RedisConnectionError("connection refused")

    async def ping(self) -> Any:
        raise RedisConnectionError("connection refused")

    async def aclose(self) -> None:
        return None


def test_extract_client_ip_trusted_proxy_cidrs() -> None:
    empty_nets: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()
    # Default TRUSTED_PROXY_CIDRS="": spoofed X-Forwarded-For MUST be ignored.
    assert extract_client_ip("203.0.113.5", "198.51.100.77", empty_nets) == "203.0.113.5"

    trusted = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
    )
    # Direct untrusted client spoofing X-Forwarded-For -> ignored.
    assert extract_client_ip("203.0.113.5", "10.0.0.2, 198.51.100.77", trusted) == "203.0.113.5"

    # Trusted proxy forwarding X-Forwarded-For with prepended spoof -> rightmost untrusted hop wins.
    assert extract_client_ip("172.18.0.5", "1.2.3.4, 198.51.100.77", trusted) == "198.51.100.77"

    # Multi-proxy chain -> skips trusted hops from right until client IP.
    assert (
        extract_client_ip("10.1.0.4", "1.2.3.4, 198.51.100.77, 172.18.0.5", trusted)
        == "198.51.100.77"
    )

    # IPv4-mapped IPv6 peer normalized cleanly.
    assert extract_client_ip("::ffff:172.18.0.5", "198.51.100.77", trusted) == "198.51.100.77"

    # Malformed X-Forwarded-For falls back to trusted peer IP cleanly.
    assert extract_client_ip("172.18.0.5", "not-an-ip", trusted) == "172.18.0.5"
    assert extract_client_ip(None, None, trusted) == "0.0.0.0"

    settings = _test_settings(trusted_proxy_cidrs="172.16.0.0/12")
    fake_request = SimpleNamespace(
        client=SimpleNamespace(host="172.20.0.3"),
        headers={"x-forwarded-for": "9.9.9.9, 198.51.100.88"},
    )
    assert get_client_ip_from_request(fake_request, settings) == "198.51.100.88"  # type: ignore[arg-type]


def test_six_bucket_pii_safe_key_builders_and_raw_token_guard() -> None:
    settings = _test_settings()
    raw_ip = "203.0.113.9"
    raw_guest = "gst_0123456789abcdef0123456789abcdef"
    guest_hash = sha256_hex(raw_guest)

    c_guest_create = build_guest_create_ip_check(raw_ip, settings)
    assert c_guest_create.bucket == RateLimitBucket.GUEST_CREATE_IP
    assert c_guest_create.limit == 5
    assert c_guest_create.window_seconds == 3600
    assert raw_ip not in c_guest_create.key_prefix
    assert c_guest_create.key_prefix == f"rl:guest_create:ip:{sha256_hex(raw_ip)}"

    c_guest_crud = build_crud_check(settings=settings, guest_token_hash=guest_hash)
    assert c_guest_crud.bucket == RateLimitBucket.GUEST_CRUD
    assert c_guest_crud.limit == 30
    assert c_guest_crud.window_seconds == 60
    assert c_guest_crud.key_prefix == f"rl:crud:g:{guest_hash[:16]}"
    assert raw_guest not in c_guest_crud.key_prefix

    c_user_crud = build_crud_check(settings=settings, user_id=42)
    assert c_user_crud.bucket == RateLimitBucket.USER_CRUD
    assert c_user_crud.limit == 60
    assert c_user_crud.key_prefix == "rl:crud:u:42"

    c_poll_u = build_poll_check(user_id=42)
    assert c_poll_u.bucket == RateLimitBucket.POLL
    assert c_poll_u.limit == POLL_RATE_LIMIT_PER_MIN == 120
    assert c_poll_u.key_prefix == "rl:poll:u:42"

    c_poll_g = build_poll_check(guest_token_hash=guest_hash)
    assert c_poll_g.key_prefix == f"rl:poll:g:{guest_hash[:16]}"

    analysis_user_checks = build_analysis_checks(
        client_ip=raw_ip,
        quota_units=4,
        settings=settings,
        user_id=7,
    )
    assert len(analysis_user_checks) == 2
    assert analysis_user_checks[0].bucket == RateLimitBucket.ANALYSIS_USER
    assert analysis_user_checks[0].limit == 40
    assert analysis_user_checks[0].cost == 4
    assert analysis_user_checks[0].key_prefix == "rl:analysis:u:7"
    assert analysis_user_checks[1].bucket == RateLimitBucket.ANALYSIS_IP
    assert analysis_user_checks[1].limit == 60
    assert analysis_user_checks[1].cost == 4
    assert analysis_user_checks[1].key_prefix == f"rl:analysis:ip:{sha256_hex(raw_ip)}"

    what_if_guest_checks = build_analysis_checks(
        client_ip=raw_ip,
        quota_units=1,
        settings=settings,
        user_id=None,
    )
    assert len(what_if_guest_checks) == 1
    assert what_if_guest_checks[0].cost == 1

    with pytest.raises(ValueError):
        guest_quota_key(raw_guest)
    with pytest.raises(ValueError):
        build_crud_check(settings=settings, guest_token_hash=raw_guest)


@pytest.mark.asyncio
async def test_redis_outage_fails_closed_503_with_retry_after_and_counter() -> None:
    settings = _test_settings()
    check = build_guest_create_ip_check("198.51.100.1", settings)
    before = REDIS_ERRORS_TOTAL.labels(operation="rate_limit")._value.get()

    with pytest.raises(FieldShiftError) as exc_info:
        await check_rate_limits(_BrokenRedisTransport(), [check], fail_closed=True)

    assert exc_info.value.code == ErrorCode.SERVICE_UNAVAILABLE
    assert exc_info.value.status_code == 503
    assert exc_info.value.headers.get("Retry-After") == "5"
    after = REDIS_ERRORS_TOTAL.labels(operation="rate_limit")._value.get()
    assert after == before + 1

    # Explicit REDIS_FAIL_CLOSED=false override degrades to pass-through with WARNING.
    open_grants = await check_rate_limits(_BrokenRedisTransport(), [check], fail_closed=False)
    assert open_grants == []

    # Worker refund sync catches RedisError without raising so PG quota commit stays safe.
    sync_before = REDIS_ERRORS_TOTAL.labels(operation="worker_quota_sync")._value.get()
    await sync_guest_quota_after_refund(
        _BrokenRedisTransport(),
        guest_token_hash=sha256_hex("gst_sync_test"),
        delta=4,
    )
    assert REDIS_ERRORS_TOTAL.labels(operation="worker_quota_sync")._value.get() == sync_before + 1

    # Uninitialized None client also fails closed when REDIS_FAIL_CLOSED=true.
    with pytest.raises(FieldShiftError) as exc_none:
        await check_rate_limits(None, [check], fail_closed=True)
    assert exc_none.value.code == ErrorCode.SERVICE_UNAVAILABLE
    assert exc_none.value.headers.get("Retry-After") == "5"
