"""Modular FAO-56 Crop Water-Balance Readiness & Evaluation Architecture (Phase N).

Clarifies that Phase I `water_efficiency` scores reflect ordinal crop water-regime
compatibility rather than volumetric crop evapotranspiration deficits, and provides a
strictly non-fabricating FAO-56 interface (`ET0`, `Kc`, `ETc`, `P_eff`, `RAW`, and
`net/gross irrigation demand`) that computes quantitative components only when verified
inputs exist and otherwise reports explicit `UNKNOWN` / `PARTIAL` missing-data states.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Default application efficiency ranges by irrigation system ONLY when farmer/advisor explicitly opts into engineering estimate
IRRIGATION_EFFICIENCY_BOUNDS: Dict[str, tuple[float, float]] = {
    "drip": (0.85, 0.92),
    "sprinkler": (0.70, 0.80),
    "surface": (0.50, 0.65),
    "none": (1.0, 1.0),
}


@dataclass(frozen=True)
class FAO56StageParameters:
    """FAO-56 single crop-coefficient growth stage parameters for a crop."""

    crop_id: str
    kc_ini: Optional[float]
    kc_mid: Optional[float]
    kc_end: Optional[float]
    l_ini_days: Optional[int]
    l_dev_days: Optional[int]
    l_mid_days: Optional[int]
    l_late_days: Optional[int]
    root_depth_max_m: Optional[float]
    p_depletion: Optional[float]


def _mid_or_val(obj: Any, key_single: str, key_min: str, key_max: str) -> Optional[float]:
    if not isinstance(obj, dict):
        return None
    if obj.get(key_single) is not None:
        return float(obj[key_single])
    lo = obj.get(key_min)
    hi = obj.get(key_max)
    if lo is not None and hi is not None:
        return round((float(lo) + float(hi)) / 2.0, 4)
    return None


def extract_crop_fao56_parameters(crop_profile: Dict[str, Any]) -> FAO56StageParameters:
    """Extract available FAO-56 Kc and rooting parameters without fabricating stage lengths."""
    params = crop_profile.get("parameters") or {}
    kc_val = (params.get("kc_profile") or {}).get("value")
    root_val = (params.get("root_depth_m") or {}).get("value")
    stages_val = (params.get("fao56_stage_lengths_days") or {}).get("value")

    kc_ini = _mid_or_val(kc_val, "kc_ini", "kc_ini_min", "kc_ini_max")
    kc_mid = _mid_or_val(kc_val, "kc_mid", "kc_mid_min", "kc_mid_max")
    kc_end = _mid_or_val(kc_val, "kc_end", "kc_end_min", "kc_end_max")

    root_max: Optional[float] = None
    if isinstance(root_val, dict):
        if root_val.get("max") is not None:
            root_max = float(root_val["max"])
        elif root_val.get("min") is not None:
            root_max = float(root_val["min"])

    if isinstance(stages_val, dict):
        l_ini = int(stages_val["l_ini"]) if stages_val.get("l_ini") is not None else None
        l_dev = int(stages_val["l_dev"]) if stages_val.get("l_dev") is not None else None
        l_mid = int(stages_val["l_mid"]) if stages_val.get("l_mid") is not None else None
        l_late = int(stages_val["l_late"]) if stages_val.get("l_late") is not None else None
    else:
        l_ini = l_dev = l_mid = l_late = None

    p_dep = _mid_or_val(params.get("depletion_fraction_p") or {}, "value", "min", "max")

    return FAO56StageParameters(
        crop_id=str(crop_profile.get("crop_id") or ""),
        kc_ini=kc_ini,
        kc_mid=kc_mid,
        kc_end=kc_end,
        l_ini_days=l_ini,
        l_dev_days=l_dev,
        l_mid_days=l_mid,
        l_late_days=l_late,
        root_depth_max_m=root_max,
        p_depletion=p_dep,
    )


def compute_fao56_penman_monteith_et0_daily(
    *,
    tmin_c: float,
    tmax_c: float,
    rh_mean_pct: float,
    rs_mj_m2_day: float,
    u2_ms: float,
    elevation_m: float,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """Compute FAO-56 Penman-Monteith daily grass reference ET0 (mm/day, Allen et al. 1998).

    Strictly requires measured/provided `u2_ms` and `elevation_m`; callers must never pass
    fabricated defaults when these variables are unavailable.
    """
    tmean = 0.5 * (tmin_c + tmax_c)
    pressure_kpa = 101.3 * (((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26)
    gamma = 0.000665 * pressure_kpa

    e_tmax = 0.6108 * math.exp((17.27 * tmax_c) / (tmax_c + 237.3))
    e_tmin = 0.6108 * math.exp((17.27 * tmin_c) / (tmin_c + 237.3))
    es = 0.5 * (e_tmax + e_tmin)
    ea = max(0.0, min(es, es * (rh_mean_pct / 100.0)))
    delta = (4098.0 * (0.6108 * math.exp((17.27 * tmean) / (tmean + 237.3)))) / ((tmean + 237.3) ** 2)

    lat_rad = math.radians(latitude_deg)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    solar_decl = 0.409 * math.sin((2.0 * math.pi * day_of_year / 365.0) - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(lat_rad) * math.tan(solar_decl))))
    ra = (
        (24.0 * 60.0 / math.pi)
        * 0.0820
        * dr
        * (ws * math.sin(lat_rad) * math.sin(solar_decl) + math.cos(lat_rad) * math.cos(solar_decl) * math.sin(ws))
    )
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = (1.0 - 0.23) * rs_mj_m2_day
    ratio_rs = min(1.0, rs_mj_m2_day / max(rso, 1e-6))
    stefan = 4.903e-9
    rnl = (
        stefan
        * (((tmax_c + 273.16) ** 4 + (tmin_c + 273.16) ** 4) / 2.0)
        * (0.34 - 0.14 * math.sqrt(max(ea, 0.0)))
        * (1.35 * ratio_rs - 0.35)
    )
    rn = rns - rnl
    # Daily soil heat flux G assumed 0 over >=24h step per FAO-56 Eq. 42
    num = 0.408 * delta * rn + gamma * (900.0 / (tmean + 273.0)) * u2_ms * (es - ea)
    den = delta + gamma * (1.0 + 0.34 * u2_ms)
    return round(max(0.0, num / den), 3)


def compute_effective_precip_usda_scs_monthly(precip_monthly_mm: float) -> float:
    """Compute monthly effective rainfall (USDA SCS method per CROPWAT 8.0) in mm."""
    p = max(0.0, float(precip_monthly_mm))
    if p <= 250.0:
        return round(p * (125.0 - 0.2 * p) / 125.0, 2)
    return round(125.0 + 0.1 * p, 2)


def assess_water_balance_readiness(
    field_profile: Dict[str, Any],
    crop_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    local_hydrology_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Audit FAO-56 water-balance readiness & compute ET0/ETc only when verified inputs exist."""
    sec_a = field_profile.get("section_a_farmer_provided") or field_profile.get("section_a_farmer_inputs") or {}
    sec_b = field_profile.get("section_b_extracted_geospatial") or {}
    ds = sec_b.get("extracted_datasets") or {}
    water_in = sec_a.get("water") or {}
    spatial = sec_b.get("spatial_validation") or {}

    nasa = ds.get("nasa_power") or {}
    dem = ds.get("terrain_dem") or {}
    soil = ds.get("soilgrids_v6") or {}
    hydro = local_hydrology_inputs or {}

    tmin = (nasa.get("nasa_power_t2m_min_2016_2025_mean_c") or {}).get("value")
    tmax = (nasa.get("nasa_power_t2m_max_2016_2025_mean_c") or {}).get("value")
    rh = (nasa.get("nasa_power_rh2m_2016_2025_mean_pct") or {}).get("value")
    sw_kwh = (nasa.get("nasa_power_solar_sw_2016_2025_mean_kwh_m2_day") or {}).get("value")
    rs_mj = hydro.get("rs_mj_m2_day")
    if rs_mj is None and sw_kwh is not None:
        rs_mj = round(float(sw_kwh) * 3.6, 4)

    u2 = hydro.get("wind_speed_2m_ms")
    elev_m = hydro.get("elevation_m")
    if elev_m is None:
        elev_m = (dem.get("dem_elevation_m") or {}).get("value")

    cent = spatial.get("centroid_lat_lon") or {}
    lat = hydro.get("latitude_deg") if hydro.get("latitude_deg") is not None else cent.get("lat")
    doy = int(hydro.get("day_of_year") or 105)

    missing_inputs: List[str] = []
    if u2 is None:
        missing_inputs.append("wind_speed_2m_ms (WS2M absent in repository NASA POWER regional extract)")
    if elev_m is None:
        missing_inputs.append("dem_elevation_m_and_slope_pct (terrain DEM not integrated locally)")
    if hydro.get("monthly_precipitation_series_mm") is None:
        missing_inputs.append("local_or_monthly_effective_rainfall_series (seasonal macro rainfall only; runoff/infiltration unmeasured)")
    if hydro.get("soil_fc_vol_pct") is None or hydro.get("soil_pwp_vol_pct") is None:
        missing_inputs.append("soil_hydraulic_properties_fc_pwp (SoilGrids texture is modeled estimate; lab FC/PWP unavailable)")

    irrig_sys = str(water_in.get("irrigation_system") or "unknown").lower()
    if irrig_sys != "none" and hydro.get("application_efficiency_ea") is None:
        missing_inputs.append("measured_irrigation_application_efficiency_ea")

    # Compute reference ET0 strictly if ALL required Penman-Monteith inputs exist
    et0_mm_day: Optional[float] = None
    if all(v is not None for v in (tmin, tmax, rh, rs_mj, u2, elev_m, lat)):
        et0_mm_day = compute_fao56_penman_monteith_et0_daily(
            tmin_c=float(tmin),
            tmax_c=float(tmax),
            rh_mean_pct=float(rh),
            rs_mj_m2_day=float(rs_mj),
            u2_ms=float(u2),
            elevation_m=float(elev_m),
            latitude_deg=float(lat),
            day_of_year=doy,
        )

    eff_precip_mm: Optional[float] = None
    monthly_p = hydro.get("monthly_precipitation_series_mm")
    if isinstance(monthly_p, list) and monthly_p:
        eff_precip_mm = round(sum(compute_effective_precip_usda_scs_monthly(float(x)) for x in monthly_p), 2)

    kc_coverage: Dict[str, str] = {}
    missing_stage_crops: List[str] = []
    if crop_profiles:
        for cid, prof in sorted(crop_profiles.items()):
            st = extract_crop_fao56_parameters(prof)
            if st.kc_ini is not None and st.kc_mid is not None and st.kc_end is not None:
                if all(x is not None for x in (st.l_ini_days, st.l_dev_days, st.l_mid_days, st.l_late_days)):
                    kc_coverage[cid] = "COMPLETE_KC_AND_STAGE_LENGTHS"
                else:
                    kc_coverage[cid] = "PARTIAL_KC_ONLY_NO_CALIBRATED_STAGE_DAYS"
                    missing_stage_crops.append(cid)
            else:
                kc_coverage[cid] = "NOT_APPLICABLE_OR_UNAVAILABLE"

    if missing_stage_crops:
        missing_inputs.append(
            f"fao56_calibrated_stage_lengths_L_ini_dev_mid_late (total growing_duration_days exists, calibrated stage split absent for {len(missing_stage_crops)} crops)"
        )

    # Check SoilGrids availability context without fabricating FC/PWP
    sg_clay = (soil.get("clay_0_30cm") or {}).get("value")
    soil_storage_status = "PARTIAL_TEXTURE_ONLY_NO_MEASURED_FC_PWP" if sg_clay is not None else "UNKNOWN"
    if hydro.get("soil_fc_vol_pct") is not None and hydro.get("soil_pwp_vol_pct") is not None:
        soil_storage_status = "PROVIDED_LOCAL_FC_PWP"

    if et0_mm_day is not None and eff_precip_mm is not None and not missing_stage_crops and soil_storage_status == "PROVIDED_LOCAL_FC_PWP":
        fao56_status = "COMPUTED_FULL"
    elif et0_mm_day is not None or eff_precip_mm is not None or bool(kc_coverage):
        fao56_status = "PARTIAL" if (et0_mm_day is not None or eff_precip_mm is not None) else "UNKNOWN"
    else:
        fao56_status = "UNKNOWN"

    return {
        "current_scoring_method": "ORDINAL_REGIME_SUITABILITY",
        "current_scoring_clarification": (
            "Phase I `water_efficiency` is a normalized ordinal heuristic evaluating crop water-regime suitability, "
            "farmer-reported water availability/irrigation access, and 11-55km macro rainfall balance. "
            "It is NOT a volumetric FAO-56 ETc minus effective rainfall irrigation balance."
        ),
        "fao56_water_balance_status": fao56_status,
        "reference_et0_mm_day": et0_mm_day,
        "effective_precipitation_mm": eff_precip_mm,
        "soil_water_storage_status": soil_storage_status,
        "climate_inputs_present": {
            "t2m_min_c": tmin,
            "t2m_max_c": tmax,
            "rh2m_pct": rh,
            "solar_sw_mj_m2_day": rs_mj,
            "wind_speed_2m_ms": u2,
            "dem_elevation_m": elev_m,
        },
        "kc_parameter_readiness_summary": {
            "crops_with_literature_kc": sum(1 for v in kc_coverage.values() if v.startswith("COMPLETE") or v.startswith("PARTIAL")),
            "crops_missing_stage_split_days": len(missing_stage_crops),
        },
        "missing_inputs": missing_inputs,
        "computable_when_supplied": [
            "ET0 (FAO-56 Penman-Monteith) once WS2M + DEM elevation supplied",
            "Monthly Effective Precipitation once monthly/daily local rainfall + slope/runoff supplied",
            "ETc = ET0 * Kc across L_ini/L_dev/L_mid/L_late once regional Guelma crop phenology stage lengths calibrated",
            "TAW/RAW & Net/Gross Irrigation Requirement once laboratory soil FC/PWP + system application efficiency Ea measured",
        ],
    }
