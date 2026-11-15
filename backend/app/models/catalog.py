from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CropCatalog(Base):
    """Versioned mirror of the ML service's supported crop catalog (`public.crop_catalog`)."""

    __tablename__ = "crop_catalog"
    __table_args__ = (
        CheckConstraint(
            "category IN ('cereals', 'legumes', 'oilseeds', "
            "'vegetables', 'forage', 'cover_crops', 'fallow')",
            name="crop_catalog_category_check",
        ),
    )

    catalog_version: Mapped[str] = mapped_column(Text, primary_key=True)
    crop_id: Mapped[str] = mapped_column(Text, primary_key=True)
    names: Mapped[dict[str, Any]] = mapped_column(PG_JSONB, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    roles: Mapped[list[str]] = mapped_column(PG_ARRAY(Text), nullable=False)
    family: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DatasetRegistry(Base):
    """Pinned active environmental dataset registry (`public.dataset_registry`)."""

    __tablename__ = "dataset_registry"
    __table_args__ = (
        CheckConstraint(
            "char_length(dataset_version) BETWEEN 1 AND 64",
            name="dataset_registry_dataset_version_check",
        ),
        Index(
            "uq_dataset_registry_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    dataset_version: Mapped[str] = mapped_column(Text, primary_key=True)
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    coverage_notes: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
