"""Catalog query, localization (`IMPL-016`), and cold-start bootstrap (`IMPL-009`)."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, FieldShiftError
from app.core.pagination import PaginationParams, decode_cursor, slice_keyset_page
from app.ml_client.base import MLClientError
from app.ml_client.manager import MLProviderManager
from app.models.catalog import CropCatalog
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import CatalogPage, CropItem, CropNames
from app.schemas.common import CropCategory, CropRole, Language

_CATALOG_SYNC_LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtext('catalog_sync'))")


def decode_catalog_cursor(cursor: str | None) -> str | None:
    """Decode and validate an opaque Base64 catalog cursor containing `crop_id`."""
    if cursor is None:
        return None
    payload = decode_cursor(cursor, required_keys=("crop_id",))
    raw_crop_id = payload["crop_id"]
    if not isinstance(raw_crop_id, str) or not (1 <= len(raw_crop_id) <= 64):
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "invalid_cursor_crop_id"}],
        )
    return raw_crop_id


def _to_crop_item(row: CropCatalog, *, target_lang: Language) -> CropItem:
    names = CropNames.model_validate(row.names)
    localized = getattr(names, target_lang.value, None)
    display_name = (
        localized
        if isinstance(localized, str) and localized.strip()
        else names.en
    )
    return CropItem(
        crop_id=row.crop_id,
        display_name=display_name,
        names=names,
        category=CropCategory(row.category),
        roles=[CropRole(role) for role in row.roles],
        family=row.family,
    )


async def sync_catalog_once(
    db: AsyncSession,
    ml_manager: MLProviderManager,
    *,
    retain_versions: int = 2,
    use_xact_lock: bool = True,
) -> str:
    """Fetch `/v1/catalog` via `MLProviderManager`, upsert into `crop_catalog`, and prune N/N-1."""
    if use_xact_lock:
        await db.execute(_CATALOG_SYNC_LOCK_SQL)

    payload = await ml_manager.get_catalog()
    version = await catalog_repo.upsert_catalog_and_prune(
        db,
        payload=payload,
        synced_at=datetime.now(UTC),
        retain_versions=retain_versions,
    )
    await db.commit()
    return version


async def bootstrap_catalog_if_empty(
    db: AsyncSession,
    ml_manager: MLProviderManager,
) -> None:
    """Populate `public.crop_catalog` on cold-start miss or raise `502 ML_UNAVAILABLE`."""
    if await catalog_repo.has_any_catalog_rows(db):
        return

    logger = structlog.get_logger("app.services.catalog")
    await db.execute(_CATALOG_SYNC_LOCK_SQL)
    if await catalog_repo.has_any_catalog_rows(db):
        return

    try:
        payload = await ml_manager.get_catalog()
    except MLClientError as exc:
        await db.rollback()
        await logger.awarning(
            "catalog_cold_start_bootstrap_failed",
            ml_provider=ml_manager.active_provider_name,
            ml_error_code=exc.ml_error_code,
        )
        raise FieldShiftError(
            ErrorCode.ML_UNAVAILABLE,
            "Crop catalog is empty and upstream ML service is unavailable.",
        ) from exc

    await catalog_repo.upsert_catalog_and_prune(
        db,
        payload=payload,
        synced_at=datetime.now(UTC),
        retain_versions=2,
    )
    await db.commit()
    await logger.ainfo(
        "catalog_cold_start_bootstrapped",
        catalog_version=payload.catalog_version,
        crop_count=len(payload.crops),
        ml_provider=ml_manager.active_provider_name,
    )


async def get_catalog_page(
    db: AsyncSession,
    ml_manager: MLProviderManager,
    *,
    pagination: PaginationParams,
    category: CropCategory | None = None,
    role: CropRole | None = None,
    lang: Language | None = None,
    version: str | None = None,
) -> CatalogPage:
    """Query paginated, filtered, and localized `crop_catalog` entries (`GET /catalog`)."""
    after_crop_id = decode_catalog_cursor(pagination.cursor)
    requested_version = version.strip() if version is not None else None
    if version is not None and not requested_version:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid catalog version query parameter.",
            details=[{"field": "version", "reason": "blank_version"}],
        )

    await bootstrap_catalog_if_empty(db, ml_manager)

    if requested_version is not None:
        synced_at = await catalog_repo.get_catalog_version_meta(
            db,
            catalog_version=requested_version,
        )
        if synced_at is None:
            raise FieldShiftError(
                ErrorCode.NOT_FOUND,
                f"Catalog version '{requested_version}' was not found.",
            )
        resolved_version = requested_version
    else:
        latest = await catalog_repo.get_latest_catalog_version_meta(db)
        if latest is None:
            raise FieldShiftError(
                ErrorCode.ML_UNAVAILABLE,
                "Crop catalog is not available.",
            )
        resolved_version, synced_at = latest

    rows = await catalog_repo.list_catalog_crops(
        db,
        catalog_version=resolved_version,
        limit=pagination.limit,
        after_crop_id=after_crop_id,
        category=category.value if category is not None else None,
        role=role.value if role is not None else None,
    )
    sliced, next_cursor, has_more = slice_keyset_page(
        rows,
        limit=pagination.limit,
        cursor_key_fn=lambda item: {"crop_id": item.crop_id},
    )

    target_lang = lang or Language.EN
    items = [_to_crop_item(row, target_lang=target_lang) for row in sliced]
    return CatalogPage(
        catalog_version=resolved_version,
        synced_at=synced_at,
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )
