from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from logging.config import fileConfig
from typing import Literal

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 - register all 13 public ORM models for target_metadata
from app.core.config import Settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_POSTGIS_INTERNAL_TABLES: frozenset[str] = frozenset(
    {
        "spatial_ref_sys",
        "geometry_columns",
        "geography_columns",
        "raster_columns",
        "raster_overviews",
    }
)


def _include_name(
    name: str | None,
    type_: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
        "check_constraint",
    ],
    parent_names: MutableMapping[
        Literal["schema_name", "table_name", "schema_qualified_table_name"],
        str | None,
    ],
) -> bool:
    """Restrict Alembic schema introspection to app tables in `public` only."""
    del parent_names
    if type_ == "schema":
        return name in (None, "public")
    if type_ == "table":
        return name not in _POSTGIS_INTERNAL_TABLES
    return True


def _get_database_url() -> str:
    """Resolve runtime DATABASE_URL dynamically without storing credentials in alembic.ini."""
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return str(configured_url)
    return Settings().DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=_get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=_include_name,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context on an active synchronous connection adapter."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=_include_name,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a one-shot asyncpg engine and execute pending migrations."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _get_database_url()

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' async mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
