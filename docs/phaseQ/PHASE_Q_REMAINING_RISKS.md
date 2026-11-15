# Field Shift — Phase Q Remaining Risks & Deployment Readiness Assessment

**Phase Scope Note:** Phase Q was strictly scoped to remediating verified software, schema, validation, and decision-gating defects (`CRITICAL-01`, `CRITICAL-02`, `HIGH-01`, `MEDIUM-01`, and the `MEDIUM-02` coordinate-order / strict readiness bug) without redesigning the agronomic scoring formulas, altering `DEFAULT_FARMER_WEIGHTS`, weakening agronomic rules, introducing ML, or fabricating agronomic/economic data.

All remaining limitations identified in Phase P that stem from missing field/laboratory measurements, regional climate resolution, or uncalibrated agronomic scoring structure remain explicitly documented below.

---

## 1. Deferred Agronomic & Modeling Findings (From Phase P)

| ID | Severity | Status after Phase Q | Summary of Remaining Gap | Observed Quantitative Impact |
|---|---|---|---|---|
| **HIGH-02** | **HIGH** | Deferred (Agronomic Model Scope) | **48 of 49** geospatial/climate features have zero continuous weight in objective scoring; **23 of 49** extracted metrics have no downstream readers anywhere in constraints, scoring, or gating. | Only `gpm_annual_precip_2016_2025_mean_mm` shifts continuous parcel scores (`CLM-GPM-220..750`, Bouchecouf -> Belkheir -> Tamlouka). `soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, and `forage_value` produce identical numeric scores regardless of SoilGrids `soc_0_30cm`, `clay_0_30cm`, `cec_0_30cm`, `sand/silt`, `30-100cm` subsoil, S2 `EVI/NDMI/NDRE`, seasonal GPM, or SMAP soil moisture (`VEG-UNUSED-11-NONE`, `CLM-UNUSED-14-NONE`, `SG-SUBSOIL-NONE`, `SG-SAND-SILT-TEXT` all yield `0.0` score delta). |
| **HIGH-03** | **HIGH** | Deferred (Agronomic Model Scope) | **Structural handicap on irrigated cash rotations & coarse water resolution.** | `STRICTLY_IRRIGATED` crops (`TOMATO_IND`, `POTATO`) are capped at `water_efficiency = 0.40` (drip), `0.30` (sprinkler), or `0.20` (surface/other), while rainfed/supplemental crops receive up to `1.0` plus an `+0.05` `irrig_buf` when irrigation is active. `water.availability = "moderate"` and `"abundant"` (with `well/drip`) return identical scores (`0.894863` on Belkheir in `FRM-WTR-MOD-DRIP` vs `FRM-WTR-ABUND-DRIP`). Paired with absent farmgate `economic_data` via HTTP `/api/v1/fields/analyze`, high-value irrigated cash strategies systematically trail low-input rainfed legumes/cereals even on well-supplied irrigated farms. |
| **MEDIUM-02** *(External Data)* | **MEDIUM** | Code bug fixed; **External Data Deferred** | **FAO-56 water balance & terrain runoff remain blocked from full activation in production.** Phase Q fixed `centroid_lon_lat` `[lon, lat]` extraction and enforced strict `COMPLETE_KC_AND_STAGE_LENGTHS` readiness gating in `src/optimization/water_balance.py`. | On all real Guelma parcels, missing `terrain_dem` (`dem_elevation_m = None`, `dem_slope_pct = None`), missing NASA POWER `WS2M` wind speed, absent lab `FC`/`PWP`, and missing calibrated stage splits (`l_ini_days`, `l_dev_days`, `l_mid_days`, `l_late_days`) keep `fao56_water_balance_status = "PARTIAL"`, `RULE_DEM_DRAINAGE_UNCERTAINTY = "UNKNOWN"`, and `erosion_protection` permanently fixed at flat-terrain baseline (`0.8667`). |
| **MEDIUM-03** | **MEDIUM** | Deferred (Rule Calibration) | **Permissive extreme-climate rules & minor water helper edge case.** | Extreme heat/frost (`45°C / -2°C` in `CLM-THERMAL-EXTREME`) and low-rainfall (`220 mm` in `CLM-GPM-220`) rules remain `WARNING` rather than `FAIL`, leaving feasibility permissive under severe heat/drought stress. Additionally, `_extract_water_context()` retains a legacy `"water_source"` fallback lookup only if called directly with `field_profile=None`. |
| **LOW-01** | **LOW** | Mitigated in Gating; Minor Metadata Deferred | **Uniform completeness inflation, unconsumed DB metadata, and minor question trigger.** | `compute_data_completeness_score()` weights all 52 inventory items uniformly (so unused metrics inflate completeness ratio; however, `CRITICAL-02` now prevents high uniform completeness from overriding `critical_data_adequacy = "INSUFFICIENT"`). `Q_IRRIGATION_SALINITY_SIGN` omits `water.source = "other"` when `irrigation_system != "none"`. Farmer DB fields `crop_history[].yield_tons_per_hectare`, `planting_month`, `notes`, and `planning.planting_month` are persisted without altering rules/scores (`FRM-HIST-YIELD-HIGH`, `FRM-PMONTH-10`). |

---

## 2. Unmeasured Physical, Chemical & Economic Evidence Gaps

1. **Missing On-Site Soil & Water Laboratory Measurements:**
   - **Salinity & Sodicity (`ECe`, irrigation `EC`, `SAR`):** Absent from SoilGrids and farmer schema; salinity tolerance cannot be verified autonomously without field/lab testing.
   - **Lab Fertility (`N`, `P`, `K`) & Validated Total Nitrogen:** `SoilGrids nitrogen_0_30cm` remains quarantined (`UNVALIDATED_EXCLUDED`); N fixation is quantified only for `FABA_BEAN` (`100–200 kg N/ha`) while `CHICKPEA`, `LENTIL`, and `VETCH_OAT` remain heuristic (`0.72` / `0.68`) and `quantitative_t_c_ha_yr` is null across `crop_profiles.json`.
   - **Laboratory `FC` / `PWP` & Local Drainage Depth:** Texture-only SoilGrids estimates cannot substitute for measured infiltration, hardpan depth, or root-zone water holding capacity.
2. **Macro-Scale vs Parcel-Scale Resolution Limits:**
   - **SoilGrids 250 m** cannot resolve intra-parcel variability, lime crusts, or small terraced pockets (and masks urban/built-up pixels such as `SPAT-PERIURBAN`, which Phase Q now safely gates to `EXPLORATORY_ONLY`).
   - **GPM (~11 km)** and **NASA POWER (~55–69 km)** reflect decadal climatology (2016–2025), not intra-season rainfall anomalies, parcel microclimates, or multi-year drought trends.
3. **Absent Regional / Farmgate Economic Data via API:**
   - While `HIGH-01` eliminated the silent `income_weight` bug (`NO_RECOMMENDATION` crash when omitted core weights were zeroed out) and now preserves scorable core weights with explicit warnings, real `income_potential` scoring via API remains inactive until verified crop yield, market price, and input cost schedules are integrated.

---

## 3. Operational Controls & Preconditions Required Before Broader Rollout

### Required for Supervised Advisor Testing (Current Phase Q Baseline — READY with Guardrails)
1. Advisors must review every `REQUIRES_LOCAL_VERIFICATION` rationale, `soft_constraint_warnings`, and `weight_warnings` / `data_quality.warnings` before issuing farmer guidance.
2. When `decision_status == "EXPLORATORY_ONLY"` (`endorsed_recommendation_id = None`), treat ranked strategies strictly as discussion candidates contingent on local soil sampling (`soil_0_30cm` + pH + texture) and boundary verification (`crop_frequency` check).
3. For irrigated or cash-crop parcels, advisors must supplement the heuristic `water_efficiency` ranking with on-site borehole/spring flow rates, irrigation salinity checks, and local gross-margin comparisons.

### Mandatory Prerequisites Before Unsupervised / Autonomous Farmer Deployment (NOT YET MET)
1. **Resolve `HIGH-02` & `MEDIUM-02` Data Integration:** Integrate an authoritative Guelma DEM (`dem_slope_pct`, `dem_elevation_m`), wind speed (`WS2M`), calibrated crop stage lengths (`L_ini/dev/mid/late`), and empirically calibrated soil/moisture response functions (rather than relying purely on a single annual precipitation scalar for spatial differentiation).
2. **Resolve `HIGH-03` Irrigated-vs-Rainfed Calibration & Volumetric Budget:** Separate rainfed drought resilience from volumetric drip/sprinkler crop water satisfaction (`ETc - P_eff`) and model seasonal water supply (`availability` + borehole quota).
3. **Integrate Verified Regional Economic Budgets:** Supply audited Algerian/Guelma crop enterprise budgets (`cost_per_ha`, reference prices, yield intervals) so `income_potential` is natively computable without manual Python overrides.
4. **Calibrate Regional Agronomic Thresholds (`MEDIUM-03`) & Field Validation:** Validate thermal/drought hard vs soft boundaries and pH/clay/salinity rules against multi-season Guelma trial parcels with independent agronomist sign-off.
