"""MLProviderManager enforcing production no-mock isolation & Redis status sharing."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

import structlog
from prometheus_client import Counter
from redis.exceptions import RedisError

from app.core.config import Settings
from app.ml_client.base import (
    MLAdapter,
    MLHealthResult,
    MLProviderSnapshot,
    ProviderKind,
)
from app.ml_client.mock_adapter import MockMLAdapter
from app.ml_client.real_adapter import RealMLAdapter
from app.schemas.catalog import MLCatalogPayload

ML_PROVIDER_STATUS_REDIS_KEY = "ml:provider_status"


@runtime_checkable
class AsyncRedisStatusStore(Protocol):
    """Minimal async Redis protocol for shared `ml:provider_status` snapshots."""

    def get(self, name: str) -> Any: ...

    def set(self, name: str, value: Any, ex: int | None = None) -> Any: ...


ML_ACTIVE_PROVIDER = Counter(
    "ml_active_provider",
    "Total ML operations dispatched per active provider (`real_ml` or `mock_ml`)",
    labelnames=("provider",),
)


async def publish_provider_status(
    redis_client: AsyncRedisStatusStore,
    *,
    health: MLHealthResult,
    provider: ProviderKind,
    ttl_seconds: int,
    checked_at: datetime | None = None,
) -> bool:
    """Publish active ML provider health snapshot to Redis `ml:provider_status` (`IMPL-008`)."""
    ts = checked_at or datetime.now(UTC)
    payload = {
        "provider": provider,
        "reachable": health.reachable,
        "status": health.status,
        "ml_engine_version": health.ml_engine_version,
        "dataset_versions_supported": list(health.dataset_versions_supported),
        "checked_at": ts.isoformat(),
    }
    logger = structlog.get_logger("app.ml_client.manager")
    try:
        await redis_client.set(
            ML_PROVIDER_STATUS_REDIS_KEY,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            ex=max(1, int(ttl_seconds)),
        )
        return True
    except RedisError as exc:
        await logger.awarning(
            "ml_provider_status_redis_publish_failed",
            error_type=type(exc).__name__,
        )
        return False


async def read_provider_status(
    redis_client: AsyncRedisStatusStore | None,
) -> MLProviderSnapshot | None:
    """Read cross-container active ML provider snapshot from Redis `ml:provider_status`."""
    if redis_client is None:
        return None
    logger = structlog.get_logger("app.ml_client.manager")
    try:
        raw = await redis_client.get(ML_PROVIDER_STATUS_REDIS_KEY)
    except RedisError as exc:
        await logger.awarning(
            "ml_provider_status_redis_read_failed",
            error_type=type(exc).__name__,
        )
        return None

    if raw is None:
        return None
    try:
        text_val = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        data = json.loads(text_val)
        provider_raw = str(data.get("provider"))
        provider: ProviderKind = "mock_ml" if provider_raw == "mock_ml" else "real_ml"
        checked_at = datetime.fromisoformat(str(data["checked_at"]))
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        datasets = data.get("dataset_versions_supported", [])
        return MLProviderSnapshot(
            provider=provider,
            reachable=bool(data.get("reachable", False)),
            status=str(data.get("status", "unknown")),
            ml_engine_version=(
                str(data["ml_engine_version"])
                if isinstance(data.get("ml_engine_version"), str)
                else None
            ),
            dataset_versions_supported=(
                tuple(str(item) for item in datasets if isinstance(item, str))
                if isinstance(datasets, list)
                else ()
            ),
            checked_at=checked_at,
        )
    except (ValueError, KeyError, TypeError):
        return None


class MLProviderManager:
    """Centralized coordinator selecting `RealMLAdapter` vs `MockMLAdapter` without silent masks."""

    def __init__(
        self,
        settings: Settings,
        *,
        real_adapter: MLAdapter | None = None,
        mock_adapter: MLAdapter | None = None,
        redis_client: AsyncRedisStatusStore | None = None,
    ) -> None:
        if settings.APP_ENV == "production" and settings.ML_PROVIDER_MODE == "mock":
            raise ValueError(
                "ML_PROVIDER_MODE='mock' is forbidden when APP_ENV='production' (IMPL-008)"
            )

        self._settings = settings
        self._redis_client = redis_client
        self._logger = structlog.get_logger("app.ml_client.manager")
        self._probe_lock = asyncio.Lock()

        self._allows_mock = (
            settings.APP_ENV in ("development", "test")
            and settings.ML_PROVIDER_MODE != "real"
        )
        self._real_adapter: MLAdapter = (
            real_adapter if real_adapter is not None else RealMLAdapter(settings)
        )
        self._mock_adapter: MLAdapter | None = (
            (mock_adapter if mock_adapter is not None else MockMLAdapter())
            if self._allows_mock
            else None
        )

        self._active_provider: ProviderKind | None
        if settings.APP_ENV == "production" or settings.ML_PROVIDER_MODE == "real":
            self._active_provider = "real_ml"
        elif settings.ML_PROVIDER_MODE == "mock":
            self._active_provider = "mock_ml"
        else:
            self._active_provider = None

        self._last_probe_at: datetime | None = None
        self._last_health: MLHealthResult | None = None

    @property
    def allows_mock(self) -> bool:
        """Whether MockMLAdapter instantiation/selection is allowed under current env/mode."""
        return self._allows_mock

    @property
    def active_provider_name(self) -> ProviderKind:
        """Return currently selected provider name (`real_ml` when unprobed/strict)."""
        if self._active_provider is not None:
            return self._active_provider
        return "real_ml"

    @property
    def real_adapter(self) -> MLAdapter:
        """Return the concrete real ML adapter."""
        return self._real_adapter

    @property
    def mock_adapter(self) -> MLAdapter | None:
        """Return the mock ML adapter (strictly None in production or `mode=real`)."""
        return self._mock_adapter

    @property
    def last_health(self) -> MLHealthResult | None:
        """Return cached latest health probe result if available."""
        return self._last_health

    def _is_probe_stale(self, now: datetime) -> bool:
        if self._last_probe_at is None:
            return True
        interval = timedelta(seconds=self._settings.ML_HEALTH_CHECK_INTERVAL_SECONDS)
        return (now - self._last_probe_at) >= interval

    async def refresh_provider_status(
        self,
        *,
        publish_redis: bool = True,
        redis_client: AsyncRedisStatusStore | None = None,
    ) -> MLHealthResult:
        """Probe `/v1/health`, update selected provider in auto mode, and publish Redis snapshot."""
        async with self._probe_lock:
            now = datetime.now(UTC)
            previous = self._active_provider

            if self._settings.APP_ENV == "production" or self._settings.ML_PROVIDER_MODE == "real":
                self._active_provider = "real_ml"
                health = await self._real_adapter.get_health()
            elif self._settings.ML_PROVIDER_MODE == "mock":
                assert self._mock_adapter is not None
                self._active_provider = "mock_ml"
                health = await self._mock_adapter.get_health()
            else:
                real_health = await self._real_adapter.get_health()
                if real_health.reachable:
                    self._active_provider = "real_ml"
                    health = real_health
                else:
                    assert self._mock_adapter is not None
                    self._active_provider = "mock_ml"
                    health = await self._mock_adapter.get_health()

            self._last_probe_at = now
            self._last_health = health

            if previous != self._active_provider:
                await self._logger.ainfo(
                    "ml_provider_selected",
                    previous_provider=previous,
                    ml_provider=self._active_provider,
                    app_env=self._settings.APP_ENV,
                    ml_provider_mode=self._settings.ML_PROVIDER_MODE,
                    real_reachable=(
                        health.reachable if self._active_provider == "real_ml" else False
                    ),
                )

            target_redis = redis_client if redis_client is not None else self._redis_client
            if publish_redis and target_redis is not None:
                await publish_provider_status(
                    target_redis,
                    health=health,
                    provider=self._active_provider,
                    ttl_seconds=2 * self._settings.ML_HEALTH_CHECK_INTERVAL_SECONDS,
                    checked_at=now,
                )

            return health

    async def _resolve_adapter_for_call(self) -> MLAdapter:
        if self._settings.APP_ENV == "production" or self._settings.ML_PROVIDER_MODE == "real":
            return self._real_adapter

        if self._settings.ML_PROVIDER_MODE == "mock":
            assert self._mock_adapter is not None
            return self._mock_adapter

        # Development/test `auto` mode only switches on periodic readiness probes.
        now = datetime.now(UTC)
        if self._active_provider is None or self._is_probe_stale(now):
            await self.refresh_provider_status(publish_redis=self._redis_client is not None)

        if self._active_provider == "mock_ml":
            assert self._mock_adapter is not None
            return self._mock_adapter
        return self._real_adapter

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        """Dispatch `POST /v1/analyze` to active provider with ZERO silent in-flight fallback."""
        adapter = await self._resolve_adapter_for_call()
        provider = adapter.provider_name
        ML_ACTIVE_PROVIDER.labels(provider=provider).inc()
        await self._logger.ainfo(
            "ml_request_dispatch",
            operation="analyze",
            ml_provider=provider,
        )
        return await adapter.analyze(
            payload,
            idempotency_key=idempotency_key,
            compress=compress,
        )

    async def get_catalog(self) -> MLCatalogPayload:
        """Dispatch `GET /v1/catalog` to active provider with ZERO silent in-flight fallback."""
        adapter = await self._resolve_adapter_for_call()
        provider = adapter.provider_name
        ML_ACTIVE_PROVIDER.labels(provider=provider).inc()
        await self._logger.ainfo(
            "ml_request_dispatch",
            operation="catalog",
            ml_provider=provider,
        )
        return await adapter.get_catalog()

    async def get_health(self) -> MLHealthResult:
        """Return health from the strict/active adapter (updating auto-selection if applicable)."""
        return await self.refresh_provider_status(publish_redis=False)

    async def aclose(self) -> None:
        """Close underlying real/mock adapters cleanly during application shutdown."""
        await self._real_adapter.aclose()
        if self._mock_adapter is not None:
            await self._mock_adapter.aclose()
