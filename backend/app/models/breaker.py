from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, SmallInteger, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MlBreakerState(Base):
    """Cluster-wide singleton circuit breaker state (`public.ml_breaker_state`)."""

    __tablename__ = "ml_breaker_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ml_breaker_state_id_check"),
        CheckConstraint(
            "state IN ('closed', 'open', 'half_open')",
            name="ml_breaker_state_state_check",
        ),
        CheckConstraint(
            "consecutive_failures >= 0",
            name="ml_breaker_state_consecutive_failures_check",
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text("1"))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'closed'"))
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    half_open_probe_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
