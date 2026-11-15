from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import asyncpg  # type: ignore[import-untyped]
import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.db.seed import seed_reference_data
from app.db.session import create_db_engine, create_sessionmaker
from app.models import (
    Base,
    DatasetRegistry,
    DemoLocation,
    Farm,
    Field,
    FieldCropHistory,
    MlBreakerState,
    User,
)
from tests.conftest import build_test_env, to_asyncpg_dsn

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

_POSTGIS_SYSTEM_TABLES: frozenset[str] = frozenset(
    {
        "spatial_ref_sys",
        "geometry_columns",
        "geography_columns",
        "raster_columns",
        "raster_overviews",
    }
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_EXE = Path(sys.executable).with_name(
    "alembic.exe" if Path(sys.executable).suffix == ".exe" else "alembic"
)


@asynccontextmanager
async def _superuser_conn(env: dict[str, str]) -> AsyncIterator[Any]:
    conn = await asyncpg.connect(to_asyncpg_dsn(env["DATABASE_URL"]))
    try:
        yield conn
    finally:
        await conn.close()


def _run_alembic(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(ALEMBIC_EXE), *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert env["ML_READER_PASSWORD"] not in result.stdout
    assert env["ML_READER_PASSWORD"] not in result.stderr
    return result


async def test_alembic_roundtrip_and_exact_13_table_schema() -> None:
    env = build_test_env()

    # Clean upgrade -> downgrade -> upgrade cycle proves full reversibility.
    _run_alembic(["upgrade", "head"], env)
    _run_alembic(["downgrade", "base"], env)

    async with _superuser_conn(env) as conn:
        remaining_tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            """
        )
        remaining_names = {row["tablename"] for row in remaining_tables} - _POSTGIS_SYSTEM_TABLES
        assert remaining_names == {"alembic_version"}

        dataset_schema_exists = await conn.fetchval(
            "SELECT EXISTS ("
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'dataset'"
            ")"
        )
        assert dataset_schema_exists is False

    _run_alembic(["upgrade", "head"], env)
    # Re-running upgrade head must succeed idempotently.
    _run_alembic(["upgrade", "head"], env)
    # ORM MetaData must report zero drift against live migrated database.
    _run_alembic(["check"], env)

    async with _superuser_conn(env) as conn:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        public_tables = (
            {row["tablename"] for row in rows} - _POSTGIS_SYSTEM_TABLES - {"alembic_version"}
        )
        assert public_tables == EXPECTED_PUBLIC_TABLES

        # Compare every SQLAlchemy ORM model column name and nullability against live DB.
        db_cols = await conn.fetch(
            """
            SELECT table_name, column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            """
        )
        by_table: dict[str, dict[str, bool]] = {}
        for row in db_cols:
            tname = str(row["table_name"])
            if tname not in EXPECTED_PUBLIC_TABLES:
                continue
            by_table.setdefault(tname, {})[str(row["column_name"])] = (
                str(row["is_nullable"]) == "YES"
            )

        for table_name, sa_table in Base.metadata.tables.items():
            expected_cols = {col.name: bool(col.nullable) for col in sa_table.columns}
            assert by_table.get(table_name) == expected_cols, (
                f"Column mismatch on public.{table_name}"
            )

        # Verify critical indexes exist in public.
        index_rows = await conn.fetch(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        )
        index_names = {str(row["indexname"]) for row in index_rows}
        expected_indexes = {
            "uq_users_email_lower",
            "idx_refresh_tokens_user_family",
            "idx_demo_locations_boundary",
            "idx_fields_geom_point",
            "idx_fields_geom_polygon",
            "uq_dataset_registry_single_active",
            "uq_analysis_idempotency",
            "idx_analysis_queue",
            "idx_one_selected_strategy_per_field",
        }
        assert expected_indexes.issubset(index_names)


async def test_minimal_seeds_and_empty_crop_catalog() -> None:
    env = build_test_env()
    _run_alembic(["upgrade", "head"], env)

    # Run async seed helper directly twice to verify idempotency and conflict safety.
    engine = create_async_engine(env["DATABASE_URL"])
    try:
        async with engine.begin() as sa_conn:
            await seed_reference_data(sa_conn)
            await seed_reference_data(sa_conn)
    finally:
        await engine.dispose()

    async with _superuser_conn(env) as conn:
        catalog_count = await conn.fetchval("SELECT COUNT(*) FROM public.crop_catalog")
        assert catalog_count == 0, "crop_catalog must stay unseeded so GET /catalog -> 502 works"

        demo = await conn.fetchrow("SELECT * FROM public.demo_locations WHERE id = 1")
        assert demo is not None
        assert demo["code"] == "guelma"
        assert "default_parcel_id" not in demo
        assert demo["is_active"] is True

        # Verify (lon=7.52, lat=36.52) is inside Guelma boundary while Algiers fails.
        inside = await conn.fetchval(
            """
            SELECT ST_Covers(boundary, ST_SetSRID(ST_MakePoint(7.52, 36.52), 4326))
            FROM public.demo_locations
            WHERE id = 1
            """
        )
        outside = await conn.fetchval(
            """
            SELECT ST_Covers(boundary, ST_SetSRID(ST_MakePoint(3.0588, 36.7538), 4326))
            FROM public.demo_locations
            WHERE id = 1
            """
        )
        assert inside is True
        assert outside is False

        # Verify sequence was bumped past explicit id=1 so inserting a new location gets id=2.
        tr = conn.transaction()
        await tr.start()
        try:
            next_id = await conn.fetchval(
                """
                INSERT INTO public.demo_locations (
                    code, name, country, region, boundary
                )
                VALUES (
                    'seq_probe', 'Probe', 'Algeria', 'Guelma',
                    ST_Multi(ST_SetSRID(ST_MakeEnvelope(7.1, 36.1, 7.2, 36.2, 4326), 4326))
                )
                RETURNING id
                """
            )
            assert next_id >= 2
        finally:
            await tr.rollback()

        dataset_row = await conn.fetchrow(
            "SELECT dataset_version, is_active FROM public.dataset_registry WHERE is_active = true"
        )
        assert dataset_row is not None
        assert dataset_row["dataset_version"] == "2026.11-guelma-v1"

        breaker = await conn.fetchrow("SELECT * FROM public.ml_breaker_state WHERE id = 1")
        assert breaker is not None
        assert breaker["state"] == "closed"
        assert breaker["consecutive_failures"] == 0


async def test_constraint_enforcement_and_pitfall10_no_history_catalog_fk() -> None:
    env = build_test_env()
    _run_alembic(["upgrade", "head"], env)

    async with _superuser_conn(env) as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            user_id = await conn.fetchval(
                """
                INSERT INTO public.users (email, password_hash, full_name)
                VALUES ('Amina@Example.DZ', 'argon2id_hash', 'Amina Benali')
                RETURNING id
                """
            )
            # Case-insensitive email uniqueness (uq_users_email_lower)
            sp1 = conn.transaction()
            await sp1.start()
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    """
                    INSERT INTO public.users (email, password_hash, full_name)
                    VALUES ('amina@example.dz', 'hash2', 'Amina 2')
                    """
                )
            await sp1.rollback()

            # Ownership XOR check on farms (both null fails, both set fails)
            sp2 = conn.transaction()
            await sp2.start()
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    """
                    INSERT INTO public.farms (farm_name, country, region)
                    VALUES ('Orphan Farm', 'Algeria', 'Guelma')
                    """
                )
            await sp2.rollback()

            farm_id = await conn.fetchval(
                """
                INSERT INTO public.farms (user_id, farm_name, country, region)
                VALUES ($1, 'Ferme Nord', 'Algeria', 'Guelma')
                RETURNING id
                """,
                user_id,
            )
            field_id = await conn.fetchval(
                """
                INSERT INTO public.fields (
                    farm_id, external_field_id, field_name, geom_point, area_hectares,
                    soil_type, water_availability, water_source, irrigation_system
                )
                VALUES (
                    $1, 'F1', 'Parcelle 1',
                    ST_SetSRID(ST_MakePoint(7.52, 36.52), 4326), 12.5,
                    'loamy', 'moderate', 'well', 'drip'
                )
                RETURNING id
                """,
                farm_id,
            )

            # Pitfall #10: crop_catalog is empty, yet field_crop_history accepts any crop_id!
            await conn.execute(
                """
                INSERT INTO public.field_crop_history (
                    field_id, season, year, catalog_version, crop_id
                )
                VALUES ($1, 'winter', 2025, '1.0.0', 'wheat_durum')
                """,
                field_id,
            )

            # Empty crop identifier must fail chk_history_crop_identifier
            sp3 = conn.transaction()
            await sp3.start()
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    """
                    INSERT INTO public.field_crop_history (field_id, season, year)
                    VALUES ($1, 'summer', 2025)
                    """,
                    field_id,
                )
            await sp3.rollback()

            # Analysis result + selections partial unique constraint
            req_id = "req_001"
            await conn.execute(
                """
                INSERT INTO public.analysis_requests (
                    request_id, farm_id, schema_version, catalog_version,
                    dataset_version, language, input_hash, full_input_hash, status
                )
                VALUES (
                    $1, $2, '5.0', '1.0.0', '2026.11-guelma-v1', 'en',
                    repeat('a', 64), repeat('b', 64), 'ok'
                )
                """,
                req_id,
                farm_id,
            )
            analysis_id = await conn.fetchval(
                """
                INSERT INTO public.analysis_results (
                    request_id, status, dataset_version_used,
                    ml_engine_version, result_json, validation_passed
                )
                VALUES ($1, 'ok', '2026.11-guelma-v1', 'ml-1.0', '{}'::jsonb, true)
                RETURNING analysis_id
                """,
                req_id,
            )
            assert re.match(r"^analysis_[0-9a-f]{12}$", analysis_id)

            # Multiple 'rejected' allowed for same (analysis_id, field_id)
            await conn.execute(
                """
                INSERT INTO public.analysis_selections
                    (analysis_id, field_id, strategy_id, selection_status)
                VALUES
                    ($1, 'F1', 'S1', 'rejected'),
                    ($1, 'F1', 'S2', 'rejected'),
                    ($1, 'F1', 'S3', 'selected')
                """,
                analysis_id,
            )

            # Second 'selected' for same (analysis_id, field_id) violates partial unique index
            sp4 = conn.transaction()
            await sp4.start()
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    """
                    INSERT INTO public.analysis_selections
                        (analysis_id, field_id, strategy_id, selection_status)
                    VALUES ($1, 'F1', 'S4', 'selected')
                    """,
                    analysis_id,
                )
            await sp4.rollback()
        finally:
            await tr.rollback()


async def test_ml_reader_isolation_and_owner_role_default_privileges() -> None:
    base_env = build_test_env()
    parsed = urlparse(to_asyncpg_dsn(base_env["DATABASE_URL"]))
    db_host = parsed.hostname or "127.0.0.1"
    db_port = parsed.port or 5432
    db_name = parsed.path.lstrip("/") or "fieldshift"
    owner_role = "ml_dataset_owner_test"

    # Pre-create simulated external ML dataset loader role before running migration with it.
    async with _superuser_conn(base_env) as su_conn:
        await su_conn.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{owner_role}') THEN
                    CREATE ROLE {owner_role} NOLOGIN;
                END IF;
            END
            $$;
            """
        )

    env = build_test_env(ml_dataset_owner_role=owner_role)
    _run_alembic(["downgrade", "base"], env)
    _run_alembic(["upgrade", "head"], env)

    try:
        async with _superuser_conn(env) as su_conn:
            # Verify connection limit & statement_timeout configured on ml_reader
            conn_limit = await su_conn.fetchval(
                "SELECT rolconnlimit FROM pg_roles WHERE rolname = 'ml_reader'"
            )
            assert conn_limit == int(env["ML_DB_CONNECTION_LIMIT"])

            # Create a dataset table as the migration user AND one as ML_DATASET_OWNER_ROLE
            await su_conn.execute("DROP TABLE IF EXISTS dataset.soil_features")
            await su_conn.execute(
                "CREATE TABLE dataset.soil_features (zone text PRIMARY KEY, ph numeric)"
            )
            await su_conn.execute(
                "INSERT INTO dataset.soil_features (zone, ph) VALUES ('guelma', 7.1)"
            )

            await su_conn.execute(f"GRANT USAGE, CREATE ON SCHEMA dataset TO {owner_role}")
            await su_conn.execute("DROP TABLE IF EXISTS dataset.owner_created_grid")
            async with su_conn.transaction():
                await su_conn.execute(f"SET LOCAL ROLE {owner_role}")
                await su_conn.execute(
                    "CREATE TABLE dataset.owner_created_grid "
                    "(cell_id int PRIMARY KEY, rainfall_mm int)"
                )
                await su_conn.execute(
                    "INSERT INTO dataset.owner_created_grid (cell_id, rainfall_mm) VALUES (1, 540)"
                )

        ml_conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            user="ml_reader",
            password=env["ML_READER_PASSWORD"],
            database=db_name,
        )
        try:
            timeout_setting = await ml_conn.fetchval("SHOW statement_timeout")
            assert timeout_setting in {"5s", "5000ms"}

            # 1. ml_reader CAN read both migration-created and owner-role-created dataset tables.
            ph_val = await ml_conn.fetchval(
                "SELECT ph FROM dataset.soil_features WHERE zone = 'guelma'"
            )
            assert float(ph_val) == pytest.approx(7.1)

            rain_val = await ml_conn.fetchval(
                "SELECT rainfall_mm FROM dataset.owner_created_grid WHERE cell_id = 1"
            )
            assert rain_val == 540

            # 2. ml_reader CANNOT mutate dataset tables or create objects in dataset/public.
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ml_conn.execute(
                    "INSERT INTO dataset.soil_features (zone, ph) VALUES ('hack', 1.0)"
                )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ml_conn.execute("CREATE TABLE dataset.should_fail (id int)")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ml_conn.execute("CREATE TABLE public.should_fail (id int)")

            # 3. ml_reader CANNOT read any PII/state table in public.*
            protected_tables = (
                "users",
                "refresh_tokens",
                "demo_locations",
                "farms",
                "analysis_results",
            )
            for protected_table in protected_tables:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await ml_conn.fetch(f"SELECT 1 FROM public.{protected_table} LIMIT 1")
        finally:
            await ml_conn.close()
    finally:
        async with _superuser_conn(base_env) as su_conn:
            await su_conn.execute("DROP TABLE IF EXISTS dataset.owner_created_grid")
            await su_conn.execute("DROP TABLE IF EXISTS dataset.soil_features")
            await su_conn.execute(f"REVOKE ALL ON SCHEMA dataset FROM {owner_role}")
            await su_conn.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner_role} "
                "IN SCHEMA dataset REVOKE SELECT ON TABLES FROM ml_reader"
            )
            await su_conn.execute(f"DROP ROLE IF EXISTS {owner_role}")
        # Ensure DB is cleanly reset using default settings without test owner role.
        _run_alembic(["downgrade", "base"], base_env)
        _run_alembic(["upgrade", "head"], base_env)


async def test_orm_models_async_session_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    env = build_test_env()
    for key, val in env.items():
        if key in Settings.model_fields:
            monkeypatch.setenv(key, val)
    settings = Settings()

    _run_alembic(["upgrade", "head"], env)

    engine = create_db_engine(settings, role="api")
    session_factory = create_sessionmaker(engine)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                async with session_factory(bind=conn) as session:
                    guelma = await session.scalar(
                        select(DemoLocation).where(DemoLocation.code == "guelma")
                    )
                    dataset = await session.scalar(
                        select(DatasetRegistry).where(DatasetRegistry.is_active.is_(True))
                    )
                    breaker = await session.scalar(
                        select(MlBreakerState).where(MlBreakerState.id == 1)
                    )
                    assert guelma is not None and guelma.id == 1
                    assert dataset is not None and dataset.dataset_version == "2026.11-guelma-v1"
                    assert breaker is not None and breaker.state == "closed"

                    user = User(
                        email="orm_test@example.dz",
                        password_hash="argon2_stub",
                        full_name="ORM Test User",
                        preferred_lang="fr",
                    )
                    session.add(user)
                    await session.flush()

                    farm = Farm(
                        user_id=user.id,
                        farm_name="Ferme ORM",
                        country="Algeria",
                        region="Guelma",
                    )
                    session.add(farm)
                    await session.flush()

                    field = Field(
                        farm_id=farm.id,
                        external_field_id="F1",
                        field_name="Parcelle ORM",
                        geom_point=WKTElement("POINT(7.52 36.52)", srid=4326),
                        area_hectares=Decimal("12.5000"),
                        soil_type="loamy",
                        water_availability="moderate",
                        water_source="well",
                        irrigation_system="drip",
                    )
                    session.add(field)
                    await session.flush()

                    history = FieldCropHistory(
                        field_id=field.id,
                        season="winter",
                        year=2025,
                        catalog_version="1.0.0",
                        crop_id="wheat_durum",
                    )
                    session.add(history)
                    await session.flush()

                    assert history.id is not None
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()
