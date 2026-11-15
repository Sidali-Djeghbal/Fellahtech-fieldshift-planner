"""Real PostgreSQL + Redis integration tests for M3 Auth endpoints (`RT-01`..`RT-09`)."""

from __future__ import annotations

import gzip
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.rate_limit import guest_quota_key, increment_guest_quarters
from app.core.security import decode_access_token, hash_token
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.models import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisSelection,
    Farm,
    Field,
    FieldCropHistory,
    GuestSession,
    RefreshToken,
    User,
)
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _auth_settings(
    *,
    guest_create_per_ip_hour: int = 5,
    rate_limit_crud_per_min: int = 60,
    redis_url: str | None = None,
) -> Settings:
    env = build_test_env()
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=env["DATABASE_URL"],
        DB_PASSWORD=env["DB_PASSWORD"],
        REDIS_URL=redis_url or _redis_url(),
        ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
        ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
        JWT_SECRET_KEY=env["JWT_SECRET_KEY"],
        JWT_ACCESS_EXPIRES_SECONDS=3600,
        JWT_REFRESH_EXPIRES_SECONDS=2592000,
        GUEST_SESSION_DAYS=7,
        GUEST_CREATE_PER_IP_HOUR=guest_create_per_ip_hour,
        RATE_LIMIT_CRUD_PER_MIN=rate_limit_crud_per_min,
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
async def auth_ctx(
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
    settings = _auth_settings()
    engine = create_db_engine(settings, role="api")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()

    # Keep seeded demo_locations / dataset_registry / ml_breaker_state intact across tests.
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


async def test_post_auth_guest_hashes_token_without_demo_parcel_and_rate_limits_ip(
    auth_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    _, engine, sessionmaker, redis_client = auth_ctx
    settings = _auth_settings(guest_create_per_ip_hour=3)
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            bad_body = await client.post("/api/v1/auth/guest", json={"demo_location_id": 0})
            assert bad_body.status_code == 400
            assert bad_body.json()["error"]["code"] == "INVALID_INPUT"

            missing_loc = await client.post("/api/v1/auth/guest", json={"demo_location_id": 999})
            assert missing_loc.status_code == 404
            assert missing_loc.json()["error"]["code"] == "NOT_FOUND"

            # missing_loc burned 1/3 IP slot; next 2 succeed (3/3), 4th returns 429.
            resp = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert resp.status_code == 201
            data = resp.json()
            raw_token = data["guest_token"]
            assert raw_token.startswith("gst_")
            assert len(raw_token) == 28
            assert data["demo_location"]["code"] == "guelma"
            assert "demo_parcel" not in data

            expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            delta_days = (expires_at - datetime.now(UTC)).total_seconds() / 86400.0
            assert 6.99 <= delta_days <= 7.01

            async with sessionmaker() as db:
                row = await db.get(GuestSession, hash_token(raw_token))
                assert row is not None
                assert await db.get(GuestSession, raw_token) is None
                farm_count = await db.scalar(select(func.count(Farm.id)))
                assert farm_count == 0

            resp_3 = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert resp_3.status_code == 201

            resp_429 = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert resp_429.status_code == 429
            assert resp_429.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert int(resp_429.headers["Retry-After"]) >= 1


async def test_register_login_refresh_logout_and_replay_revokes_family(
    auth_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = auth_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Validation override 422 -> 400
            weak_pw = await client.post(
                "/api/v1/auth/register",
                json={"email": "amina@example.dz", "password": "short", "full_name": "Amina"},
            )
            assert weak_pw.status_code == 400
            assert weak_pw.json()["error"]["code"] == "INVALID_INPUT"

            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "Amina@Example.DZ",
                    "password": "StrongPassword123!",
                    "full_name": "Amina Benali",
                    "preferred_lang": "fr",
                },
            )
            assert reg.status_code == 201
            reg_body = reg.json()
            assert isinstance(reg_body["user"]["id"], int)
            assert reg_body["user"]["email"] == "amina@example.dz"
            assert reg_body["token_type"] == "bearer"
            assert reg_body["expires_in"] == 3600
            claims_reg = decode_access_token(reg_body["access_token"], settings)

            # Case-insensitive duplicate email -> 409 CONFLICT
            dup = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "amina@example.dz",
                    "password": "AnotherPassword123!",
                    "full_name": "Duplicate",
                },
            )
            assert dup.status_code == 409
            assert dup.json()["error"]["code"] == "CONFLICT"

            # Unauthenticated /auth/me -> 401
            no_auth = await client.get("/api/v1/auth/me")
            assert no_auth.status_code == 401
            assert no_auth.json()["error"]["code"] == "UNAUTHORIZED"

            # Valid GET /auth/me
            me = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {reg_body['access_token']}"},
            )
            assert me.status_code == 200
            assert me.json()["id"] == reg_body["user"]["id"]
            assert "password_hash" not in me.json()

            # Second login creates independent refresh family (multi-device)
            bad_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "amina@example.dz", "password": "WrongPassword!"},
            )
            assert bad_login.status_code == 401

            login2 = await client.post(
                "/api/v1/auth/login",
                json={"email": "amina@example.dz", "password": "StrongPassword123!"},
            )
            assert login2.status_code == 200
            dev2_tokens = login2.json()
            claims_dev2 = decode_access_token(dev2_tokens["access_token"], settings)
            assert claims_dev2.family_id != claims_reg.family_id

            # Rotate device 1 token once: rt1 -> rt2
            rt1 = reg_body["refresh_token"]
            rot = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
            assert rot.status_code == 200
            rt2 = rot.json()["refresh_token"]
            assert rt2 != rt1

            # Replay rt1: must return 401 AND revoke entire device 1 family (including rt2!)
            replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
            assert replay.status_code == 401
            assert replay.json()["error"]["code"] == "UNAUTHORIZED"

            # Using rotated rt2 now fails 401 because replay committed family revocation
            rt2_after_replay = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": rt2},
            )
            assert rt2_after_replay.status_code == 401

            # Device 2 family remains completely unaffected until explicit logout
            dev2_rot = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": dev2_tokens["refresh_token"]},
            )
            assert dev2_rot.status_code == 200
            dev2_rt2 = dev2_rot.json()["refresh_token"]

            # Empty-body POST /auth/logout revokes caller JWT's fid claim (`IMPL-014`)
            logout_empty = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {dev2_rot.json()['access_token']}"},
            )
            assert logout_empty.status_code == 204

            # Device 2 refresh token now fails 401
            dev2_after_logout = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": dev2_rt2},
            )
            assert dev2_after_logout.status_code == 401

            # Third login + explicit body logout
            login3 = await client.post(
                "/api/v1/auth/login",
                json={"email": "amina@example.dz", "password": "StrongPassword123!"},
            )
            assert login3.status_code == 200
            dev3_rt = login3.json()["refresh_token"]
            logout_body = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {login3.json()['access_token']}"},
                json={"refresh_token": dev3_rt},
            )
            assert logout_body.status_code == 204
            dev3_after = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": dev3_rt},
            )
            assert dev3_after.status_code == 401


async def test_export_me_data_and_delete_me_cascade_purge(
    auth_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = auth_ctx
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
                    "email": "karim@example.dz",
                    "password": "KarimPassword123!",
                    "full_name": "Karim Haddad",
                    "preferred_lang": "en",
                },
            )
            assert reg.status_code == 201
            uid = reg.json()["user"]["id"]
            access_token = reg.json()["access_token"]

            # Populate farm, Guelma demo parcel + outside Setif field, history, gzip snapshot,
            # analysis result, and selection directly via ORM to verify full export & cascade.
            req_id = f"req_{uuid.uuid4().hex[:12]}"
            analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"
            async with sessionmaker() as db:
                farm = Farm(
                    user_id=uid,
                    farm_name="Export Farm",
                    country="Algeria",
                    region="Guelma",
                    commune="Bouchegouf",
                )
                db.add(farm)
                await db.flush()

                field_guelma = Field(
                    farm_id=farm.id,
                    external_field_id="F1",
                    field_name="Guelma Parcel",
                    is_unverified_demo_parcel=True,
                    geom_point=WKTElement("POINT(7.52 36.52)", srid=4326),
                    geom_polygon=None,
                    area_hectares=12.5,
                    elevation_m=310.0,
                    soil_type="loamy",
                    soil_source="farmer",
                    soil_ph=6.8,
                    organic_matter_percent=2.1,
                    soil_test_date=date(2026, 5, 10),
                    water_availability="moderate",
                    water_source="well",
                    water_source_other=None,
                    irrigation_system="drip",
                )
                field_setif = Field(
                    farm_id=farm.id,
                    external_field_id="F2",
                    field_name="Setif Parcel",
                    is_unverified_demo_parcel=False,
                    geom_point=WKTElement("POINT(5.41 36.19)", srid=4326),
                    geom_polygon=WKTElement(
                        "POLYGON((5.40 36.18, 5.42 36.18, 5.42 36.20, 5.40 36.20, 5.40 36.18))",
                        srid=4326,
                    ),
                    area_hectares=8.0,
                    soil_type="unknown",
                    soil_source="unknown",
                    water_availability="rainfed_only",
                    water_source="rainwater",
                    irrigation_system="rainfed",
                )
                db.add_all([field_guelma, field_setif])
                await db.flush()

                db.add(
                    FieldCropHistory(
                        field_id=field_guelma.id,
                        season="autumn",
                        year=2025,
                        planting_month=11,
                        crop_id="wheat_durum",
                        yield_tons_per_hectare=3.4,
                    )
                )
                db.add(
                    AnalysisRequest(
                        request_id=req_id,
                        farm_id=farm.id,
                        schema_version="5.0",
                        catalog_version="2026.11",
                        dataset_version="2026.11-guelma-v1",
                        language="en",
                        quota_units=4,
                        input_hash="a" * 64,
                        full_input_hash="b" * 64,
                        input_snapshot_gz=gzip.compress(b'{"binary_secret":"must_not_export"}'),
                        warnings=[],
                        status="ok",
                    )
                )
                await db.flush()

                db.add(
                    AnalysisResult(
                        analysis_id=analysis_id,
                        request_id=req_id,
                        status="ok",
                        dataset_version_used="2026.11-guelma-v1",
                        ml_engine_version="mock-1.0",
                        result_json={"overall_summary": {"note": "ok"}},
                        validation_passed=True,
                    )
                )
                await db.flush()

                db.add(
                    AnalysisSelection(
                        analysis_id=analysis_id,
                        field_id="F1",
                        strategy_id="strat_1",
                        selection_status="selected",
                    )
                )
                await db.commit()

            export_resp = await client.get(
                "/api/v1/auth/me/export",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert export_resp.status_code == 200
            raw_text = export_resp.text
            assert "input_snapshot_gz" not in raw_text
            assert "password_hash" not in raw_text
            assert "token_hash" not in raw_text
            assert "must_not_export" not in raw_text

            exp = export_resp.json()
            assert exp["user"]["id"] == uid
            assert len(exp["farms"]) == 1
            assert exp["farms"][0]["farm_id"].startswith("farm_")
            assert exp["farms"][0]["field_count"] == 2
            assert len(exp["fields"]) == 2
            f1, f2 = exp["fields"]
            assert f1["field_id"] == "F1"
            assert f1["warnings"][0]["code"] == "DEMO_PARCEL_UNVERIFIED"
            assert f1["crop_history"][0]["crop_id"] == "wheat_durum"
            assert "catalog_version" not in f1["crop_history"][0]
            assert f2["field_id"] == "F2"
            assert f2["location"]["boundary"]["type"] == "Polygon"
            assert f2["warnings"][0]["code"] == "MVP_OUTSIDE_COVERAGE"
            assert len(exp["analysis_requests"]) == 1
            assert exp["analysis_requests"][0]["farm_id"].startswith("farm_")
            assert "input_snapshot_gz" not in exp["analysis_requests"][0]
            assert len(exp["analysis_results"]) == 1
            assert exp["analysis_selections"][0]["selection_status"] == "selected"

            # Hard delete must purge all 8 owned tables in a single transaction
            deleted = await client.delete(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert deleted.status_code == 204

            # Old access JWT must now be rejected with 401
            me_after = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert me_after.status_code == 401

            async with sessionmaker() as db:
                for model in (
                    User,
                    RefreshToken,
                    Farm,
                    Field,
                    FieldCropHistory,
                    AnalysisRequest,
                    AnalysisResult,
                    AnalysisSelection,
                ):
                    cnt = await db.scalar(select(func.count()).select_from(model))
                    assert cnt == 0, f"Expected 0 remaining rows in {model.__tablename__}"


async def test_claim_guest_transfers_farms_preserves_data_and_deletes_redis_quota(
    auth_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = auth_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            guest_resp = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert guest_resp.status_code == 201
            raw_guest_token = guest_resp.json()["guest_token"]
            guest_hash = hash_token(raw_guest_token)

            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "claim@example.dz",
                    "password": "ClaimPassword123!",
                    "full_name": "Claimant",
                },
            )
            assert reg.status_code == 201
            uid = reg.json()["user"]["id"]
            access_token = reg.json()["access_token"]

            async with sessionmaker() as db:
                farm = Farm(
                    guest_session_token=guest_hash,
                    farm_name="Guest Farm To Claim",
                    country="Algeria",
                    region="Guelma",
                )
                db.add(farm)
                await db.flush()
                farm_id = farm.id
                await db.commit()

            await increment_guest_quarters(
                redis_client,
                guest_token_hash=guest_hash,
                delta=8,
                fallback_total=0,
                ttl_seconds=3600,
            )
            assert await redis_client.exists(guest_quota_key(guest_hash)) == 1

            # Must require BOTH Bearer and X-Guest-Token
            missing_guest = await client.post(
                "/api/v1/auth/claim-guest",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert missing_guest.status_code == 401
            missing_bearer = await client.post(
                "/api/v1/auth/claim-guest",
                headers={"X-Guest-Token": raw_guest_token},
            )
            assert missing_bearer.status_code == 401

            claim = await client.post(
                "/api/v1/auth/claim-guest",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Guest-Token": raw_guest_token,
                },
            )
            assert claim.status_code == 200
            assert claim.json() == {"claimed_farms_count": 1}

            # Verify farm survived ON DELETE CASCADE, user owns it, guest row + Redis key deleted
            async with sessionmaker() as db:
                claimed_farm = await db.get(Farm, farm_id)
                assert claimed_farm is not None
                assert claimed_farm.user_id == uid
                assert claimed_farm.guest_session_token is None
                assert await db.get(GuestSession, guest_hash) is None

            assert await redis_client.exists(guest_quota_key(guest_hash)) == 0

            # Re-claiming with deleted guest token fails 401
            reclaim = await client.post(
                "/api/v1/auth/claim-guest",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Guest-Token": raw_guest_token,
                },
            )
            assert reclaim.status_code == 401


async def test_crud_rate_limit_429_and_redis_outage_503_on_auth_me(
    auth_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    _, engine, sessionmaker, redis_client = auth_ctx
    settings = _auth_settings(rate_limit_crud_per_min=2)
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
                    "email": "ratelimit@example.dz",
                    "password": "RatePassword123!",
                    "full_name": "Rate Tester",
                },
            )
            assert reg.status_code == 201
            access_token = reg.json()["access_token"]

            assert (
                await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            ).status_code == 200
            assert (
                await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            ).status_code == 200
            limited = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert limited.status_code == 429
            assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert int(limited.headers["Retry-After"]) >= 1

            # Redis outage fails closed 503 with Retry-After: 5
            down_redis = redis_async.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1)
            app.state.redis = down_redis
            try:
                outage = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert outage.status_code == 503
                assert outage.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
                assert outage.headers["Retry-After"] == "5"
            finally:
                app.state.redis = redis_client
                await down_redis.aclose()


async def test_expired_guest_token_rejected_401(
    auth_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = auth_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    raw_expired = "gst_deadbeefdeadbeefdeadbeef"
    async with sessionmaker() as db:
        db.add(
            GuestSession(
                guest_token=hash_token(raw_expired),
                demo_location_id=1,
                expires_at=datetime.now(UTC) - timedelta(seconds=10),
            )
        )
        await db.commit()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "exp@example.dz",
                    "password": "ExpiredPassword123!",
                    "full_name": "Exp User",
                },
            )
            claim = await client.post(
                "/api/v1/auth/claim-guest",
                headers={
                    "Authorization": f"Bearer {reg.json()['access_token']}",
                    "X-Guest-Token": raw_expired,
                },
            )
            assert claim.status_code == 401
            assert claim.json()["error"]["code"] == "UNAUTHORIZED"
