# Phase K — Climate, Missing-Data & Weight Sensitivity Validation Report

> **Scope:** Independent stress testing of Field Shift Phases F–J across precipitation dataset disagreement (`GPM IMERG` vs. `NASA POWER`), degraded geospatial inputs (`SoilGrids`, `Sentinel-2`, missing `DEM`, unknown water/salinity, cross-border polygons), and Phase I multi-objective weight perturbations.

---

## 1. Sensitivity Testing vs. Scientific Confidence (Essential Distinction)

A high `stability_index` in Phase I measures **internal ranking consistency** across alternative linear objective weights (equal weights, OAT `+/- 25%`, and `0.65` dominant focus scenarios). It does **not** prove yield accuracy, true soil carbon gain, or local farm profitability. Conversely, when a realistic stress scenario flips the top recommendation (e.g., `PRECIP_SENSITIVE_RANK_SHIFT`), that reveals genuine biophysical boundary fragility that farmers and advisors must see explicitly.

---

## 2. Stress Test Matrix: Missing Data, Spatial Edge Cases & Climate Divergence

Verified directly from live end-to-end executions saved in [`validation_scenarios.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/validation_scenarios.csv):

| Stress Scenario ID | Perturbation Tested | Key Degraded / Shifted Values | Suggested Strategy | Weighted Score | Schema Valid | Observed Scientific & Behavioral Response |
|---|---|---|---|---:|:---:|---|
| `BACKTEST_BOU_2022_DRY_SHOCK` | **Climate Dataset Divergence (2022 Drought)** | `GPM = 444.04 mm` vs `POWER = 608.94 mm` | `STRAT_WATER_CONSCIOUS` | `0.859228` | `True` | **`PRECIP_SENSITIVE_RANK_SHIFT`**: GPM falls below `FABA_BEAN` `450 mm` gate and flips top strategy to Barley/Chickpea; POWER keeps `STRAT_SOIL_IMPROVEMENT` |
| `BACKTEST_TAM_2022_DRY_SHOCK` | **Severe Semi-Arid Drought Shock (2022)** | `GPM = 311.58 mm`, `POWER = 426.29 mm` | `STRAT_WATER_CONSCIOUS` | `0.765384` | `True` | `ROBUST_GPM_AND_POWER`: both datasets agree on drought escape; sharp drop from `0.859228` to `0.765384` reflects wheat/faba rainfall deficit cleanly |
| `SENS_BOU_PARTIAL_SOILGRIDS` | **Missing SoilGrids (`clay=null`, `soc=null`)** | `soil_clay_pct = null`, `soil_soc_g_kg = null` | `STRAT_SOIL_IMPROVEMENT` | `0.876238` | `True` | Soil rules report `UNKNOWN`; `soil_improvement` drops cleanly to `PARTIAL`—**caveat:** ordinal KB direction keeps numeric score `0.876238` unchanged |
| `SPAT_BOU_SMALL_2HA_RAINFED` | **Small Polygon (`1.79 ha`) Sub-Pixel Mask** | `clay = null`, `soc = 13.52 g/kg`, `crop_freq = 0.0` | `STRAT_SOIL_IMPROVEMENT` | `0.876238` | `True` | SoilGrids `250 m` clay mask propagates cleanly (`PARTIAL` soil status) without crashing |
| `SPAT_OUED_ZENATI_RAINFED` | **Urban Edge Masking (`Oued Zenati`)** | `clay = null`, `soc = null`, `crop_freq = 0.0002` | `STRAT_WATER_CONSCIOUS` | `0.859228` | `True` | All soil texture/SOC rules stay `UNKNOWN`; water regime still governs `STRAT_WATER_CONSCIOUS` cleanly |
| `SENS_BOU_REDUCED_S2_NULL` | **Dropped Sentinel-2 (`2024-03` NDVI `null`)** | `s2_2024_03_ndvi = null` | `STRAT_SOIL_IMPROVEMENT` | `0.876238` | `True` | Removes S2 bare-field vigor context cleanly (`0` crashes) with zero distortion to crop-sequence ranking |
| `SENS_BOU_UNKNOWN_WATER` | **Unknown Water Availability & Source** | `water = unknown` | `STRAT_SOIL_IMPROVEMENT` | `0.876238` | `True` | `RULE_WATER_IRRIGATION_GATE` blocks irrigated `TOMATO_IND` (`UNVERIFIED_HARD_UNKNOWN`); rainfed strategies stay eligible with `water_efficiency = PARTIAL` |
| `SPAT_BORDER_PARTIAL_WILAYA` | **Cross-Border Polygon (`3971.84 ha`, `32.0043%` inside Guelma)** | `soc = 28.0231 g/kg` on clipped piedmont | `STRAT_SOIL_IMPROVEMENT` | `0.882737` | `True` | Spatial boundary warning emitted while clipped pixels execute reproducibly; external `68%` area unmodeled |
| Global Baseline Structural Check | **Missing DEM Slope + Unknown ECe Salinity** | `DEM = UNAVAILABLE_NOT_INTEGRATED`; `ECe = null` | All scenarios | `—` | `True` | `RULE_DEM_DRAINAGE_UNCERTAINTY` & `RULE_SALINITY_UNMEASURED_IRRIGATION` hold `recommendation_status = CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION` across 100% of runs |

---

## 3. Weight Perturbation & Preference-Boundary Analysis (Phase I Sensitivity Engine)

Live tests via `src/optimization/sensitivity.py` evaluated `19` perturbation scenarios when forage is inactive (`EQUAL_ACTIVE_WEIGHTS`, 12 OAT `+/- 25%` perturbations on the 6 weighted objectives, and 6 domain focus `0.65` stress runs) and `22` scenarios when `forage_value_weight` is active (observed via `BELKHEIR_RAINFED`, `BELKHEIR_HIGH_FORAGE`, `TAMLOUKA_RAINFED`, `TAMLOUKA_SOIL_EMPHASIS`):

| Preference Stress Test | Top Strategy | Scenarios Evaluated | Winner Changes | `stability_index` | Top-2 Score Margin | Scenarios That Flip Winner |
|---|---|---:|---:|---:|---:|---|
| `BELKHEIR_RAINFED` (`1-yr Durum Wheat` history, default weights) | `STRAT_WATER_CONSCIOUS` | `19` | `6` | `0.6842` | **`0.003394`** | `EQUAL_ACTIVE_WEIGHTS -> STRAT_CEREAL_FORAGE`, `FOCUS_SOIL_IMPROVEMENT -> STRAT_CEREAL_FORAGE`, `FOCUS_NITROGEN_CONTRIBUTION -> STRAT_SOIL_IMPROVEMENT`, `FOCUS_PEST_DISEASE_DISRUPTION -> STRAT_CEREAL_FORAGE`, `FOCUS_EROSION_PROTECTION -> STRAT_CEREAL_FORAGE`, `FOCUS_FARMER_PRIORITY_FIT -> STRAT_CEREAL_FORAGE` |
| `BELKHEIR_HIGH_FORAGE` (`forage_value_weight = 0.60`) | `STRAT_CEREAL_FORAGE` | `22` | `2` | `0.9091` | `0.104668` | `FOCUS_WATER_EFFICIENCY -> STRAT_WATER_CONSCIOUS`, `FOCUS_NITROGEN_CONTRIBUTION -> STRAT_SOIL_IMPROVEMENT` |
| `TAMLOUKA_RAINFED` (default weights, `440.13 mm` GPM) | `STRAT_WATER_CONSCIOUS` | `19` | `3` | `0.8421` | `0.036331` | `FOCUS_SOIL_IMPROVEMENT -> STRAT_SOIL_IMPROVEMENT`, `FOCUS_NITROGEN_CONTRIBUTION -> STRAT_SOIL_IMPROVEMENT`, `FOCUS_EROSION_PROTECTION -> STRAT_CEREAL_FORAGE` |
| `TAMLOUKA_SOIL_EMPHASIS` (`soil_improvement_weight = 0.50`) | `STRAT_WATER_CONSCIOUS` | `19` | `3` | `0.8421` | `0.010758` | `FOCUS_SOIL_IMPROVEMENT -> STRAT_SOIL_IMPROVEMENT`, `FOCUS_NITROGEN_CONTRIBUTION -> STRAT_SOIL_IMPROVEMENT`, `FOCUS_EROSION_PROTECTION -> STRAT_CEREAL_FORAGE` |

### Key Analytical Takeaways
1. **Tight Top Cluster in Humid Rainfed Zones (`margin = 0.003394`):** When rainfed plots in northern/central Guelma (`Belkheir`) lack strong livestock-forage or cash preferences, `STRAT_WATER_CONSCIOUS`, `STRAT_CEREAL_FORAGE`, and `STRAT_SOIL_IMPROVEMENT` sit nearly tied (`0.0034` margin, `stability_index = 0.6842`). This is agronomically realistic: multiple diversified cereal-pulse/forage rotations are genuinely viable on deep northern clay loams, so small priority shifts naturally switch preferences among Pareto equals rather than relying on one fragile monoculture.
2. **Clear Separation Under Semi-Arid Stress & Explicit Farmer Priorities:** In `Tamlouka` (`440.13 mm` GPM), `STRAT_WATER_CONSCIOUS` holds a `0.036331` margin (`stability_index = 0.8421`) even if soil weight rises to `0.50` (`margin = 0.010758`), flipping only under extreme `0.65` soil/nitrogen overrides. Similarly, when livestock forage (`forage_value_weight = 0.60`) is requested, `STRAT_CEREAL_FORAGE` separates decisively (`margin = 0.104668`, `stability = 0.9091`).
3. **Graceful Degradation Guarantee:** Across every missing-data and climate stress case tested, zero crashes, zero silent `null -> 0` imputations, and `0` Draft 2020-12 schema violations occurred.

---

## 4. Sensitivity Validation Verdict

- **Degradation & Structural Robustness:** **PASS** (100% graceful handling of missing SoilGrids, missing Sentinel-2, unknown water, missing DEM, unmeasured ECe, small polygons, and cross-border clips).
- **Climate-Source Robustness Caveat:** **CONDITIONAL** due to `PRECIP_SENSITIVE_RANK_SHIFT` (`GPM` vs `NASA POWER` discrepancy around the `450 mm` rainfed legume threshold in dry years such as `2022`).
- **Heuristic Scoring Sensitivity Caveat:** **CONDITIONAL** because `soil_improvement` remains insensitive to missing `SoilGrids` numerics (`0.876238` unchanged except `status = PARTIAL`) and `income_potential` remains inactive (`UNKNOWN`).
