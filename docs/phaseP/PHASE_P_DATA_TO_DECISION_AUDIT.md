# Field Shift — Phase P: End-to-End Data-to-Decision Audit

**System Audited:** Field Shift — Guelma Crop Rotation Decision Support System (DSS)  
**Decision Engine Version:** `FieldShift-PhaseFJ-1.1.0` | **Profile Schema:** `1.1.0`  
**Audit Scope:** Strictly non-mutating source-code trace, dependency mapping, gate audit, and controlled perturbation testing (`docs/phaseP/PHASE_P_CONTROLLED_TEST_RESULTS.csv`). No model weights, rules, schemas, or tests were altered.

---

## Executive Summary

Field Shift implements a **transparent, deterministic, rule-and-heuristic decision pipeline** rather than a statistical/ML prediction model. Its strongest asset is architectural honesty: unknown parameters (`null` vs `[]`, quarantined SoilGrids Nitrogen, missing FAO-56 ET0 inputs, unavailable enterprise crop budgets) are preserved explicitly instead of fabricated.

However, tracing every data element from raw extraction to final recommendation reveals a **sharp gap between rich feature extraction and narrow decision utilization**:

1. **Of 49 geospatial metrics extracted in `field_geospatial_processor.py`, 23 are completely unused downstream, 11 are reporting/display-only or sit in an uncomputable FAO-56 module, 13 only emit soft text warnings or toggle `SCORED`/`PARTIAL` labels without changing scores, and only **1** continuous metric (`gpm_annual_precip_2016_2025_mean_mm`) directly alters numeric strategy scores across real Guelma parcels** (with `crop_frequency_2021_2025`, `s2_2024_03_ndvi_10m`, `modis_ndvi_spring_2016_2025_mean`, `clay_0_30cm` coverage/masking, and `ph_0_30cm` gating land-use status or feasibility).
2. **All 7 other scoring objectives are numerically invariant to parcel soil and climate properties** once basic feasibility passes (`soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, `forage_value`, `income_potential`, `farmer_priority_fit`). SoilGrids `clay`, `ph`, `soc`, `cec`, `sand`, and `silt` carry **zero continuous weight** in any scoring function.
3. **Controlled testing uncovered two Critical software/gating defects and one High economic/UX trap:**
   - **Schema Crash (`HTTP 500 OutputValidationError`) on Out-of-Range `pH` (`SG-PH-8.6`, `SG-PH-9.1`, `SG-PH-7.8-DRIP-TOMATO`):** `RULE_SOIL_PH_SUITABILITY` (labeled `SOFT_CONSTRAINT` in `constraint_rules.json`) emits `FAIL`, causing `constraint_engine.py` to output `feasibility_status = "INFEASIBLE_CONSTRAINT"`, which is not in `schemas/final_recommendation_output.schema.json`'s allowed enum and crashes `validate_final_recommendation()`.
   - **Decision-Gate vs. Critical-Adequacy Desync (`SG-GAP-PARTIAL-WILAYA`, `SG-GAP-LOW-CF`):** A parcel with **zero SoilGrids pixels (`clay_0_30cm = None`, `coverage = 0%`)** receives `critical_data_adequacy = "INSUFFICIENT"`, yet if either `wilaya_overlap_pct < 99%` OR `0.05 <= crop_frequency < 0.40`, `decision_gate` still issues `REQUIRES_LOCAL_VERIFICATION` with a non-null `endorsed_recommendation_id`.
   - **Solo `income_weight` Breaks Ranking (`FRM-WT-INCOME-ALONE`):** Because `income_potential` is permanently `UNKNOWN` in the HTTP API, supplying `income_weight > 0` without core weights zeroes the omitted core weights, drops `income_weight` to `0`, leaves zero active objectives, and returns `NO_RECOMMENDATION`.

---

## Task 1 — End-to-End Decision Pipeline Trace

| Stage | Source File & Entry Function(s) | Exact Responsibility & Key Data Handled |
|---|---|---|
| 1. HTTP Request & Contract Validation | [`src/api/app.py`](../../src/api/app.py) (`create_app`, `/api/v1/fields/analyze`), [`src/api/schemas.py`](../../src/api/schemas.py) (`FieldAnalyzeRequest.to_scientific_payload`), [`field_input_schema.json`](../../field_input_schema.json) | Validates Draft 2020-12 / Pydantic types, rejects `FORBIDDEN_TECHNICAL_KEYS`, preserves `null` (`NOT_PROVIDED`) vs `[]` (`EXPLICITLY_CONFIRMED_EMPTY`) vs omitted weights, hashes deterministic `analysis_id`. |
| 2. Geospatial Feature Extraction | [`field_geospatial_processor.py`](../../field_geospatial_processor.py) (`validate_and_project_polygon`, `extract_field_geospatial_context`, `_extract_soilgrids`, `_extract_crop_frequency`, `_extract_sentinel2`, `_extract_modis_seasonal`, `_extract_gpm_smap`, `_extract_nasa_power`, `_extract_dem_placeholder`) | Projects GeoJSON polygon (`EPSG:4326 -> EPSG:32632`), computes Wilaya overlap & area weights, extracts **49 metrics** across 7 domains (quarantining `nitrogen_0_30cm` and returning `None` placeholders for unavailable 30 m DEM). |
| 3. Field Profile, Completeness & Land-Use Gate | [`field_profile_builder.py`](../../field_profile_builder.py) (`validate_farmer_input`, `_build_agronomic_context`, `_build_quality_and_clarifications`, `build_field_profile`), [`src/agronomic/temporal_planning.py`](../../src/agronomic/temporal_planning.py), [`src/agronomic/land_use_assessment.py`](../../src/agronomic/land_use_assessment.py) (`assess_land_use`) | Normalizes `crop_history` chronologically (`Winter < Spring < Summer < Autumn`), rejects future/concurrent crops and target/excluded intersections (`422`), evaluates 5-class arable land-use support, emits `FieldProfile` (`1.1.0`). |
| 4. Agronomic Constraints & Candidate Generation | [`src/agronomic/constraint_engine.py`](../../src/agronomic/constraint_engine.py) (`evaluate_crop_for_field`, `evaluate_crop_sequence`), [`src/rotation/candidate_generator.py`](../../src/rotation/candidate_generator.py) (`_construct_pattern_sequences`, `generate_rotation_candidates`) | Applies 15 crop rules (`RULE_*`) and 10 sequence rules (`SEQ_01..SEQ_10`) using [`crop_profiles.json`](../../agronomic_knowledge/crop_profiles.json), [`constraint_rules.json`](../../agronomic_knowledge/constraint_rules.json), [`sequence_compatibility.json`](../../agronomic_knowledge/sequence_compatibility.json); constructs up to 8 candidate 2–4 season rotation archetypes (plus optional `STRAT_EXISTING_BASELINE` and target-injected strategies). |
| 5. Multi-Objective Scoring, Weighting, Pareto & Sensitivity | [`src/optimization/scoring_engine.py`](../../src/optimization/scoring_engine.py) (`_resolve_weights`, `_eval_*`, `rank_rotation_candidates`), [`src/optimization/pareto.py`](../../src/optimization/pareto.py), [`src/optimization/sensitivity.py`](../../src/optimization/sensitivity.py), [`src/optimization/water_balance.py`](../../src/optimization/water_balance.py) | Evaluates 8 objectives across eligible candidates; excludes `UNKNOWN`/`NOT_APPLICABLE` objectives and renormalizes active weights to 1.0; computes non-dominated Pareto front, near-tie margin status (`<= 0.015` near tie, `<= 0.04` narrow), macro-climate sensitivity (`gpm` vs `power`), and sets `decision_gate`. |
| 6. Output Assembly & Validation | [`src/output/recommendation_builder.py`](../../src/output/recommendation_builder.py) (`_assess_critical_data_adequacy`, `_build_data_quality`, `build_final_recommendation`), [`src/output/output_validator.py`](../../src/output/output_validator.py) (`validate_final_recommendation`) | Computes `completeness_score` and `critical_data_adequacy`, formats field insights & explanations, enforces Draft 2020-12 [`final_recommendation_output.schema.json`](../../schemas/final_recommendation_output.schema.json) and semantic invariants. |

---

## Task 2 — Data-to-Decision Dependency Summary & Epistemic Provenance

Full item-by-item mapping across **all 49 extracted geospatial metrics**, **4 polygon spatial metrics**, **all farmer schema fields**, and **2 unintegrated runtime arguments** is delivered in [`PHASE_P_FEATURE_DEPENDENCY_MATRIX.csv`](./PHASE_P_FEATURE_DEPENDENCY_MATRIX.csv).

### Epistemic Classification of Active Inputs
- **Directly Measured Field Data:** **0** agronomic soil/water/yield layers exist. Only the submitted **polygon geometry** (`area_ha`, `wilaya_overlap_pct`, `primary_commune`) is geometrically exact.
- **Satellite-Derived Surface / Vegetation Layers:** `crop_frequency_2021_2025` (10 m ESA product, primary land-use gate), `s2_2024_03_ndvi_10m` (10 m single-month March 2024 snapshot), `modis_ndvi_spring_2016_2025_mean` (250 m 10-year spring composite), and `gpm_annual_precip_2016_2025_mean_mm` (11 km IMERG hydrological annual sum — **the sole quantitative satellite feature entering an objective score**).
- **Coarse Regional Climate / Reanalysis Data:** `nasa_power_annual_precip_2016_2025_mean_mm`, `nasa_power_t2m_max/min` (`0.5° × 0.625°`, ~55–69 km MERRA-2 — identical `736.84 mm` across Belkheir, Guelma peri-urban, and Bouchecouf), and `smap_rootzone_sm_spring_2016_2025_mean` (`11 km` SMAP L4 assimilated model).
- **Static Modeled Soil Estimates:** `soilgrids_v6` 250 m layers (`clay`, `sand`, `silt`, `ph`, `soc`, `cec`, `usda_texture_0_5cm`). Treated transparently as modeled spatial proxies rather than lab tests; `nitrogen_0_30cm` is quarantined due to `N > SOC` anomaly.
- **Farmer-Reported Operational Inputs:** `water` (`availability`, `source`, `irrigation_system`), chronological `crop_history`, `planning`, `preferences` (`target_crop_ids`, `excluded_crop_ids`, `equipment_constraints`, and 5 weights).
- **Expert-Defined Agronomic Rules & Heuristic Weights:** `crop_profiles.json`, `constraint_rules.json`, `sequence_compatibility.json`, plus heuristic lookup tables `_SOM_DIRECTION_SCORES`, `_EROSION_COVER_SCORES`, `_FORAGE_VALUE_SCORES`, and `DEFAULT_FARMER_WEIGHTS`.

---

## Task 3 — Actual Scoring Objective Audit

Full formula and threshold matrix is delivered in [`PHASE_P_SCORING_DEPENDENCY_MATRIX.csv`](./PHASE_P_SCORING_DEPENDENCY_MATRIX.csv). Key architectural audit findings across all 8 objectives:

1. **Only `water_efficiency` is continuously geo-responsive:** Computed from `gpm_annual_precip_2016_2025_mean_mm`, crop `min_annual_rainfed_precip_mm`, and farmer irrigation declaration. On `STRICTLY_IRRIGATED` crops (`TOMATO_IND`, `POTATO`), score is hardcoded (`drip=0.40`, `sprinkler=0.30`, `surface=0.20`, `rainfed/none=0.0`), independent of `availability="abundant"` vs `"moderate"` and local rainfall. Combined with inactive `income_potential`, rainfed cereal/vetch sequences routinely score `~0.95` on irrigated farms while `STRAT_IRRIGATED_CASH` stays structurally handicapped (`0.40` slot ceiling on Tomato).
2. **`soil_improvement` ignores quantitative SoilGrids values:** Computed purely from crop `_SOM_DIRECTION_SCORES` and `_root_depth_class` diversity (`+0.05` if `>= 2` classes). `soc_0_30cm` and `clay_0_30cm` only toggle `status` (`"SCORED"` vs `"PARTIAL"` if `None`).
3. **`nitrogen_contribution` is completely site-agnostic:** Uses fixed constants (`0.95` Faba Bean, `0.72` unquantified pulses, `0.68` Vetch-Oat) plus `+0.06` per `SEQ_07` transition (capped at `+0.12`). Gives identical `0.6490` scores on Belkheir, Bouchecouf, and Tamlouka.
4. **`pest_disease_disruption` is entirely rule/sequence-driven:** Scores botanical-family transitions across slots (and optional `T-1` predecessor when `SEQ_10=PASS`) minus `-0.12` / `-0.04` warning and `-0.45` fail penalties.
5. **`erosion_protection` operates permanently in missing-DEM `PARTIAL` mode:** Because `dem_slope_pct` is always `None` on disk (`UNAVAILABLE_NOT_INTEGRATED`), `slope_adj` (`-0.10` if `dem_slope >= 8%` and cover `< 0.70`) never fires. Every field in Guelma receives the identical flat-terrain score (`0.8667` for `STRAT_SOIL_IMPROVEMENT`).
6. **`income_potential` is permanently `UNKNOWN` in HTTP API/UI:** Requires caller Python dict `economic_data` (`src/api/pipeline_service.py` passes `None`). Consequently its `0.20` default weight is always dropped and renormalized (`1.0 / 0.8 = 1.25x`) across the remaining 6 active objectives, making baseline effective weights: Water `0.3125`, Soil (`0.50` SOC + `0.25` N + `0.25` Erosion) `0.3750` total, Risk (`0.65` Pest + `0.35` Fit) `0.3125` total.
7. **`forage_value` is cleanly gated (`null`/`0.0` -> `NOT_APPLICABLE`),** preserving default core weights when passed alone (`FRM-WT-FORAGE`).
8. **`farmer_priority_fit` exhibits an equipment-warning paradox:** Empty confirmed `[]` scores `1.00` operational points/slot, `UNKNOWN` (`null` or unmodeled tags) scores `0.75`, and `WARNING` falls to `else: 0.45`. Therefore, declaring `equipment_constraints=["no_hay_baler"]` upgrades Durum Wheat & Faba Bean from `UNKNOWN` (`0.75`) to `PASS` (`1.00`) while lowering `VETCH_OAT` from `0.75` to `0.45`—raising `STRAT_SOIL_IMPROVEMENT` mean `ops_pts` from `0.75` to `0.8167` (`+0.003642` composite score gain in `FRM-EQ-NO-HAY-BALER`!).

---

## Task 4 — Unused, Reporting-Only, and Unintegrated Features

Out of **49 geospatial metrics** produced on every analysis call by `field_geospatial_processor.py`:
- **23 `EXTRACTED_ONLY` (Zero Downstream Readers anywhere in `field_profile_builder.py` or `src/`):**
  - 6 SoilGrids subsoil `30–100 cm` layers (`clay_30_100cm`, `sand_30_100cm`, `silt_30_100cm`, `ph_30_100cm`, `soc_30_100cm`, `cec_30_100cm`)
  - 3 Sentinel-2 March 2024 bands (`s2_2024_03_evi_10m`, `s2_2024_03_ndmi_20m`, `s2_2024_03_ndre_20m`)
  - 5 MODIS 250 m layers (`modis_ndvi_autumn_2016_2025_mean`, `modis_evi_{winter,spring,summer,autumn}_2016_2025_mean`)
  - 4 GPM seasonal precipitation totals (`gpm_precip_{winter,spring,summer,autumn}_2016_2025_mean_mm`)
  - 5 SMAP seasonal layers (`smap_rootzone_sm_autumn`, `smap_surface_sm_{winter,spring,summer,autumn}`)
- **11 Reporting / Display-Only / Quarantined / Dead-Module Metrics:**
  - `sand_0_30cm`, `silt_0_30cm`, `cec_0_30cm`, `usda_texture_0_5cm` (never branched in rules/scores), `s2_wilaya_spring_ndvi_climatology_2017_2025`, `modis_ndvi_winter_2016_2025_mean`, `modis_ndvi_summer_2016_2025_mean`, `smap_rootzone_sm_winter_2016_2025_mean`, `smap_rootzone_sm_summer_2016_2025_mean`, `nasa_power_t2m_2016_2025_mean_c`, and quarantined `nitrogen_0_30cm`.
- **3 Dead FAO-56 Inputs (`water_balance.py`):** `nasa_power_rh2m`, `nasa_power_solar_sw`, `dem_elevation_m` are only read by `assess_water_balance_readiness()`, which always terminates in `UNAVAILABLE` because `WS2M` (wind speed), `DEM`, and soil FC/PWP are absent—and **further contains a key lookup bug** (`water_balance.py:187` reads `spatial.get("centroid_lat_lon")` instead of `spatial.get("centroid_lon_lat")`!).
- **Unused Farmer Inputs:** `crop_history[*].planting_month`, `crop_history[*].yield_tons_per_hectare`, and `crop_history[*].notes` are persisted in SQLite (`repository.py`) with zero constraint or scoring effect. `planning.planting_month` only validates past-month errors in `CURRENT_PLANNING` and populates `seasons[0].planting_month` display metadata. `water.availability = "moderate"` vs `"abundant"` are functionally indistinguishable across the entire engine.

---

## Task 5 — Decision Gates & Critical Data Adequacy Audit

1. **Why `completeness_score` diverges from `critical_data_adequacy`:**
   - `_build_data_quality()` computes `completeness_score` unweighted across all `total_geospatial` (49 metrics, including the 23 unused metrics!) plus 3 optional farmer items (`crop_history`, `equipment_constraints`, `forage_value_weight`). On Belkheir baseline, `46/49` geospatial metrics exist (`nitrogen_0_30cm`, `dem_elevation_m`, `dem_slope_pct` are excluded/missing) -> `completeness_score = 46/52 = 0.8846`, even though critical site soil/water/ET0 measurements are absent.
   - `_assess_critical_data_adequacy()` flags **`PARTIAL`** whenever terrain DEM slope, soil/water ECe/ECw salinity, Soil N/P/K, complete multi-year crop history, enterprise budgets, or full FAO-56 inputs are missing; and **`INSUFFICIENT`** if `land_use in {UNVERIFIED, CONFLICTING_EVIDENCE}`, `clay_0_30cm is None`, `clay_0_30cm polygon_coverage_pct < 25%`, or `eligible_count == 0`.
2. **Why `REQUIRES_LOCAL_VERIFICATION` always fires on Guelma:**
   - In `rank_rotation_candidates()`, `FEASIBLE_PASS` and `CONDITIONALLY_FEASIBLE` are unreachable in production because `has_hard_or_critical_unknowns` triggers `REQUIRES_LOCAL_VERIFICATION` whenever `fao56_water_balance_status != "COMPUTED_FULL"` (permanently true) or any `UNKNOWN` rule remains (`RULE_DEM_DRAINAGE_UNCERTAINTY` is permanently `UNKNOWN`, `RULE_SALINITY_UNMEASURED_IRRIGATION` is `UNKNOWN` on irrigated fields, `SEQ_10` is `UNKNOWN` without complete T-1 history).
3. **Can a candidate be endorsed (`endorsed_recommendation_id != None`) despite missing critical evidence?**
   - **YES — verified in two controlled tests (`SG-GAP-PARTIAL-WILAYA` and `SG-GAP-LOW-CF`):** `decision_gate` in `scoring_engine.py` checks only `land_use.get("is_provisional")`, ignoring `critical_data_adequacy`! If a polygon has zero SoilGrids pixels (`clay_val = None`, `clay_cov = 0%`) AND either borders the Wilaya boundary (`wilaya_overlap_pct < 99%`) OR falls into `LAND_USE_LOW_EVIDENCE` (`0.05 <= crop_frequency < 0.40`), `is_provisional` stays `False`. Consequently, `recommendation_builder.py` marks `critical_data_adequacy = "INSUFFICIENT"` (`CRITICAL_BLOCKER`), yet **`decision_gate` still returns `REQUIRES_LOCAL_VERIFICATION` with `suggested_strategy_endorsed = True`!**

---

## Task 6 & Task 7 — Controlled Dependency Test Summary & Existing Test Suite Verification

- **Existing Regression Test Suite:** Executed full `./venv/bin/python -m unittest discover -s tests -v` cleanly -> **`Ran 91 tests in 782.632s — OK` (0 failures, 0 skips)** prior to audit artifact creation; zero repository source or test files were edited.
- **Controlled Phase P Audit Battery (`63` scenarios in [`PHASE_P_CONTROLLED_TEST_RESULTS.csv`](./PHASE_P_CONTROLLED_TEST_RESULTS.csv)):**
  - `20/20` tests varying subsoil layers, `cec_0_30cm`, `sand_0_30cm`, `silt_0_30cm`, `usda_texture_0_5cm`, `soc_0_30cm`, `clay_0_30cm` (`20%..55%`), `ph_0_30cm` (`6.0..7.8` rainfed), thermal Tmax/Tmin (`45°C/-2°C` vs `29°C/10°C`), SMAP rootzone/surface moisture, MODIS EVI/NDVI winter/summer/autumn, S2 EVI/NDMI/NDRE, POWER precip (when GPM present), `yield_tons_per_hectare`, and `planting_month` yielded **`score_delta_vs_base = 0.000000`** on top composite scores.
  - `4/4` real spatial contrast extractions (`Belkheir North`, `Belkheir Peri-Urban Fringe`, `Bouchecouf`, `Tamlouka`) demonstrated that non-water scores remained identical (`0.86`, `0.649`, `1.0`, `0.8667`, `0.825`) across Belkheir North and Bouchecouf (`587.56` vs `581.3 mm`), while only Tamlouka's drop to `440.13 mm` GPM flipped the winner to `STRAT_WATER_CONSCIOUS` (`0.864853` vs `0.854731`).
  - `3` pH tests (`SG-PH-8.6`, `SG-PH-9.1`, `SG-PH-7.8-DRIP-TOMATO`) triggered uncaught `OutputValidationError` (`HTTP 500` equivalent) due to `"INFEASIBLE_CONSTRAINT"` schema enum mismatch.
  - `2` SoilGrids-null gate tests (`SG-GAP-PARTIAL-WILAYA`, `SG-GAP-LOW-CF`) endorsed `STRAT_SOIL_IMPROVEMENT` despite `adequacy_status = "INSUFFICIENT"`.
  - `1` weight test (`FRM-WT-INCOME-ALONE`) returned `NO_RECOMMENDATION` despite valid polygon and feasible crops.
