"""Real PostgreSQL concurrency race tests for Auth rotation, register, and claim-guest."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import hash_token
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.models import Farm, GuestSession, RefreshToken
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
    )


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

    async with sessionmaker() as db:
        await db.execute(
            text(
                "TRUNCATE TABLE public.analysis_selections, public.analysis_results, "
                "public.analysis_requests, public.field_crop_history, public.fields, "
                "public.farms, public.guest_sessions, public.refresh_tokens, public.users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await db.commit()

    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        async with sessionmaker() as db:
            await db.execute(
                text(
                    "TRUNCATE TABLE public.analysis_selections, public.analysis_results, "
                    "public.analysis_requests, public.field_crop_history, public.fields, "
                    "public.farms, public.guest_sessions, public.refresh_tokens, public.users "
                    "RESTART IDENTITY CASCADE"
                )
            )
            await db.commit()
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


async def test_concurrent_refresh_race_allows_exactly_one_and_revokes_family(
    conc_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "race_refresh@example.dz",
                    "password": "RacePassword123!",
                    "full_name": "Race Tester",
                },
            )
            assert reg.status_code == 201
            shared_refresh = reg.json()["refresh_token"]

            responses = await asyncio.gather(
                *[
                    client.post("/api/v1/auth/refresh", json={"refresh_token": shared_refresh})
                    for _ in range(8)
                ]
            )
            statuses = [resp.status_code for resp in responses]
            assert statuses.count(200) == 1
            assert statuses.count(401) == 7

            winning_resp = next(resp for resp in responses if resp.status_code == 200)
            rotated_token = winning_resp.json()["refresh_token"]

            # Losing concurrent contenders saw used_at != NULL and revoked the entire family,
            # including the winner's freshly minted rotated_token.
            follow_up = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": rotated_token},
            )
            assert follow_up.status_code == 401

            async with sessionmaker() as db:
                unrevoked = await db.scalar(
                    select(func.count(RefreshToken.id)).where(RefreshToken.revoked_at.is_(None))
                )
                assert unrevoked == 0


async def test_concurrent_duplicate_register_serializes_into_single_201_and_409s(
    conc_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            emails = [
                "dup_race@example.dz",
                "DUP_RACE@example.dz",
                "Dup_Race@Example.DZ",
                "dup_race@EXAMPLE.dz",
                "dup_race@example.dz",
            ]
            responses = await asyncio.gather(
                *[
                    client.post(
                        "/api/v1/auth/register",
                        json={
                            "email": email,
                            "password": "DupPassword123!",
                            "full_name": "Dup Race",
                        },
                    )
                    for email in emails
                ]
            )
            statuses = [resp.status_code for resp in responses]
            assert statuses.count(201) == 1
            assert statuses.count(409) == 4


async def test_concurrent_claim_guest_transfers_once_without_losing_farms(
    conc_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = conc_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            guest = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert guest.status_code == 201
            raw_guest = guest.json()["guest_token"]
            guest_hash = hash_token(raw_guest)

            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "claim_race@example.dz",
                    "password": "ClaimRacePassword123!",
                    "full_name": "Claim Race",
                },
            )
            assert reg.status_code == 201
            uid = reg.json()["user"]["id"]
            access_token = reg.json()["access_token"]

            async with sessionmaker() as db:
                db.add_all(
                    [
                        Farm(
                            guest_session_token=guest_hash,
                            farm_name="Concurrent Farm 1",
                            country="Algeria",
                            region="Guelma",
                        ),
                        Farm(
                            guest_session_token=guest_hash,
                            farm_name="Concurrent Farm 2",
                            country="Algeria",
                            region="Guelma",
                        ),
                    ]
                )
                await db.commit()

            responses = await asyncio.gather(
                *[
                    client.post(
                        "/api/v1/auth/claim-guest",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "X-Guest-Token": raw_guest,
                        },
                    )
                    for _ in range(5)
                ]
            )
            statuses = [resp.status_code for resp in responses]
            assert statuses.count(200) == 1
            assert statuses.count(401) == 4
            winner = next(resp for resp in responses if resp.status_code == 200)
            assert winner.json() == {"claimed_farms_count": 2}

            async with sessionmaker() as db:
                user_farms = await db.scalar(
                    select(func.count(Farm.id)).where(Farm.user_id == uid)
                )
                assert user_farms == 2
                assert await db.get(GuestSession, guest_hash) is None
