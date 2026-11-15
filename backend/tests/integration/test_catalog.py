"""Real PostGIS + Redis integration & OpenAPI conformance tests for M6 Catalog & Datasets."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import os
import socket
import subprocess
import sys
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
import uvicorn
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from referencing.typing import URI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.pagination import encode_cursor
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import (
    ML_PROVIDER_STATUS_REDIS_KEY,
    MLAdapter,
    MLHealthResult,
    MLProviderManager,
    MockMLAdapter,
    read_provider_status,
)
from app.ml_client.base import ProviderKind, validate_contract_def
from app.ml_client.mock_server import create_mock_ml_app
from app.repositories import catalog as catalog_repo
from app.repositories import dataset as dataset_repo
from app.schemas.catalog import MLCatalogPayload
from app.services import catalog as catalog_service
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
    """Validate HTTP JSON response payload strictly against `openapi.yaml` + `schema-v5.0.json`."""
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


def _free_unbound_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _m6_settings(
    *,
    app_env: Literal["production", "development", "test"] = "test",
    ml_provider_mode: Literal["auto", "real", "mock"] = "auto",
    ml_service_url: str | None = None,
    ml_api_key: str | None = None,
    rate_limit_crud_per_min: int = 60,
    guest_burst_per_min: int = 30,
    redis_url: str | None = None,
) -> Settings:
    env = build_test_env()
    return Settings(
        _env_file=None,
        APP_ENV=app_env,
        ML_PROVIDER_MODE=ml_provider_mode,
        ML_SERVICE_URL=ml_service_url or f"http://127.0.0.1:{_free_unbound_port()}",
        ML_SERVICE_API_KEY=ml_api_key or env["ML_SERVICE_API_KEY"],
        ML_TIMEOUT_SECONDS=5,
        ML_CATALOG_TIMEOUT_SECONDS=3,
        ML_HEALTH_TIMEOUT_SECONDS=1,
        ML_HEALTH_CHECK_INTERVAL_SECONDS=30,
        DATABASE_URL=env["DATABASE_URL"],
        DB_PASSWORD=env["DB_PASSWORD"],
        REDIS_URL=redis_url or _redis_url(),
        ML_DATASET_DB_URL=env["ML_DATASET_DB_URL"],
        ML_READER_PASSWORD=env["ML_READER_PASSWORD"],
        JWT_SECRET_KEY=env["JWT_SECRET_KEY"],
        GUEST_CREATE_PER_IP_HOUR=100,
        GUEST_BURST_PER_MIN=guest_burst_per_min,
        RATE_LIMIT_CRUD_PER_MIN=rate_limit_crud_per_min,
    )


async def _cleanup_test_rows(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as db:
        await db.execute(
            text(
                "TRUNCATE TABLE public.crop_catalog, public.analysis_selections, "
                "public.analysis_results, public.analysis_requests, public.field_crop_history, "
                "public.fields, public.farms, public.guest_sessions, public.refresh_tokens, "
                "public.users RESTART IDENTITY CASCADE"
            )
        )
        await db.execute(
            text(
                "UPDATE public.dataset_registry SET is_active = TRUE "
                "WHERE dataset_version = :ver"
            ),
            {"ver": DEFAULT_DATASET_VERSION},
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
async def m6_ctx(
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
    settings = _m6_settings()
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


async def _start_guest(client: httpx.AsyncClient, ip: str = "198.51.100.10") -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/guest",
        headers={"X-Forwarded-For": ip},
        json={"demo_location_id": GUELMA_LOCATION_ID},
    )
    assert resp.status_code == 201
    return {"X-Guest-Token": str(resp.json()["guest_token"])}


async def _register_user(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword!123",
            "full_name": "Catalog Tester",
            "preferred_lang": "en",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class _CountingOfflineSafeRealAdapter(MLAdapter):
    """Stub counting upstream `get_catalog` calls for advisory-lock race testing."""

    def __init__(self, inner: MLAdapter) -> None:
        self._inner = inner
        self.catalog_calls = 0

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
        return await self._inner.analyze(
            payload,
            idempotency_key=idempotency_key,
            compress=compress,
        )

    async def get_catalog(self) -> MLCatalogPayload:
        self.catalog_calls += 1
        await asyncio.sleep(0.05)
        return await self._inner.get_catalog()

    async def get_health(self) -> MLHealthResult:
        return await self._inner.get_health()


@pytest.mark.asyncio
async def test_catalog_cold_start_production_offline_returns_502_ml_unavailable(
    m6_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _base_settings, _engine, _sessionmaker, _redis = m6_ctx
    prod_settings = _m6_settings(
        app_env="production",
        ml_provider_mode="auto",
        ml_service_url=f"https://127.0.0.1:{_free_unbound_port()}",
    )
    app = create_app(settings=prod_settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        guest_headers = await _start_guest(client, "198.51.100.11")
        resp = await client.get("/api/v1/catalog", headers=guest_headers)
        assert resp.status_code == 502
        body = resp.json()
        _assert_openapi_schema(body, "ErrorEnvelope")
        assert body["error"]["code"] == ErrorCode.ML_UNAVAILABLE.value
        assert app.state.ml_provider_manager.allows_mock is False
        assert app.state.ml_provider_manager.mock_adapter is None


@pytest.mark.asyncio
async def test_catalog_cold_start_auto_mock_filters_localization_and_cursor_pagination(
    m6_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, _sessionmaker, redis_client = m6_ctx
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        user_headers = await _register_user(client, "catalog_user@example.com")

        # Cold-start lazy bootstrap in test/auto falls back to MockMLAdapter (DB empty -> 6 crops).
        first = await client.get("/api/v1/catalog", headers=user_headers)
        assert first.status_code == 200
        full_page = first.json()
        _assert_openapi_schema(full_page, "CatalogPage")
        assert full_page["catalog_version"] == "2026.11"
        assert len(full_page["items"]) == 6
        assert full_page["has_more"] is False
        assert full_page["next_cursor"] is None
        for crop_item in full_page["items"]:
            assert validate_contract_def(crop_item, "CropItem") == []

        # Live Redis ml:provider_status snapshot + positive TTL verified in Redis.
        ttl_s = await redis_client.ttl(ML_PROVIDER_STATUS_REDIS_KEY)
        assert 0 < ttl_s <= 2 * settings.ML_HEALTH_CHECK_INTERVAL_SECONDS
        snap = await read_provider_status(redis_client)
        assert snap is not None
        assert snap.provider == "mock_ml"
        assert snap.reachable is True

        # Language localization (`en`, `fr`, `ar`) preserving full `names` object & `display_name`.
        ar_resp = await client.get(
            "/api/v1/catalog",
            headers=user_headers,
            params={"lang": "ar", "limit": 100},
        )
        assert ar_resp.status_code == 200
        ar_page = ar_resp.json()
        _assert_openapi_schema(ar_page, "CatalogPage")
        wheat_ar = next(i for i in ar_page["items"] if i["crop_id"] == "durum_wheat")
        assert wheat_ar["display_name"] == wheat_ar["names"]["ar"]
        assert set(wheat_ar["names"].keys()) == {"en", "fr", "ar"}

        fr_resp = await client.get(
            "/api/v1/catalog",
            headers=user_headers,
            params={"lang": "fr", "category": "legumes", "role": "nitrogen_fixer"},
        )
        assert fr_resp.status_code == 200
        fr_page = fr_resp.json()
        _assert_openapi_schema(fr_page, "CatalogPage")
        assert len(fr_page["items"]) >= 1
        assert all(i["category"] == "legumes" for i in fr_page["items"])
        assert all("nitrogen_fixer" in i["roles"] for i in fr_page["items"])
        assert all(i["display_name"] == i["names"]["fr"] for i in fr_page["items"])

        # Empty filtered slice returns 200 empty CatalogPage.
        empty_resp = await client.get(
            "/api/v1/catalog",
            headers=user_headers,
            params={"category": "fallow", "role": "forage"},
        )
        assert empty_resp.status_code == 200
        empty_page = empty_resp.json()
        _assert_openapi_schema(empty_page, "CatalogPage")
        assert empty_page["items"] == []
        assert empty_page["has_more"] is False
        assert empty_page["next_cursor"] is None

        # Multi-page keyset cursor walk (`limit=2` across 6 crops = 2 + 2 + 2).
        observed_ids: list[str] = []
        cursor: str | None = None
        pages = 0
        while True:
            params: dict[str, Any] = {"limit": 2}
            if cursor is not None:
                params["cursor"] = cursor
            page_resp = await client.get("/api/v1/catalog", headers=user_headers, params=params)
            assert page_resp.status_code == 200
            page_json = page_resp.json()
            _assert_openapi_schema(page_json, "CatalogPage")
            observed_ids.extend(item["crop_id"] for item in page_json["items"])
            pages += 1
            if not page_json["has_more"]:
                assert page_json["next_cursor"] is None
                break
            cursor = str(page_json["next_cursor"])
        assert pages == 3
        assert len(observed_ids) == 6
        assert observed_ids == sorted(observed_ids)

        # Invalid/tampered cursor and blank version return 400 INVALID_INPUT.
        for bad_params in (
            {"cursor": "not-valid-base64!"},
            {"cursor": encode_cursor({"crop_id": 123})},
            {"version": "   "},
        ):
            bad_resp = await client.get("/api/v1/catalog", headers=user_headers, params=bad_params)
            assert bad_resp.status_code == 400
            err_body = bad_resp.json()
            _assert_openapi_schema(err_body, "ErrorEnvelope")
            assert err_body["error"]["code"] == ErrorCode.INVALID_INPUT.value


@pytest.mark.asyncio
async def test_catalog_wire_http_real_adapter_against_live_mock_server_and_sync_retention(
    m6_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _s, _engine, sessionmaker, redis_client = m6_ctx
    mock_app = create_mock_ml_app(accepted_api_keys=["m6-tcp-key"])
    mock_app.state.catalog_page_size = 4

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    port = int(sock.getsockname()[1])

    config = uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        while not server.started:
            await asyncio.sleep(0.01)

        settings = _m6_settings(
            app_env="test",
            ml_provider_mode="real",
            ml_service_url=f"http://127.0.0.1:{port}",
            ml_api_key="m6-tcp-key",
        )
        app = create_app(settings=settings)

        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client,
        ):
            guest_headers = await _start_guest(client, "198.51.100.12")
            resp = await client.get("/api/v1/catalog", headers=guest_headers)
            assert resp.status_code == 200
            body = resp.json()
            _assert_openapi_schema(body, "CatalogPage")
            assert body["catalog_version"] == "2026.11"
            assert len(body["items"]) == 6

            health = await app.state.ml_provider_manager.refresh_provider_status(publish_redis=True)
            assert health.reachable is True
            snap = await read_provider_status(redis_client)
            assert snap is not None
            assert snap.provider == "real_ml"

            # Verify N / N-1 retention (`v1` -> `v2` -> `v3` prunes `v1`, retains `v2` and `v3`).
            base_catalog = json.loads(
                (TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
            )
            async with sessionmaker() as db:
                await db.execute(text("TRUNCATE TABLE public.crop_catalog"))
                await db.commit()

                for idx, ver in enumerate(("2026.01", "2026.02", "2026.03")):
                    payload_dict = copy.deepcopy(base_catalog)
                    payload_dict["catalog_version"] = ver
                    if idx == 2:
                        # Drop last 3 crops on v3 to confirm orphan removal within a version too.
                        payload_dict["crops"] = payload_dict["crops"][:3]
                    payload = MLCatalogPayload.model_validate(payload_dict)

                    class _StaticCatalogAdapter(MLAdapter):
                        def __init__(self, p: MLCatalogPayload) -> None:
                            self._p = p

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
                            raise NotImplementedError

                        async def get_catalog(self) -> MLCatalogPayload:
                            return self._p

                        async def get_health(self) -> MLHealthResult:
                            return MLHealthResult(reachable=True, status="ok", provider="real_ml")

                    sync_mgr = MLProviderManager(
                        settings,
                        real_adapter=_StaticCatalogAdapter(payload),
                    )
                    await catalog_service.sync_catalog_once(db, sync_mgr)

                versions = await catalog_repo.list_catalog_versions(db)
                assert versions == ["2026.03", "2026.02"]

            # Querying retained N-1 (`2026.02`) returns 200; pruned `2026.01` returns 404 NOT_FOUND.
            n_minus_1 = await client.get(
                "/api/v1/catalog",
                headers=guest_headers,
                params={"version": "2026.02"},
            )
            assert n_minus_1.status_code == 200
            _assert_openapi_schema(n_minus_1.json(), "CatalogPage")
            assert n_minus_1.json()["catalog_version"] == "2026.02"
            assert len(n_minus_1.json()["items"]) == 6

            pruned = await client.get(
                "/api/v1/catalog",
                headers=guest_headers,
                params={"version": "2026.01"},
            )
            assert pruned.status_code == 404
            pruned_err = pruned.json()
            _assert_openapi_schema(pruned_err, "ErrorEnvelope")
            assert pruned_err["error"]["code"] == ErrorCode.NOT_FOUND.value
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task
        sock.close()


@pytest.mark.asyncio
async def test_catalog_concurrent_cold_start_advisory_lock_deduplicates_ml_sync(
    m6_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _base, _engine, _sessionmaker, _redis = m6_ctx
    settings = _m6_settings(app_env="test", ml_provider_mode="real")
    counting_real = _CountingOfflineSafeRealAdapter(MockMLAdapter())
    manager = MLProviderManager(settings, real_adapter=counting_real)
    app = create_app(settings=settings)
    app.state.ml_provider_manager = manager

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        guest_headers = await _start_guest(client, "198.51.100.13")
        r1, r2 = await asyncio.gather(
            client.get("/api/v1/catalog", headers=guest_headers),
            client.get("/api/v1/catalog", headers=guest_headers),
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert counting_real.catalog_calls == 1
        assert len(r1.json()["items"]) == 6
        assert len(r2.json()["items"]) == 6


@pytest.mark.asyncio
async def test_catalog_auth_401_rate_limit_429_and_redis_outage_503_fail_closed(
    m6_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _base, _engine, _sessionmaker, redis_client = m6_ctx
    settings = _m6_settings(app_env="test", ml_provider_mode="auto", guest_burst_per_min=2)
    app = create_app(settings=settings)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        unauth = await client.get("/api/v1/catalog")
        assert unauth.status_code == 401
        _assert_openapi_schema(unauth.json(), "ErrorEnvelope")

        guest_headers = await _start_guest(client, "198.51.100.14")
        ok1 = await client.get("/api/v1/catalog", headers=guest_headers)
        ok2 = await client.get("/api/v1/catalog", headers=guest_headers)
        throttled = await client.get("/api/v1/catalog", headers=guest_headers)
        assert ok1.status_code == 200
        assert ok2.status_code == 200
        assert throttled.status_code == 429
        assert "retry-after" in throttled.headers
        throttled_body = throttled.json()
        _assert_openapi_schema(throttled_body, "ErrorEnvelope")
        assert throttled_body["error"]["code"] == ErrorCode.RATE_LIMIT_EXCEEDED.value

        # Simulate Redis outage via unbound dead TCP Redis URL -> 503 fail-closed.
        dead_port = _free_unbound_port()
        broken_redis = redis_async.Redis.from_url(
            f"redis://127.0.0.1:{dead_port}/0",
            socket_connect_timeout=0.5,
            decode_responses=False,
        )
        original_redis = app.state.redis
        app.state.redis = broken_redis
        try:
            outage = await client.get("/api/v1/catalog", headers=guest_headers)
            assert outage.status_code == 503
            assert outage.headers.get("retry-after") == "5"
            outage_body = outage.json()
            _assert_openapi_schema(outage_body, "ErrorEnvelope")
            assert outage_body["error"]["code"] == ErrorCode.SERVICE_UNAVAILABLE.value
        finally:
            app.state.redis = original_redis
            await broken_redis.aclose()
        assert await redis_client.ping() is True


@pytest.mark.asyncio
async def test_dataset_registry_active_lookup_and_503_dataset_unavailable(
    m6_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    _settings, _engine, sessionmaker, _redis = m6_ctx
    async with sessionmaker() as db:
        active = await dataset_repo.require_active_dataset(db)
        assert active.dataset_version == DEFAULT_DATASET_VERSION
        assert active.is_active is True

        fetched = await dataset_repo.get_dataset_by_version(
            db,
            dataset_version=DEFAULT_DATASET_VERSION,
        )
        assert fetched is not None
        assert fetched.dataset_version == DEFAULT_DATASET_VERSION

        await db.execute(text("UPDATE public.dataset_registry SET is_active = FALSE"))
        await db.commit()

        with pytest.raises(FieldShiftError) as exc_info:
            await dataset_repo.require_active_dataset(db)
        assert exc_info.value.code == ErrorCode.DATASET_UNAVAILABLE
        assert exc_info.value.status_code == 503
        assert datetime.now(UTC) > datetime(2020, 1, 1, tzinfo=UTC)
