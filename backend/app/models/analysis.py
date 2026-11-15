from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AnalysisRequest(Base):
    """Async analysis job & snapshot queue record (`public.analysis_requests`)."""

    __tablename__ = "analysis_requests"
    __table_args__ = (
        CheckConstraint("language IN ('en', 'fr', 'ar')", name="analysis_requests_language_check"),
        CheckConstraint("quota_units IN (0, 1, 4)", name="analysis_requests_quota_units_check"),
        CheckConstraint("char_length(input_hash) = 64", name="analysis_requests_input_hash_check"),
        CheckConstraint(
            "char_length(full_input_hash) = 64",
            name="analysis_requests_full_input_hash_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'ok', 'partial', 'failed', 'cancelled')",
            name="analysis_requests_status_check",
        ),
        CheckConstraint("attempts >= 0", name="analysis_requests_attempts_check"),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="analysis_requests_duration_ms_check",
        ),
        Index(
            "uq_analysis_idempotency",
            "farm_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("idx_analysis_queue", "status", "lease_until", "created_at"),
    )

    request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_request_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("analysis_requests.request_id", ondelete="SET NULL"),
        nullable=True,
    )
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_version: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(
        Text,
        ForeignKey("dataset_registry.dataset_version", ondelete="RESTRICT"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    quota_units: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("4"),
    )
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    input_snapshot_gz: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(
        PG_JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    result: Mapped[AnalysisResult | None] = relationship(
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AnalysisResult(Base):
    """Write-once raw ML AnalysisResult JSON storage (`public.analysis_results`)."""

    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint(
            "analysis_id ~ '^analysis_[0-9a-f]{12}$'",
            name="analysis_results_analysis_id_check",
        ),
        CheckConstraint(
            "status IN ('ok', 'partial', 'invalid')",
            name="analysis_results_status_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        server_default=text(
            "('analysis_'::text "
            "|| substr(replace((gen_random_uuid())::text, '-'::text, ''::text), 1, 12))"
        ),
    )
    request_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("analysis_requests.request_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version_used: Mapped[str] = mapped_column(Text, nullable=False)
    ml_engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(PG_JSONB, nullable=False)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_errors: Mapped[list[Any] | None] = mapped_column(PG_JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    request: Mapped[AnalysisRequest] = relationship(back_populates="result")
    selections: Mapped[list[AnalysisSelection]] = relationship(
        back_populates="analysis_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AnalysisSelection(Base):
    """User strategy selection/rejection per analyzed field (`public.analysis_selections`)."""

    __tablename__ = "analysis_selections"
    __table_args__ = (
        CheckConstraint(
            "selection_status IN ('selected', 'rejected')",
            name="analysis_selections_selection_status_check",
        ),
        Index(
            "idx_one_selected_strategy_per_field",
            "analysis_id",
            "field_id",
            unique=True,
            postgresql_where=text("selection_status = 'selected'"),
        ),
    )

    analysis_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("analysis_results.analysis_id", ondelete="CASCADE"),
        primary_key=True,
    )
    field_id: Mapped[str] = mapped_column(Text, primary_key=True)
    strategy_id: Mapped[str] = mapped_column(Text, primary_key=True)
    selection_status: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    analysis_result: Mapped[AnalysisResult] = relationship(back_populates="selections")
