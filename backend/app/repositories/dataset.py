"""PostgreSQL repositories for `public.dataset_registry` pinned dataset resolution."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, FieldShiftError
from app.models.catalog import DatasetRegistry


async def get_active_dataset(db: AsyncSession) -> DatasetRegistry | None:
    """Return the active row in `public.dataset_registry` (`is_active = true`), or None."""
    stmt = select(DatasetRegistry).where(DatasetRegistry.is_active.is_(True)).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def require_active_dataset(db: AsyncSession) -> DatasetRegistry:
    """Return the active `DatasetRegistry` row or raise `503 DATASET_UNAVAILABLE`."""
    dataset = await get_active_dataset(db)
    if dataset is None:
        raise FieldShiftError(
            ErrorCode.DATASET_UNAVAILABLE,
            "No active environmental dataset version is available in dataset_registry.",
        )
    return dataset


async def get_dataset_by_version(
    db: AsyncSession,
    *,
    dataset_version: str,
) -> DatasetRegistry | None:
    """Return a `DatasetRegistry` row by primary key `dataset_version`."""
    stmt = select(DatasetRegistry).where(DatasetRegistry.dataset_version == dataset_version)
    return (await db.execute(stmt)).scalar_one_or_none()
