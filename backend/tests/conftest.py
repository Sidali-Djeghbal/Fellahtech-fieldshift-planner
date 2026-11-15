from __future__ import annotations

import os
import re


def build_test_env(*, ml_dataset_owner_role: str = "") -> dict[str, str]:
    """Build deterministic environment settings for local/CI PostGIS and Redis tests."""
    db_password = os.getenv("TEST_DB_PASSWORD", os.getenv("DB_PASSWORD", "fieldshift_test_pw"))
    ml_reader_pw = os.getenv(
        "TEST_ML_READER_PASSWORD",
        os.getenv("ML_READER_PASSWORD", "ml_reader_test_secret_987"),
    )
    db_host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    db_port = os.getenv("TEST_DB_PORT", "5432")
    db_user = os.getenv("TEST_DB_USER", "fieldshift")
    db_name = os.getenv("TEST_DB_NAME", "fieldshift")

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": (
                f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            ),
            "DB_PASSWORD": db_password,
            "ML_DATASET_DB_URL": (
                f"postgresql://ml_reader:{ml_reader_pw}@{db_host}:{db_port}/{db_name}"
            ),
            "ML_READER_PASSWORD": ml_reader_pw,
            "ML_DB_STATEMENT_TIMEOUT_MS": os.getenv("ML_DB_STATEMENT_TIMEOUT_MS", "5000"),
            "ML_DB_CONNECTION_LIMIT": os.getenv("ML_DB_CONNECTION_LIMIT", "10"),
            "JWT_SECRET_KEY": "test_jwt_secret_key_for_migrations",
            "ML_SERVICE_API_KEY": "test_ml_api_key_for_migrations",
            "ML_DATASET_OWNER_ROLE": ml_dataset_owner_role,
        }
    )
    return env


def to_asyncpg_dsn(sqlalchemy_url: str) -> str:
    """Convert `postgresql+asyncpg://` DSN to raw `postgresql://` DSN for asyncpg."""
    return re.sub(r"^postgresql\+asyncpg://", "postgresql://", sqlalchemy_url)
