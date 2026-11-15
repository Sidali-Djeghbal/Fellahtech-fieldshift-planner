"""Real PostGIS + Redis integration tests for M8 Worker Core, Cancellations & Refunds."""

from __future__ import annotations

import asyncio
import copy
import gzip
import json
import os
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from redis.exceptions import RedisError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.rate_limit import guest_quota_key
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import (
    MLAdapter,
    MLCatalogVersionMismatchError,
    MLHealthResult,
    MLProviderManager,
    MockMLAdapter,
    ProviderKind,
)
from app.models import AnalysisRequest, AnalysisResult, CropCatalog, Farm
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import MLCatalogPayload
from app.worker.healthcheck import check_worker_health
from app.worker.jobs import ResultVerificationOutcome, verify_analysis_result_basic
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _worker_settings(**overrides: Any) -> Settings:
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
        "GUEST_CREATE_PER_IP_HOUR": 100,
        "GUEST_BURST_PER_MIN": 200,
        "RATE_LIMIT_CRUD_PER_MIN": 200,
        "RATE_LIMIT_ANALYSIS_PER_HOUR": 100,
        "ANALYSIS_PER_IP_HOUR": 100,
        "TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128",
        "WORKER_CONCURRENCY": 4,
        "ML_MAX_CONCURRENT_REQUESTS": 8,
        "ML_MAX_RETRIES": 1,
        "JOB_LEASE_SECONDS": 90,
        "MAX_JOB_ATTEMPTS": 2,
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
        await db.commit()


async def _seed_catalog(sessionmaker: async_sessionmaker[AsyncSession]) -> MLCatalogPayload:
    raw = json.loads((TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8"))
    payload = MLCatalogPayload.model_validate(raw)
    async with sessionmaker() as db:
        await catalog_repo.upsert_catalog_and_prune(
            db,
            payload=payload,
            synced_at=datetime.now(UTC),
            retain_versions=2,
        )
        await db.commit()
    return payload


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
async def m8_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[
        Settings,
        AsyncEngine,
        async_sessionmaker[AsyncSession],
        redis_async.Redis,
    ]
]:
    del migrated_database
    settings = _worker_settings()
    engine = create_db_engine(settings, role="worker")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
    await _cleanup_all(sessionmaker)
    await _seed_catalog(sessionmaker)
    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await _cleanup_all(sessionmaker)
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


def _make_bound_app(
    settings: Settings,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    redis_client: redis_async.Redis,
    ml_manager: MLProviderManager,
) -> Any:
    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager
    return app


def _make_runner(
    settings: Settings,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    redis_client: Any,
    ml_manager: MLProviderManager,
    *,
    heartbeat_interval_s: float = 0.05,
    verifier: Any = None,
) -> WorkerRunner:
    return WorkerRunner(
        settings=settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
        verifier=verifier,
        heartbeat_interval_seconds=heartbeat_interval_s,
        poll_interval_seconds=0.02,
        reap_interval_seconds=1.0,
        bulkhead_probe_interval_seconds=0.02,
        jitter_fn=lambda: 0.0,
    )


async def _setup_guest_and_field(
    client: httpx.AsyncClient,
    *,
    crop_history_count: int = 1,
    ip: str = "198.51.100.31",
) -> tuple[str, dict[str, str], str]:
    guest_resp = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert guest_resp.status_code == 201
    guest_tok = str(guest_resp.json()["guest_token"])
    headers = {"X-Guest-Token": guest_tok, "X-Forwarded-For": ip}

    farm_resp = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": "Worker Test Farm", "country": "Algeria", "region": "Guelma"},
    )
    assert farm_resp.status_code == 201
    farm_id = str(farm_resp.json()["farm_id"])

    history = [
        {
            "season": "spring",
            "year": 2020 + idx,
            "planting_month": 3,
            "crop_id": "durum_wheat",
            "crop_name_raw": "Durum Wheat",
            "yield_tons_per_hectare": 3.1,
        }
        for idx in range(crop_history_count)
    ]
    fld_resp = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcelle F1",
            "is_unverified_demo_parcel": False,
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 10.0,
            "elevation_m": 250.0,
            "soil": {
                "soil_type": "loamy",
                "soil_ph": 7.0,
                "organic_matter_percent": 2.0,
                "soil_test_date": None,
            },
            "water": {
                "availability": "moderate",
                "source": "well",
                "source_other": None,
                "irrigation_system": "drip",
            },
            "crop_history": history,
        },
    )
    assert fld_resp.status_code == 201
    return guest_tok, headers, farm_id


async def _submit_job(
    client: httpx.AsyncClient,
    headers: Mapping[str, str],
    farm_id: str,
    *,
    wait: bool = False,
    target_crops: list[str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"/api/v1/analysis{'?wait=true' if wait else ''}",
        headers=headers,
        json={
            "farm_id": farm_id,
            "field_ids": ["F1"],
            "language": "en",
            "planning": {
                "start_season": "spring",
                "start_year": 2027,
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
                "target_crop_ids": target_crops if target_crops is not None else ["chickpea"],
                "excluded_crop_ids": [],
                "equipment_constraints": [],
            },
        },
    )


async def _count_active_bulkhead_locks(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        res = await conn.execute(
            text(
                "SELECT COUNT(*) FROM pg_locks "
                "WHERE locktype = 'advisory' AND objid BETWEEN 1001 AND 1064"
            )
        )
        return int(res.scalar_one())


@pytest.mark.asyncio
async def test_worker_happy_e2e_poll_permalink_and_sync_wait(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m8_ctx
    mock_adapter = MockMLAdapter()
    ml_manager = MLProviderManager(settings, mock_adapter=mock_adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)
    runner = _make_runner(settings, engine, sessionmaker, redis_client, ml_manager)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        _, headers, farm_id = await _setup_guest_and_field(client)
        queued_resp = await _submit_job(client, headers, farm_id, wait=False)
        assert queued_resp.status_code == 202
        request_id = str(queued_resp.json()["request_id"])

        summary = await runner.run_once()
        assert summary is not None
        assert summary.outcome == "completed"
        assert summary.analysis_id is not None
        assert summary.analysis_id.startswith("analysis_")

        poll_resp = await client.get(f"/api/v1/analysis/requests/{request_id}", headers=headers)
        assert poll_resp.status_code == 200
        poll_body = poll_resp.json()
        assert poll_body["status"] == "ok"
        assert poll_body["analysis_id"] == summary.analysis_id

        perm_resp = await client.get(f"/api/v1/analysis/{summary.analysis_id}", headers=headers)
        assert perm_resp.status_code == 200
        assert perm_resp.json()["analysis_id"] == summary.analysis_id

        # Verify synchronous `?wait=true` completes concurrently when worker is running.
        async def _background_drain() -> None:
            for _ in range(100):
                if await runner.run_once() is not None:
                    return
                await asyncio.sleep(0.02)

        bg = asyncio.create_task(_background_drain())
        sync_resp = await _submit_job(client, headers, farm_id, wait=True)
        await bg
        assert sync_resp.status_code == 200
        assert sync_resp.json()["status"] == "ok"
        assert await _count_active_bulkhead_locks(engine) == 0


@pytest.mark.asyncio
async def test_worker_stale_lease_reclaim_and_reaper(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m8_ctx
    mock_adapter = MockMLAdapter()
    ml_manager = MLProviderManager(settings, mock_adapter=mock_adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)
    runner = _make_runner(settings, engine, sessionmaker, redis_client, ml_manager)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_tok, headers, farm_id = await _setup_guest_and_field(client)
        tok_hash = hash_token(guest_tok)

        r1 = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        r2 = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        r3 = str((await _submit_job(client, headers, farm_id)).json()["request_id"])

        past = datetime.now(UTC) - timedelta(seconds=30)
        async with sessionmaker() as db:
            # r1: crashed attempt=1 -> reclaimable via SKIP LOCKED!
            req1 = await db.get(AnalysisRequest, r1)
            assert req1 is not None
            req1.status = "running"
            req1.attempts = 1
            req1.lease_until = past
            # r2: crashed attempt=2 (>= MAX_JOB_ATTEMPTS=2) -> reaped as failed & refunded!
            req2 = await db.get(AnalysisRequest, r2)
            assert req2 is not None
            req2.status = "running"
            req2.attempts = 2
            req2.sent_at = past
            req2.lease_until = past
            # r3: crashed after cancel before finalization (sent_at IS NULL) -> reaped cancelled!
            req3 = await db.get(AnalysisRequest, r3)
            assert req3 is not None
            req3.status = "running"
            req3.attempts = 1
            req3.cancelled_at = past
            req3.sent_at = None
            req3.lease_until = past
            await db.commit()

        claimed = await runner.run_once()
        assert claimed is not None
        assert claimed.request_id == r1
        assert claimed.outcome == "completed"
        assert await runner.run_once() is None

        swept = await runner.reap_stale_jobs_once()
        assert swept == 2

        async with sessionmaker() as db:
            row1 = await db.get(AnalysisRequest, r1)
            row2 = await db.get(AnalysisRequest, r2)
            row3 = await db.get(AnalysisRequest, r3)
            assert row1 is not None and row1.status == "ok" and row1.attempts == 2
            assert (
                row2 is not None
                and row2.status == "failed"
                and row2.error_code == ErrorCode.INTERNAL_ERROR.value
                and row2.quota_units == 0
            )
            assert row3 is not None and row3.status == "cancelled" and row3.quota_units == 0

        cached_q = await redis_client.get(guest_quota_key(tok_hash))
        assert int(cached_q) == 4


class _ControllableSlowMLAdapter(MLAdapter):
    """Test adapter supporting cancel barriers, backoff aborts & sequence injections."""

    def __init__(self, template_output: dict[str, Any], template_catalog: MLCatalogPayload) -> None:
        self._template_output = template_output
        self._template_catalog = template_catalog
        self.analyze_calls = 0
        self.started_event = asyncio.Event()
        self.release_event = asyncio.Event()
        self.cancelled_midflight = False
        self.hold_on_analyze = False
        self.custom_analyze_fn: (
            Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]] | None
        ) = None

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
        self.analyze_calls += 1
        parsed = (
            json.loads(payload.decode("utf-8")) if isinstance(payload, bytes) else dict(payload)
        )
        if self.custom_analyze_fn is not None:
            return await self.custom_analyze_fn(parsed, idempotency_key)
        if self.hold_on_analyze:
            self.started_event.set()
            try:
                await self.release_event.wait()
            except asyncio.CancelledError:
                self.cancelled_midflight = True
                raise
        out = copy.deepcopy(self._template_output)
        out["request_id"] = idempotency_key
        out["dataset_version_used"] = str(parsed["dataset_version"])
        return out

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


@pytest.mark.asyncio
async def test_worker_cooperative_cancellations_all_checkpoints(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m8_ctx
    base_out: dict[str, Any] = dict(
        json.loads((TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8"))
    )
    base_cat = MLCatalogPayload.model_validate(
        json.loads((TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8"))
    )
    adapter = _ControllableSlowMLAdapter(base_out, base_cat)
    ml_manager = MLProviderManager(settings, mock_adapter=adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)
    runner = _make_runner(
        settings, engine, sessionmaker, redis_client, ml_manager, heartbeat_interval_s=0.05
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_tok, headers, farm_id = await _setup_guest_and_field(client)
        tok_hash = hash_token(guest_tok)

        # Checkpoint 1: Pre-dispatch cancel (`cancelled_at` already set on claimed running row).
        r_pre = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        async with sessionmaker() as db:
            await db.execute(
                text(
                    "UPDATE public.analysis_requests "
                    "SET status = 'running', attempts = 1, cancelled_at = now() "
                    "WHERE request_id = :rid"
                ),
                {"rid": r_pre},
            )
            await db.commit()
        pre_res = await runner.execute_claimed_job(r_pre)
        assert pre_res.outcome == "cancelled"
        assert pre_res.refunded_quarters == 4
        assert adapter.analyze_calls == 0
        assert await _count_active_bulkhead_locks(engine) == 0

        # Checkpoint 2: Mid-flight slow ML HTTP abort via cooperative heartbeat cancel.
        adapter.hold_on_analyze = True
        r_mid = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        mid_task = asyncio.create_task(runner.run_once())
        await asyncio.wait_for(adapter.started_event.wait(), timeout=3.0)

        cancel_resp = await client.post(
            f"/api/v1/analysis/requests/{r_mid}/cancel",
            headers=headers,
        )
        assert cancel_resp.status_code == 200
        mid_res = await asyncio.wait_for(mid_task, timeout=3.0)
        assert mid_res is not None
        assert mid_res.outcome == "cancelled"
        assert adapter.cancelled_midflight is True
        assert await _count_active_bulkhead_locks(engine) == 0

        # Checkpoint 3: Final cascade guard catches cancel after ML 200 OK before INSERT result.
        adapter.hold_on_analyze = False
        r_fin = str((await _submit_job(client, headers, farm_id)).json()["request_id"])

        async def _cancel_inside_verifier(
            result_payload: Mapping[str, Any],
            *,
            expected_dataset_version: str,
            input_snapshot: Mapping[str, Any],
        ) -> ResultVerificationOutcome:
            async with sessionmaker() as vdb:
                await vdb.execute(
                    text(
                        "UPDATE public.analysis_requests SET cancelled_at = now() "
                        "WHERE request_id = :rid"
                    ),
                    {"rid": r_fin},
                )
                await vdb.commit()
            return await verify_analysis_result_basic(
                result_payload,
                expected_dataset_version=expected_dataset_version,
                input_snapshot=input_snapshot,
            )

        guard_runner = _make_runner(
            settings,
            engine,
            sessionmaker,
            redis_client,
            ml_manager,
            verifier=_cancel_inside_verifier,
        )
        fin_res = await guard_runner.run_once()
        assert fin_res is not None
        assert fin_res.outcome == "cancelled"

        async with sessionmaker() as db:
            res_count = int(
                (
                    await db.execute(
                        select(func.count(AnalysisResult.id)).where(
                            AnalysisResult.request_id.in_([r_pre, r_mid, r_fin])
                        )
                    )
                ).scalar_one()
            )
            assert res_count == 0
        # Only r_pre (sent_at IS NULL) refunded (4Q -> 0Q), whereas r_mid/r_fin kept sent_at!=NULL.
        cached = await redis_client.get(guest_quota_key(tok_hash))
        assert int(cached) == 8

        # Checkpoint 4: Mid-flight DELETE /farms/{farm_id} cascade delete guard.
        adapter.hold_on_analyze = True
        adapter.started_event.clear()
        adapter.release_event.clear()
        await _submit_job(client, headers, farm_id)
        del_task = asyncio.create_task(runner.run_once())
        await asyncio.wait_for(adapter.started_event.wait(), timeout=3.0)
        async with sessionmaker() as db:
            farm_pk = int(farm_id.split("_")[1])
            farm_row = await db.get(Farm, farm_pk)
            assert farm_row is not None
            await db.delete(farm_row)
            await db.commit()
        adapter.release_event.set()
        del_res = await asyncio.wait_for(del_task, timeout=3.0)
        assert del_res is not None
        assert del_res.outcome in ("cancelled", "vanished")
        assert await _count_active_bulkhead_locks(engine) == 0


@pytest.mark.asyncio
async def test_worker_409_catalog_sync_and_413_payload_trim(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m8_ctx
    base_out: dict[str, Any] = dict(
        json.loads((TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8"))
    )
    raw_cat = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
    )
    cat_v2_data = copy.deepcopy(raw_cat)
    cat_v2_data["catalog_version"] = "2026.12-guelma-v2"
    cat_v2 = MLCatalogPayload.model_validate(cat_v2_data)

    adapter = _ControllableSlowMLAdapter(base_out, cat_v2)
    observed_versions: list[str] = []
    observed_history_counts: list[int] = []

    async def _fault_then_ok_409(parsed: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        observed_versions.append(str(parsed["catalog_version"]))
        if len(observed_versions) == 1:
            raise MLCatalogVersionMismatchError("Stale catalog version")
        out: dict[str, Any] = copy.deepcopy(base_out)
        out["request_id"] = idempotency_key
        out["dataset_version_used"] = str(parsed["dataset_version"])
        return out

    adapter.custom_analyze_fn = _fault_then_ok_409
    ml_manager = MLProviderManager(settings, mock_adapter=adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)
    runner = _make_runner(settings, engine, sessionmaker, redis_client, ml_manager)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        _, headers, farm_id = await _setup_guest_and_field(client, crop_history_count=6)
        await _submit_job(client, headers, farm_id)
        s_409 = await runner.run_once()
        assert s_409 is not None and s_409.outcome == "completed" and s_409.retries_used == 1
        assert observed_versions == [str(raw_cat["catalog_version"]), "2026.12-guelma-v2"]

        # 413 PAYLOAD_TOO_LARGE -> trims history for retry, preserves immutable DB snapshot!
        class _TrimSpyAdapter(_ControllableSlowMLAdapter):
            async def analyze(
                self,
                payload: bytes | Mapping[str, Any],
                *,
                idempotency_key: str,
                compress: bool = False,
            ) -> dict[str, Any]:
                del compress
                parsed = (
                    json.loads(payload.decode("utf-8"))
                    if isinstance(payload, bytes)
                    else dict(payload)
                )
                if self.custom_analyze_fn is not None:
                    return await self.custom_analyze_fn(parsed, idempotency_key)
                observed_history_counts.append(len(parsed["fields"][0]["crop_history"]))
                if len(observed_history_counts) == 1:
                    from app.ml_client.base import MLPayloadTooLargeError

                    raise MLPayloadTooLargeError("Too large")
                out: dict[str, Any] = copy.deepcopy(base_out)
                out["request_id"] = idempotency_key
                out["dataset_version_used"] = str(parsed["dataset_version"])
                return out

        trim_adapter = _TrimSpyAdapter(base_out, cat_v2)
        ml_manager_trim = MLProviderManager(
            settings, mock_adapter=trim_adapter, redis_client=redis_client
        )
        runner_trim = _make_runner(settings, engine, sessionmaker, redis_client, ml_manager_trim)
        r_413 = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        s_413 = await runner_trim.run_once()
        assert s_413 is not None and s_413.outcome == "completed" and s_413.retries_used == 1
        assert observed_history_counts == [6, 3]

        async with sessionmaker() as db:
            db_req = await db.get(AnalysisRequest, r_413)
            assert db_req is not None and db_req.input_snapshot_gz is not None
            stored_snap = json.loads(gzip.decompress(db_req.input_snapshot_gz).decode("utf-8"))
            assert len(stored_snap["fields"][0]["crop_history"]) == 6

        # Catalog mismatch where requested crop dropped in synced v3 -> immediate 409 fail.
        cat_v3_data = copy.deepcopy(raw_cat)
        cat_v3_data["catalog_version"] = "2027.01-guelma-v3"
        cat_v3_data["crops"] = [
            item for item in cat_v3_data["crops"] if item["crop_id"] != "chickpea"
        ]
        trim_adapter._template_catalog = MLCatalogPayload.model_validate(cat_v3_data)

        async def _always_409(_parsed: dict[str, Any], _key: str) -> dict[str, Any]:
            raise MLCatalogVersionMismatchError()

        trim_adapter.custom_analyze_fn = _always_409
        # Re-seed catalog back to v1 briefly so W1 accepts `chickpea` before ML rejects.
        async with sessionmaker() as db:
            await db.execute(select(CropCatalog).limit(1))
        await _seed_catalog(sessionmaker)
        r_bad_cat = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        s_bad_cat = await runner_trim.run_once()
        assert s_bad_cat is not None
        assert s_bad_cat.outcome == "failed"
        assert s_bad_cat.error_code == ErrorCode.CATALOG_VERSION_MISMATCH.value
        assert s_bad_cat.request_id == r_bad_cat


@pytest.mark.asyncio
async def test_worker_guest_refund_cap_insufficient_and_redis_resilience(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m8_ctx
    mock_adapter = MockMLAdapter()
    ml_manager = MLProviderManager(settings, mock_adapter=mock_adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)
    runner = _make_runner(
        settings,
        engine,
        sessionmaker,
        redis_client,
        ml_manager,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_tok, headers, farm_id = await _setup_guest_and_field(client)
        tok_hash = hash_token(guest_tok)

        # 1. Pending cancel refunds without consuming the 3-ML-refund cap.
        r_cancel = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        assert (
            await client.post(f"/api/v1/analysis/requests/{r_cancel}/cancel", headers=headers)
        ).status_code == 200

        # 2. 422 INSUFFICIENT_DATA does NOT refund guest (quota_units=4 kept).
        mock_adapter.set_fault_mode("http_422_insufficient")
        r_insuff = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        s_insuff = await runner.run_once()
        assert s_insuff is not None
        assert s_insuff.outcome == "failed"
        assert s_insuff.error_code == ErrorCode.INSUFFICIENT_DATA.value
        assert s_insuff.refunded_quarters == 0

        # 3. Up to GUEST_MAX_ML_REFUNDS=3 external ML errors ARE refunded cleanly.
        for seq in (
            ["timeout", "timeout"],
            ["http_503", "http_503"],
            ["ml_dataset_error"],
        ):
            mock_adapter.set_fault_sequence(seq)
            await _submit_job(client, headers, farm_id)
            out = await runner.run_once()
            assert out is not None and out.outcome == "failed" and out.refunded_quarters == 4

        # 4. 4th external ML failure hits GUEST_MAX_ML_REFUNDS=3 ceiling -> NO refund!
        mock_adapter.set_fault_mode("http_400")
        await _submit_job(client, headers, farm_id)
        out_4th = await runner.run_once()
        assert out_4th is not None
        assert out_4th.outcome == "failed"
        assert out_4th.error_code == ErrorCode.ML_CONTRACT_ERROR.value
        assert out_4th.refunded_quarters == 0

        # Expected remaining guest quota: 0(cancel) + 4(insufficient) + 0*3 + 4(4th) = 8 quarters.
        assert int(await redis_client.get(guest_quota_key(tok_hash))) == 8

        # 5. Stage 1 / SEM-07 failures persist invalid result JSON with validation_passed=False.
        mock_adapter.set_fault_mode("wrong_dataset_version")
        r_sem07 = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        await runner.run_once()
        async with sessionmaker() as db:
            invalid_res = (
                await db.execute(select(AnalysisResult).where(AnalysisResult.request_id == r_sem07))
            ).scalar_one_or_none()
            assert invalid_res is not None
            assert invalid_res.status == "invalid"
            assert invalid_res.validation_passed is False
            req_sem07 = await db.get(AnalysisRequest, r_sem07)
            assert req_sem07 is not None
            assert req_sem07.error_code == ErrorCode.DATASET_VERSION_UNAVAILABLE.value

        # 6. Worker backoff sleep cancellation aborts immediately (< 1.0s) instead of waiting 2s.
        mock_adapter.set_fault_sequence(["http_503", "none"])
        r_backoff = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        t0 = time.monotonic()
        task = asyncio.create_task(runner.run_once())
        await asyncio.sleep(0.15)
        await client.post(f"/api/v1/analysis/requests/{r_backoff}/cancel", headers=headers)
        cancelled_backoff = await asyncio.wait_for(task, timeout=1.5)
        assert cancelled_backoff is not None and cancelled_backoff.outcome == "cancelled"
        assert (time.monotonic() - t0) < 1.2
        assert await _count_active_bulkhead_locks(engine) == 0
        assert r_insuff != r_backoff

    # 7. Simulated Redis failure during worker refund commits PG quota_units=0 unconditionally!
    class _BrokenRedis:
        def get(self, name: str) -> Any:
            del name
            raise RedisError("Redis offline")

        def eval(self, script: str, numkeys: int, *keys_and_args: str) -> Any:
            del script, numkeys, keys_and_args
            raise RedisError("Redis offline")

    guest2_tok: str
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest2_tok, h2, f2 = await _setup_guest_and_field(client, ip="198.51.100.44")
        del guest2_tok
        mock_adapter.set_fault_sequence(["ml_dataset_error"])
        r_broken_redis = str((await _submit_job(client, h2, f2)).json()["request_id"])

    broken_runner = _make_runner(
        settings,
        engine,
        sessionmaker,
        _BrokenRedis(),
        ml_manager,
    )
    res_broken = await broken_runner.run_once()
    assert res_broken is not None
    assert res_broken.outcome == "failed"
    assert res_broken.refunded_quarters == 4
    async with sessionmaker() as db:
        row_b = await db.get(AnalysisRequest, r_broken_redis)
        assert row_b is not None and row_b.quota_units == 0


@pytest.mark.asyncio
async def test_worker_healthcheck_live_and_broken_redis(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _, _, _ = m8_ctx
    assert await check_worker_health(settings) is True

    bad_settings = _worker_settings(REDIS_URL="redis://127.0.0.1:6399/0")
    with pytest.raises(RedisError):
        await check_worker_health(bad_settings)


@pytest.mark.asyncio
async def test_worker_runner_loop_rate_limit_retry_and_corrupt_snapshot(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    from app.ml_client import ML_PROVIDER_STATUS_REDIS_KEY

    settings, engine, sessionmaker, redis_client = m8_ctx
    mock_adapter = MockMLAdapter()
    ml_manager = MLProviderManager(settings, mock_adapter=mock_adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)
    runner = _make_runner(settings, engine, sessionmaker, redis_client, ml_manager)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        _, headers, farm_id = await _setup_guest_and_field(client)
        r_429 = str((await _submit_job(client, headers, farm_id)).json()["request_id"])
        r_corrupt = str(
            (await _submit_job(client, headers, farm_id, target_crops=["durum_wheat"])).json()[
                "request_id"
            ]
        )

    mock_adapter.set_fault_mode("none", retry_after_seconds=0)
    mock_adapter.set_fault_sequence(["http_429", "none"])

    async with sessionmaker() as db:
        bad_row = await db.get(AnalysisRequest, r_corrupt)
        assert bad_row is not None
        bad_row.input_snapshot_gz = b"not-valid-gzip"
        await db.commit()

    stop_event = asyncio.Event()
    loop_task = asyncio.create_task(runner.run(stop_event))
    try:
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            async with sessionmaker() as db:
                row_429 = await db.get(AnalysisRequest, r_429)
                row_corrupt = await db.get(AnalysisRequest, r_corrupt)
                if (
                    row_429 is not None
                    and row_corrupt is not None
                    and row_429.status == "ok"
                    and row_corrupt.status == "failed"
                ):
                    break
            await asyncio.sleep(0.05)
    finally:
        stop_event.set()
        await asyncio.wait_for(loop_task, timeout=5.0)

    raw_status = await redis_client.get(ML_PROVIDER_STATUS_REDIS_KEY)
    assert raw_status is not None
    async with sessionmaker() as db:
        fin_429 = await db.get(AnalysisRequest, r_429)
        fin_corrupt = await db.get(AnalysisRequest, r_corrupt)
        assert fin_429 is not None and fin_429.status == "ok"
        assert fin_corrupt is not None
        assert fin_corrupt.status == "failed"
        assert fin_corrupt.error_code == ErrorCode.INTERNAL_ERROR.value
        assert fin_corrupt.quota_units == 0
    assert await _count_active_bulkhead_locks(engine) == 0


@pytest.mark.asyncio
async def test_worker_pretrim_untrimmable_and_service_lifecycle(
    m8_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    from app.ml_client.base import MLPayloadTooLargeError
    from app.worker.jobs import serialize_compact_json
    from app.worker.runner import acquire_ml_bulkhead_slot, run_worker_service

    settings, engine, sessionmaker, redis_client = m8_ctx
    mock_adapter = MockMLAdapter()
    ml_manager = MLProviderManager(settings, mock_adapter=mock_adapter, redis_client=redis_client)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client, ml_manager)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        _, h6, f6 = await _setup_guest_and_field(
            client, crop_history_count=6, ip="198.51.100.77"
        )
        r_pretrim = str((await _submit_job(client, h6, f6)).json()["request_id"])

        async with sessionmaker() as db:
            snap_row = await db.get(AnalysisRequest, r_pretrim)
            assert snap_row is not None and snap_row.input_snapshot_gz is not None
            snap_dict = json.loads(gzip.decompress(snap_row.input_snapshot_gz).decode("utf-8"))
        full_bytes = len(serialize_compact_json(snap_dict))
        one_item_copy = copy.deepcopy(snap_dict)
        one_item_copy["fields"][0]["crop_history"] = snap_dict["fields"][0]["crop_history"][-1:]
        min_bytes = len(serialize_compact_json(one_item_copy))
        mid_limit = (full_bytes + min_bytes) // 2

        pretrim_runner = _make_runner(
            _worker_settings(ML_MAX_PAYLOAD_BYTES=mid_limit),
            engine,
            sessionmaker,
            redis_client,
            ml_manager,
        )
        s_pre = await pretrim_runner.run_once()
        assert s_pre is not None and s_pre.outcome == "completed"

        _, h1, f1 = await _setup_guest_and_field(
            client, crop_history_count=1, ip="198.51.100.78"
        )
        await _submit_job(client, h1, f1)
        tiny_runner = _make_runner(
            _worker_settings(ML_MAX_PAYLOAD_BYTES=min_bytes - 50),
            engine,
            sessionmaker,
            redis_client,
            ml_manager,
        )
        s_tiny = await tiny_runner.run_once()
        assert (
            s_tiny is not None
            and s_tiny.outcome == "failed"
            and s_tiny.error_code == ErrorCode.INTERNAL_ERROR.value
        )

        # 413 on single-item history -> untrimmable retry failure -> INTERNAL_ERROR.
        class _Always413Adapter(MLAdapter):
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
                del payload, idempotency_key, compress
                raise MLPayloadTooLargeError("Always 413")

            async def get_catalog(self) -> MLCatalogPayload:
                return await mock_adapter.get_catalog()

            async def get_health(self) -> MLHealthResult:
                return await mock_adapter.get_health()

            async def aclose(self) -> None:
                return None

        mgr_413 = MLProviderManager(
            settings, mock_adapter=_Always413Adapter(), redis_client=redis_client
        )
        runner_413 = _make_runner(settings, engine, sessionmaker, redis_client, mgr_413)
        await _submit_job(client, h1, f1, target_crops=["durum_wheat"])
        s_413_fail = await runner_413.run_once()
        assert (
            s_413_fail is not None
            and s_413_fail.outcome == "failed"
            and s_413_fail.error_code == ErrorCode.INTERNAL_ERROR.value
        )

    vanished = await runner_413.execute_claimed_job("00000000-0000-4000-8000-000000000099")
    assert vanished.outcome == "vanished"

    with pytest.raises(ValueError, match="max_concurrent"):
        async with acquire_ml_bulkhead_slot(engine, max_concurrent=0):
            pass

    svc_task = asyncio.create_task(run_worker_service(settings))
    await asyncio.sleep(0.15)
    svc_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await svc_task


def test_worker_healthcheck_main_cli(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.worker.healthcheck import main as healthcheck_main

    del migrated_database
    for key, val in build_test_env().items():
        monkeypatch.setenv(key, val)
    monkeypatch.setenv("REDIS_URL", _redis_url())
    assert healthcheck_main() == 0

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6399/0")
    assert healthcheck_main() == 1
