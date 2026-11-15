"""Real-Redis & PostgreSQL integration tests for M2 sliding-window rate limiter & quota sync.

Requires a live Redis instance (`REDIS_URL`, default `redis://127.0.0.1:6379/0`) and, for
PG->Redis cache hydration tests, live PostgreSQL (`TEST_DB_*` / `build_test_env()`).
Never mocks Redis (`fakeredis` is strictly disallowed).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from fastapi import Request
from sqlalchemy import delete

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.rate_limit import (
    POLL_RATE_LIMIT_PER_MIN,
    build_analysis_checks,
    build_crud_check,
    build_guest_create_ip_check,
    build_poll_check,
    check_rate_limits,
    get_or_hydrate_guest_quarters,
    guest_quota_key,
    increment_guest_quarters,
    refund_guest_quarters,
    rollback_rate_limits,
    sha256_hex,
    sync_guest_quota_after_refund,
)
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.models import AnalysisRequest, Farm, GuestSession
from tests.conftest import build_test_env


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _integration_settings() -> Settings:
    env = build_test_env()
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=env["DATABASE_URL"],
        DB_PASSWORD=env["DB_PASSWORD"],
        REDIS_URL=_redis_url(),
        ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
        ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
        JWT_SECRET_KEY=env["JWT_SECRET_KEY"],
        ML_SERVICE_API_KEY=env["ML_SERVICE_API_KEY"],
    )


@pytest_asyncio.fixture
async def live_redis() -> AsyncIterator[tuple[redis_async.Redis, list[str]]]:
    client = redis_async.Redis.from_url(_redis_url(), decode_responses=False)
    tracked_patterns: list[str] = []
    await client.ping()
    try:
        yield client, tracked_patterns
    finally:
        for pattern in tracked_patterns:
            keys = [key async for key in client.scan_iter(match=pattern)]
            if keys:
                await client.delete(*keys)
        await client.aclose()


@pytest.mark.asyncio
async def test_all_six_buckets_and_120_poll_exemption(
    live_redis: tuple[redis_async.Redis, list[str]],
) -> None:
    redis_client, tracked = live_redis
    settings = _integration_settings()
    suffix = uuid.uuid4().hex
    guest_hash = sha256_hex(f"gst_{suffix}")
    user_id = int(suffix[:8], 16)
    ip_addr = f"198.51.100.{user_id % 250}"
    base_time = 1_800_000_000

    tracked.extend(
        [
            "rl:guest_create:ip:*",
            f"rl:crud:g:{guest_hash[:16]}:*",
            f"rl:crud:u:{user_id}:*",
            f"rl:poll:*:{user_id}:*",
            f"rl:poll:g:{guest_hash[:16]}:*",
            f"rl:analysis:u:{user_id}:*",
            "rl:analysis:ip:*",
        ]
    )

    # 1. Guest create IP limit (5/h)
    g_create = build_guest_create_ip_check(ip_addr, settings)
    for _ in range(settings.GUEST_CREATE_PER_IP_HOUR):
        await check_rate_limits(redis_client, [g_create], now_override=base_time + 5)
    with pytest.raises(FieldShiftError) as exc_create:
        await check_rate_limits(redis_client, [g_create], now_override=base_time + 5)
    assert exc_create.value.code == ErrorCode.RATE_LIMIT_EXCEEDED
    assert int(exc_create.value.headers["Retry-After"]) >= 1

    # 2. Guest CRUD burst (30/min) exhausted; Poll bucket (120/min) stays independent.
    g_crud = build_crud_check(settings=settings, guest_token_hash=guest_hash)
    for _ in range(settings.GUEST_BURST_PER_MIN):
        await check_rate_limits(redis_client, [g_crud], now_override=base_time + 5)
    with pytest.raises(FieldShiftError) as exc_g_crud:
        await check_rate_limits(redis_client, [g_crud], now_override=base_time + 5)
    assert exc_g_crud.value.code == ErrorCode.RATE_LIMIT_EXCEEDED

    g_poll = build_poll_check(guest_token_hash=guest_hash)
    for _ in range(POLL_RATE_LIMIT_PER_MIN):
        await check_rate_limits(redis_client, [g_poll], now_override=base_time + 5)
    with pytest.raises(FieldShiftError) as exc_poll:
        await check_rate_limits(redis_client, [g_poll], now_override=base_time + 5)
    assert exc_poll.value.code == ErrorCode.RATE_LIMIT_EXCEEDED

    # 3. Registered User CRUD (60/min)
    u_crud = build_crud_check(settings=settings, user_id=user_id)
    for _ in range(settings.RATE_LIMIT_CRUD_PER_MIN):
        await check_rate_limits(redis_client, [u_crud], now_override=base_time + 5)
    with pytest.raises(FieldShiftError):
        await check_rate_limits(redis_client, [u_crud], now_override=base_time + 5)

    # 4. Analysis User (40 quarters/h) & Analysis IP (60 quarters/h)
    analysis_full = build_analysis_checks(
        client_ip=ip_addr,
        quota_units=4,
        settings=settings,
        user_id=user_id,
    )
    for _ in range(10):
        await check_rate_limits(redis_client, analysis_full, now_override=base_time + 10)
    with pytest.raises(FieldShiftError) as exc_an_u:
        await check_rate_limits(redis_client, analysis_full, now_override=base_time + 10)
    assert exc_an_u.value.code == ErrorCode.RATE_LIMIT_EXCEEDED

    # Guest on same IP still has remaining IP budget (60 - 40 = 20 quarters -> 5 full analyses)
    ip_only = build_analysis_checks(
        client_ip=ip_addr,
        quota_units=4,
        settings=settings,
        user_id=None,
    )
    for _ in range(5):
        await check_rate_limits(redis_client, ip_only, now_override=base_time + 10)
    with pytest.raises(FieldShiftError) as exc_an_ip:
        await check_rate_limits(redis_client, ip_only, now_override=base_time + 10)
    assert exc_an_ip.value.code == ErrorCode.RATE_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_two_bucket_sliding_window_prevents_2x_boundary_burst(
    live_redis: tuple[redis_async.Redis, list[str]],
) -> None:
    redis_client, tracked = live_redis
    settings = _integration_settings()
    guest_hash = sha256_hex(f"boundary_{uuid.uuid4().hex}")
    tracked.append(f"rl:crud:g:{guest_hash[:16]}:*")
    check = build_crud_check(settings=settings, guest_token_hash=guest_hash)

    # Window 0: [1_800_000_000 .. 1_800_000_059]; saturate 30/30 at t=50
    t_prev = 1_800_000_050
    for _ in range(30):
        await check_rate_limits(redis_client, [check], now_override=t_prev)

    # Exact boundary start t=60 (prev_remaining=60): MUST block immediately (no 2x burst!)
    with pytest.raises(FieldShiftError) as exc_boundary:
        await check_rate_limits(redis_client, [check], now_override=1_800_000_060)
    assert exc_boundary.value.code == ErrorCode.RATE_LIMIT_EXCEEDED
    assert int(exc_boundary.value.headers["Retry-After"]) >= 1

    # Halfway through next bucket t=90 (prev_remaining=30 -> weighted prev=15):
    # Exactly 15 requests MUST be allowed, 16th MUST block with exact Retry-After recovery.
    for _ in range(15):
        await check_rate_limits(redis_client, [check], now_override=1_800_000_090)
    with pytest.raises(FieldShiftError) as exc_mid:
        await check_rate_limits(redis_client, [check], now_override=1_800_000_090)
    retry_after = int(exc_mid.value.headers["Retry-After"])
    assert retry_after == 2
    await check_rate_limits(redis_client, [check], now_override=1_800_000_090 + retry_after)


@pytest.mark.asyncio
async def test_non_burning_multi_bucket_and_clamped_decrby_never_leaves_negative_ttl(
    live_redis: tuple[redis_async.Redis, list[str]],
) -> None:
    redis_client, tracked = live_redis
    settings = _integration_settings()
    suffix = uuid.uuid4().hex
    user_id = int(suffix[:8], 16)
    ip_addr = f"203.0.113.{(user_id % 250) + 1}"
    guest_hash = sha256_hex(f"quota_{suffix}")
    tracked.extend(
        [
            f"rl:analysis:u:{user_id}:*",
            "rl:analysis:ip:*",
            guest_quota_key(guest_hash),
        ]
    )

    # Pre-fill IP quota to 58/60 quarters so a cost=4 check passes USER (0/40) then fails IP
    ip_checks = build_analysis_checks(
        client_ip=ip_addr,
        quota_units=4,
        settings=settings,
        user_id=None,
    )
    for _ in range(14):  # 56 quarters
        await check_rate_limits(redis_client, ip_checks, now_override=1_800_003_610)
    await check_rate_limits(
        redis_client,
        build_analysis_checks(client_ip=ip_addr, quota_units=1, settings=settings),
        now_override=1_800_003_610,
    )  # 57
    await check_rate_limits(
        redis_client,
        build_analysis_checks(client_ip=ip_addr, quota_units=1, settings=settings),
        now_override=1_800_003_610,
    )  # 58

    both_checks = build_analysis_checks(
        client_ip=ip_addr,
        quota_units=4,
        settings=settings,
        user_id=user_id,
    )
    with pytest.raises(FieldShiftError) as exc_multi:
        await check_rate_limits(redis_client, both_checks, now_override=1_800_003_610)
    assert exc_multi.value.code == ErrorCode.RATE_LIMIT_EXCEEDED
    # USER bucket MUST have been rolled back cleanly and deleted (never burned)
    user_keys = [k async for k in redis_client.scan_iter(match=f"rl:analysis:u:{user_id}:*")]
    assert user_keys == []

    # Rollback exact bucket_key after hour rollover still targets the incremented key cleanly
    grants = await check_rate_limits(
        redis_client,
        [both_checks[0]],
        now_override=1_800_003_599,
    )
    assert len(grants) == 1
    assert await redis_client.get(grants[0].bucket_key) == b"4"
    await rollback_rate_limits(redis_client, grants)
    assert await redis_client.exists(grants[0].bucket_key) == 0

    # Clamped EXISTS-guarded DECRBY on missing/expired/over-refunded guest quota keys
    q_key = guest_quota_key(guest_hash)
    assert await refund_guest_quarters(redis_client, guest_token_hash=guest_hash, delta=4) == 0
    assert await redis_client.exists(q_key) == 0  # NEVER creates negative TTL=-1 key!

    await redis_client.set(q_key, 8, ex=300)
    rem = await refund_guest_quarters(redis_client, guest_token_hash=guest_hash, delta=4)
    assert rem == 4
    assert await redis_client.get(q_key) == b"4"
    assert 0 < await redis_client.ttl(q_key) <= 300

    rem_zero = await refund_guest_quarters(redis_client, guest_token_hash=guest_hash, delta=10)
    assert rem_zero == 0
    assert await redis_client.exists(q_key) == 0


@pytest.mark.asyncio
async def test_pg_to_redis_guest_quota_cache_miss_hydration(
    live_redis: tuple[redis_async.Redis, list[str]],
) -> None:
    redis_client, tracked = live_redis
    settings = _integration_settings()
    engine = create_db_engine(settings, role="api")
    session_factory = create_sessionmaker(engine)
    token_hash = sha256_hex(f"hydrate_{uuid.uuid4().hex}")
    q_key = guest_quota_key(token_hash)
    tracked.append(q_key)

    farm_id: int | None = None
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2],
            env=build_test_env(),
            check=True,
            capture_output=True,
            text=True,
        )

        async with session_factory() as session:
            async with session.begin():
                guest = GuestSession(
                    guest_token=token_hash,
                    demo_location_id=1,
                    expires_at=datetime.now(UTC) + timedelta(days=5),
                )
                session.add(guest)
                await session.flush()

                farm = Farm(
                    guest_session_token=token_hash,
                    farm_name="Hydration Test Farm",
                    country="DZ",
                    region="Guelma",
                )
                session.add(farm)
                await session.flush()
                farm_id = farm.id

                for units in (4, 1):
                    session.add(
                        AnalysisRequest(
                            request_id=str(uuid.uuid4()),
                            farm_id=farm.id,
                            schema_version="5.0",
                            catalog_version="v1",
                            dataset_version="2026.11-guelma-v1",
                            language="en",
                            quota_units=units,
                            input_hash=sha256_hex(f"ih-{units}"),
                            full_input_hash=sha256_hex(f"fih-{units}"),
                            status="ok",
                        )
                    )

        # Ensure cache key is absent before hydration check
        await redis_client.delete(q_key)

        async with session_factory() as session:
            async with session.begin():
                used, ttl = await get_or_hydrate_guest_quarters(
                    session,
                    redis_client,
                    guest_token_hash=token_hash,
                )
                assert used == 5
                assert ttl > 4 * 86400

        assert await redis_client.get(q_key) == b"5"
        assert await redis_client.ttl(q_key) > 0

        updated = await increment_guest_quarters(
            redis_client,
            guest_token_hash=token_hash,
            delta=4,
            fallback_total=9,
            ttl_seconds=ttl,
        )
        assert updated == 9
        assert await redis_client.get(q_key) == b"9"
        assert await redis_client.ttl(q_key) > 0

        # Cache-hit read uses Redis value cleanly without re-querying SUM overwriting it
        async with session_factory() as session:
            async with session.begin():
                cached_used, _ = await get_or_hydrate_guest_quarters(
                    session,
                    redis_client,
                    guest_token_hash=token_hash,
                )
                assert cached_used == 9

        # Worker best-effort refund sync decrements cleanly on live Redis
        await sync_guest_quota_after_refund(
            redis_client,
            guest_token_hash=token_hash,
            delta=4,
        )
        assert await redis_client.get(q_key) == b"5"

        # Expired / missing guest session raises 401 UNAUTHORIZED
        expired_hash = sha256_hex(f"expired_{uuid.uuid4().hex}")
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    GuestSession(
                        guest_token=expired_hash,
                        demo_location_id=1,
                        expires_at=datetime.now(UTC) - timedelta(minutes=5),
                    )
                )
        try:
            async with session_factory() as session:
                async with session.begin():
                    with pytest.raises(FieldShiftError) as exc_exp:
                        await get_or_hydrate_guest_quarters(
                            session,
                            redis_client,
                            guest_token_hash=expired_hash,
                        )
                    assert exc_exp.value.code == ErrorCode.UNAUTHORIZED
                    assert exc_exp.value.status_code == 401
        finally:
            async with session_factory() as cleanup_exp:
                async with cleanup_exp.begin():
                    await cleanup_exp.execute(
                        delete(GuestSession).where(GuestSession.guest_token == expired_hash)
                    )
    finally:
        async with session_factory() as cleanup:
            async with cleanup.begin():
                if farm_id is not None:
                    await cleanup.execute(delete(Farm).where(Farm.id == farm_id))
                await cleanup.execute(
                    delete(GuestSession).where(GuestSession.guest_token == token_hash)
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_fastapi_lifespan_real_redis_429_and_error_envelope(
    live_redis: tuple[redis_async.Redis, list[str]],
) -> None:
    _client, tracked = live_redis
    settings = _integration_settings()
    ip_addr = f"198.51.100.{(uuid.uuid4().int % 200) + 10}"
    tracked.append("rl:guest_create:ip:*")

    app = create_app(settings=settings)

    @app.get("/_test/rl-guest-create")
    async def limited_route(request: Request) -> dict[str, bool]:
        check = build_guest_create_ip_check(ip_addr, settings)
        await check_rate_limits(
            request.app.state.redis,
            [check],
            fail_closed=settings.REDIS_FAIL_CLOSED,
        )
        return {"ok": True}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for _ in range(settings.GUEST_CREATE_PER_IP_HOUR):
                ok = await client.get("/_test/rl-guest-create")
                assert ok.status_code == 200

            throttled = await client.get(
                "/_test/rl-guest-create",
                headers={"X-Request-Id": "req-rl-429"},
            )
            assert throttled.status_code == 429
            assert int(throttled.headers["retry-after"]) >= 1
            assert throttled.headers["x-request-id"] == "req-rl-429"
            payload = throttled.json()
            assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert payload["error"]["request_id"] == "req-rl-429"
