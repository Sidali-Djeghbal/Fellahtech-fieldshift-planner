"""Real PostGIS + Redis integration tests for M9 verification persistence, IMPL-007 & collisions."""

from __future__ import annotations

import logging
import os
import re
import secrets
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
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
from app.core.metrics import ML_UNKNOWN_FIELDS_OBSERVED_TOTAL
from app.core.rate_limit import guest_quota_key
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, MockMLAdapter
from app.models import AnalysisRequest, AnalysisResult
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import MLCatalogPayload
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ANALYSIS_ID_RE = re.compile(r"^analysis_[0-9a-f]{12}$")


def _m9_settings() -> Settings:
    env = build_test_env()
    return Settings(
        _env_file=None,
        APP_ENV="test",
        ML_PROVIDER_MODE="mock",
        DATABASE_URL=env["DATABASE_URL"],
        DB_PASSWORD=env["DB_PASSWORD"],
        REDIS_URL=os.getenv(
            "TEST_REDIS_URL",
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ),
        ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
        ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
        JWT_SECRET_KEY=env["JWT_SECRET_KEY"],
        ML_SERVICE_API_KEY=env["ML_SERVICE_API_KEY"],
        GUEST_CREATE_PER_IP_HOUR=100,
        GUEST_BURST_PER_MIN=200,
        RATE_LIMIT_CRUD_PER_MIN=200,
        RATE_LIMIT_ANALYSIS_PER_HOUR=100,
        ANALYSIS_PER_IP_HOUR=100,
        TRUSTED_PROXY_CIDRS="127.0.0.1/32,::1/128",
        WORKER_CONCURRENCY=2,
        ML_MAX_CONCURRENT_REQUESTS=4,
        ML_MAX_RETRIES=1,
        JOB_LEASE_SECONDS=60,
        MAX_JOB_ATTEMPTS=2,
        GUEST_MAX_ML_REFUNDS=3,
        SEM04_NUMERIC_TOLERANCE=0.001,
    )


class _TamperingMockAdapter(MockMLAdapter):
    """Test double delegating to MockMLAdapter then applying deterministic payload mutations."""

    def __init__(self, *, mutator: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._mutator = mutator

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        result = await super().analyze(
            payload,
            idempotency_key=idempotency_key,
            compress=compress,
        )
        if self._mutator is not None:
            self._mutator(result)
        return result


@pytest_asyncio.fixture
async def m9_ctx() -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    settings = _m9_settings()
    engine = create_db_engine(settings, role="worker")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
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
            text(
                "UPDATE public.dataset_registry SET is_active = (dataset_version = :ver) "
                "WHERE dataset_version = :ver OR is_active = true"
            ),
            {"ver": DEFAULT_DATASET_VERSION},
        )
        raw_cat = (TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
        await catalog_repo.upsert_catalog_and_prune(
            db,
            payload=MLCatalogPayload.model_validate_json(raw_cat),
            synced_at=datetime.now(UTC),
            retain_versions=2,
        )
        await db.commit()
    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


async def _create_guest_field_and_submit(
    client: httpx.AsyncClient,
    *,
    soil_ph: float | None = None,
    ip: str = "198.51.100.77",
) -> tuple[str, str]:
    g = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert g.status_code == 201
    tok = str(g.json()["guest_token"])
    headers = {"X-Guest-Token": tok, "X-Forwarded-For": ip}

    f = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": "M9 Farm", "country": "Algeria", "region": "Guelma"},
    )
    assert f.status_code == 201
    farm_id = str(f.json()["farm_id"])

    fld = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcelle M9",
            "is_unverified_demo_parcel": False,
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 12.0,
            "elevation_m": 240.0,
            "soil": {
                "soil_type": "clay",
                "soil_ph": soil_ph,
                "organic_matter_percent": 1.8 if soil_ph is not None else None,
                "soil_test_date": None,
            },
            "water": {
                "availability": "moderate",
                "source": "well",
                "source_other": None,
                "irrigation_system": "drip",
            },
            "crop_history": [
                {
                    "season": "autumn",
                    "year": 2025,
                    "planting_month": 11,
                    "crop_id": "durum_wheat",
                    "crop_name_raw": "Durum Wheat",
                    "yield_tons_per_hectare": 2.8,
                }
            ],
        },
    )
    assert fld.status_code == 201

    sub = await client.post(
        "/api/v1/analysis",
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
                    "water_saving": 30,
                    "soil_improvement": 20,
                    "income": 30,
                    "risk_reduction": 10,
                    "forage_value": 10,
                },
                "market_preference": "mixed",
                "target_crop_ids": ["chickpea"],
                "excluded_crop_ids": [],
                "equipment_constraints": [],
            },
        },
    )
    assert sub.status_code == 202
    return tok, str(sub.json()["request_id"])


def _bind_app(
    settings: Settings,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    redis_client: redis_async.Redis,
    manager: MLProviderManager,
) -> Any:
    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = manager
    return app


def _make_runner(
    settings: Settings,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    redis_client: redis_async.Redis,
    manager: MLProviderManager,
) -> WorkerRunner:
    return WorkerRunner(
        settings=settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=manager,
        heartbeat_interval_seconds=0.05,
        poll_interval_seconds=0.02,
        reap_interval_seconds=1.0,
        bulkhead_probe_interval_seconds=0.02,
        jitter_fn=lambda: 0.0,
    )


@pytest.mark.asyncio
async def test_m9_tolerant_reader_5_1_and_schema_6_0_through_worker(
    m9_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings, engine, sessionmaker, redis_client = m9_ctx
    adapter = MockMLAdapter(fault_mode="none")
    manager = MLProviderManager(settings=settings, mock_adapter=adapter)
    app = _bind_app(settings, engine, sessionmaker, redis_client, manager)
    runner = _make_runner(settings, engine, sessionmaker, redis_client, manager)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        tok, rid_51 = await _create_guest_field_and_submit(client)
        adapter.set_fault_sequence(["extra_fields_5_1"])
        before_unknown = float(ML_UNKNOWN_FIELDS_OBSERVED_TOTAL._value.get())
        with caplog.at_level(logging.WARNING):
            res_51 = await runner.run_once()
        after_unknown = float(ML_UNKNOWN_FIELDS_OBSERVED_TOTAL._value.get())

        assert res_51 is not None
        assert res_51.request_id == rid_51
        assert res_51.outcome == "completed"
        assert res_51.analysis_id is not None
        assert ANALYSIS_ID_RE.match(res_51.analysis_id)
        assert after_unknown - before_unknown >= 1.0

        # Schema 6.0 rejects Stage 1, persists write-once invalid result_json & refunds guest.
        _, rid_60 = await _create_guest_field_and_submit(client, ip="198.51.100.78")
        # Wait: reuse same guest on a second submit to verify refund count directly.
        sub_60 = await client.post(
            "/api/v1/analysis",
            headers={"X-Guest-Token": tok, "X-Forwarded-For": "198.51.100.77"},
            json={
                "farm_id": str(
                    (
                        await client.get(
                            "/api/v1/farms",
                            headers={"X-Guest-Token": tok, "X-Forwarded-For": "198.51.100.77"},
                        )
                    ).json()["items"][0]["farm_id"]
                ),
                "field_ids": ["F1"],
                "language": "en",
                "planning": {
                    "start_season": "spring",
                    "start_year": 2027,
                    "horizon_seasons": 3,
                    "cycle_mode": "annual_rotation",
                    "planting_month": 3,
                    "scenario_overrides": {"temp_delta_c": 0.0, "precip_pct_delta": -5.0},
                },
                "priorities": {
                    "weights": {
                        "water_saving": 30,
                        "soil_improvement": 20,
                        "income": 30,
                        "risk_reduction": 10,
                        "forage_value": 10,
                    },
                    "market_preference": "mixed",
                    "target_crop_ids": ["chickpea"],
                    "excluded_crop_ids": [],
                    "equipment_constraints": [],
                },
            },
        )
        assert sub_60.status_code == 202
        rid_guest_60 = str(sub_60.json()["request_id"])
        adapter.set_fault_sequence(["schema_6_0"])
        res_60 = await runner.run_once()
        # Drain the queued rid_60 created above too if needed; assert our guest's rid_guest_60.
        if res_60 is not None and res_60.request_id == rid_60:
            adapter.set_fault_sequence(["schema_6_0"])
            res_60 = await runner.run_once()

        assert res_60 is not None
        assert res_60.request_id == rid_guest_60
        assert res_60.outcome == "failed"
        assert res_60.error_code == ErrorCode.ML_INVALID_RESPONSE.value
        assert res_60.refunded_quarters == 4

        async with sessionmaker() as db:
            ar_51 = (
                await db.execute(select(AnalysisResult).where(AnalysisResult.request_id == rid_51))
            ).scalar_one()
            assert ar_51.validation_passed is True
            assert "extra_tolerant_reader_metadata" in ar_51.result_json

            ar_60 = (
                await db.execute(
                    select(AnalysisResult).where(AnalysisResult.request_id == rid_guest_60)
                )
            ).scalar_one()
            assert ANALYSIS_ID_RE.match(ar_60.analysis_id)
            assert ar_60.validation_passed is False
            assert ar_60.result_json.get("schema_version") == "6.0"
            assert ar_60.validation_errors

            req_60 = (
                await db.execute(
                    select(AnalysisRequest).where(AnalysisRequest.request_id == rid_guest_60)
                )
            ).scalar_one()
            assert req_60.status == "failed"
            assert req_60.error_code == ErrorCode.ML_INVALID_RESPONSE.value

        # Guest consumed 4Q for rid_51 + 4Q refunded for rid_guest_60 => 4Q remaining out of 8Q.
        tok_hash = hash_token(tok)
        assert int(await redis_client.get(guest_quota_key(tok_hash))) == 4


@pytest.mark.asyncio
async def test_m9_sem04_fabricated_soil_and_impl007_dataset_priority_and_id_collision(
    m9_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, engine, sessionmaker, redis_client = m9_ctx

    def _inject_fabricated_soil(payload: dict[str, Any]) -> None:
        payload["field_plans"][0]["strategies"][0]["explanation"]["evidence"].append(
            {
                "data_source": "farmer_input",
                "parameter": "soil_ph",
                "observed_value": 6.8,
                "unit": None,
                "period": "2026",
                "derived": False,
                "interpretation": "Fabricated soil pH when input is null.",
            }
        )

    adapter_sem04 = _TamperingMockAdapter(mutator=_inject_fabricated_soil)
    mgr_sem04 = MLProviderManager(settings=settings, mock_adapter=adapter_sem04)
    app = _bind_app(settings, engine, sessionmaker, redis_client, mgr_sem04)
    runner_sem04 = _make_runner(settings, engine, sessionmaker, redis_client, mgr_sem04)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, rid_sem04 = await _create_guest_field_and_submit(client, soil_ph=None)
        out_sem04 = await runner_sem04.run_once()
        assert out_sem04 is not None
        assert out_sem04.request_id == rid_sem04
        assert out_sem04.outcome == "failed"
        assert out_sem04.error_code == ErrorCode.ML_INVALID_RESPONSE.value
        assert out_sem04.refunded_quarters == 4

        async with sessionmaker() as db:
            ar_sem04 = (
                await db.execute(
                    select(AnalysisResult).where(AnalysisResult.request_id == rid_sem04)
                )
            ).scalar_one()
            assert ANALYSIS_ID_RE.match(ar_sem04.analysis_id)
            assert ar_sem04.validation_passed is False
            assert ar_sem04.validation_errors is not None
            assert any(e["rule"] == "SEM-04" for e in ar_sem04.validation_errors)

        # IMPL-007: Stage-1-valid payload + mismatched dataset -> DATASET_VERSION_UNAVAILABLE.
        def _inject_wrong_ds(payload: dict[str, Any]) -> None:
            payload["dataset_version_used"] = "1999.01-wrong-ds"

        adapter_sem07 = _TamperingMockAdapter(mutator=_inject_wrong_ds)
        mgr_sem07 = MLProviderManager(settings=settings, mock_adapter=adapter_sem07)
        app.state.ml_provider_manager = mgr_sem07
        runner_sem07 = _make_runner(settings, engine, sessionmaker, redis_client, mgr_sem07)

        _, rid_sem07 = await _create_guest_field_and_submit(client, ip="198.51.100.79")
        out_sem07 = await runner_sem07.run_once()
        assert out_sem07 is not None
        assert out_sem07.request_id == rid_sem07
        assert out_sem07.outcome == "failed"
        assert out_sem07.error_code == ErrorCode.DATASET_VERSION_UNAVAILABLE.value

        async with sessionmaker() as db:
            ar_sem07 = (
                await db.execute(
                    select(AnalysisResult).where(AnalysisResult.request_id == rid_sem07)
                )
            ).scalar_one()
            assert ar_sem07.validation_passed is False
            assert ar_sem07.validation_errors is not None
            assert any(e["rule"] == "SEM-07" for e in ar_sem07.validation_errors)

        # UniqueViolation savepoint collision retry on analysis_<12hex> minting.
        clean_adapter = MockMLAdapter(fault_mode="none")
        clean_mgr = MLProviderManager(settings=settings, mock_adapter=clean_adapter)
        app.state.ml_provider_manager = clean_mgr
        clean_runner = _make_runner(settings, engine, sessionmaker, redis_client, clean_mgr)

        existing_hex = "a1b2c3d4e5f6"
        fresh_hex = "f6e5d4c3b2a1"
        _, _rid_first = await _create_guest_field_and_submit(client, ip="198.51.100.80")
        hex_iter = iter([existing_hex, existing_hex, fresh_hex])
        monkeypatch.setattr(secrets, "token_hex", lambda n: next(hex_iter))

        res_first = await clean_runner.run_once()
        assert res_first is not None
        assert res_first.analysis_id == f"analysis_{existing_hex}"

        _, rid_collide = await _create_guest_field_and_submit(client, ip="198.51.100.81")
        res_collide = await clean_runner.run_once()
        assert res_collide is not None
        assert res_collide.request_id == rid_collide
        assert res_collide.outcome == "completed"
        assert res_collide.analysis_id == f"analysis_{fresh_hex}"
