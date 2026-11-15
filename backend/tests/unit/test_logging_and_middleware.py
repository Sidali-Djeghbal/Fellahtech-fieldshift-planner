"""Unit tests for secret/PII logging redaction, DB pool sizing, and FastAPI middleware."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.core.logging import redact_sensitive_data
from app.db.session import calculate_pool_budget
from app.main import create_app


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://fieldshift:secret@db:5432/fieldshift",
        DB_PASSWORD="secret",
        ML_DATASET_DB_URL="postgresql://ml_reader:secret2@db:5432/fieldshift",
        ML_READER_PASSWORD="secret2",
        JWT_SECRET_KEY="jwt-secret-key-for-tests-32-chars!!",
        ML_SERVICE_API_KEY="ml-secret-key",
        CORS_ALLOWED_ORIGINS="http://localhost:5173",
    )


def test_logging_redacts_secrets_and_info_pii() -> None:
    nested: dict[str, str] = {
        "x-ml-api-key": "super-secret-ml-key",
        "header": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        "note": "Contact farmer@example.com with gst_0123456789abcdef01234567",
    }
    event: dict[str, object] = {
        "event": "auth_attempt",
        "password": "my-clear-password",
        "guest_token": "gst_0123456789abcdef01234567",
        "email": "farmer@example.com",
        "nested": nested,
        "request_id": "req-123",
    }
    sanitized = redact_sensitive_data(None, "info", dict(event))
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["guest_token"] == "***REDACTED***"
    assert sanitized["email"] == "***REDACTED***"
    sanitized_nested = sanitized["nested"]
    assert isinstance(sanitized_nested, dict)
    assert sanitized_nested["x-ml-api-key"] == "***REDACTED***"
    assert sanitized_nested["header"] == "Bearer ***REDACTED***"
    assert "farmer@example.com" not in str(sanitized_nested["note"])
    assert "0123456789abcdef" not in str(sanitized_nested["note"])
    assert sanitized["request_id"] == "req-123"


def test_worker_pool_budget_exceeds_concurrency_plus_bulkhead() -> None:
    settings = _test_settings()
    pool_size, max_overflow = calculate_pool_budget(settings, role="worker")
    assert pool_size == settings.WORKER_CONCURRENCY + settings.ML_MAX_CONCURRENT_REQUESTS
    assert pool_size + max_overflow >= settings.worker_db_pool_min_total


@pytest.mark.asyncio
async def test_request_id_and_cors_middleware() -> None:
    app = create_app(settings=_test_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp_auto = await client.get(
            "/api/v1/health?check=live",
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp_auto.status_code == 200
        assert "x-request-id" in resp_auto.headers
        assert resp_auto.headers.get("access-control-allow-origin") == "http://localhost:5173"

        resp_echo = await client.get(
            "/api/v1/health?check=live",
            headers={"X-Request-Id": "req-custom-abc-123"},
        )
        assert resp_echo.status_code == 200
        assert resp_echo.headers["x-request-id"] == "req-custom-abc-123"


@pytest.mark.asyncio
async def test_lifespan_initializes_settings() -> None:
    settings = _test_settings()
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        assert app.state.settings.APP_ENV == "test"

