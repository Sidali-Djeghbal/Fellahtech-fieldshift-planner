"""Deterministic Agronomic Constraint & Sequence Compatibility Engine (Phase G).

Evaluates individual candidate crops and multi-year/seasonal crop sequences
against the validated Field Profile without performing rotation optimization,
yield estimation, or Earth Engine calls.

Strict scientific principles:
- Evidence classes: HARD_CONSTRAINT, SOFT_CONSTRAINT, EXPERT_ASSUMPTION, UNKNOWN.
- Evaluation statuses: PASS, WARNING, FAIL, UNKNOWN.
- Unknown constraints or missing local datasets NEVER silently become PASS.
- SoilGrids Nitrogen (nitrogen_0_30cm) remains strictly quarantined.
- Optional farmer inputs preserve null ('NOT_PROVIDED') distinctly from []
  ('EXPLICITLY_CONFIRMED_EMPTY') via input_completeness_flags.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fieldshift_integration.config import PROJECT_ROOT

KNOWLEDGE_DIR = PROJECT_ROOT / "agronomic_knowledge"
CROP_PROFILES_JSON = KNOWLEDGE_DIR / "crop_profiles.json"
CONSTRAINT_RULES_JSON = KNOWLEDGE_DIR / "constraint_rules.json"
SEQUENCE_COMPAT_JSON = KNOWLEDGE_DIR / "sequence_compatibility.json"

EVIDENCE_CLASSES = ("HARD_CONSTRAINT", "SOFT_CONSTRAINT", "EXPERT_ASSUMPTION", "UNKNOWN")
EVALUATION_STATUSES = ("PASS", "WARNING", "FAIL", "UNKNOWN")


@dataclass(frozen=True)
class RuleEvaluation:
    """Standard deterministic outcome for a single agronomic or sequence rule."""

    rule_id: str
    domain: str
    evidence_classification: str
    status: str
    reason: str
    source: str
    uncertainty_note: str
    observed_inputs: Dict[str, Any]

    def __post_init__(self) -> None:
        if self.evidence_classification not in EVIDENCE_CLASSES:
            raise ValueError(f"Invalid evidence_classification: {self.evidence_classification}")
        if self.status not in EVALUATION_STATUSES:
            raise ValueError(f"Invalid evaluation status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgronomicKnowledgeBase:
    """In-memory structured Phase G agronomic knowledge base."""

    crops: Dict[str, Dict[str, Any]]
    rules_catalog: Dict[str, Dict[str, Any]]
    sequence_rules: Dict[str, Dict[str, Any]]
    group_membership: Dict[str, List[str]]
    quarantined_inputs: List[Dict[str, str]]


@lru_cache(maxsize=1)
def load_knowledge_base() -> AgronomicKnowledgeBase:
    """Load and validate Phase G JSON knowledge files deterministically."""
    crops_raw = json.loads(CROP_PROFILES_JSON.read_text(encoding="utf-8"))
    rules_raw = json.loads(CONSTRAINT_RULES_JSON.read_text(encoding="utf-8"))
    seq_raw = json.loads(SEQUENCE_COMPAT_JSON.read_text(encoding="utf-8"))

    return AgronomicKnowledgeBase(
        crops=crops_raw["crops"],
        rules_catalog={r["rule_id"]: r for r in rules_raw["rules"]},
        sequence_rules={r["seq_rule_id"]: r for r in seq_raw["sequence_rules"]},
        group_membership=seq_raw["group_membership"],
        quarantined_inputs=rules_raw["quarantined_inputs"],
    )


def _metric_val(section: Dict[str, Any], key: str) -> Optional[Any]:
    return section.get(key, {}).get("value")


def _metric_stats(section: Dict[str, Any], key: str) -> Dict[str, Any]:
    return section.get(key, {}).get("stats") or {}


def _param(crop: Dict[str, Any], pname: str) -> Dict[str, Any]:
    return crop["parameters"][pname]


def _make_rule(
    kb: AgronomicKnowledgeBase,
    rule_id: str,
    status: str,
    reason: str,
    uncertainty_note: str,
    observed_inputs: Dict[str, Any],
    evidence_override: Optional[str] = None,
) -> RuleEvaluation:
    meta = kb.rules_catalog[rule_id]
    ev_class = evidence_override or meta["evidence_classification"]
    return RuleEvaluation(
        rule_id=rule_id,
        domain=meta["domain"],
        evidence_classification=ev_class,
        status=status,
        reason=reason,
        source=meta["source"],
        uncertainty_note=uncertainty_note,
        observed_inputs=observed_inputs,
    )


def _eval_perennial_exclusion(kb: AgronomicKnowledgeBase, crop: Dict[str, Any]) -> RuleEvaluation:
    in_scope = crop.get("in_annual_rotation_scope")
    cyc = crop.get("annual_or_perennial")
    obs = {"annual_or_perennial": cyc, "in_annual_rotation_scope": in_scope}
    if in_scope is None:
        return _make_rule(kb, "RULE_PERENNIAL_EXCLUSION", "UNKNOWN", "Crop annual/perennial rotation scope missing.", "Cannot confirm eligibility.", obs)
    if not bool(in_scope):
        return _make_rule(
            kb, "RULE_PERENNIAL_EXCLUSION", "FAIL",
            f"{crop['canonical_name']} is a {cyc} orchard crop excluded from ordinary annual rotation switching.",
            "Phase E permanent perennial anchor guard.", obs,
        )
    return _make_rule(
        kb, "RULE_PERENNIAL_EXCLUSION", "PASS",
        f"{crop['canonical_name']} is an annual crop/period eligible for annual rotation evaluation.",
        "Verified against Phase E crop system inventory.", obs,
    )


def _eval_planting_season(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], target_season: Optional[str]) -> RuleEvaluation:
    seasons_p = _param(crop, "suitable_planting_seasons")
    allowed = seasons_p["value"]
    obs = {"target_season": target_season, "suitable_planting_seasons": allowed}
    if not target_season or allowed is None:
        return _make_rule(kb, "RULE_PLANTING_SEASON_COMPATIBILITY", "UNKNOWN", "Target or crop planting seasons missing.", "Season compatibility unresolved.", obs)
    if len(allowed) == 0 or target_season not in allowed:
        return _make_rule(
            kb, "RULE_PLANTING_SEASON_COMPATIBILITY", "FAIL",
            f"{crop['canonical_name']} planting seasons {allowed} exclude target season '{target_season}'.",
            "Regional ITGC/FAO-56 sowing calendar.", obs,
        )
    return _make_rule(
        kb, "RULE_PLANTING_SEASON_COMPATIBILITY", "PASS",
        f"{crop['canonical_name']} supports '{target_season}' sowing ({_param(crop, 'planting_window')['value']}).",
        "Check exact soil moisture & frost timing before planting.", obs,
    )


def _eval_water_irrigation_gate(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], water: Dict[str, Any]) -> RuleEvaluation:
    regime = _param(crop, "water_requirement_category")["value"]
    avail = water.get("availability")
    src = water.get("source")
    sys = water.get("irrigation_system")
    obs = {"crop_water_regime": regime, "availability": avail, "source": src, "irrigation_system": sys}

    if regime is None:
        return _make_rule(kb, "RULE_WATER_IRRIGATION_GATE", "UNKNOWN", "Crop water requirement category is missing.", "Cannot evaluate irrigation gate.", obs)
    if regime == "STRICTLY_IRRIGATED":
        if src == "rainfed" or sys == "none":
            return _make_rule(
                kb, "RULE_WATER_IRRIGATION_GATE", "FAIL",
                f"{crop['canonical_name']} requires strict irrigation and cannot be grown on a rainfed / unirrigated parcel.",
                "Phase E CON_13_IRRIGATION binary gate.", obs,
            )
        if avail == "unknown" or sys == "unknown":
            return _make_rule(
                kb, "RULE_WATER_IRRIGATION_GATE", "UNKNOWN",
                f"Water availability='{avail}' or irrigation_system='{sys}' is unknown for strictly irrigated {crop['canonical_name']}.",
                "An unknown water gate MUST NOT auto-pass (triggers Q_WATER_MATERIAL).", obs,
            )
        if avail == "limited":
            return _make_rule(
                kb, "RULE_WATER_IRRIGATION_GATE", "WARNING",
                f"Declared irrigation availability is 'limited' for moisture-sensitive {crop['canonical_name']} (blossom-end rot / rationing hazard).",
                "Verify seasonal Bouhamdane dam or well delivery before summer planting.", obs,
            )
        return _make_rule(
            kb, "RULE_WATER_IRRIGATION_GATE", "PASS",
            f"Farmer declared '{avail}' water via {src} ({sys}) satisfying {crop['canonical_name']} irrigation gate.",
            "Dam quota volumes remain unverified spatially; surface irrigation incurs higher evaporative loss than drip.", obs,
        )
    # Rainfed or supplemental crop
    if avail == "unknown" and regime == "RAINFED_OR_SUPPLEMENTAL":
        return _make_rule(
            kb, "RULE_WATER_IRRIGATION_GATE", "PASS",
            f"{crop['canonical_name']} can operate rainfed (supplemental capacity unknown).",
            "Evaluated conservatively under rainfed assumption in rainfall check.", obs,
        )
    return _make_rule(
        kb, "RULE_WATER_IRRIGATION_GATE", "PASS",
        f"{crop['canonical_name']} water gate ({regime}) satisfied by declared field water profile.",
        "Actual rainfed adequacy depends on seasonal precipitation regime.", obs,
    )


def _eval_precipitation_regime(
    kb: AgronomicKnowledgeBase, crop: Dict[str, Any], water: Dict[str, Any], gpm: Dict[str, Any], npw: Dict[str, Any]
) -> RuleEvaluation:
    gpm_ann = _metric_val(gpm, "gpm_annual_precip_2016_2025_mean_mm")
    np_ann = _metric_val(npw, "nasa_power_annual_precip_2016_2025_mean_mm")
    min_req = _param(crop, "min_annual_rainfed_precip_mm")["value"]
    irrig_active = (water.get("availability") in {"moderate", "abundant"}) and (water.get("source") != "rainfed") and (water.get("irrigation_system") != "none")
    obs = {"gpm_annual_mm": gpm_ann, "nasa_power_annual_mm": np_ann, "min_rainfed_mm": min_req, "irrig_active": irrig_active}

    if min_req is None:
        return _make_rule(
            kb, "RULE_PRECIPITATION_REGIME", "PASS" if irrig_active else "UNKNOWN",
            "Strictly irrigated crop governed by confirmed water supply rather than rainfed precipitation." if irrig_active else "Precipitation threshold N/A and irrigation not actively confirmed.",
            "CON_06_PRECIP dual-bound check.", obs,
        )
    if irrig_active:
        return _make_rule(
            kb, "RULE_PRECIPITATION_REGIME", "PASS",
            f"Active irrigation ({water.get('source')}/{water.get('irrigation_system')}) buffers regional rainfall envelope (GPM={gpm_ann}, POWER={np_ann} mm/yr).",
            "11 km GPM & ~55 km NASA POWER represent regional background only.", obs,
        )
    if gpm_ann is None and np_ann is None:
        return _make_rule(
            kb, "RULE_PRECIPITATION_REGIME", "UNKNOWN",
            "Both GPM and NASA POWER precipitation datasets are missing/unavailable locally.",
            "Cannot validate rainfed rainfall envelope without local climate data.", obs,
        )
    if crop["crop_id"] == "SUNFLOWER":
        return _make_rule(
            kb, "RULE_PRECIPITATION_REGIME", "WARNING",
            f"Rainfed Sunflower faces extreme Summer rainfall deficit (~38-49 mm summer rain) despite annual mean (GPM={gpm_ann}, POWER={np_ann} mm/yr).",
            "CON_06 & crop_system_inventory note supplemental irrigation or unverified deep clay storage needed.", obs,
        )
    vals = [v for v in (gpm_ann, np_ann) if v is not None]
    if all(v < min_req for v in vals):
        return _make_rule(
            kb, "RULE_PRECIPITATION_REGIME", "WARNING",
            f"Regional annual rain (GPM={gpm_ann}, POWER={np_ann} mm/yr) lies below {min_req} mm/yr preferred rainfed baseline for {crop['canonical_name']}.",
            "Elevates moisture deficit risk in dry years; neither dataset replaces on-farm rain gauges.", obs,
        )
    if gpm_ann is not None and np_ann is not None and (min(gpm_ann, np_ann) < min_req <= max(gpm_ann, np_ann)):
        return _make_rule(
            kb, "RULE_PRECIPITATION_REGIME", "WARNING",
            f"PRECIP_SENSITIVE cross-product straddle: GPM ({gpm_ann} mm/yr) < {min_req} mm threshold while NASA POWER ({np_ann} mm/yr) >= {min_req} mm.",
            "Known +132 mm/yr regional offset (CON_06_PRECIP); apply conservative rainfed caution.", obs,
        )
    return _make_rule(
        kb, "RULE_PRECIPITATION_REGIME", "PASS",
        f"Regional rainfall envelope (GPM={gpm_ann}, POWER={np_ann} mm/yr) meets {min_req} mm/yr rainfed threshold.",
        "Macro 11 km / ~55 km climate context only; Spring interannual drought volatility remains significant.", obs,
    )


def _eval_thermal_heat_frost(
    kb: AgronomicKnowledgeBase, crop: Dict[str, Any], target_season: str, npw: Dict[str, Any]
) -> RuleEvaluation:
    tmax = _metric_val(npw, "nasa_power_t2m_max_2016_2025_mean_c")
    tmin = _metric_val(npw, "nasa_power_t2m_min_2016_2025_mean_c")
    tmax_stats = _metric_stats(npw, "nasa_power_t2m_max_2016_2025_mean_c")
    tmin_stats = _metric_stats(npw, "nasa_power_t2m_min_2016_2025_mean_c")
    summer_tmax = tmax_stats.get("summer")
    winter_tmin = tmin_stats.get("winter")
    obs = {"summer_mean_tmax_c": summer_tmax, "winter_mean_tmin_c": winter_tmin, "target_season": target_season}

    if tmax is None or tmin is None:
        return _make_rule(
            kb, "RULE_THERMAL_HEAT_FROST", "UNKNOWN",
            "NASA POWER macro temperature observations are missing locally.",
            "Thermal heat/frost hazard unverified.", obs,
        )
    if crop["crop_id"] in {"TOMATO_IND", "SUNFLOWER", "CHICKPEA_SPRING"} and summer_tmax is not None and summer_tmax >= 34.5:
        return _make_rule(
            kb, "RULE_THERMAL_HEAT_FROST", "WARNING",
            f"High Summer mean Tmax ({summer_tmax} degC on ~55-69 km cell) signals flowering/fruit-set heat stress hazard for {crop['canonical_name']}.",
            "Coarse MERRA-2 cell misses valley microclimate cooling or heatwaves.", obs,
        )
    if crop["crop_id"] == "CHICKPEA_WINTER" and winter_tmin is not None and winter_tmin <= 6.5:
        return _make_rule(
            kb, "RULE_THERMAL_HEAT_FROST", "WARNING",
            f"Cool Winter mean Tmin ({winter_tmin} degC) requires cold- and Ascochyta-tolerant winter chickpea cultivars (ICARDA-ITGC).",
            "Local frost-pocket inversions are unresolved by ~55-69 km macro cells.", obs,
        )
    return _make_rule(
        kb, "RULE_THERMAL_HEAT_FROST", "PASS",
        f"Coarse thermal regime (Winter Tmin={winter_tmin} C, Summer Tmax={summer_tmax} C) falls within nominal range for {crop['canonical_name']}.",
        "Macro ~55-69 km reanalysis cell; does not replace local frost/heat checks.", obs,
    )


def _eval_soil_moisture(
    kb: AgronomicKnowledgeBase, crop: Dict[str, Any], water: Dict[str, Any], gpm: Dict[str, Any]
) -> RuleEvaluation:
    win_sm = _metric_val(gpm, "smap_rootzone_sm_winter_2016_2025_mean")
    spr_sm = _metric_val(gpm, "smap_rootzone_sm_spring_2016_2025_mean")
    obs = {"smap_winter_rz_m3m3": win_sm, "smap_spring_rz_m3m3": spr_sm}
    if win_sm is None and spr_sm is None:
        return _make_rule(kb, "RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT", "UNKNOWN", "SMAP 11 km root-zone moisture unavailable locally.", "Moisture context unresolved.", obs)
    irrig_active = (water.get("availability") in {"moderate", "abundant"}) and (water.get("source") != "rainfed")
    if not irrig_active and crop["crop_id"] in {"CHICKPEA_SPRING", "FABA_BEAN", "LENTIL"} and spr_sm is not None and spr_sm < 0.21:
        return _make_rule(
            kb, "RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT", "WARNING",
            f"Coarse 11 km Spring root-zone moisture averages {spr_sm} m3/m3 (<0.21), indicating Spring dry-year stress sensitivity for rainfed pulses.",
            "11 km SMAP L4 modeled product is insensitive to field soil management.", obs,
        )
    return _make_rule(
        kb, "RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT", "PASS",
        f"Coarse 11 km SMAP root-zone moisture logged (Winter={win_sm}, Spring={spr_sm} m3/m3).",
        "Regional 11 km model context only; insensitive to parcel irrigation.", obs,
    )


def _eval_soil_texture(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], soil: Dict[str, Any]) -> RuleEvaluation:
    clay = _metric_val(soil, "clay_0_30cm")
    tex = _metric_val(soil, "usda_texture_0_5cm")
    obs = {"clay_0_30cm_pct": clay, "usda_texture_0_5cm": tex}
    if clay is None:
        return _make_rule(
            kb, "RULE_SOIL_TEXTURE_WORKABILITY", "UNKNOWN",
            "SoilGrids 250 m clay_0_30cm is null (masked pixel or missing dataset).",
            "Never substitute default clay values; inspect parcel tilth physically.", obs,
        )
    if crop["crop_id"] == "BARE_FALLOW":
        return _make_rule(kb, "RULE_SOIL_TEXTURE_WORKABILITY", "PASS", f"Modeled clay={clay}% ({tex}) logged for fallow baseline.", "SoilGrids 250 m modeled proxy.", obs)
    if crop["crop_id"] in {"LENTIL", "POTATO"} and clay >= 35.0:
        return _make_rule(
            kb, "RULE_SOIL_TEXTURE_WORKABILITY", "WARNING",
            f"Modeled Clay ({clay}%, {tex}) >=35% heavy-clay threshold: elevated waterlogging (Lentil) or tuber deformation/digging hazard (Potato).",
            "250 m SoilGrids modeled estimate (NOT lab granulometry).", obs,
        )
    if crop["crop_id"] in {"POTATO", "LENTIL", "CHICKPEA_WINTER", "OLIVE"} and clay >= 32.0:
        return _make_rule(
            kb, "RULE_SOIL_TEXTURE_WORKABILITY", "WARNING",
            f"Modeled Clay ({clay}%, {tex}) >=32% signals narrow winter tillage windows & sensitive root aeration for {crop['canonical_name']}.",
            "SoilGrids 250 m model estimate; verify friability and surface drainage locally.", obs,
        )
    return _make_rule(
        kb, "RULE_SOIL_TEXTURE_WORKABILITY", "PASS",
        f"Modeled texture {tex} (Clay={clay}%) falls within workable suitability bounds for {crop['canonical_name']}.",
        "Global 250 m SoilGrids prediction; NOT a parcel soil lab measurement.", obs,
    )


def _eval_dem_drainage(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], soil: Dict[str, Any], terrain: Dict[str, Any]) -> RuleEvaluation:
    slope = _metric_val(terrain, "dem_slope_pct")
    clay = _metric_val(soil, "clay_0_30cm")
    sens = (_param(crop, "soil_drainage_requirements")["value"] or {}).get("waterlogging_sensitivity")
    obs = {"dem_slope_pct": slope, "clay_0_30cm_pct": clay, "waterlogging_sensitivity": sens}
    if slope is None:
        if sens in {"EXTREME", "EXTREME_ROOT_ASPHYXIA", "HIGH", "HIGH_ON_POOR_DRAINAGE", "MODERATE_HIGH"}:
            return _make_rule(
                kb, "RULE_DEM_DRAINAGE_UNCERTAINTY", "UNKNOWN",
                f"DEM elevation/slope is UNAVAILABLE_NOT_INTEGRATED while {crop['canonical_name']} exhibits '{sens}' waterlogging sensitivity.",
                "Drainage suitability remains UNKNOWN until visual puddling check or SRTM DEM integration.", obs,
            )
        if crop["crop_id"] == "BARE_FALLOW":
            return _make_rule(
                kb, "RULE_DEM_DRAINAGE_UNCERTAINTY", "WARNING",
                "DEM slope missing: Bare Fallow winter erosion risk on >5% slopes cannot be evaluated spatially.",
                "Avoid leaving steep slopes bare through winter rains.", obs,
            )
        return _make_rule(
            kb, "RULE_DEM_DRAINAGE_UNCERTAINTY", "WARNING",
            f"DEM slope unavailable locally; surface ponding hazard in wet winters on {clay}% clay remains unverified visually.",
            "Missing local DEM preserved explicitly.", obs,
        )
    return _make_rule(kb, "RULE_DEM_DRAINAGE_UNCERTAINTY", "PASS", f"Local slope ({slope}%) evaluated.", "DEM integrated.", obs)


def _eval_soil_ph(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], soil: Dict[str, Any]) -> RuleEvaluation:
    ph = _metric_val(soil, "ph_0_30cm")
    ss = _param(crop, "soil_suitability")["value"] or {}
    obs = {"ph_0_30cm": ph, "optimal_ph": [ss.get("optimal_ph_min"), ss.get("optimal_ph_max")]}
    if ph is None:
        return _make_rule(kb, "RULE_SOIL_PH_SUITABILITY", "UNKNOWN", "SoilGrids 250 m ph_0_30cm is null (masked or missing).", "Soil pH reaction unverified.", obs)
    if crop["crop_id"] == "POTATO" and ph >= ss.get("scab_warning_ph_above", 6.5):
        return _make_rule(
            kb, "RULE_SOIL_PH_SUITABILITY", "WARNING",
            f"Modeled topsoil pH={ph} >= 6.5 triggers common scab (Streptomyces) hazard for Potato (optimal 5.0-6.2).",
            "CON_02_PH SoilGrids 250 m prediction (lab pH & CaCO3 unavailable).", obs,
        )
    tol_min = ss.get("tolerable_ph_min", 4.5)
    tol_max = ss.get("tolerable_ph_max", 8.8)
    opt_min = ss.get("optimal_ph_min", 0.0)
    opt_max = ss.get("optimal_ph_max", 14.0)
    if ph < tol_min or ph > tol_max:
        return _make_rule(
            kb, "RULE_SOIL_PH_SUITABILITY", "FAIL",
            f"Modeled pH={ph} falls outside biological tolerance [{tol_min}, {tol_max}] for {crop['canonical_name']}.",
            "Verify against lab pH sample before exclusion.", obs,
        )
    if ph < opt_min or ph > opt_max:
        return _make_rule(
            kb, "RULE_SOIL_PH_SUITABILITY", "WARNING",
            f"Modeled pH={ph} lies outside optimal range [{opt_min}, {opt_max}] (within tolerable limits) for {crop['canonical_name']}.",
            "CaCO3 active lime & micronutrient availability unmeasured locally.", obs,
        )
    return _make_rule(
        kb, "RULE_SOIL_PH_SUITABILITY", "PASS",
        f"Modeled pH={ph} sits within optimal range [{opt_min}, {opt_max}] for {crop['canonical_name']}.",
        "250 m SoilGrids prediction; NOT laboratory soil analysis.", obs,
    )


def _eval_soil_soc(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], soil: Dict[str, Any]) -> RuleEvaluation:
    soc = _metric_val(soil, "soc_0_30cm")
    som_dir = (_param(crop, "som_contribution")["value"] or {}).get("direction", "")
    obs = {"soc_0_30cm_g_kg": soc, "som_contribution_direction": som_dir}
    if soc is None:
        return _make_rule(
            kb, "RULE_SOIL_SOC_PRIORITY", "UNKNOWN",
            "SoilGrids 250 m soc_0_30cm is null (including native 100 Guelma SOC-NaN pixels or missing archive).",
            "Never impute SOC values silently.", obs,
        )
    if soc < 18.0 and (crop["crop_id"] in {"BARE_FALLOW", "POTATO"} or "NEGATIVE" in som_dir):
        return _make_rule(
            kb, "RULE_SOIL_SOC_PRIORITY", "WARNING",
            f"Depleted topsoil SOC ({soc} g/kg < 18 g/kg) disfavors carbon-depleting {crop['canonical_name']}; prioritize legume/Vetch-Oat conservation break.",
            "CON_03_SOC modeled 250 m organic carbon proxy.", obs,
        )
    return _make_rule(
        kb, "RULE_SOIL_SOC_PRIORITY", "PASS",
        f"Topsoil SOC ({soc} g/kg) evaluated with SOM role '{som_dir}'.",
        "SoilGrids 250 m SOC proxy; lab Walkley-Black/Dumas SOC & Nmin remain unavailable (Nitrogen excluded).", obs,
    )


def _eval_salinity_unmeasured(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], water: Dict[str, Any]) -> RuleEvaluation:
    src = water.get("source")
    sys = water.get("irrigation_system")
    tol = _param(crop, "salinity_tolerance")["value"]
    obs = {"water_source": src, "irrigation_system": sys, "crop_salinity_tolerance": tol}
    if src in {"reservoir", "river", "well", "groundwater"} and sys != "none":
        if crop["crop_id"] in {"BARLEY", "BARE_FALLOW"}:
            return _make_rule(
                kb, "RULE_SALINITY_UNMEASURED_IRRIGATION", "WARNING",
                f"Irrigated field lacks local ECe/ECw salinity measurement; {crop['canonical_name']} tolerates higher salinity than pulses/vegetables but salt buildup must be checked.",
                "Regional Seybouse perimeter ~20% salinization hazard.", obs,
            )
        return _make_rule(
            kb, "RULE_SALINITY_UNMEASURED_IRRIGATION", "UNKNOWN",
            f"Irrigated parcel ({src}/{sys}) has NO local ECe/ECw salinity measurement on disk for {crop['canonical_name']} ({tol}).",
            "Secondary salinization hazard unverified (Seybouse literature); triggers Q_IRRIGATION_SALINITY_SIGN.", obs,
        )
    return _make_rule(
        kb, "RULE_SALINITY_UNMEASURED_IRRIGATION", "PASS",
        "Rainfed parcel carries minimal irrigation-induced secondary salinization exposure.",
        "Natural soil ECe remains unmeasured locally.", obs,
    )


def _eval_cropland_veg(
    kb: AgronomicKnowledgeBase, crop: Dict[str, Any], cf_sec: Dict[str, Any], s2_sec: Dict[str, Any], modis_sec: Dict[str, Any]
) -> RuleEvaluation:
    cf = _metric_val(cf_sec, "crop_frequency_2021_2025")
    s2_ndvi = _metric_val(s2_sec, "s2_2024_03_ndvi_10m")
    modis_sp = _metric_val(modis_sec, "modis_ndvi_spring_2016_2025_mean")
    obs = {"crop_frequency_2021_2025": cf, "s2_2024_03_ndvi_10m": s2_ndvi, "modis_spring_ndvi": modis_sp}
    if cf is None and s2_ndvi is None and modis_sp is None:
        return _make_rule(kb, "RULE_CROPLAND_VEG_CONTEXT", "UNKNOWN", "All remote-sensing vegetation layers missing locally.", "Parcel land cover unverified.", obs)
    if cf is not None and cf < 0.2 and crop["crop_id"] not in {"OLIVE", "BARE_FALLOW"}:
        return _make_rule(
            kb, "RULE_CROPLAND_VEG_CONTEXT", "WARNING",
            f"Low 2021-2025 ESA Crop Frequency ({cf} < 0.20): polygon may contain permanent orchards, buildings, water, or non-arable land.",
            "CropFreq valid ONLY 2021-2025 (blocked 2017-2020); multi-year S2 rasters remain Wilaya fallback only.", obs,
        )
    return _make_rule(
        kb, "RULE_CROPLAND_VEG_CONTEXT", "PASS",
        f"Cropland & vegetation context observed (CropFreq 2021-2025={cf}, S2 2024-03 NDVI={s2_ndvi}, MODIS Spring={modis_sp}).",
        "Vegetation greenness never identifies crop species; Wilaya multi-year S2 metric is regional fallback only.", obs,
    )


def _eval_hypothesis_status(kb: AgronomicKnowledgeBase, crop: Dict[str, Any]) -> RuleEvaluation:
    status_g = crop.get("guelma_evidence_status")
    obs = {"guelma_evidence_status": status_g}
    if status_g == "HYPOTHESIS_NEEDS_DSA_CHECK":
        return _make_rule(
            kb, "RULE_HYPOTHESIS_LOCAL_EVIDENCE_STATUS", "WARNING",
            f"{crop['canonical_name']} carries Phase E status 'HYPOTHESIS_NEEDS_DSA_CHECK' and lacks local Guelma yield/agronomy trial validation.",
            "Requires local DSA Guelma / ITGC trial confirmation before wide farmer rollout.", obs,
        )
    return _make_rule(
        kb, "RULE_HYPOTHESIS_LOCAL_EVIDENCE_STATUS", "PASS",
        f"{crop['canonical_name']} carries verified regional status '{status_g}'.",
        "Regional/Mediterranean agronomic literature foundation.", obs,
    )


def _eval_equipment_constraints(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], farmer: Dict[str, Any]) -> RuleEvaluation:
    flags = farmer.get("input_completeness_flags") or {}
    eq_status = flags.get("equipment_constraints", "NOT_PROVIDED")
    pref = farmer.get("preferences") or {}
    eq_list = pref.get("equipment_constraints")
    ops = _param(crop, "machinery_and_operations")["value"] or {}
    sensitive = set(ops.get("equipment_tags_sensitive") or [])
    obs = {"equipment_completeness": eq_status, "equipment_constraints": eq_list, "sensitive_tags": sorted(sensitive)}

    if eq_status == "NOT_PROVIDED" or eq_list is None:
        return _make_rule(
            kb, "RULE_EQUIPMENT_CONSTRAINT_CHECK", "UNKNOWN",
            "Optional equipment_constraints is null ('NOT_PROVIDED'); refusing to assume machinery availability.",
            "Preserves strict null vs [] separation per Phase G Section 8.", obs,
        )
    if eq_status == "EXPLICITLY_CONFIRMED_EMPTY" or len(eq_list) == 0:
        return _make_rule(
            kb, "RULE_EQUIPMENT_CONSTRAINT_CHECK", "PASS",
            "Farmer explicitly confirmed empty equipment_constraints ([]).",
            "Machinery constraints verified empty.", obs,
        )
    hits = sorted(set(eq_list) & sensitive)
    if hits:
        return _make_rule(
            kb, "RULE_EQUIPMENT_CONSTRAINT_CHECK", "WARNING",
            f"Declared equipment constraints {hits} conflict with {crop['canonical_name']} operations ({ops.get('operations')}).",
            "Requires contractor service or alternative crop selection.", obs,
        )
    return _make_rule(
        kb, "RULE_EQUIPMENT_CONSTRAINT_CHECK", "PASS",
        f"Declared equipment constraints {eq_list} do not conflict with {crop['canonical_name']} tagged requirements.",
        "Specific tractor/implement fuel/hour parameters remain unquantified locally.", obs,
    )


def _eval_forage_alignment(kb: AgronomicKnowledgeBase, crop: Dict[str, Any], farmer: Dict[str, Any]) -> RuleEvaluation:
    flags = farmer.get("input_completeness_flags") or {}
    fw_status = flags.get("forage_value_weight", "NOT_PROVIDED")
    pref = farmer.get("preferences") or {}
    fw = pref.get("forage_value_weight")
    obs = {"forage_completeness": fw_status, "forage_value_weight": fw}

    if fw_status == "NOT_PROVIDED" or fw is None:
        return _make_rule(
            kb, "RULE_FORAGE_REQUIREMENT_ALIGNMENT", "UNKNOWN",
            "Optional forage_value_weight is null ('NOT_PROVIDED'); livestock forage priority cannot be assumed zero or mandatory.",
            "Preserves null vs explicit value per Phase G Section 8.", obs,
        )
    if float(fw) >= 0.4 and crop["crop_id"] == "BARE_FALLOW":
        return _make_rule(
            kb, "RULE_FORAGE_REQUIREMENT_ALIGNMENT", "WARNING",
            f"Declared forage_value_weight={fw} favors livestock feed; Bare Fallow sacrifices Vetch-Oat hay / Barley straw.",
            "Consider Vetch-Oat fallow replacement in mixed livestock farms.", obs,
        )
    return _make_rule(
        kb, "RULE_FORAGE_REQUIREMENT_ALIGNMENT", "PASS",
        f"Explicitly provided forage_value_weight={fw} is compatible with {crop['canonical_name']}.",
        "Livestock prioritization handled without defaulting missing weights.", obs,
    )


def evaluate_crop_for_field(
    field_profile: Dict[str, Any],
    crop_id: str,
    target_season: Optional[str] = None,
    kb: Optional[AgronomicKnowledgeBase] = None,
) -> Dict[str, Any]:
    """Deterministically evaluate all single-crop rules against a validated Field Profile."""
    kb = kb or load_knowledge_base()
    if crop_id not in kb.crops:
        raise ValueError(f"Unknown crop_id '{crop_id}'; expected one of {sorted(kb.crops.keys())}.")

    crop = kb.crops[crop_id]
    sec_a = field_profile["section_a_farmer_provided"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    season = target_season or sec_a["planning"]["start_season"]

    water = sec_a["water"]
    soil = ds["soilgrids_v6"]
    gpm = ds["gpm_and_smap"]
    npw = ds["nasa_power"]
    cf = ds["crop_frequency"]
    s2 = ds["sentinel2"]
    modis = ds["modis"]
    terrain = ds["terrain_dem"]

    evals: List[RuleEvaluation] = [
        _eval_perennial_exclusion(kb, crop),
        _eval_planting_season(kb, crop, season),
        _eval_water_irrigation_gate(kb, crop, water),
        _eval_precipitation_regime(kb, crop, water, gpm, npw),
        _eval_thermal_heat_frost(kb, crop, season, npw),
        _eval_soil_moisture(kb, crop, water, gpm),
        _eval_soil_texture(kb, crop, soil),
        _eval_dem_drainage(kb, crop, soil, terrain),
        _eval_soil_ph(kb, crop, soil),
        _eval_soil_soc(kb, crop, soil),
        _eval_salinity_unmeasured(kb, crop, water),
        _eval_cropland_veg(kb, crop, cf, s2, modis),
        _eval_hypothesis_status(kb, crop),
        _eval_equipment_constraints(kb, crop, sec_a),
        _eval_forage_alignment(kb, crop, sec_a),
    ]

    status_counts = {s: sum(1 for r in evals if r.status == s) for s in EVALUATION_STATUSES}
    hard_fails = [r.rule_id for r in evals if r.evidence_classification == "HARD_CONSTRAINT" and r.status == "FAIL"]
    hard_unknowns = [r.rule_id for r in evals if r.evidence_classification == "HARD_CONSTRAINT" and r.status == "UNKNOWN"]
    other_fails = [r.rule_id for r in evals if r.evidence_classification != "HARD_CONSTRAINT" and r.status == "FAIL"]

    if hard_fails:
        feasible = False
        feasibility_status = "INFEASIBLE_HARD_CONSTRAINT"
    elif hard_unknowns:
        feasible = False
        feasibility_status = "UNVERIFIED_HARD_UNKNOWN"
    elif other_fails:
        feasible = False
        feasibility_status = "INFEASIBLE_CONSTRAINT"
    elif status_counts["WARNING"] > 0 or status_counts["UNKNOWN"] > 0:
        feasible = True
        feasibility_status = "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS"
    else:
        feasible = True
        feasibility_status = "FEASIBLE_PASS"

    return {
        "crop_id": crop_id,
        "canonical_name": crop["canonical_name"],
        "target_season": season,
        "feasible": feasible,
        "feasibility_status": feasibility_status,
        "hard_fail_rules": hard_fails,
        "hard_unknown_rules": hard_unknowns,
        "status_counts": status_counts,
        "quarantined_excluded": ["soilgrids_v6.nitrogen_0_30cm"],
        "rule_evaluations": [r.to_dict() for r in evals],
    }


def evaluate_all_crops_for_field(
    field_profile: Dict[str, Any],
    target_season: Optional[str] = None,
    kb: Optional[AgronomicKnowledgeBase] = None,
) -> Dict[str, Dict[str, Any]]:
    """Evaluate all 13 Phase E/G crop profiles for a Field Profile (no optimization ranking)."""
    kb = kb or load_knowledge_base()
    return {
        cid: evaluate_crop_for_field(field_profile, cid, target_season=target_season, kb=kb)
        for cid in kb.crops
    }


def _canonical_annual_season(crop: Dict[str, Any]) -> str:
    allowed = _param(crop, "suitable_planting_seasons")["value"] or []
    for preferred in ("Winter", "Autumn", "Spring", "Summer"):
        if preferred in allowed:
            return preferred
    return "Winter"


def _make_seq_rule(
    kb: AgronomicKnowledgeBase,
    seq_rule_id: str,
    status: str,
    reason: str,
    observed_inputs: Dict[str, Any],
) -> RuleEvaluation:
    meta = kb.sequence_rules[seq_rule_id]
    return RuleEvaluation(
        rule_id=seq_rule_id,
        domain=meta["name"],
        evidence_classification=meta["evidence_classification"],
        status=status,
        reason=reason,
        source=meta["source"],
        uncertainty_note=meta["rule"],
        observed_inputs=observed_inputs,
    )


def evaluate_crop_sequence(
    field_profile: Dict[str, Any],
    sequence_crops: Sequence[str],
    slot_seasons: Optional[Sequence[Optional[str]]] = None,
    kb: Optional[AgronomicKnowledgeBase] = None,
) -> Dict[str, Any]:
    """Deterministically evaluate a 2-4 crop sequence combining field suitability & transition pathology rules."""
    kb = kb or load_knowledge_base()
    if not sequence_crops or len(sequence_crops) < 2 or len(sequence_crops) > 4:
        raise ValueError("sequence_crops must contain 2 to 4 crop_ids.")
    for cid in sequence_crops:
        if cid not in kb.crops:
            raise ValueError(f"Unknown crop_id '{cid}' in sequence.")
    if slot_seasons is not None and len(slot_seasons) != len(sequence_crops):
        raise ValueError("slot_seasons length must match sequence_crops length.")

    sec_a = field_profile["section_a_farmer_provided"]
    ds = field_profile["section_b_extracted_geospatial"]["extracted_datasets"]
    water = sec_a["water"]
    soil = ds["soilgrids_v6"]
    terrain = ds["terrain_dem"]
    soc = _metric_val(soil, "soc_0_30cm")
    slope = _metric_val(terrain, "dem_slope_pct")
    start_year = sec_a["planning"]["start_year"]
    start_season = sec_a["planning"]["start_season"]

    # Step 1: Single-crop field evaluations per slot
    slot_evaluations: List[Dict[str, Any]] = []
    for idx, cid in enumerate(sequence_crops):
        s_season = (
            slot_seasons[idx]
            if slot_seasons is not None and slot_seasons[idx] is not None
            else (start_season if idx == 0 and slot_seasons is not None else _canonical_annual_season(kb.crops[cid]))
        )
        slot_evaluations.append(evaluate_crop_for_field(field_profile, cid, target_season=s_season, kb=kb))

    seq_evals: List[RuleEvaluation] = []
    cereals = set(kb.group_membership["CEREALS"])
    pulses = set(kb.group_membership["FOOD_LEGUMES"])
    solanaceae = set(kb.group_membership["SOLANACEAE"])

    # Perennial presence across any slot
    perennial_slots = [cid for cid in sequence_crops if not kb.crops[cid]["in_annual_rotation_scope"]]
    if perennial_slots:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_01_PERENNIAL_GUARD", "FAIL",
            f"Perennial orchard crop {perennial_slots} appears in annual sequence {list(sequence_crops)}.",
            {"perennial_crops_present": perennial_slots},
        ))
    else:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_01_PERENNIAL_GUARD", "PASS",
            "All sequence slots are annual cropping systems/periods.",
            {"sequence_crops": list(sequence_crops)},
        ))

    # Extract resolved recent historical timeline (year -> resolved crop_id)
    hist_raw = sec_a.get("crop_history")
    hist_map: Dict[int, Optional[str]] = {}
    if hist_raw:
        for h in hist_raw:
            yr = int(h["year"])
            hist_map[yr] = h.get("crop_id_resolved")

    prev_year_crop = hist_map.get(start_year - 1)
    prev2_year_crop = hist_map.get(start_year - 2)
    if hist_raw is None or (start_year - 1) not in hist_map or prev_year_crop is None:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_10_UNKNOWN_PREDECESSOR_GUARD", "UNKNOWN",
            f"Crop preceding start_year ({start_year - 1}) is missing or unresolved (crop_history={sec_a['input_completeness_flags']['crop_history']}); break safety for slot 0 ({sequence_crops[0]}) is unverified.",
            {"start_year": start_year, "prev_year_crop": prev_year_crop, "history_completeness": sec_a["input_completeness_flags"]["crop_history"]},
        ))
    else:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_10_UNKNOWN_PREDECESSOR_GUARD", "PASS",
            f"Predecessor history for {start_year - 1} resolved cleanly as '{prev_year_crop}'.",
            {"start_year": start_year, "prev_year_crop": prev_year_crop, "prev2_year_crop": prev2_year_crop},
        ))

    # Build chronological combined crop chain [known history..., seq...] for return-interval checks
    # Keep track of indices belonging to planned sequence
    combined: List[Tuple[str, str]] = []
    if prev2_year_crop is not None:
        combined.append((f"T-2({start_year - 2})", prev2_year_crop))
    if prev_year_crop is not None:
        combined.append((f"T-1({start_year - 1})", prev_year_crop))
    plan_start_idx = len(combined)
    for i, cid in enumerate(sequence_crops):
        combined.append((f"S{i + 1}", cid))

    # Check cereal streak length
    max_cereal_streak = 0
    cur_streak = 0
    for _, cid in combined:
        if cid in cereals:
            cur_streak += 1
            max_cereal_streak = max(max_cereal_streak, cur_streak)
        else:
            cur_streak = 0
    same_wheat_repeat = any(
        combined[i][1] in {"DURUM_WHEAT", "SOFT_WHEAT"} and combined[i][1] == combined[i - 1][1]
        for i in range(max(1, plan_start_idx), len(combined))
    )
    if max_cereal_streak >= 3:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_02_CEREAL_REPETITION", "FAIL",
            f"Sequence reaches {max_cereal_streak} consecutive cereal seasons (>=3 triggers severe take-all/Fusarium/wild oat hazard).",
            {"combined_timeline": combined, "max_cereal_streak": max_cereal_streak},
        ))
    elif max_cereal_streak == 2:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_02_CEREAL_REPETITION", "WARNING",
            f"Consecutive cereal repetition detected ({'same wheat species' if same_wheat_repeat else 'cross-cereal'}); insert legume/Vetch-Oat break next.",
            {"combined_timeline": combined, "max_cereal_streak": max_cereal_streak, "same_wheat_repeat": same_wheat_repeat},
        ))
    else:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_02_CEREAL_REPETITION", "PASS",
            "No consecutive cereal monoculture detected across planned sequence.",
            {"combined_timeline": combined},
        ))

    # Solanaceae 3-year return break check (TOMATO_IND / POTATO)
    sol_indices = [i for i, (_, cid) in enumerate(combined) if cid in solanaceae and i >= max(0, plan_start_idx - 2)]
    sol_in_plan = [i for i in sol_indices if i >= plan_start_idx]
    sol_violation = False
    for idx_b in sol_in_plan:
        for idx_a in sol_indices:
            if idx_a < idx_b and (idx_b - idx_a) < 3:
                sol_violation = True
    if sol_violation:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_03_SOLANACEAE_BREAK", "FAIL",
            "Solanaceae crops (Processing Tomato / Potato) occur within <3 years gap -> high Verticillium/Fusarium/nematode/Orobanche risk.",
            {"combined_timeline": combined},
        ))
    elif sol_in_plan:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_03_SOLANACEAE_BREAK", "PASS",
            "No repeated Solanaceae crop within evaluated 3-year horizon window (verify >=3-4 yr total field gap if T-2/T-3 unknown).",
            {"combined_timeline": combined},
        ))

    # Food Legumes return break check (FABA_BEAN, CHICKPEA_*, LENTIL)
    pulse_indices = [(i, combined[i][1]) for i in range(len(combined)) if combined[i][1] in pulses]
    same_pulse_or_orobanche = False
    cross_pulse_short = False
    for pos_b in range(len(pulse_indices)):
        ib, cb = pulse_indices[pos_b]
        if ib < plan_start_idx:
            continue
        for pos_a in range(pos_b):
            ia, ca = pulse_indices[pos_a]
            if (ib - ia) < 3:
                norm_a = "CHICKPEA" if "CHICKPEA" in ca else ca
                norm_b = "CHICKPEA" if "CHICKPEA" in cb else cb
                if norm_a == norm_b or ({ca, cb} == {"FABA_BEAN", "LENTIL"}):
                    same_pulse_or_orobanche = True
                else:
                    cross_pulse_short = True
    if same_pulse_or_orobanche:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_04_PULSE_BROOMRAPE_BREAK", "FAIL",
            "Repeated food legume or Faba Bean <-> Lentil within <3 years escalates Orobanche crenata / Ascochyta / Fusarium blight.",
            {"pulse_positions": pulse_indices},
        ))
    elif cross_pulse_short:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_04_PULSE_BROOMRAPE_BREAK", "WARNING",
            "Cross-legume placement within <3 years shares Sclerotinia/Fusarium carryover risk; extend gap to 3-4 years if possible.",
            {"pulse_positions": pulse_indices},
        ))
    elif any(i >= plan_start_idx for i, _ in pulse_indices):
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_04_PULSE_BROOMRAPE_BREAK", "PASS",
            "Food legume return interval clean inside observed timeline.",
            {"pulse_positions": pulse_indices},
        ))

    # Sunflower 3-year break
    sun_idx = [i for i, (_, cid) in enumerate(combined) if cid == "SUNFLOWER"]
    if any(sun_idx[k] >= plan_start_idx and (sun_idx[k] - sun_idx[k - 1]) < 3 for k in range(1, len(sun_idx))):
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_05_SUNFLOWER_BREAK", "FAIL",
            "Repeated Sunflower within <3 years violates Sclerotinia & Orobanche cumana break requirement.",
            {"sunflower_indices": sun_idx},
        ))

    # Vetch-Oat repeat & role
    vo_repeat = any(combined[i][1] == "VETCH_OAT" and combined[i - 1][1] == "VETCH_OAT" for i in range(max(1, plan_start_idx), len(combined)))
    if vo_repeat:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_06_VETCH_OAT_ROLE_AND_REPEAT", "WARNING",
            "Consecutive Vetch-Oat -> Vetch-Oat repeats Avena (oat) host; cut hay early and rotate cleanly to broadleaf or wheat.",
            {"combined_timeline": combined},
        ))
    elif "VETCH_OAT" in sequence_crops:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_06_VETCH_OAT_ROLE_AND_REPEAT", "PASS",
            "Vetch-Oat serves as validated Algerian fallow-replacement forage break (cut in Apr-May before grass-weed seed shed).",
            {"combined_timeline": combined},
        ))

    # Legume -> Cereal synergy
    legume_to_cereal = [
        (combined[i - 1][1], combined[i][1])
        for i in range(max(1, plan_start_idx), len(combined))
        if (combined[i - 1][1] in pulses or combined[i - 1][1] == "VETCH_OAT") and combined[i][1] in cereals
    ]
    if legume_to_cereal:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_07_LEGUME_CEREAL_SYNERGY", "PASS",
            f"Beneficial broadleaf/forage -> cereal transition(s) {legume_to_cereal}: interrupts grass weeds/root rot and provides organic N break benefit.",
            {"transitions": legume_to_cereal},
        ))

    # Bare fallow consecutive & SOC/erosion check
    consec_fallow = any(combined[i][1] == "BARE_FALLOW" and combined[i - 1][1] == "BARE_FALLOW" for i in range(max(1, plan_start_idx), len(combined)))
    if consec_fallow:
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_08_BARE_FALLOW_COVER", "FAIL",
            "Consecutive Bare Fallow -> Bare Fallow leaves soil uncropped for 2 consecutive seasons (erosion & SOC oxidation hazard).",
            {"combined_timeline": combined},
        ))
    elif "BARE_FALLOW" in sequence_crops and ((soc is not None and soc < 18.0) or slope is None):
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_08_BARE_FALLOW_COVER", "WARNING",
            f"Bare Fallow included with SOC={soc} g/kg and DEM slope={slope}: consider Vetch-Oat or food legume replacement to protect SOC & cover.",
            {"soc_0_30cm": soc, "dem_slope_pct": slope},
        ))

    # Water competition / Sunflower before rainfed cereal / Autumn Potato overlap
    irrig_active = (water.get("availability") in {"moderate", "abundant"}) and (water.get("source") != "rainfed")
    sun_before_cereal = any(
        combined[i - 1][1] == "SUNFLOWER" and combined[i][1] in cereals and not irrig_active
        for i in range(max(1, plan_start_idx), len(combined))
    )
    autumn_potato_overlap = False
    if slot_seasons is not None:
        for i in range(1, len(sequence_crops)):
            if sequence_crops[i - 1] == "POTATO" and slot_seasons[i - 1] == "Autumn" and slot_seasons[i] in {"Autumn", "Winter"}:
                autumn_potato_overlap = True

    if sun_before_cereal or autumn_potato_overlap:
        reasons = []
        if sun_before_cereal:
            reasons.append("Deep-taproot Sunflower before rainfed Winter Cereal risks deep subsoil moisture depletion if Autumn rains arrive late.")
        if autumn_potato_overlap:
            reasons.append("Autumn Potato (Nov-Dec harvest) overlaps tightly with Winter Cereal/Pulse sowing.")
        seq_evals.append(_make_seq_rule(
            kb, "SEQ_09_WATER_COMPETITION_AND_CALENDAR", "WARNING",
            " ".join(reasons),
            {"irrig_active": irrig_active, "sun_before_cereal": sun_before_cereal, "autumn_potato_overlap": autumn_potato_overlap},
        ))

    # Summarize combined feasibility across BOTH slot-level single-crop checks and sequence transition rules
    all_rules: List[Dict[str, Any]] = []
    for se in slot_evaluations:
        all_rules.extend(se["rule_evaluations"])
    all_rules.extend(r.to_dict() for r in seq_evals)

    hard_fails = (
        [f"{se['crop_id']}::{rid}" for se in slot_evaluations for rid in se["hard_fail_rules"]]
        + [r.rule_id for r in seq_evals if r.evidence_classification == "HARD_CONSTRAINT" and r.status == "FAIL"]
    )
    hard_unknowns = (
        [f"{se['crop_id']}::{rid}" for se in slot_evaluations for rid in se["hard_unknown_rules"]]
        + [r.rule_id for r in seq_evals if r.evidence_classification == "HARD_CONSTRAINT" and r.status == "UNKNOWN"]
    )
    any_slot_infeasible = any(not se["feasible"] for se in slot_evaluations)
    seq_soft_fails = [r.rule_id for r in seq_evals if r.evidence_classification != "HARD_CONSTRAINT" and r.status == "FAIL"]

    if hard_fails:
        feasible = False
        feasibility_status = "INFEASIBLE_HARD_CONSTRAINT"
    elif hard_unknowns:
        feasible = False
        feasibility_status = "UNVERIFIED_HARD_UNKNOWN"
    elif any_slot_infeasible or seq_soft_fails:
        feasible = False
        feasibility_status = "INFEASIBLE_CONSTRAINT"
    elif any(r["status"] in {"WARNING", "UNKNOWN"} for r in all_rules):
        feasible = True
        feasibility_status = "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS"
    else:
        feasible = True
        feasibility_status = "FEASIBLE_PASS"

    seq_status_counts = {s: sum(1 for r in seq_evals if r.status == s) for s in EVALUATION_STATUSES}
    return {
        "sequence": list(sequence_crops),
        "feasible": feasible,
        "feasibility_status": feasibility_status,
        "hard_fail_reasons": hard_fails,
        "hard_unknown_reasons": hard_unknowns,
        "sequence_status_counts": seq_status_counts,
        "quarantined_excluded": ["soilgrids_v6.nitrogen_0_30cm"],
        "slot_evaluations": slot_evaluations,
        "sequence_rule_evaluations": [r.to_dict() for r in seq_evals],
    }
