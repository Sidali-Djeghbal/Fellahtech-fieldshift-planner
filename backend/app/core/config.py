"""Application settings loading all 40 normative env vars and 7 Companion Settings."""

from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Authoritative list of the 40 environment variables from ENDPOINTS Section C.
NORMATIVE_ENV_VARS: tuple[str, ...] = (
    "DATABASE_URL",
    "DB_PASSWORD",
    "REDIS_URL",
    "ML_DATASET_DB_URL",
    "ML_READER_PASSWORD",
    "ML_DB_STATEMENT_TIMEOUT_MS",
    "ML_DB_CONNECTION_LIMIT",
    "JWT_SECRET_KEY",
    "JWT_PREVIOUS_SECRET_KEY",
    "JWT_ACCESS_EXPIRES_SECONDS",
    "JWT_REFRESH_EXPIRES_SECONDS",
    "GUEST_SESSION_DAYS",
    "GUEST_MAX_FARMS",
    "GUEST_MAX_FIELDS_PER_FARM",
    "GUEST_MAX_ANALYSES",
    "GUEST_MAX_ML_REFUNDS",
    "GUEST_BURST_PER_MIN",
    "GUEST_CREATE_PER_IP_HOUR",
    "RATE_LIMIT_CRUD_PER_MIN",
    "RATE_LIMIT_ANALYSIS_PER_HOUR",
    "ANALYSIS_PER_IP_HOUR",
    "ML_SERVICE_URL",
    "ML_SERVICE_API_KEY",
    "ML_SERVICE_PREVIOUS_API_KEY",
    "ML_TIMEOUT_SECONDS",
    "ML_MAX_RETRIES",
    "ML_MAX_PAYLOAD_BYTES",
    "ML_CATALOG_TIMEOUT_SECONDS",
    "ML_HEALTH_TIMEOUT_SECONDS",
    "ML_CATALOG_SYNC_HOURS",
    "ML_CIRCUIT_BREAKER_THRESHOLD",
    "ML_BREAKER_COOLDOWN_SECONDS",
    "ML_MAX_CONCURRENT_REQUESTS",
    "DEGRADED_MODE_MAX_AGE_HOURS",
    "ALLOW_SYNC_WAIT",
    "SYNC_WAIT_TIMEOUT_SECONDS",
    "WORKER_CONCURRENCY",
    "JOB_LEASE_SECONDS",
    "MAX_JOB_ATTEMPTS",
    "CORS_ALLOWED_ORIGINS",
)

# Isolated non-spec runtime safety & tuning knobs (IMPL-018).
COMPANION_SETTINGS_VARS: tuple[str, ...] = (
    "APP_ENV",
    "ML_PROVIDER_MODE",
    "ML_HEALTH_CHECK_INTERVAL_SECONDS",
    "SEM04_NUMERIC_TOLERANCE",
    "TRUSTED_PROXY_CIDRS",
    "REDIS_FAIL_CLOSED",
    "ML_DATASET_OWNER_ROLE",
)


class Settings(BaseSettings):
    """Fail-fast backend configuration adhering to ENDPOINTS Section C & IMPL-018."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Normative Database & Redis (7) ---
    DATABASE_URL: str
    DB_PASSWORD: str
    REDIS_URL: str = "redis://redis:6379/0"
    ML_DATASET_DB_URL: str
    ML_READER_PASSWORD: str
    # TODO(OQ-D4): Confirm production SQL timeout & connection cap with ML/DBA owners.
    ML_DB_STATEMENT_TIMEOUT_MS: int = Field(default=5000, ge=100)
    ML_DB_CONNECTION_LIMIT: int = Field(default=10, ge=1)

    # --- Normative Auth & JWT Keys (4) ---
    JWT_SECRET_KEY: str
    JWT_PREVIOUS_SECRET_KEY: str = ""
    JWT_ACCESS_EXPIRES_SECONDS: int = Field(default=3600, ge=60)
    JWT_REFRESH_EXPIRES_SECONDS: int = Field(default=2592000, ge=300)

    # --- Normative Guest Quotas & Redis Rate Limits (10) ---
    GUEST_SESSION_DAYS: int = Field(default=7, ge=1)
    GUEST_MAX_FARMS: int = Field(default=3, ge=1)
    GUEST_MAX_FIELDS_PER_FARM: int = Field(default=5, ge=1)
    GUEST_MAX_ANALYSES: int = Field(default=10, ge=1)
    GUEST_MAX_ML_REFUNDS: int = Field(default=3, ge=0)
    GUEST_BURST_PER_MIN: int = Field(default=30, ge=1)
    GUEST_CREATE_PER_IP_HOUR: int = Field(default=5, ge=1)
    RATE_LIMIT_CRUD_PER_MIN: int = Field(default=60, ge=1)
    RATE_LIMIT_ANALYSIS_PER_HOUR: int = Field(default=10, ge=1)
    ANALYSIS_PER_IP_HOUR: int = Field(default=15, ge=1)

    # --- Normative External ML Service (9) ---
    ML_SERVICE_URL: str = "https://ml.fieldshift.internal"
    ML_SERVICE_API_KEY: str
    ML_SERVICE_PREVIOUS_API_KEY: str = ""
    ML_TIMEOUT_SECONDS: int = Field(default=60, ge=1)
    ML_MAX_RETRIES: int = Field(default=1, ge=0)
    # TODO(OQ-4): Confirm exact uncompressed payload cap with ML team.
    ML_MAX_PAYLOAD_BYTES: int = Field(default=524288, ge=1024)
    ML_CATALOG_TIMEOUT_SECONDS: int = Field(default=5, ge=1)
    ML_HEALTH_TIMEOUT_SECONDS: int = Field(default=3, ge=1)
    ML_CATALOG_SYNC_HOURS: int = Field(default=6, ge=1)

    # --- Normative Breaker, Degraded Mode & Worker (9) ---
    ML_CIRCUIT_BREAKER_THRESHOLD: int = Field(default=5, ge=1)
    ML_BREAKER_COOLDOWN_SECONDS: int = Field(default=30, ge=1)
    ML_MAX_CONCURRENT_REQUESTS: int = Field(default=8, ge=1)
    # TODO(OQ-8): Confirm max degraded replay age and ADR-7 deprecation window.
    DEGRADED_MODE_MAX_AGE_HOURS: int = Field(default=72, ge=1)
    ALLOW_SYNC_WAIT: bool = False
    SYNC_WAIT_TIMEOUT_SECONDS: int = Field(default=58, ge=1)
    WORKER_CONCURRENCY: int = Field(default=4, ge=1)
    JOB_LEASE_SECONDS: int = Field(default=90, ge=10)
    MAX_JOB_ATTEMPTS: int = Field(default=2, ge=1)

    # --- Normative CORS (1 -> total 40) ---
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"

    # --- Companion Runtime Settings (7 — IMPL-018) ---
    APP_ENV: Literal["production", "development", "test"] = "production"
    ML_PROVIDER_MODE: Literal["auto", "real", "mock"] = "auto"
    ML_HEALTH_CHECK_INTERVAL_SECONDS: int = Field(default=30, ge=5)
    # TODO(OQ-3): Confirm numeric comparison tolerance with ML & Agronomy owners.
    SEM04_NUMERIC_TOLERANCE: float = Field(default=0.001, ge=0.0)
    TRUSTED_PROXY_CIDRS: str = ""
    REDIS_FAIL_CLOSED: bool = True
    ML_DATASET_OWNER_ROLE: str = ""

    @field_validator(
        "DB_PASSWORD",
        "ML_READER_PASSWORD",
        "JWT_SECRET_KEY",
        "ML_SERVICE_API_KEY",
    )
    @classmethod
    def _validate_non_empty_secret(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Required secret configuration variable must be non-empty")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the 'postgresql+asyncpg://' asyncpg driver")
        return value

    @field_validator("REDIS_URL")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        if not (value.startswith("redis://") or value.startswith("rediss://")):
            raise ValueError("REDIS_URL must start with 'redis://' or 'rediss://'")
        return value

    @field_validator("ML_DATASET_DB_URL")
    @classmethod
    def _validate_ml_dataset_url(cls, value: str) -> str:
        if not (value.startswith("postgresql://") or value.startswith("postgres://")):
            raise ValueError("ML_DATASET_DB_URL must use a PostgreSQL connection URI")
        return value

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def _validate_trusted_proxy_cidrs(cls, value: str) -> str:
        for raw_cidr in value.split(","):
            cidr = raw_cidr.strip()
            if cidr:
                ipaddress.ip_network(cidr, strict=False)
        return value

    @model_validator(mode="after")
    def _validate_production_safety(self) -> Settings:
        if self.APP_ENV == "production":
            if self.ML_PROVIDER_MODE == "mock":
                raise ValueError(
                    "ML_PROVIDER_MODE='mock' is forbidden when APP_ENV='production' (IMPL-008)"
                )
            if not self.ML_SERVICE_URL.startswith("https://"):
                raise ValueError(
                    "ML_SERVICE_URL must use 'https://' when APP_ENV='production'"
                )
        elif not (
            self.ML_SERVICE_URL.startswith("https://")
            or self.ML_SERVICE_URL.startswith("http://")
        ):
            raise ValueError("ML_SERVICE_URL must start with 'http://' or 'https://'")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins cleanly."""
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_proxy_networks(self) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
        """Parse validated CIDR allowlist for X-Forwarded-For trust."""
        return tuple(
            ipaddress.ip_network(cidr.strip(), strict=False)
            for cidr in self.TRUSTED_PROXY_CIDRS.split(",")
            if cidr.strip()
        )

    @property
    def worker_db_pool_min_total(self) -> int:
        """Minimum worker connection pool capacity preventing bulkhead starvation (E4)."""
        return self.WORKER_CONCURRENCY + self.ML_MAX_CONCURRENT_REQUESTS + 4
