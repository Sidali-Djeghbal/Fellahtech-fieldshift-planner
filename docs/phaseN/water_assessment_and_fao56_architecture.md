# Phase N — Water Assessment Audit & Modular FAO-56 Readiness Architecture

## 1. Current Water Scoring Clarification (`ORDINAL_REGIME_SUITABILITY`)

Phase I's `water_efficiency` objective (`src/optimization/scoring_engine.py::_eval_water_efficiency`) is a **normalized `[0, 1]` ordinal compatibility heuristic** built from:
- Crop `water_requirement_category` (`STRICTLY_IRRIGATED`, `RAINFED_OR_SUPPLEMENTAL`, `RAINFED_SEMI_ARID_TOLERANT`) and `min_annual_rainfed_precip_mm` (`crop_profiles.json`),
- Farmer-declared `water.availability`, `water.source`, and `water.irrigation_system`,
- Multi-annual regional precipitation bounds (`gpm_annual_precip_2016_2025_mean_mm` vs `nasa_power_annual_precip_2016_2025_mean_mm`).

In Phase N:
- Both `ranking_methodology.water_efficiency_scope` and `water_balance_assessment.current_scoring_method = "ORDINAL_REGIME_SUITABILITY"` explicitly warn users and API consumers that this score is **not** a volumetric FAO-56 evapotranspiration deficit ($ET_c - P_{\text{eff}}$) or irrigation scheduling volume (m³/ha).
- In `frontend/app.js`, strategy cards explicitly display **Water Efficiency (Ordinal)** alongside an overall banner reporting `fao56_water_balance_status`.

---

## 2. Dataset Audit for Quantitative FAO-56 Water Balance

Inspecting [`data/NASA_POWER_REGIONAL/extraction_metadata.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/NASA_POWER_REGIONAL/extraction_metadata.json) and repository assets confirms:

| Required FAO-56 Component | Repository Status | Notes |
|---|---|---|
| $T_{\min}, T_{\max}, RH_{2m}, R_s$ (`ALLSKY_SFC_SW_DWN`), `PRECTOTCORR` | **Present (55 km regional)** | `meteorological_variables = ['T2M', 'T2M_MAX', 'T2M_MIN', 'PRECTOTCORR', 'RH2M']`, `solar_variables = ['ALLSKY_SFC_SW_DWN']`. |
| **Wind Speed at 2 m (`WS2M`)** | **MISSING** | Absent from `extraction_metadata.json`; FAO-56 Penman-Monteith $ET_0$ cannot be computed without wind fabrication. |
| **Terrain DEM Elevation & Slope** | **MISSING (`UNAVAILABLE_NOT_INTEGRATED`)** | Atmospheric pressure adjustment and runoff/slope fraction for $P_{\text{eff}}$ require DEM elevation/slope. |
| **Crop $K_c$ & Max Rooting Depth** | **Present (Literature)** | All annual crops in `crop_profiles.json` include `kc_profile` (`kc_ini`, `kc_mid`, `kc_end`) and `root_depth_m`. |
| **Calibrated Stage Lengths ($L_{\text{ini}}, L_{\text{dev}}, L_{\text{mid}}, L_{\text{late}}$)** | **MISSING** | Total `growing_duration_days` exists, but stage-day splits calibrated to Guelma sowing windows are absent. |
| **Measured Soil FC, PWP & Irrigation $E_a$** | **MISSING** | SoilGrids provides modeled 250 m texture (`clay`/`sand`/`silt`), NOT lab field capacity (`FC`), permanent wilting point (`PWP`), or pump/emitter application efficiency ($E_a$). |

---

## 3. Modular FAO-56 Engine ([`src/optimization/water_balance.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/water_balance.py))

Phase N delivers a strictly non-fabricating FAO-56 evaluation layer ready for progressive field calibration:
- `extract_crop_fao56_parameters(crop_profile) -> FAO56StageParameters`
- `compute_fao56_penman_monteith_et0_daily(*, tmin_c, tmax_c, rh_mean_pct, rs_mj_m2_day, u2_ms, elevation_m, latitude_deg, day_of_year) -> float` (Allen et al., 1998 FAO Irrigation & Drainage Paper 56)
- `compute_effective_precip_usda_scs_monthly(precip_monthly_mm) -> float` (USDA SCS monthly effective rainfall formula)
- `assess_water_balance_readiness(field_profile, crop_profiles=..., local_hydrology_inputs=None) -> Dict[str, Any]`

### Strict Non-Fabrication Guarantee
- When local `wind_speed_2m_ms`, `elevation_m`, `monthly_precipitation_series_mm`, or `soil_fc_vol_pct`/`soil_pwp_vol_pct` are absent (default Guelma pipeline), `reference_et0_mm_day` and `effective_precipitation_mm` remain `None`, `fao56_water_balance_status` reports `"UNKNOWN"` (or `"PARTIAL"` if partial hydrology inputs are supplied), and `missing_inputs` enumerates the exact missing measurements.
- Whenever complete measured inputs are supplied via `local_hydrology_inputs` (verified in `test_phaseN_hardening.py::test_06`), `compute_fao56_penman_monteith_et0_daily` and `compute_effective_precip_usda_scs_monthly` compute deterministic quantitative outputs cleanly.
