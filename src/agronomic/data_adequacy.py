"""Shared decision-critical data adequacy and catalog completeness assessment.

Provides a single canonical source of truth used by both Phase I (`scoring_engine.py`
`decision_gate`) and Phase J (`recommendation_builder.py` `data_quality`) so that
`critical_data_adequacy = INSUFFICIENT` can never diverge from exploratory gating.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.agronomic.land_use_assessment import (
    LAND_USE_CONFLICTING_EVIDENCE,
    LAND_USE_DATA_UNAVAILABLE,
    LAND_USE_LOW_EVIDENCE,
    LAND_USE_UNVERIFIED,
    assess_land_use,
)

BLOCKING_ADEQUACY_STATUSES: Tuple[str, ...] = ("INSUFFICIENT", "NOT_ASSESSABLE")


def compute_data_completeness_score(field_profile: Dict[str, Any]) -> Tuple[int, float]:
    """Compute available geospatial count and catalog completeness_score from a Field Profile."""
    sec_d = field_profile["section_d_quality_and_uncertainty"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    q_counts = sec_d["quality_status_counts"]

    total_geospatial = sum(len(dom) for dom in ds.values())
    incomplete_geospatial = (
        int(q_counts.get("UNAVAILABLE_NOT_INTEGRATED", 0))
        + int(q_counts.get("UNVALIDATED_EXCLUDED", 0))
        + int(q_counts.get("UNAVAILABLE_MASKED_PIXEL", 0))
    )
    avail_geospatial = max(0, total_geospatial - incomplete_geospatial)

    opt_flags = sec_d["input_completeness_flags"]
    farmer_items = ("crop_history", "equipment_constraints", "forage_value_weight")
    farmer_provided_or_empty = sum(
        1
        for k in farmer_items
        if opt_flags.get(k) in ("PROVIDED", "PROVIDED_PARTIAL", "PROVIDED_COMPLETE", "EXPLICITLY_CONFIRMED_EMPTY")
    )
    completeness_score = round(
        (avail_geospatial + farmer_provided_or_empty) / max(total_geospatial + len(farmer_items), 1),
        4,
    )
    return avail_geospatial, completeness_score


def assess_critical_data_adequacy(
    *,
    field_profile: Optional[Dict[str, Any]] = None,
    field_insights: Optional[Dict[str, Any]] = None,
    land_use_assessment: Optional[Dict[str, Any]] = None,
    water_balance_assessment: Optional[Dict[str, Any]] = None,
    water_context: Optional[Dict[str, Any]] = None,
    optional_flags: Optional[Dict[str, str]] = None,
    history_sufficient: Optional[bool] = None,
    eligible_for_ranking_count: Optional[int] = None,
    income_potential_unavailable: bool = True,
    avail_geospatial: Optional[int] = None,
    completeness_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Classify decision-critical data adequacy separately from catalog completeness_score.

    Any `CRITICAL_BLOCKER` (including unverified/conflicting cropland or SoilGrids
    `clay_0_30cm` missing or `< 25%` polygon coverage) produces `INSUFFICIENT` (or
    `NOT_ASSESSABLE` if core climate/geospatial inputs are entirely unavailable),
    which decision gates must treat as an `EXPLORATORY_ONLY` endorsement blocker.
    Missing optional/local verification items (DEM, irrigation ECe, economic budgets,
    history, WS2M/FC/PWP, optional farmer inputs) yield `PARTIAL` rather than `INSUFFICIENT`.
    """
    if field_profile is not None:
        sec_a = field_profile["section_a_farmer_provided"]
        ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
        sec_d = field_profile["section_d_quality_and_uncertainty"]
        opt_flags = sec_d["input_completeness_flags"]
        water = sec_a.get("water") or {}

        if avail_geospatial is None or completeness_score is None:
            comp_avail, comp_score = compute_data_completeness_score(field_profile)
            if avail_geospatial is None:
                avail_geospatial = comp_avail
            if completeness_score is None:
                completeness_score = comp_score

        land_use = (
            land_use_assessment
            or field_profile.get("section_c_agronomic_knowledge_base", {}).get("land_use_assessment")
            or assess_land_use(field_profile)
        )
        sg_clay = (ds.get("soilgrids_v6") or {}).get("clay_0_30cm") or {}
        clay_val = sg_clay.get("value")
        clay_cov = sg_clay.get("polygon_coverage_pct")
        clay_qstatus = str(sg_clay.get("quality_status") or "UNKNOWN")
        sg_n_status = str(((ds.get("soilgrids_v6") or {}).get("nitrogen_0_30cm") or {}).get("quality_status") or "UNVALIDATED_EXCLUDED")

        gpm_ann = ((ds.get("gpm_and_smap") or {}).get("gpm_annual_precip_2016_2025_mean_mm") or {}).get("value")
        power_ann = ((ds.get("nasa_power") or {}).get("nasa_power_annual_precip_2016_2025_mean_mm") or {}).get("value")
        dem_slope_status = str(((ds.get("terrain_dem") or {}).get("dem_slope_pct") or {}).get("quality_status") or "UNKNOWN")
    else:
        fi = field_insights or {}
        soil_s = fi.get("soil_summary_modeled_250m") or {}
        clim_s = fi.get("climate_water_summary") or {}
        veg_s = fi.get("vegetation_and_terrain_summary") or {}
        opt_flags = optional_flags or {}
        water = water_context or {}
        land_use = land_use_assessment or {}

        clay_val = soil_s.get("clay_0_30cm_pct")
        clay_cov = soil_s.get("clay_0_30cm_coverage_pct")
        if clay_cov is None:
            clay_cov = land_use.get("soilgrids_clay_coverage_pct")
        clay_qstatus = str(soil_s.get("clay_0_30cm_quality_status") or ("UNAVAILABLE" if clay_val is None else "MODELED_SOILGRIDS"))
        sg_n_status = str(soil_s.get("nitrogen_0_30cm_status") or "UNVALIDATED_EXCLUDED")
        gpm_ann = clim_s.get("gpm_annual_precip_mm")
        power_ann = clim_s.get("nasa_power_annual_precip_mm")
        dem_slope_status = str(veg_s.get("dem_quality_status") or "UNKNOWN")
        if avail_geospatial is None:
            avail_geospatial = 1 if (gpm_ann is not None or power_ann is not None or clay_val is not None) else 0
        if completeness_score is None:
            completeness_score = 0.0

    lu_status = str(land_use.get("status") or "UNKNOWN")
    wb = water_balance_assessment or {}
    wb_status = str(wb.get("fao56_water_balance_status") or "UNKNOWN")

    critical_missing: List[Dict[str, str]] = []
    blockers = 0

    if avail_geospatial == 0 or (gpm_ann is None and power_ann is None):
        critical_missing.append({
            "variable": "core_geospatial_and_climate_envelope",
            "severity": "NOT_ASSESSABLE",
            "impact": "No usable climate precipitation source or geospatial extraction available.",
        })
        return {
            "adequacy_status": "NOT_ASSESSABLE",
            "completeness_score": float(completeness_score),
            "land_use_verification_status": lu_status,
            "soilgrids_clay_coverage_pct": clay_cov,
            "fao56_water_balance_status": wb_status,
            "critical_blocker_count": 1,
            "critical_gaps": critical_missing,
            "adequacy_vs_completeness_explanation": (
                f"Decision adequacy is NOT_ASSESSABLE (catalog completeness={float(completeness_score):.2f}) because core climate/geospatial inputs are unavailable."
            ),
        }

    if lu_status in (LAND_USE_UNVERIFIED, LAND_USE_CONFLICTING_EVIDENCE):
        blockers += 1
        critical_missing.append({
            "variable": "cropland_land_use_verification",
            "severity": "CRITICAL_BLOCKER",
            "impact": f"{lu_status}: parcel annual arable cultivation unverified (CropFreq={land_use.get('crop_frequency_mean')}); rotation rankings are exploratory only.",
        })
    elif lu_status in (LAND_USE_LOW_EVIDENCE, LAND_USE_DATA_UNAVAILABLE):
        critical_missing.append({
            "variable": "cropland_land_use_verification",
            "severity": "CRITICAL_VERIFICATION_REQUIRED",
            "impact": f"{lu_status}: verify active arable boundary vs orchard/fallow locally.",
        })

    if (
        clay_val is None
        or clay_qstatus in ("UNAVAILABLE_NOT_INTEGRATED", "UNAVAILABLE_MASKED_PIXEL", "TEMPORAL_GUARD_EXCLUDED")
        or (clay_cov is not None and float(clay_cov) < 25.0)
    ):
        blockers += 1
        critical_missing.append({
            "variable": "soilgrids_polygon_soil_coverage",
            "severity": "CRITICAL_BLOCKER",
            "impact": f"Modeled SoilGrids covers only {clay_cov}% of polygon (status={clay_qstatus}); soil suitability unrepresentative.",
        })

    if dem_slope_status in ("UNAVAILABLE_NOT_INTEGRATED", "UNKNOWN", "UNAVAILABLE_MASKED_PIXEL"):
        critical_missing.append({
            "variable": "terrain_dem_elevation_and_slope_pct",
            "severity": "CRITICAL_VERIFICATION_REQUIRED",
            "impact": "Drainage/waterlogging and slope erosion hazards cannot be confirmed without DEM or field puddling inspection.",
        })

    if water.get("availability") == "unknown" or (water.get("source") != "rainfed" and water.get("irrigation_system") != "none"):
        critical_missing.append({
            "variable": "soil_and_irrigation_salinity_ECe_ECw",
            "severity": "CRITICAL_VERIFICATION_REQUIRED",
            "impact": "No local lab ECe/ECw salinity or irrigation flow metering exists on disk.",
        })

    if sg_n_status == "UNVALIDATED_EXCLUDED":
        critical_missing.append({
            "variable": "soil_nitrogen_and_lab_PK",
            "severity": "CRITICAL_VERIFICATION_REQUIRED",
            "impact": "SoilGrids Nitrogen is quarantined (N>SOC anomaly) and local lab N/P/K is unavailable.",
        })

    if opt_flags.get("crop_history") in ("NOT_PROVIDED", "EXPLICITLY_CONFIRMED_EMPTY", "PROVIDED_PARTIAL") or not bool(history_sufficient):
        critical_missing.append({
            "variable": "verified_multi_year_crop_history",
            "severity": "CRITICAL_VERIFICATION_REQUIRED",
            "impact": "Short/missing crop history leaves Orobanche/Fusarium/take-all break years partially unverified (SEQ_10 UNKNOWN).",
        })

    if income_potential_unavailable:
        critical_missing.append({
            "variable": "local_crop_budgets_yield_price_cost",
            "severity": "ADVISORY_GAP",
            "impact": "Income_potential remains UNKNOWN without local yield/price/cost enterprise budgets.",
        })

    if wb_status != "COMPUTED_FULL":
        critical_missing.append({
            "variable": "fao56_et0_wind_and_soil_fc_pwp",
            "severity": "ADVISORY_GAP",
            "impact": "Full FAO-56 Penman-Monteith water balance is uncomputable (WS2M wind speed, DEM, and soil FC/PWP missing).",
        })

    if opt_flags.get("equipment_constraints") == "NOT_PROVIDED" or opt_flags.get("forage_value_weight") == "NOT_PROVIDED":
        critical_missing.append({
            "variable": "optional_farmer_constraints_or_forage_priority",
            "severity": "ADVISORY_GAP",
            "impact": "Null optional farmer preferences/equipment keep operational alignment PARTIAL.",
        })

    zero_eligible = eligible_for_ranking_count is not None and int(eligible_for_ranking_count) == 0
    if blockers > 0 or zero_eligible:
        adequacy_status = "INSUFFICIENT"
    elif len(critical_missing) > 0:
        adequacy_status = "PARTIAL"
    else:
        adequacy_status = "ADEQUATE"

    return {
        "adequacy_status": adequacy_status,
        "completeness_score": float(completeness_score),
        "land_use_verification_status": lu_status,
        "soilgrids_clay_coverage_pct": clay_cov,
        "fao56_water_balance_status": wb_status,
        "critical_blocker_count": blockers + (1 if zero_eligible else 0),
        "critical_gaps": critical_missing,
        "adequacy_vs_completeness_explanation": (
            f"Catalog completeness_score={float(completeness_score):.4f} counts non-null geospatial/farmer fields ONLY; "
            f"decision-critical adequacy is '{adequacy_status}' ({len(critical_missing)} critical gap(s), "
            f"land_use='{lu_status}', SoilGrids coverage={clay_cov}%)."
        ),
    }
