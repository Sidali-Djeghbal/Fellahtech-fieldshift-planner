# Phase I — Multi-Objective Scoring Methodology

**Project:** Field Shift — Guelma Wilaya Crop Rotation Decision-Support System  
**Module:** [`src/optimization/scoring_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py)  
**Data Dictionary:** [`docs/phaseI/scoring_data_dictionary.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseI/scoring_data_dictionary.csv)

---

## 1. Core Evidence Governance Rules

Phase I consumes Phase H candidate strategies (`seasons`, `constraint_evaluations`, `field_insights`, `history_assessment`, `preference_handling`) alongside optional `field_profile` priority weights and optional verified `economic_data`. No candidates are generated in Phase I, and Phases A–H remain untouched.

1. **Explicit Objective Status Partition:** Every objective returns `score` (`float in [0, 1]` or `null`), `status` in `{"SCORED", "PARTIAL", "UNKNOWN", "NOT_APPLICABLE"}`, `evidence`, `evidence_classification`, `confidence_or_uncertainty`, `missing_information`, `applicability_condition`, and `explanation`.
2. **No Zero-Coercion of Missing Inputs:** Missing variables (`UNKNOWN`) or inactive requirements (`NOT_APPLICABLE`) retain `score = null` and are excluded from both Pareto dominance comparisons and weighted scoring denominators.
3. **SoilGrids Nitrogen Quarantine Respected:** SoilGrids `nitrogen_0_30cm` (`UNVALIDATED_EXCLUDED`) is strictly excluded from all nitrogen and soil formulas.

---

## 2. Independent Objective Specifications

### 2.1 `water_efficiency` (Water Efficiency & Drought Safety)
- **Definition:** Alignment between seasonal crop water requirements, rainfall buffer headroom, and field irrigation reliance, rewarding drought-escaping rainfed systems and penalized high-ET blue-water extraction.
- **Calculation Method:**
  - `BARE_FALLOW`: slot score `0.60`.
  - `STRICTLY_IRRIGATED` (`TOMATO_IND`, `POTATO`): `0.40` (`drip`), `0.30` (`sprinkler`), `0.20` (`surface`/`other`), `0.0` (`rainfed`/`none`).
  - Rainfed-capable crops (`RAINFED_SEMI_ARID_TOLERANT`, `RAINFED_OR_SUPPLEMENTAL`):
    $$\text{headroom} = \text{clip}\left(\frac{P_{\text{gpm}} - P_{\min}}{300.0}, -0.35, 0.45\right)$$
    $$\text{slot\_score} = \text{clip}(0.40 + \text{headroom} + \text{category\_bonus} + \text{irrig\_buffer}, 0.0, 1.0)$$
    where `category_bonus = 0.15` for `RAINFED_SEMI_ARID_TOLERANT` and `0.05` for `RAINFED_OR_SUPPLEMENTAL`; `irrig_buffer = 0.05` when declared irrigation is active (`availability` in `{abundant, moderate}` and `source != rainfed`).
  - Sequence score = arithmetic mean over horizon slots; evaluated in parallel under `nasa_power_annual_precip_mm` (`score_power`) for climate spread tracking.
- **Input Variables:** `gpm_annual_precip_mm`, `nasa_power_annual_precip_mm`, `water.availability`, `water.source`, `water.irrigation_system`, KB `water_requirement_category`, `min_annual_rainfed_precip_mm`.
- **Units:** Normalized `[0, 1]` index (inputs in `mm/yr`).
- **Source Datasets / Rules:** GPM 11 km (2016–2025), NASA POWER (2016–2025), Phase G `RULE_WATER_IRRIGATION_GATE` & `RULE_PRECIPITATION_REGIME`, [`crop_profiles.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json).
- **Evidence Classification:** `REMOTE_SENSING_DERIVED + REGIONAL_CLIMATE_CONTEXT` (`UNKNOWN` when precipitation unavailable or water is `unknown` on strictly irrigated crops).
- **Uncertainty:** Regional macro precipitation spread (`GPM` 11 km vs `NASA POWER` 55–69 km) tracked via $|S_{\text{power}} - S_{\text{gpm}}|$; coarse pixels do not reflect plot-scale micro-irrigation losses.
- **Applicability Conditions:** `UNKNOWN` (`score = null`) if both precip products are null or `water.availability == "unknown"` with strictly irrigated slots; `PARTIAL` if one rainfall source is absent or `availability == "unknown"` on rainfed sequences; `SCORED` otherwise.

### 2.2 `soil_improvement` (Soil Organic Matter & Structural Restoration)
- **Definition:** Ordinal soil organic carbon preservation, clay structural workability support, and rooting-depth stratification across the multi-season sequence.
- **Calculation Method:**
  $$\text{base} = \frac{1}{T}\sum_{t=1}^{T} S_{\text{SOM}}(\text{direction}_t), \quad S_{\text{soil}} = \text{clip}(\text{base} + \mathbb{I}_{|\text{root\_classes}| \ge 2} \cdot 0.05, 0.0, 1.0)$$
  using verified KB `_SOM_DIRECTION_SCORES` (`VETCH_OAT = 0.95`, `FABA_BEAN = 0.90`, `CHICKPEA_WINTER = 0.78`, cereals = `0.58–0.68`, `TOMATO_IND = 0.30`, `BARE_FALLOW = 0.20`, `POTATO = 0.15`).
- **Input Variables:** KB `som_contribution.direction`, KB `root_depth_m`, Field Profile SoilGrids `soc_0_30cm`, `clay_0_30cm`.
- **Units:** Normalized ordinal `[0, 1]` index (NOT predicted `t C/ha/yr`).
- **Source Datasets / Rules:** SoilGrids V6 250 m (`soc_0_30cm`, `clay_0_30cm`), Phase G `RULE_SOIL_SOC_PRIORITY` & `crop_profiles.json`.
- **Evidence Classification:** `AGRONOMIC_RULE_BASED + EXPERT_ASSUMPTION + MODELED_SPATIAL_ESTIMATE`.
- **Uncertainty:** `quantitative_t_c_ha_yr` is null in KB; SoilGrids 250 m is a modeled map rather than a laboratory core test.
- **Applicability Conditions:** `PARTIAL` when modeled `soc_0_30cm` or `clay_0_30cm` is masked/null; `SCORED` when present.

### 2.3 `nitrogen_contribution` (Biological Nitrogen Fixation & Carry-Over)
- **Definition:** Symbiotic atmospheric $\text{N}_2$ fixation potential and legume-to-cereal N carry-over benefit, strictly excluding quarantined SoilGrids Nitrogen.
- **Calculation Method:** Per-slot weights: `FABA_BEAN` (quantified `100–200 kg N/ha` in KB) = `0.95`; food legumes lacking quantified `kg N/ha` (`CHICKPEA_WINTER`, `CHICKPEA_SPRING`, `LENTIL`) = `0.72`; `VETCH_OAT` = `0.68`; `BARE_FALLOW` = `0.05`; non-legumes = `0.0`. Sequence score:
  $$S_N = \text{clip}\left(0.10 + 0.90 \cdot \bar{n}_{\text{slot}} + \min(0.12, 0.06 \cdot N_{\text{SEQ\_07}}), 0.0, 1.0\right)$$
  where $N_{\text{SEQ\_07}}$ counts verified `SEQ_07_LEGUME_CEREAL_SYNERGY` beneficial transitions.
- **Input Variables:** KB `nitrogen_fixation_potential_kg_n_ha`, `crop_category`, Phase G `SEQ_07_LEGUME_CEREAL_SYNERGY`, `nitrogen_0_30cm_status`.
- **Units:** Normalized `[0, 1]` agronomic N-break index (input N fixation range `kg N/ha` where available).
- **Source Datasets / Rules:** Phase G `crop_profiles.json`, [`sequence_compatibility.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/sequence_compatibility.json).
- **Evidence Classification:** `AGRONOMIC_RULE_BASED + EXPERT_ASSUMPTION`.
- **Uncertainty:** `CHICKPEA_*`, `LENTIL`, and `VETCH_OAT` carry `nitrogen_fixation_potential_kg_n_ha = null` in KB; SoilGrids N is quarantined (`UNVALIDATED_EXCLUDED`).
- **Applicability Conditions:** Marked `PARTIAL` whenever a sequence includes a legume/forage-legume lacking quantified KB `kg N/ha`; `SCORED` when all slots have verified quantitative fixation or `0.0`.

### 2.4 `pest_disease_disruption` (Pest, Disease & Weed Cycle Disruption)
- **Definition:** Pathogen and grass-weed break effectiveness across consecutive botanical-family transitions and Phase G sanitary return intervals.
- **Calculation Method:** Evaluates adjacent crop pairs $(c_{t-1}, c_t)$ across the sequence (and `T-1 -> T0` when `SEQ_10_UNKNOWN_PREDECESSOR_GUARD == PASS`): cross-family transition = `1.0`, clean transition involving `Mixed_Fabaceae_Poaceae` (`VETCH_OAT`) = `0.75`, same-family/repeat = `0.0`. Sequence score:
  $$S_{\text{pest}} = \text{clip}\left(0.30 + 0.70 \cdot \bar{r}_{\text{trans}} - 0.12 \cdot N_{\text{seq\_warn}} - 0.45 \cdot N_{\text{seq\_fail}}, 0.0, 1.0\right)$$
- **Input Variables:** `history_assessment.most_recent_predecessor`, KB `botanical_family`, Phase G `SEQ_02`..`SEQ_07` & `SEQ_10`.
- **Units:** Normalized `[0, 1]` index.
- **Source Datasets / Rules:** Farmer `crop_history` (`USER_REPORTED`) and Phase G `sequence_compatibility.json`.
- **Evidence Classification:** `AGRONOMIC_RULE_BASED`.
- **Uncertainty:** When `crop_history` is `NOT_PROVIDED` (`null`), `EXPLICITLY_CONFIRMED_EMPTY` (`[]`), or unresolved (`SEQ_10 = UNKNOWN`), slot-1 pest carryover from `T-1` cannot be verified.
- **Applicability Conditions:** `SCORED` when `T-1` crop is verified (`SEQ_10 = PASS`); `PARTIAL` when `T-1` history is `UNKNOWN`.

### 2.5 `erosion_protection` (Winter Ground Cover & Erosion Protection)
- **Definition:** Rainy-season living soil cover continuity and avoidance of exposed bare winter soil or deep soil-disturbing lifting.
- **Calculation Method:** Averages KB-derived winter canopy protection (`_EROSION_COVER_SCORES`: winter cereals / `VETCH_OAT` `0.90`, winter `FABA_BEAN` / `CHICKPEA_WINTER` `0.78–0.80`, spring pulses / `SUNFLOWER` `0.60–0.65`, `TOMATO_IND` `0.40`, `POTATO` `0.25`, `BARE_FALLOW` `0.15`), minus bare-fallow penalty (`SEQ_08_BARE_FALLOW_COVER`: `-0.20` on `FAIL`, `-0.10` on `WARNING`), plus `-0.10` slope-hazard penalty when DEM slope `>= 8%` with cover `< 0.70`.
- **Input Variables:** Crop planting season/cover type, `SEQ_08_BARE_FALLOW_COVER`, `terrain_dem.dem_slope_pct` & `dem_quality_status`.
- **Units:** Normalized `[0, 1]` index (DEM slope in `%` when available).
- **Source Datasets / Rules:** `crop_profiles.json`, `SEQ_08_BARE_FALLOW_COVER`, `terrain_dem`.
- **Evidence Classification:** `AGRONOMIC_RULE_BASED` (plus `REMOTE_SENSING_DERIVED` when DEM integrated).
- **Uncertainty:** Local DEM elevation/slope is currently `UNAVAILABLE_NOT_INTEGRATED` (`null`), so field gradient steepness remains unverified.
- **Applicability Conditions:** `PARTIAL` while `dem_slope_pct is null`; `SCORED` once local DEM slope is supplied.

### 2.6 `income_potential` (Economic Return Potential)
- **Definition:** Distinction between **qualitative market positioning** (horticulture cash crop vs staple grain/pulse vs forage/fallow) and **verified net financial return**.
- **Calculation Method:**
  - When verified `economic_data` (containing `net_margin_per_ha` or `expected_yield_t_ha`, `price_per_t`, and `cost_per_ha` for all crops in sequence) is **absent**: **`score = null`**, **`status = "UNKNOWN"`**, alongside `qualitative_market_tiers` metadata. Never invents `DA/ha` profit or `0.0`.
  - When complete verified `economic_data` is supplied: computes mean annual net margin across sequence slots and min-max scales eligible pool spans into `[0.10, 1.00]`, `status = "SCORED"`.
- **Input Variables:** Optional caller `economic_data`, crop identity for qualitative tier labeling.
- **Units:** `null` (`UNKNOWN`) without budgets; normalized `[0.1, 1.0]` index from `DZD/ha` verified net margins when supplied.
- **Source Datasets / Rules:** Phases A–H (no verified price/cost data on disk) or verified caller `economic_data`.
- **Evidence Classification:** `UNKNOWN` by default; `MEASURED_OR_OBSERVED` when verified budgets are supplied.
- **Uncertainty:** Regional market price fluctuations, contract availability (e.g., Bouchegouf tomato canneries), and input subsidies are unobserved unless supplied.
- **Applicability Conditions:** `UNKNOWN` (inactive in optimization) unless complete verified local yield/price/cost budgets exist.

### 2.7 `forage_value` (Livestock Forage & Fodder Value, Conditional)
- **Definition:** Green forage hay (`VETCH_OAT`) and dual-purpose straw/stubble production for mixed cereal-livestock farms.
- **Calculation Method:** When `forage_value_weight > 0`: averages `_FORAGE_VALUE_SCORES` (`VETCH_OAT = 1.00`, `BARLEY = 0.55`, `FABA_BEAN = 0.25`, `DURUM_WHEAT`/`SOFT_WHEAT = 0.20`, pulses `0.15`, `BARE_FALLOW`/`SUNFLOWER = 0.05`, cash vegetables `0.00`).
- **Input Variables:** `optional_input_completeness.forage_value_weight`, farmer `forage_value_weight`, KB crop forage role.
- **Units:** Normalized `[0, 1]` index when active; `null` otherwise.
- **Source Datasets / Rules:** Field Profile completeness flags, [`crop_profiles.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json).
- **Evidence Classification:** `AGRONOMIC_RULE_BASED` when active; `UNKNOWN`/`USER_REPORTED` when `null`/`0.0`.
- **Uncertainty:** Dry-matter `t/ha` yield varies with winter rainfall and cutting date.
- **Applicability Conditions:** **`NOT_APPLICABLE`** (`score = null`) whenever `forage_value_weight` is `null` (`NOT_PROVIDED`) or explicitly `0.0`; `SCORED` strictly when `forage_value_weight > 0.0`.

### 2.8 `farmer_priority_fit` (Farmer Targets, Exclusions & Operational Fit)
- **Definition:** Alignment with requested `target_crop_ids`, strict adherence to `excluded_crop_ids`, irrigation water readiness, and machinery compatibility (`RULE_EQUIPMENT_COMPATIBILITY`).
- **Calculation Method:** `0.0` if any `excluded_crop_ids` member appears; otherwise `0.50 * target_match_ratio + 0.50 * operational_readiness`, where `operational_readiness` averages slot scores from `RULE_WATER_IRRIGATION_GATE` and `RULE_EQUIPMENT_COMPATIBILITY` (`PASS+PASS = 1.0`, `PASS+UNKNOWN = 0.75`, `FAIL = 0.0`, other = `0.45`).
- **Input Variables:** `target_crop_ids`, `excluded_crop_ids`, `equipment_constraints`, slot rule evaluations.
- **Units:** Normalized `[0, 1]` index.
- **Source Datasets / Rules:** `preference_handling`, Phase G `RULE_WATER_IRRIGATION_GATE` & `RULE_EQUIPMENT_COMPATIBILITY`.
- **Evidence Classification:** `USER_REPORTED + AGRONOMIC_RULE_BASED`.
- **Uncertainty:** When `equipment_constraints` is `null` (`NOT_PROVIDED`), specialized machinery bottlenecks (drip/harvester/baler) remain unverified.
- **Applicability Conditions:** `PARTIAL` when `equipment_constraints == "NOT_PROVIDED"`; `SCORED` when explicitly confirmed (`[]` or list).
