"""PostgreSQL repositories for mirrored `public.crop_catalog` versions and crops."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CropCatalog
from app.schemas.catalog import MLCatalogPayload


async def has_any_catalog_rows(db: AsyncSession) -> bool:
    """Return True if at least one crop exists in `public.crop_catalog`."""
    stmt = select(CropCatalog.catalog_version).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def get_latest_catalog_version_meta(db: AsyncSession) -> tuple[str, datetime] | None:
    """Return `(catalog_version, synced_at)` for the newest active catalog snapshot (`N`)."""
    max_synced = func.max(CropCatalog.synced_at).label("synced_at")
    stmt = (
        select(CropCatalog.catalog_version, max_synced)
        .group_by(CropCatalog.catalog_version)
        .order_by(max_synced.desc(), CropCatalog.catalog_version.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    synced = row[1]
    if isinstance(synced, datetime) and synced.tzinfo is None:
        synced = synced.replace(tzinfo=UTC)
    return str(row[0]), synced


async def get_catalog_version_meta(
    db: AsyncSession,
    *,
    catalog_version: str,
) -> datetime | None:
    """Return `synced_at` for an explicit `catalog_version`, or None if absent."""
    stmt = select(func.max(CropCatalog.synced_at)).where(
        CropCatalog.catalog_version == catalog_version
    )
    synced = (await db.execute(stmt)).scalar_one_or_none()
    if synced is None:
        return None
    if synced.tzinfo is None:
        return synced.replace(tzinfo=UTC)
    return synced


async def list_catalog_versions(db: AsyncSession) -> list[str]:
    """Return stored catalog versions ordered newest (`N`) to oldest (`N-1`, ...)."""
    max_synced = func.max(CropCatalog.synced_at).label("synced_at")
    stmt = (
        select(CropCatalog.catalog_version)
        .group_by(CropCatalog.catalog_version)
        .order_by(max_synced.desc(), CropCatalog.catalog_version.desc())
    )
    return [str(v) for v in (await db.execute(stmt)).scalars().all()]


async def find_missing_crop_ids(
    db: AsyncSession,
    *,
    catalog_version: str,
    crop_ids: Sequence[str],
) -> list[str]:
    """Return sorted subset of `crop_ids` absent from `(catalog_version, crop_id)`."""
    unique_ids = sorted(set(crop_ids))
    if not unique_ids:
        return []
    stmt = select(CropCatalog.crop_id).where(
        CropCatalog.catalog_version == catalog_version,
        CropCatalog.crop_id.in_(unique_ids),
    )
    found = {str(cid) for cid in (await db.execute(stmt)).scalars().all()}
    return [cid for cid in unique_ids if cid not in found]


async def list_catalog_crops(
    db: AsyncSession,
    *,
    catalog_version: str,
    limit: int,
    after_crop_id: str | None = None,
    category: str | None = None,
    role: str | None = None,
) -> list[CropCatalog]:
    """Fetch `limit + 1` crops for keyset cursor pagination ordered by `crop_id ASC`."""
    stmt = select(CropCatalog).where(CropCatalog.catalog_version == catalog_version)
    if category is not None:
        stmt = stmt.where(CropCatalog.category == category)
    if role is not None:
        stmt = stmt.where(CropCatalog.roles.contains([role]))
    if after_crop_id is not None:
        stmt = stmt.where(CropCatalog.crop_id > after_crop_id)

    stmt = stmt.order_by(CropCatalog.crop_id.asc()).limit(limit + 1)
    return list((await db.execute(stmt)).scalars().all())


async def upsert_catalog_and_prune(
    db: AsyncSession,
    *,
    payload: MLCatalogPayload,
    synced_at: datetime | None = None,
    retain_versions: int = 2,
) -> str:
    """Atomically upsert all crops for `payload.catalog_version` and retain latest `N`/`N-1`."""
    effective_synced_at = synced_at or datetime.now(UTC)
    if effective_synced_at.tzinfo is None:
        effective_synced_at = effective_synced_at.replace(tzinfo=UTC)

    latest = await get_latest_catalog_version_meta(db)
    if latest is not None and effective_synced_at <= latest[1]:
        # Guard against same-tick clock ties so newest synced version orders strictly first (`N`).
        effective_synced_at = latest[1] + timedelta(microseconds=1)

    crop_ids: list[str] = []
    rows_to_upsert: list[dict[str, object]] = []
    for crop in payload.crops:
        crop_ids.append(crop.crop_id)
        names_dict = crop.names.model_dump(mode="json")
        rows_to_upsert.append(
            {
                "catalog_version": payload.catalog_version,
                "crop_id": crop.crop_id,
                "names": names_dict,
                "category": crop.category.value,
                "roles": [r.value for r in crop.roles],
                "family": crop.family,
                "synced_at": effective_synced_at,
            }
        )

    stmt = pg_insert(CropCatalog).values(rows_to_upsert)
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=[CropCatalog.catalog_version, CropCatalog.crop_id],
        set_={
            "names": stmt.excluded.names,
            "category": stmt.excluded.category,
            "roles": stmt.excluded.roles,
            "family": stmt.excluded.family,
            "synced_at": stmt.excluded.synced_at,
        },
    )
    await db.execute(upsert_stmt)

    # Remove crops dropped from the same version snapshot.
    await db.execute(
        delete(CropCatalog).where(
            CropCatalog.catalog_version == payload.catalog_version,
            CropCatalog.crop_id.not_in(crop_ids),
        )
    )

    if retain_versions >= 1:
        max_synced = func.max(CropCatalog.synced_at).label("synced_at")
        keep_stmt = (
            select(CropCatalog.catalog_version)
            .group_by(CropCatalog.catalog_version)
            .order_by(max_synced.desc(), CropCatalog.catalog_version.desc())
            .limit(retain_versions)
        )
        kept_versions = [str(v) for v in (await db.execute(keep_stmt)).scalars().all()]
        if kept_versions:
            await db.execute(
                delete(CropCatalog).where(CropCatalog.catalog_version.not_in(kept_versions))
            )

    await db.flush()
    return payload.catalog_version


async def get_catalog_crop_meta_map(
    db: AsyncSession,
    *,
    catalog_version: str,
) -> dict[str, tuple[str, tuple[str, ...], str]]:
    """Return `{crop_id: (category, roles, family)}` for one synced `catalog_version`."""
    stmt = select(
        CropCatalog.crop_id,
        CropCatalog.category,
        CropCatalog.roles,
        CropCatalog.family,
    ).where(CropCatalog.catalog_version == catalog_version)
    rows = (await db.execute(stmt)).all()
    return {
        str(crop_id): (str(category), tuple(str(role) for role in roles), str(family))
        for crop_id, category, roles, family in rows
    }

