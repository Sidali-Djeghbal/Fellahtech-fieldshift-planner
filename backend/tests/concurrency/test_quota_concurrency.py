"""Real PostGIS + Redis concurrency tests for M5 row-locked guest quotas and uniqueness."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.seed import GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.models import Farm, Field
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _concurrency_settings() -> Settings:
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
        GUEST_CREATE_PER_IP_HOUR=100,
        GUEST_BURST_PER_MIN=200,
        RATE_LIMIT_CRUD_PER_MIN=200,
    )


async def _cleanup(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as db:
        await db.execute(
            text(
                "TRUNCATE TABLE public.analysis_selections, public.analysis_results, "
                "public.analysis_requests, public.field_crop_history, public.fields, "
                "public.farms, public.guest_sessions, public.refresh_tokens, public.users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await db.execute(
            text("DELETE FROM public.demo_locations WHERE id <> :gid"),
            {"gid": GUELMA_LOCATION_ID},
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
    tuple[
        Settings,
        AsyncEngine,
        async_sessionmaker[AsyncSession],
        redis_async.Redis,
    ]
]:
    del migrated_database
    settings = _concurrency_settings()
    engine = create_db_engine(settings, role="api")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
    await _cleanup(sessionmaker)

    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await _cleanup(sessionmaker)
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


def _field_payload(field_id: str) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "field_name": f"Parcel {field_id}",
        "is_unverified_demo_parcel": False,
        "location": {"latitude": 36.47, "longitude": 7.43, "boundary": None},
        "area_hectares": 4.5,
        "elevation_m": 250.0,
        "soil": {"soil_type": "loamy"},
        "water": {
            "availability": "moderate",
            "source": "well",
            "source_other": None,
            "irrigation_system": "drip",
        },
        "crop_history": [
            {"season": "autumn", "year": 2025, "crop_id": "durum_wheat"},
        ],
    }


async def test_concurrent_guest_farm_creation_enforces_guest_max_farms(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, _redis_client = conc_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        g_resp = await client.post(
            "/api/v1/auth/guest",
            headers={"X-Forwarded-For": "10.9.1.1"},
            json={"demo_location_id": GUELMA_LOCATION_ID},
        )
        assert g_resp.status_code == 201
        guest_token = str(g_resp.json()["guest_token"])

        async def _create_one(idx: int) -> httpx.Response:
            return await client.post(
                "/api/v1/farms",
                headers={"X-Guest-Token": guest_token},
                json={
                    "farm_name": f"Race Farm {idx}",
                    "country": "Algeria",
                    "region": "Guelma",
                },
            )

        responses = await asyncio.gather(*(_create_one(i) for i in range(8)))
        created = [r for r in responses if r.status_code == 201]
        blocked = [r for r in responses if r.status_code == 403]

        assert len(created) == settings.GUEST_MAX_FARMS
        assert len(blocked) == 8 - settings.GUEST_MAX_FARMS
        assert all(r.json()["error"]["code"] == "GUEST_LIMIT_REACHED" for r in blocked)

        async with sessionmaker() as db:
            db_count = int((await db.execute(select(func.count(Farm.id)))).scalar_one())
        assert db_count == settings.GUEST_MAX_FARMS


async def test_concurrent_guest_field_creation_enforces_guest_max_fields_per_farm(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, _redis_client = conc_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        g_resp = await client.post(
            "/api/v1/auth/guest",
            headers={"X-Forwarded-For": "10.9.2.1"},
            json={"demo_location_id": GUELMA_LOCATION_ID},
        )
        assert g_resp.status_code == 201
        guest_token = str(g_resp.json()["guest_token"])

        farm_resp = await client.post(
            "/api/v1/farms",
            headers={"X-Guest-Token": guest_token},
            json={"farm_name": "Race Host Farm", "country": "Algeria", "region": "Guelma"},
        )
        assert farm_resp.status_code == 201
        farm_id = str(farm_resp.json()["farm_id"])

        async def _create_field(idx: int) -> httpx.Response:
            return await client.post(
                f"/api/v1/farms/{farm_id}/fields",
                headers={"X-Guest-Token": guest_token},
                json=_field_payload(f"RACE_{idx}"),
            )

        responses = await asyncio.gather(*(_create_field(i) for i in range(10)))
        created = [r for r in responses if r.status_code == 201]
        blocked = [r for r in responses if r.status_code == 403]

        assert len(created) == settings.GUEST_MAX_FIELDS_PER_FARM
        assert len(blocked) == 10 - settings.GUEST_MAX_FIELDS_PER_FARM
        assert all(r.json()["error"]["code"] == "GUEST_LIMIT_REACHED" for r in blocked)

        async with sessionmaker() as db:
            db_count = int((await db.execute(select(func.count(Field.id)))).scalar_one())
        assert db_count == settings.GUEST_MAX_FIELDS_PER_FARM


async def test_concurrent_duplicate_field_id_creation_yields_single_201_and_409s(
    conc_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, _redis_client = conc_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "field_dup_race@example.com",
                "password": "StrongPassword123!",
                "full_name": "Race Owner",
                "preferred_lang": "en",
            },
        )
        assert reg.status_code == 201
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        farm = await client.post(
            "/api/v1/farms",
            headers=headers,
            json={"farm_name": "Unique Race Farm", "country": "Algeria", "region": "Guelma"},
        )
        assert farm.status_code == 201
        farm_id = str(farm.json()["farm_id"])

        async def _submit_same() -> httpx.Response:
            return await client.post(
                f"/api/v1/farms/{farm_id}/fields",
                headers=headers,
                json=_field_payload("F_SAME"),
            )

        responses = await asyncio.gather(*(_submit_same() for _ in range(6)))
        created = [r for r in responses if r.status_code == 201]
        conflicts = [r for r in responses if r.status_code == 409]

        assert len(created) == 1
        assert len(conflicts) == 5
        assert all(r.json()["error"]["code"] == "CONFLICT" for r in conflicts)

        async with sessionmaker() as db:
            db_count = int((await db.execute(select(func.count(Field.id)))).scalar_one())
        assert db_count == 1
