"""Pydantic v2 transport contracts for Field Shift Phase L Backend API.

Matches field_input_schema.json strictly:
- Accepts ONLY farmer-known geometry, water access, optional history, planning, preferences.
- Rejects technical soil/weather/remote-sensing keys via ConfigDict(extra='forbid').
- Preserves None ('NOT_PROVIDED') strictly distinct from [] ('EXPLICITLY_CONFIRMED_EMPTY')
  and None weights strictly distinct from 0.0.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base contract blocking unknown or forbidden technical keys."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class GeoJSONPolygonInput(StrictModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]] = Field(..., min_length=1)


class FieldInputContract(StrictModel):
    field_id: str = Field(..., min_length=1, max_length=80)
    field_name: Optional[str] = Field(default=None, max_length=120)
    geometry: GeoJSONPolygonInput
    geometry_crs: str = Field(default="EPSG:4326")


class WaterInputContract(StrictModel):
    availability: Literal["limited", "moderate", "abundant", "unknown"]
    source: Literal["groundwater", "well", "reservoir", "river", "rainfed", "other", "unknown"]
    irrigation_system: Literal["drip", "sprinkler", "surface", "none", "unknown"]


class CropHistoryItemContract(StrictModel):
    season: Literal["Winter", "Spring", "Summer", "Autumn"]
    year: int = Field(..., ge=2010, le=2035)
    planting_month: Optional[int] = Field(default=None, ge=1, le=12)
    crop_id: Optional[str] = Field(default=None, max_length=64)
    crop_name_raw: str = Field(..., min_length=1, max_length=120)
    yield_tons_per_hectare: Optional[float] = Field(default=None, ge=0.0, le=200.0)
    notes: Optional[str] = Field(default=None, max_length=500)


class PlanningInputContract(StrictModel):
    start_season: Literal["Winter", "Spring", "Summer", "Autumn"]
    start_year: int = Field(..., ge=2024, le=2035)
    horizon_seasons: int = Field(..., ge=2, le=4)
    planting_month: Optional[int] = Field(default=None, ge=1, le=12)
    planning_mode: Optional[Literal["CURRENT_PLANNING", "HISTORICAL_SIMULATION"]] = None


class PreferencesInputContract(StrictModel):
    target_crop_ids: Optional[List[str]] = None
    excluded_crop_ids: Optional[List[str]] = None
    equipment_constraints: Optional[List[str]] = None
    water_saving_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    soil_improvement_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    income_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    risk_reduction_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    forage_value_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class FarmerAccountContext(StrictModel):
    """Optional API identity context separated cleanly from scientific FieldProfile payload."""

    user_id: Optional[str] = Field(default=None, max_length=80)
    role: Literal["farmer", "advisor", "admin", "anonymous_pilot"] = "farmer"
    display_name: str = Field(default="Guelma Pilot User", min_length=1, max_length=120)
    commune_name: Optional[str] = Field(default=None, max_length=80)


class FieldValidationRequest(StrictModel):
    """Contract for POST /api/v1/fields/validate."""

    field: FieldInputContract
    water: WaterInputContract
    planning: PlanningInputContract
    crop_history: Optional[List[CropHistoryItemContract]] = None
    preferences: Optional[PreferencesInputContract] = None

    def to_scientific_payload(self) -> Dict[str, Any]:
        """Serialize strictly to field_input_schema.json contract preserving null vs []."""
        payload: Dict[str, Any] = {
            "field": self.field.model_dump(exclude_unset=True),
            "water": self.water.model_dump(),
            "planning": self.planning.model_dump(exclude_unset=True),
        }
        if "crop_history" in self.model_fields_set:
            payload["crop_history"] = (
                None if self.crop_history is None else [c.model_dump() for c in self.crop_history]
            )
        if "preferences" in self.model_fields_set:
            if self.preferences is None:
                payload["preferences"] = None
            else:
                payload["preferences"] = {
                    k: getattr(self.preferences, k)
                    for k in self.preferences.model_fields_set
                }
        return payload


class FieldAnalyzeRequest(FieldValidationRequest):
    """Contract for POST /api/v1/fields/analyze."""

    language: Literal["en", "fr", "ar"] = "en"
    farmer_account: Optional[FarmerAccountContext] = None


class FieldValidationResponse(BaseModel):
    valid: bool
    field_id: str
    field_name: Optional[str] = None
    area_m2: float
    area_ha: float
    perimeter_m: float
    centroid_lon_lat: List[float]
    wilaya_overlap_pct: float
    primary_commune: Optional[Dict[str, Any]] = None
    commune_overlaps: List[Dict[str, Any]]
    validation_warnings: List[str]
    input_completeness_flags: Dict[str, str]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    decision_engine_version: str
    dataset_version_used: str
    knowledge_base: Dict[str, int]
    geospatial_assets: Dict[str, Any]
    database: Dict[str, Any]
    disclaimers: List[str]


class FieldAnalyzeResponse(BaseModel):
    analysis_id: str
    payload_sha256: str
    reused_existing: bool
    persistence_backend: str
    field_profile_summary: Dict[str, Any]
    recommendation: Dict[str, Any]


class StoredAnalysisResponse(BaseModel):
    analysis_id: str
    created_at_utc: str
    payload_sha256: str
    persistence_backend: str
    original_request: Dict[str, Any]
    field_profile_summary: Dict[str, Any]
    recommendation: Dict[str, Any]
