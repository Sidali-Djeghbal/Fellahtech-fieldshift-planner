from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.models import Base

EXPECTED_PUBLIC_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "refresh_tokens",
        "demo_locations",
        "guest_sessions",
        "farms",
        "fields",
        "field_crop_history",
        "crop_catalog",
        "dataset_registry",
        "analysis_requests",
        "analysis_results",
        "analysis_selections",
        "ml_breaker_state",
    }
)


def test_orm_metadata_contains_exact_13_public_tables() -> None:
    assert frozenset(Base.metadata.tables.keys()) == EXPECTED_PUBLIC_TABLES


def test_alembic_offline_sql_renders_cleanly_without_secret_leak() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_exe = Path(sys.executable).with_name(
        "alembic.exe" if os.name == "nt" else "alembic"
    )
    sentinel_pw = "super_secret_ml_reader_pw_do_not_leak"
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": "postgresql+asyncpg://fieldshift:devpw@127.0.0.1:5432/fieldshift",
            "DB_PASSWORD": "devpw",
            "ML_DATASET_DB_URL": "postgresql://ml_reader:x@127.0.0.1:5432/fieldshift",
            "ML_READER_PASSWORD": sentinel_pw,
            "JWT_SECRET_KEY": "jwt-dev-secret-key",
            "ML_SERVICE_API_KEY": "ml-dev-secret-key",
            "ML_DATASET_OWNER_ROLE": "",
        }
    )

    up_proc = subprocess.run(
        [str(alembic_exe), "upgrade", "head", "--sql"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "CREATE SCHEMA IF NOT EXISTS dataset" in up_proc.stdout
    assert "uq_users_email_lower" in up_proc.stdout
    assert "idx_one_selected_strategy_per_field" in up_proc.stdout
    assert sentinel_pw not in up_proc.stdout
    assert sentinel_pw not in up_proc.stderr

    down_proc = subprocess.run(
        [str(alembic_exe), "downgrade", "head:base", "--sql"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "DROP TABLE IF EXISTS public.ml_breaker_state" in down_proc.stdout
    assert "DROP SCHEMA IF EXISTS dataset CASCADE" in down_proc.stdout
    assert sentinel_pw not in down_proc.stdout
    assert sentinel_pw not in down_proc.stderr
