from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
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
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.models import AnalysisRequest, AnalysisResult, AnalysisSelection
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import MLCatalogPayload
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = BACKEND_DIR / ".venv" / "Scripts" / "alembic.exe"
TEST_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"


def _conc_settings() -> Settings:
    env = build_test_env()
    redis_url = os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    return Settings(
        _env_file=None,
        APP_ENV="test",
        ML_PROVIDER_MODE="auto",
        DATABASE_URL=env["DATABASE_URL"],
        DB_PASSWORD=env["DB_PASSWORD"],
        REDIS_URL=redis_url,
        ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
        ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
        JWT_SECRET_KEY=env["JWT_SECRET_KEY"],
        ML_SERVICE_API_KEY=env["ML_SERVICE_API_KEY"],
        TRUSTED_PROXY_CIDRS="0.0.0.0/0,::/0",
        GUEST_CREATE_PER_IP_HOUR=100,
        GUEST_BURST_PER_MIN=300,
        RATE_LIMIT_CRUD_PER_MIN=300,
        RATE_LIMIT_ANALYSIS_PER_HOUR=100,
        ANALYSIS_PER_IP_HOUR=100,
        GUEST_MAX_ANALYSES=10,
    )


async def _cleanup(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
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


async def _seed_catalog(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
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
async def conc_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _conc_settings()
    engine = create_db_engine(settings, role="api")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
    await _cleanup(sessionmaker)
    await _seed_catalog(sessionmaker)
    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await _cleanup(sessionmaker)
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


def _make_bound_app(
    settings: Settings,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    redis_client: redis_async.Redis,
) -> Any:
    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    return app


async def _snapshot_analysis_rate_keys(
    redis_client: redis_async.Redis,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    async for raw_key in redis_client.scan_iter(match="rl:analysis:*"):
        key_str = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
        ttl = int(await redis_client.ttl(raw_key))
        assert ttl > 0, f"Orphan or missing-TTL rate key detected: {key_str} (ttl={ttl})"
        val = await redis_client.get(raw_key)
        if val is not None:
            parsed = int(val)
            if parsed > 0:
                counts[key_str] = parsed
    return counts


async def _setup_guest_farm_and_field(
    client: httpx.AsyncClient,
    *,
    ip: str,
) -> tuple[str, dict[str, str], str]:
    g_resp = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert g_resp.status_code == 201
    guest_token = str(g_resp.json()["guest_token"])
    headers = {"X-Guest-Token": guest_token, "X-Forwarded-For": ip}

    f_resp = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": "Concurrency Farm", "country": "Algeria", "region": "Guelma"},
    )
    assert f_resp.status_code == 201
    farm_id = str(f_resp.json()["farm_id"])

    p_resp = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcel F1",
            "is_unverified_demo_parcel": False,
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 10.0,
            "elevation_m": 240.0,
            "soil": {"soil_type": "loamy"},
            "water": {
                "availability": "moderate",
                "source": "well",
                "source_other": None,
                "irrigation_system": "drip",
            },
            "crop_history": [{"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}],
        },
    )
    assert p_resp.status_code == 201
    return guest_token, headers, farm_id


async def _setup_user_farm_and_field(
    client: httpx.AsyncClient,
    *,
    email: str,
    ip: str,
) -> tuple[int, dict[str, str], str]:
    reg = await client.post(
        "/api/v1/auth/register",
        headers={"X-Forwarded-For": ip},
        json={
            "email": email,
            "password": "StrongPassword!123",
            "full_name": "Race Tester",
            "preferred_lang": "en",
        },
    )
    assert reg.status_code == 201
    user_id = int(reg.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}", "X-Forwarded-For": ip}

    f_resp = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": "User Race Farm", "country": "Algeria", "region": "Guelma"},
    )
    assert f_resp.status_code == 201
    farm_id = str(f_resp.json()["farm_id"])

    p_resp = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": "F1",
            "field_name": "Parcel F1",
            "is_unverified_demo_parcel": False,
            "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
            "area_hectares": 10.0,
            "elevation_m": 240.0,
            "soil": {"soil_type": "loamy"},
            "water": {
                "availability": "moderate",
                "source": "well",
                "source_other": None,
                "irrigation_system": "drip",
            },
            "crop_history": [{"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}],
        },
    )
    assert p_resp.status_code == 201
    return user_id, headers, farm_id


def _analysis_payload(
    farm_id: str,
    *,
    horizon_seasons: int = 4,
    target_crop_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "farm_id": farm_id,
        "language": "en",
        "planning": {
            "start_season": "spring",
            "start_year": 2027,
            "horizon_seasons": horizon_seasons,
            "cycle_mode": "annual_rotation",
            "planting_month": 3,
            "scenario_overrides": {"temp_delta_c": 0.0, "precip_pct_delta": 0.0},
        },
        "priorities": {
            "weights": {
                "water_saving": 30,
                "soil_improvement": 25,
                "income": 25,
                "risk_reduction": 15,
                "forage_value": 5,
            },
            "market_preference": "mixed",
            "target_crop_ids": target_crop_ids if target_crop_ids is not None else ["chickpea"],
            "excluded_crop_ids": [],
            "equipment_constraints": [],
        },
        "field_ids": ["F1"],
    }


@pytest.mark.asyncio
async def test_concurrent_identical_idempotency_key_charges_once_and_returns_same_202(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_token, headers, farm_id = await _setup_guest_farm_and_field(
            client, ip="198.51.100.10"
        )
        req_headers: Mapping[str, str] = {
            **headers,
            "Idempotency-Key": "conc-same-idem-key-01",
        }
        body = _analysis_payload(farm_id)

        responses = await asyncio.gather(
            *(client.post("/api/v1/analysis", headers=req_headers, json=body) for _ in range(6))
        )
        assert [r.status_code for r in responses] == [202] * 6
        request_ids = {r.json()["request_id"] for r in responses}
        assert len(request_ids) == 1

        async with sessionmaker() as db:
            db_count = int(
                (await db.execute(select(func.count(AnalysisRequest.request_id)))).scalar_one()
            )
        assert db_count == 1

        sess_resp = await client.get(
            "/api/v1/demo/session",
            headers={"X-Guest-Token": guest_token},
        )
        assert sess_resp.status_code == 200
        assert sess_resp.json()["usage"]["analysis_quarters"] == 4
        assert await redis_client.get(f"guest_quota:{hash_token(guest_token)}:quarters") == b"4"

        rl_snapshot = await _snapshot_analysis_rate_keys(redis_client)
        assert sum(v for k, v in rl_snapshot.items() if k.startswith("rl:analysis:ip:")) == 4


@pytest.mark.asyncio
async def test_concurrent_conflicting_idempotency_key_single_202_and_five_409_no_burn(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        user_id, headers, farm_id = await _setup_user_farm_and_field(
            client, email="idem_conflict@example.com", ip="198.51.100.20"
        )
        req_headers = {**headers, "Idempotency-Key": "conc-diff-idem-key-01"}

        async def _submit_distinct(idx: int) -> httpx.Response:
            return await client.post(
                "/api/v1/analysis",
                headers=req_headers,
                json=_analysis_payload(farm_id, horizon_seasons=(idx % 6) + 1),
            )

        responses = await asyncio.gather(*(_submit_distinct(i) for i in range(6)))
        accepted = [r for r in responses if r.status_code == 202]
        conflicts = [r for r in responses if r.status_code == 409]
        assert len(accepted) == 1
        assert len(conflicts) == 5
        assert all(r.json()["error"]["code"] == "CONFLICT" for r in conflicts)

        async with sessionmaker() as db:
            db_count = int(
                (await db.execute(select(func.count(AnalysisRequest.request_id)))).scalar_one()
            )
        assert db_count == 1

        rl_snapshot = await _snapshot_analysis_rate_keys(redis_client)
        user_prefix = f"rl:analysis:u:{user_id}:"
        assert sum(v for k, v in rl_snapshot.items() if k.startswith(user_prefix)) == 4
        assert sum(v for k, v in rl_snapshot.items() if k.startswith("rl:analysis:ip:")) == 4


@pytest.mark.asyncio
async def test_concurrent_guest_quota_at_36_of_40_allows_one_and_rolls_back_seven(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_token, headers, farm_id = await _setup_guest_farm_and_field(
            client, ip="198.51.100.30"
        )
        g_hash = hash_token(guest_token)

        # Saturate guest to 36/40 quarters using 9 distinct non-what-if analyses (9 * 4 = 36).
        for idx in range(9):
            crops = ["chickpea"] if idx < 6 else ["durum_wheat"]
            r_pre = await client.post(
                "/api/v1/analysis",
                headers=headers,
                json=_analysis_payload(
                    farm_id,
                    horizon_seasons=(idx % 6) + 1,
                    target_crop_ids=crops,
                ),
            )
            assert r_pre.status_code == 202, r_pre.text

        assert await redis_client.get(f"guest_quota:{g_hash}:quarters") == b"36"
        rl_before_race = await _snapshot_analysis_rate_keys(redis_client)
        ip_total_before = sum(rl_before_race.values())
        assert ip_total_before == 36

        # Launch 8 concurrent full-cost submissions: only 1 can succeed (40/40); 7 -> 403.
        async def _race_one(idx: int) -> httpx.Response:
            crops = (
                ["durum_wheat"]
                if idx < 3
                else ["chickpea", "durum_wheat"]
            )
            horizon = (idx + 4) if idx < 3 else ((idx - 3) + 1)
            return await client.post(
                "/api/v1/analysis",
                headers=headers,
                json=_analysis_payload(
                    farm_id,
                    horizon_seasons=horizon,
                    target_crop_ids=crops,
                ),
            )

        responses = await asyncio.gather(*(_race_one(i) for i in range(8)))
        accepted = [r for r in responses if r.status_code == 202]
        blocked = [r for r in responses if r.status_code == 403]
        assert len(accepted) == 1
        assert len(blocked) == 7
        assert all(r.json()["error"]["code"] == "GUEST_LIMIT_REACHED" for r in blocked)

        async with sessionmaker() as db:
            db_count = int(
                (await db.execute(select(func.count(AnalysisRequest.request_id)))).scalar_one()
            )
        assert db_count == 10

        sess_resp = await client.get(
            "/api/v1/demo/session",
            headers={"X-Guest-Token": guest_token},
        )
        assert sess_resp.status_code == 200
        assert sess_resp.json()["usage"]["analysis_quarters"] == 40
        assert await redis_client.get(f"guest_quota:{g_hash}:quarters") == b"40"

        rl_after_race = await _snapshot_analysis_rate_keys(redis_client)
        assert sum(rl_after_race.values()) == 40


@pytest.mark.asyncio
async def test_concurrent_selection_updates_maintain_single_selected_invariant(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)
    fixture_result = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )
    strategy_ids = [
        str(s["strategy_id"]) for s in fixture_result["field_plans"][0]["strategies"]
    ]
    assert len(strategy_ids) >= 3

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        _guest_token, headers, farm_id = await _setup_guest_farm_and_field(
            client, ip="198.51.100.40"
        )
        r_sub = await client.post(
            "/api/v1/analysis",
            headers=headers,
            json=_analysis_payload(farm_id),
        )
        assert r_sub.status_code == 202
        req_id = str(r_sub.json()["request_id"])
        analysis_id = "analysis_000111222333"

        result_payload = copy.deepcopy(fixture_result)
        result_payload["request_id"] = req_id
        now = datetime.now(UTC)
        async with sessionmaker() as db:
            req_row = await db.get(AnalysisRequest, req_id)
            assert req_row is not None
            req_row.status = "ok"
            req_row.received_at = now
            req_row.duration_ms = 120
            db.add(
                AnalysisResult(
                    analysis_id=analysis_id,
                    request_id=req_id,
                    status="ok",
                    dataset_version_used=DEFAULT_DATASET_VERSION,
                    ml_engine_version="agro-ml-2.1.0",
                    result_json=result_payload,
                    validation_passed=True,
                    created_at=now,
                )
            )
            await db.commit()

        async def _patch_selection(idx: int) -> httpx.Response:
            sid = strategy_ids[idx % len(strategy_ids)]
            return await client.patch(
                f"/api/v1/analysis/{analysis_id}/selection",
                headers=headers,
                json={
                    "field_id": "F1",
                    "strategy_id": sid,
                    "selection_status": "selected",
                },
            )

        responses = await asyncio.gather(*(_patch_selection(i) for i in range(12)))
        assert [r.status_code for r in responses] == [200] * 12

        async with sessionmaker() as db:
            selected_count = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(AnalysisSelection)
                        .where(
                            AnalysisSelection.analysis_id == analysis_id,
                            AnalysisSelection.field_id == "F1",
                            AnalysisSelection.selection_status == "selected",
                        )
                    )
                ).scalar_one()
            )
        assert selected_count == 1

        r_get = await client.get(f"/api/v1/analysis/{analysis_id}", headers=headers)
        assert r_get.status_code == 200
        strategies = r_get.json()["result"]["field_plans"][0]["strategies"]
        selected_strategies = [
            s
            for s in strategies
            if all(season["selection_status"] == "selected" for season in s["seasons"])
        ]
        assert len(selected_strategies) == 1
