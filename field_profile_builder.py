"""Farmer Input Validation & 4-Part Field Profile Builder for Field Shift.

Combines:
A. Validated minimal farmer-provided data (USER_REPORTED)
B. Automatically extracted multi-scale geospatial context (field_geospatial_processor)
C. Attributed Phase E agronomic knowledge-base diagnostics (NO rotation optimization)
D. Internal data-quality provenance ledger & material UX follow-up prompts

Does NOT expose technical soil/weather/quality fields as farmer inputs and
never fabricates missing observations.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from field_geospatial_processor import extract_field_geospatial_context
from fieldshift_integration.config import PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "field_input_schema.json"
CROP_INVENTORY_CSV = PROJECT_ROOT / "docs" / "phaseE" / "crop_system_inventory.csv"
CONSTRAINTS_CSV = PROJECT_ROOT / "docs" / "phaseE" / "agronomic_constraints_framework.csv"

VALID_SEASONS = {"Winter", "Spring", "Summer", "Autumn"}
VALID_WATER_AVAIL = {"limited", "moderate", "abundant", "unknown"}
VALID_WATER_SRC = {"groundwater", "well", "reservoir", "river", "rainfed", "other"}
VALID_IRRIG_SYS = {"drip", "sprinkler", "surface", "none", "unknown"}

QUALITY_TAXONOMY = (
    "USER_REPORTED",
    "REMOTE_SENSING_DERIVED",
    "MODELED_SPATIAL_ESTIMATE",
    "INSTITUTIONAL_SOURCE",
    "REGIONAL_FALLBACK_ONLY",
    "UNKNOWN",
    "UNAVAILABLE_NOT_INTEGRATED",
    "UNVALIDATED_EXCLUDED",
)

FORBIDDEN_TECHNICAL_KEYS = {
    "soil_ph",
    "ph",
    "soil_organic_carbon",
    "soil_organic_matter",
    "soc",
    "clay",
    "clay_pct",
    "sand",
    "sand_pct",
    "silt",
    "silt_pct",
    "cec",
    "soil_type",
    "usda_texture",
    "nitrogen",
    "ndvi",
    "evi",
    "ndmi",
    "ndre",
    "rainfall_mm",
    "precipitation_mm",
    "temperature_c",
    "elevation_m",
    "slope_deg",
    "quality_status",
    "data_quality_metadata",
}

CROP_ALIASES: Dict[str, str] = {
    "durum wheat": "DURUM_WHEAT",
    "ble dur": "DURUM_WHEAT",
    "qamh": "DURUM_WHEAT",
    "wheat": "DURUM_WHEAT",
    "soft wheat": "SOFT_WHEAT",
    "bread wheat": "SOFT_WHEAT",
    "ble tendre": "SOFT_WHEAT",
    "barley": "BARLEY",
    "orge": "BARLEY",
    "chaïr": "BARLEY",
    "chayir": "BARLEY",
    "faba bean": "FABA_BEAN",
    "broad bean": "FABA_BEAN",
    "feve": "FABA_BEAN",
    "feverole": "FABA_BEAN",
    "foul": "FABA_BEAN",
    "winter chickpea": "CHICKPEA_WINTER",
    "pois chiche dhiver": "CHICKPEA_WINTER",
    "spring chickpea": "CHICKPEA_SPRING",
    "chickpea": "CHICKPEA_SPRING",
    "pois chiche": "CHICKPEA_SPRING",
    "hommos": "CHICKPEA_SPRING",
    "lentil": "LENTIL",
    "lentille": "LENTIL",
    "ades": "LENTIL",
    "vetch oat": "VETCH_OAT",
    "vetch-oat": "VETCH_OAT",
    "vesce avoine": "VETCH_OAT",
    "vesce-avoine": "VETCH_OAT",
    "processing tomato": "TOMATO_IND",
    "industrial tomato": "TOMATO_IND",
    "tomato": "TOMATO_IND",
    "tomate industrielle": "TOMATO_IND",
    "tomate": "TOMATO_IND",
    "tmatem": "TOMATO_IND",
    "potato": "POTATO",
    "pomme de terre": "POTATO",
    "batata": "POTATO",
    "sunflower": "SUNFLOWER",
    "tournesol": "SUNFLOWER",
    "olive": "OLIVE",
    "olivier": "OLIVE",
    "zitoune": "OLIVE",
    "fallow": "BARE_FALLOW",
    "bare fallow": "BARE_FALLOW",
    "jachere": "BARE_FALLOW",
    "bour": "BARE_FALLOW",
}


class FarmerInputValidationError(ValueError):
    """Raised when farmer payload violates the minimal input schema or supplies forbidden technical fields."""


@lru_cache(maxsize=1)
def load_input_schema() -> Dict[str, Any]:
    """Load authoritative field_input_schema.json."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_knowledge_base() -> Tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(CROP_INVENTORY_CSV), pd.read_csv(CONSTRAINTS_CSV)


def _normalize_text(text: str) -> str:
    cleaned = text.strip().lower().replace("é", "e").replace("è", "e").replace("ê", "e").replace("'", "")
    return re.sub(r"\s+", " ", cleaned)


def _check_forbidden_recursive(obj: Any, path: str = "root") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).strip().lower()
            if kl in FORBIDDEN_TECHNICAL_KEYS:
                raise FarmerInputValidationError(
                    f"Forbidden technical field '{k}' at {path}: farmers must NOT supply technical soil, weather, remote-sensing, or quality fields."
                )
            _check_forbidden_recursive(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _check_forbidden_recursive(item, f"{path}[{idx}]")


def _classify_list_input(present: bool, val: Any, field_name: str) -> Tuple[Optional[List[str]], str]:
    """Preserve null/omitted ('NOT_PROVIDED') strictly distinct from [] ('EXPLICITLY_CONFIRMED_EMPTY')."""
    if not present or val is None:
        return None, "NOT_PROVIDED"
    if not isinstance(val, list):
        raise FarmerInputValidationError(f"'{field_name}' must be an array or null.")
    cleaned: List[str] = []
    for item in val:
        if not isinstance(item, str) or not item.strip():
            raise FarmerInputValidationError(f"Each element of '{field_name}' must be a non-empty string.")
        cleaned.append(item.strip())
    if len(cleaned) == 0:
        return [], "EXPLICITLY_CONFIRMED_EMPTY"
    return cleaned, "PROVIDED"


def _classify_weight_input(present: bool, val: Any, key_name: str) -> Tuple[Optional[float], str]:
    """Validate optional preference weights in [0.0, 1.0], keeping None distinct from 0.0."""
    if not present or val is None:
        return None, "NOT_PROVIDED"
    if not isinstance(val, (int, float)) or isinstance(val, bool) or not (0.0 <= float(val) <= 1.0):
        raise FarmerInputValidationError(f"Preference weight '{key_name}' must be in [0.0, 1.0] or null.")
    return float(val), "PROVIDED"


def validate_farmer_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strictly validate farmer input against field_input_schema.json rules and normalize optional fields."""
    if not isinstance(payload, dict):
        raise FarmerInputValidationError("Input payload must be a JSON object.")

    _check_forbidden_recursive(payload)
    required_top = {"field", "water", "planning"}
    optional_top = {"crop_history", "preferences"}
    extra_top = set(payload.keys()) - (required_top | optional_top)
    missing_top = required_top - set(payload.keys())
    if extra_top:
        raise FarmerInputValidationError(f"Unsupported top-level fields not permitted in minimal contract: {sorted(extra_top)}")
    if missing_top:
        raise FarmerInputValidationError(f"Missing required farmer input sections: {sorted(missing_top)}")

    # 1. Field
    fld = payload["field"]
    if not isinstance(fld, dict):
        raise FarmerInputValidationError("'field' must be an object.")
    allowed_fld = {"field_id", "field_name", "geometry", "geometry_crs"}
    if set(fld.keys()) - allowed_fld:
        raise FarmerInputValidationError(f"Unsupported keys in 'field': {sorted(set(fld.keys()) - allowed_fld)}")
    field_id = str(fld.get("field_id", "")).strip()
    if not field_id:
        raise FarmerInputValidationError("'field.field_id' is required and must be non-empty.")
    if "geometry" not in fld or not isinstance(fld["geometry"], dict):
        raise FarmerInputValidationError("'field.geometry' GeoJSON Polygon is required.")

    # 2. Water
    wat = payload["water"]
    if not isinstance(wat, dict):
        raise FarmerInputValidationError("'water' must be an object.")
    if set(wat.keys()) != {"availability", "source", "irrigation_system"}:
        raise FarmerInputValidationError("'water' must contain exactly availability, source, irrigation_system.")
    if wat["availability"] not in VALID_WATER_AVAIL:
        raise FarmerInputValidationError(f"Invalid water.availability: {wat['availability']}")
    if wat["source"] not in VALID_WATER_SRC:
        raise FarmerInputValidationError(f"Invalid water.source: {wat['source']}")
    if wat["irrigation_system"] not in VALID_IRRIG_SYS:
        raise FarmerInputValidationError(f"Invalid water.irrigation_system: {wat['irrigation_system']}")

    # 3. Crop History (optional; None/omitted preserved distinctly from [])
    crop_inv, _ = _load_knowledge_base()
    known_crop_ids: Set[str] = set(crop_inv["crop_id"].astype(str))
    norm_history: Optional[List[Dict[str, Any]]]
    if "crop_history" not in payload or payload["crop_history"] is None:
        norm_history = None
        history_completeness = "NOT_PROVIDED"
    else:
        hist = payload["crop_history"]
        if not isinstance(hist, list):
            raise FarmerInputValidationError("'crop_history' must be a list or null.")
        allowed_h = {"season", "year", "planting_month", "crop_id", "crop_name_raw", "yield_tons_per_hectare", "notes"}
        norm_history = []
        for idx, entry in enumerate(hist):
            if not isinstance(entry, dict):
                raise FarmerInputValidationError(f"crop_history[{idx}] must be an object.")
            if set(entry.keys()) - allowed_h:
                raise FarmerInputValidationError(f"Unsupported keys in crop_history[{idx}]: {sorted(set(entry.keys()) - allowed_h)}")
            if entry.get("season") not in VALID_SEASONS:
                raise FarmerInputValidationError(f"Invalid season in crop_history[{idx}]: {entry.get('season')}")
            yr = entry.get("year")
            if not isinstance(yr, int) or isinstance(yr, bool) or not (2010 <= yr <= 2035):
                raise FarmerInputValidationError(f"Invalid year in crop_history[{idx}]: {yr}")
            raw_name = str(entry.get("crop_name_raw", "")).strip()
            if not raw_name:
                raise FarmerInputValidationError(f"crop_history[{idx}].crop_name_raw is required.")
            pm = entry.get("planting_month")
            if pm is not None and (not isinstance(pm, int) or isinstance(pm, bool) or not (1 <= pm <= 12)):
                raise FarmerInputValidationError(f"Invalid planting_month in crop_history[{idx}]: {pm}")
            y_tpha = entry.get("yield_tons_per_hectare")
            if y_tpha is not None and (not isinstance(y_tpha, (int, float)) or isinstance(y_tpha, bool) or float(y_tpha) < 0.0):
                raise FarmerInputValidationError(f"Invalid yield_tons_per_hectare in crop_history[{idx}]: {y_tpha}")

            provided_cid = entry.get("crop_id")
            if provided_cid and provided_cid in known_crop_ids:
                resolved_cid, norm_status = provided_cid, "USER_SPECIFIED_KNOWN_ID"
            else:
                alias_hit = CROP_ALIASES.get(_normalize_text(raw_name))
                if alias_hit:
                    resolved_cid, norm_status = alias_hit, "NORMALIZED_FROM_RAW_NAME"
                else:
                    resolved_cid, norm_status = None, "UNMAPPED_CROP_NAME_UNKNOWN_ID"

            norm_history.append({
                "season": entry["season"],
                "year": yr,
                "planting_month": pm,
                "crop_id_input": provided_cid,
                "crop_id_resolved": resolved_cid,
                "crop_name_raw": raw_name,
                "normalization_status": norm_status,
                "yield_tons_per_hectare": float(y_tpha) if y_tpha is not None else None,
                "notes": entry.get("notes"),
                "provenance": "USER_REPORTED",
            })
        history_completeness = "EXPLICITLY_CONFIRMED_EMPTY" if len(norm_history) == 0 else "PROVIDED"

    # 4. Planning
    pln = payload["planning"]
    if not isinstance(pln, dict):
        raise FarmerInputValidationError("'planning' must be an object.")
    if set(pln.keys()) - {"start_season", "start_year", "horizon_seasons", "planting_month"}:
        raise FarmerInputValidationError("Unsupported keys in 'planning'.")
    if pln.get("start_season") not in VALID_SEASONS:
        raise FarmerInputValidationError(f"Invalid planning.start_season: {pln.get('start_season')}")
    sy = pln.get("start_year")
    if not isinstance(sy, int) or isinstance(sy, bool) or not (2024 <= sy <= 2035):
        raise FarmerInputValidationError(f"Invalid planning.start_year: {sy}")
    hz = pln.get("horizon_seasons")
    if not isinstance(hz, int) or isinstance(hz, bool) or not (2 <= hz <= 4):
        raise FarmerInputValidationError("planning.horizon_seasons must be an integer between 2 and 4.")
    ppm = pln.get("planting_month")
    if ppm is not None and (not isinstance(ppm, int) or isinstance(ppm, bool) or not (1 <= ppm <= 12)):
        raise FarmerInputValidationError(f"Invalid planning.planting_month: {ppm}")

    # 5. Preferences (optional; omitted/null subfields preserved distinctly from [])
    list_pref_keys = ("target_crop_ids", "excluded_crop_ids", "equipment_constraints")
    weight_pref_keys = (
        "water_saving_weight",
        "soil_improvement_weight",
        "income_weight",
        "risk_reduction_weight",
        "forage_value_weight",
    )
    allowed_pref = set(list_pref_keys) | set(weight_pref_keys)
    completeness_flags: Dict[str, str] = {"crop_history": history_completeness}

    norm_pref: Optional[Dict[str, Any]]
    if "preferences" not in payload or payload["preferences"] is None:
        norm_pref = None
        completeness_flags["preferences_block"] = "NOT_PROVIDED"
        for k in list_pref_keys + weight_pref_keys:
            completeness_flags[k] = "NOT_PROVIDED"
    else:
        pref = payload["preferences"]
        if not isinstance(pref, dict):
            raise FarmerInputValidationError("'preferences' must be an object or null.")
        extra_p = set(pref.keys()) - allowed_pref
        if extra_p:
            raise FarmerInputValidationError(f"Unsupported keys in 'preferences': {sorted(extra_p)}")
        norm_pref = {}
        completeness_flags["preferences_block"] = "EXPLICITLY_CONFIRMED_EMPTY" if len(pref) == 0 else "PROVIDED"
        for lk in list_pref_keys:
            val, status = _classify_list_input(lk in pref, pref.get(lk), f"preferences.{lk}")
            norm_pref[lk] = val
            completeness_flags[lk] = status
        for wk in weight_pref_keys:
            val, status = _classify_weight_input(wk in pref, pref.get(wk), wk)
            norm_pref[wk] = val
            completeness_flags[wk] = status
        norm_pref["provenance"] = "USER_REPORTED"

    return {
        "field": {
            "field_id": field_id,
            "field_name": fld.get("field_name"),
            "geometry": fld["geometry"],
            "geometry_crs": fld.get("geometry_crs", "EPSG:4326"),
            "provenance": "USER_REPORTED",
        },
        "water": {**wat, "provenance": "USER_REPORTED"},
        "crop_history": norm_history,
        "planning": {
            "start_season": pln["start_season"],
            "start_year": sy,
            "horizon_seasons": hz,
            "planting_month": ppm,
            "provenance": "USER_REPORTED",
        },
        "preferences": norm_pref,
        "input_completeness_flags": completeness_flags,
    }


def _build_agronomic_context(
    farmer_data: Dict[str, Any],
    geospatial_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach descriptive Phase E agronomic diagnostics without running rotation optimization."""
    crop_inv, constraints_df = _load_knowledge_base()
    ds = geospatial_ctx["extracted_datasets"]
    soil = ds["soilgrids_v6"]
    gpm = ds["gpm_and_smap"]
    npw = ds["nasa_power"]

    clay_val = soil.get("clay_0_30cm", {}).get("value")
    ph_val = soil.get("ph_0_30cm", {}).get("value")
    soc_val = soil.get("soc_0_30cm", {}).get("value")
    cec_val = soil.get("cec_0_30cm", {}).get("value")
    gpm_ann = gpm.get("gpm_annual_precip_2016_2025_mean_mm", {}).get("value")
    np_ann = npw.get("nasa_power_annual_precip_2016_2025_mean_mm", {}).get("value")

    diagnostics: List[Dict[str, Any]] = []
    if clay_val is not None and clay_val >= 32.0:
        diagnostics.append({
            "constraint_id": "CON_01_TEXTURE",
            "status": "ADVISORY_CAUTION",
            "finding": f"Extracted modeled Clay (0-30 cm) = {clay_val}% ({soil.get('usda_texture_0_5cm', {}).get('value')}).",
            "agronomic_implication": "Moderate-to-heavy Clay Loam supports cereals/faba bean well, but creates narrow winter tillage windows and raises waterlogging caution for Lentil and compaction risk for Potato (Sys et al. 1993).",
            "source_rule": "agronomic_constraints_framework.csv::CON_01_TEXTURE",
        })
    if ph_val is not None:
        diagnostics.append({
            "constraint_id": "CON_02_PH",
            "status": "POTATO_SCAB_CAUTION" if ph_val >= 6.8 else "OPTIMAL_CEREAL_PULSE_PH",
            "finding": f"Extracted modeled pH (0-30 cm) = {ph_val}.",
            "agronomic_implication": "Well-suited for Wheat, Barley, Faba bean, Chickpea, and Lentil (6.0-8.0). Neutral-slightly alkaline pH increases common scab hazard for Potato above pH 6.5 (FAO EcoCrop).",
            "source_rule": "agronomic_constraints_framework.csv::CON_02_PH",
        })
    if soc_val is not None:
        diagnostics.append({
            "constraint_id": "CON_03_SOC",
            "status": "DEPLETED_SOC_PRIORITY" if soc_val < 18.0 else "MODERATE_SOC",
            "finding": f"Extracted modeled SOC (0-30 cm) = {soc_val} g/kg.",
            "agronomic_implication": (
                "Arable SOC below 18 g/kg weakens moisture retention and N mineralization; legume or vetch-oat break crops carry high conservation value (ITGC Algeria)."
                if soc_val < 18.0
                else "Moderate topsoil SOC baseline; maintain crop residues or legume intervals."
            ),
            "source_rule": "agronomic_constraints_framework.csv::CON_03_SOC",
        })
    if cec_val is not None:
        diagnostics.append({
            "constraint_id": "CON_04_CEC",
            "status": "ADEQUATE_BUFFERING",
            "finding": f"Extracted modeled CEC (0-30 cm) = {cec_val} cmol(c)/kg.",
            "agronomic_implication": "Nutrient exchange buffering exceeds 16 cmol(c)/kg; no inherent CEC deficit signaled, though lab P/K/ECe remain unmeasured.",
            "source_rule": "agronomic_constraints_framework.csv::CON_04_CEC",
        })
    if gpm_ann is not None and np_ann is not None:
        gap = round(float(np_ann) - float(gpm_ann), 1)
        diagnostics.append({
            "constraint_id": "CON_06_PRECIP",
            "status": "CROSS_PRODUCT_SPREAD_NOTE",
            "finding": f"Regional annual precipitation: GPM (11 km) = {gpm_ann} mm/yr vs NASA POWER (~55 km) = {np_ann} mm/yr (delta = {gap:+.1f} mm/yr).",
            "agronomic_implication": "Future suitability & balance checks must preserve both conservative (GPM) and upper (NASA POWER) bounds due to missing local rain gauges.",
            "source_rule": "agronomic_constraints_framework.csv::CON_06_PRECIP",
        })

    # Target/excluded crop knowledge cards (strictly descriptive lookup, zero scoring)
    inv_map = crop_inv.set_index("crop_id").to_dict(orient="index")
    pref_obj = farmer_data.get("preferences") or {}
    target_ids = pref_obj.get("target_crop_ids") or []
    target_profiles = {
        cid: {
            "common_name": inv_map[cid]["common_name"],
            "water_regime": inv_map[cid]["water_regime"],
            "planting_window": inv_map[cid]["planting_window"],
            "harvest_window": inv_map[cid]["harvest_window"],
            "guelma_evidence_status": inv_map[cid]["guelma_evidence_status"],
        }
        for cid in target_ids
        if cid in inv_map
    }

    hist_entries = farmer_data.get("crop_history")
    hist_groups: Optional[List[Dict[str, Any]]]
    if hist_entries is None:
        hist_groups = None
    else:
        hist_groups = [
            {
                "year": h["year"],
                "season": h["season"],
                "crop_id_resolved": h["crop_id_resolved"],
                "crop_group": inv_map[h["crop_id_resolved"]]["crop_group"] if h["crop_id_resolved"] in inv_map else None,
            }
            for h in hist_entries
        ]

    return {
        "knowledge_base_sources": [str(CROP_INVENTORY_CSV.name), str(CONSTRAINTS_CSV.name)],
        "optimization_executed": False,
        "descriptive_field_diagnostics": diagnostics,
        "target_crop_kb_profiles": target_profiles,
        "resolved_history_summary": hist_groups,
        "relevant_constraint_domains_count": int(len(constraints_df)),
    }


def _build_quality_and_clarifications(
    farmer_data: Dict[str, Any],
    geospatial_ctx: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Generate internal data-quality accounting and strictly material farmer follow-up prompts."""
    counts: Dict[str, int] = {q: 0 for q in QUALITY_TAXONOMY}
    counts["USER_REPORTED"] += (
        3
        + (1 if farmer_data["crop_history"] is not None else 0)
        + (1 if farmer_data["preferences"] is not None else 0)
    )

    for domain_dict in geospatial_ctx["extracted_datasets"].values():
        for metric in domain_dict.values():
            qs = metric.get("quality_status", "UNKNOWN")
            counts[qs] = counts.get(qs, 0) + 1

    follow_ups: List[Dict[str, Any]] = []
    wat = farmer_data["water"]
    hist = farmer_data.get("crop_history") or []
    pref_obj = farmer_data.get("preferences") or {}
    soil = geospatial_ctx["extracted_datasets"]["soilgrids_v6"]
    clay_val = soil.get("clay_0_30cm", {}).get("value")
    dem_status = geospatial_ctx["extracted_datasets"]["terrain_dem"]["dem_slope_pct"]["quality_status"]

    # Materiality rule 1: Water uncertainty impacts Rainfed vs Irrigated crop gating
    if wat["availability"] == "unknown" or (wat["source"] != "rainfed" and wat["irrigation_system"] == "unknown"):
        follow_ups.append({
            "question_id": "Q_WATER_MATERIAL",
            "material_reason": "Irrigation capacity determines whether summer crops (such as processing tomato) are feasible or excluded.",
            "farmer_prompt": "During spring and summer, can you reliably irrigate this plot (and if so, via drip, sprinkler, or surface)?",
            "fallback_if_unanswered": "Run dual scenarios (Rainfed-safe vs. Supplemental-irrigated) and disclose uncertainty clearly.",
        })

    # Materiality rule 2: Missing recent history affects cereal/pulse/Solanaceae disease intervals
    start_yr = farmer_data["planning"]["start_year"]
    recent_yrs = {h["year"] for h in hist}
    if farmer_data["crop_history"] is None or not hist or (start_yr - 1) not in recent_yrs:
        follow_ups.append({
            "question_id": "Q_LAST_CROP_MATERIAL",
            "material_reason": "Previous 1-2 crops govern cereal weed/disease carryover and legume/Solanaceae 3-4 year break rules.",
            "farmer_prompt": f"What crop (or fallow) was planted on this field in {start_yr - 1} (and {start_yr - 2} if remembered)?",
            "fallback_if_unanswered": "Apply conservative disease-break warnings without assuming safe break history.",
        })

    # Materiality rule 3: Heavy clay + absent DEM + drainage-sensitive crops -> simple puddle check (NEVER ask for % slope!)
    sensitive_targets = set(pref_obj.get("target_crop_ids") or []) & {"LENTIL", "CHICKPEA_WINTER", "CHICKPEA_SPRING", "POTATO"}
    if dem_status == "UNAVAILABLE_NOT_INTEGRATED" and clay_val is not None and clay_val >= 32.0 and sensitive_targets:
        follow_ups.append({
            "question_id": "Q_DRAINAGE_QUALITATIVE",
            "material_reason": "Topographic DEM is not yet integrated locally and modeled clay exceeds 32%; standing water strongly affects lentil/chickpea/potato.",
            "farmer_prompt": "After heavy winter rains, does water stay standing/puddled on this field for more than 2 days?",
            "fallback_if_unanswered": "Keep waterlogging-sensitive legume caution visible in the analysis report.",
        })

    # Materiality rule 4: Irrigated field without local ECe salinity lab layer
    if wat["source"] in {"reservoir", "river", "well", "groundwater"} and wat["irrigation_system"] != "none":
        follow_ups.append({
            "question_id": "Q_IRRIGATION_SALINITY_SIGN",
            "material_reason": "Regional Seybouse studies report secondary salinization pockets, and no spatial ECe salinity layer exists on disk.",
            "farmer_prompt": "Have you noticed white salt crusts on dry ridges or leaf-edge burn when irrigating this field?",
            "fallback_if_unanswered": "Display standard Seybouse water/soil salinity check reminder prior to salt-sensitive vegetable planting.",
        })

    quality_ledger = {
        "quality_status_counts": counts,
        "input_completeness_flags": farmer_data["input_completeness_flags"],
        "soilgrids_vs_laboratory_distinction": (
            "All soil values (pH, SOC, Clay, Sand, Silt, CEC) come from global 250 m SoilGrids 2.0 V6 spatial predictions "
            "(MODELED_SPATIAL_ESTIMATE). They are NOT laboratory soil sample measurements, and SoilGrids Nitrogen is quarantined."
        ),
        "regional_climate_vs_field_distinction": (
            "GPM (~11 km), SMAP (~11 km), and NASA POWER (~55-111 km) are regional macro observations, NOT on-farm weather stations. "
            "Multi-year 10 m/20 m Sentinel-2 rasters remain deferred; Wilaya monthly statistics serve solely as regional fallback context."
        ),
        "missing_values_policy": (
            "Missing measurements (e.g., DEM elevation/slope, unobserved crop yields, missing SoilGrids N) and omitted/null optional farmer fields "
            "are explicitly preserved as null ('NOT_PROVIDED') and never collapsed into [] ('EXPLICITLY_CONFIRMED_EMPTY') or 0."
        ),
    }
    return quality_ledger, follow_ups


def build_field_profile(farmer_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build complete validated 4-part Field Profile from minimal farmer input."""
    farmer_data = validate_farmer_input(farmer_payload)
    geom_cfg = farmer_data["field"]
    geo_ctx = extract_field_geospatial_context(geom_cfg["geometry"], geometry_crs=geom_cfg.get("geometry_crs", "EPSG:4326"))
    agronomic_ctx = _build_agronomic_context(farmer_data, geo_ctx)
    quality_ledger, follow_ups = _build_quality_and_clarifications(farmer_data, geo_ctx)

    return {
        "profile_schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "section_a_farmer_provided": farmer_data,
        "section_b_extracted_geospatial": geo_ctx,
        "section_c_agronomic_knowledge_base": agronomic_ctx,
        "section_d_quality_and_uncertainty": {
            **quality_ledger,
            "conditional_follow_up_questions": follow_ups,
        },
    }


def render_field_analysis_report_md(profile: Dict[str, Any]) -> str:
    """Render an accessible Generated Field Analysis Report presenting extracted soil/climate facts to farmers/advisors."""
    sec_a = profile["section_a_farmer_provided"]
    sec_b = profile["section_b_extracted_geospatial"]
    sec_c = profile["section_c_agronomic_knowledge_base"]
    sec_d = profile["section_d_quality_and_uncertainty"]

    sv = sec_b["spatial_validation"]
    comm = sv["primary_commune"] or {"name_2": "Unknown", "overlap_pct": 0.0}
    ds = sec_b["extracted_datasets"]
    soil = ds["soilgrids_v6"]
    cf = ds["crop_frequency"]["crop_frequency_2021_2025"]
    s2_mar = ds["sentinel2"]["s2_2024_03_ndvi_10m"]
    gpm_ann = ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]
    np_ann = ds["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"]
    np_t2m = ds["nasa_power"]["nasa_power_t2m_2016_2025_mean_c"]
    smap_sp = ds["gpm_and_smap"]["smap_rootzone_sm_spring_2016_2025_mean"]

    lines = [
        f"# Field Analysis Report — {sec_a['field'].get('field_name') or sec_a['field']['field_id']}",
        "",
        f"**Field ID:** `{sec_a['field']['field_id']}` | **Mapped Area:** `{sv['area_ha']:.2f} ha` | **Primary Commune:** `{comm['name_2']}` (`{comm['overlap_pct']:.1f}%` overlap)",
        f"**Water Declared (`USER_REPORTED`):** Availability=`{sec_a['water']['availability']}`, Source=`{sec_a['water']['source']}`, System=`{sec_a['water']['irrigation_system']}`",
        "",
        "## 1. Automatically Estimated Soil & Cropland Snapshot *(No Farmer Soil Entry Needed)*",
        f"- **Dominant Texture (`SoilGrids 250 m`, modeled):** `{soil.get('usda_texture_0_5cm', {}).get('value')}` (`Clay 0–30 cm = {soil['clay_0_30cm']['value']}%`, `Sand = {soil['sand_0_30cm']['value']}%`, `Silt = {soil['silt_0_30cm']['value']}%`; `valid_px = {soil['clay_0_30cm']['valid_pixel_count']}`, `cov = {soil['clay_0_30cm']['polygon_coverage_pct']}%`)",
        f"- **Soil Reaction & Fertility Proxies (`MODELED_SPATIAL_ESTIMATE`):** `pH = {soil['ph_0_30cm']['value']}`, `SOC = {soil['soc_0_30cm']['value']} g/kg`, `CEC = {soil['cec_0_30cm']['value']} cmol(c)/kg` *(SoilGrids Nitrogen intentionally excluded; not a lab test)*",
        f"- **Recent Cropland Activity (`ESA 10 m, 2021–2025`):** Mean Crop Frequency = `{cf['value']}` (`valid_px = {cf['valid_pixel_count']}`, `cov = {cf['polygon_coverage_pct']}%`)",
        f"- **Vegetation Snapshot (`Sentinel-2 10 m, 2024-03`):** Spring NDVI = `{s2_mar['value']}` (`valid_px = {s2_mar['valid_pixel_count']}`)",
        "",
        "## 2. Regional Climate & Moisture Envelope *(Macro Context — Not Field Station)*",
        f"- **Annual Rainfall Range:** `{gpm_ann['value']} mm/yr` (`GPM 11 km`) to `{np_ann['value']} mm/yr` (`NASA POWER ~55 km`)",
        f"- **Mean Annual Temperature (`NASA POWER`):** `{np_t2m['value']} °C`",
        f"- **Spring Root-Zone Moisture (`SMAP L4 11 km`):** `{smap_sp['value']} m³/m³`",
        f"- **Terrain (`DEM`):** `{ds['terrain_dem']['dem_elevation_m']['value']}` (`{ds['terrain_dem']['dem_elevation_m']['quality_status']}`)",
        "",
        "## 3. Agronomic Notes & Data Limitations",
    ]
    for diag in sec_c["descriptive_field_diagnostics"]:
        lines.append(f"- **[{diag['constraint_id']} / {diag['status']}]** {diag['finding']} — {diag['agronomic_implication']}")

    if sec_d["conditional_follow_up_questions"]:
        lines.extend(["", "## 4. Optional Material Clarifications (Asked Only Where Helpful)"])
        for q in sec_d["conditional_follow_up_questions"]:
            lines.append(f"- **{q['farmer_prompt']}** *(Why: {q['material_reason']} Fallback: {q['fallback_if_unanswered']})*")

    lines.extend([
        "",
        f"> **Provenance Notice:** {sec_d['soilgrids_vs_laboratory_distinction']} {sec_d['regional_climate_vs_field_distinction']}",
    ])
    return "\n".join(lines)
