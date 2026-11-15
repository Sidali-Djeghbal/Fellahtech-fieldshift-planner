"""Live PostGIS + Redis concurrency fault-injection tests for circuit breaker & replay."""

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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, MLUpstreamServerError, MockMLAdapter
from app.models import AnalysisRequest, MlBreakerState
from app.worker.breaker import read_breaker_snapshot
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _fi_settings(**overrides: Any) -> Settings:
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
        "ML_BREAKER_COOLDOWN_SECONDS": 2,
        "DEGRADED_MODE_MAX_AGE_HOURS": 72,
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
async def fi_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _fi_settings()
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


class _SlowConfigurableMLAdapter(MockMLAdapter):
    """Instrumented MockMLAdapter simulating slow ML probe calls and outages."""

    def __init__(self, *, sleep_seconds: float = 0.0, fail_503: bool = False) -> None:
        super().__init__(fault_mode="none")
        self.sleep_seconds = sleep_seconds
        self.fail_503 = fail_503
        self.analyze_calls = 0

    async def analyze(
        self,
        payload: Any,
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        self.analyze_calls += 1
        if self.sleep_seconds > 0:
            await asyncio.sleep(self.sleep_seconds)
        if self.fail_503:
            raise MLUpstreamServerError("Simulated concurrent ML outage", status_code=503)
        return await super().analyze(payload, idempotency_key=idempotency_key, compress=compress)


async def _register_farm_and_field(client: httpx.AsyncClient) -> tuple[dict[str, str], str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"fi_{os.urandom(4).hex()}@example.com",
            "password": "StrongPassword!123",
            "full_name": "Fault Injector",
            "preferred_lang": "en",
        },
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    farm_id = str(
        (
            await client.post(
                "/api/v1/farms",
                headers=headers,
                json={"farm_name": "FI Farm", "country": "Algeria", "region": "Guelma"},
            )
        ).json()["farm_id"]
    )
    fld = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcel FI",
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 12.0,
            "soil": {"soil_type": "loamy", "soil_ph": 7.0},
            "water": {"availability": "moderate", "source": "well", "irrigation_system": "drip"},
            "crop_history": [{"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}],
        },
    )
    assert fld.status_code == 201
    return headers, farm_id


async def _submit_year(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    farm_id: str,
    start_year: int,
) -> str:
    resp = await client.post(
        "/api/v1/analysis",
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
    assert resp.status_code == 202
    return str(resp.json()["request_id"])


@pytest.mark.asyncio
async def test_concurrent_single_flight_half_open_probe_zero_thundering_herd(
    fi_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = fi_ctx
    slow_ml = _SlowConfigurableMLAdapter(sleep_seconds=0.0, fail_503=False)
    ml_manager = MLProviderManager(settings, mock_adapter=slow_ml, redis_client=redis_client)

    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        headers, farm_id = await _register_farm_and_field(client)
        # Seed baseline result for start_year=2027.
        r0 = await _submit_year(client, headers, farm_id, 2027)
        seed_runner = WorkerRunner(
            settings=settings,
            engine=engine,
            sessionmaker=sessionmaker,
            redis_client=redis_client,
            ml_manager=ml_manager,
        )
        s0 = await seed_runner.run_once()
        assert s0 is not None and s0.outcome == "completed" and r0 == s0.request_id
        src_aid = s0.analysis_id
        assert src_aid is not None

        # Open breaker past cooldown; 6 concurrent workers claim 6 hash_A jobs simultaneously!
        slow_ml.analyze_calls = 0
        slow_ml.sleep_seconds = 0.25
        slow_ml.fail_503 = True

        async with sessionmaker() as db:
            row = await db.get(MlBreakerState, 1)
            assert row is not None
            row.state = "open"
            row.consecutive_failures = 5
            row.opened_at = datetime.now(UTC) - timedelta(seconds=10)
            row.half_open_probe_at = None
            await db.commit()

        race_ids = [await _submit_year(client, headers, farm_id, 2027) for _ in range(6)]

    worker_engines = [create_db_engine(settings, role="worker") for _ in range(6)]
    try:
        runners = [
            WorkerRunner(
                settings=settings,
                engine=wk_e,
                sessionmaker=create_sessionmaker(wk_e),
                redis_client=redis_client,
                ml_manager=ml_manager,
                probe_stale_after_seconds=30.0,
            )
            for wk_e in worker_engines
        ]
        # Execute 1 simultaneous job per worker concurrently.
        outcomes = await asyncio.gather(*(r.run_once() for r in runners))
    finally:
        await asyncio.gather(*(wk_e.dispose() for wk_e in worker_engines))

    completed = [o for o in outcomes if o is not None]
    assert len(completed) == 6
    # Strictly ONE single-flight probe hit ML; the other 5 saw active half_open probe -> replayed!
    assert slow_ml.analyze_calls == 1

    async with sessionmaker() as db:
        snap = await read_breaker_snapshot(db)
        assert snap.state == "open"
        assert snap.half_open_probe_at is None
        rows = (
            await db.execute(
                select(AnalysisRequest).where(AnalysisRequest.request_id.in_(race_ids))
            )
        ).scalars().all()
        assert all(
            r.status == "ok" and r.error_code == f"last_good_replay:{src_aid}" for r in rows
        )


@pytest.mark.asyncio
async def test_concurrent_outage_storm_opens_breaker_and_subsequent_batch_replays(
    fi_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    base_settings, engine, sessionmaker, redis_client = fi_ctx
    # Use full 30s cooldown so instrumented concurrent runs stay firmly inside `open` window.
    settings = base_settings.model_copy(update={"ML_BREAKER_COOLDOWN_SECONDS": 30})
    storm_ml = _SlowConfigurableMLAdapter(sleep_seconds=0.05, fail_503=False)
    ml_manager = MLProviderManager(settings, mock_adapter=storm_ml, redis_client=redis_client)

    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    runner_single = WorkerRunner(
        settings=settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        headers, farm_id = await _register_farm_and_field(client)
        # Seed baseline result for start_year=2027.
        await _submit_year(client, headers, farm_id, 2027)
        s0 = await runner_single.run_once()
        assert s0 is not None and s0.outcome == "completed" and s0.analysis_id is not None
        src_aid = s0.analysis_id

        # Trigger 8 concurrent outages without prior hashes -> safely trips open >= 5.
        storm_ml.analyze_calls = 0
        storm_ml.fail_503 = True
        outage_ids = [
            await _submit_year(client, headers, farm_id, yr) for yr in range(2028, 2036)
        ]

        worker_engines = [create_db_engine(settings, role="worker") for _ in range(4)]
        try:
            runners = [
                WorkerRunner(
                    settings=settings,
                    engine=wk_e,
                    sessionmaker=create_sessionmaker(wk_e),
                    redis_client=redis_client,
                    ml_manager=ml_manager,
                    poll_interval_seconds=0.01,
                )
                for wk_e in worker_engines
            ]
            await asyncio.gather(*(r.drain_until_idle() for r in runners))
        finally:
            await asyncio.gather(*(wk_e.dispose() for wk_e in worker_engines))

        async with sessionmaker() as db:
            snap = await read_breaker_snapshot(db)
            assert snap.state == "open"
            assert snap.consecutive_failures >= 5
            failed_rows = (
                await db.execute(
                    select(AnalysisRequest).where(AnalysisRequest.request_id.in_(outage_ids))
                )
            ).scalars().all()
            assert len(failed_rows) == 8
            assert all(
                r.status == "failed" and r.error_code == ErrorCode.ML_UNAVAILABLE.value
                for r in failed_rows
            )

        # Follow-up batch of 4 matching jobs executes with ZERO ML calls via last_good_replay!
        storm_ml.analyze_calls = 0
        replay_ids = [await _submit_year(client, headers, farm_id, 2027) for _ in range(4)]
        await runner_single.drain_until_idle()
        assert storm_ml.analyze_calls == 0

        async with sessionmaker() as db:
            rep_rows = (
                await db.execute(
                    select(AnalysisRequest).where(AnalysisRequest.request_id.in_(replay_ids))
                )
            ).scalars().all()
            assert len(rep_rows) == 4
            assert all(
                r.status == "ok" and r.error_code == f"last_good_replay:{src_aid}"
                for r in rep_rows
            )
