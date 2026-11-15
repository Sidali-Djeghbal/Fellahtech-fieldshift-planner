"""Evidence-aware Multi-Objective Scoring & Ranking Engine (Phase I).

Consumes Phase H candidate-generation output (and optional Field Profile /
explicit farmer priority weights / verified local economic budgets) without
modifying Phases A-H or fabricating missing agronomic/economic values.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.agronomic.constraint_engine import AgronomicKnowledgeBase, load_knowledge_base
from src.agronomic.data_adequacy import BLOCKING_ADEQUACY_STATUSES, assess_critical_data_adequacy
from src.agronomic.land_use_assessment import (
    LAND_USE_DATA_UNAVAILABLE,
    LAND_USE_LOW_EVIDENCE,
    LAND_USE_SUPPORTED,
    assess_land_use,
)
from src.optimization.pareto import ACTIVE_SCORE_STATUSES, compute_pareto_front
from src.optimization.sensitivity import DEFAULT_MARGIN_THRESHOLDS, MarginThresholds, run_sensitivity_analysis
from src.optimization.water_balance import assess_water_balance_readiness

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

FARMER_WEIGHT_KEYS: Tuple[str, ...] = (
    "water_saving_weight",
    "soil_improvement_weight",
    "income_weight",
    "risk_reduction_weight",
    "forage_value_weight",
)

DEFAULT_FARMER_WEIGHTS: Dict[str, Optional[float]] = {
    "water_saving_weight": 0.25,
    "soil_improvement_weight": 0.30,
    "income_weight": 0.20,
    "risk_reduction_weight": 0.25,
    "forage_value_weight": None,
}

# Qualitative SOM directions from Phase G crop_profiles.json -> bounded [0, 1] ordinal index
_SOM_DIRECTION_SCORES: Dict[str, float] = {
    "HIGH_POSITIVE_ROOT_RESIDUE_AND_SOC_REBUILD": 0.95,
    "HIGH_POSITIVE_CLAY_STRUCTURE_AND_N_RICH_RESIDUE": 0.90,
    "POSITIVE_LEGUME_RESIDUE_AND_FALLOW_REPLACEMENT": 0.78,
    "PERMANENT_CANOPY_MULCH_AND_PRUNING_RESIDUES": 0.75,
    "POSITIVE_IF_STRAW_RETAINED_OR_GRAZED_MODERATELY": 0.68,
    "MODERATE_POSITIVE_LEGUME_BREAK": 0.68,
    "MODERATE_DEEP_ROOT_SUBSOIL_STALK_RESIDUE": 0.65,
    "LOW_TO_MODERATE_POSITIVE_BREAK": 0.60,
    "NEUTRAL_TO_MODERATE_POSITIVE_WITH_RESIDUE": 0.58,
    "LOW_TO_NEGATIVE_UNLESS_RESIDUE_OR_MANURE_ADDED": 0.30,
    "NEUTRAL_TO_NEGATIVE_OXIDATION_WHEN_WORKED": 0.20,
    "NEGATIVE_TILLAGE_AND_SOIL_DISTURBANCE": 0.15,
}

_EROSION_COVER_SCORES: Dict[str, float] = {
    "DURUM_WHEAT": 0.90,
    "SOFT_WHEAT": 0.90,
    "BARLEY": 0.90,
    "VETCH_OAT": 0.90,
    "OLIVE": 0.85,
    "FABA_BEAN": 0.80,
    "CHICKPEA_WINTER": 0.78,
    "LENTIL": 0.65,
    "SUNFLOWER": 0.62,
    "CHICKPEA_SPRING": 0.60,
    "TOMATO_IND": 0.40,
    "POTATO": 0.25,
    "BARE_FALLOW": 0.15,
}

_FORAGE_VALUE_SCORES: Dict[str, float] = {
    "VETCH_OAT": 1.00,
    "BARLEY": 0.55,
    "FABA_BEAN": 0.25,
    "DURUM_WHEAT": 0.20,
    "SOFT_WHEAT": 0.20,
    "CHICKPEA_WINTER": 0.15,
    "CHICKPEA_SPRING": 0.15,
    "LENTIL": 0.15,
    "BARE_FALLOW": 0.05,
    "SUNFLOWER": 0.05,
    "TOMATO_IND": 0.00,
    "POTATO": 0.00,
    "OLIVE": 0.00,
}

_QUALITATIVE_INCOME_TIERS: Dict[str, str] = {
    "TOMATO_IND": "HIGH_VALUE_IRRIGATED_CONTRACT_HORTICULTURE",
    "POTATO": "HIGH_VALUE_IRRIGATED_TUBER_HORTICULTURE",
    "SUNFLOWER": "STRATEGIC_OILSEED_CASH_CROP",
    "DURUM_WHEAT": "CORE_STAPLE_GRAIN_SUPPORT_MARKET",
    "SOFT_WHEAT": "CORE_STAPLE_GRAIN_SUPPORT_MARKET",
    "FABA_BEAN": "REGIONAL_PULSE_PROTEIN_MARKET",
    "CHICKPEA_WINTER": "REGIONAL_PULSE_PROTEIN_MARKET",
    "CHICKPEA_SPRING": "REGIONAL_PULSE_PROTEIN_MARKET",
    "LENTIL": "REGIONAL_PULSE_PROTEIN_MARKET",
    "BARLEY": "FEED_AND_STRAW_DUAL_MARKET",
    "VETCH_OAT": "ON_FARM_OR_LOCAL_HAY_FORAGE_MARKET",
    "OLIVE": "PERENNIAL_ORCHARD_OLIVE_OIL",
    "BARE_FALLOW": "ZERO_DIRECT_CROP_REVENUE",
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _root_depth_class(root_val: Optional[Dict[str, Any]]) -> str:
    if not isinstance(root_val, dict):
        return "none"
    rmax = float(root_val.get("max", 0.0) or 0.0)
    if rmax < 0.8:
        return "shallow"
    if rmax < 1.2:
        return "medium"
    return "deep"


def _extract_water_context(
    candidate_output: Dict[str, Any],
    field_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if field_profile is not None:
        w = field_profile.get("section_a_farmer_provided", {}).get("water", {})
        return {
            "availability": w.get("availability", "unknown"),
            "source": w.get("source", "other"),
            "irrigation_system": w.get("irrigation_system", "unknown"),
        }
    # Fallback cleanly from Phase H embedded slot_constraint_evaluations observed_inputs
    for strat in candidate_output.get("strategies", []):
        for season in strat.get("seasons", []):
            for r in season.get("slot_constraint_evaluations", []):
                if r.get("rule_id") == "RULE_WATER_IRRIGATION_GATE":
                    obs = r.get("observed_inputs", {})
                    return {
                        "availability": obs.get("availability", "unknown"),
                        "source": obs.get("water_source", "other"),
                        "irrigation_system": obs.get("irrigation_system", "unknown"),
                    }
    return {"availability": "unknown", "source": "other", "irrigation_system": "unknown"}


def _validate_weight_value(name: str, val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"Invalid priority weight '{name}': expected float in [0, 1] or null, got {val!r}.")
    fval = float(val)
    if math.isnan(fval) or math.isinf(fval) or fval < 0.0 or fval > 1.0:
        raise ValueError(f"Priority weight '{name}'={fval} must be finite and within [0.0, 1.0].")
    return fval


def _resolve_farmer_weights_from_mapping(
    mapping: Dict[str, Any],
    *,
    explicit_mode: bool,
    income_scorable: bool = True,
) -> Tuple[Dict[str, Optional[float]], str, List[str], str]:
    """Validate and resolve 5 farmer weights while keeping scorable defaults safe."""
    core_keys = ("water_saving_weight", "soil_improvement_weight", "income_weight", "risk_reduction_weight")
    scorable_core_keys = ("water_saving_weight", "soil_improvement_weight", "risk_reduction_weight")
    farmer_w = {k: _validate_weight_value(k, mapping.get(k)) for k in FARMER_WEIGHT_KEYS}
    any_provided = any(v is not None for v in farmer_w.values())
    if not any_provided:
        return dict(DEFAULT_FARMER_WEIGHTS), "DEFAULT_BALANCED_AGRONOMIC_WEIGHTS", [], (
            "DEFAULT_WEIGHTS_USED" if income_scorable else "DEFAULT_UNAVAILABLE_ECONOMIC_DATA"
        )

    core_provided = any(farmer_w[k] is not None for k in core_keys)
    scorable_core_provided = any(farmer_w[k] is not None for k in scorable_core_keys)
    warnings: List[str] = []
    explicit_inc = farmer_w.get("income_weight")
    inc_status = "APPLIED_VERIFIED_ECONOMIC_DATA" if (income_scorable and (explicit_inc or 0.0) > 0.0) else "NOT_REQUESTED_OR_ZERO"
    src_label = "EXPLICIT_FARMER_PRIORITY_WEIGHTS" if explicit_mode else "FIELD_PROFILE_FARMER_WEIGHTS"

    if not core_provided:
        # Preserve balanced default core priorities when only forage_value_weight (0.0 or >0) is supplied.
        for k in core_keys:
            farmer_w[k] = DEFAULT_FARMER_WEIGHTS[k]
        if not income_scorable:
            inc_status = "DEFAULT_UNAVAILABLE_ECONOMIC_DATA"
    else:
        if all((v is None or v == 0.0) for v in farmer_w.values()):
            raise ValueError(
                "All provided priority weights are zero or null; at least one positive (> 0.0) weight is required."
            )

        pos_forage = float(farmer_w.get("forage_value_weight") or 0.0) > 0.0
        explicit_scorable_pos = any((farmer_w[k] or 0.0) > 0.0 for k in scorable_core_keys) or pos_forage

        if not income_scorable and not scorable_core_provided:
            # Solo income_weight (with or without forage_value_weight) while economic_data is absent:
            # preserve default scorable core weights so active_weight_sum > 0 and never NO_RECOMMENDATION.
            for k in scorable_core_keys:
                farmer_w[k] = DEFAULT_FARMER_WEIGHTS[k]
            src_label = "DEFAULT_SCORABLE_WEIGHTS_FALLBACK_INCOME_UNAVAILABLE"
            if explicit_inc is not None and float(explicit_inc) > 0.0:
                inc_status = "IGNORED_UNAVAILABLE_ECONOMIC_DATA_DEFAULT_CORE_PRESERVED"
                warnings.append(
                    f"Requested income_weight={explicit_inc} cannot be scored because verified local crop budgets "
                    "(yield, farmgate price, cost) are unavailable (income_potential='UNKNOWN'). "
                    "Default scorable core weights (water=0.25, soil=0.30, risk=0.25) were preserved instead of "
                    "returning NO_RECOMMENDATION; effective active income weight is 0.0."
                )
        elif not income_scorable and not explicit_scorable_pos:
            omitted_scorable = [k for k in scorable_core_keys if farmer_w[k] is None]
            if omitted_scorable and explicit_inc is not None and float(explicit_inc) > 0.0:
                for k in omitted_scorable:
                    farmer_w[k] = DEFAULT_FARMER_WEIGHTS[k]
                for k in scorable_core_keys:
                    if farmer_w[k] is None:
                        farmer_w[k] = 0.0
                src_label = "PARTIAL_DEFAULT_FALLBACK_INCOME_UNAVAILABLE"
                inc_status = "IGNORED_UNAVAILABLE_ECONOMIC_DATA_DEFAULT_CORE_PRESERVED"
                warnings.append(
                    f"Requested income_weight={explicit_inc} cannot be scored without verified local economic data "
                    f"and no positive scorable priority was supplied; omitted core weights {omitted_scorable} "
                    "reverted to defaults so ranking stays valid (effective active income weight is 0.0)."
                )
            else:
                raise ValueError(
                    "All scorable priority weights were explicitly set to zero while income_weight cannot be scored "
                    "without verified local economic data; provide at least one positive (> 0.0) scorable weight."
                )
        else:
            for k in core_keys:
                if farmer_w[k] is None:
                    farmer_w[k] = 0.0
            if explicit_inc is not None and float(explicit_inc) > 0.0:
                if income_scorable:
                    inc_status = "APPLIED_VERIFIED_ECONOMIC_DATA"
                else:
                    inc_status = "IGNORED_UNAVAILABLE_ECONOMIC_DATA_RENORMALIZED"
                    warnings.append(
                        f"Requested income_weight={explicit_inc} cannot be applied in active ranking because verified local crop budgets "
                        "(yield, farmgate price, cost) are unavailable (income_potential='UNKNOWN'). "
                        "Active scorable weights were renormalized to 1.0 without numeric income weight."
                    )

    return farmer_w, src_label, warnings, inc_status


def _resolve_weights(
    candidate_output: Dict[str, Any],
    field_profile: Optional[Dict[str, Any]],
    priority_weights: Optional[Dict[str, Optional[float]]],
    *,
    income_scorable: bool = True,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]], str, List[str], str, Optional[float]]:
    """Map either farmer 5-weight preferences or explicit 8-objective weights onto OBJECTIVE_ORDER."""
    opt_flags = candidate_output.get("preference_handling", {}).get("optional_input_completeness", {})
    forage_flag = opt_flags.get("forage_value_weight", "NOT_PROVIDED")
    weight_warnings: List[str] = []
    inc_status = "DEFAULT_UNAVAILABLE_ECONOMIC_DATA" if not income_scorable else "APPLIED_VERIFIED_ECONOMIC_DATA"
    requested_inc: Optional[float] = None

    # Direct 8-objective override mode if caller passes OBJECTIVE_ORDER keys
    if priority_weights is not None:
        unknown_keys = set(priority_weights.keys()) - set(OBJECTIVE_ORDER) - set(FARMER_WEIGHT_KEYS)
        if unknown_keys:
            raise ValueError(f"Unsupported priority weight keys: {sorted(unknown_keys)}")

        using_obj_keys = bool(set(priority_weights.keys()) & set(OBJECTIVE_ORDER))
        using_farmer_keys = bool(set(priority_weights.keys()) & set(FARMER_WEIGHT_KEYS))
        if using_obj_keys and using_farmer_keys:
            raise ValueError("Do not mix 8-objective keys and 5-farmer weight keys in priority_weights.")

        if using_obj_keys:
            raw_obj: Dict[str, Optional[float]] = {obj: None for obj in OBJECTIVE_ORDER}
            for obj in OBJECTIVE_ORDER:
                if obj in priority_weights:
                    raw_obj[obj] = _validate_weight_value(obj, priority_weights[obj])
                elif obj != "forage_value":
                    raw_obj[obj] = 0.0
            pos_sum = sum(v for v in raw_obj.values() if v is not None and v > 0.0)
            if pos_sum <= 0.0:
                raise ValueError("At least one active priority weight must be positive (> 0.0).")
            req_inc_obj = raw_obj.get("income_potential")
            if req_inc_obj is not None and req_inc_obj > 0.0 and not income_scorable:
                inc_status = "IGNORED_UNAVAILABLE_ECONOMIC_DATA_RENORMALIZED"
                weight_warnings.append(
                    f"Requested income_potential weight={req_inc_obj} cannot be scored without verified local economic data."
                )
            return raw_obj, {"forage_value_weight": raw_obj.get("forage_value")}, "EXPLICIT_OBJECTIVE_WEIGHTS", weight_warnings, inc_status, req_inc_obj

        if "income_weight" in priority_weights and priority_weights["income_weight"] is not None:
            requested_inc = float(priority_weights["income_weight"])
        farmer_w, source_label, weight_warnings, inc_status = _resolve_farmer_weights_from_mapping(
            priority_weights,
            explicit_mode=True,
            income_scorable=income_scorable,
        )
    elif field_profile is not None and field_profile.get("section_a_farmer_provided", {}).get("preferences"):
        prefs = field_profile["section_a_farmer_provided"]["preferences"]
        if prefs.get("income_weight") is not None:
            requested_inc = float(prefs["income_weight"])
        farmer_w, source_label, weight_warnings, inc_status = _resolve_farmer_weights_from_mapping(
            prefs,
            explicit_mode=False,
            income_scorable=income_scorable,
        )
    else:
        farmer_w = dict(DEFAULT_FARMER_WEIGHTS)
        source_label = "DEFAULT_BALANCED_AGRONOMIC_WEIGHTS"
        inc_status = "DEFAULT_UNAVAILABLE_ECONOMIC_DATA" if not income_scorable else "APPLIED_VERIFIED_ECONOMIC_DATA"

    # Respect null vs explicitly zero forage_value_weight from Field Profile / Phase H completeness flags
    if forage_flag == "NOT_PROVIDED" and (priority_weights is None or "forage_value_weight" not in priority_weights):
        farmer_w["forage_value_weight"] = None

    w_water = float(farmer_w.get("water_saving_weight") or 0.0)
    w_soil = float(farmer_w.get("soil_improvement_weight") or 0.0)
    w_inc = float(farmer_w.get("income_weight") or 0.0)
    w_risk = float(farmer_w.get("risk_reduction_weight") or 0.0)
    w_forage = farmer_w.get("forage_value_weight")

    raw_obj = {
        "water_efficiency": w_water,
        "soil_improvement": round(0.50 * w_soil, 6),
        "nitrogen_contribution": round(0.25 * w_soil, 6),
        "erosion_protection": round(0.25 * w_soil, 6),
        "pest_disease_disruption": round(0.65 * w_risk, 6),
        "farmer_priority_fit": round(0.35 * w_risk, 6),
        "income_potential": w_inc,
        "forage_value": w_forage,
    }
    return raw_obj, farmer_w, source_label, weight_warnings, inc_status, requested_inc


def _eval_water_efficiency(
    strat: Dict[str, Any],
    water_ctx: Dict[str, Any],
    clim_summary: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> Tuple[Dict[str, Any], Optional[float]]:
    """Compute water efficiency under conservative GPM (plus NASA POWER alternate score)."""
    gpm_mm = clim_summary.get("gpm_annual_precip_mm")
    power_mm = clim_summary.get("nasa_power_annual_precip_mm")
    avail = water_ctx.get("availability", "unknown")
    source = water_ctx.get("source", "other")
    irrig_sys = water_ctx.get("irrigation_system", "unknown")
    irrig_active = (
        (source not in {"rainfed", "unknown", None})
        and (irrig_sys not in {"none", "unknown", None})
        and (avail in ("abundant", "moderate"))
    )

    crops = [s["crop_id"] for s in strat["seasons"]]
    has_strict_irrig = any(
        kb.crops[c]["parameters"]["water_requirement_category"]["value"] == "STRICTLY_IRRIGATED" for c in crops
    )
    water_unconfirmed = (
        (avail == "unknown")
        or (source == "unknown" and irrig_sys != "none")
        or (irrig_sys == "unknown" and source != "rainfed")
    )

    if (gpm_mm is None and power_mm is None) or (water_unconfirmed and has_strict_irrig):
        return (
            {
                "score": None,
                "status": "UNKNOWN",
                "evidence": [
                    f"Declared water=({avail}, {source}, {irrig_sys}); GPM={gpm_mm} mm/yr, POWER={power_mm} mm/yr."
                ],
                "evidence_classification": "UNKNOWN",
                "confidence_or_uncertainty": "UNRESOLVED_WATER_GATE",
                "missing_information": [
                    "Field irrigation availability or precipitation regime is unknown for irrigation-dependent crop(s)."
                ],
                "applicability_condition": "Always evaluated across horizon slots.",
                "explanation": "Cannot compute defensible water efficiency without verified irrigation access or rainfall data; not coerced to zero.",
            },
            None,
        )

    def _score_with_precip(precip_mm: Optional[float]) -> float:
        vals: List[float] = []
        for cid in crops:
            p = kb.crops[cid]["parameters"]
            wcat = p["water_requirement_category"]["value"]
            min_rain = p["min_annual_rainfed_precip_mm"]["value"]
            if cid == "BARE_FALLOW":
                vals.append(0.60)
                continue
            if wcat == "STRICTLY_IRRIGATED":
                if source == "rainfed" or irrig_sys == "none":
                    vals.append(0.0)
                elif irrig_sys == "drip":
                    vals.append(0.40)
                elif irrig_sys == "sprinkler":
                    vals.append(0.30)
                else:
                    vals.append(0.20)
                continue
            p_eff = float(precip_mm) if precip_mm is not None else 0.0
            p_min = float(min_rain or 300.0)
            headroom = max(-0.35, min(0.45, (p_eff - p_min) / 300.0))
            if wcat == "RAINFED_SEMI_ARID_TOLERANT":
                # Semi-arid resilience confers maximum advantage under moisture limitation (<=500 mm);
                # under humid sub-humid regimes (>=600 mm), drought specialization loses its relative edge.
                dry_edge = max(0.0, min(1.0, (600.0 - p_eff) / 100.0))
                cat_bonus = 0.05 + 0.10 * dry_edge
            else:
                cat_bonus = 0.05
            irrig_buf = 0.05 if irrig_active else 0.0
            vals.append(_clip01(0.40 + headroom + cat_bonus + irrig_buf))
        return round(sum(vals) / len(vals), 4)

    primary_precip = gpm_mm if gpm_mm is not None else power_mm
    score_primary = _score_with_precip(primary_precip)
    score_power = _score_with_precip(power_mm) if power_mm is not None else None

    spread = abs(score_power - score_primary) if (score_power is not None and gpm_mm is not None) else None
    missing: List[str] = []
    if gpm_mm is None or power_mm is None:
        missing.append("One regional precipitation source (GPM or NASA POWER) is missing.")
    if water_unconfirmed:
        missing.append("Farmer water parameters include 'unknown'; rainfed tolerance scored conservatively only.")

    status = "PARTIAL" if (gpm_mm is None or power_mm is None or water_unconfirmed) else "SCORED"
    conf = (
        f"MODERATE (Coarse 11 km GPM vs 55-69 km POWER spread delta={spread:.4f})"
        if spread is not None
        else "LOW_PARTIAL (Single climate source or unknown water availability)"
    )
    return (
        {
            "score": score_primary,
            "status": status,
            "evidence": [
                "RULE_WATER_IRRIGATION_GATE & RULE_PRECIPITATION_REGIME",
                f"Conservative GPM precip={gpm_mm} mm/yr; NASA POWER={power_mm} mm/yr; score_power={score_power}.",
            ],
            "evidence_classification": "REMOTE_SENSING_DERIVED + REGIONAL_CLIMATE_CONTEXT",
            "confidence_or_uncertainty": conf,
            "missing_information": missing,
            "applicability_condition": "Always applicable; ordinal suitability comparison only (NOT volumetric FAO-56 ETc - P_eff).",
            "explanation": (
                f"Ordinal water suitability score {score_primary:.4f} (NOT volumetric FAO-56 ETc/irrigation demand) "
                f"comparing drought tolerance and farmer irrigation access against macro GPM ({gpm_mm} mm/yr) vs POWER ({power_mm} mm/yr)."
            ),
        },
        score_power,
    )


def _eval_soil_improvement(
    strat: Dict[str, Any],
    soil_summary: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> Dict[str, Any]:
    crops = [s["crop_id"] for s in strat["seasons"]]
    soc = soil_summary.get("soc_0_30cm_g_kg")
    clay = soil_summary.get("clay_0_30cm_pct")

    slot_scores: List[float] = []
    root_classes: set = set()
    for cid in crops:
        p = kb.crops[cid]["parameters"]
        som_dir = (p["som_contribution"]["value"] or {}).get("direction", "")
        slot_scores.append(_SOM_DIRECTION_SCORES.get(som_dir, 0.50))
        rc = _root_depth_class(p["root_depth_m"]["value"])
        if rc != "none":
            root_classes.add(rc)

    base = sum(slot_scores) / len(slot_scores)
    diversity_bonus = 0.05 if len(root_classes) >= 2 else 0.0
    score = round(_clip01(base + diversity_bonus), 4)

    missing: List[str] = ["Quantitative carbon balance (quantitative_t_c_ha_yr) is null in KB; index is ordinal."]
    if soc is None or clay is None:
        missing.append("SoilGrids 250 m soc_0_30cm or clay_0_30cm is missing/masked locally.")
    status = "PARTIAL" if (soc is None or clay is None) else "SCORED"

    soc_note = f"Topsoil SoilGrids SOC={soc} g/kg, clay={clay}%" if soc is not None else "Topsoil SOC/clay unavailable"
    return {
        "score": score,
        "status": status,
        "evidence": [
            "RULE_SOIL_SOC_PRIORITY & crop_profiles.som_contribution.direction + root_depth_m",
            soc_note,
        ],
        "evidence_classification": "AGRONOMIC_RULE_BASED + EXPERT_ASSUMPTION + MODELED_SPATIAL_ESTIMATE",
        "confidence_or_uncertainty": "LOW_TO_MODERATE (Qualitative SOM directions + 250 m SoilGrids proxy; not t C/ha/yr or lab test)",
        "missing_information": missing,
        "applicability_condition": "Always applicable; highlights SOC depletion (<18 g/kg) and clay workability.",
        "explanation": (
            f"Ordinal soil-restoration index {score:.4f} combining KB organic residue directions across {len(crops)} slots "
            f"and rooting-depth diversity ({sorted(root_classes)})."
        ),
    }


def _eval_nitrogen_contribution(
    strat: Dict[str, Any],
    soil_summary: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> Dict[str, Any]:
    crops = [s["crop_id"] for s in strat["seasons"]]
    n_slots: List[float] = []
    unquantified_legumes: List[str] = []

    for cid in crops:
        p = kb.crops[cid]["parameters"]
        nfix_val = p["nitrogen_fixation_potential_kg_n_ha"]["value"]
        cat = kb.crops[cid]["crop_category"]
        if isinstance(nfix_val, dict) and nfix_val.get("max"):
            # FABA_BEAN quantified 100-200 kg N/ha
            n_slots.append(0.95)
        elif cat in ("Winter Food Legume", "Spring Food Legume", "Winter/Early-Spring Pulse"):
            n_slots.append(0.72)
            unquantified_legumes.append(cid)
        elif cid == "VETCH_OAT":
            n_slots.append(0.68)
            unquantified_legumes.append(cid)
        elif cid == "BARE_FALLOW":
            n_slots.append(0.05)
        else:
            n_slots.append(0.0)

    # Check SEQ_07 beneficial legume/vetch -> cereal transitions
    seq_rules = {r["rule_id"]: r for r in strat["constraint_evaluations"].get("sequence_rules", [])}
    seq07 = seq_rules.get("SEQ_07_LEGUME_CEREAL_SYNERGY", {})
    obs07 = seq07.get("observed_inputs") or {}
    transitions = obs07.get("transitions") or obs07.get("beneficial_transitions") or []
    n_synergy_count = len(transitions)
    synergy_bonus = min(0.12, 0.06 * n_synergy_count)

    # Sequence-level biological N supply score normalized so 1+ legumes in 2-4 yrs score meaningfully (~0.35-0.75)
    raw_mean = sum(n_slots) / len(n_slots)
    score = round(_clip01(0.10 + 0.90 * raw_mean + synergy_bonus), 4)

    missing = [
        f"Field SoilGrids nitrogen_0_30cm is {soil_summary.get('nitrogen_0_30cm_status', 'UNVALIDATED_EXCLUDED')} (quarantined)."
    ]
    if unquantified_legumes:
        missing.append(
            f"Quantitative kg N/ha fixation is null in KB for {sorted(set(unquantified_legumes))}; scored via SEQ_07 legume break role."
        )

    if "VETCH_OAT" in crops:
        missing.append(
            "Vetch-Oat N contribution varies strongly with vetch:oat seed ratio and off-field hay baling export vs in-situ grazing."
        )

    status = "PARTIAL" if unquantified_legumes else "SCORED"
    return {
        "score": score,
        "status": status,
        "evidence": [
            "crop_profiles.nitrogen_fixation_potential_kg_n_ha & SEQ_07_LEGUME_CEREAL_SYNERGY",
            f"Beneficial legume/forage -> cereal transitions: {n_synergy_count}.",
        ],
        "evidence_classification": "AGRONOMIC_RULE_BASED + EXPERT_ASSUMPTION",
        "confidence_or_uncertainty": "LOW_TO_MODERATE (SoilGrids N quarantined; non-faba legumes lack local kg N/ha trials)",
        "missing_information": missing,
        "applicability_condition": "Always applicable; excludes quarantined SoilGrids Nitrogen.",
        "explanation": (
            f"Symbiotic biological N index {score:.4f} driven by legume/vetch frequency and {n_synergy_count} "
            f"legume-to-cereal carry-over transition(s) without using quarantined SoilGrids Nitrogen."
        ),
    }


def _eval_pest_disease_disruption(
    strat: Dict[str, Any],
    history_assessment: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> Dict[str, Any]:
    crops = [s["crop_id"] for s in strat["seasons"]]
    seq_rules = {r["rule_id"]: r for r in strat["constraint_evaluations"].get("sequence_rules", [])}
    seq10 = seq_rules.get("SEQ_10_UNKNOWN_PREDECESSOR_GUARD", {})
    prev_known = seq10.get("status") == "PASS" and history_assessment.get("most_recent_predecessor") in kb.crops

    transitions: List[float] = []
    pairs: List[Tuple[str, str]] = []
    if prev_known:
        pairs.append((history_assessment["most_recent_predecessor"], crops[0]))
    for i in range(len(crops) - 1):
        pairs.append((crops[i], crops[i + 1]))

    for c_prev, c_curr in pairs:
        f_prev = kb.crops[c_prev]["botanical_family"]
        f_curr = kb.crops[c_curr]["botanical_family"]
        if c_prev == c_curr:
            transitions.append(0.0)
        elif f_prev != f_curr and "Mixed_Fabaceae_Poaceae" not in (f_prev, f_curr):
            transitions.append(1.0)
        elif "Mixed_Fabaceae_Poaceae" in (f_prev, f_curr) and c_prev != c_curr:
            transitions.append(0.75)
        else:
            transitions.append(0.0)

    trans_ratio = sum(transitions) / len(transitions) if transitions else 0.0
    warn_penalty = 0.0
    for rid in ("SEQ_02_CEREAL_REPETITION", "SEQ_04_PULSE_BROOMRAPE_BREAK"):
        if seq_rules.get(rid, {}).get("status") == "WARNING":
            warn_penalty += 0.12
    seq06_rule = seq_rules.get("SEQ_06_VETCH_OAT_ROLE_AND_REPEAT", {})
    if seq06_rule.get("status") == "WARNING":
        rep_mode = (seq06_rule.get("observed_inputs") or {}).get("repeat_mode")
        # Consecutive 1-yr repeat (<2 yr break) incurs full sanitation penalty; 2-yr hay cycle carries lighter management caution
        warn_penalty += 0.12 if rep_mode == "CONSECUTIVE_1YR" else 0.04
    fail_penalty = sum(
        0.45 for rid in ("SEQ_02_CEREAL_REPETITION", "SEQ_03_SOLANACEAE_BREAK", "SEQ_04_PULSE_BROOMRAPE_BREAK", "SEQ_05_SUNFLOWER_BREAK")
        if seq_rules.get(rid, {}).get("status") == "FAIL"
    )
    score = round(_clip01(0.30 + 0.70 * trans_ratio - warn_penalty - fail_penalty), 4)

    missing: List[str] = []
    if not prev_known:
        missing.append("T-1 crop_history is UNKNOWN (SEQ_10_UNKNOWN_PREDECESSOR_GUARD); slot-1 pest carryover unverified.")

    status = "SCORED" if prev_known else "PARTIAL"
    return {
        "score": score,
        "status": status,
        "evidence": [
            "SEQ_02..SEQ_07 & SEQ_10 botanical-family break transitions",
            f"Transition diversity ratio={trans_ratio:.3f} over {len(pairs)} break(s); prev_known={prev_known}.",
        ],
        "evidence_classification": "AGRONOMIC_RULE_BASED",
        "confidence_or_uncertainty": "MODERATE-HIGH when T-1 history known; PARTIAL when T-1 history missing",
        "missing_information": missing,
        "applicability_condition": "Always applicable across multi-season sequence transitions.",
        "explanation": (
            f"Pest/disease break score {score:.4f} based on cross-family transitions ({len(pairs)} pairs) and Phase G "
            f"cereal/Solanaceae/broomrape sanitary guards."
        ),
    }


def _eval_erosion_protection(
    strat: Dict[str, Any],
    veg_terrain: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> Dict[str, Any]:
    crops = [s["crop_id"] for s in strat["seasons"]]
    dem_slope = veg_terrain.get("dem_slope_pct")
    dem_status = veg_terrain.get("dem_quality_status", "UNAVAILABLE_NOT_INTEGRATED")

    seq_rules = {r["rule_id"]: r for r in strat["constraint_evaluations"].get("sequence_rules", [])}
    seq08_status = seq_rules.get("SEQ_08_BARE_FALLOW_COVER", {}).get("status")

    base = sum(_EROSION_COVER_SCORES.get(c, 0.50) for c in crops) / len(crops)
    penalty = 0.20 if seq08_status == "FAIL" else (0.10 if seq08_status == "WARNING" else 0.0)
    slope_adj = 0.0
    missing: List[str] = []
    if dem_slope is None:
        missing.append(f"Terrain DEM slope is {dem_status}; field runoff steepness hazard unverified.")
        status = "PARTIAL"
        conf = "LOW_TO_MODERATE (Crop winter cover evaluated; site DEM slope unavailable locally)"
    else:
        # Moderate slope amplification if steeper slopes lack dense cover
        if float(dem_slope) >= 8.0 and base < 0.70:
            slope_adj = -0.10
        status = "SCORED"
        conf = "MODERATE (Crop canopy cover + local DEM slope)"

    score = round(_clip01(base - penalty + slope_adj), 4)
    return {
        "score": score,
        "status": status,
        "evidence": [
            "crop_profiles winter/spring canopy timing & SEQ_08_BARE_FALLOW_COVER",
            f"dem_slope_pct={dem_slope} ({dem_status}).",
        ],
        "evidence_classification": "AGRONOMIC_RULE_BASED" + (" + REMOTE_SENSING_DERIVED" if dem_slope is not None else ""),
        "confidence_or_uncertainty": conf,
        "missing_information": missing,
        "applicability_condition": "Always applicable; favors continuous winter living cover over bare fallow or tuber lifting.",
        "explanation": (
            f"Soil cover & erosion protection index {score:.4f} driven by winter canopy density and avoidance of bare fallow/root lifting."
        ),
    }


def _eval_income_potential(
    strat: Dict[str, Any],
    economic_data: Optional[Dict[str, Dict[str, float]]],
    kb: AgronomicKnowledgeBase,
) -> Dict[str, Any]:
    crops = [s["crop_id"] for s in strat["seasons"]]
    tiers = [_QUALITATIVE_INCOME_TIERS.get(c, "UNCLASSIFIED") for c in crops]

    has_complete_econ = bool(
        economic_data
        and all(
            cid in economic_data
            and economic_data[cid] is not None
            and (
                "net_margin_per_ha" in economic_data[cid]
                or (
                    "expected_yield_t_ha" in economic_data[cid]
                    and "price_per_t" in economic_data[cid]
                    and "cost_per_ha" in economic_data[cid]
                )
            )
            for cid in crops
        )
    )

    if not has_complete_econ:
        return {
            "score": None,
            "status": "UNKNOWN",
            "qualitative_market_tiers": tiers,
            "evidence": [
                "No verified farmgate price, production-cost, or calibrated local yield table supplied in Phases A-H."
            ],
            "evidence_classification": "UNKNOWN",
            "confidence_or_uncertainty": "NONE (Quantitative financial return cannot be estimated without verified local market/cost budgets)",
            "missing_information": [
                "Verified local crop yields (t/ha), farmgate prices (DZD/t), and production costs (DZD/ha) are unavailable."
            ],
            "applicability_condition": "Scored numerically ONLY when verified local yield, price, and production-cost budgets are supplied.",
            "explanation": (
                f"Qualitative market orientation covers {tiers}, but quantitative income_potential remains UNKNOWN "
                f"(never fabricated or assigned zero)."
            ),
        }

    margins: List[float] = []
    for cid in crops:
        ed = economic_data[cid]  # type: ignore[index]
        if "net_margin_per_ha" in ed:
            margins.append(float(ed["net_margin_per_ha"]))
        else:
            margins.append(float(ed["expected_yield_t_ha"]) * float(ed["price_per_t"]) - float(ed["cost_per_ha"]))

    avg_margin = sum(margins) / len(margins)
    # Normalize smoothly via caller min-max or anchored scale; initial store raw_margin for cross-strategy scaling
    return {
        "score": None,  # Populated once all strategies' verified margins are normalized together
        "raw_verified_mean_margin_per_ha": round(avg_margin, 2),
        "status": "SCORED",
        "qualitative_market_tiers": tiers,
        "evidence": ["Caller-supplied verified local yield, price, and production-cost budget table."],
        "evidence_classification": "MEASURED_OR_OBSERVED",
        "confidence_or_uncertainty": "HIGH_CONDITIONAL_ON_SUPPLIED_BUDGET",
        "missing_information": [],
        "applicability_condition": "Verified local yield/price/cost budget supplied.",
        "explanation": f"Verified mean annual net margin = {avg_margin:.2f}/ha across supplied market budgets.",
    }


def _eval_forage_value(
    strat: Dict[str, Any],
    forage_weight: Optional[float],
    forage_completeness_flag: str,
) -> Dict[str, Any]:
    if forage_weight is None or forage_completeness_flag == "NOT_PROVIDED":
        return {
            "score": None,
            "status": "NOT_APPLICABLE",
            "evidence": [f"forage_value_weight flag is '{forage_completeness_flag}' (null / not provided)."],
            "evidence_classification": "UNKNOWN",
            "confidence_or_uncertainty": "NOT_APPLICABLE (Forage priority not specified by farmer)",
            "missing_information": ["Optional forage_value_weight is null ('NOT_PROVIDED'); demand cannot be inferred."],
            "applicability_condition": "Active only when farmer provides forage_value_weight > 0.",
            "explanation": "Forage objective marked NOT_APPLICABLE because farmer forage priority was not provided (null preserved).",
        }
    if float(forage_weight) <= 0.0:
        return {
            "score": None,
            "status": "NOT_APPLICABLE",
            "evidence": ["Farmer explicitly set forage_value_weight = 0.0."],
            "evidence_classification": "USER_REPORTED",
            "confidence_or_uncertainty": "EXPLICITLY_INACTIVE",
            "missing_information": [],
            "applicability_condition": "Active only when forage_value_weight > 0.",
            "explanation": "Forage objective marked NOT_APPLICABLE because farmer explicitly assigned zero weight.",
        }

    crops = [s["crop_id"] for s in strat["seasons"]]
    score = round(sum(_FORAGE_VALUE_SCORES.get(c, 0.0) for c in crops) / len(crops), 4)
    return {
        "score": score,
        "status": "SCORED",
        "evidence": [
            "crop_profiles forage role (VETCH_OAT primary hay, BARLEY straw/grain, pulse stubble)",
            f"Farmer forage_value_weight={forage_weight}.",
        ],
        "evidence_classification": "AGRONOMIC_RULE_BASED",
        "confidence_or_uncertainty": "MODERATE (Qualitative biomass/straw yield hierarchy without local dry-matter t/ha measurement)",
        "missing_information": ["Quantitative forage DM t/ha depends on cultivar and rainfall."],
        "applicability_condition": "Active because farmer supplied forage_value_weight > 0.",
        "explanation": f"Forage & fodder score {score:.4f} driven by Vetch-Oat hay share and Barley dual-purpose residue.",
    }


def _eval_farmer_priority_fit(
    strat: Dict[str, Any],
    pref_handling: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
) -> Dict[str, Any]:
    crops = [s["crop_id"] for s in strat["seasons"]]
    crops_set = set(crops)
    excluded = set(pref_handling.get("excluded_crop_ids", []))
    target_rep = pref_handling.get("target_crop_report", {})
    req_targets = [
        t for t in target_rep.get("requested_targets", [])
        if t in kb.crops and kb.crops[t]["in_annual_rotation_scope"] and t not in excluded
    ]
    equip_flag = pref_handling.get("optional_input_completeness", {}).get("equipment_constraints", "NOT_PROVIDED")

    if crops_set & excluded:
        return {
            "score": 0.0,
            "status": "SCORED",
            "evidence": [f"Contains excluded crop(s): {sorted(crops_set & excluded)}."],
            "evidence_classification": "USER_REPORTED",
            "confidence_or_uncertainty": "HIGH (Direct violation of farmer excluded_crop_ids)",
            "missing_information": [],
            "applicability_condition": "Always applicable.",
            "explanation": "Contains farmer-excluded crop; preference fit = 0.0.",
        }

    # Target alignment component [0..0.5]
    if req_targets:
        hit_ratio = sum(1 for t in req_targets if t in crops_set) / len(req_targets)
        target_pts = 0.50 * hit_ratio
    else:
        target_pts = 0.45

    # Operational readiness component [0..0.5]
    def _ops_slot_score(w_st: str, e_st: str) -> float:
        if w_st == "FAIL" or e_st == "FAIL":
            return 0.0
        if w_st == "PASS" and e_st == "PASS":
            return 1.0
        if w_st == "PASS" and e_st == "UNKNOWN":
            return 0.75
        if w_st == "PASS" and e_st == "WARNING":
            return 0.35
        if w_st == "WARNING" and e_st == "PASS":
            return 0.60
        if w_st == "WARNING" and e_st == "UNKNOWN":
            return 0.50
        if w_st == "WARNING" and e_st == "WARNING":
            return 0.25
        if w_st == "UNKNOWN" and e_st == "WARNING":
            return 0.20
        return 0.45

    slot_scores: List[float] = []
    unk_baseline_scores: List[float] = []
    warn_indices: List[int] = []
    unsupported_eq = sorted({
        tag
        for s in strat["seasons"]
        for r in s["slot_constraint_evaluations"]
        if r["rule_id"] == "RULE_EQUIPMENT_CONSTRAINT_CHECK"
        for tag in (r.get("observed_inputs") or {}).get("unsupported_equipment_tags", [])
    })
    for idx, s in enumerate(strat["seasons"]):
        rules = {r["rule_id"]: r["status"] for r in s["slot_constraint_evaluations"]}
        w_st = rules.get("RULE_WATER_IRRIGATION_GATE", "UNKNOWN")
        e_st = rules.get("RULE_EQUIPMENT_CONSTRAINT_CHECK") or rules.get("RULE_EQUIPMENT_COMPATIBILITY", "UNKNOWN")
        slot_scores.append(_ops_slot_score(w_st, e_st))
        unk_baseline_scores.append(_ops_slot_score(w_st, "UNKNOWN"))
        if e_st == "WARNING":
            warn_indices.append(idx)

    mean_slot = sum(slot_scores) / len(slot_scores)
    mean_unk_baseline = sum(unk_baseline_scores) / len(unk_baseline_scores)
    if warn_indices:
        # Never let unrelated PASS slots override or elevate an explicit machinery conflict above UNKNOWN.
        min_warn_slot = min(slot_scores[i] for i in warn_indices)
        ops_factor = max(
            0.0,
            min(0.50 * mean_slot + 0.50 * min_warn_slot, mean_unk_baseline - 0.05 * len(warn_indices)),
        )
    else:
        ops_factor = mean_slot

    ops_pts = 0.50 * ops_factor
    score = round(_clip01(target_pts + ops_pts), 4)

    missing: List[str] = []
    if equip_flag == "NOT_PROVIDED":
        missing.append("equipment_constraints is null ('NOT_PROVIDED'); machinery compatibility unverified (RULE_EQUIPMENT_CONSTRAINT_CHECK).")
    if unsupported_eq:
        missing.append(
            f"Unsupported equipment_constraints tag(s) {unsupported_eq} not modeled in Phase E/G crop profiles; kept as UNKNOWN (not PASS)."
        )
    status = "PARTIAL" if (equip_flag == "NOT_PROVIDED" or bool(unsupported_eq)) else "SCORED"
    return {
        "score": score,
        "status": status,
        "evidence": [
            "preference_handling (target_crop_ids, excluded_crop_ids) & RULE_EQUIPMENT_CONSTRAINT_CHECK / RULE_WATER_IRRIGATION_GATE",
            f"equipment_constraints={equip_flag}; eligible_targets_matched={sum(1 for t in req_targets if t in crops_set)}/{len(req_targets)}; equipment_warning_slots={len(warn_indices)}; unsupported_equipment_tags={unsupported_eq}.",
        ],
        "evidence_classification": "USER_REPORTED + AGRONOMIC_RULE_BASED",
        "confidence_or_uncertainty": "HIGH when equipment_constraints confirmed & modeled; PARTIAL when null ('NOT_PROVIDED') or contains unmodeled tags",
        "missing_information": missing,
        "applicability_condition": "Always applicable.",
        "explanation": f"Farmer priority & operational fit score {score:.4f} combining target alignment, exclusions, irrigation, and equipment status.",
    }


def _normalize_income_scores_across_pool(scored_map: Dict[str, Dict[str, Any]]) -> None:
    """Normalize verified net margins into [0.1, 1.0] ONLY when economic_data was supplied."""
    eligible_margins = [
        m["income_potential"]["raw_verified_mean_margin_per_ha"]
        for m in scored_map.values()
        if m["income_potential"].get("status") == "SCORED"
        and "raw_verified_mean_margin_per_ha" in m["income_potential"]
    ]
    if not eligible_margins:
        return
    m_min = min(eligible_margins)
    m_max = max(eligible_margins)
    span = m_max - m_min
    for m in scored_map.values():
        inc = m["income_potential"]
        if inc.get("status") == "SCORED" and "raw_verified_mean_margin_per_ha" in inc:
            val = inc.pop("raw_verified_mean_margin_per_ha")
            inc["score"] = 1.0 if span <= 1e-9 else round(0.10 + 0.90 * ((val - m_min) / span), 4)


def _derive_benefits_and_risks(
    strat: Dict[str, Any],
    scores: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    benefits: List[str] = []
    risks: List[str] = []

    if (scores["pest_disease_disruption"].get("score") or 0.0) >= 0.75:
        benefits.append("Strong botanical-family break disrupts cereal soil-borne root rot and grass weed cycles.")
    if (scores["soil_improvement"].get("score") or 0.0) >= 0.70:
        benefits.append("Supports soil organic matter and structural resilience via legume/forage residue return.")
    if (scores["nitrogen_contribution"].get("score") or 0.0) >= 0.45:
        benefits.append("Provides biological nitrogen fixation carry-over reducing synthetic N reliance.")
    if (scores["water_efficiency"].get("score") or 0.0) >= 0.75:
        benefits.append("High drought/rainfall efficiency aligned with semi-arid Guelma precipitation.")
    if (scores["erosion_protection"].get("score") or 0.0) >= 0.75:
        benefits.append("Maintains protective winter ground cover during peak seasonal rainfall.")
    if scores["forage_value"].get("status") == "SCORED" and (scores["forage_value"].get("score") or 0.0) >= 0.50:
        benefits.append("Delivers substantial on-farm hay/forage biomass alongside grain breaks.")

    hard_fails = strat["constraint_evaluations"].get("hard_fail_reasons", [])
    hard_unks = strat["constraint_evaluations"].get("hard_unknown_reasons", [])
    for hf in hard_fails:
        risks.append(f"HARD CONSTRAINT BLOCKER: {hf}")
    for hu in hard_unks:
        risks.append(f"HARD UNRESOLVED BLOCKER: {hu}")
    for gap in strat.get("information_gaps", []):
        risks.append(gap)
    for r in strat.get("reasons", []):
        if r.startswith("[WARNING]"):
            risks.append(r)

    return benefits, risks


def rank_rotation_candidates(
    candidate_output: Dict[str, Any],
    field_profile: Optional[Dict[str, Any]] = None,
    priority_weights: Optional[Dict[str, Optional[float]]] = None,
    economic_data: Optional[Dict[str, Dict[str, float]]] = None,
    kb: Optional[AgronomicKnowledgeBase] = None,
    *,
    margin_thresholds: MarginThresholds = DEFAULT_MARGIN_THRESHOLDS,
) -> Dict[str, Any]:
    """Evaluate multi-objective scores, Pareto front, normalized weighted rankings, and sensitivity."""
    kb = kb or load_knowledge_base()
    raw_strategies = list(candidate_output.get("strategies", []))
    field_insights = candidate_output.get("field_insights", {})
    soil_summary = field_insights.get("soil_summary_modeled_250m", {})
    clim_summary = field_insights.get("climate_water_summary", {})
    veg_terrain = field_insights.get("vegetation_and_terrain_summary", {})
    history_assessment = candidate_output.get("history_assessment", {})
    pref_handling = candidate_output.get("preference_handling", {})
    water_ctx = _extract_water_context(candidate_output, field_profile)

    land_use = candidate_output.get("land_use_assessment")
    if land_use is None and field_profile is not None:
        land_use = (
            field_profile.get("section_c_agronomic_knowledge_base", {}).get("land_use_assessment")
            or assess_land_use(field_profile)
        )
    if land_use is None:
        cf_val = veg_terrain.get("crop_frequency_2021_2025")
        if cf_val is None:
            lu_status, is_prov, req_verif = LAND_USE_DATA_UNAVAILABLE, False, True
        elif float(cf_val) < 0.05:
            lu_status, is_prov, req_verif = "LAND_USE_UNVERIFIED", True, True
        elif float(cf_val) < 0.40:
            lu_status, is_prov, req_verif = LAND_USE_LOW_EVIDENCE, False, True
        else:
            lu_status, is_prov, req_verif = LAND_USE_SUPPORTED, False, False
        land_use = {
            "status": lu_status,
            "is_provisional": is_prov,
            "requires_local_verification": req_verif,
            "crop_frequency_mean": cf_val,
            "explanations": [f"Fallback land-use status inferred from crop_frequency_2021_2025={cf_val}."],
            "provisional_gating_reason": (
                f"Provisional exploratory gating due to crop_frequency_2021_2025={cf_val}."
                if is_prov
                else ("Verify active arable parcel use locally." if req_verif else None)
            ),
        }

    water_balance_assessment = (
        assess_water_balance_readiness(field_profile, kb.crops)
        if field_profile is not None
        else {
            "current_scoring_method": "ORDINAL_REGIME_SUITABILITY",
            "fao56_water_balance_status": "UNKNOWN",
            "missing_inputs": ["Full field_profile absent; daily ET0 / DEM / FC-PWP unavailable."],
        }
    )

    # 1. Score all non-forage objectives first so income_scorable is known before weight fallback resolution
    per_strategy_scores: Dict[str, Dict[str, Dict[str, Any]]] = {}
    power_water_scores: Dict[str, float] = {}

    for strat in raw_strategies:
        sid = strat["strategy_id"]
        water_eval, power_score = _eval_water_efficiency(strat, water_ctx, clim_summary, kb)
        if power_score is not None:
            power_water_scores[sid] = power_score
        per_strategy_scores[sid] = {
            "water_efficiency": water_eval,
            "soil_improvement": _eval_soil_improvement(strat, soil_summary, kb),
            "nitrogen_contribution": _eval_nitrogen_contribution(strat, soil_summary, kb),
            "pest_disease_disruption": _eval_pest_disease_disruption(strat, history_assessment, kb),
            "erosion_protection": _eval_erosion_protection(strat, veg_terrain, kb),
            "income_potential": _eval_income_potential(strat, economic_data, kb),
            "farmer_priority_fit": _eval_farmer_priority_fit(strat, pref_handling, kb),
        }

    _normalize_income_scores_across_pool(per_strategy_scores)

    # Partition strictly on Phase H feasibility gates
    eligible_strats = [s for s in raw_strategies if bool(s.get("feasible", False))]
    infeasible_strats = [s for s in raw_strategies if not bool(s.get("feasible", False))]

    income_scorable = any(
        per_strategy_scores[s["strategy_id"]]["income_potential"]["status"] == "SCORED"
        for s in (eligible_strats or raw_strategies)
    )
    (
        raw_obj_weights,
        raw_farmer_weights,
        weight_source,
        weight_warnings,
        income_weight_status,
        requested_income_weight,
    ) = _resolve_weights(
        candidate_output,
        field_profile,
        priority_weights,
        income_scorable=income_scorable,
    )
    forage_w = raw_farmer_weights.get("forage_value_weight")
    if priority_weights is not None and ("forage_value_weight" in priority_weights or "forage_value" in priority_weights):
        forage_flag = "PROVIDED" if forage_w is not None else "NOT_PROVIDED"
    else:
        forage_flag = pref_handling.get("optional_input_completeness", {}).get(
            "forage_value_weight",
            "PROVIDED" if forage_w is not None else "NOT_PROVIDED",
        )

    for strat in raw_strategies:
        sid = strat["strategy_id"]
        per_strategy_scores[sid]["forage_value"] = _eval_forage_value(strat, forage_w, forage_flag)
        # Re-order dict strictly to OBJECTIVE_ORDER
        per_strategy_scores[sid] = {obj: per_strategy_scores[sid][obj] for obj in OBJECTIVE_ORDER}

    feasible_pass_count = sum(1 for s in eligible_strats if s.get("feasibility_status") == "FEASIBLE_PASS")
    cond_count = sum(
        1 for s in eligible_strats if s.get("feasibility_status") == "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS"
    )
    all_conditional = len(eligible_strats) > 0 and feasible_pass_count == 0

    # 2. Identify active Pareto objectives and compute dominance front over eligible pool
    pareto_input = [{"strategy_id": s["strategy_id"], "scores": per_strategy_scores[s["strategy_id"]]} for s in eligible_strats]
    pareto_res = compute_pareto_front(pareto_input, OBJECTIVE_ORDER)
    active_pareto_objs: List[str] = pareto_res["active_pareto_objectives"]
    front_set = set(pareto_res["front_strategy_ids"])

    # 3. Determine active weighted objectives (scorable AND positive raw weight) + normalize weights strictly
    active_weighted_objs: List[str] = []
    inactive_weight_audit: Dict[str, Dict[str, Any]] = {}
    for obj in OBJECTIVE_ORDER:
        rw = raw_obj_weights.get(obj)
        if obj not in active_pareto_objs:
            reason = (
                "INCOME_POTENTIAL_UNAVAILABLE_WITHOUT_ECONOMIC_DATA"
                if (obj == "income_potential" and income_weight_status.startswith("IGNORED_"))
                else "OBJECTIVE_STATUS_UNKNOWN_OR_NOT_APPLICABLE"
            )
            audit_entry: Dict[str, Any] = {
                "raw_weight": (
                    requested_income_weight
                    if (obj == "income_potential" and requested_income_weight is not None)
                    else rw
                ),
                "reason": reason,
            }
            if obj == "income_potential" and income_weight_status != "NOT_REQUESTED":
                audit_entry["income_weight_status"] = income_weight_status
            inactive_weight_audit[obj] = audit_entry
        elif rw is None or float(rw) <= 0.0:
            inactive_weight_audit[obj] = {
                "raw_weight": rw,
                "reason": "ZERO_OR_NULL_FARMER_PRIORITY_WEIGHT",
            }
        else:
            active_weighted_objs.append(obj)

    active_weight_sum = sum(float(raw_obj_weights[o]) for o in active_weighted_objs)
    normalized_weights: Dict[str, float] = {
        o: (round(float(raw_obj_weights[o]) / active_weight_sum, 6) if (o in active_weighted_objs and active_weight_sum > 0.0) else 0.0)
        for o in OBJECTIVE_ORDER
    }

    # 4. Compute composite scores & rank eligible candidates deterministically
    ranked_rows: List[Dict[str, Any]] = []
    for strat in eligible_strats:
        sid = strat["strategy_id"]
        sc_map = per_strategy_scores[sid]
        if active_weighted_objs and active_weight_sum > 0.0:
            w_score = round(sum(normalized_weights[o] * float(sc_map[o]["score"]) for o in active_weighted_objs), 6)
        else:
            w_score = None
        pass_cnt = int(strat["constraint_evaluations"]["overall_status_counts"].get("PASS", 0))
        is_non_front = 0 if sid in front_set else 1
        ranked_rows.append(
            {
                "strategy_id": sid,
                "weighted_score": w_score,
                "is_non_front": is_non_front,
                "pass_cnt": pass_cnt,
            }
        )

    if active_weighted_objs and active_weight_sum > 0.0:
        ranked_rows.sort(
            key=lambda r: (
                -round(float(r["weighted_score"]), 9),
                r["is_non_front"],
                -r["pass_cnt"],
                r["strategy_id"],
            )
        )
        rank_lookup = {r["strategy_id"]: idx for idx, r in enumerate(ranked_rows, start=1)}
        wscore_lookup = {r["strategy_id"]: r["weighted_score"] for r in ranked_rows}
        ranked_ids = [r["strategy_id"] for r in ranked_rows]
    else:
        rank_lookup = {}
        wscore_lookup = {r["strategy_id"]: None for r in ranked_rows}
        ranked_ids = []

    # 5. Sensitivity analysis & explicit Decision Gating (Phase N hardened)
    gpm_ann = clim_summary.get("gpm_annual_precip_mm")
    power_ann = clim_summary.get("nasa_power_annual_precip_mm")
    precip_spread_mm = (
        round(abs(float(gpm_ann) - float(power_ann)), 2)
        if gpm_ann is not None and power_ann is not None
        else None
    )

    prelim_winner_id: Optional[str] = ranked_ids[0] if (eligible_strats and ranked_ids and active_weight_sum > 0.0) else None
    sens_eligible = [
        {
            "strategy_id": s["strategy_id"],
            "scores": per_strategy_scores[s["strategy_id"]],
            "constraint_evaluations": s["constraint_evaluations"],
        }
        for s in eligible_strats
    ]
    sensitivity_res = run_sensitivity_analysis(
        eligible_strategies=sens_eligible,
        baseline_weights_norm={o: normalized_weights[o] for o in active_weighted_objs},
        active_objectives=active_weighted_objs,
        pareto_front_ids=pareto_res["front_strategy_ids"],
        baseline_winner_id=prelim_winner_id,
        power_water_scores=power_water_scores,
        margin_thresholds=margin_thresholds,
        precip_spread_mm=precip_spread_mm,
    )

    critical_adequacy = assess_critical_data_adequacy(
        field_profile=field_profile,
        field_insights=field_insights,
        land_use_assessment=land_use,
        water_balance_assessment=water_balance_assessment,
        water_context=water_ctx,
        optional_flags=pref_handling.get("optional_input_completeness"),
        history_sufficient=history_assessment.get("sufficient_for_existing_baseline"),
        eligible_for_ranking_count=len(eligible_strats),
        income_potential_unavailable=not income_scorable,
    )
    adequacy_blocked = critical_adequacy["adequacy_status"] in BLOCKING_ADEQUACY_STATUSES

    provisional_lu = bool(land_use.get("is_provisional", False))
    gate_reasons: List[str] = []
    if not eligible_strats:
        suggested_id: Optional[str] = None
        rec_status = "NO_STRATEGY_RECOMMENDED_ALL_INFEASIBLE"
        decision_status = "INFEASIBLE" if raw_strategies else "NO_RECOMMENDATION"
        endorsed_id: Optional[str] = None
        gate_reasons.append("Zero strategies satisfied hard feasibility constraints.")
    elif not ranked_ids or active_weight_sum <= 0.0:
        suggested_id = None
        rec_status = "INSUFFICIENT_SCORABLE_EVIDENCE_NO_WINNER"
        decision_status = "NO_RECOMMENDATION"
        endorsed_id = None
        gate_reasons.append("No active scorable objectives available to form a composite ranking.")
    elif provisional_lu or adequacy_blocked:
        suggested_id = prelim_winner_id
        rec_status = "EXPLORATORY_ONLY"
        decision_status = "EXPLORATORY_ONLY"
        endorsed_id = None
        if provisional_lu:
            gate_reasons.append(land_use.get("provisional_gating_reason") or f"Provisional land-use gate: {land_use.get('status')}.")
        if adequacy_blocked:
            blocker_impacts = [
                g["impact"]
                for g in critical_adequacy.get("critical_gaps", [])
                if g.get("severity") in ("CRITICAL_BLOCKER", "NOT_ASSESSABLE")
            ]
            if blocker_impacts:
                gate_reasons.append(
                    f"Critical data adequacy='{critical_adequacy['adequacy_status']}': {'; '.join(blocker_impacts)}"
                )
            else:
                gate_reasons.append(
                    f"Critical data adequacy='{critical_adequacy['adequacy_status']}' blocks operational endorsement."
                )
    elif all_conditional or land_use.get("requires_local_verification"):
        suggested_id = prelim_winner_id
        rec_status = "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION"
        # Distinguish CONDITIONALLY_FEASIBLE (soft cautions only) vs REQUIRES_LOCAL_VERIFICATION (UNKNOWN/missing critical data)
        has_hard_or_critical_unknowns = bool(
            water_balance_assessment.get("fao56_water_balance_status") != "COMPUTED_FULL"
            or any(
                s["constraint_evaluations"].get("overall_status_counts", {}).get("UNKNOWN", 0) > 0
                for s in eligible_strats
            )
            or land_use.get("requires_local_verification")
        )
        decision_status = "REQUIRES_LOCAL_VERIFICATION" if has_hard_or_critical_unknowns else "CONDITIONALLY_FEASIBLE"
        endorsed_id = prelim_winner_id
        if has_hard_or_critical_unknowns:
            gate_reasons.append("Unresolved UNKNOWN constraints (e.g. DEM/drainage, ECe salinity, history, or land-use check) require local verification.")
        if sensitivity_res.get("near_tie_detected"):
            gate_reasons.append(
                f"Ranking near-tie/narrow margin ({sensitivity_res.get('margin_status')}: diff={sensitivity_res.get('baseline_top_two_margin')}); "
                "plausible alternatives should be considered jointly."
            )
    else:
        suggested_id = prelim_winner_id
        rec_status = "FEASIBLE_RECOMMENDATION"
        decision_status = "FEASIBLE_PASS"
        endorsed_id = prelim_winner_id

    decision_gate = {
        "decision_status": decision_status,
        "endorsed_recommendation_id": endorsed_id,
        "exploratory_candidate_id": prelim_winner_id if decision_status == "EXPLORATORY_ONLY" else None,
        "suggested_strategy_endorsed": bool(endorsed_id is not None),
        "provisional_only": bool(decision_status == "EXPLORATORY_ONLY"),
        "land_use_status": land_use.get("status"),
        "margin_status": sensitivity_res.get("margin_status"),
        "near_tie_detected": bool(sensitivity_res.get("near_tie_detected", False)),
        "plausible_alternatives": sensitivity_res.get("plausible_alternatives", []),
        "gating_reasons": gate_reasons,
    }

    # 7. Assemble final strategy objects conforming to Section 7 output contract
    strat_by_id = {s["strategy_id"]: s for s in raw_strategies}
    ordered_input_strats = [strat_by_id[sid] for sid in (ranked_ids if ranked_ids else [s["strategy_id"] for s in eligible_strats])] + infeasible_strats

    strategies_out: List[Dict[str, Any]] = []
    for strat in ordered_input_strats:
        sid = strat["strategy_id"]
        is_elig = bool(strat.get("feasible", False))
        sc_map = per_strategy_scores[sid]

        for obj in OBJECTIVE_ORDER:
            sc_map[obj]["active_in_ranking"] = obj in active_weighted_objs
            sc_map[obj]["normalized_weight"] = normalized_weights[obj]

        p_info = pareto_res["strategy_pareto_map"].get(
            sid,
            {"pareto_status": "EXCLUDED_INFEASIBLE", "dominated_by": [], "dominates": []},
        )
        if not is_elig:
            p_status = "EXCLUDED_INFEASIBLE"
            dom_by: List[str] = []
        else:
            p_status = p_info["pareto_status"]
            dom_by = p_info["dominated_by"]

        status_tally = {
            st: sum(1 for o in OBJECTIVE_ORDER if sc_map[o]["status"] == st)
            for st in ("SCORED", "PARTIAL", "UNKNOWN", "NOT_APPLICABLE")
        }
        applicable_objs = max(len(OBJECTIVE_ORDER) - status_tally["NOT_APPLICABLE"], 1)
        cov_ratio = round((status_tally["SCORED"] + 0.5 * status_tally["PARTIAL"]) / applicable_objs, 4)

        benefits, risks = _derive_benefits_and_risks(strat, sc_map)
        extra_gaps = sorted(
            {
                *strat.get("information_gaps", []),
                *(m for o in OBJECTIVE_ORDER for m in sc_map[o].get("missing_information", [])),
            }
        )
        extra_ev = sorted(
            {
                *strat.get("evidence", []),
                *(f"PHASE_I[{o}]: {e}" for o in OBJECTIVE_ORDER for e in sc_map[o].get("evidence", [])),
            }
        )

        if not is_elig:
            ce = strat["constraint_evaluations"]
            infeas_reasons = (
                ce.get("hard_fail_reasons", [])
                + ce.get("hard_unknown_reasons", [])
                + ce.get("soft_fail_reasons", [])
            )
            if not infeas_reasons:
                infeas_reasons = [r for r in strat.get("reasons", []) if "[FAIL]" in r or "[UNKNOWN]" in r][:3]
            expl = (
                f"EXCLUDED from recommendation pool due to Phase H feasibility verdict '{strat['feasibility_status']}': "
                f"{'; '.join(infeas_reasons)}."
            )
            conf_level = "INFEASIBLE_BLOCKED"
        else:
            rank_val = rank_lookup.get(sid)
            ws_val = wscore_lookup.get(sid)
            expl = (
                f"Ranked #{rank_val} with normalized weighted score {ws_val:.4f} ({p_status}) under "
                f"'{strat['feasibility_status']}'. "
                f"Top strengths: water={sc_map['water_efficiency'].get('score')}, "
                f"soil={sc_map['soil_improvement'].get('score')}, "
                f"pest_break={sc_map['pest_disease_disruption'].get('score')}; "
                f"unresolved constraints or data gaps keep needs_local_review={strat.get('needs_local_review', True)}."
                if rank_val is not None and ws_val is not None
                else f"Eligible strategy ({strat['feasibility_status']}) left unranked due to insufficient active scorable weighted objectives."
            )
            conf_level = "CONDITIONAL_MEDIUM_LOW" if strat.get("feasibility_status") != "FEASIBLE_PASS" else "MODERATE"

        reasons_list = list(strat.get("reasons", []))
        if not is_elig:
            reasons_list.insert(0, f"[PHASE_I_EXCLUDED] Excluded from Pareto & weighted ranking due to '{strat['feasibility_status']}'.")
        elif rank_lookup.get(sid) is not None:
            reasons_list.insert(0, f"[PHASE_I_RANK_{rank_lookup[sid]}] Weighted score={wscore_lookup[sid]:.4f}; Pareto={p_status}.")

        strategies_out.append(
            {
                "strategy_id": sid,
                "candidate_id": strat.get("candidate_id"),
                "pattern_id": strat.get("pattern_id"),
                "name": strat.get("name"),
                "is_existing_rotation": strat.get("is_existing_rotation", False),
                "selection_status": strat.get("selection_status"),
                "provisional": bool(decision_status == "EXPLORATORY_ONLY" or provisional_lu or adequacy_blocked or strat.get("provisional", False)),
                "land_use_status": land_use.get("status"),
                "feasibility_status": strat["feasibility_status"],
                "feasible": is_elig,
                "rank": rank_lookup.get(sid),
                "pareto_status": p_status,
                "dominated_by": dom_by,
                "weighted_score": wscore_lookup.get(sid),
                "seasons": strat.get("seasons", []),
                "scores": sc_map,
                "stability_metrics": sensitivity_res.get("per_strategy_stability", {}).get(sid),
                "confidence": {
                    "level": conf_level,
                    "score_coverage_ratio": cov_ratio,
                    "scored_objectives_count": status_tally["SCORED"],
                    "partial_objectives_count": status_tally["PARTIAL"],
                    "unknown_objectives_count": status_tally["UNKNOWN"],
                    "not_applicable_objectives_count": status_tally["NOT_APPLICABLE"],
                    "unresolved_constraints_summary": strat["constraint_evaluations"].get("overall_status_counts"),
                    "regional_caveats": strat.get("confidence_limitations", {}),
                },
                "explanation": expl,
                "reasons": reasons_list,
                "evidence": extra_ev,
                "benefits": benefits,
                "risks": risks,
                "assumptions": strat.get("assumptions", []),
                "information_gaps": extra_gaps,
                "needs_local_review": bool(strat.get("needs_local_review", True) or status_tally["UNKNOWN"] > 0 or status_tally["PARTIAL"] > 0),
                "review_checklist": strat.get("review_checklist", []),
            }
        )

    feas_notice = (
        "All eligible strategies carry unresolved WARNING or UNKNOWN constraints (zero clean FEASIBLE_PASS candidates); comparisons are conditional pending on-farm verification."
        if all_conditional
        else (
            "Zero eligible candidates passed Phase H hard feasibility gates; no strategy can be responsibly recommended."
            if not eligible_strats
            else "At least one candidate achieved clean FEASIBLE_PASS."
        )
    )

    return {
        "schema_version": "1.1.0",
        "phase": "PHASE_I_SCORING_AND_RANKING",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "field_id": candidate_output.get("field_id"),
        "field_name": candidate_output.get("field_name"),
        "suggested_strategy_id": suggested_id,
        "recommendation_status": rec_status,
        "decision_gate": decision_gate,
        "land_use_assessment": land_use,
        "water_balance_assessment": water_balance_assessment,
        "critical_data_adequacy": critical_adequacy,
        "all_candidates_conditional": all_conditional,
        "feasibility_gate_summary": {
            "total_input_candidates": len(raw_strategies),
            "eligible_for_ranking_count": len(eligible_strats),
            "feasible_pass_count": feasible_pass_count,
            "conditionally_feasible_count": cond_count,
            "excluded_infeasible_count": len(infeasible_strats),
            "notice": feas_notice,
        },
        "ranking_methodology": {
            "weight_source": weight_source,
            "raw_farmer_weights": raw_farmer_weights,
            "raw_objective_weights": raw_obj_weights,
            "requested_income_weight": requested_income_weight,
            "income_weight_status": income_weight_status,
            "weight_warnings": weight_warnings,
            "active_weighted_objectives": active_weighted_objs,
            "normalized_active_weights": normalized_weights,
            "normalized_active_weight_sum": round(sum(normalized_weights.values()), 6),
            "inactive_objectives_audit": inactive_weight_audit,
            "water_efficiency_scope": "ORDINAL_REGIME_SUITABILITY (not volumetric FAO-56 ETc/irrigation demand)",
            "tie_breaker": "(-weighted_score, is_non_pareto_front, -pass_rule_count, strategy_id)",
            "income_policy": "Qualitative market tier reported separately; numeric income_potential scored ONLY with verified local yield/price/cost data.",
            "forage_policy": "Null ('NOT_PROVIDED') and 0.0 keep forage_value inactive ('NOT_APPLICABLE'); never silently treated as favorable or penalized.",
        },
        "pareto_analysis": pareto_res,
        "sensitivity_analysis": sensitivity_res,
        "ranked_strategy_ids": ranked_ids,
        "excluded_infeasible_strategy_ids": [s["strategy_id"] for s in infeasible_strats],
        "strategies": strategies_out,
    }
