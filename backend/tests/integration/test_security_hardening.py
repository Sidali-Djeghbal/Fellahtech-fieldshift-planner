"""Security hardening, 6 Redis 429 buckets, proxy spoofing, IDOR 404, JWT & DB isolation (`M12`)."""

from __future__ import annotations

import base64
import copy
import gzip
import json
import os
import socket
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx
import jwt
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.core.rate_limit import (
    POLL_RATE_LIMIT_PER_MIN,
    RateLimitBucket,
    RateLimitCheck,
    check_rate_limits,
)
from app.core.security import create_access_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, validate_contract_def
from app.services.catalog import sync_catalog_once
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env, to_asyncpg_dsn

BACKEND_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _free_unbound_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _sec_settings(**overrides: Any) -> Settings:
    env = build_test_env()
    params: dict[str, Any] = {
        "_env_file": None,
        "APP_ENV": "test",
        "ML_PROVIDER_MODE": "mock",
        "ML_SERVICE_URL": f"http://127.0.0.1:{_free_unbound_port()}",
        "ML_SERVICE_API_KEY": env["ML_SERVICE_API_KEY"],
        "DATABASE_URL": env["DATABASE_URL"],
        "DB_PASSWORD": env["DB_PASSWORD"],
        "REDIS_URL": _redis_url(),
        "ML_DATASET_DB_URL": env["ML_DATASET_DB_URL"],
        "ML_READER_PASSWORD": env["ML_READER_PASSWORD"],
        "JWT_SECRET_KEY": env["JWT_SECRET_KEY"],
        "TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128",
        "GUEST_CREATE_PER_IP_HOUR": 200,
        "GUEST_BURST_PER_MIN": 200,
        "RATE_LIMIT_CRUD_PER_MIN": 200,
        "RATE_LIMIT_ANALYSIS_PER_HOUR": 200,
        "ANALYSIS_PER_IP_HOUR": 200,
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
                "UPDATE public.ml_breaker_state SET state = 'closed', "
                "consecutive_failures = 0, opened_at = NULL, half_open_probe_at = NULL, "
                "updated_at = NOW() WHERE id = 1"
            )
        )
        await db.commit()


def _field_payload_from_fixture(fixture_field: dict[str, Any]) -> dict[str, Any]:
    history = [
        {
            "season": item["season"],
            "year": item["year"],
            "planting_month": item.get("planting_month"),
            "crop_id": item["crop_id"],
            "crop_name_raw": item.get("crop_name_raw"),
            "yield_tons_per_hectare": item.get("yield_tons_per_hectare"),
        }
        for item in fixture_field["crop_history"]
    ]
    soil_payload = {k: v for k, v in fixture_field["soil"].items() if k != "source"}
    return {
        "field_id": fixture_field["field_id"],
        "field_name": fixture_field["field_name"],
        "is_unverified_demo_parcel": fixture_field.get("is_unverified_demo_parcel", False),
        "location": fixture_field["location"],
        "area_hectares": fixture_field["area_hectares"],
        "elevation_m": fixture_field.get("elevation_m"),
        "soil": soil_payload,
        "water": fixture_field["water"],
        "crop_history": history,
    }


def _analysis_body_from_fixture(farm_id: str, fixture_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "farm_id": farm_id,
        "field_ids": [f["field_id"] for f in fixture_input["fields"]],
        "language": fixture_input["language"],
        "planning": fixture_input["planning"],
        "priorities": fixture_input["priorities"],
    }


def _b64u_json(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


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
async def sec_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _sec_settings()
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


@pytest.mark.asyncio
async def test_all_6_rate_limit_buckets_window_recovery_and_redis_fail_closed(
    sec_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, redis_client = sec_ctx
    f91: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    # Tight bucket limits covering guest_create_ip, guest_crud, user_crud,
    # analysis_user, and analysis_ip
    tight_settings = _sec_settings(
        GUEST_CREATE_PER_IP_HOUR=2,
        GUEST_BURST_PER_MIN=2,
        RATE_LIMIT_CRUD_PER_MIN=3,
        RATE_LIMIT_ANALYSIS_PER_HOUR=2,
        ANALYSIS_PER_IP_HOUR=2,
    )
    app = create_app(settings=tight_settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # Bucket 1: guest_create_ip (`GUEST_CREATE_PER_IP_HOUR=2`)
            ip1 = "198.51.100.10"
            g1 = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip1},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            g2 = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip1},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            g3 = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip1},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            assert g1.status_code == 201 and g2.status_code == 201
            assert g3.status_code == 429
            assert g3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert "Retry-After" in g3.headers

            # Bucket 2: guest_crud (`GUEST_BURST_PER_MIN=2`)
            gh = {"X-Guest-Token": g1.json()["guest_token"], "X-Forwarded-For": ip1}
            assert (await client.get("/api/v1/farms", headers=gh)).status_code == 200
            assert (await client.get("/api/v1/farms", headers=gh)).status_code == 200
            gc_429 = await client.get("/api/v1/farms", headers=gh)
            assert gc_429.status_code == 429
            assert gc_429.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

            # Bucket 3: user_crud (`RATE_LIMIT_CRUD_PER_MIN=3`)
            ip_u1 = "198.51.100.21"
            reg1 = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip_u1},
                json={
                    "email": "rl.user1@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "RL User One",
                    "preferred_lang": "en",
                },
            )
            u1_headers = {"Authorization": f"Bearer {reg1.json()['access_token']}"}
            farm1 = (
                await client.post(
                    "/api/v1/farms",
                    headers={**u1_headers, "X-Forwarded-For": ip_u1},
                    json={"farm_name": "RL Farm 1", "country": "Algeria", "region": "Guelma"},
                )
            ).json()["farm_id"]
            field1 = await client.post(
                f"/api/v1/farms/{farm1}/fields",
                headers={**u1_headers, "X-Forwarded-For": ip_u1},
                json=_field_payload_from_fixture(f91["fields"][0]),
            )
            assert field1.status_code == 201
            assert (
                await client.get("/api/v1/farms", headers={**u1_headers, "X-Forwarded-For": ip_u1})
            ).status_code == 200
            uc_429 = await client.get(
                "/api/v1/farms", headers={**u1_headers, "X-Forwarded-For": ip_u1}
            )
            assert uc_429.status_code == 429
            assert uc_429.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

            # Bucket 4: analysis_user (`RATE_LIMIT_ANALYSIS_PER_HOUR=2` -> 8 quarters)
            base_a1 = _analysis_body_from_fixture(farm1, f91)
            sub_ok1 = await client.post(
                "/api/v1/analysis",
                headers={**u1_headers, "X-Forwarded-For": "198.51.100.31"},
                json=base_a1,
            )
            a1_yr2 = copy.deepcopy(base_a1)
            a1_yr2["planning"]["start_year"] = 2028
            sub_ok2 = await client.post(
                "/api/v1/analysis",
                headers={**u1_headers, "X-Forwarded-For": "198.51.100.32"},
                json=a1_yr2,
            )
            a1_yr3 = copy.deepcopy(base_a1)
            a1_yr3["planning"]["start_year"] = 2029
            sub_u_429 = await client.post(
                "/api/v1/analysis",
                headers={**u1_headers, "X-Forwarded-For": "198.51.100.33"},
                json=a1_yr3,
            )
            assert sub_ok1.status_code == 202 and sub_ok2.status_code == 202
            assert sub_u_429.status_code == 429
            assert sub_u_429.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

            # Bucket 5: poll (`POLL_RATE_LIMIT_PER_MIN == 120` dedicated bucket)
            assert POLL_RATE_LIMIT_PER_MIN == 120
            poll_req_id = sub_ok1.json()["request_id"]
            for _ in range(120):
                p_ok = await client.get(
                    f"/api/v1/analysis/requests/{poll_req_id}",
                    headers={**u1_headers, "X-Forwarded-For": ip_u1},
                )
                assert p_ok.status_code == 200
            p_429 = await client.get(
                f"/api/v1/analysis/requests/{poll_req_id}",
                headers={**u1_headers, "X-Forwarded-For": ip_u1},
            )
            assert p_429.status_code == 429
            assert p_429.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

            # Bucket 6: analysis_ip (`ANALYSIS_PER_IP_HOUR=2` across distinct users sharing IP)
            await redis_client.flushdb()
            shared_ip = "198.51.100.55"
            reg2 = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": shared_ip},
                json={
                    "email": "rl.user2@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "RL User Two",
                    "preferred_lang": "en",
                },
            )
            reg3 = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": shared_ip},
                json={
                    "email": "rl.user3@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "RL User Three",
                    "preferred_lang": "en",
                },
            )
            h2 = {
                "Authorization": f"Bearer {reg2.json()['access_token']}",
                "X-Forwarded-For": shared_ip,
            }
            h3 = {
                "Authorization": f"Bearer {reg3.json()['access_token']}",
                "X-Forwarded-For": shared_ip,
            }
            f2 = (
                await client.post(
                    "/api/v1/farms",
                    headers=h2,
                    json={"farm_name": "IP Farm 2", "country": "Algeria", "region": "Guelma"},
                )
            ).json()["farm_id"]
            f3 = (
                await client.post(
                    "/api/v1/farms",
                    headers=h3,
                    json={"farm_name": "IP Farm 3", "country": "Algeria", "region": "Guelma"},
                )
            ).json()["farm_id"]
            assert (
                await client.post(
                    f"/api/v1/farms/{f2}/fields",
                    headers=h2,
                    json=_field_payload_from_fixture(f91["fields"][0]),
                )
            ).status_code == 201
            assert (
                await client.post(
                    f"/api/v1/farms/{f3}/fields",
                    headers=h3,
                    json=_field_payload_from_fixture(f91["fields"][0]),
                )
            ).status_code == 201

            s_ip1 = await client.post(
                "/api/v1/analysis", headers=h2, json=_analysis_body_from_fixture(f2, f91)
            )
            s_ip2 = await client.post(
                "/api/v1/analysis", headers=h3, json=_analysis_body_from_fixture(f3, f91)
            )
            s_ip_429 = await client.post(
                "/api/v1/analysis",
                headers={**u1_headers, "X-Forwarded-For": shared_ip},
                json=base_a1,
            )
            assert s_ip1.status_code == 202 and s_ip2.status_code == 202
            assert s_ip_429.status_code == 429
            assert s_ip_429.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    # Sliding-window advance recovery verified via `now_override` + Redis failure 503
    check = RateLimitCheck(
        bucket=RateLimitBucket.GUEST_CREATE_IP,
        key_prefix="rl:test:sliding",
        window_seconds=60,
        limit=2,
        cost=1,
    )
    t0 = 1_700_000_040  # exact 60s bucket boundary
    await check_rate_limits(redis_client, [check], fail_closed=True, now_override=t0)
    await check_rate_limits(redis_client, [check], fail_closed=True, now_override=t0)
    with pytest.raises(FieldShiftError) as blocked_halfway:
        await check_rate_limits(redis_client, [check], fail_closed=True, now_override=t0 + 75)
    assert blocked_halfway.value.code == ErrorCode.RATE_LIMIT_EXCEEDED
    await check_rate_limits(redis_client, [check], fail_closed=True, now_override=t0 + 90)

    class _DownRedis:
        async def get(self, name: str) -> Any:
            del name
            raise RedisConnectionError("simulated redis outage")

        async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> Any:
            del script, numkeys, keys_and_args
            raise RedisConnectionError("simulated redis outage")

    outage_app = create_app(settings=_sec_settings(REDIS_FAIL_CLOSED=True))
    async with outage_app.router.lifespan_context(outage_app):
        await outage_app.state.redis.aclose()
        outage_app.state.redis = _DownRedis()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=outage_app),
            base_url="http://testserver",
        ) as client:
            r_outage = await client.post(
                "/api/v1/auth/guest", json={"demo_location_id": GUELMA_LOCATION_ID}
            )
            assert r_outage.status_code == 503
            assert r_outage.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_trusted_proxy_spoofing_protection(
    sec_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _settings, _engine, _sessionmaker, _redis = sec_ctx

    # Peer 127.0.0.1 is NOT in `10.0.0.0/8` -> spoofed X-Forwarded-For is ignored cleanly!
    untrusted_app = create_app(
        settings=_sec_settings(
            TRUSTED_PROXY_CIDRS="10.0.0.0/8",
            GUEST_CREATE_PER_IP_HOUR=1,
        )
    )
    async with untrusted_app.router.lifespan_context(untrusted_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=untrusted_app),
            base_url="http://testserver",
        ) as client:
            ok1 = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": "203.0.113.10"},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            spoof_blocked = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": "203.0.113.99"},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            assert ok1.status_code == 201
            assert spoof_blocked.status_code == 429


@pytest.mark.asyncio
async def test_cross_tenant_idor_404_jwt_hardening_zero_pii_sanitization_and_ml_reader_isolation(
    sec_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = sec_ctx
    f91: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        worker = WorkerRunner(
            settings=settings,
            engine=engine,
            sessionmaker=sessionmaker,
            redis_client=redis_client,
            ml_manager=app.state.ml_provider_manager,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            ip = "203.0.113.55"
            owner_reg = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "pii.farmer@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Amina Benali",
                    "preferred_lang": "en",
                },
            )
            attacker_reg = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "attacker@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Foreign Attacker",
                    "preferred_lang": "en",
                },
            )
            owner_h = {
                "Authorization": f"Bearer {owner_reg.json()['access_token']}",
                "X-Forwarded-For": ip,
            }
            attacker_h = {
                "Authorization": f"Bearer {attacker_reg.json()['access_token']}",
                "X-Forwarded-For": ip,
            }
            guest_other = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            guest_other_h = {
                "X-Guest-Token": guest_other.json()["guest_token"],
                "X-Forwarded-For": ip,
            }

            # Sanitization (# TODO(OQ-2)) + SQLi literal parameterization check
            sqli_name = "Ferme\x00'; DROP TABLE farms;--\x07"
            f_resp = await client.post(
                "/api/v1/farms",
                headers=owner_h,
                json={"farm_name": sqli_name, "country": "Algeria", "region": "Guelma"},
            )
            assert f_resp.status_code == 201
            assert "\x00" not in f_resp.json()["farm_name"]
            assert "\x07" not in f_resp.json()["farm_name"]
            farm_id = f_resp.json()["farm_id"]

            fld_payload = _field_payload_from_fixture(f91["fields"][0])
            fld_payload["field_name"] = "Parcel\x00 <script>alert(1)</script>\x1f"
            fld_resp = await client.post(
                f"/api/v1/farms/{farm_id}/fields", headers=owner_h, json=fld_payload
            )
            assert fld_resp.status_code == 201
            assert "\x00" not in fld_resp.json()["field_name"]
            assert "\x1f" not in fld_resp.json()["field_name"]

            # Schema payload guards: >10 field_ids & >10,000 GeoJSON polygon vertices rejected
            too_many_fields = _analysis_body_from_fixture(farm_id, f91)
            too_many_fields["field_ids"] = [f"F{i}" for i in range(1, 12)]
            r_11_flds = await client.post("/api/v1/analysis", headers=owner_h, json=too_many_fields)
            assert r_11_flds.status_code == 400
            assert r_11_flds.json()["error"]["code"] == "INVALID_INPUT"

            huge_ring = [[7.52, 36.52] for _ in range(10_005)]
            huge_fld = copy.deepcopy(fld_payload)
            huge_fld["field_id"] = "F_HUGE"
            huge_fld["location"]["boundary"] = {"type": "Polygon", "coordinates": [huge_ring]}
            r_huge = await client.post(
                f"/api/v1/farms/{farm_id}/fields", headers=owner_h, json=huge_fld
            )
            assert r_huge.status_code == 400 and r_huge.json()["error"]["code"] == "INVALID_INPUT"

            # Submit analysis + complete via worker
            sub = await client.post(
                "/api/v1/analysis",
                headers=owner_h,
                json=_analysis_body_from_fixture(farm_id, f91),
            )
            assert sub.status_code == 202
            req_id = sub.json()["request_id"]
            summary = await worker.run_once()
            assert summary is not None and summary.analysis_id is not None
            analysis_id = summary.analysis_id

            # Zero-PII check on compressed snapshot stored in public.analysis_requests
            async with sessionmaker() as db:
                snap_bytes: Any = (
                    await db.execute(
                        text(
                            "SELECT input_snapshot_gz FROM public.analysis_requests "
                            "WHERE request_id = :rid"
                        ),
                        {"rid": req_id},
                    )
                ).scalar_one()
                assert isinstance(snap_bytes, (bytes, bytearray))
                snap_obj = json.loads(gzip.decompress(bytes(snap_bytes)).decode("utf-8"))
                assert validate_contract_def(snap_obj, "FarmAnalysisInput") == []
                snap_text = json.dumps(snap_obj)
                for pii in ("pii.farmer@example.com", "Amina Benali", "203.0.113.55", "password"):
                    assert pii not in snap_text

            # Cross-tenant IDOR: attacker user AND foreign guest must ALWAYS see 404 NOT_FOUND
            for actor_h in (attacker_h, guest_other_h):
                for method, path, body in (
                    ("GET", f"/api/v1/farms/{farm_id}", None),
                    (
                        "PUT",
                        f"/api/v1/farms/{farm_id}",
                        {"farm_name": "X", "country": "Algeria", "region": "Guelma"},
                    ),
                    ("PATCH", f"/api/v1/farms/{farm_id}", {"farm_name": "X"}),
                    ("DELETE", f"/api/v1/farms/{farm_id}", None),
                    ("GET", f"/api/v1/farms/{farm_id}/fields", None),
                    ("POST", f"/api/v1/farms/{farm_id}/fields", fld_payload),
                    ("GET", f"/api/v1/farms/{farm_id}/fields/F1", None),
                    ("PUT", f"/api/v1/farms/{farm_id}/fields/F1", fld_payload),
                    ("PATCH", f"/api/v1/farms/{farm_id}/fields/F1", {"field_name": "X"}),
                    ("DELETE", f"/api/v1/farms/{farm_id}/fields/F1", None),
                    ("GET", f"/api/v1/analysis/requests/{req_id}", None),
                    ("POST", f"/api/v1/analysis/requests/{req_id}/cancel", None),
                    ("GET", f"/api/v1/analysis/{analysis_id}", None),
                    (
                        "PATCH",
                        f"/api/v1/analysis/{analysis_id}/selection",
                        {
                            "field_id": "F1",
                            "strategy_id": "S1_baseline_cereal",
                            "selection_status": "selected",
                        },
                    ),
                    ("GET", f"/api/v1/farms/{farm_id}/analyses", None),
                ):
                    if body is None:
                        resp = await client.request(method, path, headers=actor_h)
                    else:
                        resp = await client.request(method, path, headers=actor_h, json=body)
                    assert resp.status_code == 404, f"{method} {path} returned {resp.status_code}"
                    assert resp.json()["error"]["code"] == "NOT_FOUND"

            # JWT attacks: alg=none, wrong secret, expired token -> 401 UNAUTHORIZED
            now_dt = datetime.now(UTC)
            alg_none_claims = {
                "sub": "1",
                "fid": str(uuid.uuid4()),
                "typ": "access",
                "iat": int(now_dt.timestamp()),
                "exp": int((now_dt + timedelta(minutes=5)).timestamp()),
            }
            alg_none_tok = (
                f"{_b64u_json({'alg': 'none', 'typ': 'JWT'})}."
                f"{_b64u_json(alg_none_claims)}."
            )
            wrong_sig_tok = jwt.encode(
                {
                    "sub": "1",
                    "fid": str(uuid.uuid4()),
                    "typ": "access",
                    "iat": int(now_dt.timestamp()),
                    "exp": int((now_dt + timedelta(minutes=5)).timestamp()),
                },
                "wrong_secret_key_0123456789_abcdef_01",
                algorithm="HS256",
            )
            expired_tok = create_access_token(
                user_id=1,
                family_id=uuid.uuid4(),
                settings=settings,
                now=now_dt - timedelta(hours=2),
            )
            for bad_tok in (alg_none_tok, str(wrong_sig_tok), expired_tok):
                bad_me = await client.get(
                    "/api/v1/auth/me", headers={"Authorization": f"Bearer {bad_tok}"}
                )
                assert bad_me.status_code == 401
                assert bad_me.json()["error"]["code"] == "UNAUTHORIZED"

    # Dual-key JWT rotation end-to-end check
    old_secret = "old_jwt_secret_key_0123456789_abcdef_01"
    new_secret = "new_jwt_secret_key_0123456789_abcdef_02"
    old_app = create_app(settings=_sec_settings(JWT_SECRET_KEY=old_secret))
    async with old_app.router.lifespan_context(old_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=old_app),
            base_url="http://testserver",
        ) as old_client:
            reg_rot = await old_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "rotation@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Rotation User",
                    "preferred_lang": "en",
                },
            )
            old_access = reg_rot.json()["access_token"]

    rot_app = create_app(
        settings=_sec_settings(JWT_SECRET_KEY=new_secret, JWT_PREVIOUS_SECRET_KEY=old_secret)
    )
    async with rot_app.router.lifespan_context(rot_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=rot_app),
            base_url="http://testserver",
        ) as rot_client:
            ok_rot = await rot_client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"}
            )
            assert ok_rot.status_code == 200

    final_app = create_app(
        settings=_sec_settings(JWT_SECRET_KEY=new_secret, JWT_PREVIOUS_SECRET_KEY="")
    )
    async with final_app.router.lifespan_context(final_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=final_app),
            base_url="http://testserver",
        ) as final_client:
            rej_rot = await final_client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"}
            )
            assert rej_rot.status_code == 401

    # ml_reader PostgreSQL role isolation check
    env = build_test_env()
    conn = await asyncpg.connect(dsn=to_asyncpg_dsn(env["ML_DATASET_DB_URL"]))
    try:
        for table in (
            "public.users",
            "public.guest_sessions",
            "public.refresh_tokens",
            "public.farms",
            "public.fields",
            "public.analysis_requests",
            "public.analysis_results",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("CREATE TABLE dataset._sec_probe(x int)")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("CREATE TABLE public._sec_probe(x int)")
    finally:
        await conn.close()
