from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.analysis import AnalysisRequest
    from app.models.demo import GuestSession
    from app.models.field import Field
    from app.models.user import User


class Farm(Base):
    """Agricultural farm owned exclusively by either a registered user or guest session."""

    __tablename__ = "farms"
    __table_args__ = (
        CheckConstraint("char_length(farm_name) BETWEEN 1 AND 120", name="farms_farm_name_check"),
        CheckConstraint("char_length(country) BETWEEN 1 AND 80", name="farms_country_check"),
        CheckConstraint("char_length(region) BETWEEN 1 AND 80", name="farms_region_check"),
        CheckConstraint(
            "commune IS NULL OR char_length(commune) <= 120",
            name="farms_commune_check",
        ),
        CheckConstraint(
            "(user_id IS NOT NULL) <> (guest_session_token IS NOT NULL)",
            name="chk_farms_single_owner",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    guest_session_token: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("guest_sessions.guest_token", ondelete="CASCADE"),
        nullable=True,
    )
    farm_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    commune: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User | None] = relationship()
    guest_session: Mapped[GuestSession | None] = relationship(back_populates="farms")
    fields: Mapped[list[Field]] = relationship(
        back_populates="farm",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analysis_requests: Mapped[list[AnalysisRequest]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
