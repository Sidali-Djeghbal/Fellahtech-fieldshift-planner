"""Real PostGIS + Redis integration & OpenAPI conformance tests for M4 Demo & Spatial Gate."""

from __future__ import annotations

import os
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
import yaml
from geoalchemy2 import WKTElement
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Resource
from referencing.jsonschema import DRAFT202012
from referencing.typing import URI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.pagination import encode_cursor
from app.core.rate_limit import guest_quota_key, increment_guest_quarters
from app.core.security import hash_token
from app.db.seed import GUELMA_BOUNDARY_GEOJSON, GUELMA_LOCATION_ID
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
)
from app.schemas.common import MVP_OUTSIDE_COVERAGE_MESSAGE, WarningCode
from app.services import geo as geo_service
from tests.conftest import build_test_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)
_OPENAPI_DOC: dict[str, Any] = yaml.safe_load(
    (BACKEND_DIR / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)


def _assert_openapi_schema(payload: Any, schema_name: str) -> None:
    """Validate an HTTP JSON payload directly against `contracts/openapi.yaml` schema."""
    root_resource = Resource.from_contents(_OPENAPI_DOC, default_specification=DRAFT202012)
    from referencing import Registry

    base_uri: URI = "urn:fieldshift:openapi"
    registry = Registry().with_resource(base_uri, root_resource)
    validator = Draft202012Validator(
        {"$ref": f"{base_uri}#/components/schemas/{schema_name}"},
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, f"OpenAPI schema {schema_name} mismatch: {[e.message for e in errors]}"


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _demo_settings(
    *,
    guest_burst_per_min: int = 30,
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
        GUEST_SESSION_DAYS=7,
        GUEST_BURST_PER_MIN=guest_burst_per_min,
        ML_SERVICE_API_KEY=env["ML_SERVICE_API_KEY"],
    )


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
        await db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('public.demo_locations', 'id'), "
                "COALESCE((SELECT MAX(id) FROM public.demo_locations), 1), true)"
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
async def demo_ctx(
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
    settings = _demo_settings()
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


async def test_list_demo_locations_pagination_filters_active_and_validates_cursor(
    demo_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = demo_ctx

    async with sessionmaker() as db:
        await db.execute(
            text(
                "INSERT INTO public.demo_locations (code, name, country, region, boundary, "
                "is_active) VALUES "
                "('skikda', 'Skikda', 'Algeria', 'Skikda', "
                "ST_SetSRID(ST_GeomFromText('MULTIPOLYGON(((6.7 36.7, 7.1 36.7, 7.1 37.0, "
                "6.7 37.0, 6.7 36.7)))'), 4326), true), "
                "('annaba_off', 'Annaba Off', 'Algeria', 'Annaba', "
                "ST_SetSRID(ST_GeomFromText('MULTIPOLYGON(((7.6 36.8, 7.9 36.8, 7.9 37.0, "
                "7.6 37.0, 7.6 36.8)))'), 4326), false)"
            )
        )
        await db.commit()

    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            page1_resp = await client.get("/api/v1/demo/locations?limit=1")
            assert page1_resp.status_code == 200
            page1 = page1_resp.json()
            _assert_openapi_schema(page1, "DemoLocationPage")
            assert "locations" not in page1
            assert len(page1["items"]) == 1
            assert page1["items"][0]["code"] == "guelma"
            assert "default_parcel_id" not in page1["items"][0]
            assert page1["has_more"] is True
            assert isinstance(page1["next_cursor"], str)

            page2_resp = await client.get(
                "/api/v1/demo/locations",
                params={"limit": 1, "cursor": page1["next_cursor"]},
            )
            assert page2_resp.status_code == 200
            page2 = page2_resp.json()
            _assert_openapi_schema(page2, "DemoLocationPage")
            assert [item["code"] for item in page2["items"]] == ["skikda"]
            assert page2["has_more"] is False
            assert page2["next_cursor"] is None

            bad_cursors = [
                "not-valid-b64!",
                encode_cursor({"other": 1}),
                encode_cursor({"id": 0}),
                encode_cursor({"id": True}),
                encode_cursor({"id": "abc"}),
            ]
            for bad_cursor in bad_cursors:
                err_resp = await client.get(
                    "/api/v1/demo/locations",
                    params={"cursor": bad_cursor},
                )
                assert err_resp.status_code == 400
                err_body = err_resp.json()
                _assert_openapi_schema(err_body, "ErrorEnvelope")
                assert err_body["error"]["code"] == "INVALID_INPUT"

            bad_limit = await client.get("/api/v1/demo/locations?limit=0")
            assert bad_limit.status_code == 400
            assert bad_limit.json()["error"]["code"] == "INVALID_INPUT"


async def test_get_demo_location_boundary_geojson_and_errors(
    demo_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = demo_ctx

    async with sessionmaker() as db:
        inserted_id = int(
            (
                await db.execute(
                    text(
                        "INSERT INTO public.demo_locations (code, name, country, region, boundary,"
                        " is_active) VALUES ('inactive_zone', 'Inactive', 'Algeria', 'Test', "
                        "ST_SetSRID(ST_GeomFromText('MULTIPOLYGON(((7.0 36.0, 7.2 36.0, "
                        "7.2 36.2, 7.0 36.2, 7.0 36.0)))'), 4326), false) RETURNING id"
                    )
                )
            ).scalar_one()
        )
        await db.commit()

    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/demo/locations/1/boundary")
            assert resp.status_code == 200
            feature = resp.json()
            _assert_openapi_schema(feature, "BoundaryFeature")
            assert feature["type"] == "Feature"
            assert feature["properties"] == {"id": 1, "code": "guelma", "name": "Guelma"}
            assert feature["geometry"] == GUELMA_BOUNDARY_GEOJSON
            assert feature["bbox"] == pytest.approx([7.0, 36.05, 7.9, 36.65])

            missing = await client.get("/api/v1/demo/locations/999/boundary")
            assert missing.status_code == 404
            _assert_openapi_schema(missing.json(), "ErrorEnvelope")
            assert missing.json()["error"]["code"] == "NOT_FOUND"

            inactive = await client.get(f"/api/v1/demo/locations/{inserted_id}/boundary")
            assert inactive.status_code == 404
            assert inactive.json()["error"]["code"] == "NOT_FOUND"

            bad_id = await client.get("/api/v1/demo/locations/0/boundary")
            assert bad_id.status_code == 400
            assert bad_id.json()["error"]["code"] == "INVALID_INPUT"


async def test_get_demo_session_limits_canonical_quarters_and_auth_throttles(
    demo_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    _, engine, sessionmaker, redis_client = demo_ctx
    settings = _demo_settings(guest_burst_per_min=3)
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            no_hdr = await client.get("/api/v1/demo/session")
            assert no_hdr.status_code == 401
            _assert_openapi_schema(no_hdr.json(), "ErrorEnvelope")
            assert no_hdr.json()["error"]["code"] == "UNAUTHORIZED"

            start_resp = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert start_resp.status_code == 201
            raw_guest = start_resp.json()["guest_token"]
            guest_hash = hash_token(raw_guest)

            # Seed 1 farm, 2 fields, and requests totaling 5 analysis_quarters (4 + 1 + 0).
            async with sessionmaker() as db:
                farm = Farm(
                    guest_session_token=guest_hash,
                    farm_name="Demo Usage Farm",
                    country="Algeria",
                    region="Guelma",
                )
                db.add(farm)
                await db.flush()

                for idx in (1, 2):
                    db.add(
                        Field(
                            farm_id=farm.id,
                            external_field_id=f"F{idx}",
                            field_name=f"Parcel {idx}",
                            is_unverified_demo_parcel=(idx == 1),
                            geom_point=WKTElement(
                                f"POINT({7.50 + idx * 0.01} {36.50 + idx * 0.01})",
                                srid=4326,
                            ),
                            area_hectares=10.0,
                            soil_type="loamy",
                            soil_source="farmer",
                            water_availability="moderate",
                            water_source="well",
                            irrigation_system="drip",
                        )
                    )
                for req_suffix, units, req_status in (
                    ("full", 4, "ok"),
                    ("whatif", 1, "pending"),
                    ("refund", 0, "cancelled"),
                ):
                    db.add(
                        AnalysisRequest(
                            request_id=f"req_{uuid.uuid4().hex[:8]}_{req_suffix}",
                            farm_id=farm.id,
                            schema_version="5.0",
                            catalog_version="2026.11-v1",
                            dataset_version="2026.11-guelma-v1",
                            language="en",
                            quota_units=units,
                            input_hash=hash_token(f"in_{req_suffix}"),
                            full_input_hash=hash_token(f"full_{req_suffix}"),
                            status=req_status,
                        )
                    )
                await db.commit()

            headers = {"X-Guest-Token": raw_guest}
            session_resp = await client.get("/api/v1/demo/session", headers=headers)
            assert session_resp.status_code == 200
            info = session_resp.json()
            _assert_openapi_schema(info, "GuestSessionInfo")
            assert "demo_parcel" not in info
            assert "default_parcel_id" not in info["demo_location"]
            assert info["demo_location"]["code"] == "guelma"
            assert info["limits"] == {
                "max_farms": 3,
                "max_fields_per_farm": 5,
                "max_analyses": 10,
                "max_analysis_quarters": 40,
            }
            assert info["usage"] == {
                "farms": 1,
                "fields": 2,
                "analysis_quarters": 5,
                "analyses": 1.25,
            }

            # Burst cap = 3: 2nd & 3rd calls succeed, 4th returns 429 RATE_LIMIT_EXCEEDED.
            assert (await client.get("/api/v1/demo/session", headers=headers)).status_code == 200
            assert (await client.get("/api/v1/demo/session", headers=headers)).status_code == 200
            throttled = await client.get("/api/v1/demo/session", headers=headers)
            assert throttled.status_code == 429
            _assert_openapi_schema(throttled.json(), "ErrorEnvelope")
            assert throttled.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert int(throttled.headers["Retry-After"]) >= 1

            # Expired guest token must return 401 UNAUTHORIZED.
            expired_raw = f"gst_{uuid.uuid4().hex[:24]}"
            async with sessionmaker() as db:
                db.add(
                    GuestSession(
                        guest_token=hash_token(expired_raw),
                        demo_location_id=1,
                        expires_at=datetime.now(UTC) - timedelta(minutes=1),
                    )
                )
                await db.commit()
            exp_resp = await client.get(
                "/api/v1/demo/session",
                headers={"X-Guest-Token": expired_raw},
            )
            assert exp_resp.status_code == 401
            assert exp_resp.json()["error"]["code"] == "UNAUTHORIZED"

            # Fail-closed Redis outage -> 503 SERVICE_UNAVAILABLE.
            broken_redis = redis_async.Redis.from_url("redis://127.0.0.1:6399/0")
            app.state.redis = broken_redis
            try:
                outage_resp = await client.get("/api/v1/demo/session", headers=headers)
                assert outage_resp.status_code == 503
                _assert_openapi_schema(outage_resp.json(), "ErrorEnvelope")
                assert outage_resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
            finally:
                app.state.redis = redis_client
                await broken_redis.aclose()


async def test_delete_demo_session_cascades_all_guest_data_and_clears_redis(
    demo_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    settings, engine, sessionmaker, redis_client = demo_ctx
    app = create_app(settings=settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker
    app.state.redis = redis_client

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            start_resp = await client.post("/api/v1/auth/guest", json={"demo_location_id": 1})
            assert start_resp.status_code == 201
            raw_guest = start_resp.json()["guest_token"]
            guest_hash = hash_token(raw_guest)

            async with sessionmaker() as db:
                farm = Farm(
                    guest_session_token=guest_hash,
                    farm_name="Ephemeral Guest Farm",
                    country="Algeria",
                    region="Guelma",
                )
                db.add(farm)
                await db.flush()

                field = Field(
                    farm_id=farm.id,
                    external_field_id="F1",
                    field_name="Temp Plot",
                    geom_point=WKTElement("POINT(7.52 36.52)", srid=4326),
                    area_hectares=8.0,
                    soil_type="loamy",
                    soil_source="farmer",
                    water_availability="moderate",
                    water_source="well",
                    irrigation_system="drip",
                )
                db.add(field)
                await db.flush()

                db.add(
                    FieldCropHistory(
                        field_id=field.id,
                        season="autumn",
                        year=2025,
                        crop_name_raw="Durum Wheat",
                    )
                )

                req_id = f"req_{uuid.uuid4().hex[:12]}"
                db.add(
                    AnalysisRequest(
                        request_id=req_id,
                        farm_id=farm.id,
                        schema_version="5.0",
                        catalog_version="2026.11-v1",
                        dataset_version="2026.11-guelma-v1",
                        language="en",
                        quota_units=4,
                        input_hash=hash_token("in_del"),
                        full_input_hash=hash_token("full_del"),
                        status="ok",
                    )
                )
                await db.flush()

                analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"
                db.add(
                    AnalysisResult(
                        analysis_id=analysis_id,
                        request_id=req_id,
                        status="ok",
                        dataset_version_used="2026.11-guelma-v1",
                        ml_engine_version="1.0.0",
                        result_json={"schema_version": "5.0", "status": "ok"},
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

            await increment_guest_quarters(
                redis_client,
                guest_token_hash=guest_hash,
                delta=4,
                fallback_total=4,
                ttl_seconds=3600,
            )
            q_key = guest_quota_key(guest_hash)
            assert await redis_client.get(q_key) == b"4"

            headers = {"X-Guest-Token": raw_guest}
            del_resp = await client.delete("/api/v1/demo/session", headers=headers)
            assert del_resp.status_code == 204
            assert del_resp.content == b""

            assert await redis_client.get(q_key) is None

            async with sessionmaker() as db:
                for model in (
                    GuestSession,
                    Farm,
                    Field,
                    FieldCropHistory,
                    AnalysisRequest,
                    AnalysisResult,
                    AnalysisSelection,
                ):
                    count = int((await db.scalar(select(func.count()).select_from(model))) or 0)
                    assert count == 0, f"Expected cascade delete for {model.__name__}, got {count}"

            recheck = await client.get("/api/v1/demo/session", headers=headers)
            assert recheck.status_code == 401
            assert recheck.json()["error"]["code"] == "UNAUTHORIZED"


async def test_postgis_spatial_boundary_gate_guelma_setif_algiers_and_axis_order(
    demo_ctx: tuple[
        Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis
    ],
) -> None:
    _, _, sessionmaker, _ = demo_ctx

    async with sessionmaker() as db:
        # 1. Point inside Wilaya of Guelma (36.52° N, 7.52° E) -> True.
        assert (
            await geo_service.is_point_inside_demo_boundary(
                db,
                latitude=36.52,
                longitude=7.52,
                demo_location_id=1,
            )
            is True
        )
        covered, notice = await geo_service.check_field_coordinates_coverage(
            db,
            latitude=36.52,
            longitude=7.52,
            is_guest=True,
            demo_location_id=1,
            field_id="F1",
        )
        assert covered is True
        assert notice is None

        # 2. Boundary vertex check (ST_Covers includes edges/vertices).
        assert (
            await geo_service.is_point_inside_demo_boundary(
                db,
                latitude=36.08,
                longitude=7.12,
                demo_location_id=1,
            )
            is True
        )

        # 3. Outside points: Setif (36.19, 5.41), Algiers (36.7538, 3.0588), swapped (7.52, 36.52).
        for outside_lat, outside_lon in (
            (36.19, 5.41),
            (36.7538, 3.0588),
            (7.52, 36.52),
        ):
            assert (
                await geo_service.is_point_inside_demo_boundary(
                    db,
                    latitude=outside_lat,
                    longitude=outside_lon,
                    demo_location_id=1,
                )
                is False
            )

            with pytest.raises(FieldShiftError) as exc_info:
                await geo_service.check_field_coordinates_coverage(
                    db,
                    latitude=outside_lat,
                    longitude=outside_lon,
                    is_guest=True,
                    demo_location_id=1,
                    field_id="F1",
                )
            assert exc_info.value.code is ErrorCode.OUTSIDE_DEMO_BOUNDARY
            assert exc_info.value.status_code == 422

        # 4. Registered user outside Guelma saves cleanly with MVP_OUTSIDE_COVERAGE notice.
        reg_covered, reg_notice = await geo_service.check_field_coordinates_coverage(
            db,
            latitude=36.19,
            longitude=5.41,
            is_guest=False,
            field_id="F_SETIF",
        )
        assert reg_covered is False
        assert reg_notice is not None
        assert reg_notice.code is WarningCode.MVP_OUTSIDE_COVERAGE
        assert reg_notice.message == MVP_OUTSIDE_COVERAGE_MESSAGE
        assert reg_notice.fields == ["F_SETIF"]

        # 5. Out-of-range coordinates rejected with 400 INVALID_INPUT before SQL query.
        with pytest.raises(FieldShiftError) as bad_lat_exc:
            await geo_service.is_point_inside_demo_boundary(
                db,
                latitude=95.0,
                longitude=7.52,
            )
        assert bad_lat_exc.value.code is ErrorCode.INVALID_INPUT
        assert bad_lat_exc.value.status_code == 400
