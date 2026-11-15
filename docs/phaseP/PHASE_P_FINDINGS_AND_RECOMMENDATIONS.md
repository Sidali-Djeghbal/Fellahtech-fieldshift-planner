# Field Shift — Phase P: Prioritized Audit Findings & Pilot Readiness Assessment

**Decision Engine Version:** `FieldShift-PhaseFJ-1.1.0`  
**Audit Basis:** Static trace across `src/`, `field_geospatial_processor.py`, `field_profile_builder.py`, `agronomic_knowledge/`, `schemas/`, `frontend/`, full regression suite (`91/91` tests passing), and `63` controlled dependency/OAT experiments ([`PHASE_P_CONTROLLED_TEST_RESULTS.csv`](./PHASE_P_CONTROLLED_TEST_RESULTS.csv)).

---

## Pilot & Field-Testing Readiness Verdict

**Is Field Shift sufficiently evidence-based for supervised field testing?**  
**Yes — strictly as a supervised decision-aid baseline (`REQUIRES_LOCAL_VERIFICATION`), PROVIDED the 2 Critical bugs below (`CRITICAL-01`, `CRITICAL-02`) are patched before exposing the live API to advisors.** Its constraint guards (cereal/Solanaceae/pulse break rules, water gates, unknown vs empty preservation, SoilGrids Nitrogen quarantine, and non-fabrication policies) behave responsibly under normal Belkheir/Bouchecouf/Tamlouka conditions and align reasonably with local ITGC agronomic principles.

**Is it ready for unsupervised pilot deployment or autonomous farmer use?**  
**NO.** Aside from missing measured site inputs (0 lab soil ECe/pH/N/P/K tests, 0 integrated DEM slope/drainage rasters, and 0 verified local yield/price budgets), the scoring engine currently functions primarily as a **single-climate-variable (`gpm_annual_precip`) plus qualitative-crop-KB ranker**, contains schema-breaking crashes on real alkaline soil pH (`CRITICAL-01`), endorses strategies even when `critical_data_adequacy = "INSUFFICIENT"` (`CRITICAL-02`), and breaks when a farmer specifies `income_weight` alone (`HIGH-01`).

---

## Prioritized Findings Matrix

### CRITICAL-01: Out-of-Range Soil pH Crashes Production Pipeline (`HTTP 500 OutputValidationError`)
- **Affected Files:** [`src/agronomic/constraint_engine.py`](../../src/agronomic/constraint_engine.py#L389) (`_eval_soil_ph`, `#L407`), [`constraint_engine.py`](../../src/agronomic/constraint_engine.py#L699) & [L1077](../../src/agronomic/constraint_engine.py#L1077), [`schemas/final_recommendation_output.schema.json`](../../schemas/final_recommendation_output.schema.json#L188), [`src/api/app.py`](../../src/api/app.py).
- **Root Cause:** `RULE_SOIL_PH_SUITABILITY` is declared `"evidence_classification": "SOFT_CONSTRAINT"` in `constraint_rules.json`, yet `_eval_soil_ph()` returns `status = "FAIL"` when `ph_0_30cm` falls outside `tolerable_ph_min..tolerable_ph_max` (e.g., `> 7.5` for `TOMATO_IND`, `> 8.0` for `BARLEY`, `> 8.5` for `DURUM_WHEAT`/`SOFT_WHEAT`/`LENTIL`, or `> 9.0` universally). `constraint_engine.py` classifies non-`HARD_CONSTRAINT` fails (`other_fails`) as `feasibility_status = "INFEASIBLE_CONSTRAINT"`, which is **absent from `final_recommendation_output.schema.json`'s allowed enum** (`FEASIBLE_PASS`, `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS`, `UNVERIFIED_HARD_UNKNOWN`, `INFEASIBLE_HARD_CONSTRAINT`). FastAPI does not catch `OutputValidationError`, causing an uncaught HTTP 500.
- **Controlled Evidence:** `SG-PH-8.6`, `SG-PH-9.1`, and `SG-PH-7.8-DRIP-TOMATO` (`water=abundant/well/drip`, `target=TOMATO_IND`, `ph=7.8`) all failed `validate_final_recommendation()`. Note that slightly calcareous Guelma pockets (`pH > 7.5`) with Tomato requested trigger this directly in real irrigated scenarios.
- **Recommended Fix:** Decide whether pH outside `tolerable_ph` is a `HARD_CONSTRAINT` (emitting `INFEASIBLE_HARD_CONSTRAINT`) or a soft `WARNING`; eliminate `"INFEASIBLE_CONSTRAINT"` from `constraint_engine.py` and handle `OutputValidationError` gracefully in `app.py`.

### CRITICAL-02: Decision Gate Endorses Winning Strategy Despite `INSUFFICIENT` Soil Coverage
- **Affected Files:** [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py#L1060-L1118) (`rank_rotation_candidates` `decision_gate` `#L1107`), [`src/agronomic/land_use_assessment.py`](../../src/agronomic/land_use_assessment.py#L229-L249), [`src/output/recommendation_builder.py`](../../src/output/recommendation_builder.py#L397).
- **Root Cause:** `recommendation_builder.py` correctly classifies `critical_data_adequacy = "INSUFFICIENT"` (`CRITICAL_BLOCKER`) whenever `clay_0_30cm is None` or `polygon_coverage_pct < 25.0%`. However, `scoring_engine.py` computes `decision_gate` **before** `_assess_critical_data_adequacy()` and gates endorsement solely via `land_use["is_provisional"]`. Whenever `clay_0_30cm` is completely missing (`0%` coverage) alongside either `wilaya_overlap_pct < 99%` (border parcels where `partial_wilaya = True` skips urban-mask conflict) OR `0.05 <= crop_frequency < 0.40` (`LAND_USE_LOW_EVIDENCE`, where `is_provisional = False`), `decision_gate` sets `decision_status = "REQUIRES_LOCAL_VERIFICATION"` with `endorsed_recommendation_id != None`.
- **Controlled Evidence:** `SG-GAP-PARTIAL-WILAYA` and `SG-GAP-LOW-CF` both returned `adequacy_status = "INSUFFICIENT"` yet endorsed `STRAT_SOIL_IMPROVEMENT` (`score = 0.879238`).
- **Recommended Fix:** Pass/derive soil coverage & critical blocker checks into `scoring_engine.decision_gate` so any `CRITICAL_BLOCKER` (including `clay_val is None` or `clay_cov < 25%`) forces `EXPLORATORY_ONLY` with `endorsed_recommendation_id = None`.

---

### HIGH-01: Solo `income_weight` Produces `NO_RECOMMENDATION` (`FRM-WT-INCOME-ALONE`)
- **Affected Files:** [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py#L168) (`_resolve_farmer_weights_from_mapping`) and [`scoring_engine.py`](../../src/optimization/scoring_engine.py#L1068).
- **Root Cause:** Unlike `forage_value_weight`, `income_weight` is listed in `core_keys`. Passing `{"income_weight": 0.80}` without explicitly passing `water_saving_weight`, `soil_improvement_weight`, or `risk_reduction_weight` triggers `core_provided = True` and sets omitted core weights to `0.0`. Since `income_potential` is permanently `UNKNOWN` in HTTP requests, `active_weighted_objs` becomes empty and the API returns `NO_RECOMMENDATION` (`INSUFFICIENT_SCORABLE_EVIDENCE_NO_WINNER`). When passed alongside other weights (`FRM-WT-INCOME-MIXED`), `income_weight = 0.70` is silently renormalized out to `0.0` effective influence.
- **Recommended Fix:** Reject unsupported positive `income_weight` explicitly (with clear API warning or HTTP 422 / UI disclosure) or preserve default core weights unless explicit core weights `> 0` are supplied for scorable objectives.

### HIGH-02: Extreme Sparsity of Soil & Climate Influence in Numerical Scoring (`48/49` Raster/Climate Features Zero-Weight in Scores)
- **Affected Files:** [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py#L261-L724), [`field_geospatial_processor.py`](../../field_geospatial_processor.py).
- **Observation:** Controlled tests (`SG-CLAY-20/38/55`, `SG-PH-6.0/7.8`, `SG-SOC-10/25/None`, `SG-CEC-5/45`, `SG-SAND-SILT-TEXT`, `SG-SUBSOIL-NONE`, `CLM-THERMAL-*`, `CLM-SMAP-SPR-*`, `CLM-UNUSED-14-NONE`, `VEG-UNUSED-11-NONE`, `SPAT-BOUCHECOUF`) proved that **only 1 geospatial scalar (`gpm_annual_precip_2016_2025_mean_mm`) alters numeric objective scores across parcels.** `soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, and `forage_value` produce identical scores on Belkheir and Bouchecouf (`587.56` vs `581.3 mm`) despite differing clay, pH, SOC, CEC, NDVI, and SMAP values.
- **23 of 49 extracted geospatial metrics** (all 6 `30–100 cm` subsoil SoilGrids, S2 `EVI/NDMI/NDRE`, 4 seasonal GPM totals, 4 surface SMAP, 1 autumn rootzone SMAP, MODIS autumn NDVI + 4 EVI) have **zero readers downstream**.
- **Recommended Fix (for future Phase):** Before pilot scaling, decide deliberately whether subsoil texture/SOC, SoilGrids topsoil SOC `< 18 g/kg` / heavy clay `>= 35%`, and seasonal spring GPM/SMAP deficits should enter continuous objective terms (grounded in validated local literature/trials) OR prune unreferenced extractions cleanly so reports do not imply multi-layer raster utilization.

### HIGH-03: Structural Handicap Against Irrigated Cash Rotations & Coarse `water.availability`
- **Affected Files:** [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py#L261) (`_eval_water_efficiency`).
- **Root Cause:** Even when a farmer declares `water = abundant / well / drip` and explicitly requests `target_crop_ids = ["TOMATO_IND"]` (`FRM-TGT-TOMATO-DRIP`), `STRAT_SOIL_IMPROVEMENT` (`0.845644`) beats `STRAT_IRRIGATED_CASH` because Tomato is capped at `water_efficiency = 0.40` (vs `0.9541` on rainfed crops receiving `+0.05` `irrig_buf`) while `income_potential` (where horticulture outperforms cereals) has `0` active weight. Additionally, `availability="moderate"` and `"abundant"` produce 100% identical outputs (`FRM-WTR-MOD-DRIP` == `FRM-WTR-ABUND-DRIP` == `0.894863`).
- **Recommended Fix:** Do not inflate rainfed strategies with `irrig_buf` over irrigated targets blindly, replace ordinal water caps with seasonal FAO-56 deficit ratios once `ET0` and irrigation supply data are integrated, and enable verified local crop-budget entry for `income_potential`.

---

### MEDIUM-01: Equipment Warning Paradox Increases Score When Declaring Missing Baler
- **Affected Files:** [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py#L724) (`_eval_farmer_priority_fit`).
- **Root Cause:** Operational slot points assign `PASS=1.00`, `UNKNOWN=0.75`, `WARNING=0.45`, `FAIL=0.00`. When a farmer declares `["no_hay_baler"]` (`FRM-EQ-NO-HAY-BALER`), `FABA_BEAN` and `DURUM_WHEAT` move from `UNKNOWN (0.75)` to `PASS (1.00)` while `VETCH_OAT` drops from `0.75` to `0.45`, raising strategy average `ops_pts` from `0.75` to `0.8167` (`+0.003642` composite increase over unknown equipment!).
- **Recommended Fix:** Penalize or flag equipment conflict warnings asymmetrically (e.g., strategy-level penalty when any critical harvest/baling equipment needed by a slot is absent, rather than offsetting conflict penalties via unrelated `PASS` slots).

### MEDIUM-02: Missing Local Terrain DEM Permanently Forces `PARTIAL` / `REQUIRES_LOCAL_VERIFICATION` & Broken Key in `water_balance.py`
- **Affected Files:** [`field_geospatial_processor.py`](../../field_geospatial_processor.py) (`_extract_dem_placeholder`), [`src/optimization/water_balance.py`](../../src/optimization/water_balance.py#L187-L188), [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py#L565).
- **Root Cause:** `dem_elevation_m` and `dem_slope_pct` are permanently `None` (`UNAVAILABLE_NOT_INTEGRATED`), locking `RULE_DEM_DRAINAGE_UNCERTAINTY` at `UNKNOWN` and `erosion_protection` at flat-terrain `0.8667`. Separately, `water_balance.py:187` looks up `spatial.get("centroid_lat_lon")` instead of `field_geospatial_processor.py:195`'s `"centroid_lon_lat"`, so even supplying `WS2M` and `DEM` directly would still leave latitude missing inside `assess_water_balance_readiness()` unless overridden manually.

### MEDIUM-03: Over-Broad Heat/Frost Rules (`Never Fail`) & Unverified 220 mm Rainfed Feasibility
- **Affected Files:** [`src/agronomic/constraint_engine.py`](../../src/agronomic/constraint_engine.py#L213) (`_eval_precipitation_regime`), [`constraint_engine.py`](../../src/agronomic/constraint_engine.py#L270) (`_eval_thermal_heat_frost`).
- **Observation:** `CLM-GPM-220` (`220 mm` arid precipitation) leaves `FABA_BEAN` (`min_annual_rainfed_precip_mm = 450 mm`) and `DURUM_WHEAT` (`400 mm`) feasible (`WARNING` only) so `STRAT_SOIL_IMPROVEMENT` remains #1 even at `220 mm/yr`. Likewise, `CLM-THERMAL-EXTREME` (`45 °C` summer Tmax, `-2 °C` winter Tmin) emits soft `WARNING`s without affecting feasibility or scores. Notice also `_extract_water_context()` fallback (`scoring_engine.py:151`) reads `"water_source"` instead of `"source"` when `field_profile=None`.

---

### LOW-01: Catalog Completeness Inflation (`0.8846`) & `Q_IRRIGATION_SALINITY_SIGN` Minor Source Gap
- **Affected Files:** [`src/output/recommendation_builder.py`](../../src/output/recommendation_builder.py#L476) (`_build_data_quality`), [`field_profile_builder.py`](../../field_profile_builder.py#L614).
- **Observation:** `completeness_score` divides non-null metrics over all 52 items (counting the 23 unused geospatial layers equally alongside SoilGrids `clay` and `crop_frequency`), giving `0.8846` even on data-sparse advisory runs where FAO-56, DEM, ECe, lab N/P/K, and budgets are all absent. Additionally, `Q_IRRIGATION_SALINITY_SIGN` (`source in {'reservoir','river','well','groundwater'}`) omits `source='other'` when `irrigation_system != 'none'`.

---

## Mandatory Remediation Checklist Before Pilot Deployment

1. **Must Fix Immediately (API Integrity & Safety Gates):**
   - Eliminate `"INFEASIBLE_CONSTRAINT"` schema mismatch (`CRITICAL-01`) and wrap `OutputValidationError` cleanly in `src/api/app.py`.
   - Enforce `critical_data_adequacy = "INSUFFICIENT"` (`clay_val is None` or `<25%` SoilGrids coverage) as an `EXPLORATORY_ONLY` blocker in `scoring_engine.decision_gate` (`CRITICAL-02`).
   - Prevent solo `income_weight > 0` from wiping out default core weights (`HIGH-01`) or surface a clear validation message that quantitative income data is not yet available in API mode.
2. **Must Resolve Before Unsupervised Advisory Pilot:**
   - Integrate a 30 m Guelma DEM (`SRTM` / `Copernicus GLO-30`) so slope runoff (`erosion_protection`) and drainage (`RULE_DEM_DRAINAGE_UNCERTAINTY`) become truly parcel-specific, and fix `centroid_lon_lat` in `water_balance.py` + integrate `WS2M` and SoilGrids hydraulic parameters (`FC`/`PWP`) or local soil tests.
   - Replace static 11 km climatology scoring dominance with seasonal water-balance / soil-calibrated scoring rules where locally verified (`soil clay/SOC`, `ECe`, field `T-1` yields/budgets), and align `equipment` `WARNING` penalties so lacking essential machinery lowers—never raises—strategy preference scores.
   - Audit and either utilize or retire the **23 unreferenced geospatial metrics** so data extraction pipelines and provenance disclosures match actual model dependencies 1-to-1.
