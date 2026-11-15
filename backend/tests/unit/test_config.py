"""Unit tests for Settings: 40 normative vars, 7 Companion Settings, and production fail-fast."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import (
    COMPANION_SETTINGS_VARS,
    NORMATIVE_ENV_VARS,
    Settings,
)


def _base_required_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql+asyncpg://fieldshift:strong-db-pass@db:5432/fieldshift",
        "DB_PASSWORD": "strong-db-pass",
        "ML_DATASET_DB_URL": "postgresql://ml_reader:strong-ml-reader-pass@db:5432/fieldshift",
        "ML_READER_PASSWORD": "strong-ml-reader-pass",
        "JWT_SECRET_KEY": "a" * 32,
        "ML_SERVICE_API_KEY": "ml-shared-secret-key",
    }


def test_settings_field_parity_40_normative_plus_7_companion() -> None:
    assert len(NORMATIVE_ENV_VARS) == 40
    assert len(COMPANION_SETTINGS_VARS) == 7
    assert set(NORMATIVE_ENV_VARS).isdisjoint(set(COMPANION_SETTINGS_VARS))
    assert set(Settings.model_fields.keys()) == set(NORMATIVE_ENV_VARS) | set(
        COMPANION_SETTINGS_VARS
    )


def test_production_fail_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(NORMATIVE_ENV_VARS) + list(COMPANION_SETTINGS_VARS):
        monkeypatch.delenv(key, raising=False)
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)
    assert settings.APP_ENV == "production"
    assert settings.ML_PROVIDER_MODE == "auto"
    assert settings.REDIS_FAIL_CLOSED is True
    assert settings.REDIS_URL == "redis://redis:6379/0"
    assert settings.ML_SERVICE_URL == "https://ml.fieldshift.internal"
    assert settings.SEM04_NUMERIC_TOLERANCE == 0.001
    assert settings.worker_db_pool_min_total == 16


def test_production_rejects_mock_ml_mode_with_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ML_PROVIDER_MODE", "mock")

    with pytest.raises(ValidationError, match="APP_ENV='production'"):
        Settings(_env_file=None)


def test_production_rejects_non_https_ml_service_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.local:8090")

    with pytest.raises(ValidationError, match="https://"):
        Settings(_env_file=None)


def test_dev_mode_allows_http_and_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ML_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ML_SERVICE_URL", "http://mock-ml:8090")

    settings = Settings(_env_file=None)
    assert settings.APP_ENV == "development"
    assert settings.ML_PROVIDER_MODE == "mock"
    assert settings.ML_SERVICE_URL == "http://mock-ml:8090"


@pytest.mark.parametrize(
    "secret_key",
    ["DB_PASSWORD", "ML_READER_PASSWORD", "JWT_SECRET_KEY", "ML_SERVICE_API_KEY"],
)
def test_empty_required_secret_rejected(
    monkeypatch: pytest.MonkeyPatch,
    secret_key: str,
) -> None:
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(secret_key, "   ")

    with pytest.raises(ValidationError, match="non-empty"):
        Settings(_env_file=None)


def test_trusted_proxy_cidrs_and_cors_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8, 172.16.0.0/12")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173, https://app.example.com")

    settings = Settings(_env_file=None)
    assert len(settings.trusted_proxy_networks) == 2
    assert settings.cors_origins_list == ["http://localhost:5173", "https://app.example.com"]

    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "not-a-cidr")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("env_var", "bad_value"),
    [
        ("DATABASE_URL", "sqlite+aiosqlite:///tmp.db"),
        ("REDIS_URL", "http://redis:6379/0"),
        ("ML_DATASET_DB_URL", "mysql://ml_reader:pass@db/fieldshift"),
        ("ML_SERVICE_URL", "ftp://ml.fieldshift.internal"),
    ],
)
def test_invalid_connection_schemes_rejected(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    bad_value: str,
) -> None:
    for key, value in _base_required_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv(env_var, bad_value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

