"""Real PostGIS + Redis integration & OpenAPI conformance tests for M5 Farms & Fields."""

from __future__ import annotations

import json
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
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from referencing.typing import URI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.pagination import encode_cursor
from app.db.seed import GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.models import Farm, Field, FieldCropHistory
from app.schemas.common import (
    DEMO_PARCEL_UNVERIFIED_MESSAGE,
    MVP_OUTSIDE_COVERAGE_MESSAGE,
    WarningCode,
)
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)
_OPENAPI_DOC: dict[str, Any] = yaml.safe_load(
    (BACKEND_DIR / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
_SCHEMA_DOC: dict[str, Any] = json.loads(
    (BACKEND_DIR / "contracts" / "schema-v5.0.json").read_text(encoding="utf-8")
)

_GUELMA_POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [
            [7.41, 36.45],
            [7.45, 36.45],
            [7.45, 36.49],
            [7.41, 36.49],
            [7.41, 36.45],
        ]
    ],
}


def _assert_openapi_ref(payload: Any, pointer: str) -> None:
    """Validate HTTP JSON response payload strictly against a pointer in `openapi.yaml`."""
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
        {"$ref": f"{openapi_uri}{pointer}"},
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, f"OpenAPI pointer {pointer} mismatch: {[e.message for e in errors]}"


def _assert_openapi_schema(payload: Any, schema_name: str) -> None:
    """Validate HTTP JSON response payload strictly against `components/schemas/<name>`."""
    _assert_openapi_ref(payload, f"#/components/schemas/{schema_name}")


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _m5_settings() -> Settings:
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
        GUEST_BURST_PER_MIN=100,
        RATE_LIMIT_CRUD_PER_MIN=200,
    )


def _sample_field_payload(
    *,
    field_id: str = "F1",
    field_name: str = "North Parcel",
    latitude: float = 36.47,
    longitude: float = 7.43,
    boundary: dict[str, Any] | None = None,
    is_unverified_demo_parcel: bool = False,
    soil_type: str = "loamy",
    soil_ph: float | None = 7.1,
    organic_matter_percent: float | None = 1.8,
    soil_test_date: str | None = "2026-09-10",
    water_availability: str = "moderate",
    water_source: str = "well",
    water_source_other: str | None = None,
    crop_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "field_name": field_name,
        "is_unverified_demo_parcel": is_unverified_demo_parcel,
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "boundary": boundary,
        },
        "area_hectares": 12.5,
        "elevation_m": 280.0,
        "soil": {
            "soil_type": soil_type,
            "soil_ph": soil_ph,
            "organic_matter_percent": organic_matter_percent,
            "soil_test_date": soil_test_date,
        },
        "water": {
            "availability": water_availability,
            "source": water_source,
            "source_other": water_source_other,
            "irrigation_system": "drip",
        },
        "crop_history": crop_history
        or [
            {
                "season": "autumn",
                "year": 2025,
                "planting_month": 11,
                "crop_id": "durum_wheat",
                "crop_name_raw": "Durum Wheat",
                "yield_tons_per_hectare": 3.4,
                "notes": None,
            }
        ],
    }


async def _cleanup_test_rows(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
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
async def m5_ctx(
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
    settings = _m5_settings()
    engine = create_db_engine(settings, role="api")
    sessionmaker = create_sessionmaker(engine)
    redis_client = redis_async.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    await redis_client.flushdb()
    await _cleanup_test_rows(sessionmaker)

    try:
        yield settings, engine, sessionmaker, redis_client
    finally:
        await _cleanup_test_rows(sessionmaker)
        await redis_client.flushdb()
        await redis_client.aclose()
        await engine.dispose()


async def _start_guest(client: httpx.AsyncClient, ip: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert resp.status_code == 201
    token = str(resp.json()["guest_token"])
    return {"X-Guest-Token": token}


async def _register_user(
    client: httpx.AsyncClient,
    *,
    email: str,
    full_name: str = "Farmer User",
) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "full_name": full_name,
            "preferred_lang": "en",
        },
    )
    assert resp.status_code == 201
    access_token = str(resp.json()["access_token"])
    return {"Authorization": f"Bearer {access_token}"}


async def test_farms_crud_pagination_filters_like_escape_and_owner_isolation(
    m5_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, _sessionmaker, _redis_client = m5_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        user_a = await _register_user(client, email="owner_a@example.com")
        user_b = await _register_user(client, email="owner_b@example.com")
        guest_a = await _start_guest(client, "10.0.1.1")

        # Create 4 farms under user_a (including literal %/_ for LIKE escape testing)
        created_ids: list[str] = []
        farm_specs = [
            ("Alpha Farm", "Algeria", "Guelma", "Bouchegouf"),
            ("Beta%Farm", "Algeria", "Guelma", "Hammam_Debagh"),
            ("Gamma Valley", "Algeria", "Setif", "El Eulma"),
            ("Delta Plain", "Tunisia", "Beja", None),
        ]
        for farm_name, country, region, commune in farm_specs:
            res = await client.post(
                "/api/v1/farms",
                headers=user_a,
                json={
                    "farm_name": farm_name,
                    "country": country,
                    "region": region,
                    "commune": commune,
                },
            )
            assert res.status_code == 201
            payload = res.json()
            _assert_openapi_schema(payload, "FarmPublic")
            assert payload["field_count"] == 0
            assert payload["farm_id"].startswith("farm_")
            created_ids.append(payload["farm_id"])

        # Keyset pagination limit=2
        page1 = await client.get("/api/v1/farms", headers=user_a, params={"limit": 2})
        assert page1.status_code == 200
        p1 = page1.json()
        _assert_openapi_schema(p1, "FarmPage")
        assert p1["has_more"] is True
        assert [item["farm_id"] for item in p1["items"]] == created_ids[:2]

        page2 = await client.get(
            "/api/v1/farms",
            headers=user_a,
            params={"limit": 2, "cursor": p1["next_cursor"]},
        )
        assert page2.status_code == 200
        p2 = page2.json()
        _assert_openapi_schema(p2, "FarmPage")
        assert p2["has_more"] is False
        assert p2["next_cursor"] is None
        assert [item["farm_id"] for item in p2["items"]] == created_ids[2:]

        # Bad cursors return 400 INVALID_INPUT
        for bad_cursor in ("not-base64!", encode_cursor({"wrong": 1}), encode_cursor({"id": 0})):
            bad_res = await client.get(
                "/api/v1/farms",
                headers=user_a,
                params={"cursor": bad_cursor},
            )
            assert bad_res.status_code == 400
            assert bad_res.json()["error"]["code"] == "INVALID_INPUT"

        # Case-insensitive country & region filters
        filtered_region = await client.get(
            "/api/v1/farms",
            headers=user_a,
            params={"country": "algeria", "region": "guelma"},
        )
        assert filtered_region.status_code == 200
        assert [i["farm_name"] for i in filtered_region.json()["items"]] == [
            "Alpha Farm",
            "Beta%Farm",
        ]

        # SQL LIKE wildcard characters `%` and `_` are escaped literally
        like_pct = await client.get("/api/v1/farms", headers=user_a, params={"search": "%Farm"})
        assert like_pct.status_code == 200
        assert [i["farm_name"] for i in like_pct.json()["items"]] == ["Beta%Farm"]

        like_under = await client.get("/api/v1/farms", headers=user_a, params={"search": "Hammam_"})
        assert like_under.status_code == 200
        assert [i["farm_name"] for i in like_under.json()["items"]] == ["Beta%Farm"]

        # GET / PUT / PATCH / DELETE own farm + Pitfall #14 farm_id validation
        target_id = created_ids[0]
        get_ok = await client.get(f"/api/v1/farms/{target_id}", headers=user_a)
        assert get_ok.status_code == 200
        _assert_openapi_schema(get_ok.json(), "FarmPublic")

        put_ok = await client.put(
            f"/api/v1/farms/{target_id}",
            headers=user_a,
            json={
                "farm_name": "Alpha\x00 Replaced",
                "country": "Algeria",
                "region": "Guelma",
                "commune": None,
            },
        )
        assert put_ok.status_code == 200
        assert put_ok.json()["farm_name"] == "Alpha Replaced"
        assert put_ok.json()["commune"] is None

        # Blank or control-character-only text fails minLength=1 -> 400 INVALID_INPUT
        ctrl_only = await client.patch(
            f"/api/v1/farms/{target_id}",
            headers=user_a,
            json={"farm_name": "\x00   \x07"},
        )
        assert ctrl_only.status_code == 400
        assert ctrl_only.json()["error"]["code"] == "INVALID_INPUT"

        patch_ok = await client.patch(
            f"/api/v1/farms/{target_id}",
            headers=user_a,
            json={"commune": "Oued Zenati"},
        )
        assert patch_ok.status_code == 200
        assert patch_ok.json()["commune"] == "Oued Zenati"

        patch_clear = await client.patch(
            f"/api/v1/farms/{target_id}",
            headers=user_a,
            json={"commune": None},
        )
        assert patch_clear.status_code == 200
        assert patch_clear.json()["commune"] is None

        # Explicit null on non-nullable PATCH property -> 400 INVALID_INPUT
        bad_patch = await client.patch(
            f"/api/v1/farms/{target_id}",
            headers=user_a,
            json={"farm_name": None},
        )
        assert bad_patch.status_code == 400
        assert bad_patch.json()["error"]["code"] == "INVALID_INPUT"

        # Invalid farm_id path formats -> 400; out-of-range int64 / zero -> 404 (never 500)
        for bad_id in ("1", "farm_abc", "farm_-1"):
            r = await client.get(f"/api/v1/farms/{bad_id}", headers=user_a)
            assert r.status_code == 400
            assert r.json()["error"]["code"] == "INVALID_INPUT"

        for missing_id in ("farm_0", "farm_999999", "farm_99999999999999999999999999"):
            r = await client.get(f"/api/v1/farms/{missing_id}", headers=user_a)
            assert r.status_code == 404
            assert r.json()["error"]["code"] == "NOT_FOUND"

        # Cross-owner access ALWAYS returns 404 NOT_FOUND (never 403)
        for foreign_headers in (user_b, guest_a):
            for method, path, body in (
                ("GET", f"/api/v1/farms/{target_id}", None),
                (
                    "PUT",
                    f"/api/v1/farms/{target_id}",
                    {"farm_name": "Hacked", "country": "DZ", "region": "Guelma"},
                ),
                ("PATCH", f"/api/v1/farms/{target_id}", {"farm_name": "Hacked"}),
                ("DELETE", f"/api/v1/farms/{target_id}", None),
            ):
                resp = await client.request(method, path, headers=foreign_headers, json=body)
                assert resp.status_code == 404
                _assert_openapi_schema(resp.json(), "ErrorEnvelope")
                assert resp.json()["error"]["code"] == "NOT_FOUND"

        # Delete farm -> 204 then 404
        del_res = await client.delete(f"/api/v1/farms/{target_id}", headers=user_a)
        assert del_res.status_code == 204
        assert del_res.content == b""
        after_del = await client.get(f"/api/v1/farms/{target_id}", headers=user_a)
        assert after_del.status_code == 404


async def test_fields_crud_postgis_gate_notices_soil_water_and_crop_history(
    m5_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, _sessionmaker, _redis_client = m5_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        reg_headers = await _register_user(client, email="fields_reg@example.com")
        other_headers = await _register_user(client, email="fields_other@example.com")
        guest_headers = await _start_guest(client, "10.0.2.1")

        reg_farm_resp = await client.post(
            "/api/v1/farms",
            headers=reg_headers,
            json={"farm_name": "Reg Farm", "country": "Algeria", "region": "Guelma"},
        )
        reg_farm_id = reg_farm_resp.json()["farm_id"]

        guest_farm_resp = await client.post(
            "/api/v1/farms",
            headers=guest_headers,
            json={"farm_name": "Guest Farm", "country": "Algeria", "region": "Guelma"},
        )
        guest_farm_id = guest_farm_resp.json()["farm_id"]

        # 1) Guest inside Guelma with polygon + DEMO_PARCEL_UNVERIFIED -> 201
        g_ok = await client.post(
            f"/api/v1/farms/{guest_farm_id}/fields",
            headers=guest_headers,
            json=_sample_field_payload(
                field_id="G1",
                boundary=_GUELMA_POLYGON,
                is_unverified_demo_parcel=True,
                soil_type="unknown",
                soil_ph=None,
                organic_matter_percent=None,
                soil_test_date=None,
            ),
        )
        assert g_ok.status_code == 201
        g_data = g_ok.json()
        _assert_openapi_schema(g_data, "FieldPublic")
        assert g_data["soil"]["source"] == "unknown"
        assert g_data["location"]["boundary"] == _GUELMA_POLYGON
        assert g_data["warnings"] == [
            {
                "code": WarningCode.DEMO_PARCEL_UNVERIFIED.value,
                "message": DEMO_PARCEL_UNVERIFIED_MESSAGE,
            }
        ]

        # 2) Guest outside Guelma (Setif 36.19, 5.41) -> 422 OUTSIDE_DEMO_BOUNDARY
        g_out = await client.post(
            f"/api/v1/farms/{guest_farm_id}/fields",
            headers=guest_headers,
            json=_sample_field_payload(field_id="G_OUT", latitude=36.19, longitude=5.41),
        )
        assert g_out.status_code == 422
        _assert_openapi_schema(g_out.json(), "ErrorEnvelope")
        assert g_out.json()["error"]["code"] == "OUTSIDE_DEMO_BOUNDARY"

        # 3) Guest PATCH/PUT moving G1 outside Guelma -> 422 OUTSIDE_DEMO_BOUNDARY
        g_move = await client.patch(
            f"/api/v1/farms/{guest_farm_id}/fields/G1",
            headers=guest_headers,
            json={"location": {"latitude": 36.19, "longitude": 5.41}},
        )
        assert g_move.status_code == 422
        assert g_move.json()["error"]["code"] == "OUTSIDE_DEMO_BOUNDARY"

        # 4) Registered outside Guelma: soil_type='unknown' + lab metric -> 'farmer' + notice
        r_out = await client.post(
            f"/api/v1/farms/{reg_farm_id}/fields",
            headers=reg_headers,
            json=_sample_field_payload(
                field_id="R1",
                latitude=36.19,
                longitude=5.41,
                is_unverified_demo_parcel=True,
                soil_type="unknown",
                soil_ph=6.8,
                organic_matter_percent=None,
                soil_test_date=None,
                water_source="other",
                water_source_other="Community Canal",
            ),
        )
        assert r_out.status_code == 201
        r1 = r_out.json()
        _assert_openapi_schema(r1, "FieldPublic")
        assert r1["soil"]["source"] == "farmer"
        assert r1["water"]["source_other"] == "Community Canal"
        assert {w["code"] for w in r1["warnings"]} == {
            WarningCode.DEMO_PARCEL_UNVERIFIED.value,
            WarningCode.MVP_OUTSIDE_COVERAGE.value,
        }
        for w in r1["warnings"]:
            if w["code"] == WarningCode.MVP_OUTSIDE_COVERAGE.value:
                assert w["message"] == MVP_OUTSIDE_COVERAGE_MESSAGE

        # Duplicate field_id in same farm -> 409 CONFLICT
        dup_id = await client.post(
            f"/api/v1/farms/{reg_farm_id}/fields",
            headers=reg_headers,
            json=_sample_field_payload(field_id="R1"),
        )
        assert dup_id.status_code == 409
        _assert_openapi_schema(dup_id.json(), "ErrorEnvelope")
        assert dup_id.json()["error"]["code"] == "CONFLICT"

        # Add second & third field for filter and cursor pagination tests
        for fid, soil, water_av in (("R2", "clay", "limited"), ("R3", "clay", "abundant")):
            res = await client.post(
                f"/api/v1/farms/{reg_farm_id}/fields",
                headers=reg_headers,
                json=_sample_field_payload(
                    field_id=fid,
                    soil_type=soil,
                    water_availability=water_av,
                ),
            )
            assert res.status_code == 201

        # Verify FarmPublic.field_count == 3
        farm_chk = await client.get(f"/api/v1/farms/{reg_farm_id}", headers=reg_headers)
        assert farm_chk.status_code == 200
        assert farm_chk.json()["field_count"] == 3

        # List fields with filter & cursor pagination
        f_list = await client.get(
            f"/api/v1/farms/{reg_farm_id}/fields",
            headers=reg_headers,
            params={"limit": 1, "soil_type": "clay"},
        )
        assert f_list.status_code == 200
        fl1 = f_list.json()
        _assert_openapi_schema(fl1, "FieldPage")
        assert [i["field_id"] for i in fl1["items"]] == ["R2"]
        assert fl1["has_more"] is True

        f_list2 = await client.get(
            f"/api/v1/farms/{reg_farm_id}/fields",
            headers=reg_headers,
            params={"limit": 5, "soil_type": "clay", "cursor": fl1["next_cursor"]},
        )
        assert f_list2.status_code == 200
        assert [i["field_id"] for i in f_list2.json()["items"]] == ["R3"]
        assert f_list2.json()["has_more"] is False

        f_water = await client.get(
            f"/api/v1/farms/{reg_farm_id}/fields",
            headers=reg_headers,
            params={"water_availability": "limited"},
        )
        assert [i["field_id"] for i in f_water.json()["items"]] == ["R2"]

        # GET /fields/R1 -> FieldDetailPublic
        detail_res = await client.get(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
        )
        assert detail_res.status_code == 200
        _assert_openapi_schema(detail_res.json(), "FieldDetailPublic")
        assert len(detail_res.json()["crop_history"]) == 1

        # PATCH partial rules:
        # (a) clearing soil_ph -> recomputes soil.source == "unknown"
        # (b) switching water.source="well" -> clears water.source_other=None
        # (c) atomic crop_history replace sorted deterministically
        patch_res = await client.patch(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json={
                "soil": {"soil_ph": None},
                "water": {"source": "well", "source_other": "Ignored value"},
                "crop_history": [
                    {
                        "season": "spring",
                        "year": 2024,
                        "planting_month": 3,
                        "crop_id": "chickpea",
                        "crop_name_raw": "Chickpea",
                        "yield_tons_per_hectare": 1.6,
                        "notes": "rainfed",
                    },
                    {
                        "season": "winter",
                        "year": 2025,
                        "planting_month": 1,
                        "crop_id": None,
                        "crop_name_raw": "Fava Bean",
                        "yield_tons_per_hectare": None,
                        "notes": None,
                    },
                ],
            },
        )
        assert patch_res.status_code == 200
        pd = patch_res.json()
        _assert_openapi_schema(pd, "FieldDetailPublic")
        assert pd["soil"]["source"] == "unknown"
        assert pd["soil"]["soil_ph"] is None
        assert pd["water"]["source"] == "well"
        assert pd["water"]["source_other"] is None
        assert [(c["year"], c["season"]) for c in pd["crop_history"]] == [
            (2025, "winter"),
            (2024, "spring"),
        ]

        # Duplicate (year, season) in PATCH -> 409 CONFLICT
        dup_hist = await client.patch(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json={
                "crop_history": [
                    {"season": "autumn", "year": 2025, "crop_id": "barley"},
                    {"season": "autumn", "year": 2025, "crop_id": "chickpea"},
                ]
            },
        )
        assert dup_hist.status_code == 409
        assert dup_hist.json()["error"]["code"] == "CONFLICT"

        # Strict FieldPatchRequest subfield & GeoJSON validation -> 400 INVALID_INPUT
        for bad_patch in (
            {"soil": {"soil_ph": 12.5}},
            {"soil": {"soil_type": None}},
            {"water": {"availability": "infinite"}},
            {"water": {"unknown_key": "x"}},
            {"location": {"latitude": 95.0}},
            {"location": {"boundary": {"type": "Point", "coordinates": [7.4, 36.4]}}},
            {
                "location": {
                    "boundary": {
                        "type": "Polygon",
                        "coordinates": [[[7.4, 36.4], [7.5, 36.4], [7.5, 36.5], [7.45, 36.5]]],
                    }
                }
            },
            {"area_hectares": 0.00001},
        ):
            r = await client.patch(
                f"/api/v1/farms/{reg_farm_id}/fields/R1",
                headers=reg_headers,
                json=bad_patch,
            )
            assert r.status_code == 400
            _assert_openapi_schema(r.json(), "ErrorEnvelope")
            assert r.json()["error"]["code"] == "INVALID_INPUT"

        # PATCH partial location preserves boundary then clears it on explicit null
        patch_poly = await client.patch(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json={"location": {"boundary": _GUELMA_POLYGON}},
        )
        assert patch_poly.status_code == 200
        assert patch_poly.json()["location"]["boundary"] == _GUELMA_POLYGON

        patch_lat_only = await client.patch(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json={"location": {"latitude": 36.48}},
        )
        assert patch_lat_only.status_code == 200
        assert patch_lat_only.json()["location"]["latitude"] == pytest.approx(36.48)
        assert patch_lat_only.json()["location"]["longitude"] == pytest.approx(5.41)
        assert patch_lat_only.json()["location"]["boundary"] == _GUELMA_POLYGON

        patch_clear_poly = await client.patch(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json={"location": {"boundary": None}},
        )
        assert patch_clear_poly.status_code == 200
        assert patch_clear_poly.json()["location"]["boundary"] is None

        # PUT full replacement & path/body field_id mismatch check
        put_mismatch = await client.put(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json=_sample_field_payload(field_id="WRONG_ID"),
        )
        assert put_mismatch.status_code == 400
        assert put_mismatch.json()["error"]["code"] == "INVALID_INPUT"

        put_ok = await client.put(
            f"/api/v1/farms/{reg_farm_id}/fields/R1",
            headers=reg_headers,
            json=_sample_field_payload(
                field_id="R1",
                field_name="Guelma Repositioned",
                latitude=36.47,
                longitude=7.43,
                boundary=_GUELMA_POLYGON,
                is_unverified_demo_parcel=False,
                soil_type="sandy",
            ),
        )
        assert put_ok.status_code == 200
        put_json = put_ok.json()
        _assert_openapi_schema(put_json, "FieldDetailPublic")
        assert put_json["field_name"] == "Guelma Repositioned"
        assert put_json["warnings"] == []
        assert put_json["soil"]["source"] == "farmer"

        # Foreign user gets 404 on every field endpoint (never 403)
        for method, path, body in (
            ("GET", f"/api/v1/farms/{reg_farm_id}/fields", None),
            ("POST", f"/api/v1/farms/{reg_farm_id}/fields", _sample_field_payload(field_id="X1")),
            ("GET", f"/api/v1/farms/{reg_farm_id}/fields/R1", None),
            ("PUT", f"/api/v1/farms/{reg_farm_id}/fields/R1", _sample_field_payload(field_id="R1")),
            ("PATCH", f"/api/v1/farms/{reg_farm_id}/fields/R1", {"field_name": "Hack"}),
            ("DELETE", f"/api/v1/farms/{reg_farm_id}/fields/R1", None),
        ):
            r = await client.request(method, path, headers=other_headers, json=body)
            assert r.status_code == 404
            assert r.json()["error"]["code"] == "NOT_FOUND"

        # DELETE field -> 204, updates farm field_count, returns 404 thereafter
        del_f = await client.delete(
            f"/api/v1/farms/{reg_farm_id}/fields/R3",
            headers=reg_headers,
        )
        assert del_f.status_code == 204
        gone_f = await client.get(
            f"/api/v1/farms/{reg_farm_id}/fields/R3",
            headers=reg_headers,
        )
        assert gone_f.status_code == 404
        farm_after_del = await client.get(f"/api/v1/farms/{reg_farm_id}", headers=reg_headers)
        assert farm_after_del.json()["field_count"] == 2


async def test_guest_quotas_export_and_claim_guest_end_to_end_with_m5_routes(
    m5_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    """Verify sequential guest limits (3 farms / 5 fields) + M3 E4 claim-guest/export HTTP flow."""
    settings, _engine, sessionmaker, _redis_client = m5_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        guest_headers = await _start_guest(client, "10.0.3.1")

        # 3 farms allowed for guest, 4th blocked with 403 GUEST_LIMIT_REACHED
        guest_farm_ids: list[str] = []
        for idx in range(settings.GUEST_MAX_FARMS):
            res = await client.post(
                "/api/v1/farms",
                headers=guest_headers,
                json={"farm_name": f"Guest Farm {idx}", "country": "Algeria", "region": "Guelma"},
            )
            assert res.status_code == 201
            guest_farm_ids.append(res.json()["farm_id"])

        fourth_farm = await client.post(
            "/api/v1/farms",
            headers=guest_headers,
            json={"farm_name": "Guest Farm 4", "country": "Algeria", "region": "Guelma"},
        )
        assert fourth_farm.status_code == 403
        _assert_openapi_schema(fourth_farm.json(), "ErrorEnvelope")
        assert fourth_farm.json()["error"]["code"] == "GUEST_LIMIT_REACHED"

        # 5 fields allowed per guest farm, 6th blocked with 403 GUEST_LIMIT_REACHED
        primary_farm_id = guest_farm_ids[0]
        for idx in range(settings.GUEST_MAX_FIELDS_PER_FARM):
            res = await client.post(
                f"/api/v1/farms/{primary_farm_id}/fields",
                headers=guest_headers,
                json=_sample_field_payload(
                    field_id=f"GF_{idx}",
                    boundary=_GUELMA_POLYGON if idx == 0 else None,
                    is_unverified_demo_parcel=(idx == 0),
                ),
            )
            assert res.status_code == 201

        sixth_field = await client.post(
            f"/api/v1/farms/{primary_farm_id}/fields",
            headers=guest_headers,
            json=_sample_field_payload(field_id="GF_EXTRA"),
        )
        assert sixth_field.status_code == 403
        assert sixth_field.json()["error"]["code"] == "GUEST_LIMIT_REACHED"

        # GET /api/v1/demo/session reflects exact PostgreSQL counts (3 farms, 5 fields)
        sess_res = await client.get("/api/v1/demo/session", headers=guest_headers)
        assert sess_res.status_code == 200
        assert sess_res.json()["usage"]["farms"] == 3
        assert sess_res.json()["usage"]["fields"] == 5

        # Register account, claim guest workspace, verify ownership + GET /auth/me/export
        user_headers = await _register_user(client, email="claimer_m5@example.com")
        claim_res = await client.post(
            "/api/v1/auth/claim-guest",
            headers={**user_headers, **guest_headers},
        )
        assert claim_res.status_code == 200
        _assert_openapi_ref(
            claim_res.json(),
            "#/paths/~1auth~1claim-guest/post/responses/200/content/application~1json/schema",
        )
        assert claim_res.json()["claimed_farms_count"] == 3

        # Registered user can now add a 6th field & 4th farm (guest cap no longer applies!)
        post_claim_field = await client.post(
            f"/api/v1/farms/{primary_farm_id}/fields",
            headers=user_headers,
            json=_sample_field_payload(field_id="REG_6", latitude=36.19, longitude=5.41),
        )
        assert post_claim_field.status_code == 201
        assert post_claim_field.json()["warnings"][0]["code"] == "MVP_OUTSIDE_COVERAGE"

        export_res = await client.get("/api/v1/auth/me/export", headers=user_headers)
        assert export_res.status_code == 200
        export_json = export_res.json()
        _assert_openapi_schema(export_json, "UserDataExport")
        assert len(export_json["farms"]) == 3
        assert len(export_json["fields"]) == 6
        assert any(
            f["field_id"] == "GF_0" and f["location"]["boundary"] == _GUELMA_POLYGON
            for f in export_json["fields"]
        )

        # Verify cascading farm delete cleans fields and crop history in PostgreSQL
        del_res = await client.delete(f"/api/v1/farms/{primary_farm_id}", headers=user_headers)
        assert del_res.status_code == 204
        async with sessionmaker() as db:
            rem_farms = int((await db.execute(select(func.count(Farm.id)))).scalar_one())
            rem_fields = int((await db.execute(select(func.count(Field.id)))).scalar_one())
            rem_hist = int(
                (await db.execute(select(func.count(FieldCropHistory.id)))).scalar_one()
            )
        assert rem_farms == 2
        assert rem_fields == 0
        assert rem_hist == 0
