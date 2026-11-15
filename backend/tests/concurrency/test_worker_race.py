"""Live PostGIS + Redis multi-worker, bulkhead saturation & refund-cap concurrency tests."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.rate_limit import guest_quota_key
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import (
    MLAdapter,
    MLHealthResult,
    MLProviderManager,
    MLUpstreamServerError,
    ProviderKind,
)
from app.models import AnalysisRequest
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import MLCatalogPayload
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _race_settings(**overrides: Any) -> Settings:
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
        "WORKER_CONCURRENCY": 4,
        "ML_MAX_CONCURRENT_REQUESTS": 8,
        "ML_MAX_RETRIES": 0,
        "GUEST_MAX_ML_REFUNDS": 3,
        "GUEST_MAX_ANALYSES": 10,
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
async def race_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _race_settings()
    engine = create_db_engine(settings, role="worker")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
    await _cleanup_all(sessionmaker)

    raw_cat = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
    )
    cat_payload = MLCatalogPayload.model_validate(raw_cat)
    async with sessionmaker() as db:
        await catalog_repo.upsert_catalog_and_prune(
            db, payload=cat_payload, synced_at=datetime.now(UTC), retain_versions=2
        )
        await db.commit()

    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await _cleanup_all(sessionmaker)
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


class _ConcurrencyProbeMLAdapter(MLAdapter):
    """Instrument concurrent active ML dispatches, duplicates, and injected failures."""

    def __init__(
        self,
        template_output: dict[str, Any],
        template_catalog: MLCatalogPayload,
        *,
        sleep_seconds: float = 0.05,
        fail_503: bool = False,
    ) -> None:
        self._template_output = template_output
        self._template_catalog = template_catalog
        self._sleep_seconds = sleep_seconds
        self._fail_503 = fail_503
        self.active = 0
        self.max_observed = 0
        self.invocations: list[str] = []

    @property
    def provider_name(self) -> ProviderKind:
        return "mock_ml"

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        del compress
        self.active += 1
        self.max_observed = max(self.max_observed, self.active)
        self.invocations.append(idempotency_key)
        try:
            await asyncio.sleep(self._sleep_seconds)
            if self._fail_503:
                raise MLUpstreamServerError("Simulated overload", status_code=503)
            parsed = (
                json.loads(payload.decode("utf-8"))
                if isinstance(payload, bytes)
                else dict(payload)
            )
            out = copy.deepcopy(self._template_output)
            out["request_id"] = idempotency_key
            out["dataset_version_used"] = str(parsed["dataset_version"])
            return out
        finally:
            self.active -= 1

    async def get_catalog(self) -> MLCatalogPayload:
        return self._template_catalog

    async def get_health(self) -> MLHealthResult:
        return MLHealthResult(
            reachable=True,
            status="ok",
            ml_engine_version="agro-ml-2.1.0",
            dataset_versions_supported=(DEFAULT_DATASET_VERSION,),
            provider="mock_ml",
        )


async def _register_and_seed_field(
    client: httpx.AsyncClient,
    *,
    as_guest: bool = False,
    ip: str = "198.51.100.77",
) -> tuple[dict[str, str], str, str | None]:
    guest_tok: str | None = None
    if as_guest:
        g_resp = await client.post(
            "/api/v1/auth/guest",
            headers={"X-Forwarded-For": ip},
            json={"demo_location_id": GUELMA_LOCATION_ID},
        )
        assert g_resp.status_code == 201
        guest_tok = str(g_resp.json()["guest_token"])
        headers = {"X-Guest-Token": guest_tok, "X-Forwarded-For": ip}
    else:
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"race_{os.urandom(4).hex()}@example.com",
                "password": "StrongPassword!123",
                "full_name": "Concurrency Tester",
                "preferred_lang": "en",
            },
        )
        assert reg_resp.status_code == 201
        tok = str(reg_resp.json()["access_token"])
        headers = {"Authorization": f"Bearer {tok}", "X-Forwarded-For": ip}

    farm_resp = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": "Race Farm", "country": "Algeria", "region": "Guelma"},
    )
    assert farm_resp.status_code == 201
    farm_id = str(farm_resp.json()["farm_id"])

    fld_resp = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcelle Race",
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 12.0,
            "soil": {"soil_type": "loamy"},
            "water": {"availability": "moderate", "source": "well", "irrigation_system": "drip"},
            "crop_history": [{"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}],
        },
    )
    assert fld_resp.status_code == 201
    return headers, farm_id, guest_tok


async def _enqueue_n(
    client: httpx.AsyncClient,
    headers: Mapping[str, str],
    farm_id: str,
    count: int,
) -> list[str]:
    req_ids: list[str] = []
    for idx in range(count):
        # Distinct `start_year` changes `input_hash` so every request consumes 4Q (non-What-If).
        resp = await client.post(
            "/api/v1/analysis",
            headers=headers,
            json={
                "farm_id": farm_id,
                "field_ids": ["F1"],
                "language": "en",
                "planning": {
                    "start_season": "spring",
                    "start_year": 2027 + idx,
                    "horizon_seasons": 4,
                    "cycle_mode": "annual_rotation",
                    "planting_month": 3,
                    "scenario_overrides": {
                        "temp_delta_c": 0.0,
                        "precip_pct_delta": 0.0,
                    },
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
        req_ids.append(str(resp.json()["request_id"]))
    return req_ids


@pytest.mark.asyncio
async def test_concurrent_workers_skip_locked_zero_duplicate_claims(
    race_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = race_ctx
    base_out = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )
    base_cat = MLCatalogPayload.model_validate(
        json.loads((TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8"))
    )
    probe = _ConcurrencyProbeMLAdapter(base_out, base_cat, sleep_seconds=0.05)
    ml_manager = MLProviderManager(settings, mock_adapter=probe, redis_client=redis_client)

    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        headers, farm_id, _ = await _register_and_seed_field(client, as_guest=False)
        req_ids = await _enqueue_n(client, headers, farm_id, 12)

    # Spawn 6 independent worker pools racing to claim the 12 queued jobs simultaneously.
    worker_engines = [create_db_engine(settings, role="worker") for _ in range(6)]
    try:
        runners = [
            WorkerRunner(
                settings=settings,
                engine=wk_engine,
                sessionmaker=create_sessionmaker(wk_engine),
                redis_client=redis_client,
                ml_manager=ml_manager,
                heartbeat_interval_seconds=0.1,
                poll_interval_seconds=0.02,
                bulkhead_probe_interval_seconds=0.02,
            )
            for wk_engine in worker_engines
        ]
        results = await asyncio.gather(*(runner.drain_until_idle() for runner in runners))
    finally:
        await asyncio.gather(*(wk_engine.dispose() for wk_engine in worker_engines))

    flat_ids = [item.request_id for group in results for item in group]
    assert sorted(flat_ids) == sorted(req_ids)
    assert len(probe.invocations) == 12
    assert len(set(probe.invocations)) == 12

    async with sessionmaker() as db:
        rows = (
            await db.execute(select(AnalysisRequest).where(AnalysisRequest.request_id.in_(req_ids)))
        ).scalars().all()
        assert len(rows) == 12
        assert all(r.status == "ok" and r.attempts == 1 for r in rows)


@pytest.mark.asyncio
async def test_advisory_lock_bulkhead_cap_and_e4_pool_headroom(
    race_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _, engine, sessionmaker, redis_client = race_ctx
    bulkhead_settings = _race_settings(
        WORKER_CONCURRENCY=12,
        ML_MAX_CONCURRENT_REQUESTS=8,
    )
    wk_engine = create_db_engine(bulkhead_settings, role="worker")
    wk_sessionmaker = create_sessionmaker(wk_engine)

    base_out = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )
    base_cat = MLCatalogPayload.model_validate(
        json.loads((TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8"))
    )
    probe = _ConcurrencyProbeMLAdapter(base_out, base_cat, sleep_seconds=0.2)
    ml_manager = MLProviderManager(
        bulkhead_settings, mock_adapter=probe, redis_client=redis_client
    )

    app = create_app(bulkhead_settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            headers, farm_id, _ = await _register_and_seed_field(client, as_guest=False)
            req_ids = await _enqueue_n(client, headers, farm_id, 14)

        runner = WorkerRunner(
            settings=bulkhead_settings,
            engine=wk_engine,
            sessionmaker=wk_sessionmaker,
            redis_client=redis_client,
            ml_manager=ml_manager,
            heartbeat_interval_seconds=0.05,
            poll_interval_seconds=0.02,
            bulkhead_probe_interval_seconds=0.02,
        )
        max_pg_advisory_locks = 0

        async def _slot_worker() -> list[str]:
            done: list[str] = []
            while True:
                res = await runner.run_once()
                if res is None:
                    break
                done.append(res.request_id)
            return done

        async def _monitor_pg_locks() -> None:
            nonlocal max_pg_advisory_locks
            while True:
                async with engine.connect() as conn:
                    val = int(
                        (
                            await conn.execute(
                                text(
                                    "SELECT COUNT(*) FROM pg_locks "
                                    "WHERE locktype = 'advisory' AND objid BETWEEN 1001 AND 1008"
                                )
                            )
                        ).scalar_one()
                    )
                    max_pg_advisory_locks = max(max_pg_advisory_locks, val)
                await asyncio.sleep(0.03)

        mon_task = asyncio.create_task(_monitor_pg_locks())
        try:
            worker_outcomes = await asyncio.gather(*(_slot_worker() for _ in range(12)))
        finally:
            mon_task.cancel()
            await asyncio.gather(mon_task, return_exceptions=True)

        claimed = [rid for group in worker_outcomes for rid in group]
        assert sorted(claimed) == sorted(req_ids)
        assert probe.max_observed <= 8
        assert probe.max_observed >= 2
        assert max_pg_advisory_locks <= 8

        async with engine.connect() as conn:
            leaked = int(
                (
                    await conn.execute(
                        text(
                            "SELECT COUNT(*) FROM pg_locks "
                            "WHERE locktype = 'advisory' AND objid BETWEEN 1001 AND 1008"
                        )
                    )
                ).scalar_one()
            )
            assert leaked == 0
    finally:
        await wk_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_guest_ml_refund_cap_under_row_locks(
    race_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = race_ctx
    base_out = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )
    base_cat = MLCatalogPayload.model_validate(
        json.loads((TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8"))
    )
    probe = _ConcurrencyProbeMLAdapter(base_out, base_cat, sleep_seconds=0.05, fail_503=True)
    ml_manager = MLProviderManager(settings, mock_adapter=probe, redis_client=redis_client)

    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        headers, farm_id, guest_tok = await _register_and_seed_field(client, as_guest=True)
        assert guest_tok is not None
        req_ids = await _enqueue_n(client, headers, farm_id, 6)

    tok_hash = hash_token(guest_tok)
    runner = WorkerRunner(
        settings=settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
        heartbeat_interval_seconds=0.1,
        poll_interval_seconds=0.02,
        bulkhead_probe_interval_seconds=0.02,
    )
    await asyncio.gather(*(runner.drain_until_idle() for _ in range(4)))

    async with sessionmaker() as db:
        refunded_count = int(
            (
                await db.execute(
                    select(func.count(AnalysisRequest.request_id)).where(
                        AnalysisRequest.request_id.in_(req_ids),
                        AnalysisRequest.status == "failed",
                        AnalysisRequest.sent_at.is_not(None),
                        AnalysisRequest.quota_units == 0,
                    )
                )
            ).scalar_one()
        )
        charged_count = int(
            (
                await db.execute(
                    select(func.count(AnalysisRequest.request_id)).where(
                        AnalysisRequest.request_id.in_(req_ids),
                        AnalysisRequest.status == "failed",
                        AnalysisRequest.quota_units == 4,
                    )
                )
            ).scalar_one()
        )
        assert refunded_count == 3
        assert charged_count == 3

    assert int(await redis_client.get(guest_quota_key(tok_hash))) == 12
