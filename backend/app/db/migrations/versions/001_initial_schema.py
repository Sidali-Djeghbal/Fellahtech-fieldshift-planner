"""Initial FieldShift public schema (13 tables), dataset schema, and ml_reader role.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-15
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

from app.core.config import Settings

_logger = logging.getLogger("alembic.runtime.migration")

revision: str = "001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SAFE_PG_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Exact DDL per FieldShift Planner — ENDPOINTS api & Database Specification.md §A.4
_CREATE_STATEMENTS: tuple[str, ...] = (
    # 1. users
    """
    CREATE TABLE public.users (
        id             bigserial PRIMARY KEY,
        email          text NOT NULL,
        password_hash  text NOT NULL,
        full_name      text NOT NULL,
        preferred_lang text NOT NULL DEFAULT 'en' CHECK (preferred_lang IN ('en', 'fr', 'ar')),
        created_at     timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE UNIQUE INDEX uq_users_email_lower ON public.users (LOWER(email))",
    # 2. refresh_tokens
    """
    CREATE TABLE public.refresh_tokens (
        id         bigserial PRIMARY KEY,
        user_id    bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
        family_id  uuid NOT NULL,
        token_hash text NOT NULL UNIQUE CHECK (char_length(token_hash) = 64),
        used_at    timestamptz NULL,
        revoked_at timestamptz NULL,
        expires_at timestamptz NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX idx_refresh_tokens_user_family ON public.refresh_tokens (user_id, family_id)",
    # 3. demo_locations (Wilaya of Guelma boundary + pre-designated unstudied parcel metadata)
    """
    CREATE TABLE public.demo_locations (
        id                     bigserial PRIMARY KEY,
        code                   text NOT NULL UNIQUE,
        name                   text NOT NULL,
        country                text NOT NULL,
        region                 text NOT NULL,
        boundary               geometry(MultiPolygon, 4326) NOT NULL,
        default_parcel_id      text NOT NULL DEFAULT 'F1',
        default_parcel_name    text NOT NULL,
        default_parcel_lat     numeric(9, 6) NOT NULL,
        default_parcel_lon     numeric(9, 6) NOT NULL,
        default_parcel_area_ha numeric(10, 2) NOT NULL CHECK (default_parcel_area_ha > 0),
        is_active              boolean NOT NULL DEFAULT true,
        created_at             timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX idx_demo_locations_boundary ON public.demo_locations USING GIST (boundary)",
    # 4. guest_sessions
    """
    CREATE TABLE public.guest_sessions (
        guest_token      text PRIMARY KEY CHECK (char_length(guest_token) = 64),
        demo_location_id bigint NOT NULL REFERENCES public.demo_locations(id) ON DELETE RESTRICT,
        created_at       timestamptz NOT NULL DEFAULT now(),
        expires_at       timestamptz NOT NULL
    )
    """,
    # 5. farms
    """
    CREATE TABLE public.farms (
        id                  bigserial PRIMARY KEY,
        user_id             bigint NULL REFERENCES public.users(id) ON DELETE CASCADE,
        guest_session_token text NULL REFERENCES public.guest_sessions(guest_token)
                            ON DELETE CASCADE,
        farm_name           text NOT NULL CHECK (char_length(farm_name) BETWEEN 1 AND 120),
        country             text NOT NULL CHECK (char_length(country) BETWEEN 1 AND 80),
        region              text NOT NULL CHECK (char_length(region) BETWEEN 1 AND 80),
        commune             text NULL CHECK (commune IS NULL OR char_length(commune) <= 120),
        created_at          timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT chk_farms_single_owner
            CHECK ((user_id IS NOT NULL) <> (guest_session_token IS NOT NULL))
    )
    """,
    # 6. fields
    """
    CREATE TABLE public.fields (
        id                        bigserial PRIMARY KEY,
        farm_id                   bigint NOT NULL REFERENCES public.farms(id) ON DELETE CASCADE,
        external_field_id         text NOT NULL CHECK (
                                      char_length(external_field_id) BETWEEN 1 AND 64
                                  ),
        field_name                text NOT NULL CHECK (char_length(field_name) BETWEEN 1 AND 120),
        is_unverified_demo_parcel boolean NOT NULL DEFAULT false,
        geom_point                geometry(Point, 4326) NOT NULL,
        geom_polygon              geometry(Polygon, 4326) NULL,
        area_hectares             numeric(10, 4) NOT NULL
                                  CHECK (area_hectares > 0 AND area_hectares <= 10000),
        soil_type                 text NOT NULL CHECK (
                                      soil_type IN ('sandy', 'clay', 'loamy', 'silty', 'unknown')
                                  ),
        soil_source               text NOT NULL DEFAULT 'unknown'
                                  CHECK (soil_source IN ('farmer', 'unknown')),
        soil_ph                   numeric(4, 2) NULL
                                  CHECK (soil_ph IS NULL OR (soil_ph >= 3.0 AND soil_ph <= 11.0)),
        organic_matter_percent    numeric(5, 2) NULL CHECK (
                                      organic_matter_percent IS NULL
                                      OR (
                                          organic_matter_percent >= 0
                                          AND organic_matter_percent <= 100
                                      )
                                  ),
        soil_test_date            date NULL,
        water_availability        text NOT NULL CHECK (
                                      water_availability IN (
                                          'abundant', 'moderate', 'limited',
                                          'very_limited', 'rainfed_only'
                                      )
                                  ),
        water_source              text NOT NULL CHECK (
                                      water_source IN (
                                          'rainwater', 'groundwater', 'well', 'dam_reservoir',
                                          'irrigation_network', 'other', 'unknown'
                                      )
                                  ),
        water_source_other        text NULL CHECK (
                                      water_source_other IS NULL
                                      OR char_length(water_source_other) <= 200
                                  ),
        irrigation_system         text NOT NULL CHECK (
                                      irrigation_system IN (
                                          'rainfed', 'drip', 'sprinkler',
                                          'flood', 'other', 'unknown'
                                      )
                                  ),
        elevation_m               numeric(7, 2) NULL CHECK (
                                      elevation_m IS NULL OR (elevation_m BETWEEN -500 AND 9000)
                                  ),
        created_at                timestamptz NOT NULL DEFAULT now(),
        updated_at                timestamptz NOT NULL DEFAULT now(),
        UNIQUE (farm_id, external_field_id)
    )
    """,
    "CREATE INDEX idx_fields_geom_point   ON public.fields USING GIST (geom_point)",
    "CREATE INDEX idx_fields_geom_polygon ON public.fields USING GIST (geom_polygon)",
    # 7. field_crop_history (deliberately no FK to crop_catalog - Pitfall #10)
    """
    CREATE TABLE public.field_crop_history (
        id                     bigserial PRIMARY KEY,
        field_id               bigint NOT NULL REFERENCES public.fields(id) ON DELETE CASCADE,
        season                 text NOT NULL CHECK (
                                   season IN ('spring', 'summer', 'autumn', 'winter')
                               ),
        year                   integer NOT NULL CHECK (year BETWEEN 1980 AND 2100),
        planting_month         smallint NULL CHECK (
                                   planting_month IS NULL OR (planting_month BETWEEN 1 AND 12)
                               ),
        catalog_version        text NULL,
        crop_id                text NULL CHECK (
                                   crop_id IS NULL OR char_length(crop_id) BETWEEN 1 AND 64
                               ),
        crop_name_raw          text NULL CHECK (
                                   crop_name_raw IS NULL
                                   OR char_length(crop_name_raw) BETWEEN 1 AND 120
                               ),
        yield_tons_per_hectare numeric(8, 3) NULL CHECK (
                                   yield_tons_per_hectare IS NULL
                                   OR yield_tons_per_hectare >= 0
                               ),
        notes                  text NULL CHECK (notes IS NULL OR char_length(notes) <= 500),
        UNIQUE (field_id, year, season),
        CONSTRAINT chk_history_crop_identifier
            CHECK (crop_id IS NOT NULL OR crop_name_raw IS NOT NULL)
    )
    """,
    # 8. crop_catalog
    """
    CREATE TABLE public.crop_catalog (
        catalog_version text NOT NULL,
        crop_id         text NOT NULL,
        names           jsonb NOT NULL,
        category        text NOT NULL CHECK (
                            category IN (
                                'cereals', 'legumes', 'oilseeds', 'vegetables',
                                'forage', 'cover_crops', 'fallow'
                            )
                        ),
        roles           text[] NOT NULL,
        family          text NOT NULL,
        synced_at       timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (catalog_version, crop_id)
    )
    """,
    # 9. dataset_registry
    """
    CREATE TABLE public.dataset_registry (
        dataset_version    text PRIMARY KEY CHECK (char_length(dataset_version) BETWEEN 1 AND 64),
        source_description text NOT NULL,
        coverage_notes     text NOT NULL,
        is_active          boolean NOT NULL DEFAULT false,
        loaded_at          timestamptz NOT NULL DEFAULT now(),
        notes              text NULL
    )
    """,
    """
    CREATE UNIQUE INDEX uq_dataset_registry_single_active
        ON public.dataset_registry (is_active)
        WHERE is_active = true
    """,
    # 10. analysis_requests
    """
    CREATE TABLE public.analysis_requests (
        request_id        text PRIMARY KEY,
        farm_id           bigint NOT NULL REFERENCES public.farms(id) ON DELETE CASCADE,
        idempotency_key   text NULL,
        parent_request_id text NULL REFERENCES public.analysis_requests(request_id)
                          ON DELETE SET NULL,
        schema_version    text NOT NULL,
        catalog_version   text NOT NULL,
        dataset_version   text NOT NULL REFERENCES public.dataset_registry(dataset_version)
                          ON DELETE RESTRICT,
        language          text NOT NULL CHECK (language IN ('en', 'fr', 'ar')),
        quota_units       smallint NOT NULL DEFAULT 4 CHECK (quota_units IN (0, 1, 4)),
        input_hash        text NOT NULL CHECK (char_length(input_hash) = 64),
        full_input_hash   text NOT NULL CHECK (char_length(full_input_hash) = 64),
        input_snapshot_gz bytea NULL,
        warnings          jsonb NOT NULL DEFAULT '[]'::jsonb,
        status            text NOT NULL CHECK (
                              status IN (
                                  'pending', 'running', 'ok', 'partial', 'failed', 'cancelled'
                              )
                          ),
        error_code        text NULL,
        lease_until       timestamptz NULL,
        heartbeat_at      timestamptz NULL,
        attempts          smallint NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        cancelled_at      timestamptz NULL,
        sent_at           timestamptz NULL,
        received_at       timestamptz NULL,
        duration_ms       integer NULL CHECK (duration_ms IS NULL OR duration_ms >= 0),
        created_at        timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE UNIQUE INDEX uq_analysis_idempotency
        ON public.analysis_requests (farm_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
    """,
    """
    CREATE INDEX idx_analysis_queue
        ON public.analysis_requests (status, lease_until, created_at)
    """,
    # 11. analysis_results (write-once raw ML JSON)
    """
    CREATE TABLE public.analysis_results (
        id                   bigserial PRIMARY KEY,
        analysis_id          text NOT NULL UNIQUE DEFAULT (
                                 'analysis_'
                                 || substr(replace(gen_random_uuid()::text, '-', ''), 1, 12)
                             ) CHECK (analysis_id ~ '^analysis_[0-9a-f]{12}$'),
        request_id           text NOT NULL UNIQUE REFERENCES public.analysis_requests(request_id)
                             ON DELETE CASCADE,
        status               text NOT NULL CHECK (status IN ('ok', 'partial', 'invalid')),
        dataset_version_used text NOT NULL,
        ml_engine_version    text NOT NULL,
        result_json          jsonb NOT NULL,
        validation_passed    boolean NOT NULL,
        validation_errors    jsonb NULL,
        created_at           timestamptz NOT NULL DEFAULT now()
    )
    """,
    # 12. analysis_selections
    """
    CREATE TABLE public.analysis_selections (
        analysis_id      text NOT NULL REFERENCES public.analysis_results(analysis_id)
                         ON DELETE CASCADE,
        field_id         text NOT NULL,
        strategy_id      text NOT NULL,
        selection_status text NOT NULL CHECK (selection_status IN ('selected', 'rejected')),
        updated_at       timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (analysis_id, field_id, strategy_id)
    )
    """,
    """
    CREATE UNIQUE INDEX idx_one_selected_strategy_per_field
        ON public.analysis_selections (analysis_id, field_id)
        WHERE selection_status = 'selected'
    """,
    # 13. ml_breaker_state
    """
    CREATE TABLE public.ml_breaker_state (
        id                   smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
        state                text NOT NULL DEFAULT 'closed'
                             CHECK (state IN ('closed', 'open', 'half_open')),
        consecutive_failures integer NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
        opened_at            timestamptz NULL,
        half_open_probe_at   timestamptz NULL,
        updated_at           timestamptz NOT NULL DEFAULT now()
    )
    """,
)


def _resolve_owner_role(raw_role: str) -> str:
    cleaned = raw_role.strip()
    if not cleaned:
        return ""
    if not _SAFE_PG_IDENTIFIER_RE.match(cleaned):
        raise ValueError(
            "ML_DATASET_OWNER_ROLE must be a valid unquoted PostgreSQL identifier; "
            f"got {cleaned!r}."
        )
    return cleaned


def _ensure_extensions() -> None:
    if context.is_offline_mode():
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        return

    bind = op.get_bind()
    ext_rows = bind.execute(
        sa.text("SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'pgcrypto')")
    ).fetchall()
    installed = {str(row[0]) for row in ext_rows}

    if "postgis" not in installed:
        try:
            with bind.begin_nested():
                bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
        except Exception as exc:
            raise RuntimeError(
                "Required PostgreSQL extension 'postgis' is missing and could not be created by "
                "the migration role."
            ) from exc

    if "pgcrypto" not in installed:
        try:
            with bind.begin_nested():
                bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        except Exception:
            try:
                with bind.begin_nested():
                    bind.execute(sa.text("SELECT gen_random_uuid()"))
                _logger.warning(
                    "Optional extension 'pgcrypto' could not be loaded; using PostgreSQL built-in "
                    "gen_random_uuid() instead."
                )
            except Exception as uuid_exc:
                raise RuntimeError(
                    "Neither 'pgcrypto' nor built-in gen_random_uuid() is available."
                ) from uuid_exc


def _provision_ml_reader() -> None:
    """Idempotently provision `dataset` schema & `ml_reader` with zero secret logs (`IMPL-005`)."""
    settings = Settings()
    conn_limit = settings.ML_DB_CONNECTION_LIMIT
    timeout_ms = settings.ML_DB_STATEMENT_TIMEOUT_MS
    if conn_limit < 1:
        raise ValueError("ML_DB_CONNECTION_LIMIT must be >= 1.")
    if timeout_ms < 1:
        raise ValueError("ML_DB_STATEMENT_TIMEOUT_MS must be >= 1.")

    # TODO(OQ-D1): `Schema: dataset` tables/columns/units are populated later by the ML team.
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS dataset"))

    owner_role = _resolve_owner_role(settings.ML_DATASET_OWNER_ROLE)

    if context.is_offline_mode():
        op.execute(
            sa.text(
                "CREATE ROLE ml_reader WITH LOGIN PASSWORD '<REDACTED>' "
                f"CONNECTION LIMIT {conn_limit}"
            )
        )
    else:
        bind = op.get_bind()
        role_caps = bind.execute(
            sa.text("SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user")
        ).first()
        is_privileged = bool(role_caps and (role_caps[0] or role_caps[1]))
        ml_reader_exists = bool(
            bind.execute(
                sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'ml_reader'")
            ).scalar()
        )

        if not ml_reader_exists and not is_privileged:
            raise RuntimeError(
                "PostgreSQL role 'ml_reader' does not exist and current migration role lacks "
                "SUPERUSER or CREATEROLE privilege to create it."
            )

        # TODO(OQ-D4): ML_DB_CONNECTION_LIMIT and ML_DB_STATEMENT_TIMEOUT_MS tuning is TBD.
        if is_privileged:
            try:
                # Bind credentials out-of-band into transaction-local GUCs so plaintext
                # passwords never appear in SQL text, Alembic logs, or pg_stat_activity.
                bind.execute(
                    sa.text("SELECT set_config('app.ml_reader_password', :pw, true)"),
                    {"pw": settings.ML_READER_PASSWORD},
                )
                bind.execute(
                    sa.text("SELECT set_config('app.ml_reader_conn_limit', :cl, true)"),
                    {"cl": str(conn_limit)},
                )
                bind.execute(
                    sa.text("SELECT set_config('app.ml_reader_stmt_timeout', :st, true)"),
                    {"st": f"{timeout_ms}ms"},
                )
                bind.execute(
                    sa.text(
                        """
                        DO $$
                        DECLARE
                            v_pw text := current_setting('app.ml_reader_password', true);
                            v_cl integer := current_setting('app.ml_reader_conn_limit', true)::int;
                            v_st text := current_setting('app.ml_reader_stmt_timeout', true);
                        BEGIN
                            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ml_reader') THEN
                                EXECUTE format(
                                    'CREATE ROLE ml_reader WITH LOGIN PASSWORD %L '
                                    'CONNECTION LIMIT %s',
                                    v_pw,
                                    v_cl
                                );
                            ELSE
                                EXECUTE format(
                                    'ALTER ROLE ml_reader WITH LOGIN PASSWORD %L '
                                    'CONNECTION LIMIT %s',
                                    v_pw,
                                    v_cl
                                );
                            END IF;
                            EXECUTE format('ALTER ROLE ml_reader SET statement_timeout = %L', v_st);
                            PERFORM set_config('app.ml_reader_password', '', true);
                        END
                        $$;
                        """
                    )
                )
            except Exception:
                raise RuntimeError(
                    "Failed to provision or configure read-only role 'ml_reader' "
                    "(verify DB privileges and secret configuration)."
                ) from None

        if owner_role:
            owner_exists = bool(
                bind.execute(
                    sa.text("SELECT 1 FROM pg_roles WHERE rolname = :owner_role"),
                    {"owner_role": owner_role},
                ).scalar()
            )
            if not owner_exists:
                raise RuntimeError(
                    f"Configured ML_DATASET_OWNER_ROLE={owner_role!r} does not exist in pg_roles."
                )

    op.execute(sa.text("REVOKE ALL ON SCHEMA public FROM ml_reader"))
    op.execute(sa.text("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ml_reader"))
    op.execute(sa.text("GRANT USAGE ON SCHEMA dataset TO ml_reader"))
    op.execute(sa.text("GRANT SELECT ON ALL TABLES IN SCHEMA dataset TO ml_reader"))
    op.execute(
        sa.text("ALTER DEFAULT PRIVILEGES IN SCHEMA dataset GRANT SELECT ON TABLES TO ml_reader")
    )
    op.execute(sa.text("REVOKE CREATE ON SCHEMA dataset FROM ml_reader"))

    if context.is_offline_mode():
        op.execute(sa.text(f"ALTER ROLE ml_reader SET statement_timeout = '{timeout_ms}ms'"))

    if owner_role:
        op.execute(
            sa.text(
                f'ALTER DEFAULT PRIVILEGES FOR ROLE "{owner_role}" '
                "IN SCHEMA dataset GRANT SELECT ON TABLES TO ml_reader"
            )
        )


def upgrade() -> None:
    _ensure_extensions()
    for statement in _CREATE_STATEMENTS:
        op.execute(sa.text(statement))
    _provision_ml_reader()


def downgrade() -> None:
    settings = Settings()
    owner_role = _resolve_owner_role(settings.ML_DATASET_OWNER_ROLE)

    drop_tables = (
        "analysis_selections",
        "analysis_results",
        "analysis_requests",
        "field_crop_history",
        "fields",
        "farms",
        "guest_sessions",
        "demo_locations",
        "refresh_tokens",
        "users",
        "crop_catalog",
        "dataset_registry",
        "ml_breaker_state",
    )
    for table_name in drop_tables:
        op.execute(sa.text(f"DROP TABLE IF EXISTS public.{table_name}"))

    if context.is_offline_mode():
        op.execute(sa.text("DROP SCHEMA IF EXISTS dataset CASCADE"))
        op.execute(sa.text("DROP ROLE IF EXISTS ml_reader"))
        return

    bind = op.get_bind()
    ml_reader_exists = bool(
        bind.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'ml_reader'")).scalar()
    )
    if ml_reader_exists:
        op.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA dataset REVOKE SELECT ON TABLES FROM ml_reader"
            )
        )
        if owner_role:
            owner_exists = bool(
                bind.execute(
                    sa.text("SELECT 1 FROM pg_roles WHERE rolname = :owner_role"),
                    {"owner_role": owner_role},
                ).scalar()
            )
            if owner_exists:
                op.execute(
                    sa.text(
                        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{owner_role}" '
                        "IN SCHEMA dataset REVOKE SELECT ON TABLES FROM ml_reader"
                    )
                )
        op.execute(sa.text("REVOKE ALL ON ALL TABLES IN SCHEMA dataset FROM ml_reader"))
        op.execute(sa.text("REVOKE ALL ON SCHEMA dataset FROM ml_reader"))
        op.execute(sa.text("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ml_reader"))
        op.execute(sa.text("REVOKE ALL ON SCHEMA public FROM ml_reader"))

    op.execute(sa.text("DROP SCHEMA IF EXISTS dataset CASCADE"))

    if ml_reader_exists:
        role_caps = bind.execute(
            sa.text("SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user")
        ).first()
        if role_caps and (role_caps[0] or role_caps[1]):
            op.execute(sa.text("DROP ROLE IF EXISTS ml_reader"))
