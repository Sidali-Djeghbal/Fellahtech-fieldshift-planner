from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.farm import Farm


class DemoLocation(Base):
    """MVP geographic zone boundary metadata (`public.demo_locations`)."""

    __tablename__ = "demo_locations"
    __table_args__ = (
        Index("idx_demo_locations_boundary", "boundary", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    boundary: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    guest_sessions: Mapped[list[GuestSession]] = relationship(
        back_populates="demo_location",
        passive_deletes=True,
    )


class GuestSession(Base):
    """Anonymous 7-day guest session (`public.guest_sessions`).

    Stores SHA-256 hex digest of raw `X-Guest-Token`, bound to an active `DemoLocation`.
    """

    __tablename__ = "guest_sessions"
    __table_args__ = (
        CheckConstraint("char_length(guest_token) = 64", name="guest_sessions_guest_token_check"),
    )

    guest_token: Mapped[str] = mapped_column(Text, primary_key=True)
    demo_location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("demo_locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    demo_location: Mapped[DemoLocation] = relationship(back_populates="guest_sessions")
    farms: Mapped[list[Farm]] = relationship(
        back_populates="guest_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
