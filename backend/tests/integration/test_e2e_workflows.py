"""End-to-end workflows, Fixtures 9.1-9.4, Visual I/O §10 matrix & KPI-01 (`M12`)."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import os
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, validate_contract_def
from app.ml_client.base import MLAdapter, MLHealthResult, MLTransportError, ProviderKind
from app.ml_client.manager import read_provider_status
from app.ml_client.mock_adapter import MockMLAdapter
from app.schemas.catalog import MLCatalogPayload
from app.services.catalog import sync_catalog_once
from app.services.verification import verify_analysis_result
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)

_FORBIDDEN_EXPORT_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token_hash",
        "refresh_token",
        "access_token",
        "guest_session_token",
        "result_gzip",
        "payload_gzip",
    }
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def os_getenv(key: str, default: str) -> str:
    import os

    return os.getenv(key, default)


def _free_unbound_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _e2e_settings(**overrides: Any) -> Settings:
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
        "GUEST_CREATE_PER_IP_HOUR": 500,
        "GUEST_BURST_PER_MIN": 500,
        "RATE_LIMIT_CRUD_PER_MIN": 500,
        "RATE_LIMIT_ANALYSIS_PER_HOUR": 500,
        "ANALYSIS_PER_IP_HOUR": 500,
        "ALLOW_SYNC_WAIT": True,
        "SYNC_WAIT_TIMEOUT_SECONDS": 5,
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


def _assert_no_forbidden_keys(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        for raw_key, val in node.items():
            key = str(raw_key)
            assert key not in _FORBIDDEN_EXPORT_KEYS, f"Forbidden secret/blob key at {path}.{key}"
            _assert_no_forbidden_keys(val, f"{path}.{key}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            _assert_no_forbidden_keys(item, f"{path}[{idx}]")


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


def _analysis_body_from_fixture(
    farm_id: str,
    fixture_input: dict[str, Any],
) -> dict[str, Any]:
    return {
        "farm_id": farm_id,
        "field_ids": [f["field_id"] for f in fixture_input["fields"]],
        "language": fixture_input["language"],
        "planning": fixture_input["planning"],
        "priorities": fixture_input["priorities"],
    }


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
async def e2e_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _e2e_settings()
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
async def test_e2e_fixtures_9_1_to_9_4_and_populated_lifecycle_cross_milestone(
    e2e_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = e2e_ctx
    f91: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    f92: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_2_input_setif.json").read_text(encoding="utf-8")
    )
    f93: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )
    f94: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
    )

    assert validate_contract_def(f93, "AnalysisResult") == []
    assert validate_contract_def(f94, "CropCatalog") == []
    f93_outcome = await verify_analysis_result(
        f93,
        expected_dataset_version=str(f91["dataset_version"]),
        input_snapshot=f91,
        catalog_crops={str(c["crop_id"]): c for c in f94["crops"]},
    )
    assert f93_outcome.valid, f93_outcome.validation_errors

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
            ip = "198.51.100.77"
            # Fixture 9.1: Guelma guest journey + analysis + selection
            g_resp = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            assert g_resp.status_code == 201
            guest_headers = {
                "X-Guest-Token": g_resp.json()["guest_token"],
                "X-Forwarded-For": ip,
            }

            cat_resp = await client.get("/api/v1/catalog?limit=50", headers=guest_headers)
            assert cat_resp.status_code == 200
            assert len(cat_resp.json()["items"]) == len(f94["crops"])

            gf_resp = await client.post(
                "/api/v1/farms",
                headers=guest_headers,
                json={
                    "farm_name": f91["farm"]["farm_name"],
                    "country": f91["farm"]["country"],
                    "region": f91["farm"]["region"],
                    "commune": f91["farm"]["commune"],
                },
            )
            assert gf_resp.status_code == 201
            guelma_farm_id = gf_resp.json()["farm_id"]

            gfield_resp = await client.post(
                f"/api/v1/farms/{guelma_farm_id}/fields",
                headers=guest_headers,
                json=_field_payload_from_fixture(f91["fields"][0]),
            )
            assert gfield_resp.status_code == 201
            assert any(
                w["code"] == "DEMO_PARCEL_UNVERIFIED" for w in gfield_resp.json()["warnings"]
            )

            sub_guest = await client.post(
                "/api/v1/analysis",
                headers=guest_headers,
                json=_analysis_body_from_fixture(guelma_farm_id, f91),
            )
            assert sub_guest.status_code == 202
            req1_id = sub_guest.json()["request_id"]

            sum1 = await worker.run_once()
            assert sum1 is not None and sum1.outcome == "completed"
            assert sum1.analysis_id is not None

            poll1 = await client.get(
                f"/api/v1/analysis/requests/{req1_id}", headers=guest_headers
            )
            assert poll1.status_code == 200 and poll1.json()["status"] == "ok"
            assert any(
                w["code"] == "DEMO_PARCEL_UNVERIFIED" for w in poll1.json()["warnings"]
            )

            res1 = await client.get(
                f"/api/v1/analysis/{sum1.analysis_id}", headers=guest_headers
            )
            assert res1.status_code == 200
            assert validate_contract_def(res1.json()["result"], "AnalysisResult") == []

            strat_id = res1.json()["result"]["field_plans"][0]["strategies"][1]["strategy_id"]
            sel_resp = await client.patch(
                f"/api/v1/analysis/{sum1.analysis_id}/selection",
                headers=guest_headers,
                json={
                    "field_id": "F1",
                    "strategy_id": strat_id,
                    "selection_status": "selected",
                },
            )
            assert sel_resp.status_code == 200

            # Register & claim guest session (including idempotent repeat call)
            reg = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "e2e.farmer@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "E2E Farmer",
                    "preferred_lang": "fr",
                },
            )
            assert reg.status_code == 201
            user_headers = {
                "Authorization": f"Bearer {reg.json()['access_token']}",
                "X-Forwarded-For": ip,
            }

            claim1 = await client.post(
                "/api/v1/auth/claim-guest",
                headers={**user_headers, "X-Guest-Token": guest_headers["X-Guest-Token"]},
            )
            assert claim1.status_code == 200 and claim1.json()["claimed_farms_count"] == 1
            # Consumed guest token cannot be reclaimed twice -> 401
            claim2 = await client.post(
                "/api/v1/auth/claim-guest",
                headers={**user_headers, "X-Guest-Token": guest_headers["X-Guest-Token"]},
            )
            assert claim2.status_code == 401

            # Fixture 9.2: Setif highlands under registered user (MVP_OUTSIDE_COVERAGE non-blocking)
            sf_resp = await client.post(
                "/api/v1/farms",
                headers=user_headers,
                json={
                    "farm_name": f92["farm"]["farm_name"],
                    "country": f92["farm"]["country"],
                    "region": f92["farm"]["region"],
                    "commune": f92["farm"]["commune"],
                },
            )
            assert sf_resp.status_code == 201
            setif_farm_id = sf_resp.json()["farm_id"]

            sfield_resp = await client.post(
                f"/api/v1/farms/{setif_farm_id}/fields",
                headers=user_headers,
                json=_field_payload_from_fixture(f92["fields"][0]),
            )
            assert sfield_resp.status_code == 201
            assert any(
                w["code"] == "MVP_OUTSIDE_COVERAGE" for w in sfield_resp.json()["warnings"]
            )

            # Execute Setif analysis through `?wait=true` while worker polls concurrently
            stop_worker = asyncio.Event()

            async def _drain_worker_once() -> None:
                while not stop_worker.is_set():
                    processed = await worker.run_once()
                    if processed is not None:
                        return
                    await asyncio.sleep(0.05)

            worker_task = asyncio.create_task(_drain_worker_once())
            try:
                wait_resp = await client.post(
                    "/api/v1/analysis?wait=true",
                    headers=user_headers,
                    json=_analysis_body_from_fixture(setif_farm_id, f92),
                )
            finally:
                stop_worker.set()
                await worker_task
            assert wait_resp.status_code == 200
            wait_body = wait_resp.json()
            assert wait_body["status"] == "ok"
            assert validate_contract_def(wait_body["result"], "AnalysisResult") == []

            hist = await client.get(
                f"/api/v1/farms/{setif_farm_id}/analyses?limit=10", headers=user_headers
            )
            assert hist.status_code == 200 and len(hist.json()["items"]) == 1

            # Populated GDPR export check (no password_hash, token_hash, or raw blobs)
            export_resp = await client.get("/api/v1/auth/me/export", headers=user_headers)
            assert export_resp.status_code == 200
            export_data = export_resp.json()
            assert len(export_data["farms"]) == 2
            assert len(export_data["fields"]) == 2
            assert len(export_data["analysis_requests"]) == 2
            assert len(export_data["analysis_results"]) == 2
            assert len(export_data["analysis_selections"]) == 1
            _assert_no_forbidden_keys(export_data)

            # GDPR account erasure & verify cascade cleanup
            del_me = await client.delete("/api/v1/auth/me", headers=user_headers)
            assert del_me.status_code == 204
            after_del = await client.get("/api/v1/auth/me", headers=user_headers)
            assert after_del.status_code == 401

        async with sessionmaker() as db:
            remaining_scalar: Any = (
                await db.execute(
                    text(
                        "SELECT "
                        "(SELECT COUNT(*) FROM public.users) + "
                        "(SELECT COUNT(*) FROM public.farms) + "
                        "(SELECT COUNT(*) FROM public.analysis_results)"
                    )
                )
            ).scalar_one()
            remaining = int(remaining_scalar)
            assert remaining == 0


@pytest.mark.asyncio
async def test_visual_io_section_10_matrix_1_through_8(
    e2e_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = e2e_ctx
    f91: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        mock_adapter = app.state.ml_provider_manager.mock_adapter
        assert isinstance(mock_adapter, MockMLAdapter)
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
            ip = "198.51.100.88"
            reg_a = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "matrix.a@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Matrix A",
                    "preferred_lang": "en",
                },
            )
            headers_a = {
                "Authorization": f"Bearer {reg_a.json()['access_token']}",
                "X-Forwarded-For": ip,
            }
            reg_b = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "matrix.b@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Matrix B",
                    "preferred_lang": "en",
                },
            )
            headers_b = {
                "Authorization": f"Bearer {reg_b.json()['access_token']}",
                "X-Forwarded-For": ip,
            }

            farm_resp = await client.post(
                "/api/v1/farms",
                headers=headers_a,
                json={"farm_name": "Matrix Farm", "country": "Algeria", "region": "Guelma"},
            )
            farm_id = farm_resp.json()["farm_id"]
            fld_payload = _field_payload_from_fixture(f91["fields"][0])
            assert (
                await client.post(
                    f"/api/v1/farms/{farm_id}/fields", headers=headers_a, json=fld_payload
                )
            ).status_code == 201

            base_body = _analysis_body_from_fixture(farm_id, f91)

            # #1: sum(weights) != 100 -> 400 INVALID_INPUT synchronously before DB enqueue
            bad_w = copy.deepcopy(base_body)
            bad_w["priorities"]["weights"]["income"] = 10
            r1 = await client.post("/api/v1/analysis", headers=headers_a, json=bad_w)
            assert r1.status_code == 400 and r1.json()["error"]["code"] == "INVALID_INPUT"

            # #2: planting_month=8 with winter@36.52 (INPUT-02) & target/excluded overlap (INPUT-03)
            bad_season = copy.deepcopy(base_body)
            bad_season["planning"]["start_season"] = "winter"
            bad_season["planning"]["planting_month"] = 8
            r2a = await client.post("/api/v1/analysis", headers=headers_a, json=bad_season)
            assert r2a.status_code == 400 and r2a.json()["error"]["code"] == "INVALID_INPUT"

            bad_overlap = copy.deepcopy(base_body)
            bad_overlap["priorities"]["target_crop_ids"] = ["chickpea"]
            bad_overlap["priorities"]["excluded_crop_ids"] = ["chickpea"]
            r2b = await client.post("/api/v1/analysis", headers=headers_a, json=bad_overlap)
            assert r2b.status_code == 400 and r2b.json()["error"]["code"] == "INVALID_INPUT"

            async with sessionmaker() as db:
                cnt_before_scalar: Any = (
                    await db.execute(text("SELECT COUNT(*) FROM public.analysis_requests"))
                ).scalar_one()
                cnt_before = int(cnt_before_scalar)
                assert cnt_before == 0

            # #6: Foreign owner 404 NOT_FOUND & Guest outside Guelma 422 OUTSIDE_DEMO_BOUNDARY
            foreign_get = await client.get(f"/api/v1/farms/{farm_id}", headers=headers_b)
            assert foreign_get.status_code == 404
            assert foreign_get.json()["error"]["code"] == "NOT_FOUND"

            g1 = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            g_headers = {"X-Guest-Token": g1.json()["guest_token"], "X-Forwarded-For": ip}
            for idx in range(1, 4):
                ok_gf = await client.post(
                    "/api/v1/farms",
                    headers=g_headers,
                    json={"farm_name": f"GF {idx}", "country": "Algeria", "region": "Guelma"},
                )
                assert ok_gf.status_code == 201
                if idx == 1:
                    g_farm_1 = ok_gf.json()["farm_id"]

            # #3a: 4th guest farm -> 403 GUEST_LIMIT_REACHED (never 429)
            r3_farm = await client.post(
                "/api/v1/farms",
                headers=g_headers,
                json={"farm_name": "GF 4", "country": "Algeria", "region": "Guelma"},
            )
            assert r3_farm.status_code == 403
            assert r3_farm.json()["error"]["code"] == "GUEST_LIMIT_REACHED"

            # #6b: Guest Setif parcel write -> 422 OUTSIDE_DEMO_BOUNDARY
            setif_field = copy.deepcopy(fld_payload)
            setif_field["location"] = {"latitude": 36.19, "longitude": 5.41, "boundary": None}
            r6_guest = await client.post(
                f"/api/v1/farms/{g_farm_1}/fields", headers=g_headers, json=setif_field
            )
            assert r6_guest.status_code == 422
            assert r6_guest.json()["error"]["code"] == "OUTSIDE_DEMO_BOUNDARY"

            # #5 + #3b: Guest analysis cancel refunds quarters; exceeding 40 quarters -> 403
            assert (
                await client.post(
                    f"/api/v1/farms/{g_farm_1}/fields", headers=g_headers, json=fld_payload
                )
            ).status_code == 201

            g_body = _analysis_body_from_fixture(g_farm_1, f91)
            g_body["planning"]["horizon_seasons"] = 6
            sub_can = await client.post("/api/v1/analysis", headers=g_headers, json=g_body)
            assert sub_can.status_code == 202
            can_req_id = sub_can.json()["request_id"]
            can_ok = await client.post(
                f"/api/v1/analysis/requests/{can_req_id}/cancel", headers=g_headers
            )
            assert can_ok.status_code == 200 and can_ok.json()["status"] == "cancelled"
            # Repeat cancel -> 409 CONFLICT
            can_conflict = await client.post(
                f"/api/v1/analysis/requests/{can_req_id}/cancel", headers=g_headers
            )
            assert can_conflict.status_code == 409
            assert can_conflict.json()["error"]["code"] == "CONFLICT"

            # Refunded quarters mean full 40 quarters remain: 10 * 4 = 40 succeed, 11th -> 403
            for yr_offset in range(1, 11):
                q_body = copy.deepcopy(g_body)
                q_body["planning"]["start_year"] = 2027 + yr_offset
                q_ok = await client.post("/api/v1/analysis", headers=g_headers, json=q_body)
                assert q_ok.status_code == 202
            q_over = copy.deepcopy(g_body)
            q_over["planning"]["start_year"] = 2040
            r3_quarters = await client.post("/api/v1/analysis", headers=g_headers, json=q_over)
            assert r3_quarters.status_code == 403
            assert r3_quarters.json()["error"]["code"] == "GUEST_LIMIT_REACHED"

            # Clear pending guest jobs so worker only processes registered requests below
            async with sessionmaker() as db:
                await db.execute(
                    text(
                        "UPDATE public.analysis_requests SET status = 'cancelled' "
                        "WHERE status = 'pending'"
                    )
                )
                await db.commit()

            # #8a + #4: schema "6.0" fails Stage 1, persists validation_passed=false -> 502
            mock_adapter.set_fault_mode("schema_6_0")
            sub_60 = await client.post("/api/v1/analysis", headers=headers_a, json=base_body)
            assert sub_60.status_code == 202
            req_60 = sub_60.json()["request_id"]
            sum_60 = await worker.run_once()
            assert sum_60 is not None and sum_60.outcome == "failed"
            assert sum_60.error_code == "ML_INVALID_RESPONSE"
            assert sum_60.analysis_id is not None and sum_60.analysis_id.startswith("analysis_")

            poll_60 = await client.get(
                f"/api/v1/analysis/requests/{req_60}", headers=headers_a
            )
            assert poll_60.status_code == 200 and poll_60.json()["status"] == "failed"
            assert poll_60.json()["error"]["code"] == "ML_INVALID_RESPONSE"
            assert poll_60.json()["error"]["http_equivalent"] == 502

            async with sessionmaker() as db:
                row_60 = (
                    await db.execute(
                        text(
                            "SELECT validation_passed FROM public.analysis_results "
                            "WHERE analysis_id = :aid"
                        ),
                        {"aid": sum_60.analysis_id},
                    )
                ).one()
                assert row_60.validation_passed is False

            # #7a: SEM-07 wrong dataset_version_used -> DATASET_VERSION_UNAVAILABLE (http 502)
            mock_adapter.set_fault_mode("wrong_dataset_version")
            body_sem7 = copy.deepcopy(base_body)
            body_sem7["planning"]["start_year"] = 2030
            sub_sem7 = await client.post("/api/v1/analysis", headers=headers_a, json=body_sem7)
            assert sub_sem7.status_code == 202
            sum_sem7 = await worker.run_once()
            assert sum_sem7 is not None and sum_sem7.outcome == "failed"
            assert sum_sem7.error_code == "DATASET_VERSION_UNAVAILABLE"
            poll_sem7 = await client.get(
                f"/api/v1/analysis/requests/{sub_sem7.json()['request_id']}", headers=headers_a
            )
            assert poll_sem7.json()["error"]["code"] == "DATASET_VERSION_UNAVAILABLE"
            assert poll_sem7.json()["error"]["http_equivalent"] == 502

            # #8b: schema_version "5.1" + unknown extra fields passes Stage 1 & completes ok
            mock_adapter.set_fault_mode("extra_fields_5_1")
            body_51 = copy.deepcopy(base_body)
            body_51["planning"]["start_year"] = 2031
            sub_51 = await client.post("/api/v1/analysis", headers=headers_a, json=body_51)
            assert sub_51.status_code == 202
            sum_51 = await worker.run_once()
            assert sum_51 is not None and sum_51.outcome == "completed"
            assert sum_51.analysis_id is not None

            # #8c: Outage replay (`last_good_replay`) serves stale=True for identical input
            mock_adapter.set_fault_mode("none")
            body_replay = copy.deepcopy(base_body)
            body_replay["planning"]["start_year"] = 2032
            sub_live = await client.post(
                "/api/v1/analysis", headers=headers_a, json=body_replay
            )
            assert sub_live.status_code == 202
            sum_live = await worker.run_once()
            assert sum_live is not None and sum_live.outcome == "completed"

            # Backdate prior completed request >24h so what-if cache expires before outage replay
            async with sessionmaker() as db:
                await db.execute(
                    text(
                        "UPDATE public.analysis_requests "
                        "SET created_at = NOW() - INTERVAL '25 hours' "
                        "WHERE request_id = :rid"
                    ),
                    {"rid": sub_live.json()["request_id"]},
                )
                await db.commit()

            mock_adapter.set_fault_mode("offline")
            sub_outage = await client.post(
                "/api/v1/analysis", headers=headers_a, json=body_replay
            )
            assert sub_outage.status_code == 202
            sum_outage = await worker.run_once()
            assert sum_outage is not None and sum_outage.outcome == "completed"
            assert sum_outage.analysis_id is not None

            poll_replay = await client.get(
                f"/api/v1/analysis/requests/{sub_outage.json()['request_id']}",
                headers=headers_a,
            )
            assert poll_replay.status_code == 200
            assert poll_replay.json()["degraded_mode"]["kind"] == "last_good_replay"
            assert poll_replay.json()["degraded_mode"]["stale"] is True

            env_replay = await client.get(
                f"/api/v1/analysis/{sum_outage.analysis_id}", headers=headers_a
            )
            assert env_replay.status_code == 200
            assert env_replay.json()["degraded_mode"]["kind"] == "last_good_replay"
            assert env_replay.json()["degraded_mode"]["stale"] is True

            # #7b: No active dataset in dataset_registry -> 503 DATASET_UNAVAILABLE
            mock_adapter.set_fault_mode("none")
            async with sessionmaker() as db:
                await db.execute(text("UPDATE public.dataset_registry SET is_active = false"))
                await db.commit()
            body_nods = copy.deepcopy(base_body)
            body_nods["planning"]["start_year"] = 2033
            r_nods_ana = await client.post("/api/v1/analysis", headers=headers_a, json=body_nods)
            r_nods_health = await client.get("/api/v1/health")
            assert r_nods_ana.status_code == 503
            assert r_nods_ana.json()["error"]["code"] == "DATASET_UNAVAILABLE"
            assert r_nods_health.status_code == 503


class _StubRealAdapter(MLAdapter):
    def __init__(self, *, healthy: bool = True, fail_analyze: bool = False) -> None:
        self.healthy = healthy
        self.fail_analyze = fail_analyze

    @property
    def provider_name(self) -> ProviderKind:
        return "real_ml"

    async def get_health(self) -> MLHealthResult:
        if not self.healthy:
            return MLHealthResult(
                reachable=False,
                status="unreachable",
                ml_engine_version=None,
                dataset_versions_supported=(),
            )
        return MLHealthResult(
            reachable=True,
            status="ok",
            ml_engine_version="agro-ml-real-2.1",
            dataset_versions_supported=(DEFAULT_DATASET_VERSION,),
        )

    async def get_catalog(self) -> MLCatalogPayload:
        return await MockMLAdapter().get_catalog()

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        del payload, idempotency_key, compress
        if self.fail_analyze:
            raise MLTransportError("Real ML dropped mid-flight.")
        return await MockMLAdapter().analyze(
            json.loads((FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")),
            idempotency_key="stub-real",
        )


def _current_provider(mgr: MLProviderManager) -> str:
    return mgr.active_provider_name


@pytest.mark.asyncio
async def test_ml_provider_manager_production_strictness_and_auto_switchover(
    e2e_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, _sessionmaker, redis_client = e2e_ctx
    env = build_test_env()

    with pytest.raises(ValueError, match="production"):
        MLProviderManager(
            Settings(
                _env_file=None,
                APP_ENV="production",
                ML_PROVIDER_MODE="mock",
                ML_SERVICE_URL="https://ml.example.com",
                ML_SERVICE_API_KEY="prod_ml_api_key_0123456789_abcdef_01",
                DATABASE_URL=env["DATABASE_URL"],
                DB_PASSWORD=env["DB_PASSWORD"],
                REDIS_URL=settings.REDIS_URL,
                ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
                ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
                JWT_SECRET_KEY="prod_jwt_secret_key_0123456789_abcdef",
                CORS_ALLOWED_ORIGINS="https://app.example.com",
            )
        )

    prod_auto = MLProviderManager(
        Settings(
            _env_file=None,
            APP_ENV="production",
            ML_PROVIDER_MODE="auto",
            ML_SERVICE_URL="https://ml.example.com",
            ML_SERVICE_API_KEY="prod_ml_api_key_0123456789_abcdef_01",
            DATABASE_URL=env["DATABASE_URL"],
            DB_PASSWORD=env["DB_PASSWORD"],
            REDIS_URL=settings.REDIS_URL,
            ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
            ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
            JWT_SECRET_KEY="prod_jwt_secret_key_0123456789_abcdef",
            CORS_ALLOWED_ORIGINS="https://app.example.com",
        )
    )
    assert prod_auto.allows_mock is False
    assert prod_auto.mock_adapter is None
    assert _current_provider(prod_auto) == "real_ml"
    await prod_auto.aclose()

    # In test `auto` mode, unreachable real ML switches on health probe & publishes Redis status
    stub_real = _StubRealAdapter(healthy=False, fail_analyze=True)
    auto_mgr = MLProviderManager(
        _e2e_settings(ML_PROVIDER_MODE="auto", ML_HEALTH_CHECK_INTERVAL_SECONDS=60),
        real_adapter=stub_real,
        mock_adapter=MockMLAdapter(),
        redis_client=redis_client,
    )
    health = await auto_mgr.refresh_provider_status(publish_redis=True)
    assert health.reachable is True
    assert _current_provider(auto_mgr) == "mock_ml"
    snap = await read_provider_status(redis_client)
    assert snap is not None and snap.provider == "mock_ml"

    # Once real ML recovers on probe, mid-flight analyze failure raises (zero silent fallback!)
    stub_real.healthy = True
    await auto_mgr.refresh_provider_status(publish_redis=True)
    assert _current_provider(auto_mgr) == "real_ml"
    f91 = json.loads((FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8"))
    with pytest.raises(MLTransportError):
        await auto_mgr.analyze(f91, idempotency_key="strict-no-fallback")
    await auto_mgr.aclose()


@pytest.mark.asyncio
async def test_local_analysis_submit_p95_latency_under_300ms(
    e2e_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, _redis = e2e_ctx
    f91: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            ip = "198.51.100.99"
            reg = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "perf.farmer@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Perf Farmer",
                    "preferred_lang": "en",
                },
            )
            headers = {
                "Authorization": f"Bearer {reg.json()['access_token']}",
                "X-Forwarded-For": ip,
            }
            farm_id = (
                await client.post(
                    "/api/v1/farms",
                    headers=headers,
                    json={"farm_name": "Perf Farm", "country": "Algeria", "region": "Guelma"},
                )
            ).json()["farm_id"]
            assert (
                await client.post(
                    f"/api/v1/farms/{farm_id}/fields",
                    headers=headers,
                    json=_field_payload_from_fixture(f91["fields"][0]),
                )
            ).status_code == 201

            # Warmup single submission to populate pools/JIT caches cleanly
            warm_body = _analysis_body_from_fixture(farm_id, f91)
            assert (
                await client.post("/api/v1/analysis", headers=headers, json=warm_body)
            ).status_code == 202

            latencies_ms: list[float] = []
            for idx in range(1, 21):
                req_body = copy.deepcopy(warm_body)
                req_body["planning"]["start_year"] = 2028 + idx
                started = time.perf_counter()
                resp = await client.post("/api/v1/analysis", headers=headers, json=req_body)
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                assert resp.status_code == 202
                latencies_ms.append(elapsed_ms)

            ordered = sorted(latencies_ms)
            p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
            p95_ms = ordered[p95_index]
            assert p95_ms < 300.0, f"POST /analysis local p95={p95_ms:.2f}ms >= 300ms: {ordered}"
