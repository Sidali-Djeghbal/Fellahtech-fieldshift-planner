"""34-route live OpenAPI 3.1 + JSON Schema Draft 2020-12 contract conformance tests (`M12`)."""

from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from referencing.typing import URI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLProviderManager, validate_contract_def
from app.services.catalog import sync_catalog_once
from app.worker.runner import WorkerRunner
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
_OPENAPI_DOC: dict[str, Any] = yaml.safe_load(
    (BACKEND_DIR / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
_SCHEMA_DOC: dict[str, Any] = json.loads(
    (BACKEND_DIR / "contracts" / "schema-v5.0.json").read_text(encoding="utf-8")
)
_OPENAPI_URI: URI = "https://fieldshift.local/contracts/openapi.yaml"
_SCHEMA_URI: URI = "https://fieldshift.local/contracts/schema-v5.0.json"
_REGISTRY: Registry[Any] = Registry().with_resources(
    [
        (_OPENAPI_URI, Resource.from_contents(_OPENAPI_DOC, default_specification=DRAFT202012)),
        (_SCHEMA_URI, Resource.from_contents(_SCHEMA_DOC, default_specification=DRAFT202012)),
    ]
)


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _free_unbound_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _contract_settings(**overrides: Any) -> Settings:
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
        "GUEST_BURST_PER_MIN": 500,
        "RATE_LIMIT_CRUD_PER_MIN": 500,
        "RATE_LIMIT_ANALYSIS_PER_HOUR": 500,
        "ANALYSIS_PER_IP_HOUR": 500,
        "ALLOW_SYNC_WAIT": True,
        "SYNC_WAIT_TIMEOUT_SECONDS": 5,
    }
    params.update(overrides)
    return Settings(**params)


def _escape_json_pointer(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _validate_openapi_response(
    method: str,
    spec_path: str,
    status_code: int,
    payload: Any,
) -> None:
    op = _OPENAPI_DOC["paths"][spec_path][method.lower()]
    resp_spec = op["responses"][str(status_code)]
    if "$ref" in resp_spec:
        schema_ref = f"{_OPENAPI_URI}{resp_spec['$ref']}/content/application~1json/schema"
    else:
        schema_ref = (
            f"{_OPENAPI_URI}#/paths/{_escape_json_pointer(spec_path)}"
            f"/{method.lower()}/responses/{status_code}/content/application~1json/schema"
        )
    scoped = Draft202012Validator(
        {"$ref": schema_ref},
        registry=_REGISTRY,
        format_checker=FormatChecker(),
    )
    errors = sorted(scoped.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, (
        f"OpenAPI mismatch for {method} {spec_path} ({status_code}): "
        f"{[f'{list(e.path)}: {e.message}' for e in errors]}"
    )


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
async def contract_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _contract_settings()
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


def test_all_34_openapi_routes_registered_with_operation_ids_and_option_a() -> None:
    app = create_app(_contract_settings())
    live_openapi = app.openapi()

    spec_ops: dict[tuple[str, str], dict[str, Any]] = {}
    for spec_path, path_item in _OPENAPI_DOC["paths"].items():
        for method, op in path_item.items():
            if method.lower() in _HTTP_METHODS:
                spec_ops[(method.upper(), spec_path)] = op

    assert len(spec_ops) == 34

    live_ops: dict[tuple[str, str], dict[str, Any]] = {}
    for full_path, path_item in live_openapi["paths"].items():
        if not str(full_path).startswith("/api/v1"):
            continue
        rel_path = str(full_path).removeprefix("/api/v1") or "/"
        for method, op in path_item.items():
            if method.lower() in _HTTP_METHODS:
                live_ops[(method.upper(), rel_path)] = op

    assert set(spec_ops.keys()) <= set(live_ops.keys()), (
        f"Missing OpenAPI routes in live FastAPI app: {sorted(set(spec_ops) - set(live_ops))}"
    )

    for key, spec_op in spec_ops.items():
        live_op = live_ops[key]
        assert live_op.get("operationId") == spec_op.get("operationId"), (
            f"operationId mismatch for {key}"
        )

    assert live_ops[("GET", "/metrics")].get("x-internal-only") is True

    # Option A global responses verified in schema (`429`/`500`/`503` on components.responses).
    for resp_name in ("RateLimited", "InternalError", "ServiceOrDatasetUnavailable"):
        assert resp_name in _OPENAPI_DOC["components"]["responses"]


@pytest.mark.asyncio
async def test_live_34_routes_request_response_schema_conformance(
    contract_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = contract_ctx

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    tested_ops: set[tuple[str, str]] = set()
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # 1-2: System /health & /metrics
            h_resp = await client.get("/api/v1/health")
            assert h_resp.status_code == 200
            _validate_openapi_response("GET", "/health", 200, h_resp.json())
            tested_ops.add(("GET", "/health"))

            m_resp = await client.get("/api/v1/metrics")
            assert m_resp.status_code == 200
            assert m_resp.headers["content-type"].startswith("text/plain")
            tested_ops.add(("GET", "/metrics"))

            # 3-4: Demo locations & boundary
            dl_resp = await client.get("/api/v1/demo/locations?limit=10")
            assert dl_resp.status_code == 200
            _validate_openapi_response("GET", "/demo/locations", 200, dl_resp.json())
            tested_ops.add(("GET", "/demo/locations"))

            bnd_resp = await client.get(f"/api/v1/demo/locations/{GUELMA_LOCATION_ID}/boundary")
            assert bnd_resp.status_code == 200
            _validate_openapi_response(
                "GET", "/demo/locations/{id}/boundary", 200, bnd_resp.json()
            )
            tested_ops.add(("GET", "/demo/locations/{id}/boundary"))

            # 5-7: Guest start -> inspect -> guest CRUD -> claim setup
            ip = "198.51.100.120"
            g_resp = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            assert g_resp.status_code == 201
            _validate_openapi_response("POST", "/auth/guest", 201, g_resp.json())
            tested_ops.add(("POST", "/auth/guest"))
            guest_headers = {"X-Guest-Token": g_resp.json()["guest_token"], "X-Forwarded-For": ip}

            ds_resp = await client.get("/api/v1/demo/session", headers=guest_headers)
            assert ds_resp.status_code == 200
            _validate_openapi_response("GET", "/demo/session", 200, ds_resp.json())
            tested_ops.add(("GET", "/demo/session"))

            # Create guest farm & field to claim later, plus test catalog as guest
            gf_resp = await client.post(
                "/api/v1/farms",
                headers=guest_headers,
                json={"farm_name": "Contract Guest Farm", "country": "Algeria", "region": "Guelma"},
            )
            assert gf_resp.status_code == 201
            _validate_openapi_response("POST", "/farms", 201, gf_resp.json())
            tested_ops.add(("POST", "/farms"))
            guest_farm_id = gf_resp.json()["farm_id"]

            cat_resp = await client.get("/api/v1/catalog", headers=guest_headers)
            assert cat_resp.status_code == 200
            _validate_openapi_response("GET", "/catalog", 200, cat_resp.json())
            tested_ops.add(("GET", "/catalog"))

            # Separate guest session for DELETE /demo/session test
            g2_resp = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            assert g2_resp.status_code == 201
            del_ds_resp = await client.delete(
                "/api/v1/demo/session",
                headers={"X-Guest-Token": g2_resp.json()["guest_token"]},
            )
            assert del_ds_resp.status_code == 204
            tested_ops.add(("DELETE", "/demo/session"))

            # 8-14: Register -> login -> refresh -> me -> claim-guest -> export
            reg_resp = await client.post(
                "/api/v1/auth/register",
                headers={"X-Forwarded-For": ip},
                json={
                    "email": "contract.user@example.com",
                    "password": "StrongPassword!123",
                    "full_name": "Contract Farmer",
                    "preferred_lang": "en",
                },
            )
            assert reg_resp.status_code == 201
            _validate_openapi_response("POST", "/auth/register", 201, reg_resp.json())
            tested_ops.add(("POST", "/auth/register"))

            login_resp = await client.post(
                "/api/v1/auth/login",
                headers={"X-Forwarded-For": ip},
                json={"email": "contract.user@example.com", "password": "StrongPassword!123"},
            )
            assert login_resp.status_code == 200
            _validate_openapi_response("POST", "/auth/login", 200, login_resp.json())
            tested_ops.add(("POST", "/auth/login"))

            ref_resp = await client.post(
                "/api/v1/auth/refresh",
                headers={"X-Forwarded-For": ip},
                json={"refresh_token": login_resp.json()["refresh_token"]},
            )
            assert ref_resp.status_code == 200
            _validate_openapi_response("POST", "/auth/refresh", 200, ref_resp.json())
            tested_ops.add(("POST", "/auth/refresh"))

            auth_headers = {
                "Authorization": f"Bearer {ref_resp.json()['access_token']}",
                "X-Forwarded-For": ip,
            }
            me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
            assert me_resp.status_code == 200
            _validate_openapi_response("GET", "/auth/me", 200, me_resp.json())
            tested_ops.add(("GET", "/auth/me"))

            claim_resp = await client.post(
                "/api/v1/auth/claim-guest",
                headers={**auth_headers, "X-Guest-Token": guest_headers["X-Guest-Token"]},
            )
            assert claim_resp.status_code == 200
            _validate_openapi_response("POST", "/auth/claim-guest", 200, claim_resp.json())
            tested_ops.add(("POST", "/auth/claim-guest"))

            # 15-26: Farms & Fields full CRUD (GET list/detail, PUT, PATCH, DELETE)
            fl_resp = await client.get("/api/v1/farms?limit=10", headers=auth_headers)
            assert fl_resp.status_code == 200
            _validate_openapi_response("GET", "/farms", 200, fl_resp.json())
            tested_ops.add(("GET", "/farms"))

            fg_resp = await client.get(f"/api/v1/farms/{guest_farm_id}", headers=auth_headers)
            assert fg_resp.status_code == 200
            _validate_openapi_response("GET", "/farms/{farm_id}", 200, fg_resp.json())
            tested_ops.add(("GET", "/farms/{farm_id}"))

            put_f_resp = await client.put(
                f"/api/v1/farms/{guest_farm_id}",
                headers=auth_headers,
                json={"farm_name": "Replaced Farm", "country": "Algeria", "region": "Guelma"},
            )
            assert put_f_resp.status_code == 200
            _validate_openapi_response("PUT", "/farms/{farm_id}", 200, put_f_resp.json())
            tested_ops.add(("PUT", "/farms/{farm_id}"))

            pat_f_resp = await client.patch(
                f"/api/v1/farms/{guest_farm_id}",
                headers=auth_headers,
                json={"farm_name": "Patched Farm"},
            )
            assert pat_f_resp.status_code == 200
            _validate_openapi_response("PATCH", "/farms/{farm_id}", 200, pat_f_resp.json())
            tested_ops.add(("PATCH", "/farms/{farm_id}"))

            cfld_resp = await client.post(
                f"/api/v1/farms/{guest_farm_id}/fields",
                headers=auth_headers,
                json={
                    "field_id": "F1",
                    "field_name": "Contract Parcel",
                    "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
                    "area_hectares": 12.0,
                    "soil": {"soil_type": "loamy", "soil_ph": 7.1},
                    "water": {
                        "availability": "moderate",
                        "source": "well",
                        "irrigation_system": "drip",
                    },
                    "crop_history": [
                        {"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}
                    ],
                },
            )
            assert cfld_resp.status_code == 201
            _validate_openapi_response(
                "POST", "/farms/{farm_id}/fields", 201, cfld_resp.json()
            )
            tested_ops.add(("POST", "/farms/{farm_id}/fields"))

            flds_resp = await client.get(
                f"/api/v1/farms/{guest_farm_id}/fields?limit=10", headers=auth_headers
            )
            assert flds_resp.status_code == 200
            _validate_openapi_response("GET", "/farms/{farm_id}/fields", 200, flds_resp.json())
            tested_ops.add(("GET", "/farms/{farm_id}/fields"))

            fld_resp = await client.get(
                f"/api/v1/farms/{guest_farm_id}/fields/F1", headers=auth_headers
            )
            assert fld_resp.status_code == 200
            _validate_openapi_response(
                "GET", "/farms/{farm_id}/fields/{field_id}", 200, fld_resp.json()
            )
            tested_ops.add(("GET", "/farms/{farm_id}/fields/{field_id}"))

            put_fld = await client.put(
                f"/api/v1/farms/{guest_farm_id}/fields/F1",
                headers=auth_headers,
                json={
                    "field_id": "F1",
                    "field_name": "Replaced Parcel",
                    "location": {"latitude": 36.462, "longitude": 7.431, "boundary": None},
                    "area_hectares": 12.5,
                    "soil": {"soil_type": "loamy", "soil_ph": 7.2},
                    "water": {
                        "availability": "moderate",
                        "source": "well",
                        "irrigation_system": "drip",
                    },
                    "crop_history": [
                        {"season": "autumn", "year": 2025, "crop_id": "durum_wheat"}
                    ],
                },
            )
            assert put_fld.status_code == 200
            _validate_openapi_response(
                "PUT", "/farms/{farm_id}/fields/{field_id}", 200, put_fld.json()
            )
            tested_ops.add(("PUT", "/farms/{farm_id}/fields/{field_id}"))

            pat_fld = await client.patch(
                f"/api/v1/farms/{guest_farm_id}/fields/F1",
                headers=auth_headers,
                json={"field_name": "Patched Parcel"},
            )
            assert pat_fld.status_code == 200
            _validate_openapi_response(
                "PATCH", "/farms/{farm_id}/fields/{field_id}", 200, pat_fld.json()
            )
            tested_ops.add(("PATCH", "/farms/{farm_id}/fields/{field_id}"))

            # 27-32: Analysis submit, pending poll, worker run, result & selection
            analysis_body: dict[str, Any] = {
                "farm_id": guest_farm_id,
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
                    "target_crop_ids": ["chickpea"],
                    "excluded_crop_ids": [],
                },
            }
            sub1 = await client.post("/api/v1/analysis", headers=auth_headers, json=analysis_body)
            assert sub1.status_code == 202
            _validate_openapi_response("POST", "/analysis", 202, sub1.json())
            tested_ops.add(("POST", "/analysis"))
            req1_id = sub1.json()["request_id"]

            poll_pending = await client.get(
                f"/api/v1/analysis/requests/{req1_id}", headers=auth_headers
            )
            assert poll_pending.status_code == 200
            assert "Retry-After" in poll_pending.headers
            _validate_openapi_response(
                "GET", "/analysis/requests/{request_id}", 200, poll_pending.json()
            )
            tested_ops.add(("GET", "/analysis/requests/{request_id}"))

            # Second request specifically to test cancel route
            cancel_body = copy.deepcopy(analysis_body)
            cancel_body["planning"]["start_year"] = 2028
            sub2 = await client.post("/api/v1/analysis", headers=auth_headers, json=cancel_body)
            assert sub2.status_code == 202
            req2_id = sub2.json()["request_id"]
            can_resp = await client.post(
                f"/api/v1/analysis/requests/{req2_id}/cancel", headers=auth_headers
            )
            assert can_resp.status_code == 200
            _validate_openapi_response(
                "POST", "/analysis/requests/{request_id}/cancel", 200, can_resp.json()
            )
            tested_ops.add(("POST", "/analysis/requests/{request_id}/cancel"))

            # Run worker once to complete req1_id
            worker = WorkerRunner(
                settings=settings,
                engine=engine,
                sessionmaker=sessionmaker,
                redis_client=redis_client,
                ml_manager=app.state.ml_provider_manager,
            )
            summary = await worker.run_once()
            assert summary is not None
            assert summary.outcome == "completed"
            assert summary.analysis_id is not None

            poll_done = await client.get(
                f"/api/v1/analysis/requests/{req1_id}", headers=auth_headers
            )
            assert poll_done.status_code == 200
            _validate_openapi_response(
                "GET", "/analysis/requests/{request_id}", 200, poll_done.json()
            )

            get_res = await client.get(
                f"/api/v1/analysis/{summary.analysis_id}", headers=auth_headers
            )
            assert get_res.status_code == 200
            _validate_openapi_response("GET", "/analysis/{analysis_id}", 200, get_res.json())
            tested_ops.add(("GET", "/analysis/{analysis_id}"))

            strategy_id = get_res.json()["result"]["field_plans"][0]["strategies"][0][
                "strategy_id"
            ]
            sel_resp = await client.patch(
                f"/api/v1/analysis/{summary.analysis_id}/selection",
                headers=auth_headers,
                json={"field_id": "F1", "strategy_id": strategy_id, "selection_status": "selected"},
            )
            assert sel_resp.status_code == 200
            _validate_openapi_response(
                "PATCH", "/analysis/{analysis_id}/selection", 200, sel_resp.json()
            )
            tested_ops.add(("PATCH", "/analysis/{analysis_id}/selection"))

            hist_resp = await client.get(
                f"/api/v1/farms/{guest_farm_id}/analyses?limit=10", headers=auth_headers
            )
            assert hist_resp.status_code == 200
            _validate_openapi_response("GET", "/farms/{farm_id}/analyses", 200, hist_resp.json())
            tested_ops.add(("GET", "/farms/{farm_id}/analyses"))

            # Populated GDPR portability export (zero binary/hash leaks!)
            exp_resp = await client.get("/api/v1/auth/me/export", headers=auth_headers)
            assert exp_resp.status_code == 200
            exp_body = exp_resp.json()
            _validate_openapi_response("GET", "/auth/me/export", 200, exp_body)
            tested_ops.add(("GET", "/auth/me/export"))
            assert len(exp_body["farms"]) == 1
            assert len(exp_body["fields"]) == 1
            assert len(exp_body["analysis_requests"]) == 2
            assert len(exp_body["analysis_results"]) == 1
            assert len(exp_body["analysis_selections"]) == 1

            # Delete field -> delete farm -> logout (using second fresh session) -> delete me
            del_fld = await client.delete(
                f"/api/v1/farms/{guest_farm_id}/fields/F1", headers=auth_headers
            )
            assert del_fld.status_code == 204
            tested_ops.add(("DELETE", "/farms/{farm_id}/fields/{field_id}"))

            del_frm = await client.delete(
                f"/api/v1/farms/{guest_farm_id}", headers=auth_headers
            )
            assert del_frm.status_code == 204
            tested_ops.add(("DELETE", "/farms/{farm_id}"))

            logout_resp = await client.post(
                "/api/v1/auth/logout",
                headers=auth_headers,
                json={"refresh_token": ref_resp.json()["refresh_token"]},
            )
            assert logout_resp.status_code == 204
            tested_ops.add(("POST", "/auth/logout"))

            del_me = await client.delete("/api/v1/auth/me", headers=auth_headers)
            assert del_me.status_code == 204
            tested_ops.add(("DELETE", "/auth/me"))

    spec_all = {
        (method.upper(), spec_path)
        for spec_path, path_item in _OPENAPI_DOC["paths"].items()
        for method in path_item
        if method.lower() in _HTTP_METHODS
    }
    assert tested_ops == spec_all


def test_official_fixtures_and_schema_version_mutations() -> None:
    f91 = json.loads((FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8"))
    f92 = json.loads((FIXTURES_DIR / "fixture_9_2_input_setif.json").read_text(encoding="utf-8"))
    f93 = json.loads((FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8"))
    f94 = json.loads((FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8"))

    assert validate_contract_def(f91, "FarmAnalysisInput") == []
    assert validate_contract_def(f92, "FarmAnalysisInput") == []
    assert validate_contract_def(f93, "AnalysisResult") == []
    assert validate_contract_def(f94, "CropCatalog") == []

    minor_bump = copy.deepcopy(f93)
    minor_bump["schema_version"] = "5.1"
    minor_bump["future_tolerant_hint"] = {"score": 0.99}
    assert validate_contract_def(minor_bump, "AnalysisResult") == []

    major_bump = copy.deepcopy(f93)
    major_bump["schema_version"] = "6.0"
    assert validate_contract_def(major_bump, "AnalysisResult") != []


@pytest.mark.asyncio
async def test_error_envelope_conformance_across_statuses(
    contract_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, _sessionmaker, _redis_client = contract_ctx
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            r401 = await client.get("/api/v1/auth/me")
            assert r401.status_code == 401
            _validate_openapi_response("GET", "/auth/me", 401, r401.json())

            r400 = await client.post("/api/v1/auth/guest", json={"demo_location_id": 0})
            assert r400.status_code == 400
            _validate_openapi_response("POST", "/auth/guest", 400, r400.json())

            r404 = await client.post("/api/v1/auth/guest", json={"demo_location_id": 999999})
            assert r404.status_code == 404
            _validate_openapi_response("POST", "/auth/guest", 404, r404.json())
