"""PostgreSQL repositories for owner-scoped farms and guest quota row locks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.farm import Farm
from app.models.field import Field


@dataclass(frozen=True, slots=True)
class FarmWithCount:
    """Persisted `Farm` ORM row bundled with its current parcel count."""

    farm: Farm
    field_count: int


def _owner_predicate(
    *,
    user_id: int | None,
    guest_token_hash: str | None,
) -> ColumnElement[bool]:
    if user_id is not None:
        return Farm.user_id == user_id
    if guest_token_hash is not None:
        return Farm.guest_session_token == guest_token_hash
    raise ValueError("Actor principal must specify either user_id or guest_token_hash.")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_farms_for_actor(
    db: AsyncSession,
    *,
    user_id: int | None,
    guest_token_hash: str | None,
    limit: int,
    after_id: int | None,
    country: str | None = None,
    region: str | None = None,
    search: str | None = None,
) -> list[FarmWithCount]:
    """Fetch `limit + 1` owner-scoped farms with field counts in deterministic keyset order."""
    stmt = (
        select(Farm, func.count(Field.id).label("field_count"))
        .outerjoin(Field, Field.farm_id == Farm.id)
        .where(_owner_predicate(user_id=user_id, guest_token_hash=guest_token_hash))
    )

    if country:
        stmt = stmt.where(func.lower(Farm.country) == country.lower())
    if region:
        stmt = stmt.where(func.lower(Farm.region) == region.lower())
    if search:
        pattern = f"%{_escape_like(search)}%"
        stmt = stmt.where(
            or_(
                Farm.farm_name.ilike(pattern, escape="\\"),
                Farm.region.ilike(pattern, escape="\\"),
                Farm.commune.ilike(pattern, escape="\\"),
            )
        )
    if after_id is not None:
        stmt = stmt.where(Farm.id > after_id)

    stmt = stmt.group_by(Farm.id).order_by(Farm.id.asc()).limit(limit + 1)
    rows = (await db.execute(stmt)).all()
    return [FarmWithCount(farm=row[0], field_count=int(row[1])) for row in rows]


async def count_farms_for_guest(db: AsyncSession, *, guest_token_hash: str) -> int:
    """Count current farms owned by a guest session (caller holds `GuestSession FOR UPDATE`)."""
    stmt = select(func.count(Farm.id)).where(Farm.guest_session_token == guest_token_hash)
    return int((await db.execute(stmt)).scalar_one())


async def create_farm(
    db: AsyncSession,
    *,
    user_id: int | None,
    guest_token_hash: str | None,
    farm_name: str,
    country: str,
    region: str,
    commune: str | None,
) -> Farm:
    """Insert a farm owned exclusively by either a registered user or guest session."""
    farm = Farm(
        user_id=user_id,
        guest_session_token=guest_token_hash if user_id is None else None,
        farm_name=farm_name,
        country=country,
        region=region,
        commune=commune,
    )
    db.add(farm)
    await db.flush()
    await db.refresh(farm)
    return farm


async def get_owned_farm(
    db: AsyncSession,
    *,
    farm_pk: int,
    user_id: int | None,
    guest_token_hash: str | None,
    for_update: bool = False,
) -> Farm | None:
    """Load an owner-scoped farm by primary key, optionally acquiring `FOR UPDATE`."""
    stmt = select(Farm).where(
        Farm.id == farm_pk,
        _owner_predicate(user_id=user_id, guest_token_hash=guest_token_hash),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_owned_farm_with_count(
    db: AsyncSession,
    *,
    farm_pk: int,
    user_id: int | None,
    guest_token_hash: str | None,
) -> FarmWithCount | None:
    """Load an owner-scoped farm along with its field count."""
    stmt = (
        select(Farm, func.count(Field.id).label("field_count"))
        .outerjoin(Field, Field.farm_id == Farm.id)
        .where(
            Farm.id == farm_pk,
            _owner_predicate(user_id=user_id, guest_token_hash=guest_token_hash),
        )
        .group_by(Farm.id)
    )
    row: Any = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    return FarmWithCount(farm=row[0], field_count=int(row[1]))


async def count_fields_for_farm(db: AsyncSession, *, farm_pk: int) -> int:
    """Count fields currently belonging to a farm."""
    stmt = select(func.count(Field.id)).where(Field.farm_id == farm_pk)
    return int((await db.execute(stmt)).scalar_one())


async def delete_owned_farm(
    db: AsyncSession,
    *,
    farm_pk: int,
    user_id: int | None,
    guest_token_hash: str | None,
) -> bool:
    """Delete an owner-scoped farm cleanly; returns True if a row was removed."""
    stmt = (
        delete(Farm)
        .where(
            Farm.id == farm_pk,
            _owner_predicate(user_id=user_id, guest_token_hash=guest_token_hash),
        )
        .returning(Farm.id)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None
