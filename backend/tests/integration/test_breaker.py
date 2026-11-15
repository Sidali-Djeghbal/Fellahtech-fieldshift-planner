"""Live PostGIS + Redis integration tests for M10 circuit breaker & `last_good_replay`."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.core.rate_limit import guest_quota_key
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, MockMLAdapter, RealMLAdapter
from app.ml_client.mock_server import create_mock_ml_app
from app.models import AnalysisRequest, AnalysisResult, MlBreakerState
from app.repositories import analysis as analysis_repo
from app.worker.breaker import (
    acquire_breaker_dispatch,
    read_breaker_snapshot,
    record_breaker_failure,
    record_breaker_non_failure,
    release_aborted_half_open_probe,
    run_release_aborted_probe,
)
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _breaker_settings(**overrides: Any) -> Settings:
    env = build_test_env()
    params: dict[str, Any] = {
        "_env_file": None,
        "APP_ENV": "test",
        "ML_PROVIDER_MODE": "mock",
        "DATABASE_URL": env["DATABASE_URL"],
        "DB_PASSWORD": env["DB_PASSWORD"],
        "REDIS_URL": _redis_url(),
        "ML_DATASET_DB_URL": env["ML_DATASET_DB_URL"],
        "ML_READER_PASSWORD": env["ML_READER_PASSWORD"],
        "JWT_SECRET_KEY": env["JWT_SECRET_KEY"],
        "ML_SERVICE_API_KEY": env["ML_SERVICE_API_KEY"],
        "GUEST_CREATE_PER_IP_HOUR": 200,
        "GUEST_BURST_PER_MIN": 500,
        "RATE_LIMIT_CRUD_PER_MIN": 500,
        "RATE_LIMIT_ANALYSIS_PER_HOUR": 500,
        "ANALYSIS_PER_IP_HOUR": 500,
        "TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128",
        "ML_MAX_RETRIES": 0,
        "ML_CIRCUIT_BREAKER_THRESHOLD": 5,
        "ML_BREAKER_COOLDOWN_SECONDS": 30,
        "DEGRADED_MODE_MAX_AGE_HOURS": 72,
        "GUEST_MAX_ANALYSES": 10,
        "GUEST_MAX_ML_REFUNDS": 3,
        "ALLOW_SYNC_WAIT": True,
        "SYNC_WAIT_TIMEOUT_SECONDS": 10,
    }
    params.update(overrides)
    return Settings(**params)


async def _cleanup_all(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as db:
        await db.execute(
            text(
                "TRUNCATE TABLE public.analysis_selections, public.analysis_results, "
                "public.analysis_requests, public.field_crop_history, public.fields, "
                "public.farms, public.guest_sessions, public.refresh_tokens, public.users, "
                "public.crop_catalog RESTART IDENTITY CASCADE"
            )
        )
        await db.execute(
            text("DELETE FROM public.demo_locations WHERE id <> :gid"),
            {"gid": GUELMA_LOCATION_ID},
        )
        await db.execute(
            text(
                "UPDATE public.dataset_registry SET is_active = (dataset_version = :ver) "
                "WHERE dataset_version = :ver OR is_active = true"
            ),
            {"ver": DEFAULT_DATASET_VERSION},
        )
        await db.execute(
            text(
                "UPDATE public.ml_breaker_state "
                "SET state = 'closed', consecutive_failures = 0, "
                "opened_at = NULL, half_open_probe_at = NULL, updated_at = NOW() "
                "WHERE id = 1"
            )
        )
        await db.commit()


@pytest.fixture(scope="module")
def migrated_database() -> None:
    env = build_test_env()
    subprocess.run(
        [str(ALEMBIC_EXE), "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest_asyncio.fixture
async def m10_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _breaker_settings()
    engine = create_db_engine(settings, role="worker")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        await redis_client.flushdb()
        await _cleanup_all(sessionmaker)
        ML_BREAKER_STATE_GAUGE.set(0.0)
        yield settings, engine, sessionmaker, redis_client
    finally:
        await _cleanup_all(sessionmaker)
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


async def _setup_guest_and_field(
    client: httpx.AsyncClient,
    *,
    ip: str = "198.51.100.88",
) -> tuple[str, dict[str, str], str]:
    g_resp = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert g_resp.status_code == 201
    guest_tok = str(g_resp.json()["guest_token"])
    headers = {"X-Guest-Token": guest_tok, "X-Forwarded-For": ip}

    farm_resp = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": "Breaker Farm", "country": "Algeria", "region": "Guelma"},
    )
    assert farm_resp.status_code == 201
    farm_id = str(farm_resp.json()["farm_id"])

    fld_resp = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcel Breaker",
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 10.0,
            "soil": {"soil_type": "loamy", "soil_ph": 7.1},
            "water": {"availability": "moderate", "source": "well", "irrigation_system": "drip"},
            "crop_history": [{"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}],
        },
    )
    assert fld_resp.status_code == 201
    return guest_tok, headers, farm_id


async def _submit(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    farm_id: str,
    *,
    start_year: int = 2027,
    wait: bool = False,
) -> httpx.Response:
    url = "/api/v1/analysis?wait=true" if wait else "/api/v1/analysis"
    return await client.post(
        url,
        headers=headers,
        json={
            "farm_id": farm_id,
            "field_ids": ["F1"],
            "language": "en",
            "planning": {
                "start_season": "spring",
                "start_year": start_year,
                "horizon_seasons": 4,
                "cycle_mode": "annual_rotation",
                "planting_month": 3,
                "scenario_overrides": {"temp_delta_c": 0.0, "precip_pct_delta": 0.0},
            },
            "priorities": {
                "weights": {
                    "water_saving": 25,
                    "soil_improvement": 25,
                    "income": 30,
                    "risk_reduction": 10,
                    "forage_value": 10,
                },
                "market_preference": "mixed",
                "target_crop_ids": ["chickpea"],
                "excluded_crop_ids": [],
            },
        },
    )


class _SpyMockMLAdapter(MockMLAdapter):
    """Wrap MockMLAdapter to count live analyze invocations."""

    def __init__(self, *, fault_mode: str = "none") -> None:
        super().__init__(fault_mode=fault_mode)
        self.analyze_calls = 0

    async def analyze(
        self,
        payload: Any,
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        self.analyze_calls += 1
        return await super().analyze(payload, idempotency_key=idempotency_key, compress=compress)


@pytest.mark.asyncio
async def test_five_outages_open_breaker_sixth_serves_non_chaining_last_good_replay(
    m10_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m10_ctx
    spy = _SpyMockMLAdapter(fault_mode="none")
    ml_manager = MLProviderManager(settings, mock_adapter=spy, redis_client=redis_client)

    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    runner = WorkerRunner(
        settings=settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
        jitter_fn=lambda: 0.0,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_tok, headers, farm_id = await _setup_guest_and_field(client)
        tok_hash = hash_token(guest_tok)

        # 1. Baseline happy request (hash for start_year=2027) -> live received_at IS NOT NULL.
        r0_resp = await _submit(client, headers, farm_id, start_year=2027)
        assert r0_resp.status_code == 202
        s0 = await runner.run_once()
        assert s0 is not None and s0.outcome == "completed" and s0.analysis_id is not None
        src_aid = s0.analysis_id

        # 2. Five distinct outage requests (start_year=2028..2032) -> trip breaker open.
        spy.set_fault_mode("http_503")
        for idx, yr in enumerate(range(2028, 2033), start=1):
            resp = await _submit(client, headers, farm_id, start_year=yr)
            assert resp.status_code == 202
            summary = await runner.run_once()
            assert summary is not None
            assert summary.outcome == "failed"
            assert summary.error_code == ErrorCode.ML_UNAVAILABLE.value
            async with sessionmaker() as db:
                snap = await read_breaker_snapshot(db)
                if idx < 5:
                    assert snap.state == "closed"
                    assert snap.consecutive_failures == idx
                else:
                    assert snap.state == "open"
                    assert snap.consecutive_failures == 5
                    assert snap.opened_at is not None

        assert ML_BREAKER_STATE_GAUGE._value.get() == 1.0

        # 3. 6th request with matching hash (start_year=2027) skips ML & serves last_good_replay!
        calls_before_replay = spy.analyze_calls
        r6_resp = await _submit(client, headers, farm_id, start_year=2027)
        assert r6_resp.status_code == 202
        r6_id = str(r6_resp.json()["request_id"])

        s6 = await runner.run_once()
        assert s6 is not None and s6.outcome == "completed" and s6.analysis_id is not None
        rep_aid = s6.analysis_id
        assert rep_aid != src_aid
        assert spy.analyze_calls == calls_before_replay  # Zero ML calls during open breaker!

        async with sessionmaker() as db:
            req6 = await db.get(AnalysisRequest, r6_id)
            assert req6 is not None
            assert req6.status == "ok"
            assert req6.received_at is None
            assert req6.sent_at is None
            assert req6.error_code == f"last_good_replay:{src_aid}"

        # Poll + permalink + ?wait=true all expose stale last_good_replay & selection isolation.
        poll6 = await client.get(f"/api/v1/analysis/requests/{r6_id}", headers=headers)
        assert poll6.status_code == 200
        assert poll6.json()["degraded_mode"]["kind"] == "last_good_replay"
        assert poll6.json()["degraded_mode"]["stale"] is True
        assert poll6.json()["degraded_mode"]["source_analysis_id"] == src_aid

        perm6 = await client.get(f"/api/v1/analysis/{rep_aid}", headers=headers)
        assert perm6.status_code == 200
        assert perm6.json()["degraded_mode"]["source_analysis_id"] == src_aid

        # Selection patched on source stays isolated from replay & vice-versa.
        sel_resp = await client.patch(
            f"/api/v1/analysis/{src_aid}/selection",
            headers=headers,
            json={
                "field_id": "F1",
                "strategy_id": "S2_water_resilient",
                "selection_status": "selected",
            },
        )
        assert sel_resp.status_code == 200
        rep_after_sel = (await client.get(f"/api/v1/analysis/{rep_aid}", headers=headers)).json()
        rep_s2 = next(
            st
            for st in rep_after_sel["result"]["field_plans"][0]["strategies"]
            if st["strategy_id"] == "S2_water_resilient"
        )
        assert all(sn["selection_status"] == "suggested" for sn in rep_s2["seasons"])

        # Synchronous `?wait=true` while worker runs returns 200 with degraded_mode!
        async def _run_worker_soon() -> None:
            for _ in range(100):
                if await runner.run_once() is not None:
                    return
                await asyncio.sleep(0.02)

        bg = asyncio.create_task(_run_worker_soon())
        wait_resp = await _submit(client, headers, farm_id, start_year=2027, wait=True)
        await bg
        assert wait_resp.status_code == 200
        assert wait_resp.json()["degraded_mode"]["source_analysis_id"] == src_aid

        # 4. Verify non-chaining + max-age expiry (73h > 72h): age ONLY live R0 past 72h.
        # Newer replay rows (R6) carry received_at=NULL so they must NOT be chain-replayed!
        stale_ts = datetime.now(UTC) - timedelta(hours=73)
        async with sessionmaker() as db:
            res0 = (
                await db.execute(
                    select(AnalysisResult).where(AnalysisResult.analysis_id == src_aid)
                )
            ).scalar_one()
            res0.created_at = stale_ts
            await db.commit()

        calls_before_expired = spy.analyze_calls
        r_expired = await _submit(client, headers, farm_id, start_year=2027)
        assert r_expired.status_code == 202
        r_expired_id = str(r_expired.json()["request_id"])
        s_exp = await runner.run_once()
        assert s_exp is not None
        assert s_exp.outcome == "failed"
        assert s_exp.error_code == ErrorCode.ML_UNAVAILABLE.value
        assert s_exp.refunded_quarters == 1  # Same canonical hash 1Q refunded pre-dispatch!
        assert spy.analyze_calls == calls_before_expired

        # Open-breaker pre-dispatch refund did NOT consume any of the 3 post-dispatch ML refunds.
        async with sessionmaker() as db:
            refund_count = await analysis_repo.count_guest_ml_refunds(
                db, guest_token_hash=tok_hash
            )
            assert refund_count == 3  # Only 3 of the 5 outage jobs were refunded before hitting cap
            exp_req = await db.get(AnalysisRequest, r_expired_id)
            assert exp_req is not None and exp_req.sent_at is None and exp_req.quota_units == 0
        assert int(await redis_client.get(guest_quota_key(tok_hash))) >= 1


@pytest.mark.asyncio
async def test_half_open_probe_failure_reopens_and_4xx_or_200_closes_breaker(
    m10_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _, engine, sessionmaker, redis_client = m10_ctx
    settings_fast = _breaker_settings(ML_BREAKER_COOLDOWN_SECONDS=1)
    spy = _SpyMockMLAdapter(fault_mode="none")
    ml_manager = MLProviderManager(settings_fast, mock_adapter=spy, redis_client=redis_client)
    app = create_app(settings_fast)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    runner = WorkerRunner(
        settings=settings_fast,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
        probe_stale_after_seconds=0.2,
        jitter_fn=lambda: 0.0,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        _, headers, farm_id = await _setup_guest_and_field(client)
        # Warm Redis/DB crop catalog before flipping spy to outage faults.
        assert (await client.get("/api/v1/catalog", headers=headers)).status_code == 200

        # Force open state whose 1s cooldown already elapsed.
        past_open = datetime.now(UTC) - timedelta(seconds=2)
        async with sessionmaker() as db:
            row = await db.get(MlBreakerState, 1)
            assert row is not None
            row.state = "open"
            row.consecutive_failures = 5
            row.opened_at = past_open
            row.half_open_probe_at = None
            await db.commit()

        # 1. Half-open probe fails with 503 -> re-opens immediately with fresh opened_at.
        spy.set_fault_mode("http_503")
        r_probe_fail = await _submit(client, headers, farm_id, start_year=2027)
        assert r_probe_fail.status_code == 202
        out_fail = await runner.run_once()
        assert out_fail is not None and out_fail.outcome == "failed"
        async with sessionmaker() as db:
            snap = await read_breaker_snapshot(db)
            assert snap.state == "open"
            assert snap.half_open_probe_at is None
            assert snap.opened_at is not None and snap.opened_at > past_open

        # 2. Cool down again; probe returns non-breaker 422 -> closes breaker (`Second Audit #5`).
        async with sessionmaker() as db:
            row = await db.get(MlBreakerState, 1)
            assert row is not None
            row.opened_at = datetime.now(UTC) - timedelta(seconds=2)
            await db.commit()

        spy.set_fault_mode("http_422_insufficient")
        r_probe_422 = await _submit(client, headers, farm_id, start_year=2028)
        assert r_probe_422.status_code == 202
        out_422 = await runner.run_once()
        assert out_422 is not None
        assert out_422.outcome == "failed"
        assert out_422.error_code == ErrorCode.INSUFFICIENT_DATA.value
        async with sessionmaker() as db:
            snap_closed = await read_breaker_snapshot(db)
            assert snap_closed.state == "closed"
            assert snap_closed.consecutive_failures == 0
            assert snap_closed.opened_at is None
            assert snap_closed.half_open_probe_at is None
        assert ML_BREAKER_STATE_GAUGE._value.get() == 0.0

        # 3. Cancelled half-open probe releases half_open_probe_at immediately before ML dispatch.
        async with sessionmaker() as db:
            now = datetime.now(UTC)
            await db.execute(
                text(
                    "UPDATE public.ml_breaker_state "
                    "SET state = 'half_open', consecutive_failures = 5, "
                    "opened_at = :opened, half_open_probe_at = :probe "
                    "WHERE id = 1"
                ),
                {"opened": now - timedelta(seconds=2), "probe": now},
            )
            rel_res = await release_aborted_half_open_probe(db, now=now)
            await db.commit()
            assert rel_res.state == "half_open"
            assert rel_res.half_open_probe_at is None

            # Now next dispatch acquires half_open cleanly and 200 OK closes breaker!
            dec = await acquire_breaker_dispatch(
                db,
                now=now,
                cooldown_seconds=1,
                probe_stale_after_seconds=0.2,
            )
            await db.commit()
            assert dec.allowed is True and dec.is_half_open_probe is True

            done_res = await record_breaker_non_failure(
                db,
                now=now,
                was_half_open_probe=True,
                reset_closed_failures=True,
            )
            await db.commit()
            assert done_res.state == "closed" and done_res.recovered is True

            # Verify stale probe recovery after crash + failure threshold helpers.
            await db.execute(
                text(
                    "UPDATE public.ml_breaker_state "
                    "SET state = 'half_open', consecutive_failures = 5, "
                    "opened_at = :opened, half_open_probe_at = :old_probe "
                    "WHERE id = 1"
                ),
                {"opened": now - timedelta(seconds=5), "old_probe": now - timedelta(seconds=1)},
            )
            await db.commit()
            reclaim = await acquire_breaker_dispatch(
                db,
                now=now,
                cooldown_seconds=1,
                probe_stale_after_seconds=0.2,
            )
            assert reclaim.allowed is True and reclaim.is_half_open_probe is True
            reopen = await record_breaker_failure(
                db,
                now=now,
                failure_threshold=5,
                was_half_open_probe=True,
            )
            await db.commit()
            assert reopen.state == "open" and reopen.tripped is True

            # Concurrent outage while open increments consecutive_failures preserving opened_at.
            open_again = await record_breaker_failure(
                db,
                now=now,
                failure_threshold=5,
                was_half_open_probe=False,
            )
            await db.commit()
            assert open_again.state == "open" and open_again.consecutive_failures >= 6

            # Closed non-reset (`reset_closed_failures=False`) keeps failures; `True` clears to 0.
            await db.execute(
                text(
                    "UPDATE public.ml_breaker_state "
                    "SET state = 'closed', consecutive_failures = 2, "
                    "opened_at = NULL, half_open_probe_at = NULL WHERE id = 1"
                )
            )
            await db.commit()
            keep_cnt = await record_breaker_non_failure(
                db,
                now=now,
                was_half_open_probe=False,
                reset_closed_failures=False,
            )
            assert keep_cnt.consecutive_failures == 2
            cleared_cnt = await record_breaker_non_failure(
                db,
                now=now,
                was_half_open_probe=False,
                reset_closed_failures=True,
            )
            await db.commit()
            assert cleared_cnt.consecutive_failures == 0

            # Auto-seed singleton when row id=1 is absent.
            await db.execute(text("DELETE FROM public.ml_breaker_state WHERE id = 1"))
            await db.commit()
            missing_snap = await read_breaker_snapshot(db)
            assert missing_snap.state == "closed" and missing_snap.consecutive_failures == 0
            seeded_dec = await acquire_breaker_dispatch(
                db,
                now=now,
                cooldown_seconds=1,
                probe_stale_after_seconds=0.2,
            )
            await db.commit()
            assert seeded_dec.allowed is True and seeded_dec.state == "closed"

        rel_wrap = await run_release_aborted_probe(sessionmaker, now=datetime.now(UTC))
        assert rel_wrap.state == "closed" and rel_wrap.half_open_probe_at is None


@pytest.mark.asyncio
async def test_post_retry_timeout_replay_and_real_ml_adapter_wire_roundtrip(
    m10_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _, engine, sessionmaker, redis_client = m10_ctx
    retry_settings = _breaker_settings(
        ML_MAX_RETRIES=1,
        ML_RETRY_BASE_DELAY_SECONDS=0.01,
        ML_CIRCUIT_BREAKER_THRESHOLD=2,
        ML_BREAKER_COOLDOWN_SECONDS=30,
    )

    # Mock ML FastAPI app over ASGI wire with togglable 503 middleware!
    mock_ml_app = create_mock_ml_app(accepted_api_keys=["wire-key-1"])
    simulate_outage = False

    @mock_ml_app.middleware("http")
    async def _fault_middleware(request: Any, call_next: Any) -> Any:
        if simulate_outage and request.url.path == "/v1/analyze":
            return JSONResponse(status_code=503, content={"error": {"code": "OVERLOADED"}})
        return await call_next(request)

    wire_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_ml_app),
        base_url="http://mock-ml.local",
    )
    real_adapter = RealMLAdapter(
        Settings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_URL=retry_settings.DATABASE_URL,
            DB_PASSWORD=retry_settings.DB_PASSWORD,
            ML_DATASET_DB_URL=retry_settings.ML_DATASET_DB_URL,
            ML_READER_PASSWORD=retry_settings.ML_READER_PASSWORD,
            JWT_SECRET_KEY=retry_settings.JWT_SECRET_KEY,
            ML_SERVICE_URL="http://mock-ml.local",
            ML_SERVICE_API_KEY="wire-key-1",
        ),
        client=wire_client,
    )

    wire_settings = retry_settings.model_copy(
        update={
            "ML_PROVIDER_MODE": "real",
            "ML_SERVICE_URL": "http://mock-ml.local",
            "ML_SERVICE_API_KEY": "wire-key-1",
        }
    )
    ml_manager = MLProviderManager(
        wire_settings,
        real_adapter=real_adapter,
        redis_client=redis_client,
    )
    app = create_app(wire_settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    runner = WorkerRunner(
        settings=wire_settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
        jitter_fn=lambda: 0.0,
    )

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            _, headers, farm_id = await _setup_guest_and_field(client)

            # 1. Seed valid result via RealMLAdapter -> create_mock_ml_app HTTP wire.
            r_live = await _submit(client, headers, farm_id, start_year=2027)
            assert r_live.status_code == 202, r_live.text
            s_live = await runner.run_once()
            assert s_live is not None and s_live.outcome == "completed"
            live_aid = s_live.analysis_id
            assert live_aid is not None

            # 2. Enable 503 outage on mock_ml HTTP wire: request fails retries & replays last_good!
            simulate_outage = True
            r_post_retry = await _submit(client, headers, farm_id, start_year=2027)
            assert r_post_retry.status_code == 202
            s_post_retry = await runner.run_once()
            assert s_post_retry is not None
            assert s_post_retry.outcome == "completed"
            assert s_post_retry.retries_used == 1
            assert s_post_retry.analysis_id is not None and s_post_retry.analysis_id != live_aid

            poll_post = await client.get(
                f"/api/v1/analysis/requests/{r_post_retry.json()['request_id']}",
                headers=headers,
            )
            assert poll_post.status_code == 200
            assert poll_post.json()["degraded_mode"]["source_analysis_id"] == live_aid

            # 3. 2nd outage trips threshold=2 -> state='open', 3rd serves open-breaker replay!
            r_trip = await _submit(client, headers, farm_id, start_year=2029)
            assert r_trip.status_code == 202
            s_trip = await runner.run_once()
            assert s_trip is not None and s_trip.outcome == "failed"

            async with sessionmaker() as db:
                snap = await read_breaker_snapshot(db)
                assert snap.state == "open"
                assert snap.consecutive_failures == 2

            # Disable mock fault so only open breaker guarantees no ML HTTP call occurs!
            simulate_outage = False
            r_replayed_open = await _submit(client, headers, farm_id, start_year=2027)
            assert r_replayed_open.status_code == 202
            s_replayed = await runner.run_once()
            assert s_replayed is not None and s_replayed.outcome == "completed"
            async with sessionmaker() as db:
                replayed_req = await db.get(
                    AnalysisRequest, str(r_replayed_open.json()["request_id"])
                )
                assert replayed_req is not None
                assert replayed_req.error_code == f"last_good_replay:{live_aid}"
    finally:
        await real_adapter.aclose()
        await wire_client.aclose()
