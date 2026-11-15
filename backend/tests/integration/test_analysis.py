"""Real PostGIS + Redis integration & OpenAPI conformance tests for M7 Analysis REST API."""

from __future__ import annotations

import asyncio
import copy
import gzip
import json
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLAdapter, MLHealthResult, MLProviderManager, validate_contract_def
from app.ml_client.base import MLTransportError, ProviderKind
from app.models import AnalysisRequest, AnalysisResult
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import MLCatalogPayload
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)
_OPENAPI_DOC: dict[str, Any] = yaml.safe_load(
    (BACKEND_DIR / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
_SCHEMA_DOC: dict[str, Any] = json.loads(
    (BACKEND_DIR / "contracts" / "schema-v5.0.json").read_text(encoding="utf-8")
)


def _assert_openapi_schema(payload: Any, schema_name: str) -> None:
    """Validate HTTP JSON response strictly against `openapi.yaml` + `schema-v5.0.json`."""
    openapi_uri: URI = "https://fieldshift.local/contracts/openapi.yaml"
    schema_uri: URI = "https://fieldshift.local/contracts/schema-v5.0.json"
    registry = Registry().with_resources(
        [
            (
                openapi_uri,
                Resource.from_contents(_OPENAPI_DOC, default_specification=DRAFT202012),
            ),
            (
                schema_uri,
                Resource.from_contents(_SCHEMA_DOC, default_specification=DRAFT202012),
            ),
        ]
    )
    validator = Draft202012Validator(
        {"$ref": f"{openapi_uri}#/components/schemas/{schema_name}"},
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, f"OpenAPI schema {schema_name} mismatch: {[e.message for e in errors]}"


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _m7_settings(**overrides: Any) -> Settings:
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
        "GUEST_CREATE_PER_IP_HOUR": 50,
        "GUEST_BURST_PER_MIN": 100,
        "RATE_LIMIT_CRUD_PER_MIN": 100,
        "RATE_LIMIT_ANALYSIS_PER_HOUR": 20,
        "ANALYSIS_PER_IP_HOUR": 25,
        "TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128",
        "ALLOW_SYNC_WAIT": False,
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
async def m7_ctx(
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
    settings = _m7_settings()
    engine = create_db_engine(settings, role="api")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
    await _cleanup_all(sessionmaker)
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
    *,
    ml_manager: MLProviderManager | None = None,
) -> Any:
    app = create_app(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client
    app.state.ml_provider_manager = ml_manager or MLProviderManager(settings)
    return app


async def _start_guest(client: httpx.AsyncClient, ip: str = "198.51.100.11") -> str:
    resp = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert resp.status_code == 201
    return str(resp.json()["guest_token"])


async def _register_user(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword!123",
            "full_name": "Secret Farmer Name PII",
            "preferred_lang": "en",
        },
    )
    assert resp.status_code == 201
    return str(resp.json()["access_token"])


async def _create_farm(
    client: httpx.AsyncClient,
    headers: Mapping[str, str],
    name: str = "Ferme Guelma Test",
) -> str:
    resp = await client.post(
        "/api/v1/farms",
        headers=headers,
        json={"farm_name": name, "country": "Algeria", "region": "Guelma", "commune": "Guelma"},
    )
    assert resp.status_code == 201
    return str(resp.json()["farm_id"])


async def _create_field(
    client: httpx.AsyncClient,
    headers: Mapping[str, str],
    farm_id: str,
    *,
    field_id: str = "F1",
    latitude: float = 36.462,
    longitude: float = 7.431,
    unverified: bool = False,
) -> None:
    resp = await client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=headers,
        json={
            "field_id": field_id,
            "field_name": f"Parcel {field_id}",
            "is_unverified_demo_parcel": unverified,
            "location": {"latitude": latitude, "longitude": longitude, "boundary": None},
            "area_hectares": 12.5,
            "elevation_m": 240.0,
            "soil": {
                "soil_type": "loamy",
                "soil_ph": 7.1,
                "organic_matter_percent": 1.9,
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
                    "yield_tons_per_hectare": 3.4,
                    "notes": "PRIVATE FARMER NOTE PII +2135551234",
                }
            ],
        },
    )
    assert resp.status_code == 201


def _analysis_payload(
    farm_id: str,
    field_ids: list[str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "farm_id": farm_id,
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
                "soil_improvement": 25,
                "income": 25,
                "risk_reduction": 10,
                "forage_value": 10,
            },
            "market_preference": "mixed",
            "target_crop_ids": ["chickpea"],
            "excluded_crop_ids": ["barley"],
            "equipment_constraints": ["Limited NPK fertilizer"],
        },
        "field_ids": field_ids or ["F1"],
    }
    body.update(overrides)
    return body


async def _snapshot_analysis_rate_keys(redis_client: redis_async.Redis) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    async for raw_key in redis_client.scan_iter(match="rl:analysis:*"):
        key_str = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
        ttl = int(await redis_client.ttl(key_str))
        assert ttl > 0, f"Rate limit key {key_str} leaked with persistent TTL={ttl}"
        val = await redis_client.get(key_str)
        if val is not None:
            out[key_str] = val
    return out


class _OfflineMLAdapter(MLAdapter):
    @property
    def provider_name(self) -> ProviderKind:
        return "real_ml"

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        raise MLTransportError("ML offline in test")

    async def get_catalog(self) -> MLCatalogPayload:
        raise MLTransportError("ML catalog offline in test")

    async def get_health(self) -> MLHealthResult:
        return MLHealthResult(reachable=False, status="unreachable", provider="real_ml")


@pytest.mark.asyncio
async def test_submit_happy_zero_pii_snapshot_and_warning_aggregation(
    m7_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m7_ctx
    await _seed_catalog(sessionmaker)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        token = await _register_user(client, "farmer@example.com")
        headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": "198.51.100.20"}
        farm_id = await _create_farm(client, headers)
        await _create_field(
            client, headers, farm_id, field_id="F1", latitude=36.75, longitude=3.05, unverified=True
        )
        await _create_field(
            client,
            headers,
            farm_id,
            field_id="F2",
            latitude=36.462,
            longitude=7.431,
            unverified=True,
        )

        # Omit equipment_constraints completely to test IMPL-022 optional normalization too.
        body = _analysis_payload(farm_id, field_ids=["F1", "F2"])
        body["priorities"].pop("equipment_constraints")

        resp = await client.post("/api/v1/analysis", headers=headers, json=body)
        assert resp.status_code == 202
        assert resp.headers["Location"].startswith("/api/v1/analysis/requests/")
        assert "X-Request-Id" in resp.headers
        data = resp.json()
        _assert_openapi_schema(data, "AnalysisQueuedResponse")

        by_code = {w["code"]: w["fields"] for w in data["warnings"]}
        assert by_code["MVP_OUTSIDE_COVERAGE"] == ["F1"]
        assert by_code["DEMO_PARCEL_UNVERIFIED"] == ["F1", "F2"]

        async with sessionmaker() as db:
            req_row = await db.get(AnalysisRequest, data["request_id"])
            assert req_row is not None
            assert req_row.status == "pending"
            assert req_row.quota_units == 4
            assert req_row.input_snapshot_gz is not None
            raw_json = gzip.decompress(req_row.input_snapshot_gz).decode("utf-8")
            assert "PRIVATE FARMER NOTE PII" not in raw_json
            assert "Secret Farmer Name PII" not in raw_json
            assert "farmer@example.com" not in raw_json
            assert "198.51.100.20" not in raw_json
            snapshot = json.loads(raw_json)
            assert snapshot["priorities"]["equipment_constraints"] == []
            assert not validate_contract_def(snapshot, "FarmAnalysisInput")


@pytest.mark.asyncio
async def test_w1_precedence_and_non_burning_lua_rollbacks(
    m7_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m7_ctx
    await _seed_catalog(sessionmaker)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        owner_token = await _register_user(client, "owner@example.com")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_token = await _register_user(client, "other@example.com")
        other_headers = {"Authorization": f"Bearer {other_token}"}

        owner_farm = await _create_farm(client, owner_headers, name="Owner Farm")
        await _create_field(client, owner_headers, owner_farm, field_id="F1")

        # 1. Step 1: foreign ownership -> 404 before rate/input/wait checks.
        bad_own = await client.post(
            "/api/v1/analysis?wait=true",
            headers=other_headers,
            json=_analysis_payload(owner_farm, field_ids=["F1"]),
        )
        assert bad_own.status_code == 404

        # 2. Missing ?wait=true permission when ALLOW_SYNC_WAIT=false -> 400 without burning.
        before_rl = await _snapshot_analysis_rate_keys(redis_client)
        r_wait = await client.post(
            "/api/v1/analysis?wait=true",
            headers={**owner_headers, "X-Forwarded-For": "198.51.100.31"},
            json=_analysis_payload(owner_farm),
        )
        assert r_wait.status_code == 400
        assert (await _snapshot_analysis_rate_keys(redis_client)) == before_rl

        # Guest checks: 422 OUTSIDE_DEMO_BOUNDARY, 400 INPUT-01..03, 409 CATALOG, 503 DATASET, 403
        guest_token = await _start_guest(client, ip="198.51.100.40")
        g_headers = {"X-Guest-Token": guest_token, "X-Forwarded-For": "198.51.100.41"}
        g_farm = await _create_farm(client, g_headers, name="Guest Farm")
        await _create_field(
            client, g_headers, g_farm, field_id="FG1", latitude=36.462, longitude=7.431
        )

        # Insert a direct outside-Guelma field row under guest farm for POST /analysis Step 3 422
        async with sessionmaker() as db:
            farm_pk = int(g_farm.split("_", 1)[1])
            await db.execute(
                text(
                    "INSERT INTO public.fields (farm_id, external_field_id, field_name, "
                    "is_unverified_demo_parcel, geom_point, area_hectares, soil_type, soil_source, "
                    "water_availability, water_source, irrigation_system) "
                    "VALUES (:fpk, 'FOUT', 'Outside Guelma', false, "
                    "ST_SetSRID(ST_MakePoint(3.05, 36.75), 4326), 5.0, 'loamy', 'unknown', "
                    "'moderate', 'well', 'drip')"
                ),
                {"fpk": farm_pk},
            )
            await db.execute(
                text(
                    "INSERT INTO public.field_crop_history (field_id, season, year, crop_id) "
                    "SELECT id, 'autumn', 2025, 'durum_wheat' FROM public.fields "
                    "WHERE farm_id = :fpk AND external_field_id = 'FOUT'"
                ),
                {"fpk": farm_pk},
            )
            await db.commit()

        # 3a. 422 OUTSIDE_DEMO_BOUNDARY beats invalid INPUT-01 (sum!=100) AND rolls back Redis!
        bad_input_and_geo = _analysis_payload(g_farm, field_ids=["FOUT"])
        bad_input_and_geo["priorities"]["weights"]["water_saving"] = 99
        r_geo = await client.post("/api/v1/analysis", headers=g_headers, json=bad_input_and_geo)
        assert r_geo.status_code == 422
        assert r_geo.json()["error"]["code"] == "OUTSIDE_DEMO_BOUNDARY"
        assert (await _snapshot_analysis_rate_keys(redis_client)) == {}

        # 3b. 400 INPUT-01, INPUT-02, INPUT-03 all roll back Redis & guest quarters.
        for mut_name in ("input01", "input02", "input03", "dup_field"):
            payload = _analysis_payload(g_farm, field_ids=["FG1"])
            if mut_name == "input01":
                payload["priorities"]["weights"]["income"] = 24
            elif mut_name == "input02":
                payload["priorities"]["excluded_crop_ids"] = ["chickpea"]
            elif mut_name == "input03":
                payload["planning"]["start_season"] = "winter"
                payload["planning"]["planting_month"] = 6
            else:
                payload["field_ids"] = ["FG1", "FG1"]
            r_bad = await client.post("/api/v1/analysis", headers=g_headers, json=payload)
            assert r_bad.status_code == 400, f"Expected 400 for {mut_name}, got {r_bad.text}"
            assert (await _snapshot_analysis_rate_keys(redis_client)) == {}

        # 4a. Unknown crop triggers miss sync then 409 CATALOG_VERSION_MISMATCH + rollback.
        bad_crop = _analysis_payload(g_farm, field_ids=["FG1"])
        bad_crop["priorities"]["target_crop_ids"] = ["nonexistent_crop_m7"]
        r_cat = await client.post("/api/v1/analysis", headers=g_headers, json=bad_crop)
        assert r_cat.status_code == 409
        assert r_cat.json()["error"]["code"] == "CATALOG_VERSION_MISMATCH"
        assert (await _snapshot_analysis_rate_keys(redis_client)) == {}

        # 4b. Deactivated dataset_registry -> 503 DATASET_UNAVAILABLE + rollback.
        async with sessionmaker() as db:
            await db.execute(text("UPDATE public.dataset_registry SET is_active = false"))
            await db.commit()
        r_ds = await client.post(
            "/api/v1/analysis",
            headers=g_headers,
            json=_analysis_payload(g_farm, field_ids=["FG1"]),
        )
        assert r_ds.status_code == 503
        assert r_ds.json()["error"]["code"] == "DATASET_UNAVAILABLE"
        assert (await _snapshot_analysis_rate_keys(redis_client)) == {}
        async with sessionmaker() as db:
            await db.execute(
                text(
                    "UPDATE public.dataset_registry SET is_active = true "
                    "WHERE dataset_version = :v"
                ),
                {"v": DEFAULT_DATASET_VERSION},
            )
            await db.commit()

        # Verify guest analysis_quarters is STILL 0 after all those rejections!
        async with sessionmaker() as db:
            g_hash = hash_token(guest_token)
            sess_info = await client.get(
                "/api/v1/demo/session", headers={"X-Guest-Token": guest_token}
            )
            assert sess_info.status_code == 200
            assert sess_info.json()["usage"]["analysis_quarters"] == 0
            assert await redis_client.get(f"guest_quota:{g_hash}:quarters") in (None, b"0")

        # 5. Saturate guest to 40/40 quarters (10 analyses); verify 403 beats 422/400 + rolls back!
        for idx in range(10):
            p = _analysis_payload(g_farm, field_ids=["FG1"])
            p["planning"]["horizon_seasons"] = (idx % 6) + 1
            p["priorities"]["target_crop_ids"] = ["chickpea"] if idx < 5 else ["durum_wheat"]
            r_ok = await client.post("/api/v1/analysis", headers=g_headers, json=p)
            assert r_ok.status_code == 202, r_ok.text

        rl_at_limit = await _snapshot_analysis_rate_keys(redis_client)
        r_over = await client.post(
            "/api/v1/analysis",
            headers=g_headers,
            json=_analysis_payload(g_farm, field_ids=["FOUT"]),  # Outside boundary -> 403 wins!
        )
        assert r_over.status_code == 403
        assert r_over.json()["error"]["code"] == "GUEST_LIMIT_REACHED"
        assert (await _snapshot_analysis_rate_keys(redis_client)) == rl_at_limit


@pytest.mark.asyncio
async def test_cold_start_catalog_sync_on_analysis_and_offline_502_rollback(
    m7_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m7_ctx
    app_mock = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_mock),
        base_url="http://testserver",
    ) as client:
        token = await _register_user(client, "coldstart@example.com")
        headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": "198.51.100.55"}
        farm_id = await _create_farm(client, headers)
        await _create_field(client, headers, farm_id, field_id="F1")

        # First test empty catalog + offline real ML -> 502 ML_UNAVAILABLE + non-burning rollback!
        offline_settings = _m7_settings(ML_PROVIDER_MODE="real")
        offline_mgr = MLProviderManager(offline_settings, real_adapter=_OfflineMLAdapter())
        app_offline = _make_bound_app(
            offline_settings, engine, sessionmaker, redis_client, ml_manager=offline_mgr
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_offline),
            base_url="http://testserver",
        ) as offline_client:
            r_502 = await offline_client.post(
                "/api/v1/analysis",
                headers=headers,
                json=_analysis_payload(farm_id),
            )
            assert r_502.status_code == 502
            assert r_502.json()["error"]["code"] == "ML_UNAVAILABLE"
            assert (await _snapshot_analysis_rate_keys(redis_client)) == {}

        # Now empty catalog + MockMLAdapter -> Step 4 auto-syncs crop_catalog & enqueues 202!
        r_ok = await client.post(
            "/api/v1/analysis",
            headers=headers,
            json=_analysis_payload(farm_id),
        )
        assert r_ok.status_code == 202
        async with sessionmaker() as db:
            meta = await catalog_repo.get_latest_catalog_version_meta(db)
            assert meta is not None


@pytest.mark.asyncio
async def test_idempotency_24h_what_if_1_quarter_and_rate_limit_429(
    m7_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings = _m7_settings(RATE_LIMIT_ANALYSIS_PER_HOUR=2, ANALYSIS_PER_IP_HOUR=3)
    _, engine, sessionmaker, redis_client = m7_ctx
    await _seed_catalog(sessionmaker)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        token = await _start_guest(client, ip="198.51.100.60")
        headers = {"X-Guest-Token": token, "X-Forwarded-For": "198.51.100.61"}
        farm_id = await _create_farm(client, headers)
        await _create_field(client, headers, farm_id, field_id="F1")

        base_body = _analysis_payload(farm_id)
        # 1. Submit initial full analysis (4 quarters) with Idempotency-Key
        r1 = await client.post(
            "/api/v1/analysis",
            headers={**headers, "Idempotency-Key": "idem-k1"},
            json=base_body,
        )
        assert r1.status_code == 202
        req1_id = r1.json()["request_id"]

        # 2. Idempotent retry returns exact request_id consuming 0 quarters and 0 rate!
        r1_dup = await client.post(
            "/api/v1/analysis",
            headers={**headers, "Idempotency-Key": "idem-k1"},
            json=base_body,
        )
        assert r1_dup.status_code == 202
        assert r1_dup.json()["request_id"] == req1_id

        # 3. Same key with altered payload -> 409 CONFLICT consuming 0 quarters and 0 rate!
        altered = copy.deepcopy(base_body)
        altered["priorities"]["weights"]["water_saving"] = 40
        altered["priorities"]["weights"]["soil_improvement"] = 15
        r_conflict = await client.post(
            "/api/v1/analysis",
            headers={**headers, "Idempotency-Key": "idem-k1"},
            json=altered,
        )
        assert r_conflict.status_code == 409

        # 4. What-If tweak (different weights & scenario_overrides, NO reused key) -> quota_units=1!
        r2 = await client.post("/api/v1/analysis", headers=headers, json=altered)
        assert r2.status_code == 202
        req2_id = r2.json()["request_id"]
        assert req2_id != req1_id

        async with sessionmaker() as db:
            row1 = await db.get(AnalysisRequest, req1_id)
            row2 = await db.get(AnalysisRequest, req2_id)
            assert row1 is not None and row1.quota_units == 4 and row1.parent_request_id is None
            assert row2 is not None and row2.quota_units == 1
            assert row2.parent_request_id == req1_id

        # 5. Now used 5 quarters out of 12/hr IP limit (ANALYSIS_PER_IP_HOUR=3 => 12 quarters/h).
        # Submit another full run (4 quarters -> total 9), then a 4th full run (9+4=13 > 12 -> 429)!
        other_full = copy.deepcopy(base_body)
        other_full["planning"]["horizon_seasons"] = 5
        r3 = await client.post("/api/v1/analysis", headers=headers, json=other_full)
        assert r3.status_code == 202

        over_full = copy.deepcopy(base_body)
        over_full["planning"]["horizon_seasons"] = 6
        r4_429 = await client.post("/api/v1/analysis", headers=headers, json=over_full)
        assert r4_429.status_code == 429
        assert int(r4_429.headers["Retry-After"]) >= 1

        # 6. Expire idempotency key > 24h in DB and reuse `idem-k1` cleanly as user!
        async with sessionmaker() as db:
            await db.execute(
                text(
                    "UPDATE public.analysis_requests "
                    "SET created_at = :old_ts WHERE request_id = :rid"
                ),
                {"old_ts": datetime.now(UTC) - timedelta(hours=25), "rid": req1_id},
            )
            await db.commit()

        # What-If with fresh header/IP after 24h window expired resets key cleanly
        reused = await client.post(
            "/api/v1/analysis",
            headers={
                "X-Guest-Token": token,
                "X-Forwarded-For": "198.51.100.62",
                "Idempotency-Key": "idem-k1",
            },
            json=altered,
        )
        assert reused.status_code == 202
        assert reused.json()["request_id"] not in (req1_id, req2_id)
        async with sessionmaker() as db:
            old_row = await db.get(AnalysisRequest, req1_id)
            assert old_row is not None and old_row.idempotency_key is None


@pytest.mark.asyncio
async def test_poll_bucket_120_cancel_refund_selection_degraded_history_export_claim(
    m7_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings = _m7_settings(GUEST_BURST_PER_MIN=20, RATE_LIMIT_CRUD_PER_MIN=20)
    _, engine, sessionmaker, redis_client = m7_ctx
    await _seed_catalog(sessionmaker)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)
    fixture_result = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        guest_token = await _start_guest(client, ip="198.51.100.70")
        g_headers = {"X-Guest-Token": guest_token, "X-Forwarded-For": "198.51.100.71"}
        g_farm = await _create_farm(client, g_headers)
        await _create_field(client, g_headers, g_farm, field_id="F1")

        # Fresh guest has used 2 CRUD calls; later 120 poll calls must succeed!
        r_sub = await client.post(
            "/api/v1/analysis", headers=g_headers, json=_analysis_payload(g_farm)
        )
        assert r_sub.status_code == 202
        req_pending_id = r_sub.json()["request_id"]

        # Submit 2nd and 3rd distinct non-what-if requests (4 quarters each = 12 total)
        p_src = _analysis_payload(g_farm)
        p_src["planning"]["horizon_seasons"] = 5
        r_src = await client.post("/api/v1/analysis", headers=g_headers, json=p_src)
        assert r_src.status_code == 202
        req_src_id = r_src.json()["request_id"]

        p_rep = _analysis_payload(g_farm)
        p_rep["planning"]["horizon_seasons"] = 6
        r_replay = await client.post("/api/v1/analysis", headers=g_headers, json=p_rep)
        assert r_replay.status_code == 202
        req_replay_id = r_replay.json()["request_id"]

        # Poll pending request -> Retry-After: 2 & poll_interval_ms: 2000
        r_poll1 = await client.get(
            f"/api/v1/analysis/requests/{req_pending_id}", headers=g_headers
        )
        assert r_poll1.status_code == 200
        assert r_poll1.headers["Retry-After"] == "2"
        poll_json = r_poll1.json()
        _assert_openapi_schema(poll_json, "AnalysisPollEnvelope")
        assert poll_json["status"] == "pending"
        assert poll_json["poll_interval_ms"] == 2000

        # Cancel pending request -> immediate refund (quota_units=0 & Redis decremented)
        r_cancel = await client.post(
            f"/api/v1/analysis/requests/{req_pending_id}/cancel",
            headers=g_headers,
        )
        assert r_cancel.status_code == 200
        assert r_cancel.json() == {"request_id": req_pending_id, "status": "cancelled"}

        # Cancel again -> 409 CONFLICT
        r_cancel_again = await client.post(
            f"/api/v1/analysis/requests/{req_pending_id}/cancel",
            headers=g_headers,
        )
        assert r_cancel_again.status_code == 409

        # Verify guest quarters in DB + Redis reflect refund cleanly (8 instead of 12)!
        g_hash = hash_token(guest_token)
        assert await redis_client.get(f"guest_quota:{g_hash}:quarters") == b"8"

        # Verify cancelled poll response
        r_poll_cancelled = await client.get(
            f"/api/v1/analysis/requests/{req_pending_id}", headers=g_headers
        )
        assert r_poll_cancelled.status_code == 200
        assert "Retry-After" not in r_poll_cancelled.headers
        assert r_poll_cancelled.json()["poll_interval_ms"] is None
        _assert_openapi_schema(r_poll_cancelled.json(), "AnalysisPollEnvelope")

        # Populate live result on req_src_id AND replay result on req_replay_id (`IMPL-017`)
        src_aid = "analysis_aaa111bbb222"
        rep_aid = "analysis_ccc333ddd444"
        now = datetime.now(UTC)
        src_result = copy.deepcopy(fixture_result)
        src_result["request_id"] = req_src_id
        rep_result = copy.deepcopy(fixture_result)
        rep_result["request_id"] = req_replay_id

        async with sessionmaker() as db:
            src_req = await db.get(AnalysisRequest, req_src_id)
            rep_req = await db.get(AnalysisRequest, req_replay_id)
            assert src_req is not None and rep_req is not None
            src_req.status = "ok"
            src_req.sent_at = now - timedelta(minutes=2)
            src_req.received_at = now - timedelta(minutes=1)
            src_req.duration_ms = 1200

            db.add(
                AnalysisResult(
                    analysis_id=src_aid,
                    request_id=req_src_id,
                    status="ok",
                    dataset_version_used=DEFAULT_DATASET_VERSION,
                    ml_engine_version="agro-ml-2.1.0",
                    result_json=src_result,
                    validation_passed=True,
                    created_at=now - timedelta(minutes=1),
                )
            )
            await db.flush()

            rep_req.status = "ok"
            rep_req.received_at = None
            rep_req.error_code = f"last_good_replay:{src_aid}"
            rep_req.duration_ms = 5
            db.add(
                AnalysisResult(
                    analysis_id=rep_aid,
                    request_id=req_replay_id,
                    status="ok",
                    dataset_version_used=DEFAULT_DATASET_VERSION,
                    ml_engine_version="agro-ml-2.1.0",
                    result_json=rep_result,
                    validation_passed=True,
                    created_at=now,
                )
            )
            await db.commit()

        # PATCH selection on `src_aid` -> does NOT mutate stored `result_json`, DOES merge on read!
        r_sel1 = await client.patch(
            f"/api/v1/analysis/{src_aid}/selection",
            headers=g_headers,
            json={
                "field_id": "F1",
                "strategy_id": "S2_water_resilient",
                "selection_status": "selected",
            },
        )
        assert r_sel1.status_code == 200
        assert r_sel1.json()["selection_status"] == "selected"

        # Switch selected to S3_income_diversified -> S2 automatically reverts to "suggested"
        r_sel2 = await client.patch(
            f"/api/v1/analysis/{src_aid}/selection",
            headers=g_headers,
            json={
                "field_id": "F1",
                "strategy_id": "S3_income_diversified",
                "selection_status": "selected",
            },
        )
        assert r_sel2.status_code == 200

        # Invalid field/strategy -> 400 INVALID_INPUT
        r_bad_sel = await client.patch(
            f"/api/v1/analysis/{src_aid}/selection",
            headers=g_headers,
            json={
                "field_id": "F1",
                "strategy_id": "S_DOES_NOT_EXIST",
                "selection_status": "rejected",
            },
        )
        assert r_bad_sel.status_code == 400

        # Read permalink `GET /analysis/{analysis_id}` -> merged selections & immutable PG row
        r_get_src = await client.get(f"/api/v1/analysis/{src_aid}", headers=g_headers)
        assert r_get_src.status_code == 200
        env_src = r_get_src.json()
        _assert_openapi_schema(env_src, "AnalysisEnvelope")
        assert env_src["degraded_mode"] is None
        strats = {s["strategy_id"]: s for s in env_src["result"]["field_plans"][0]["strategies"]}
        assert all(
            s["selection_status"] == "suggested" for s in strats["S2_water_resilient"]["seasons"]
        )
        assert all(
            s["selection_status"] == "selected"
            for s in strats["S3_income_diversified"]["seasons"]
        )

        # Replay poll + replay permalink BOTH reconstruct degraded_mode (`IMPL-017`)
        r_get_rep = await client.get(f"/api/v1/analysis/{rep_aid}", headers=g_headers)
        assert r_get_rep.status_code == 200
        env_rep = r_get_rep.json()
        _assert_openapi_schema(env_rep, "AnalysisEnvelope")
        assert env_rep["degraded_mode"]["kind"] == "last_good_replay"
        assert env_rep["degraded_mode"]["stale"] is True
        assert env_rep["degraded_mode"]["source_analysis_id"] == src_aid
        assert env_rep["degraded_mode"]["age_seconds"] >= 50
        # Isolation: S3 selection on src_aid does NOT leak onto rep_aid!
        rep_s3 = next(
            s
            for s in env_rep["result"]["field_plans"][0]["strategies"]
            if s["strategy_id"] == "S3_income_diversified"
        )
        assert all(s["selection_status"] == "suggested" for s in rep_s3["seasons"])

        r_poll_rep = await client.get(
            f"/api/v1/analysis/requests/{req_replay_id}", headers=g_headers
        )
        assert r_poll_rep.status_code == 200
        _assert_openapi_schema(r_poll_rep.json(), "AnalysisPollEnvelope")
        assert r_poll_rep.json()["degraded_mode"]["source_analysis_id"] == src_aid

        # List farm analyses with pagination & ?status=ok
        r_hist_p1 = await client.get(
            f"/api/v1/farms/{g_farm}/analyses?limit=2", headers=g_headers
        )
        assert r_hist_p1.status_code == 200
        p1_json = r_hist_p1.json()
        _assert_openapi_schema(p1_json, "FarmAnalysesPage")
        assert len(p1_json["items"]) == 2 and p1_json["has_more"] is True
        r_hist_p2 = await client.get(
            f"/api/v1/farms/{g_farm}/analyses?limit=2&cursor={p1_json['next_cursor']}",
            headers=g_headers,
        )
        assert r_hist_p2.status_code == 200 and len(r_hist_p2.json()["items"]) == 1

        r_hist_ok = await client.get(
            f"/api/v1/farms/{g_farm}/analyses?status=ok", headers=g_headers
        )
        assert r_hist_ok.status_code == 200 and len(r_hist_ok.json()["items"]) == 2

        # Claim guest session (`POST /auth/claim-guest`), verify `GET /auth/me/export`
        user_token = await _register_user(client, "claimed@example.com")
        u_headers = {"Authorization": f"Bearer {user_token}", "X-Forwarded-For": "198.51.100.72"}
        r_claim = await client.post(
            "/api/v1/auth/claim-guest",
            headers={**u_headers, "X-Guest-Token": guest_token},
        )
        assert r_claim.status_code == 200
        assert r_claim.json()["claimed_farms_count"] == 1
        assert await redis_client.get(f"guest_quota:{g_hash}:quarters") is None

        r_export = await client.get("/api/v1/auth/me/export", headers=u_headers)
        assert r_export.status_code == 200
        exp_json = r_export.json()
        _assert_openapi_schema(exp_json, "UserDataExport")
        assert len(exp_json["analysis_requests"]) == 3
        assert len(exp_json["analysis_results"]) == 2
        assert len(exp_json["analysis_selections"]) == 1
        assert all("input_snapshot_gz" not in item for item in exp_json["analysis_requests"])

        # Prove 120 req/min poll bucket is independent of CRUD limit (RATE_LIMIT_CRUD_PER_MIN=20)
        # Clear existing poll counter first; all 120 succeed -> then 429 (tolerant of :00 rollover).
        async for rk in redis_client.scan_iter(match="rl:poll:*"):
            await redis_client.delete(rk)
        for _ in range(120):
            ok_poll = await client.get(
                f"/api/v1/analysis/requests/{req_replay_id}", headers=u_headers
            )
            assert ok_poll.status_code == 200
        throttled_poll: httpx.Response | None = None
        for _ in range(10):
            cand = await client.get(
                f"/api/v1/analysis/requests/{req_replay_id}", headers=u_headers
            )
            if cand.status_code == 429:
                throttled_poll = cand
                break
            assert cand.status_code == 200
        assert throttled_poll is not None
        assert throttled_poll.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert int(throttled_poll.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_sync_wait_mode_completion_error_translation_and_timeout(
    m7_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _, engine, sessionmaker, redis_client = m7_ctx
    settings = _m7_settings(ALLOW_SYNC_WAIT=True, SYNC_WAIT_TIMEOUT_SECONDS=1)
    await _seed_catalog(sessionmaker)
    app = _make_bound_app(settings, engine, sessionmaker, redis_client)
    fixture_result = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        token = await _register_user(client, "waiter@example.com")
        headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": "198.51.100.80"}
        farm_id = await _create_farm(client, headers)
        await _create_field(client, headers, farm_id, field_id="F1")

        # 1. Timeout -> 504 JOB_TIMEOUT when nobody completes the pending job within 1s
        r_timeout = await client.post(
            "/api/v1/analysis?wait=true",
            headers=headers,
            json=_analysis_payload(farm_id),
        )
        assert r_timeout.status_code == 504
        assert r_timeout.json()["error"]["code"] == "JOB_TIMEOUT"

        # Helper completing ONLY a newly inserted pending job after short async delay
        async def _complete_new_pending(
            *,
            exclude_ids: set[str],
            target_status: str,
            err_code: str | None = None,
        ) -> str:
            while True:
                await asyncio.sleep(0.05)
                async with sessionmaker() as db:
                    stmt = select(AnalysisRequest).where(AnalysisRequest.status == "pending")
                    if exclude_ids:
                        stmt = stmt.where(AnalysisRequest.request_id.notin_(exclude_ids))
                    row = (
                        await db.execute(
                            stmt.order_by(AnalysisRequest.created_at.desc()).limit(1)
                        )
                    ).scalar_one_or_none()
                    if row is None:
                        continue
                    if target_status == "ok":
                        aid = f"analysis_{uuid.uuid4().hex[:12]}"
                        res_copy = copy.deepcopy(fixture_result)
                        res_copy["request_id"] = row.request_id
                        row.status = "ok"
                        row.received_at = datetime.now(UTC)
                        db.add(
                            AnalysisResult(
                                analysis_id=aid,
                                request_id=row.request_id,
                                status="ok",
                                dataset_version_used=DEFAULT_DATASET_VERSION,
                                ml_engine_version="agro-ml-2.1.0",
                                result_json=res_copy,
                                validation_passed=True,
                            )
                        )
                    else:
                        row.status = "failed"
                        row.error_code = err_code
                    rid = row.request_id
                    await db.commit()
                    return rid

        async def _all_request_ids() -> set[str]:
            async with sessionmaker() as db:
                rows = (await db.execute(select(AnalysisRequest.request_id))).scalars().all()
                return set(rows)

        # 2. Completion -> 200 AnalysisEnvelope
        known_ids = await _all_request_ids()
        task_ok = asyncio.create_task(
            _complete_new_pending(exclude_ids=known_ids, target_status="ok")
        )
        r_ok = await client.post(
            "/api/v1/analysis?wait=true",
            headers=headers,
            json=_analysis_payload(farm_id),
        )
        await task_ok
        assert r_ok.status_code == 200
        _assert_openapi_schema(r_ok.json(), "AnalysisEnvelope")

        # 3. Error translation (`IMPL-020` §3): INSUFFICIENT_DATA -> 422, ML_TIMEOUT -> 504
        for err_code_val, expected_http in (
            ("INSUFFICIENT_DATA", 422),
            ("ML_TIMEOUT", 504),
            ("INTERNAL_ERROR", 500),
            ("DATASET_VERSION_UNAVAILABLE", 502),
        ):
            known_ids = await _all_request_ids()
            t_err = asyncio.create_task(
                _complete_new_pending(
                    exclude_ids=known_ids,
                    target_status="failed",
                    err_code=err_code_val,
                )
            )
            r_err = await client.post(
                "/api/v1/analysis?wait=true",
                headers=headers,
                json=_analysis_payload(farm_id),
            )
            await t_err
            assert r_err.status_code == expected_http
            assert r_err.json()["error"]["code"] == err_code_val
