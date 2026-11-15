from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.farm import Farm


class Field(Base):
    """Spatial plot/parcel within a farm (`public.fields`)."""

    __tablename__ = "fields"
    __table_args__ = (
        CheckConstraint(
            "char_length(external_field_id) BETWEEN 1 AND 64",
            name="fields_external_field_id_check",
        ),
        CheckConstraint(
            "char_length(field_name) BETWEEN 1 AND 120",
            name="fields_field_name_check",
        ),
        CheckConstraint(
            "area_hectares > 0 AND area_hectares <= 10000",
            name="fields_area_hectares_check",
        ),
        CheckConstraint(
            "soil_type IN ('sandy', 'clay', 'loamy', 'silty', 'unknown')",
            name="fields_soil_type_check",
        ),
        CheckConstraint(
            "soil_source IN ('farmer', 'unknown')",
            name="fields_soil_source_check",
        ),
        CheckConstraint(
            "soil_ph IS NULL OR (soil_ph >= 3.0 AND soil_ph <= 11.0)",
            name="fields_soil_ph_check",
        ),
        CheckConstraint(
            "organic_matter_percent IS NULL OR "
            "(organic_matter_percent >= 0 AND organic_matter_percent <= 100)",
            name="fields_organic_matter_percent_check",
        ),
        CheckConstraint(
            "water_availability IN "
            "('abundant', 'moderate', 'limited', 'very_limited', 'rainfed_only')",
            name="fields_water_availability_check",
        ),
        CheckConstraint(
            "water_source IN ('rainwater', 'groundwater', 'well', 'dam_reservoir', "
            "'irrigation_network', 'other', 'unknown')",
            name="fields_water_source_check",
        ),
        CheckConstraint(
            "water_source_other IS NULL OR char_length(water_source_other) <= 200",
            name="fields_water_source_other_check",
        ),
        CheckConstraint(
            "irrigation_system IN ('rainfed', 'drip', 'sprinkler', 'flood', 'other', 'unknown')",
            name="fields_irrigation_system_check",
        ),
        CheckConstraint(
            "elevation_m IS NULL OR (elevation_m BETWEEN -500 AND 9000)",
            name="fields_elevation_m_check",
        ),
        UniqueConstraint(
            "farm_id",
            "external_field_id",
            name="fields_farm_id_external_field_id_key",
        ),
        Index("idx_fields_geom_point", "geom_point", postgresql_using="gist"),
        Index("idx_fields_geom_polygon", "geom_polygon", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_field_id: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_unverified_demo_parcel: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    geom_point: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    geom_polygon: Mapped[WKBElement | None] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=False),
        nullable=True,
    )
    area_hectares: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    soil_type: Mapped[str] = mapped_column(Text, nullable=False)
    soil_source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    soil_ph: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    organic_matter_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    soil_test_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    water_availability: Mapped[str] = mapped_column(Text, nullable=False)
    water_source: Mapped[str] = mapped_column(Text, nullable=False)
    water_source_other: Mapped[str | None] = mapped_column(Text, nullable=True)
    irrigation_system: Mapped[str] = mapped_column(Text, nullable=False)
    elevation_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    farm: Mapped[Farm] = relationship(back_populates="fields")
    crop_history: Mapped[list[FieldCropHistory]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FieldCropHistory(Base):
    """Historical planting record for a field (`public.field_crop_history`).

    Deliberately has NO foreign key to `public.crop_catalog` (`Pitfall #10`) so catalog
    upgrades never invalidate user plot history; stores `catalog_version` + `crop_name_raw`.
    """

    __tablename__ = "field_crop_history"
    __table_args__ = (
        CheckConstraint(
            "season IN ('spring', 'summer', 'autumn', 'winter')",
            name="field_crop_history_season_check",
        ),
        CheckConstraint("year BETWEEN 1980 AND 2100", name="field_crop_history_year_check"),
        CheckConstraint(
            "planting_month IS NULL OR (planting_month BETWEEN 1 AND 12)",
            name="field_crop_history_planting_month_check",
        ),
        CheckConstraint(
            "crop_id IS NULL OR char_length(crop_id) BETWEEN 1 AND 64",
            name="field_crop_history_crop_id_check",
        ),
        CheckConstraint(
            "crop_name_raw IS NULL OR char_length(crop_name_raw) BETWEEN 1 AND 120",
            name="field_crop_history_crop_name_raw_check",
        ),
        CheckConstraint(
            "yield_tons_per_hectare IS NULL OR yield_tons_per_hectare >= 0",
            name="field_crop_history_yield_tons_per_hectare_check",
        ),
        CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 500",
            name="field_crop_history_notes_check",
        ),
        UniqueConstraint(
            "field_id",
            "year",
            "season",
            name="field_crop_history_field_id_year_season_key",
        ),
        CheckConstraint(
            "crop_id IS NOT NULL OR crop_name_raw IS NOT NULL",
            name="chk_history_crop_identifier",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    field_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    season: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    planting_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    catalog_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Intentionally un-constrained against crop_catalog (Pitfall #10).
    crop_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    crop_name_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    yield_tons_per_hectare: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    field: Mapped[Field] = relationship(back_populates="crop_history")
