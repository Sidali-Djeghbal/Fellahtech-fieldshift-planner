"""Phase H: Deterministic, Constraint-Aware Crop Rotation Candidate Generator.

Consumes a validated Phase F Field Profile and Phase G Agronomic Knowledge Base
& Constraint Engine to generate diverse 2-4 season crop rotation candidates.

Strict boundaries:
- Zero ranking or multi-objective scoring (deferred to Phase I).
- Zero crop yield or financial predictions.
- Never invents missing crop_history or missing field observations.
- Never bypasses Phase G constraint rules or coerces UNKNOWN into PASS.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from src.agronomic.constraint_engine import (
    AgronomicKnowledgeBase,
    EVALUATION_STATUSES,
    evaluate_all_crops_for_field,
    evaluate_crop_sequence,
    load_knowledge_base,
)
from src.agronomic.land_use_assessment import LAND_USE_SUPPORTED, assess_land_use
from src.agronomic.temporal_planning import (
    assess_crop_history_completeness,
    season_window_bounds,
    validate_and_build_planning_timeline,
)

CROP_VALID_PLANTING_MONTHS: Dict[str, Tuple[int, ...]] = {
    "DURUM_WHEAT": (10, 11, 12),
    "SOFT_WHEAT": (10, 11, 12),
    "BARLEY": (10, 11, 12),
    "FABA_BEAN": (10, 11),
    "CHICKPEA_WINTER": (11, 12),
    "CHICKPEA_SPRING": (2, 3),
    "LENTIL": (11, 12, 1, 2),
    "VETCH_OAT": (11, 12),
    "TOMATO_IND": (3, 4),
    "POTATO": (1, 2, 8, 9),
    "SUNFLOWER": (3, 4),
    "OLIVE": (),
    "BARE_FALLOW": (10, 11, 12, 1, 2, 3, 4, 5),
}

CROP_ROLES: Dict[str, str] = {
    "DURUM_WHEAT": "Primary regional staple & residue-producing cereal",
    "SOFT_WHEAT": "Secondary winter cereal staple",
    "BARLEY": "Drought-resilient semi-arid cereal & straw resource",
    "FABA_BEAN": "Premier nitrogen-fixing broadleaf cereal break crop",
    "CHICKPEA_WINTER": "Winter moisture-capture legume break crop",
    "CHICKPEA_SPRING": "Spring-sown legume break after wet winter blocks autumn sowing",
    "LENTIL": "Drought-adapted pulse break suited to well-drained lighter soils",
    "VETCH_OAT": "Dual-purpose forage mix & proven Algerian fallow replacement",
    "TOMATO_IND": "Irrigation-gated high-value cash break crop",
    "POTATO": "Irrigation-gated tuber crop (requires loose soil & pH/scab vigilance)",
    "SUNFLOWER": "Candidate spring/summer deep-root oilseed diversification",
    "OLIVE": "Permanent perennial orchard crop (excluded from annual rotation)",
    "BARE_FALLOW": "Uncropped moisture-storage & weed-control baseline counterfactual",
}


@dataclass(frozen=True)
class GenerationConfig:
    """Configurable deterministic bounds for candidate generation."""

    max_candidates: int = 8
    min_history_entries_for_baseline: int = 2
    include_infeasible_existing_baseline: bool = True
    include_infeasible_requested_targets: bool = True


def _canonical_season_for_crop(crop: Dict[str, Any]) -> str:
    allowed = crop["parameters"]["suitable_planting_seasons"]["value"] or []
    for s in ("Winter", "Autumn", "Spring", "Summer"):
        if s in allowed:
            return s
    return "Winter"


def _resolve_planting_month(crop_id: str, slot_idx: int, slot_season: str, requested_pm: Optional[int]) -> Optional[int]:
    if slot_idx != 0 or requested_pm is None:
        return None
    valid_months = CROP_VALID_PLANTING_MONTHS.get(crop_id, ())
    if requested_pm in valid_months:
        # Ensure month aligns roughly with season if Spring vs Winter
        if slot_season == "Spring" and requested_pm not in (1, 2, 3, 4, 5):
            return None
        if slot_season in {"Winter", "Autumn"} and requested_pm not in (8, 9, 10, 11, 12, 1):
            return None
        return int(requested_pm)
    return None


def _build_field_insights(field_profile: Dict[str, Any]) -> Dict[str, Any]:
    sv = field_profile["section_b_extracted_geospatial"]["spatial_validation"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    sec_d = field_profile["section_d_quality_and_uncertainty"]

    soil = ds["soilgrids_v6"]
    gpm = ds["gpm_and_smap"]
    npw = ds["nasa_power"]
    s2 = ds["sentinel2"]
    cf = ds["crop_frequency"]
    modis = ds["modis"]
    dem = ds["terrain_dem"]

    return {
        "area_ha": sv["area_ha"],
        "wilaya_overlap_pct": sv["wilaya_overlap_pct"],
        "primary_commune": sv["primary_commune"],
        "validation_warnings": sv["validation_warnings"],
        "soil_summary_modeled_250m": {
            "usda_texture_0_5cm": soil.get("usda_texture_0_5cm", {}).get("value"),
            "clay_0_30cm_pct": soil.get("clay_0_30cm", {}).get("value"),
            "clay_0_30cm_coverage_pct": soil.get("clay_0_30cm", {}).get("polygon_coverage_pct"),
            "clay_0_30cm_quality_status": soil.get("clay_0_30cm", {}).get("quality_status"),
            "ph_0_30cm": soil.get("ph_0_30cm", {}).get("value"),
            "soc_0_30cm_g_kg": soil.get("soc_0_30cm", {}).get("value"),
            "cec_0_30cm_cmol_kg": soil.get("cec_0_30cm", {}).get("value"),
            "nitrogen_0_30cm_status": soil.get("nitrogen_0_30cm", {}).get("quality_status"),
            "caveat": sec_d["soilgrids_vs_laboratory_distinction"],
        },
        "climate_water_summary": {
            "gpm_annual_precip_mm": gpm.get("gpm_annual_precip_2016_2025_mean_mm", {}).get("value"),
            "nasa_power_annual_precip_mm": npw.get("nasa_power_annual_precip_2016_2025_mean_mm", {}).get("value"),
            "nasa_power_mean_temp_c": npw.get("nasa_power_t2m_2016_2025_mean_c", {}).get("value"),
            "smap_spring_rootzone_sm": gpm.get("smap_rootzone_sm_spring_2016_2025_mean", {}).get("value"),
            "caveat": sec_d["regional_climate_vs_field_distinction"],
        },
        "vegetation_and_terrain_summary": {
            "crop_frequency_2021_2025": cf.get("crop_frequency_2021_2025", {}).get("value"),
            "s2_2024_03_ndvi_10m": s2.get("s2_2024_03_ndvi_10m", {}).get("value"),
            "s2_wilaya_spring_ndvi_fallback": s2.get("s2_wilaya_spring_ndvi_climatology_2017_2025", {}).get("value"),
            "modis_spring_ndvi_250m": modis.get("modis_ndvi_spring_2016_2025_mean", {}).get("value"),
            "dem_slope_pct": dem.get("dem_slope_pct", {}).get("value"),
            "dem_quality_status": dem.get("dem_slope_pct", {}).get("quality_status"),
        },
    }


def _assess_crop_history(field_profile: Dict[str, Any], min_entries: int) -> Dict[str, Any]:
    sec_a = field_profile["section_a_farmer_provided"]
    flags = sec_a["input_completeness_flags"]
    hist_status = flags.get("crop_history", "NOT_PROVIDED")
    hist = sec_a.get("crop_history")
    start_season = sec_a["planning"]["start_season"]
    start_year = sec_a["planning"]["start_year"]

    summary = assess_crop_history_completeness(
        hist,
        start_season,
        start_year,
        min_entries_for_complete=min_entries,
    )
    if hist is None:
        return {
            "completeness_flag": hist_status,
            "raw_entries_count": 0,
            "resolved_entries_count": 0,
            "sufficient_for_existing_baseline": False,
            "resolved_chronological_sequence": [],
            "most_recent_predecessor": None,
            "predecessor_period": None,
            "limitation_note": "crop_history is null ('NOT_PROVIDED'); cannot verify predecessor break safety or construct an existing rotation baseline.",
        }

    recent = summary["recent_resolved_entries"]
    resolved_all = [h for h in summary["ordered_entries"] if h.get("crop_id_resolved") is not None]
    last_pre = summary["most_recent_predecessor"]
    pred_rec = summary["predecessor_record"]
    sufficient = summary["sufficient_for_existing_baseline"]
    if sufficient and pred_rec is not None:
        note = f"Resolved {len(recent)} recent crop_history season(s) ending cleanly at {pred_rec['season']} {pred_rec['year']} ({last_pre})."
    else:
        pred_desc = f"{pred_rec['season']} {pred_rec['year']}={last_pre}" if pred_rec else f"none resolved immediately before {start_season} {start_year}"
        note = (
            f"Insufficient verified history ({len(recent)} recent resolved entries, immediate predecessor={pred_desc}): "
            f"existing-rotation baseline withheld; no missing history invented."
        )
    return {
        "completeness_flag": hist_status,
        "raw_entries_count": len(hist),
        "resolved_entries_count": len(resolved_all),
        "sufficient_for_existing_baseline": sufficient,
        "resolved_chronological_sequence": [{"year": h["year"], "season": h["season"], "crop_id": h["crop_id_resolved"]} for h in recent],
        "most_recent_predecessor": last_pre,
        "predecessor_period": f"{pred_rec['season']} {pred_rec['year']}" if pred_rec else None,
        "limitation_note": note,
    }


def _slot_calendar_sequence(
    crops: Sequence[str],
    start_season: str,
    start_year: int,
    kb: AgronomicKnowledgeBase,
) -> Tuple[List[str], List[int]]:
    """Assign chronologically ordered, biologically valid planting season and calendar year per planned step."""
    seasons: List[str] = []
    years: List[int] = []
    prev_end: Optional[date] = None
    for idx, cid in enumerate(crops):
        crop = kb.crops[cid]
        allowed = crop["parameters"]["suitable_planting_seasons"]["value"] or []
        if idx == 0:
            season_choice = start_season
            yr = start_year
        else:
            season_choice = start_season if start_season in allowed else _canonical_season_for_crop(crop)
            yr = years[-1]
            while True:
                s_start, s_end = season_window_bounds(season_choice, yr)
                # Advance until the new planting window begins strictly after the previous slot's main sowing window
                if prev_end is None or s_start > prev_end:
                    break
                yr += 1
        _, w_end = season_window_bounds(season_choice, yr)
        prev_end = w_end
        seasons.append(season_choice)
        years.append(yr)
    return seasons, years


def _choose_first_eligible(
    options: Sequence[str],
    season: str,
    excluded: set,
    prev_crop: Optional[str],
    slot_eval_cache: Dict[Tuple[str, str], Dict[str, Any]],
    avoid_same_group: Optional[set] = None,
) -> Optional[str]:
    for cid in options:
        if cid in excluded:
            continue
        if prev_crop is not None and cid == prev_crop:
            continue
        if avoid_same_group and cid in avoid_same_group and prev_crop in avoid_same_group:
            continue
        ev = slot_eval_cache[(cid, season)]
        if season in (ev["rule_evaluations"][1]["observed_inputs"].get("suitable_planting_seasons") or []):
            return cid
    return None


def _construct_pattern_sequences(
    field_profile: Dict[str, Any],
    history_info: Dict[str, Any],
    kb: AgronomicKnowledgeBase,
    slot_eval_cache: Dict[Tuple[str, str], Dict[str, Any]],
    cfg: GenerationConfig,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Deterministically synthesize pattern-diverse candidate sequence blueprints."""
    sec_a = field_profile["section_a_farmer_provided"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    horizon = int(sec_a["planning"]["horizon_seasons"])
    start_season = sec_a["planning"]["start_season"]
    pref = sec_a.get("preferences") or {}
    excluded = set(pref.get("excluded_crop_ids") or [])
    targets = list(pref.get("target_crop_ids") or [])
    water = sec_a["water"]
    clay = ds["soilgrids_v6"].get("clay_0_30cm", {}).get("value")
    gpm_mm = ds["gpm_and_smap"].get("gpm_annual_precip_2016_2025_mean_mm", {}).get("value")
    prev_crop = history_info["most_recent_predecessor"]

    cereals = set(kb.group_membership["CEREALS"])
    pulses = set(kb.group_membership["FOOD_LEGUMES"])

    # Helper to build horizon sequence respecting T-1 boundary & no consecutive repeat traps
    def _build_cycle(primary_cereal: str, break_pool: Sequence[str], start_with_break: bool) -> List[str]:
        seq: List[str] = []
        last = prev_crop
        break_used: List[str] = [x for x in (prev_crop,) if x in pulses]
        for idx in range(horizon):
            s_target = start_season if idx == 0 else None
            use_cereal = (idx % 2 == 0) if not start_with_break else (idx % 2 == 1)
            # If last crop was already a cereal on slot 0, force break first when possible
            if idx == 0 and last in cereals and not start_with_break:
                use_cereal = False
            if use_cereal:
                cand_opts = [c for c in (primary_cereal, "DURUM_WHEAT", "BARLEY", "SOFT_WHEAT") if c not in excluded]
                chosen = _choose_first_eligible(cand_opts, s_target or "Winter", excluded, last, slot_eval_cache, avoid_same_group=cereals)
                if chosen is None:
                    chosen = _choose_first_eligible(cand_opts, s_target or "Winter", excluded, None, slot_eval_cache)
            else:
                fresh_breaks = [b for b in break_pool if b not in excluded and b not in break_used and not ({b, *break_used} >= {"FABA_BEAN", "LENTIL"})]
                if not fresh_breaks:
                    fresh_breaks = [b for b in break_pool if b not in excluded and b != last]
                # Try matching start_season first if slot 0
                eff_s = s_target or _canonical_season_for_crop(kb.crops[fresh_breaks[0]]) if fresh_breaks else "Winter"
                chosen = _choose_first_eligible(fresh_breaks, eff_s, excluded, last, slot_eval_cache, avoid_same_group=pulses if idx > 0 else None)
                if chosen is None and s_target is not None:
                    # Fallback within target season
                    any_s = [b for b in break_pool if b not in excluded and s_target in (kb.crops[b]["parameters"]["suitable_planting_seasons"]["value"] or [])]
                    if any_s:
                        chosen = any_s[0]
                if chosen in pulses:
                    break_used.append(chosen)
            if chosen is None:
                chosen = "BARE_FALLOW" if "BARE_FALLOW" not in excluded and last != "BARE_FALLOW" else ("DURUM_WHEAT" if "DURUM_WHEAT" not in excluded else "BARLEY")
            seq.append(chosen)
            last = chosen
        return seq

    blueprints: List[Dict[str, Any]] = []

    # 1. Cereal-Legume Break Rotation
    pref_cereal = "BARLEY" if (gpm_mm is not None and gpm_mm < 460.0 and "BARLEY" not in excluded) else "DURUM_WHEAT"
    legume_pool = ["CHICKPEA_SPRING", "LENTIL", "FABA_BEAN", "CHICKPEA_WINTER"] if start_season == "Spring" else ["FABA_BEAN", "CHICKPEA_WINTER", "LENTIL", "CHICKPEA_SPRING"]
    if clay is not None and clay >= 35.0:
        legume_pool = ["FABA_BEAN", "CHICKPEA_WINTER", "CHICKPEA_SPRING", "VETCH_OAT"]
    seq_cl = _build_cycle(pref_cereal, legume_pool, start_with_break=(prev_crop in cereals or start_season == "Spring"))
    blueprints.append({
        "pattern_id": "CEREAL_LEGUME",
        "strategy_id": "STRAT_CEREAL_LEGUME",
        "name": "Cereal–Legume Break Rotation",
        "description": "Alternates regional winter cereals with nitrogen-fixing food legumes while maintaining >=3-year pulse/broomrape intervals.",
        "is_existing_rotation": False,
        "selection_status": "SELECTED_CANDIDATE_ELIGIBLE",
        "rationale": "Breaks cereal take-all/Fusarium/wild oat cycles and improves soil nitrogen availability per Phase E CON_12.",
        "sequence": seq_cl,
    })

    # 2. Cereal-Forage Rotation
    forage_pool = ["VETCH_OAT", "FABA_BEAN", "CHICKPEA_WINTER"]
    seq_cf = _build_cycle("DURUM_WHEAT" if "DURUM_WHEAT" not in excluded else "BARLEY", forage_pool, start_with_break=(prev_crop in cereals))
    if "VETCH_OAT" not in seq_cf and "VETCH_OAT" not in excluded and start_season in ("Winter", "Autumn"):
        idx_rep = 0 if len(seq_cf) >= 2 and prev_crop in cereals else 1
        seq_cf[idx_rep] = "VETCH_OAT"
    blueprints.append({
        "pattern_id": "CEREAL_FORAGE",
        "strategy_id": "STRAT_CEREAL_FORAGE",
        "name": "Cereal–Forage (Vetch–Oat) Fallow Replacement",
        "description": "Pairs winter grain cereals with Algerian Vetch–Oat forage hay mix cut prior to weed seed shed.",
        "is_existing_rotation": False,
        "selection_status": "SELECTED_CANDIDATE_ELIGIBLE",
        "rationale": "Replaces unproductive bare fallow with high-residue livestock forage and wild-oat suppression.",
        "sequence": seq_cf,
    })

    # 3. Soil-Improvement Rotation (prioritizes high-biomass legume/forage + single cereal cycle)
    soil_pool = ["FABA_BEAN", "VETCH_OAT", "CHICKPEA_WINTER"]
    seq_soil = _build_cycle("BARLEY" if gpm_mm and gpm_mm < 460 else "DURUM_WHEAT", soil_pool, start_with_break=True)
    # Ensure distinct variant starting with FABA_BEAN or VETCH_OAT if seq_cl also started with break
    if tuple(seq_soil) == tuple(seq_cl) and "VETCH_OAT" not in excluded and horizon >= 2:
        seq_soil = [("VETCH_OAT" if seq_cl[0] != "VETCH_OAT" else "FABA_BEAN") if i == 0 else seq_cl[i] for i in range(horizon)]
    blueprints.append({
        "pattern_id": "SOIL_IMPROVEMENT",
        "strategy_id": "STRAT_SOIL_IMPROVEMENT",
        "name": "Soil Organic Carbon & Structure Restoration Rotation",
        "description": "Prioritizes legume & forage organic residue return without soil-oxidizing bare fallow or heavy tuber tillage.",
        "is_existing_rotation": False,
        "selection_status": "SELECTED_CANDIDATE_ELIGIBLE",
        "rationale": "Directly addresses depleted topsoil SOC (<18 g/kg) and clay structural workability noted in CON_01/CON_03.",
        "sequence": seq_soil,
    })

    # 4. Water-Conscious Rotation
    wc_pool = ["CHICKPEA_SPRING", "LENTIL", "VETCH_OAT", "CHICKPEA_WINTER"] if start_season == "Spring" else ["CHICKPEA_WINTER", "VETCH_OAT", "LENTIL", "CHICKPEA_SPRING"]
    seq_wc = _build_cycle("BARLEY" if "BARLEY" not in excluded else "DURUM_WHEAT", wc_pool, start_with_break=(prev_crop in cereals or start_season == "Spring"))
    if "BARLEY" not in seq_wc and "BARLEY" not in excluded:
        for idx in range(horizon):
            if idx == 0 and start_season not in ("Winter", "Autumn"):
                continue
            if seq_wc[idx] in cereals:
                seq_wc[idx] = "BARLEY"
                break
    blueprints.append({
        "pattern_id": "WATER_CONSCIOUS",
        "strategy_id": "STRAT_WATER_CONSCIOUS",
        "name": "Water-Conscious Semi-Arid Resilience Rotation",
        "description": "Emphasizes drought-escaping Barley, Chickpea, Lentil, and early-cut Vetch–Oat avoiding high-ET summer cash crops.",
        "is_existing_rotation": False,
        "selection_status": "SELECTED_CANDIDATE_ELIGIBLE",
        "rationale": "Buffers coarse rainfall volatility (CON_06 GPM vs POWER spread) and Spring drought sensitivity.",
        "sequence": seq_wc,
    })

    # 5. Irrigation-Gated Cash Rotation (if irrigated OR farmer explicitly targets TOMATO_IND / POTATO)
    irrig_eligible = (
        water.get("source") not in {"rainfed", "unknown", None}
        and water.get("irrigation_system") not in {"none", "unknown", None}
    )
    if (irrig_eligible or "TOMATO_IND" in targets) and "TOMATO_IND" not in excluded:
        cereal_cash = "DURUM_WHEAT" if "DURUM_WHEAT" not in excluded else "BARLEY"
        leg_cash = "FABA_BEAN" if "FABA_BEAN" not in excluded else "VETCH_OAT"
        seq_ir: List[str] = []
        if start_season == "Spring":
            pattern_ir = ["TOMATO_IND", cereal_cash, leg_cash, "CHICKPEA_WINTER"]
        elif prev_crop in cereals:
            pattern_ir = [leg_cash, "TOMATO_IND", cereal_cash, "CHICKPEA_WINTER"]
        else:
            pattern_ir = [cereal_cash, "TOMATO_IND", leg_cash, cereal_cash]
        seq_ir = [c if c not in excluded else "BARE_FALLOW" for c in pattern_ir[:horizon]]
        blueprints.append({
            "pattern_id": "IRRIGATED_CASH_BREAK",
            "strategy_id": "STRAT_IRRIGATED_CASH",
            "name": "Irrigation-Gated Cash Crop & Cereal–Legume Rotation",
            "description": "Incorporates Processing Tomato in Spring irrigated campaign separated by >=3 years Solanaceae break.",
            "is_existing_rotation": False,
            "selection_status": "SELECTED_CANDIDATE_ELIGIBLE" if irrig_eligible and water.get("availability") != "unknown" else "SELECTED_INFEASIBLE_COUNTERFACTUAL",
            "rationale": "Evaluates Guelma–Bouchegouf high-value irrigated break subject strictly to Phase G water & salinity gates.",
            "sequence": seq_ir,
        })

    # 6. Target Crop Integration / Rejection Accounting
    target_report: Dict[str, Any] = {"requested_targets": targets, "included_targets": [], "not_included_reasons": {}}
    existing_crops_set = {c for bp in blueprints for c in bp["sequence"]}
    for tcid in targets:
        if tcid not in kb.crops:
            target_report["not_included_reasons"][tcid] = "Unknown crop_id not present in Phase E/G inventory."
            continue
        if tcid in excluded:
            target_report["not_included_reasons"][tcid] = "Explicitly listed in farmer's excluded_crop_ids (exclusion takes precedence)."
            continue
        if not kb.crops[tcid]["in_annual_rotation_scope"]:
            target_report["not_included_reasons"][tcid] = "Perennial tree crop (OLIVE) excluded from annual rotation scope (RULE_PERENNIAL_EXCLUSION)."
            if cfg.include_infeasible_requested_targets:
                blueprints.append({
                    "pattern_id": f"REQUESTED_TARGET_{tcid}",
                    "strategy_id": f"STRAT_REQUESTED_{tcid}",
                    "name": f"Farmer-Requested Counterfactual ({kb.crops[tcid]['canonical_name']})",
                    "description": "Explicit evaluation of requested target crop confirming why Phase G hard constraints exclude it.",
                    "is_existing_rotation": False,
                    "selection_status": "SELECTED_INFEASIBLE_COUNTERFACTUAL",
                    "rationale": f"Evaluated per Phase H Section 6 rule so farmer-requested crop '{tcid}' is never silently dropped.",
                    "sequence": [tcid] + (["DURUM_WHEAT"] if horizon == 2 else ["DURUM_WHEAT", "FABA_BEAN", "BARLEY"][: horizon - 1]),
                })
            continue
        if tcid in existing_crops_set:
            target_report["included_targets"].append(tcid)
            continue

        # Construct a valid sequence placing target tcid in the earliest season-compatible slot
        t_seasons = kb.crops[tcid]["parameters"]["suitable_planting_seasons"]["value"] or []
        seq_t = list(seq_cl)
        placed = False
        for idx in range(horizon):
            if idx == 0 and start_season not in t_seasons:
                continue
            if idx == 0 or (tcid not in kb.group_membership["SOLANACEAE"] or prev_crop != tcid):
                seq_t[idx] = tcid
                placed = True
                break
        if not placed and horizon >= 2:
            seq_t[1] = tcid
            placed = True

        if placed:
            blueprints.append({
                "pattern_id": f"FARMER_TARGET_{tcid}",
                "strategy_id": f"STRAT_TARGET_{tcid}",
                "name": f"Target-Crop Diversification ({kb.crops[tcid]['canonical_name']})",
                "description": f"Integrates farmer-requested {kb.crops[tcid]['canonical_name']} into a compatible cereal/legume rotation.",
                "is_existing_rotation": False,
                "selection_status": "SELECTED_CANDIDATE_ELIGIBLE",
                "rationale": f"Includes farmer-requested target '{tcid}' without bypassing Phase G hard/soft constraints.",
                "sequence": seq_t,
            })
            existing_crops_set.add(tcid)
            target_report["included_targets"].append(tcid)

    # 7. Existing Rotation Baseline ONLY when >= min_history_entries_for_baseline resolved entries exist
    if history_info["sufficient_for_existing_baseline"]:
        hist_seq = [h["crop_id"] for h in history_info["resolved_chronological_sequence"]]
        tail = hist_seq[-min(len(hist_seq), 3):]
        # Repeat observed historical pattern forward deterministically over horizon
        seq_ex = [tail[i % len(tail)] for i in range(horizon)]
        # Respect start_season strictly on slot 0 only if compatible, else run actual counterfactual cycle
        if not excluded & set(seq_ex):
            blueprints.append({
                "pattern_id": "EXISTING_ROTATION_BASELINE",
                "strategy_id": "STRAT_EXISTING_BASELINE",
                "name": "Existing Historical Rotation Baseline",
                "description": f"Projects the farmer's observed {len(tail)}-crop historical cadence forward over {horizon} seasons.",
                "is_existing_rotation": True,
                "selection_status": "EXISTING_BASELINE_EVALUATED",
                "rationale": "Evaluated directly from resolved multi-year crop_history without inventing missing years.",
                "sequence": seq_ex,
            })

    # Deduplicate exact crop sequences while preserving first pattern ownership, respecting max_candidates
    deduped: List[Dict[str, Any]] = []
    seen_seqs: set = set()
    skipped_duplicates: List[Dict[str, Any]] = []
    for bp in blueprints:
        key = tuple(bp["sequence"])
        if key in seen_seqs:
            skipped_duplicates.append({"strategy_id": bp["strategy_id"], "sequence": bp["sequence"]})
            continue
        # Double-check exclusions for eligible patterns
        if bp["selection_status"] == "SELECTED_CANDIDATE_ELIGIBLE" and (set(bp["sequence"]) & excluded):
            continue
        seen_seqs.add(key)
        deduped.append(bp)
        if len(deduped) >= cfg.max_candidates:
            break

    # Final check on targets actually represented as eligible candidates (excluding counterfactuals already flagged)
    represented_eligible = {
        c
        for bp in deduped
        if bp["selection_status"] == "SELECTED_CANDIDATE_ELIGIBLE"
        for c in bp["sequence"]
    }
    for tcid in targets:
        if (
            tcid in kb.crops
            and tcid in represented_eligible
            and tcid not in target_report["included_targets"]
            and tcid not in target_report["not_included_reasons"]
        ):
            target_report["included_targets"].append(tcid)

    return deduped, {
        "target_report": target_report,
        "skipped_duplicate_sequences": skipped_duplicates,
    }


def generate_rotation_candidates(
    field_profile: Dict[str, Any],
    config: Optional[GenerationConfig] = None,
    kb: Optional[AgronomicKnowledgeBase] = None,
    *,
    reference_date: Optional[Union[date, datetime, str]] = None,
    clock: Optional[Callable[[], date]] = None,
) -> Dict[str, Any]:
    """Generate and deterministically evaluate diverse crop rotation candidates for one Field Profile."""
    cfg = config or GenerationConfig()
    kb = kb or load_knowledge_base()

    sec_a = field_profile["section_a_farmer_provided"]
    sec_c = field_profile.get("section_c_agronomic_knowledge_base") or {}
    sec_d = field_profile["section_d_quality_and_uncertainty"]
    fld = sec_a["field"]
    planning = sec_a["planning"]
    start_season = planning["start_season"]
    start_year = int(planning["start_year"])
    horizon = int(planning["horizon_seasons"])
    req_pm = planning.get("planting_month")
    flags = sec_a["input_completeness_flags"]
    pref = sec_a.get("preferences") or {}

    if horizon < 2 or horizon > 4:
        raise ValueError("planning.horizon_seasons must be between 2 and 4.")

    # Enforce centralized temporal validation unless profile was constructed explicitly via injected clock
    if planning.get("temporal_validation") is not None and reference_date is None and clock is None:
        temporal_info = planning["temporal_validation"]
    else:
        temporal_info = validate_and_build_planning_timeline(
            planning,
            crop_history=sec_a.get("crop_history"),
            reference_date=reference_date,
            clock=clock,
        )

    land_use = sec_c.get("land_use_assessment") or assess_land_use(field_profile)

    # Cache single-crop slot evaluations across key seasons using Phase G directly
    slot_eval_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for s in {start_season, "Winter", "Spring", "Autumn"}:
        evals_s = evaluate_all_crops_for_field(field_profile, target_season=s, kb=kb)
        for cid, res in evals_s.items():
            slot_eval_cache[(cid, s)] = res

    history_info = _assess_crop_history(field_profile, cfg.min_history_entries_for_baseline)
    blueprints, meta_gen = _construct_pattern_sequences(field_profile, history_info, kb, slot_eval_cache, cfg)

    strategies: List[Dict[str, Any]] = []
    feasible_pass = 0
    cond_feasible = 0
    infeasible = 0

    for idx, bp in enumerate(blueprints, start=1):
        seq_crops = bp["sequence"]
        slot_seasons, slot_years = _slot_calendar_sequence(seq_crops, start_season, start_year, kb)
        seq_eval = evaluate_crop_sequence(field_profile, seq_crops, slot_seasons=slot_seasons, kb=kb)

        if not cfg.include_infeasible_existing_baseline and bp["is_existing_rotation"] and not seq_eval["feasible"]:
            continue

        fstatus = seq_eval["feasibility_status"]
        if fstatus == "FEASIBLE_PASS":
            feasible_pass += 1
        elif fstatus == "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS":
            cond_feasible += 1
        else:
            infeasible += 1

        # Build detailed per-season objects
        seasons_out: List[Dict[str, Any]] = []
        for s_idx, cid in enumerate(seq_crops):
            slot_ev = seq_eval["slot_evaluations"][s_idx]
            crop_meta = kb.crops[cid]
            pm_resolved = _resolve_planting_month(cid, s_idx, slot_seasons[s_idx], req_pm)
            pm_note = ""
            if s_idx == 0 and req_pm is not None and pm_resolved is None:
                pm_note = f" Requested planting_month={req_pm} omitted because crop window is '{crop_meta['parameters']['planting_window']['value']}'."

            seasons_out.append({
                "season_order": s_idx + 1,
                "calendar_year": slot_years[s_idx],
                "agricultural_season": slot_seasons[s_idx],
                "planting_month": pm_resolved,
                "crop_id": cid,
                "canonical_name": crop_meta["canonical_name"],
                "crop_category": crop_meta["crop_category"],
                "agronomic_role": CROP_ROLES.get(cid, crop_meta["crop_category"]),
                "selection_status": slot_ev["feasibility_status"],
                "supporting_notes": (
                    f"Planting window: {crop_meta['parameters']['planting_window']['value']}; "
                    f"Harvest: {crop_meta['parameters']['harvest_window']['value']}; "
                    f"Slot rule counts: {slot_ev['status_counts']}.{pm_note}"
                ),
                "slot_constraint_evaluations": slot_ev["rule_evaluations"],
            })

        # Aggregate traceability lists without collapsing UNKNOWN into PASS
        all_rules = list(seq_eval["sequence_rule_evaluations"])
        for se in seq_eval["slot_evaluations"]:
            all_rules.extend(se["rule_evaluations"])

        combined_counts = {st: sum(1 for r in all_rules if r["status"] == st) for st in EVALUATION_STATUSES}
        status_rank = {"FAIL": 0, "UNKNOWN": 1, "WARNING": 2, "PASS": 3}
        reasons = sorted(
            {f"[{r['status']}] {r['rule_id']}: {r['reason']}" for r in all_rules if r["status"] in ("FAIL", "WARNING", "PASS")},
            key=lambda s: (status_rank.get(s.split("]", 1)[0].lstrip("["), 9), s),
        )
        evidence = sorted({f"{r['rule_id']} ({r['evidence_classification']}): {r['source']}" for r in all_rules})
        assumptions = sorted({f"{r['rule_id']}: {r['uncertainty_note']}" for r in all_rules if r["evidence_classification"] == "EXPERT_ASSUMPTION"})
        info_gaps = sorted({f"[UNKNOWN] {r['rule_id']}: {r['reason']}" for r in all_rules if r["status"] == "UNKNOWN"})

        checklist: List[str] = []
        if land_use["is_provisional"]:
            checklist.insert(0, f"EXPLORATORY / LAND-USE BLOCKER: {land_use.get('provisional_gating_reason')}")
        elif land_use["status"] != LAND_USE_SUPPORTED:
            checklist.append(f"LAND-USE VERIFICATION: {land_use.get('provisional_gating_reason')}")
        if combined_counts["UNKNOWN"] > 0:
            checklist.append("Resolve UNKNOWN constraints (DEM/drainage puddling check, irrigation salinity ECe, missing history or optional inputs).")
        if combined_counts["WARNING"] > 0:
            checklist.append("Review WARNING flags (GPM vs NASA POWER precipitation spread, clay workability, sequence return breaks, Hypothesis DSA trial status).")
        if not seq_eval["feasible"]:
            checklist.append("HARD/UNKNOWN/CONSTRAINT BLOCKER: Sequence infeasible as configured; inspect hard_fail_reasons / hard_unknown_reasons / soft_fail_reasons.")

        strategies.append({
            "candidate_id": f"CAND_{len(strategies) + 1:02d}",
            "strategy_id": bp["strategy_id"],
            "pattern_id": bp["pattern_id"],
            "name": bp["name"],
            "description": bp["description"],
            "is_existing_rotation": bp["is_existing_rotation"],
            "selection_status": bp["selection_status"],
            "provisional": bool(land_use["is_provisional"]),
            "land_use_status": land_use["status"],
            "provisional_reasons": (
                [land_use["provisional_gating_reason"]]
                if land_use["is_provisional"] and land_use.get("provisional_gating_reason")
                else []
            ),
            "generation_rationale": bp["rationale"],
            "feasibility_status": fstatus,
            "feasible": seq_eval["feasible"],
            "seasons": seasons_out,
            "constraint_evaluations": {
                "overall_status_counts": combined_counts,
                "sequence_status_counts": seq_eval["sequence_status_counts"],
                "hard_fail_reasons": seq_eval["hard_fail_reasons"],
                "hard_unknown_reasons": seq_eval["hard_unknown_reasons"],
                "soft_fail_reasons": seq_eval.get("soft_fail_reasons", []),
                "sequence_rules": seq_eval["sequence_rule_evaluations"],
            },
            "confidence_limitations": {
                "soilgrids_limitation": sec_d["soilgrids_vs_laboratory_distinction"],
                "climate_limitation": sec_d["regional_climate_vs_field_distinction"],
                "missing_values_policy": sec_d["missing_values_policy"],
            },
            "reasons": reasons,
            "evidence": evidence,
            "assumptions": assumptions,
            "information_gaps": info_gaps,
            "needs_local_review": bool(combined_counts["UNKNOWN"] > 0 or combined_counts["WARNING"] > 0 or not seq_eval["feasible"] or land_use["requires_local_verification"]),
            "review_checklist": checklist,
        })

    return {
        "schema_version": "1.1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "field_id": fld["field_id"],
        "field_name": fld.get("field_name"),
        "generation_config": {
            **asdict(cfg),
            "start_season": start_season,
            "start_year": start_year,
            "planning_mode": temporal_info["planning_mode"],
            "horizon_seasons": horizon,
            "deterministic": True,
            "ranking_executed": False,
        },
        "temporal_validation": temporal_info,
        "land_use_assessment": land_use,
        "field_insights": _build_field_insights(field_profile),
        "history_assessment": history_info,
        "preference_handling": {
            "excluded_crop_ids": list(pref.get("excluded_crop_ids") or []),
            "target_crop_report": meta_gen["target_report"],
            "optional_input_completeness": {
                "crop_history": flags.get("crop_history", "NOT_PROVIDED"),
                "preferences_block": flags.get("preferences_block", "NOT_PROVIDED"),
                "equipment_constraints": flags.get("equipment_constraints", "NOT_PROVIDED"),
                "forage_value_weight": flags.get("forage_value_weight", "NOT_PROVIDED"),
            },
        },
        "generation_summary": {
            "total_candidates": len(strategies),
            "feasible_pass_count": feasible_pass,
            "conditionally_feasible_count": cond_feasible,
            "infeasible_count": infeasible,
            "existing_baseline_generated": any(s["is_existing_rotation"] for s in strategies),
            "patterns_represented": [s["pattern_id"] for s in strategies],
            "duplicates_skipped_count": len(meta_gen["skipped_duplicate_sequences"]),
        },
        "strategies": strategies,
    }
