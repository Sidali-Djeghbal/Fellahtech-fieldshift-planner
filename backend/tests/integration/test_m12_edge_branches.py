"""Integration edge-branch tests against real PostGIS & Redis (`M12`)."""

from __future__ import annotations

import asyncio
import copy
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

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, MockMLAdapter
from app.models.analysis import AnalysisRequest
from app.repositories import analysis as analysis_repo
from app.services.analysis import _reconstruct_degraded_mode
from app.services.catalog import sync_catalog_once
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

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


def _edge_settings(**overrides: Any) -> Settings:
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
        "planning": copy.deepcopy(fixture_input["planning"]),
        "priorities": copy.deepcopy(fixture_input["priorities"]),
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
async def edge_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _edge_settings()
    engine = create_db_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await _cleanup_all(sessionmaker)
    await redis_client.flushdb()
    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await redis_client.flushdb()
        await redis_client.aclose()
        await _cleanup_all(sessionmaker)
        await engine.dispose()


@pytest.mark.asyncio
async def test_fields_service_and_analysis_repo_edge_branches(
    edge_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    """Cover field PUT/PATCH/DELETE 404s, geo rollback, empty-catalog sync, and repo edges."""
    settings, _engine, sessionmaker, _redis_client = edge_ctx
    f91 = json.loads((FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8"))

    # Precondition: empty catalog with offline ML -> 502 ML_UNAVAILABLE before seeding catalog
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            ip = "198.51.100.81"
            g_resp = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            gh = {"X-Guest-Token": g_resp.json()["guest_token"], "X-Forwarded-For": ip}
            farm_id = (
                await client.post(
                    "/api/v1/farms",
                    headers=gh,
                    json={"farm_name": "Edge Farm", "country": "Algeria", "region": "Guelma"},
                )
            ).json()["farm_id"]
            fld_payload = _field_payload_from_fixture(f91["fields"][0])
            assert (
                await client.post(f"/api/v1/farms/{farm_id}/fields", headers=gh, json=fld_payload)
            ).status_code == 201

            # Missing field PUT / PATCH / DELETE -> 404
            missing_put = copy.deepcopy(fld_payload)
            missing_put["field_id"] = "F_MISSING"
            assert (
                await client.put(
                    f"/api/v1/farms/{farm_id}/fields/F_MISSING", headers=gh, json=missing_put
                )
            ).status_code == 404
            assert (
                await client.patch(
                    f"/api/v1/farms/{farm_id}/fields/F_MISSING",
                    headers=gh,
                    json={"field_name": "Nope"},
                )
            ).status_code == 404
            assert (
                await client.delete(
                    f"/api/v1/farms/{farm_id}/fields/F_MISSING", headers=gh
                )
            ).status_code == 404

            # PATCH updating area_hectares & elevation_m -> 200
            patch_ok = await client.patch(
                f"/api/v1/farms/{farm_id}/fields/F1",
                headers=gh,
                json={"area_hectares": 12.5, "elevation_m": 410.0},
            )
            assert patch_ok.status_code == 200
            assert patch_ok.json()["area_hectares"] == pytest.approx(12.5)
            assert patch_ok.json()["elevation_m"] == pytest.approx(410.0)

            # PUT moving guest field outside Guelma boundary -> 422 OUTSIDE_DEMO_BOUNDARY
            out_put = copy.deepcopy(fld_payload)
            out_put["location"] = {"latitude": 36.19, "longitude": 5.41, "boundary": None}
            put_out = await client.put(
                f"/api/v1/farms/{farm_id}/fields/F1", headers=gh, json=out_put
            )
            assert put_out.status_code == 422
            assert put_out.json()["error"]["code"] == "OUTSIDE_DEMO_BOUNDARY"

            # Empty catalog + offline ML during submit -> 502 ML_UNAVAILABLE
            app.state.ml_provider_manager.mock_adapter.set_fault_mode("offline")
            no_cat_body = _analysis_body_from_fixture(farm_id, f91)
            r_nocat = await client.post("/api/v1/analysis", headers=gh, json=no_cat_body)
            assert r_nocat.status_code == 502
            assert r_nocat.json()["error"]["code"] == "ML_UNAVAILABLE"

            # Recover ML, seed catalog via submit, test unknown crop_id -> 409
            app.state.ml_provider_manager.mock_adapter.set_fault_mode("none")
            bad_crop = _analysis_body_from_fixture(farm_id, f91)
            bad_crop["priorities"]["target_crop_ids"] = ["nonexistent_crop_xyz"]
            r_bad_crop = await client.post("/api/v1/analysis", headers=gh, json=bad_crop)
            assert r_bad_crop.status_code == 409
            assert r_bad_crop.json()["error"]["code"] == "CATALOG_VERSION_MISMATCH"

            # Invalid empty Idempotency-Key & mismatched payload reuse -> 400 then 409
            base_body = _analysis_body_from_fixture(farm_id, f91)
            assert (
                await client.post(
                    "/api/v1/analysis",
                    headers={**gh, "Idempotency-Key": "   "},
                    json=base_body,
                )
            ).status_code == 400
            r_idem1 = await client.post(
                "/api/v1/analysis",
                headers={**gh, "Idempotency-Key": "idem-edge-1"},
                json=base_body,
            )
            assert r_idem1.status_code == 202, r_idem1.text
            diff_body = copy.deepcopy(base_body)
            diff_body["planning"]["start_year"] = 2030
            r_mismatch = await client.post(
                "/api/v1/analysis",
                headers={**gh, "Idempotency-Key": "idem-edge-1"},
                json=diff_body,
            )
            assert r_mismatch.status_code == 409

    # Repository finalize & lookup edge states against real DB
    async with sessionmaker() as db:
        farm_pk = int((await db.execute(text("SELECT id FROM public.farms LIMIT 1"))).scalar_one())
        assert await analysis_repo.get_owned_analysis_fields(
            db, farm_pk=farm_pk, requested_field_ids=[]
        ) is None
        assert await analysis_repo.get_owned_analysis_fields(
            db, farm_pk=farm_pk, requested_field_ids=["F1", "NO_SUCH"]
        ) is None

        missing_req_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        disp_miss = await analysis_repo.lock_and_mark_dispatched(
            db, request_id=missing_req_id, now=now
        )
        assert disp_miss[0] == "abort"
        canc_miss = await analysis_repo.finalize_worker_cancelled(db, request_id=missing_req_id)
        assert canc_miss.outcome == "vanished"
        assert (
            await analysis_repo.finalize_worker_failure(
                db,
                request_id=missing_req_id,
                error_code=ErrorCode.ML_UNAVAILABLE,
                duration_ms=10,
                max_guest_ml_refunds=2,
                now=now,
            )
        ).outcome == "vanished"
        assert (
            await analysis_repo.finalize_worker_success(
                db,
                request_id=missing_req_id,
                result_status="ok",
                dataset_version_used=DEFAULT_DATASET_VERSION,
                ml_engine_version="agro-ml-2.1.0",
                result_json={},
                validation_passed=True,
                validation_errors=None,
                failure_error_code=None,
                duration_ms=10,
                catalog_version_used="2026.11",
                max_guest_ml_refunds=2,
                now=now,
            )
        ).outcome == "vanished"

        # Existing pending request -> skipped by running-only finalize functions
        existing_row = await db.execute(
            text("SELECT request_id FROM public.analysis_requests LIMIT 1")
        )
        existing_req_id = str(existing_row.scalar_one())
        disp_skip = await analysis_repo.lock_and_mark_dispatched(
            db, request_id=existing_req_id, now=now
        )
        assert disp_skip[0] == "abort"
        canc_skip = await analysis_repo.finalize_worker_cancelled(db, request_id=existing_req_id)
        assert canc_skip.outcome == "skipped"
        assert (
            await analysis_repo.finalize_worker_failure(
                db,
                request_id=existing_req_id,
                error_code=ErrorCode.ML_UNAVAILABLE,
                duration_ms=10,
                max_guest_ml_refunds=2,
                now=now,
            )
        ).outcome == "skipped"

        # Missing source analysis_id for replay reconstruction returns None
        fake_replay_req = AnalysisRequest(
            request_id=str(uuid.uuid4()),
            farm_id=farm_pk,
            schema_version="5.0",
            catalog_version="2026.11",
            dataset_version=DEFAULT_DATASET_VERSION,
            language="en",
            status="ok",
            error_code="last_good_replay:analysis_missing_xyz",
            input_hash="c" * 64,
            full_input_hash="d" * 64,
            input_snapshot_gz=b"x",
            warnings=[],
        )
        assert await _reconstruct_degraded_mode(db, req=fake_replay_req, now=now) is None
        await db.rollback()


@pytest.mark.asyncio
async def test_worker_runner_corrupt_snapshot_cancellation_429_retry_and_loop(
    edge_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    """Exercise worker corrupt snapshot, pre-dispatch cancel refund, 429 retry, and daemon loop."""
    settings, engine, sessionmaker, redis_client = edge_ctx
    f91 = json.loads((FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8"))

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    mock_adapter = MockMLAdapter(retry_after_seconds=0)
    mock_adapter.set_fault_sequence(["http_429", "none"])
    ml_mgr = MLProviderManager(settings, mock_adapter=mock_adapter)
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            ip = "198.51.100.82"
            gh = {
                "X-Guest-Token": (
                    await client.post(
                        "/api/v1/auth/guest",
                        headers={"X-Forwarded-For": ip},
                        json={"demo_location_id": GUELMA_LOCATION_ID},
                    )
                ).json()["guest_token"],
                "X-Forwarded-For": ip,
            }
            farm_id = (
                await client.post(
                    "/api/v1/farms",
                    headers=gh,
                    json={
                        "farm_name": "Worker Edge Farm",
                        "country": "Algeria",
                        "region": "Guelma",
                    },
                )
            ).json()["farm_id"]
            assert (
                await client.post(
                    f"/api/v1/farms/{farm_id}/fields",
                    headers=gh,
                    json=_field_payload_from_fixture(f91["fields"][0]),
                )
            ).status_code == 201

            body = _analysis_body_from_fixture(farm_id, f91)
            r1 = await client.post("/api/v1/analysis", headers=gh, json=body)
            assert r1.status_code == 202

            body2 = copy.deepcopy(body)
            body2["planning"]["start_year"] = 2028
            r2 = await client.post("/api/v1/analysis", headers=gh, json=body2)
            req_corrupt_id = r2.json()["request_id"]

            # Corrupt snapshot on req_corrupt_id
            async with sessionmaker() as db:
                await db.execute(
                    text(
                        "UPDATE public.analysis_requests SET input_snapshot_gz = :bad "
                        "WHERE request_id = :rid"
                    ),
                    {"bad": b"not-gzip", "rid": req_corrupt_id},
                )
                await db.commit()

            runner = WorkerRunner(
                settings=settings,
                engine=engine,
                sessionmaker=sessionmaker,
                redis_client=redis_client,
                ml_manager=ml_mgr,
                poll_interval_seconds=0.05,
                worker_concurrency=1,
            )
            # First job hits one-shot 429 retry and completes; second fails INTERNAL_ERROR
            s1 = await runner.run_once()
            s2 = await runner.run_once()
            assert s1 is not None and s1.outcome == "completed"
            assert s1.retries_used == 1
            assert s2 is not None and s2.outcome == "failed"

            # Direct finalize_worker_failure with require_stale_before on fresh running lease
            body3 = copy.deepcopy(body)
            body3["planning"]["start_year"] = 2029
            r3 = await client.post("/api/v1/analysis", headers=gh, json=body3)
            req_fresh_id = r3.json()["request_id"]
            async with sessionmaker() as db:
                await db.execute(
                    text(
                        "UPDATE public.analysis_requests SET status = 'running', "
                        "lease_until = :lu WHERE request_id = :rid"
                    ),
                    {"lu": datetime.now(UTC) + timedelta(minutes=5), "rid": req_fresh_id},
                )
                await db.commit()
            async with sessionmaker() as db:
                sk1 = await analysis_repo.finalize_worker_cancelled(
                    db, request_id=req_fresh_id, require_stale_before=datetime.now(UTC)
                )
                sk2 = await analysis_repo.finalize_worker_failure(
                    db,
                    request_id=req_fresh_id,
                    error_code=ErrorCode.ML_UNAVAILABLE,
                    duration_ms=10,
                    max_guest_ml_refunds=2,
                    now=datetime.now(UTC),
                    require_stale_before=datetime.now(UTC),
                )
                await db.rollback()
                assert sk1.outcome == "skipped" and sk2.outcome == "skipped"

            # Running request with cancelled_at set before dispatch & on failure/replay
            async with sessionmaker() as db:
                await db.execute(
                    text(
                        "UPDATE public.analysis_requests SET cancelled_at = NOW(), "
                        "sent_at = NULL, quota_units = 4 WHERE request_id = :rid"
                    ),
                    {"rid": req_fresh_id},
                )
                await db.commit()
            async with sessionmaker() as db:
                act_c, ref_c, _ = await analysis_repo.lock_and_mark_dispatched(
                    db, request_id=req_fresh_id, now=datetime.now(UTC)
                )
                assert act_c == "cancelled" and ref_c == 4
                await db.rollback()
            async with sessionmaker() as db:
                fin_fail_c = await analysis_repo.finalize_worker_failure(
                    db,
                    request_id=req_fresh_id,
                    error_code=ErrorCode.ML_UNAVAILABLE,
                    duration_ms=10,
                    max_guest_ml_refunds=2,
                    now=datetime.now(UTC),
                )
                assert fin_fail_c.outcome == "cancelled" and fin_fail_c.refunded_quarters == 4
                await db.rollback()

            # Run worker daemon briefly via stop_event
            stop_ev = asyncio.Event()
            daemon_task = asyncio.create_task(runner.run(stop_ev))
            await asyncio.sleep(0.12)
            stop_ev.set()
            await daemon_task
