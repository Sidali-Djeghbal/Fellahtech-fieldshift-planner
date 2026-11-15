# Phase K — Scientific Validation, Agricultural Backtesting & Model Reliability Report

> **Project:** Field Shift — Crop Rotation Decision-Support System (Guelma Wilaya, Algeria)  
> **Phase Scope:** Independent scientific audit of Phases A–J (`CONDITIONAL` readiness verdict; zero feature edits to Phases A–J; zero fabricated field data).  
> **Companion Artifacts:** [`validation_scenarios.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/validation_scenarios.csv), [`validation_scorecard.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/validation_scorecard.csv), [`historical_backtesting_report.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/historical_backtesting_report.md), [`sensitivity_validation_report.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/sensitivity_validation_report.md), [`known_model_risks.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/known_model_risks.md).

---

## 1. Epistemic Framework: Separating Software Tests from Field Truth

Evaluating an agricultural decision-support system requires strictly separating **three validation levels** so engineering success is never mistaken for agronomic proof:

1. **Software & Contract Verification (`PASS`):** Deterministic unit tests (`59` baseline + Phase K validation tests), UTM Zone 32N spatial alignment, temporal non-leakage guards (`CropFreq 2021–2025` masked before 2021), Draft 2020-12 schema conformance, and `null` vs `[]` preservation.
2. **Scientific Rule & Logic Validation (`CONDITIONAL`):** Literature traceability (`FAO-56`, `Sys et al. 1993`, `ITGC Algeria`, `ICARDA`, `FAO EcoCrop`), fail-closed `UNKNOWN` semantics, regional climate/soil responsiveness (`Belkheir`/`Bouchekouf` vs `Tamlouka`/`Oued Zenati`), and stress testing across missing data and `2019`/`2022` extremes.
3. **Real-World Empirical Field Validation (`NOT_VALIDATABLE`):** Statistical benchmarking against measured plot harvest yields (`t/ha`), lab soil cores (`ECe`, `CaCO3`, `Olsen-P`), parcel disease scouting (*Orobanche* / *Fusarium*), and farmgate budgets (`DZD/ha`). **Zero labeled field crop/yield datasets exist in this repository**, so quantitative predictive error (`RMSE`, `R²`, classification `F1`) cannot be measured in Phase K.

---

## 2. Independent Agronomic Knowledge Review (Phase G)

### 2.1 Review of the 13 Crop / System Profiles ([`crop_profiles.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json))

| Crop ID | Family & Lifecycle | `guelma_evidence_status` | Rainfed Precip Floor (`mm`) | N Fixation (`kg N/ha`) | `kc_mid` (`FAO-56`) | Min Break (`yrs`) | Independent Audit Assessment |
|---|---|---|---:|---|---:|---:|---|
| `DURUM_WHEAT` | Poaceae, Annual | `LOCAL_VERIFIED_REGIONAL` | `400.0` | `0.0` | `1.15` | `2` | Scientifically sound staple threshold; explains stress in semi-arid `Tamlouka` dry years (`311.58 mm`). |
| `SOFT_WHEAT` | Poaceae, Annual | `REGIONAL_ALGERIAN_ITGC` | `400.0` | `0.0` | `1.15` | `2` | Sound ITGC rainfed threshold; shares cereal rust/grass-weed break requirements with durum wheat. |
| `BARLEY` | Poaceae, Annual | `LOCAL_VERIFIED_REGIONAL` | `250.0` | `0.0` | `1.15` | `2` | Well-calibrated semi-arid cereal (`>= 250 mm`); anchors `Tamlouka` drought resilience cleanly. |
| `FABA_BEAN` | Fabaceae, Annual | `LOCAL_VERIFIED_REGIONAL` | `450.0` | `100.0–200.0` | `1.15` | `3` | High-value cereal break (`100–200 kg N/ha`), but `450.0 mm` floor sits near northern drought boundary (`444.04 mm` GPM in `2022`). |
| `CHICKPEA_WINTER` | Fabaceae, Annual | `REGIONAL_ALGERIAN_ITGC` | `300.0` | `None` (unquantified) | `1.00` | `3` | Sound ICARDA/ITGC Ascochyta-tolerant winter option; missing local `kg N/ha` range keeps `nitrogen_contribution` at `PARTIAL`. |
| `CHICKPEA_SPRING` | Fabaceae, Annual | `LOCAL_VERIFIED_REGIONAL` | `300.0` | `None` (unquantified) | `1.00` | `3` | Appropriate wet-winter fallback; sensitive to dry terminal springs on shallow soils (DEM slope missing). |
| `LENTIL` | Fabaceae, Annual | `LOCAL_VERIFIED_REGIONAL` | `300.0` | `None` (unquantified) | `1.10` | `3` | Drought-adapted pulse, appropriately gated by `RULE_DEM_DRAINAGE_UNCERTAINTY` against winter waterlogging. |
| `VETCH_OAT` | Fabaceae+Poaceae, Annual | `REGIONAL_ALGERIAN_ITGC` | `300.0` | `None` (unquantified) | `None` | `2` | Proven Algerian fallow-replacement forage; needs DSA confirmation of vetch fraction N-credit & local `kc_mid`. |
| `TOMATO_IND` | Solanaceae, Annual | `LOCAL_VERIFIED_REGIONAL` | `None` (Irrig-gated) | `0.0` | `1.15` | `3` | Major Bouchekouf/Seybouse sector crop; appropriately blocked under `rainfed`/`unknown` water and flagged for `ECe` test. |
| `POTATO` | Solanaceae, Annual | **`HYPOTHESIS_NEEDS_DSA_CHECK`** | `None` (Irrig-gated) | `0.0` | `1.15` | `3` | Correctly tagged unverified for local Guelma clay soils; heavy clay compaction/drainage risk warrants DSA check. |
| `SUNFLOWER` | Asteraceae, Annual | **`HYPOTHESIS_NEEDS_DSA_CHECK`** | `500.0` | `0.0` | `None` | `3` | Appropriately flagged `HYPOTHESIS_NEEDS_DSA_CHECK`; oilseed supply-chain feasibility in Guelma unconfirmed. |
| `OLIVE` | Oleaceae, Perennial | `LOCAL_VERIFIED_REGIONAL` | `350.0` | `0.0` | `None` | `None` | Hard-excluded (`in_annual_rotation_scope = False`) from annual crop sequences (`RULE_PERENNIAL_EXCLUSION`). |
| `BARE_FALLOW` | Uncropped Period | `LOCAL_VERIFIED_REGIONAL` | `0.0` | `0.0` | `None` | `1` | Valid baseline counterfactual; erosion & SOC oxidation penalties prevent unprompted recommendation. |

### 2.2 Review of the 15 Individual Crop Rules ([`constraint_rules.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/constraint_rules.json))

| Classification | Count | Rules Included | Audit Assessment |
|---|---:|---|---|
| `HARD_CONSTRAINT` | `3` | `RULE_PERENNIAL_EXCLUSION`, `RULE_PLANTING_SEASON_COMPATIBILITY`, `RULE_WATER_IRRIGATION_GATE` | **Strong & fail-closed.** Never forces irrigation passes when water is unknown; blocks perennial `OLIVE` cleanly. |
| `SOFT_CONSTRAINT` | `9` | `RULE_PRECIPITATION_REGIME`, `RULE_THERMAL_HEAT_FROST`, `RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT`, `RULE_SOIL_TEXTURE_WORKABILITY`, `RULE_SOIL_PH_SUITABILITY`, `RULE_SOIL_SOC_PRIORITY`, `RULE_CROPLAND_VEG_CONTEXT`, `RULE_HYPOTHESIS_LOCAL_EVIDENCE_STATUS`, `RULE_EQUIPMENT_CONSTRAINT_CHECK` | **Literature-aligned.** Propagates `UNKNOWN` cleanly on urban/small-plot SoilGrids nulls (`1.79 ha` Belkheir, `Oued Zenati`) and preserves `null` vs `[]`. Climate rules remain limited by `11–69 km` pixel scale. |
| `EXPERT_ASSUMPTION` | `2` | `RULE_DEM_DRAINAGE_UNCERTAINTY`, `RULE_FORAGE_REQUIREMENT_ALIGNMENT` | **Honest placeholder logic.** Clearly marked non-empirical; DEM relief integration is essential before autonomous release. |
| `UNKNOWN` | `1` | `RULE_SALINITY_UNMEASURED_IRRIGATION` | **Crucial safeguard.** Prevents blind promotion of irrigated `TOMATO_IND` / `POTATO` in salinity-prone `Seybouse` perimeters without `ECe`/`ECw` labs. |

### 2.3 Review of the 10 Sequence Rules ([`sequence_compatibility.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/sequence_compatibility.json))
- **`HARD_CONSTRAINT` (6 rules):** `SEQ_01_PERENNIAL_GUARD`, `SEQ_02_CEREAL_REPETITION`, `SEQ_03_SOLANACEAE_BREAK` (`3–4` yr guard matching `Cahiers Agricultures Bouchegouf` context), `SEQ_04_PULSE_BROOMRAPE_BREAK` (`Orobanche crenata` / `Ascochyta`), `SEQ_05_SUNFLOWER_BREAK`, `SEQ_08_BARE_FALLOW_COVER`. All scientifically defensible structural rotation guards.
- **`SOFT_CONSTRAINT` (2 rules):** `SEQ_06_VETCH_OAT_ROLE_AND_REPEAT` and `SEQ_07_LEGUME_CEREAL_SYNERGY` (well-established Mediterranean legume-cereal N/break synergy).
- **`EXPERT_ASSUMPTION` (1 rule) & `UNKNOWN` (1 rule):** `SEQ_09_WATER_COMPETITION_AND_CALENDAR` (heuristic moisture carry-over/harvest overlap—requires local soil water balance tuning) and `SEQ_10_UNKNOWN_PREDECESSOR_GUARD` (prevents silent break-assumption when farmer history is missing).

---

## 3. Evaluation of Phase H Candidate Generator, Phase I Scoring & Phase J Output

### 3.1 Phase H Candidate Patterns
- Generates up to `8` deterministic candidates spanning `2–4` seasons across six structural archetypes: `STRAT_CEREAL_LEGUME`, `STRAT_CEREAL_FORAGE`, `STRAT_SOIL_IMPROVEMENT`, `STRAT_WATER_CONSCIOUS`, `STRAT_IRRIGATED_CASH`, and `STRAT_EXISTING_BASELINE` (counterfactual comparison even when agronomically infeasible).
- **Strength:** Preserves infeasible targets/baselines for transparency rather than hiding failures; avoids duplicate sequences; honors optional planting month bounds (`CROP_VALID_PLANTING_MONTHS`) and missing-history rules.
- **Limitation:** Evaluates seasonal sequences chronologically without modeling multi-parcel labor allocation or sub-month sowing window delays.

### 3.2 Phase I 8-Objective Scoring, Pareto Dominance & Sensitivity
- Evaluates 8 explicitly separated dimensions: `water_efficiency`, `soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, `income_potential`, `forage_value`, `farmer_priority_fit`.
- **Crucial Safeguards Verified:**
  - `income_potential` stays `UNKNOWN` (excluded from active weighted average) without farmgate price/cost budgets—never zero-coerced.
  - `forage_value` stays `NOT_APPLICABLE` when `forage_value_weight` is `null` or `0.0`, becoming active only when positive weight (`> 0`) is supplied (`BELKHEIR_HIGH_FORAGE` raises active count from `6` to `7` and promotes `STRAT_CEREAL_FORAGE` cleanly with `0.104668` margin).
- **Documented Quantitative Limitations:**
  - `soil_improvement` indexes qualitative KB SOM direction (`_SOM_DIRECTION_SCORES`), so `SENS_BOU_PARTIAL_SOILGRIDS` shifts `status` to `PARTIAL` while holding numeric score constant (`0.876238`).
  - `nitrogen_contribution` stays `PARTIAL` on rotations containing chickpea/lentil/vetch-oat because only `FABA_BEAN` has quantified `100–200 kg N/ha`.
  - Phase I tie-breaker (`(-weighted_score, is_non_pareto_front, -pass_rule_count, strategy_id)`) cleanly separates close Pareto alternatives (`margin = 0.003394` on default `BELKHEIR_RAINFED`), while `sensitivity.py` (`19` or `22` perturbations) transparently distinguishes mathematical weight robustness from empirical accuracy.

### 3.3 Phase J Output Contract Reliability
- Tested across all `17` representative spatial, temporal backtest, and stress-degradation scenarios in [`validation_scenarios.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/validation_scenarios.csv):
  - **`schema_valid = True` (`17/17`, 0 Draft 2020-12 structural or semantic errors)**,
  - `completeness_score` (`0.8846` baseline; adjusts cleanly when S2 drops) remains strictly isolated from heuristic ranking scores,
  - `recommendation_status` consistently stays `CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION` whenever `DEM`, `ECe`, or `HYPOTHESIS_NEEDS_DSA_CHECK` uncertainty exists—refusing false certainty.

---

## 4. Regional Agro-Ecological Plausibility Check (`Guelma` Spatial & Historical Matrix)

Qualitative comparison against Guelma sector morphology (**note: regional structural coherence checks model plausibility only and does not constitute parcel yield validation**):

| Agro-Ecological Zone (Verified Scenarios) | Modeled Inputs Observed | Top Strategy Selected | Regional Plausibility vs. DSA/ITGC Expectations |
|---|---|---|---|
| **Alluvial Seybouse & Humid Plains** (`Belkheir 298.31 ha`, `Boumahra 24.86 ha`, `Bouchekouf 35.79 ha`) | `565.94–581.30 mm` GPM; `33.76%–35.32%` clay; `12.85–16.20 g/kg` SOC | `STRAT_SOIL_IMPROVEMENT` (`0.876144`–`0.891894`) | **Plausible:** Sub-humid Seybouse plains traditionally anchor cereal-pulse (`Faba Bean / Durum Wheat / Vetch-Oat`) intensification, conditional on drainage checks and `ECe` screening for irrigated `TOMATO_IND`. |
| **Semi-Arid Southern Plains** (`Tamlouka 24.97 ha`) | `440.13 mm` GPM (`508.07 mm` POWER); `30.13%` clay; `13.00 g/kg` SOC | `STRAT_WATER_CONSCIOUS` (`0.859228`; `0.765384` in `2022` drought) | **Plausible:** Drier southern interior (`< 460 mm`) favors barley + chickpea drought-escape over high-water wheat/faba intensification. |
| **Interior Urban-Edge Parcel** (`Oued Zenati 35.87 ha`) | `500.26 mm` GPM; `clay = null`, `soc = null` (urban mask) | `STRAT_WATER_CONSCIOUS` (`0.859228`) | **Plausible & Safe:** Emits `UNKNOWN` soil rules cleanly and defaults toward conservative water-conscious cereals without fabricating masked pixel soils. |
| **Small Parcel / Cross-Border Boundary** (`Belkheir 1.79 ha`; `Bouchekouf 3971.84 ha`, `32.0043%` overlap) | `1.79 ha` `clay=null`; cross-border clipped SOC `28.0231 g/kg` | `STRAT_SOIL_IMPROVEMENT` (`0.876238` / `0.882737`) | **Plausible with Warning:** Partial overlap triggers cross-border advisory notice; small-plot `250 m` SoilGrids masking triggers `PARTIAL` soil status rather than false certainty. |

---

## 5. Final Component & Readiness Scorecard (`Section 9` Summary)

Reproduced directly from [`validation_scorecard.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/validation_scorecard.csv):

| Component | Verdict | Software Status | Scientific Rule & Logic Status | Empirical Field Validation |
|---|---|---|---|---|
| **Geospatial Data (Phases A–F)** | **`CONDITIONAL`** | `PASS` (15 tests) | `CONDITIONAL` (UTM 32N & non-leakage clean; DEM absent; N quarantined; 11–69 km macro-scale) | `NOT_VALIDATABLE` (no field cores / gauges) |
| **Agronomic Knowledge (Phase G)** | **`CONDITIONAL`** | `PASS` (11 tests) | `CONDITIONAL` (13/15 crop rules & 9/10 sequence rules literature-backed; `POTATO`/`SUNFLOWER` unverified) | `NOT_VALIDATABLE` (no local trial matrix) |
| **Crop Sequence Generation (Phase H)** | **`PASS`** | `PASS` (10 tests) | `PASS` (diverse archetypes; deterministic; excludes `OLIVE` & respects T-1 break guards) | `NOT_VALIDATABLE` (pending farmer audit) |
| **Objective Scoring (Phase I)** | **`CONDITIONAL`** | `PASS` (10 tests) | `CONDITIONAL` (no zero-coercion; captures `2022` `PRECIP_SENSITIVE_RANK_SHIFT`; ordinal SOM & missing economic budgets) | `NOT_VALIDATABLE` (no profit/yield budgets) |
| **Final Output Contract (Phase J)** | **`PASS`** | `PASS` (8 tests + `17/17` stress valid) | `PASS` (Draft 2020-12 compliant; strict `EvidenceItem` provenance; refuses forced winners) | `CONDITIONAL` (pending advisor UX test) |
| **Empirical Yield & Crop Accuracy** | **`NOT_VALIDATABLE`** | `N/A` (no ML model trained) | `NOT_VALIDATABLE` (`0` labeled parcel crop/yield rows on disk) | **`NOT_VALIDATABLE`** |
| **Overall System Readiness** | **`CONDITIONAL`** | `PASS` (complete automated suite) | `CONDITIONAL` (scientifically coherent & fail-closed under conditional banners) | **`BLOCKED_FOR_AUTONOMOUS_FARMER_RELEASE_UNTIL_FIELD_GATES_PASS`** |

---

## 6. Recommended Next Steps Before Autonomous Deployment

Following Phase E's pre-deployment gates ([`validation_strategy.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/validation_strategy.md)), deploy only after executing:
1. **ITGC & DSA Agronomic Delphi Check (Pillar 2):** Obtain formal local sign-off on `POTATO`, `SUNFLOWER`, `VETCH_OAT` N-credit, and `EXPERT_ASSUMPTION` thresholds (`RULE_DEM_DRAINAGE_UNCERTAINTY`, `SEQ_09`).
2. **Ground Soil Lab & Weather Station Calibration (Pillar 4):** Collect `30–50` geo-referenced lab cores (`ECe`, `CaCO3`, `Olsen-P`, `pH`, `SOC`, texture) across North/Central/South Guelma and calibrate `GPM`/`NASA POWER` against `ONM`/`ANRH` stations (resolving the `~+132 mm/yr` historical offset and `2022` rank flip).
3. **DEM Slope Integration:** Add 10–30 m DEM topography (`SRTM` / `ALOS`) to replace `UNAVAILABLE_NOT_INTEGRATED` drainage proxies.
4. **DSA Commune Yield & Participatory Farmer Audit (Pillars 3 & 5):** Collect historical commune yields (`t/ha`), enterprise farmgate budgets (`DZD/ha`), and run structured usability/trust reviews with `30–60` farmers and DSA advisors across Belkheir, Bouchekouf, Oued Zenati, and Tamlouka.
