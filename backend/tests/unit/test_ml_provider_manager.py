"""Unit tests for MLProviderManager strict no-mock production guard and provider selection."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import Settings
from app.ml_client import (
    ML_ACTIVE_PROVIDER,
    ML_PROVIDER_STATUS_REDIS_KEY,
    MLAdapter,
    MLContractError,
    MLHealthResult,
    MLInsufficientDataError,
    MLProviderManager,
    MLTimeoutError,
    MLTransportError,
    MLUpstreamServerError,
    MockMLAdapter,
    publish_provider_status,
    read_provider_status,
)
from app.ml_client.base import ProviderKind
from app.schemas.catalog import MLCatalogPayload

TEST_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class _FakeRealAdapter(MLAdapter):
    """Configurable stub representing the real HTTP adapter in unit tests."""

    def __init__(self) -> None:
        self.health = MLHealthResult(
            reachable=True,
            status="ok",
            ml_engine_version="agro-ml-2.1.0",
            dataset_versions_supported=("2026.11-guelma-v1",),
            provider="real_ml",
        )
        self.analyze_error: Exception | None = None
        self.catalog_error: Exception | None = None
        self.closed = False
        self._catalog_json = json.loads(
            (TEST_FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
        )
        self._output_json = json.loads(
            (TEST_FIXTURES_DIR / "fixture_9_3_output.json").read_text(encoding="utf-8")
        )

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
        _ = payload, idempotency_key, compress
        if self.analyze_error is not None:
            raise self.analyze_error
        return dict(self._output_json)

    async def get_catalog(self) -> MLCatalogPayload:
        if self.catalog_error is not None:
            raise self.catalog_error
        return MLCatalogPayload.model_validate(self._catalog_json)

    async def get_health(self) -> MLHealthResult:
        return self.health

    async def aclose(self) -> None:
        self.closed = True


class _InMemoryStatusRedis:
    def __init__(self, *, fail_set: bool = False, fail_get: bool = False) -> None:
        self.store: dict[str, tuple[Any, int | None]] = {}
        self.fail_set = fail_set
        self.fail_get = fail_get

    async def set(self, name: str, value: Any, ex: int | None = None) -> bool:
        if self.fail_set:
            raise RedisConnectionError("redis set failed")
        self.store[name] = (value, ex)
        return True

    async def get(self, name: str) -> Any:
        if self.fail_get:
            raise RedisConnectionError("redis get failed")
        pair = self.store.get(name)
        return pair[0] if pair is not None else None


def _active_provider(manager: MLProviderManager) -> ProviderKind:
    return manager.active_provider_name


def _build_settings(
    *,
    app_env: Literal["production", "development", "test"] = "test",
    mode: Literal["auto", "real", "mock"] = "auto",
    interval_s: int = 30,
) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV=app_env,
        ML_PROVIDER_MODE=mode,
        ML_HEALTH_CHECK_INTERVAL_SECONDS=interval_s,
        DATABASE_URL="postgresql+asyncpg://fieldshift:secret@db:5432/fieldshift",
        DB_PASSWORD="secret",
        ML_DATASET_DB_URL="postgresql://ml_reader:secret2@db:5432/fieldshift",
        ML_READER_PASSWORD="secret2",
        JWT_SECRET_KEY="jwt-secret-key-for-tests-32-chars!!",
        ML_SERVICE_API_KEY="ml-secret-key",
    )


def test_production_forbids_mock_mode_in_settings_and_manager() -> None:
    with pytest.raises((ValidationError, ValueError), match="ML_PROVIDER_MODE"):
        _build_settings(app_env="production", mode="mock")

    # Even if Settings validation is bypassed with model_construct, MLProviderManager rejects mock.
    bypassed = Settings.model_construct(
        APP_ENV="production",
        ML_PROVIDER_MODE="mock",
        ML_HEALTH_CHECK_INTERVAL_SECONDS=30,
        ML_SERVICE_URL="https://ml.fieldshift.internal",
        ML_SERVICE_API_KEY="ml-secret-key",
        ML_SERVICE_PREVIOUS_API_KEY="",
        ML_TIMEOUT_SECONDS=60,
        ML_CATALOG_TIMEOUT_SECONDS=5,
        ML_HEALTH_TIMEOUT_SECONDS=3,
    )
    with pytest.raises(ValueError, match="forbidden when APP_ENV='production'"):
        MLProviderManager(bypassed, real_adapter=_FakeRealAdapter())


@pytest.mark.asyncio
async def test_production_and_real_mode_never_instantiate_or_fallback_to_mock() -> None:
    sample_input = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )

    for settings in (
        _build_settings(app_env="production", mode="auto"),
        _build_settings(app_env="test", mode="real"),
    ):
        real_stub = _FakeRealAdapter()
        real_stub.health = MLHealthResult(reachable=False, status="unavailable", error="OFFLINE")
        real_stub.catalog_error = MLTransportError("Real ML unreachable")
        real_stub.analyze_error = MLTransportError("Real ML unreachable")

        # Even if a caller attempts to inject a MockMLAdapter, manager strips it to None.
        manager = MLProviderManager(
            settings,
            real_adapter=real_stub,
            mock_adapter=MockMLAdapter(),
        )
        assert manager.allows_mock is False
        assert manager.mock_adapter is None
        assert manager.active_provider_name == "real_ml"

        health = await manager.get_health()
        assert health.reachable is False
        assert manager.active_provider_name == "real_ml"

        with pytest.raises(MLTransportError):
            await manager.get_catalog()
        with pytest.raises(MLTransportError):
            await manager.analyze(sample_input, idempotency_key="strict-real")
        await manager.aclose()
        assert real_stub.closed is True


@pytest.mark.asyncio
async def test_dev_auto_selects_mock_when_offline_and_promotes_to_real_on_health_recovery(
) -> None:
    sample_input = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    settings = _build_settings(app_env="development", mode="auto", interval_s=30)
    real_stub = _FakeRealAdapter()
    real_stub.health = MLHealthResult(reachable=False, status="unavailable", error="ECONNREFUSED")
    redis_stub = _InMemoryStatusRedis()

    manager = MLProviderManager(
        settings,
        real_adapter=real_stub,
        mock_adapter=MockMLAdapter(),
        redis_client=redis_stub,
    )
    assert manager.allows_mock is True
    assert manager.mock_adapter is not None

    before_mock_count = ML_ACTIVE_PROVIDER.labels(provider="mock_ml")._value.get()
    before_real_count = ML_ACTIVE_PROVIDER.labels(provider="real_ml")._value.get()

    catalog = await manager.get_catalog()
    assert len(catalog.crops) == 6
    assert _active_provider(manager) == "mock_ml"
    assert ML_ACTIVE_PROVIDER.labels(provider="mock_ml")._value.get() == before_mock_count + 1

    snap = await read_provider_status(redis_stub)
    assert snap is not None
    assert snap.provider == "mock_ml"
    assert snap.reachable is True
    assert redis_stub.store[ML_PROVIDER_STATUS_REDIS_KEY][1] == 60

    # Real ML comes online; stale probe promotes manager back to real_ml.
    real_stub.health = MLHealthResult(
        reachable=True,
        status="ok",
        ml_engine_version="agro-ml-2.1.0",
        dataset_versions_supported=("2026.11-guelma-v1",),
        provider="real_ml",
    )
    manager._last_probe_at = datetime.now(UTC) - timedelta(seconds=31)
    result = await manager.analyze(sample_input, idempotency_key="promoted-real")
    assert result["request_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert _active_provider(manager) == "real_ml"
    assert ML_ACTIVE_PROVIDER.labels(provider="real_ml")._value.get() == before_real_count + 1

    # CRITICAL (`IMPL-008`): ZERO silent in-flight fallback when active real_ml fails.
    for exc in (
        MLContractError("400 bad payload"),
        MLInsufficientDataError("422 insufficient"),
        MLUpstreamServerError("500 internal error", status_code=500),
        MLTimeoutError("60s timeout"),
    ):
        real_stub.analyze_error = exc
        with pytest.raises(type(exc)):
            await manager.analyze(sample_input, idempotency_key=f"no-fallback-{type(exc).__name__}")
        assert _active_provider(manager) == "real_ml"


@pytest.mark.asyncio
async def test_publish_and_read_provider_status_resilience() -> None:
    redis_ok = _InMemoryStatusRedis()
    sample_health = MLHealthResult(
        reachable=True,
        status="ok",
        ml_engine_version="agro-ml-2.1.0",
        dataset_versions_supported=("2026.11-guelma-v1",),
        provider="real_ml",
    )
    ok = await publish_provider_status(
        redis_ok,
        health=sample_health,
        provider="real_ml",
        ttl_seconds=60,
    )
    assert ok is True
    snap = await read_provider_status(redis_ok)
    assert snap is not None
    assert snap.provider == "real_ml"
    assert snap.ml_engine_version == "agro-ml-2.1.0"
    assert snap.dataset_versions_supported == ("2026.11-guelma-v1",)

    assert await read_provider_status(None) is None

    # Corrupt payload & Redis errors never crash callers.
    redis_ok.store[ML_PROVIDER_STATUS_REDIS_KEY] = (b"not-json", 60)
    assert await read_provider_status(redis_ok) is None

    redis_broken = _InMemoryStatusRedis(fail_set=True, fail_get=True)
    assert (
        await publish_provider_status(
            redis_broken,
            health=sample_health,
            provider="real_ml",
            ttl_seconds=60,
        )
        is False
    )
    assert await read_provider_status(redis_broken) is None
