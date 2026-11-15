"""Final Recommendation Output Engine (Phase J).

Assembles Phase F (Field Profile), Phase G (Knowledge/Constraints), Phase H
(Candidate Generation), and Phase I (Multi-Objective Scoring, Pareto, and
Sensitivity) into the validated frontend-ready final JSON response without
recomputing agronomic rules or optimization scores.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.agronomic.constraint_engine import AgronomicKnowledgeBase, load_knowledge_base
from src.agronomic.data_adequacy import (
    BLOCKING_ADEQUACY_STATUSES,
    assess_critical_data_adequacy,
    compute_data_completeness_score,
)

OBJECTIVE_ORDER: Tuple[str, ...] = (
    "water_efficiency",
    "soil_improvement",
    "nitrogen_contribution",
    "pest_disease_disruption",
    "erosion_protection",
    "income_potential",
    "forage_value",
    "farmer_priority_fit",
)

DECISION_ENGINE_VERSION = "FieldShift-PhaseFJ-1.1.0"
DATASET_VERSION_USED = "Guelma_Phases_AD_SoilGridsV6_250m_GPM_SMAP_11km_POWER_2016_2025_S2_2024_03"


def _deterministic_request_id(field_id: str, cand_out: Dict[str, Any]) -> str:
    payload_str = json.dumps(
        {
            "field_id": field_id,
            "generation_config": cand_out.get("generation_config", {}),
            "history": cand_out.get("history_assessment", {}).get("resolved_chronological_sequence", []),
            "preferences": cand_out.get("preference_handling", {}),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:10].upper()
    return f"REQ_{field_id}_{digest}"


def _build_field_insights(field_profile: Dict[str, Any], cand_out: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble bare-field, stress, and climate trend summaries strictly from Phase F/H data."""
    sec_a = field_profile["section_a_farmer_provided"]
    sec_b = field_profile["section_b_extracted_geospatial"]
    sec_c = field_profile["section_c_agronomic_knowledge_base"]
    ds = sec_b["extracted_datasets"]

    cf = ds["crop_frequency"]["crop_frequency_2021_2025"]
    s2_mar = ds["sentinel2"]["s2_2024_03_ndvi_10m"]
    modis = ds["modis"]
    gpm = ds["gpm_and_smap"]
    npw = ds["nasa_power"]

    bare_periods: List[Dict[str, Any]] = []
    if cf.get("value") is not None and float(cf["value"]) < 0.25:
        bare_periods.append(
            {
                "period": cf["temporal_coverage"],
                "indicator": "crop_frequency_2021_2025",
                "observed_value": cf["value"],
                "unit": cf["unit"],
                "interpretation": (
                    f"Low 2021-2025 ESA mean crop frequency ({cf['value']}) indicates predominantly sparse cropland, "
                    "fallow, orchard, or non-arable cover inside the drawn polygon."
                ),
                "data_source": cf["source_dataset"],
                "spatial_resolution": cf["spatial_resolution"],
                "quality_status": cf["quality_status"],
            }
        )
    modis_sum = modis.get("modis_ndvi_summer_2016_2025_mean", {})
    if modis_sum.get("value") is not None:
        bare_periods.append(
            {
                "period": "Summer (JJA, 2016-2025 mean)",
                "indicator": "modis_ndvi_summer_2016_2025_mean",
                "observed_value": modis_sum["value"],
                "unit": modis_sum["unit"],
                "interpretation": (
                    "Coarse 250 m seasonal summer NDVI baseline reflects post-harvest cereal senescence / dry bare stubble envelope "
                    "(single multi-year S2 pixel time series remains deferred)."
                ),
                "data_source": modis_sum["source_dataset"],
                "spatial_resolution": modis_sum["spatial_resolution"],
                "quality_status": modis_sum["quality_status"],
            }
        )
    if s2_mar.get("value") is not None and float(s2_mar["value"]) < 0.30:
        bare_periods.append(
            {
                "period": s2_mar["temporal_coverage"],
                "indicator": "s2_2024_03_ndvi_10m",
                "observed_value": s2_mar["value"],
                "unit": s2_mar["unit"],
                "interpretation": "Low March 2024 10 m NDVI snapshot suggests bare soil, delayed emergence, or sparse canopy in spring 2024.",
                "data_source": s2_mar["source_dataset"],
                "spatial_resolution": s2_mar["spatial_resolution"],
                "quality_status": s2_mar["quality_status"],
            }
        )
    # Include any farmer-reported bare fallow seasons from crop_history if present
    for h in sec_a.get("crop_history") or []:
        if h.get("crop_id_resolved") == "BARE_FALLOW":
            bare_periods.append(
                {
                    "period": f"{h['season']} {h['year']}",
                    "indicator": "farmer_crop_history",
                    "observed_value": h.get("crop_name_raw"),
                    "unit": "categorical",
                    "interpretation": "Farmer-reported historical fallow/unplanted season.",
                    "data_source": "farmer_input",
                    "spatial_resolution": "Parcel",
                    "quality_status": "USER_REPORTED",
                }
            )

    stress_periods: List[Dict[str, Any]] = []
    for diag in sec_c.get("descriptive_field_diagnostics", []):
        stress_periods.append(
            {
                "constraint_id": diag["constraint_id"],
                "status": diag["status"],
                "finding": diag["finding"],
                "agronomic_implication": diag["agronomic_implication"],
                "source_rule": diag["source_rule"],
            }
        )
    smap_sum = gpm.get("smap_rootzone_sm_summer_2016_2025_mean", {})
    if smap_sum.get("value") is not None:
        stress_periods.append(
            {
                "constraint_id": "SMAP_SUMMER_MOISTURE_ENVELOPE",
                "status": smap_sum["quality_status"],
                "finding": f"Regional SMAP summer 2016-2025 mean root-zone moisture = {smap_sum['value']} {smap_sum['unit']}.",
                "agronomic_implication": "Dry summer root-zone soil moisture envelope reinforces strict irrigation gating for summer cash crops.",
                "source_rule": smap_sum["source_dataset"],
            }
        )

    gpm_ann = gpm.get("gpm_annual_precip_2016_2025_mean_mm", {})
    np_ann = npw.get("nasa_power_annual_precip_2016_2025_mean_mm", {})
    np_t2m = npw.get("nasa_power_t2m_2016_2025_mean_c", {})
    smap_spr = gpm.get("smap_rootzone_sm_spring_2016_2025_mean", {})
    spread = (
        round(float(np_ann["value"]) - float(gpm_ann["value"]), 2)
        if gpm_ann.get("value") is not None and np_ann.get("value") is not None
        else None
    )

    climate_trend_summary = {
        "temporal_window": "2016-2025 regional multi-year seasonal/annual baseline",
        "gpm_annual_precip_mean_mm": gpm_ann.get("value"),
        "nasa_power_annual_precip_mean_mm": np_ann.get("value"),
        "cross_product_precip_spread_mm": spread,
        "nasa_power_mean_temp_c": np_t2m.get("value"),
        "smap_spring_rootzone_sm_mean": smap_spr.get("value"),
        "smap_summer_rootzone_sm_mean": smap_sum.get("value"),
        "climate_sensitivity_agreement": cand_out.get("climate_agreement_note")
        or "Dual precipitation bounds (GPM 11 km conservative vs NASA POWER ~55 km upper) preserved rather than averaged.",
        "scale_and_trend_caveat": (
            "Reported values represent 2016-2025 regional macro-climate seasonal/annual averages (11 km to ~55 km support), "
            "NOT on-farm rain-gauge trends or parcel-scale microclimate trends."
        ),
    }

    return {
        "bare_field_periods": bare_periods,
        "stress_periods": stress_periods,
        "climate_trend_summary": climate_trend_summary,
    }


def _build_strategy_evidence(
    field_profile: Dict[str, Any],
    phase_h_strat: Dict[str, Any],
    phase_i_strat: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build structured EvidenceItem records preserving exact Phase F-I provenance."""
    sec_a = field_profile["section_a_farmer_provided"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    items: List[Dict[str, Any]] = []

    # 1. Verified Water Profile (USER_REPORTED)
    wat = sec_a["water"]
    items.append(
        {
            "data_source": "farmer_input",
            "parameter": "water_profile",
            "observed_value": f"availability={wat['availability']}, source={wat['source']}, system={wat['irrigation_system']}",
            "unit": "categorical",
            "period": "Requested Planning Season",
            "derived": False,
            "interpretation": "Operational water supply governing rainfed vs strictly irrigated crop eligibility.",
            "spatial_resolution": "Parcel",
            "quality_status": "USER_REPORTED",
        }
    )

    # 2. Key Extracted Geospatial Evidence from Phase F
    metric_specs = [
        (ds["soilgrids_v6"]["clay_0_30cm"], "clay_0_30cm", "Topsoil 0-30 cm modeled clay fraction governing drainage and workability."),
        (ds["soilgrids_v6"]["ph_0_30cm"], "ph_0_30cm", "Topsoil 0-30 cm modeled soil reaction (pH) affecting legume nodulation and potato scab risk."),
        (ds["soilgrids_v6"]["soc_0_30cm"], "soc_0_30cm", "Topsoil 0-30 cm modeled organic carbon proxy; below 18 g/kg prioritizes residue-building rotations."),
        (ds["soilgrids_v6"]["nitrogen_0_30cm"], "nitrogen_0_30cm", "SoilGrids Nitrogen explicitly quarantined (excluded from all suitability and N formulas)."),
        (ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"], "gpm_annual_precip_2016_2025_mean_mm", "Conservative 11 km GPM precipitation baseline used for water-efficiency scoring."),
        (ds["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"], "nasa_power_annual_precip_2016_2025_mean_mm", "Upper ~55 km NASA POWER precipitation bound tested in climate sensitivity."),
        (ds["crop_frequency"]["crop_frequency_2021_2025"], "crop_frequency_2021_2025", "ESA 10 m 2021-2025 cropland detection frequency context (not valid pre-2021)."),
        (ds["terrain_dem"]["dem_slope_pct"], "dem_slope_pct", "DEM terrain slope unavailable locally; surface ponding and runoff steepness require local verification."),
    ]
    for metric, pname, interp in metric_specs:
        items.append(
            {
                "data_source": metric["source_dataset"],
                "parameter": pname,
                "observed_value": metric["value"],
                "unit": metric["unit"],
                "period": metric["temporal_coverage"],
                "derived": metric["quality_status"] == "MODELED_SPATIAL_ESTIMATE",
                "interpretation": interp,
                "spatial_resolution": metric["spatial_resolution"],
                "quality_status": metric["quality_status"],
            }
        )

    # 3. Sequence-level Phase G Agronomic Rules Evaluated in Phase H
    for sr in phase_h_strat["constraint_evaluations"].get("sequence_rules", []):
        items.append(
            {
                "data_source": "PhaseG_SequenceCompatibility",
                "parameter": sr["rule_id"],
                "observed_value": sr["status"],
                "unit": "rule_verdict",
                "period": f"{len(phase_i_strat['seasons'])}-season sequence",
                "derived": True,
                "interpretation": sr["reason"],
                "spatial_resolution": None,
                "quality_status": sr["evidence_classification"],
            }
        )

    # 4. Phase I Objective Score Provenance
    for obj_id in OBJECTIVE_ORDER:
        obj = phase_i_strat["scores"][obj_id]
        items.append(
            {
                "data_source": "PhaseI_MultiObjectiveScoring",
                "parameter": f"objective_{obj_id}",
                "observed_value": obj["score"],
                "unit": "normalized_index_0_to_1" if obj["score"] is not None else None,
                "period": f"{len(phase_i_strat['seasons'])}-season sequence",
                "derived": True,
                "interpretation": obj["explanation"],
                "spatial_resolution": None,
                "quality_status": obj["status"],
            }
        )

    return items


def _build_requested_crop_results(
    field_profile: Dict[str, Any],
    cand_out: Dict[str, Any],
    rank_out: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> List[Dict[str, Any]]:
    """Account transparently for every farmer target_crop_id without silent drops."""
    prefs = field_profile["section_a_farmer_provided"].get("preferences") or {}
    targets = list(prefs.get("target_crop_ids") or [])
    excluded = set(prefs.get("excluded_crop_ids") or [])
    t_report = cand_out.get("preference_handling", {}).get("target_crop_report", {})
    not_inc_reasons = t_report.get("not_included_reasons", {})

    results: List[Dict[str, Any]] = []
    for cid in targets:
        cname = kb.crops[cid]["canonical_name"] if cid in kb.crops else None
        matching = [
            s for s in rank_out["strategies"]
            if any(slot["crop_id"] == cid for slot in s["seasons"])
        ]
        elig_matches = [s for s in matching if s["feasible"]]
        infeas_matches = [s for s in matching if not s["feasible"]]
        match_ids = [s["strategy_id"] for s in matching]
        match_statuses = sorted({s["feasibility_status"] for s in matching})

        if cid not in kb.crops:
            outcome = "not_evaluated"
            reason = not_inc_reasons.get(cid, "Crop ID is not present in the Phase E/G Guelma crop inventory.")
        elif cid in excluded:
            outcome = "excluded"
            reason = not_inc_reasons.get(cid, "Crop listed in farmer excluded_crop_ids; exclusion overrides targets.")
        elif not kb.crops[cid]["in_annual_rotation_scope"]:
            outcome = "excluded"
            reason = not_inc_reasons.get(cid, "Perennial system excluded from annual crop rotation scope (RULE_PERENNIAL_EXCLUSION).")
        elif elig_matches:
            outcome = "included"
            reason = f"Included in {len(elig_matches)} eligible candidate strategy/strategies: {[s['strategy_id'] for s in elig_matches]}."
        elif infeas_matches and all(s["feasibility_status"] == "UNVERIFIED_HARD_UNKNOWN" for s in infeas_matches):
            outcome = "unavailable_due_to_insufficient_evidence"
            reason = (
                "Candidate sequence evaluated counterfactual but failed hard verification due to insufficient field evidence "
                "(e.g., unknown irrigation availability / missing prerequisite data)."
            )
        elif infeas_matches and all(s["feasibility_status"] == "INFEASIBLE_CONSTRAINT" for s in infeas_matches):
            outcome = "excluded"
            fails = sorted({r for s in infeas_matches for r in s.get("reasons", []) if "[FAIL]" in r})
            reason = (
                "Excluded by Phase G tolerance/constraint rule (verifiable with local soil/agronomic test): "
                + "; ".join(fails[:3])
            )
        elif infeas_matches:
            outcome = "excluded"
            fails = sorted({r for s in infeas_matches for r in s.get("reasons", []) if "[FAIL]" in r})
            reason = f"Excluded by hard Phase G agronomic constraints: {'; '.join(fails[:3])}"
        else:
            outcome = "not_evaluated"
            reason = "Not retained within bounded deduplicated candidate generation cap."

        results.append(
            {
                "crop_id": cid,
                "crop_name": cname,
                "outcome": outcome,
                "reason": reason,
                "included_in_strategy_ids": match_ids,
                "feasibility_statuses": match_statuses,
            }
        )
    return results


def _assess_critical_data_adequacy(
    field_profile: Dict[str, Any],
    cand_out: Dict[str, Any],
    rank_out: Dict[str, Any],
    *,
    avail_geospatial: int,
    completeness_score: float,
) -> Dict[str, Any]:
    """Delegate critical data adequacy to single canonical Phase G/I/J source of truth."""
    land_use = rank_out.get("land_use_assessment") or cand_out.get("land_use_assessment")
    wb = rank_out.get("water_balance_assessment")
    income_unavail = bool(
        rank_out.get("ranking_methodology", {}).get("inactive_objectives_audit", {}).get("income_potential")
    )
    elig_count = int(rank_out.get("feasibility_gate_summary", {}).get("eligible_for_ranking_count", 0))
    hist_suff = bool(cand_out.get("history_assessment", {}).get("sufficient_for_existing_baseline", False))
    return assess_critical_data_adequacy(
        field_profile=field_profile,
        land_use_assessment=land_use,
        water_balance_assessment=wb,
        history_sufficient=hist_suff,
        eligible_for_ranking_count=elig_count,
        income_potential_unavailable=income_unavail,
        avail_geospatial=avail_geospatial,
        completeness_score=completeness_score,
    )


def _build_data_quality(
    field_profile: Dict[str, Any],
    cand_out: Dict[str, Any],
    rank_out: Dict[str, Any],
) -> Dict[str, Any]:
    """Build Section 3 data_quality keeping dataset completeness separate from critical adequacy and decision confidence."""
    sec_d = field_profile["section_d_quality_and_uncertainty"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    opt_flags = sec_d["input_completeness_flags"]
    farmer_items = ["crop_history", "equipment_constraints", "forage_value_weight"]

    avail_geospatial, completeness_score = compute_data_completeness_score(field_profile)
    critical_adequacy = _assess_critical_data_adequacy(
        field_profile,
        cand_out,
        rank_out,
        avail_geospatial=avail_geospatial,
        completeness_score=completeness_score,
    )

    missing_data: List[str] = []
    for dom_name, dom in ds.items():
        for m_key, metric in dom.items():
            if metric.get("quality_status") in ("UNAVAILABLE_NOT_INTEGRATED", "UNVALIDATED_EXCLUDED", "UNAVAILABLE_MASKED_PIXEL"):
                missing_data.append(f"{dom_name}.{m_key} ({metric['quality_status']}): {metric['uncertainty_or_limitations']}")
    if rank_out["ranking_methodology"]["inactive_objectives_audit"].get("income_potential"):
        missing_data.append("Verified local crop yields (t/ha), farmgate prices, and production costs unavailable; numeric income_potential remains UNKNOWN.")
    for k in farmer_items:
        if opt_flags.get(k) == "NOT_PROVIDED":
            missing_data.append(f"Farmer optional input '{k}' is null ('NOT_PROVIDED'); never silently defaulted to empty list or zero.")

    unsupported_eq_tags = sorted({
        tag
        for strat in cand_out.get("strategies", [])
        for slot in strat.get("seasons", [])
        for rule in slot.get("slot_constraint_evaluations", [])
        if rule.get("rule_id") == "RULE_EQUIPMENT_CONSTRAINT_CHECK"
        for tag in (rule.get("observed_inputs") or {}).get("unsupported_equipment_tags", [])
    })
    if unsupported_eq_tags:
        missing_data.append(
            f"Unsupported equipment_constraints tag(s) {unsupported_eq_tags} are not modeled in Phase E/G crop profiles (retained as UNKNOWN)."
        )

    warnings: List[str] = []
    if unsupported_eq_tags:
        warnings.append(
            f"[UNSUPPORTED_EQUIPMENT_TAG] Equipment tag(s) {unsupported_eq_tags} are unmodeled in crop_profiles.json and treated conservatively as UNKNOWN (never assumed PASS)."
        )
    for w_msg in (rank_out.get("ranking_methodology") or {}).get("weight_warnings", []):
        warnings.append(f"[INCOME_WEIGHT_IGNORED_UNAVAILABLE_ECONOMIC_DATA] {w_msg}")
    for diag in field_profile["section_c_agronomic_knowledge_base"].get("descriptive_field_diagnostics", []):
        if diag["status"] != "ADEQUATE_BUFFERING":
            warnings.append(f"[{diag['constraint_id']}] {diag['finding']}")
    if field_profile["section_b_extracted_geospatial"]["spatial_validation"].get("validation_warnings"):
        warnings.extend(field_profile["section_b_extracted_geospatial"]["spatial_validation"]["validation_warnings"])

    land_use = rank_out.get("land_use_assessment") or cand_out.get("land_use_assessment") or {}
    if land_use.get("status") and land_use.get("status") != "LAND_USE_SUPPORTED":
        warnings.append(f"[LAND_USE:{land_use['status']}] {land_use.get('provisional_gating_reason') or 'Verify parcel cropland status.'}")
    temporal = (field_profile.get("section_a_farmer_provided", {}).get("planning") or {}).get("temporal_validation") or {}
    if temporal.get("is_historical_simulation"):
        warnings.extend(temporal.get("warnings") or ["HISTORICAL_SIMULATION mode active."])

    limitations = [
        sec_d["soilgrids_vs_laboratory_distinction"],
        sec_d["regional_climate_vs_field_distinction"],
        sec_d["missing_values_policy"],
        "Data completeness_score tracks availability of raster/tabular inputs and MUST NOT be interpreted as critical decision adequacy, recommendation confidence, or yield probability.",
        "Sensitivity stability_index measures ranking invariance across priority-weight and macro-climate perturbations; it is NOT scientific proof or statistical confidence.",
    ]

    return {
        "completeness_score": completeness_score,
        "critical_data_adequacy": critical_adequacy,
        "confidence_note": (
            f"Data completeness ({completeness_score:.2f}) measures available vs unavailable catalog inputs ONLY; "
            f"critical decision adequacy is '{critical_adequacy['adequacy_status']}' and strategy status is '{rank_out['recommendation_status']}'. "
            "Recommendations remain subject to missing local DEM/ECe and field checks."
        ),
        "missing_data": sorted(set(missing_data)),
        "warnings": sorted(set(warnings)),
        "limitations": limitations,
        "input_completeness_flags": opt_flags,
    }


def build_final_recommendation(
    field_profile: Dict[str, Any],
    candidate_output: Dict[str, Any],
    ranking_output: Dict[str, Any],
    *,
    request_id: Optional[str] = None,
    language: str = "en",
    generated_at: Optional[str] = None,
    kb: Optional[AgronomicKnowledgeBase] = None,
) -> Dict[str, Any]:
    """Assemble Phases F-I into the final farmer-facing recommendation JSON response."""
    kb = kb or load_knowledge_base()
    if language not in ("en", "fr", "ar"):
        raise ValueError(f"Unsupported language '{language}'; expected one of ('en', 'fr', 'ar').")

    f_id = field_profile["section_a_farmer_provided"]["field"]["field_id"]
    if candidate_output.get("field_id") != f_id or ranking_output.get("field_id") != f_id:
        raise ValueError("Mismatched field_id across Phase F Field Profile, Phase H candidates, and Phase I ranking.")

    req_id = request_id or _deterministic_request_id(f_id, candidate_output)
    gen_ts = generated_at or datetime.now(timezone.utc).isoformat()

    h_by_sid = {s["strategy_id"]: s for s in candidate_output.get("strategies", [])}
    strategies_final: List[Dict[str, Any]] = []

    for i_strat in ranking_output.get("strategies", []):
        sid = i_strat["strategy_id"]
        h_strat = h_by_sid[sid]

        seasons_final = [
            {
                "order": sl["season_order"],
                "season": sl["agricultural_season"],
                "year": sl["calendar_year"],
                "planting_month": sl["planting_month"],
                "crop_id": sl["crop_id"],
                "crop_name": sl["canonical_name"],
                "category": sl["crop_category"],
                "role": sl["agronomic_role"],
                "selection_status": sl["selection_status"],
                "notes": sl["supporting_notes"],
            }
            for sl in h_strat["seasons"]
        ]

        evidence_items = _build_strategy_evidence(field_profile, h_strat, i_strat)

        # Clean objective dict copying Phase I without modifying null scores; zero weights on excluded strategies
        is_feasible_strat = bool(i_strat.get("feasible", False))
        scores_clean: Dict[str, Any] = {}
        for obj in OBJECTIVE_ORDER:
            entry = dict(i_strat["scores"][obj])
            if not is_feasible_strat or entry.get("status") in ("UNKNOWN", "NOT_APPLICABLE"):
                entry["active_in_ranking"] = False
                entry["normalized_weight"] = 0.0
            scores_clean[obj] = entry

        strategies_final.append(
            {
                "strategy_id": sid,
                "name": h_strat["name"],
                "is_existing_rotation": h_strat["is_existing_rotation"],
                "description": h_strat["description"],
                "seasons": seasons_final,
                "feasibility_status": i_strat["feasibility_status"],
                "scores": scores_clean,
                "confidence": i_strat["confidence"],
                "pareto_status": i_strat["pareto_status"],
                "dominated_by": i_strat["dominated_by"],
                "rank": i_strat["rank"],
                "weighted_score": i_strat["weighted_score"],
                "provisional": bool(i_strat.get("provisional", False)),
                "land_use_status": i_strat.get("land_use_status"),
                "stability_metrics": i_strat.get("stability_metrics"),
                "explanation": {
                    "summary": i_strat["explanation"],
                    "reasons": i_strat["reasons"],
                    "evidence": evidence_items,
                    "benefits": i_strat["benefits"],
                    "risks": i_strat["risks"],
                    "assumptions": i_strat["assumptions"],
                    "information_gaps": i_strat["information_gaps"],
                    "needs_local_review": i_strat["needs_local_review"],
                    "review_checklist": i_strat["review_checklist"],
                },
            }
        )

    data_quality = _build_data_quality(field_profile, candidate_output, ranking_output)
    rec_status = ranking_output["recommendation_status"]
    sugg_id = ranking_output["suggested_strategy_id"]
    adequacy_blocked_fallback = data_quality["critical_data_adequacy"]["adequacy_status"] in BLOCKING_ADEQUACY_STATUSES
    fallback_decision_status = (
        "INFEASIBLE"
        if sugg_id is None
        else (
            "EXPLORATORY_ONLY"
            if adequacy_blocked_fallback
            else ("REQUIRES_LOCAL_VERIFICATION" if ranking_output.get("all_candidates_conditional") else "FEASIBLE_PASS")
        )
    )
    decision_gate = ranking_output.get("decision_gate") or {
        "decision_status": fallback_decision_status,
        "endorsed_recommendation_id": None if fallback_decision_status in ("INFEASIBLE", "EXPLORATORY_ONLY") else sugg_id,
        "exploratory_candidate_id": sugg_id if fallback_decision_status == "EXPLORATORY_ONLY" else None,
        "suggested_strategy_endorsed": bool(sugg_id is not None and fallback_decision_status not in ("INFEASIBLE", "EXPLORATORY_ONLY")),
        "provisional_only": bool(fallback_decision_status == "EXPLORATORY_ONLY"),
        "land_use_status": (ranking_output.get("land_use_assessment") or {}).get("status"),
        "margin_status": (ranking_output.get("sensitivity_analysis") or {}).get("margin_status"),
        "near_tie_detected": bool((ranking_output.get("sensitivity_analysis") or {}).get("near_tie_detected", False)),
        "plausible_alternatives": (ranking_output.get("sensitivity_analysis") or {}).get("plausible_alternatives", []),
        "gating_reasons": (
            [f"Critical data adequacy='{data_quality['critical_data_adequacy']['adequacy_status']}' blocks endorsement."]
            if fallback_decision_status == "EXPLORATORY_ONLY"
            else []
        ),
    }
    land_use = ranking_output.get("land_use_assessment") or candidate_output.get("land_use_assessment") or {}
    temporal_val = (
        (field_profile.get("section_a_farmer_provided", {}).get("planning") or {}).get("temporal_validation")
        or candidate_output.get("temporal_validation")
        or {}
    )
    wb_assess = ranking_output.get("water_balance_assessment") or {}

    if sugg_id is None:
        fp_status = "NO_ELIGIBLE_STRATEGY"
        partial_reason: Optional[str] = ranking_output["feasibility_gate_summary"]["notice"]
        root_status = "PARTIAL"
    elif decision_gate.get("decision_status") == "EXPLORATORY_ONLY":
        fp_status = "PARTIAL"
        partial_reason = (
            f"EXPLORATORY_ONLY / PROVISIONAL: {decision_gate.get('gating_reasons', ['Land-use evidence unverified or conflicting'])[0]} "
            "Missing local DEM, irrigation ECe, and enterprise budgets further prevent operational endorsement."
        )
        root_status = "PARTIAL"
    elif ranking_output["all_candidates_conditional"] or data_quality["missing_data"]:
        fp_status = "PARTIAL"
        partial_reason = (
            "Recommendations are conditional pending on-farm verification because local DEM slope, irrigation ECe salinity, "
            "and verified local economic budgets remain unavailable."
        )
        root_status = "PARTIAL"
    else:
        fp_status = "COMPLETE"
        partial_reason = None
        root_status = "COMPLETE"

    field_plan = {
        "field_id": f_id,
        "field_name": field_profile["section_a_farmer_provided"]["field"].get("field_name"),
        "status": fp_status,
        "partial_reason": partial_reason,
        "field_insights": _build_field_insights(field_profile, candidate_output),
        "strategies": strategies_final,
        "suggested_strategy_id": sugg_id,
        "recommendation_status": rec_status,
        "decision_gate": decision_gate,
        "land_use_assessment": land_use,
        "temporal_validation": temporal_val,
        "water_balance_assessment": wb_assess,
        "pareto_summary": {
            "active_pareto_objectives": ranking_output["pareto_analysis"]["active_pareto_objectives"],
            "front_strategy_ids": ranking_output["pareto_analysis"]["front_strategy_ids"],
            "dominated_strategy_ids": ranking_output["pareto_analysis"]["dominated_strategy_ids"],
            "equal_objective_ties": ranking_output["pareto_analysis"]["equal_objective_ties"],
            "dominance_relations": ranking_output["pareto_analysis"]["dominance_relations"],
        },
        "ranking_methodology": ranking_output["ranking_methodology"],
        "sensitivity_summary": {
            **{k: v for k, v in ranking_output["sensitivity_analysis"].items() if k != "scenario_results"},
            "non_confidence_note": "Sensitivity stability_index evaluates sensitivity to weight/climate perturbations and is NOT statistical or scientific confidence.",
        },
        "requested_crop_results": _build_requested_crop_results(field_profile, candidate_output, ranking_output, kb),
        "data_quality": data_quality,
    }

    front_n = len(field_plan["pareto_summary"]["front_strategy_ids"])
    sens_sum = field_plan["sensitivity_summary"]
    near_tie_msg = ""
    if sens_sum.get("near_tie_detected") and sens_sum.get("plausible_alternatives"):
        alt_ids = [a["strategy_id"] for a in sens_sum["plausible_alternatives"][:2]]
        near_tie_msg = (
            f" Near-tie/narrow ranking margin detected ({sens_sum.get('margin_status')}, diff={sens_sum.get('baseline_top_two_margin')}, "
            f"rel={sens_sum.get('relative_top_two_margin_pct')}%): plausible alternatives {alt_ids} should be weighed alongside rank #1."
        )

    if sugg_id is None:
        overall_summary = (
            f"Evaluated {len(strategies_final)} candidate strategies for field '{f_id}'. "
            f"No strategy can be responsibly recommended (status='{rec_status}', decision='{decision_gate['decision_status']}'); inspect hard blockers and missing evidence."
        )
    elif decision_gate.get("decision_status") == "EXPLORATORY_ONLY":
        overall_summary = (
            f"PROVISIONAL / EXPLORATORY ONLY (NOT an endorsed operational farm recommendation) for field '{f_id}'. "
            f"Evaluated {len(strategies_final)} candidates; land-use status='{land_use.get('status')}' and critical data adequacy='{data_quality['critical_data_adequacy']['adequacy_status']}' "
            f"prevent operational endorsement. Provisional top-scoring sequence='{sugg_id}'.{near_tie_msg}"
        )
    else:
        overall_summary = (
            f"Evaluated {len(strategies_final)} candidate strategies for field '{f_id}'. "
            f"Top conditional recommendation: '{sugg_id}' (Pareto front contains {front_n} non-dominated option(s); "
            f"status='{rec_status}', decision='{decision_gate['decision_status']}', adequacy='{data_quality['critical_data_adequacy']['adequacy_status']}').{near_tie_msg}"
        )

    disclaimer = (
        "Field Shift decision support integrates modeled 250 m SoilGrids estimates, coarse 11-55 km GPM/SMAP/NASA POWER climate baselines, "
        "10-20 m vegetation snapshots, and regional agronomic rules (ITGC/ICARDA/FAO). It does NOT replace laboratory soil/water testing (ECe, pH, N/P/K), "
        "local field drainage inspection, or verified farmgate market budgets. Null or unknown values are never fabricated."
    )

    return {
        "schema_version": "1.0.0",
        "request_id": req_id,
        "dataset_version_used": DATASET_VERSION_USED,
        "generated_at": gen_ts,
        "status": root_status,
        "language": language,
        "decision_engine_version": DECISION_ENGINE_VERSION,
        "overall_summary": overall_summary,
        "disclaimer": disclaimer,
        "field_plans": [field_plan],
    }
