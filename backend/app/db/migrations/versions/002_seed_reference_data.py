"""Seed Guelma demo location, initial dataset registry version, and breaker singleton.

Note (`IMPL-009` / `DI-15`): `public.crop_catalog` is intentionally NOT seeded here.

Revision ID: 002_seed_reference_data
Revises: 001_initial_schema
Create Date: 2026-11-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

from app.db.seed import (
    DEFAULT_DATASET_VERSION,
    GUELMA_CODE,
    GUELMA_LOCATION_ID,
    seed_reference_data_sync,
    unseed_reference_data_sync,
)

revision: str = "002_seed_reference_data"
down_revision: str | Sequence[str] | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.execute(sa.text(f"-- Seed Guelma demo_locations id={GUELMA_LOCATION_ID}"))
        return
    seed_reference_data_sync(op.get_bind())


def downgrade() -> None:
    if context.is_offline_mode():
        op.execute(sa.text("DELETE FROM public.ml_breaker_state WHERE id = 1"))
        op.execute(
            sa.text(
                "DELETE FROM public.dataset_registry "
                f"WHERE dataset_version = '{DEFAULT_DATASET_VERSION}'"
            )
        )
        op.execute(
            sa.text(
                f"DELETE FROM public.demo_locations WHERE id = {GUELMA_LOCATION_ID} "
                f"AND code = '{GUELMA_CODE}'"
            )
        )
        return
    unseed_reference_data_sync(op.get_bind())
