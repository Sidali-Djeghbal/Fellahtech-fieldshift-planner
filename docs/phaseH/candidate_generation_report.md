# Phase H — Crop Rotation Candidate Generation Report

**Project:** Field Shift — Guelma Wilaya Crop Rotation Decision-Support System  
**Implementation:** [`src/rotation/__init__.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/__init__.py), [`src/rotation/candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py)  
**Test Suite:** [`tests/test_phaseH_candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseH_candidate_generator.py)  
**Sample Output:** [`docs/phaseH/sample_candidate_generation_output.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseH/sample_candidate_generation_output.json)

---

## 1. Executive Summary

Phase H implements a deterministic, single-field crop rotation candidate generator integrating Phase F geospatial Field Profiles with Phase G single-crop (15 rules) and sequence-level (10 rules) agronomic constraint evaluation.

- **No Phase I Ranking Performed:** Phase H produces structurally diverse, rule-verified candidate portfolios (`ranking_executed: false`) ready for Phase I multi-objective scoring.
- **No Phases A–G Modified:** All Phase D–G code, schemas, knowledge bases, and tests remain untouched.
- **Zero Google Earth Engine Tasks:** All execution runs strictly on verified local geospatial datasets.
- **Full Regression Suite Verification:** `PYTHONPATH=. /home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m unittest discover -s tests -v` ran **41 tests in 129.229s — OK** (`0` failures, `0` skips across Phases D, F, G, and H).

---

## 2. Verification Sample Scenario (`F_BOU_SAMPLE_01`)

To ground Phase H behavior on real Guelma data, `generate_rotation_candidates()` was executed on a `24.8577 ha` irrigated parcel in **Belkheir / Boumahra Ahmed** (`wilaya_overlap_pct = 100.0%`, `USDA texture = Clay loam`, modeled `clay_0_30cm = 33.7561%`, `ph_0_30cm = 7.3667`, `soc_0_30cm = 12.8532 g/kg`, `gpm_annual_precip_mm = 566.28 mm`, `nasa_power_annual_precip_mm = 736.84 mm`).

### Scenario Inputs
- **Water:** `availability = "abundant"`, `source = "reservoir"`, `irrigation_system = "drip"`
- **Crop History:** `2024 Autumn: Ble dur -> DURUM_WHEAT`, `2025 Autumn: Faba bean -> FABA_BEAN`
- **Planning:** `start_season = "Autumn"`, `start_year = 2026`, `horizon_seasons = 3`, `planting_month = 11`
- **Preferences:** `target_crop_ids = ["TOMATO_IND", "SUNFLOWER"]`, `excluded_crop_ids = ["BARLEY"]`, `equipment_constraints = []` (`EXPLICITLY_CONFIRMED_EMPTY`), `forage_value_weight = null` (`NOT_PROVIDED`)

### Candidate Generation Summary (`F_BOU_SAMPLE_01`)
- `total_candidates`: **6** (`duplicates_skipped_count = 1`)
- `feasible_pass_count`: **0** (honest reflection of unmeasured field DEM & ECe/ECw)
- `conditionally_feasible_count`: **5** (`CAND_01`..`CAND_05`)
- `infeasible_count`: **1** (`CAND_06`, `EXISTING_ROTATION_BASELINE`)
- `existing_baseline_generated`: **`true`**

| Candidate ID | Pattern ID | Selection Status | Feasibility Verdict | Crop Sequence (`2026 -> 2027 -> 2028`) | Rule Counts (`P / W / F / U`) |
|---|---|---|---|---|---|
| `CAND_01` | `CEREAL_LEGUME` | `SELECTED_CANDIDATE_ELIGIBLE` | `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` | `DURUM_WHEAT` (Aut) -> `CHICKPEA_WINTER` (Aut) -> `DURUM_WHEAT` (Aut) | `35 / 8 / 0 / 7` |
| `CAND_02` | `CEREAL_FORAGE` | `SELECTED_CANDIDATE_ELIGIBLE` | `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` | `DURUM_WHEAT` (Aut) -> `VETCH_OAT` (Aut) -> `DURUM_WHEAT` (Aut) | `38 / 6 / 0 / 6` |
| `CAND_03` | `SOIL_IMPROVEMENT` | `SELECTED_CANDIDATE_ELIGIBLE` | `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` | `VETCH_OAT` (Aut) -> `DURUM_WHEAT` (Aut) -> `VETCH_OAT` (Aut) | `38 / 6 / 0 / 6` |
| `CAND_04` | `IRRIGATED_CASH_BREAK` | `SELECTED_CANDIDATE_ELIGIBLE` | `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` | `DURUM_WHEAT` (Aut) -> `TOMATO_IND` (Spr) -> `FABA_BEAN` (Aut) | `36 / 7 / 0 / 8` |
| `CAND_05` | `FARMER_TARGET_SUNFLOWER` | `SELECTED_CANDIDATE_ELIGIBLE` | `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` | `DURUM_WHEAT` (Aut) -> `SUNFLOWER` (Spr) -> `DURUM_WHEAT` (Aut) | `35 / 8 / 0 / 6` |
| `CAND_06` | `EXISTING_ROTATION_BASELINE` | `EXISTING_BASELINE_EVALUATED` | `INFEASIBLE_HARD_CONSTRAINT` | `DURUM_WHEAT` (Aut) -> `FABA_BEAN` (Aut) -> `DURUM_WHEAT` (Aut) | `37 / 5 / 1 / 7` |

### Key Scientific Insights From `F_BOU_SAMPLE_01`
1. **Historical Baseline Failure Exposed (`CAND_06`):** Repeating the farmer's historical `2024 DURUM_WHEAT -> 2025 FABA_BEAN` cycle places `FABA_BEAN` again in `2027`—only 2 years apart—triggering a hard failure on `SEQ_04_PULSE_BROOMRAPE_BREAK` (`<3` years food legume / broomrape interval). Meanwhile `CAND_01` automatically shifts the legume break to `CHICKPEA_WINTER` to avoid the *Orobanche* hazard while preserving nitrogen fixation.
2. **Farmer Preferences Honored Without Compromising Constraints:** Both requested targets (`TOMATO_IND` via `CAND_04` and `SUNFLOWER` via `CAND_05`) were integrated into compatible `Spring` slots (`2027`), while `BARLEY` (`excluded_crop_ids`) remained completely excluded.
3. **No False Certainty (`feasible_pass_count = 0`):** Every candidate retains unresolved `UNKNOWN` items in `information_gaps` (missing DEM drainage/slope `UNAVAILABLE_NOT_INTEGRATED`, unmeasured reservoir irrigation salinity `ECe/ECw` in `RULE_SALINITY_UNMEASURED_IRRIGATION`, and `forage_value_weight = NOT_PROVIDED`), alongside regional `WARNING` items (ESA `crop_frequency_2021_2025 = 0.0561`, `GPM vs NASA POWER` rainfall divergence, and clay workability).

---

## 3. Automated Verification Coverage

[`tests/test_phaseH_candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseH_candidate_generator.py) contributes **10 dedicated unit/integration tests** verifying:
1. Valid planning horizons (`2`, `3`, `4`) and rejection of horizons outside `2..4`.
2. Strict separation between `crop_history = null` (`NOT_PROVIDED`) vs `[]` (`EXPLICITLY_CONFIRMED_EMPTY`), suppression of `EXISTING_ROTATION_BASELINE`, and preservation of `SEQ_10_UNKNOWN_PREDECESSOR_GUARD = UNKNOWN`.
3. `EXISTING_ROTATION_BASELINE` synthesis when `>= 2` recent resolved history seasons end at `start_year - 1`, and enforcement of the `T-1 -> T0` break boundary.
4. Detection of `SEQ_04_PULSE_BROOMRAPE_BREAK` hard failure on the projected existing baseline.
5. `target_crop_ids` vs `excluded_crop_ids` precedence (`excluded_crop_ids` overrides targets; `OLIVE` emits counterfactual `REQUESTED_TARGET_OLIVE` with `INFEASIBLE_HARD_CONSTRAINT` and `not_included_reasons`).
6. Preservation of optional `forage_value_weight` and `equipment_constraints` `null` vs `[]`.
7. Hard water gate failure (rainfed `TOMATO_IND` -> `INFEASIBLE_HARD_CONSTRAINT`) and `UNKNOWN` water gating (`availability="unknown"` -> `UNVERIFIED_HARD_UNKNOWN`, `feasible=False`).
8. Sequence deduplication, contiguous `CAND_01..CAND_NN` numbering even when `include_infeasible_existing_baseline=False`, and deterministic repeated execution.
9. One-field-per-request enforcement and verification that zero Phase I scoring/ranking keys appear.
10. Spring-start season compatibility (`start_season="Spring"`).

Across the entire repository, all **41 automated tests** (`test_phaseD_integration.py`, `test_field_profile.py`, `test_phaseF_audit.py`, `test_phaseG_knowledge.py`, `test_phaseH_candidate_generator.py`) passed with zero failures or skips.

---

## 4. Known Missing Evidence & Limitations Carried Forward to Phase I

1. **Missing Local DEM Slope (`UNAVAILABLE_NOT_INTEGRATED`):** High waterlogging sensitivity crops (`CHICKPEA_WINTER`, `FABA_BEAN`, `TOMATO_IND`) carry `UNKNOWN` ponding risk pending field drainage verification.
2. **Unmeasured Soil & Irrigation Salinity (`ECe`/`ECw`):** Irrigated candidates (`CAND_04`, `CAND_05`, or irrigated baselines) trigger `RULE_SALINITY_UNMEASURED_IRRIGATION` (`UNKNOWN`) requiring pre-season water/soil salinity testing.
3. **SoilGrids 250 m & Climate Macro Support:** Modeled `SoilGrids V6` properties (`Nitrogen` quarantined) and coarse `GPM`/`SMAP`/`POWER` macro series remain non-equivalent to laboratory sampling or on-farm rain gauges.
4. **Deferred Multi-Year Sentinel-2 Time Series:** Field-level vegetation relies on the `2024-03` 10 m/20 m snapshot and `2016–2025` MODIS 250 m seasonal series until multi-year S2 rasters are exported.
