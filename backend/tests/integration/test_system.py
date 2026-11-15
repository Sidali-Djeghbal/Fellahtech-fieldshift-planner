"""Live PostGIS + Redis integration tests for M11 Ops, /health, /metrics, Reaper & Logs."""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import io
import json
import os
import socket
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
import structlog
import uvicorn
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from prometheus_client.parser import text_string_to_metric_families
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from referencing.typing import URI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.logging import configure_logging
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.core.security import hash_token
from app.db.seed import DEFAULT_DATASET_VERSION, GUELMA_LOCATION_ID
from app.db.session import create_db_engine, create_sessionmaker
from app.main import create_app
from app.ml_client import MLAdapter, MLHealthResult, MLProviderManager, MockMLAdapter
from app.ml_client.base import ProviderKind
from app.ml_client.mock_server import create_mock_ml_app
from app.models import AnalysisRequest, Farm, GuestSession
from app.schemas.catalog import MLCatalogPayload
from app.services.catalog import sync_catalog_once
from app.services.health import probe_health
from app.services.worker_heartbeat import (
    WORKER_HEARTBEAT_REDIS_PREFIX,
    clear_worker_heartbeat,
    count_active_workers,
    publish_worker_heartbeat,
)
from app.worker.breaker import record_breaker_failure
from app.worker.healthcheck import check_worker_health
from app.worker.runner import WorkerRunner, sync_catalog_under_advisory_lock
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


def _redis_url() -> str:
    return os.getenv("TEST_REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def _free_unbound_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _assert_openapi_schema(payload: Any, schema_name: str) -> None:
    openapi_uri: URI = "https://fieldshift.local/contracts/openapi.yaml"
    schema_uri: URI = "https://fieldshift.local/contracts/schema-v5.0.json"
    registry = Registry().with_resources(
        [
            (openapi_uri, Resource.from_contents(_OPENAPI_DOC, default_specification=DRAFT202012)),
            (schema_uri, Resource.from_contents(_SCHEMA_DOC, default_specification=DRAFT202012)),
        ]
    )
    validator = Draft202012Validator(
        {"$ref": f"{openapi_uri}#/components/schemas/{schema_name}"},
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, f"Schema {schema_name} errors: {[e.message for e in errors]}"


def _system_settings(**overrides: Any) -> Settings:
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
        "ML_HEALTH_TIMEOUT_SECONDS": 1,
        "ML_HEALTH_CHECK_INTERVAL_SECONDS": 30,
        "ML_TIMEOUT_SECONDS": 5,
        "ML_MAX_RETRIES": 0,
        "ML_CIRCUIT_BREAKER_THRESHOLD": 5,
        "ML_BREAKER_COOLDOWN_SECONDS": 30,
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
                "UPDATE public.ml_breaker_state "
                "SET state = 'closed', consecutive_failures = 0, "
                "opened_at = NULL, half_open_probe_at = NULL, updated_at = NOW() "
                "WHERE id = 1"
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
async def m11_ctx(
    migrated_database: None,
) -> AsyncIterator[
    tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis]
]:
    del migrated_database
    settings = _system_settings()
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


@asynccontextmanager
async def _running_mock_ml_server(settings: Settings) -> AsyncIterator[str]:
    mock_app = create_mock_ml_app(accepted_api_keys=(settings.ML_SERVICE_API_KEY,))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    config = uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(50):
            if server.started:
                break
            await asyncio.sleep(0.05)
        assert server.started
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(serve_task, timeout=5.0)


@pytest.mark.asyncio
async def test_health_live_dependencies_and_ready_openapi_ok(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, redis_client = m11_ctx

    async with sessionmaker() as db:
        await sync_catalog_once(db, ml_manager=MLProviderManager(settings))
        await db.commit()

    await publish_worker_heartbeat(redis_client, worker_id="worker-a", ttl_seconds=30)

    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            live_resp = await client.get("/api/v1/health?check=live")
            assert live_resp.status_code == 200
            live_body = live_resp.json()
            _assert_openapi_schema(live_body, "HealthResponse")
            assert live_body["status"] == "ok"
            assert live_body["db"] == {"connected": False, "postgis_version": "skipped"}

            dep_resp = await client.get("/api/v1/health")
            assert dep_resp.status_code == 200
            dep_body = dep_resp.json()
            _assert_openapi_schema(dep_body, "HealthResponse")
            assert dep_body["status"] == "ok"
            assert dep_body["db"]["connected"] is True
            assert len(dep_body["db"]["postgis_version"]) > 0
            assert dep_body["dataset"]["active_version"] == DEFAULT_DATASET_VERSION
            assert dep_body["dataset"]["loaded_at"] is not None
            assert dep_body["catalog"]["version"] is not None
            assert dep_body["catalog"]["synced_at"] is not None
            assert dep_body["worker_queue"]["active_workers"] == 1
            assert dep_body["worker_queue"]["pending_jobs"] == 0
            assert dep_body["worker_queue"]["stale_leases"] == 0
            assert dep_body["ml_service"]["reachable"] is True
            assert dep_body["ml_service"]["circuit_breaker"] == "closed"
            assert dep_body["ml_service"]["consecutive_failures"] == 0
            assert dep_body["ml_service"]["ml_engine_version"] is not None

            ready_resp = await client.get("/api/v1/health?check=ready")
            assert ready_resp.status_code == 200
            ready_body = ready_resp.json()
            _assert_openapi_schema(ready_body, "HealthResponse")
            assert ready_body["status"] == "ok"
            assert ready_body["ml_service"]["reachable"] is True

    await clear_worker_heartbeat(redis_client, worker_id="worker-a")
    assert await count_active_workers(redis_client) == 0


@pytest.mark.asyncio
async def test_health_production_offline_ml_and_worker_api_redis_agreement(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    base_settings, engine, sessionmaker, redis_client = m11_ctx

    prod_settings = _system_settings(
        APP_ENV="production",
        ML_PROVIDER_MODE="real",
        ML_SERVICE_URL=f"https://127.0.0.1:{_free_unbound_port()}",
    )
    del base_settings

    # Trip PostgreSQL circuit breaker open & write worker-side `ml:provider_status` to Redis.
    now = datetime.now(UTC)
    async with sessionmaker() as db:
        for _ in range(prod_settings.ML_CIRCUIT_BREAKER_THRESHOLD):
            await record_breaker_failure(
                db,
                now=now,
                failure_threshold=prod_settings.ML_CIRCUIT_BREAKER_THRESHOLD,
                was_half_open_probe=False,
            )
        await db.commit()

    worker_manager = MLProviderManager(prod_settings, redis_client=redis_client)
    runner = WorkerRunner(
        settings=prod_settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=worker_manager,
        worker_id="worker-prod-check",
    )
    try:
        await runner._publish_provider_status_best_effort()
        await publish_worker_heartbeat(redis_client, worker_id="worker-prod-check", ttl_seconds=60)

        app = create_app(settings=prod_settings)
        async with app.router.lifespan_context(app):
            # Invalidate in-memory API manager health to prove API reads worker's Redis snapshot.
            api_mgr: MLProviderManager = app.state.ml_provider_manager
            assert api_mgr.last_health is None

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                for query in ("", "?check=dependencies", "?check=ready"):
                    resp = await client.get(f"/api/v1/health{query}")
                    assert resp.status_code == 200
                    body = resp.json()
                    _assert_openapi_schema(body, "HealthResponse")
                    assert body["status"] == "degraded"
                    assert body["db"]["connected"] is True
                    assert body["worker_queue"]["active_workers"] == 1
                    assert body["ml_service"]["reachable"] is False
                    assert body["ml_service"]["circuit_breaker"] == "open"
                    assert (
                        body["ml_service"]["consecutive_failures"]
                        == prod_settings.ML_CIRCUIT_BREAKER_THRESHOLD
                    )
                    assert body["ml_service"]["ml_engine_version"] is None
    finally:
        await worker_manager.aclose()


@pytest.mark.asyncio
async def test_health_returns_503_on_redis_or_postgres_or_dataset_outage(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, _redis_client = m11_ctx

    # 1. Redis unreachable while Postgres is healthy -> 503 SERVICE_UNAVAILABLE
    bad_redis_settings = _system_settings(REDIS_URL=f"redis://127.0.0.1:{_free_unbound_port()}/0")
    app_bad_redis = create_app(settings=bad_redis_settings)
    async with app_bad_redis.router.lifespan_context(app_bad_redis):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_bad_redis),
            base_url="http://testserver",
        ) as client:
            for check_q in ("dependencies", "ready"):
                r = await client.get(f"/api/v1/health?check={check_q}")
                assert r.status_code == 503
                err = r.json()
                _assert_openapi_schema(err, "ErrorEnvelope")
                assert err["error"]["code"] == ErrorCode.SERVICE_UNAVAILABLE.value

    # 2. PostgreSQL unreachable while Redis is healthy -> 503 SERVICE_UNAVAILABLE
    env = build_test_env()
    bad_pg_settings = _system_settings(
        DATABASE_URL=f"postgresql+asyncpg://fieldshift:{env['DB_PASSWORD']}@127.0.0.1:{_free_unbound_port()}/fieldshift"
    )
    app_bad_pg = create_app(settings=bad_pg_settings)
    # Create app manually if lifespan skips or fails? Lifespan only builds engine lazily!
    async with app_bad_pg.router.lifespan_context(app_bad_pg):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_bad_pg),
            base_url="http://testserver",
        ) as client:
            r = await client.get("/api/v1/health?check=dependencies")
            assert r.status_code == 503
            err = r.json()
            _assert_openapi_schema(err, "ErrorEnvelope")
            assert err["error"]["code"] == ErrorCode.SERVICE_UNAVAILABLE.value

    # 3. Missing active dataset -> 503 DATASET_UNAVAILABLE
    try:
        async with sessionmaker() as db:
            await db.execute(text("UPDATE public.dataset_registry SET is_active = FALSE"))
            await db.commit()

        app_no_ds = create_app(settings=settings)
        async with app_no_ds.router.lifespan_context(app_no_ds):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_no_ds),
                base_url="http://testserver",
            ) as client:
                r = await client.get("/api/v1/health?check=dependencies")
                assert r.status_code == 503
                err = r.json()
                _assert_openapi_schema(err, "ErrorEnvelope")
                assert err["error"]["code"] == ErrorCode.DATASET_UNAVAILABLE.value
    finally:
        async with sessionmaker() as db:
            await db.execute(
                text(
                    "UPDATE public.dataset_registry SET is_active = (dataset_version = :ver)"
                ),
                {"ver": DEFAULT_DATASET_VERSION},
            )
            await db.commit()

    # 4. Direct helper edge guards (`redis_client is None`, `sessionmaker is None`)
    with pytest.raises(FieldShiftError) as missing_redis_exc:
        await probe_health(
            check="ready",
            sessionmaker=sessionmaker,
            redis_client=None,
            ml_manager=None,
            settings=settings,
        )
    assert missing_redis_exc.value.code == ErrorCode.SERVICE_UNAVAILABLE

    with pytest.raises(FieldShiftError) as missing_db_exc:
        await probe_health(
            check="ready",
            sessionmaker=None,
            redis_client=_redis_client,
            ml_manager=None,
            settings=settings,
        )
    assert missing_db_exc.value.code == ErrorCode.SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_metrics_endpoint_and_internal_only_openapi_marker(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, sessionmaker, _redis = m11_ctx

    app = create_app(settings=settings)
    schema_doc = app.openapi()
    assert "/api/v1/metrics" in schema_doc["paths"]
    assert schema_doc["paths"]["/api/v1/metrics"]["get"].get("x-internal-only") is True

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # Closed state -> gauge 0.0
            m1 = await client.get("/api/v1/metrics")
            assert m1.status_code == 200
            assert m1.headers["content-type"].startswith("text/plain")
            families1 = {fam.name: fam for fam in text_string_to_metric_families(m1.text)}
            for expected in (
                "analysis_requests",
                "ml_request_duration_seconds",
                "worker_active_leases",
                "worker_bulkhead_inflight",
                "ml_breaker_state",
                "ml_unknown_fields_observed",
            ):
                assert expected in families1, f"Missing metric {expected}"
            assert families1["ml_breaker_state"].samples[0].value == 0.0

            # Trip breaker open in DB -> API `/metrics` syncs live `ml_breaker_state == 1.0`
            now = datetime.now(UTC)
            async with sessionmaker() as db:
                for _ in range(settings.ML_CIRCUIT_BREAKER_THRESHOLD):
                    await record_breaker_failure(
                        db,
                        now=now,
                        failure_threshold=settings.ML_CIRCUIT_BREAKER_THRESHOLD,
                        was_half_open_probe=False,
                    )
                await db.commit()

            m2 = await client.get("/api/v1/metrics")
            assert m2.status_code == 200
            families2 = {fam.name: fam for fam in text_string_to_metric_families(m2.text)}
            assert families2["ml_breaker_state"].samples[0].value == 1.0


@pytest.mark.asyncio
async def test_worker_healthcheck_cli_live_and_outage(
    migrated_database: None,
) -> None:
    del migrated_database
    settings = _system_settings()
    assert await check_worker_health(settings) is True

    env = build_test_env()
    env.update(
        {
            "APP_ENV": "test",
            "REDIS_URL": _redis_url(),
            "ML_SERVICE_URL": settings.ML_SERVICE_URL,
        }
    )
    ok_proc = subprocess.run(
        [sys.executable, "-m", "app.worker.healthcheck"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert ok_proc.returncode == 0, ok_proc.stderr

    bad_redis_env = dict(env)
    bad_redis_env["REDIS_URL"] = f"redis://127.0.0.1:{_free_unbound_port()}/0"
    bad_redis_proc = subprocess.run(
        [sys.executable, "-m", "app.worker.healthcheck"],
        cwd=BACKEND_DIR,
        env=bad_redis_env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert bad_redis_proc.returncode == 1

    bad_pg_env = dict(env)
    bad_pg_env["DATABASE_URL"] = (
        f"postgresql+asyncpg://fieldshift:{env['DB_PASSWORD']}@127.0.0.1:{_free_unbound_port()}/fieldshift"
    )
    bad_pg_proc = subprocess.run(
        [sys.executable, "-m", "app.worker.healthcheck"],
        cwd=BACKEND_DIR,
        env=bad_pg_env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert bad_pg_proc.returncode == 1


@pytest.mark.asyncio
async def test_reaper_housekeeping_expired_guests_old_idempotency_and_nonleader(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m11_ctx
    now = datetime.now(UTC)

    expired_hash = hash_token("gst_expired_m11_token_001")
    active_hash = hash_token("gst_active_m11_token_002")

    async with sessionmaker() as db:
        db.add_all(
            [
                GuestSession(
                    guest_token=expired_hash,
                    demo_location_id=GUELMA_LOCATION_ID,
                    expires_at=now - timedelta(hours=1),
                ),
                GuestSession(
                    guest_token=active_hash,
                    demo_location_id=GUELMA_LOCATION_ID,
                    expires_at=now + timedelta(hours=24),
                ),
            ]
        )
        await db.flush()

        old_farm = Farm(
            guest_session_token=expired_hash,
            farm_name="Expired Guest Farm",
            country="Algeria",
            region="Guelma",
        )
        live_farm = Farm(
            guest_session_token=active_hash,
            farm_name="Active Guest Farm",
            country="Algeria",
            region="Guelma",
        )
        db.add_all([old_farm, live_farm])
        await db.flush()

        gz_empty = gzip.compress(b"{}")
        db.add_all(
            [
                AnalysisRequest(
                    request_id=f"req_{uuid.uuid4().hex}",
                    farm_id=live_farm.id,
                    idempotency_key="old-idemp-key-25h",
                    status="ok",
                    schema_version="5.0",
                    dataset_version=DEFAULT_DATASET_VERSION,
                    catalog_version="2026.11-test",
                    language="en",
                    quota_units=4,
                    input_hash="a" * 64,
                    full_input_hash="a" * 64,
                    input_snapshot_gz=gz_empty,
                    warnings=[],
                    created_at=now - timedelta(hours=25),
                ),
                AnalysisRequest(
                    request_id=f"req_{uuid.uuid4().hex}",
                    farm_id=live_farm.id,
                    idempotency_key="fresh-idemp-key-2h",
                    status="ok",
                    schema_version="5.0",
                    dataset_version=DEFAULT_DATASET_VERSION,
                    catalog_version="2026.11-test",
                    language="en",
                    quota_units=4,
                    input_hash="b" * 64,
                    full_input_hash="b" * 64,
                    input_snapshot_gz=gz_empty,
                    warnings=[],
                    created_at=now - timedelta(hours=2),
                ),
            ]
        )
        await db.commit()

    runner = WorkerRunner(
        settings=settings,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=MLProviderManager(settings),
        worker_id="reaper-leader-test",
    )

    # Hold `hashtext('reaper')` advisory lock on another session -> non-leader skips sweep.
    async with engine.connect() as contender_conn:
        lock_res = await contender_conn.execute(
            text("SELECT pg_try_advisory_lock(hashtext('reaper'))")
        )
        got = bool(lock_res.scalar_one())
        assert got is True
        try:
            assert await runner.reap_stale_jobs_once() == 0
            async with sessionmaker() as db:
                rem_expired = await db.scalar(
                    select(func.count())
                    .select_from(GuestSession)
                    .where(GuestSession.guest_token == expired_hash)
                )
                assert rem_expired == 1
        finally:
            await contender_conn.execute(text("SELECT pg_advisory_unlock(hashtext('reaper'))"))

    # Leader acquires lock -> purges expired guest + cascades its farm, clears >24h key only.
    assert await runner.reap_stale_jobs_once() == 0
    async with sessionmaker() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(GuestSession)
                .where(GuestSession.guest_token == expired_hash)
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Farm)
                .where(Farm.guest_session_token == expired_hash)
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(GuestSession)
                .where(GuestSession.guest_token == active_hash)
            )
            == 1
        )
        old_key_val = await db.scalar(
            select(AnalysisRequest.idempotency_key).where(AnalysisRequest.input_hash == "a" * 64)
        )
        fresh_key_val = await db.scalar(
            select(AnalysisRequest.idempotency_key).where(AnalysisRequest.input_hash == "b" * 64)
        )
        assert old_key_val is None
        assert fresh_key_val == "fresh-idemp-key-2h"


class _SlowGateAdapter(MLAdapter):
    """Test adapter that signals entry and waits briefly before returning valid mock output."""

    provider_name: ProviderKind = "real_ml"

    def __init__(self, *, entered: asyncio.Event, delay_s: float = 0.35) -> None:
        self._entered = entered
        self._delay_s = delay_s
        self._inner = MockMLAdapter()

    async def get_health(self) -> MLHealthResult:
        res = await self._inner.get_health()
        return MLHealthResult(
            reachable=True,
            status=res.status,
            ml_engine_version=res.ml_engine_version,
            dataset_versions_supported=res.dataset_versions_supported,
            provider="real_ml",
        )

    async def get_catalog(self) -> MLCatalogPayload:
        return await self._inner.get_catalog()

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        self._entered.set()
        await asyncio.sleep(self._delay_s)
        return await self._inner.analyze(
            payload, idempotency_key=idempotency_key, compress=compress
        )


@pytest.mark.asyncio
async def test_worker_graceful_shutdown_drains_inflight_job_and_clears_heartbeat(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, engine, sessionmaker, redis_client = m11_ctx

    # Sync catalog cleanly via advisory-locked helper too (`catalog_sync`).
    async with _running_mock_ml_server(settings) as mock_url:
        live_settings = _system_settings(ML_SERVICE_URL=mock_url, ML_PROVIDER_MODE="real")
        live_mgr = MLProviderManager(live_settings, redis_client=redis_client)
        try:
            ver = await sync_catalog_under_advisory_lock(
                engine=engine,
                sessionmaker=sessionmaker,
                ml_manager=live_mgr,
            )
            assert ver is not None
        finally:
            await live_mgr.aclose()

    entered = asyncio.Event()
    slow_adapter = _SlowGateAdapter(entered=entered, delay_s=0.35)
    slow_mgr = MLProviderManager(
        _system_settings(ML_PROVIDER_MODE="real"),
        real_adapter=slow_adapter,
        redis_client=redis_client,
    )

    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            ip = "198.51.100.77"
            g_resp = await client.post(
                "/api/v1/auth/guest",
                headers={"X-Forwarded-For": ip},
                json={"demo_location_id": GUELMA_LOCATION_ID},
            )
            assert g_resp.status_code == 201
            headers = {"X-Guest-Token": g_resp.json()["guest_token"], "X-Forwarded-For": ip}

            farm_resp = await client.post(
                "/api/v1/farms",
                headers=headers,
                json={"farm_name": "Graceful Farm", "country": "Algeria", "region": "Guelma"},
            )
            assert farm_resp.status_code == 201
            farm_id = farm_resp.json()["farm_id"]

            fld_resp = await client.post(
                f"/api/v1/farms/{farm_id}/fields",
                headers=headers,
                json={
                    "field_id": "F1",
                    "field_name": "Drain Parcel",
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
            assert fld_resp.status_code == 201

            sub_resp = await client.post(
                "/api/v1/analysis",
                headers=headers,
                json={
                    "farm_id": farm_id,
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
                },
            )
            assert sub_resp.status_code == 202
            req_id = sub_resp.json()["request_id"]

        worker_id = "worker-drain-01"
        runner = WorkerRunner(
            settings=_system_settings(ML_PROVIDER_MODE="real"),
            engine=engine,
            sessionmaker=sessionmaker,
            redis_client=redis_client,
            ml_manager=slow_mgr,
            worker_concurrency=1,
            poll_interval_seconds=0.05,
            reap_interval_seconds=0.2,
            worker_id=worker_id,
        )
        stop_event = asyncio.Event()
        run_task = asyncio.create_task(runner.run(stop_event))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5.0)
            assert await redis_client.get(f"{WORKER_HEARTBEAT_REDIS_PREFIX}{worker_id}") is not None
            assert await count_active_workers(redis_client) == 1

            # Trigger clean shutdown while slow ML job is still running in flight.
            stop_event.set()
            await asyncio.wait_for(run_task, timeout=5.0)
        finally:
            if not run_task.done():
                stop_event.set()
                with contextlib.suppress(BaseException):
                    await asyncio.wait_for(run_task, timeout=2.0)
            await slow_mgr.aclose()

        # Worker heartbeat removed and in-flight job committed `ok` cleanly!
        assert await redis_client.get(f"{WORKER_HEARTBEAT_REDIS_PREFIX}{worker_id}") is None
        assert await count_active_workers(redis_client) == 0

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            status_resp = await client.get(f"/api/v1/analysis/requests/{req_id}", headers=headers)
            assert status_resp.status_code == 200
            assert status_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_live_json_log_redaction_and_zero_pii_secret_leakage(
    m11_ctx: tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession], redis_async.Redis],
) -> None:
    settings, _engine, _sessionmaker, _redis_client = m11_ctx

    email = "secret.farmer@example.com"
    full_name = "Karim Benali SensitiveName"
    password = "SuperSecretPassword!9876"

    log_buf = io.StringIO()
    orig_stdout = sys.stdout
    sys.stdout = log_buf
    try:
        configure_logging("INFO")
        app = create_app(settings=settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                reg_resp = await client.post(
                    "/api/v1/auth/register",
                    headers={"X-Forwarded-For": "198.51.100.51"},
                    json={"email": email, "password": password, "full_name": full_name},
                )
                assert reg_resp.status_code == 201
                access_tok = reg_resp.json()["access_token"]
                refresh_tok = reg_resp.json()["refresh_token"]

                g_resp = await client.post(
                    "/api/v1/auth/guest",
                    headers={"X-Forwarded-For": "198.51.100.52"},
                    json={"demo_location_id": GUELMA_LOCATION_ID},
                )
                assert g_resp.status_code == 201
                guest_tok = g_resp.json()["guest_token"]

                me_resp = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {access_tok}"},
                )
                assert me_resp.status_code == 200

                h_resp = await client.get("/api/v1/health?check=dependencies")
                assert h_resp.status_code == 200

                audit_logger = structlog.get_logger("app.audit_probe")
                await audit_logger.ainfo(
                    "auth_attempt_audit",
                    email=email,
                    full_name=full_name,
                    password=password,
                    authorization=f"Bearer {access_tok}",
                    token=refresh_tok,
                    nested={
                        "x-guest-token": guest_tok,
                        "x-ml-api-key": settings.ML_SERVICE_API_KEY,
                        "jwt_secret": settings.JWT_SECRET_KEY,
                        "inline": f"Bearer {access_tok} user={email} tok={guest_tok}",
                    },
                )
                await audit_logger.awarning(
                    "ml_call_header_probe",
                    headers={"Authorization": f"Bearer {access_tok}"},
                )
    finally:
        sys.stdout = orig_stdout
        configure_logging("INFO")

    raw_output = log_buf.getvalue()
    lines = [line for line in raw_output.splitlines() if line.strip()]
    json_lines = [line for line in lines if line.lstrip().startswith("{")]
    assert len(json_lines) >= 3
    for line in json_lines:
        parsed = json.loads(line)
        assert isinstance(parsed, dict)
        assert "event" in parsed

    for forbidden in (
        email,
        full_name,
        password,
        access_tok,
        refresh_tok,
        guest_tok,
        settings.JWT_SECRET_KEY,
        settings.ML_SERVICE_API_KEY,
    ):
        assert forbidden not in raw_output, f"Sensitive secret/PII leaked in logs: {forbidden!r}"
