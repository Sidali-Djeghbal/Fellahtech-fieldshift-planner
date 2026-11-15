"""Orchestration service connecting Field Shift Phases F -> G -> H -> I -> J cleanly."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from field_geospatial_processor import validate_and_project_polygon
from field_profile_builder import FarmerInputValidationError, build_field_profile, validate_farmer_input
from fieldshift_integration.config import (
    BOUNDARY_COMMUNES_GPKG,
    BOUNDARY_WILAYA_GPKG,
    CROP_FREQ_ALIGNED_10M_TIF,
    NASA_POWER_DAILY_CELLS_CSV,
    S2_PHASEA_10M_TIF,
    SOILGRIDS_V6_ZIP,
)
from src.agronomic import load_knowledge_base
from src.optimization import rank_rotation_candidates
from src.output import (
    DECISION_ENGINE_VERSION,
    OutputValidationError,
    build_final_recommendation,
    validate_final_recommendation,
)
from src.rotation import generate_rotation_candidates


class PipelineExecutionError(RuntimeError):
    """Raised when an internal scientific or contract-validation gate fails."""


def compute_payload_sha256(scientific_payload: Dict[str, Any], language: str = "en") -> str:
    """Compute a deterministic full-request SHA-256 covering engine version, language, and farmer inputs."""
    canonical = json.dumps(
        {
            "decision_engine_version": DECISION_ENGINE_VERSION,
            "language": language,
            "scientific_payload": scientific_payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_analysis_id(payload_sha256: str) -> str:
    """Create content-addressed analysis identifier independent of upstream field_id collisions."""
    return f"ANAL_{payload_sha256[:16].upper()}"


def validate_farmer_submission(
    scientific_payload: Dict[str, Any],
    *,
    reference_date: Optional[Any] = None,
    clock: Optional[Any] = None,
) -> Dict[str, Any]:
    """Validate farmer input contract + GeoJSON Polygon inside Guelma Wilaya (no raster extraction)."""
    normalized = validate_farmer_input(
        scientific_payload,
        reference_date=reference_date,
        clock=clock,
    )
    geom_cfg = normalized["field"]
    spatial = validate_and_project_polygon(
        geom_cfg["geometry"],
        geometry_crs=geom_cfg.get("geometry_crs", "EPSG:4326"),
    )
    return {
        "valid": True,
        "field_id": geom_cfg["field_id"],
        "field_name": geom_cfg.get("field_name"),
        "area_m2": spatial["area_m2"],
        "area_ha": spatial["area_ha"],
        "perimeter_m": spatial["perimeter_m"],
        "centroid_lon_lat": spatial["centroid_lon_lat"],
        "wilaya_overlap_pct": spatial["wilaya_overlap_pct"],
        "primary_commune": spatial["primary_commune"],
        "commune_overlaps": spatial["commune_overlaps"],
        "validation_warnings": spatial["validation_warnings"],
        "input_completeness_flags": normalized["input_completeness_flags"],
    }


def build_field_profile_summary(field_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Extract clean summary view from 4-part FieldProfile without duplicating rules or faking values."""
    sec_a = field_profile["section_a_farmer_provided"]
    sec_b = field_profile["section_b_extracted_geospatial"]
    sec_c = field_profile["section_c_agronomic_knowledge_base"]
    sec_d = field_profile["section_d_quality_and_uncertainty"]

    sv = sec_b["spatial_validation"]
    ds = sec_b["extracted_datasets"]
    soil = ds["soilgrids_v6"]
    cf = ds["crop_frequency"]["crop_frequency_2021_2025"]
    s2 = ds["sentinel2"]["s2_2024_03_ndvi_10m"]
    gpm = ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]
    npw = ds["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"]
    t2m = ds["nasa_power"]["nasa_power_t2m_2016_2025_mean_c"]
    smap_sp = ds["gpm_and_smap"]["smap_rootzone_sm_spring_2016_2025_mean"]
    dem = ds["terrain_dem"]["dem_elevation_m"]

    return {
        "field_id": sec_a["field"]["field_id"],
        "field_name": sec_a["field"].get("field_name"),
        "geometry": sec_a["field"]["geometry"],
        "spatial_validation": sv,
        "water_declared": sec_a["water"],
        "planning": sec_a["planning"],
        "extracted_summary": {
            "usda_texture_0_5cm": soil.get("usda_texture_0_5cm", {}).get("value"),
            "clay_0_30cm_pct": soil["clay_0_30cm"],
            "sand_0_30cm_pct": soil["sand_0_30cm"],
            "silt_0_30cm_pct": soil["silt_0_30cm"],
            "ph_0_30cm": soil["ph_0_30cm"],
            "soc_0_30cm_g_kg": soil["soc_0_30cm"],
            "cec_0_30cm": soil["cec_0_30cm"],
            "crop_frequency_2021_2025": cf,
            "s2_2024_03_ndvi_10m": s2,
            "gpm_annual_precip_mm": gpm,
            "nasa_power_annual_precip_mm": npw,
            "nasa_power_t2m_mean_c": t2m,
            "smap_rootzone_sm_spring": smap_sp,
            "dem_elevation_m": dem,
        },
        "descriptive_field_diagnostics": sec_c.get("descriptive_field_diagnostics", []),
        "land_use_assessment": sec_c.get("land_use_assessment"),
        "temporal_validation": sec_a.get("planning", {}).get("temporal_validation"),
        "conditional_follow_up_questions": sec_d.get("conditional_follow_up_questions", []),
        "quality_status_counts": sec_d.get("quality_status_counts", {}),
        "input_completeness_flags": sec_d.get("input_completeness_flags", {}),
        "provenance_disclosures": {
            "soilgrids_vs_laboratory_distinction": sec_d.get("soilgrids_vs_laboratory_distinction"),
            "regional_climate_vs_field_distinction": sec_d.get("regional_climate_vs_field_distinction"),
            "missing_values_policy": sec_d.get("missing_values_policy"),
        },
    }


def run_field_analysis_pipeline(
    scientific_payload: Dict[str, Any],
    *,
    analysis_id: str,
    language: str = "en",
    generated_at: Optional[str] = None,
    reference_date: Optional[Any] = None,
    clock: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute Phases F -> G -> H -> I -> J + Draft 2020-12 schema/semantic validation."""
    kb = load_knowledge_base()
    field_profile = build_field_profile(
        scientific_payload,
        reference_date=reference_date,
        clock=clock,
    )
    candidate_output = generate_rotation_candidates(
        field_profile,
        kb=kb,
        reference_date=reference_date,
        clock=clock,
    )
    ranking_output = rank_rotation_candidates(candidate_output, field_profile=field_profile, kb=kb)

    recommendation = build_final_recommendation(
        field_profile,
        candidate_output,
        ranking_output,
        request_id=analysis_id,
        language=language,
        generated_at=generated_at,
        kb=kb,
    )

    validation = validate_final_recommendation(recommendation)
    if not validation["valid"]:
        raise OutputValidationError(validation["errors"])

    return {
        "field_profile": field_profile,
        "field_profile_summary": build_field_profile_summary(field_profile),
        "candidate_output": candidate_output,
        "ranking_output": ranking_output,
        "recommendation": recommendation,
        "schema_validation": validation,
    }


def check_geospatial_assets_status() -> Dict[str, Any]:
    """Inspect presence of core local geospatial archives without executing GEE calls."""
    assets = {
        "wilaya_boundary_gpkg": BOUNDARY_WILAYA_GPKG.exists(),
        "communes_boundary_gpkg": BOUNDARY_COMMUNES_GPKG.exists(),
        "soilgrids_v6_zip": SOILGRIDS_V6_ZIP.exists(),
        "crop_frequency_10m_tif": CROP_FREQ_ALIGNED_10M_TIF.exists(),
        "s2_2024_03_10m_tif": S2_PHASEA_10M_TIF.exists(),
        "nasa_power_daily_cells_csv": NASA_POWER_DAILY_CELLS_CSV.exists(),
    }
    return {
        "all_core_assets_present": all(assets.values()),
        "assets": assets,
        "gee_tasks_submitted": False,
    }


__all__ = [
    "FarmerInputValidationError",
    "OutputValidationError",
    "PipelineExecutionError",
    "build_field_profile_summary",
    "check_geospatial_assets_status",
    "compute_payload_sha256",
    "derive_analysis_id",
    "run_field_analysis_pipeline",
    "validate_farmer_submission",
]
