# Phase I — Weight & Climate Sensitivity Analysis

**Module:** [`src/optimization/sensitivity.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/sensitivity.py)  
**Verified Sample Output:** [`docs/phaseI/sample_ranking_output.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseI/sample_ranking_output.json)

---

## 1. Methodology

`run_sensitivity_analysis()` evaluates ranking stability across **two independent uncertainty axes** over the eligible/conditional strategy pool and active weighted objectives:

1. **Farmer Priority Weight Perturbations & Emphasis Scenarios:**
   - **`EQUAL_ACTIVE_WEIGHTS`:** Uniform equal weights ($1 / |K_{\text{active}}|$) across all active scorable objectives.
   - **One-at-a-Time (`OAT_*_PLUS_25PCT` / `OAT_*_MINUS_25PCT`):** Each active objective's baseline weight is multiplied by $1.25$ and $0.75$ in turn, then renormalized strictly to $1.0$.
   - **Domain Priority Stress Scenarios (`FOCUS_*`):** Assigns $0.65$ dominant weight to one active objective (`water_efficiency`, `soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, `farmer_priority_fit`, plus `forage_value` / `income_potential` when active) and distributes $0.35$ equally across the remaining active objectives.
   - **Outputs Reported:** `stability_index` (fraction of scenarios preserving the baseline Rank #1 strategy), `preferred_strategy_stable`, `baseline_top_two_margin`, `winner_changes_count`, `winner_change_scenarios`, and full ordered lists per scenario.
2. **Macro Climate Rainfall Envelope (`GPM` 11 km vs `NASA POWER` 55–69 km):**
   - Replaces conservative `GPM` precipitation scores in `water_efficiency` with the wetter `NASA POWER` rainfall regime (`nasa_power_annual_precip_mm`) and checks whether Rank #1 flips (`ROBUST_GPM_AND_POWER` vs `PRECIP_SENSITIVE_RANK_SHIFT`).

---

## 2. Verified Sensitivity Findings (`F_BOU_SAMPLE_01`)

- **Baseline Top Strategy:** `STRAT_SOIL_IMPROVEMENT` (`0.847803`)
- **Top-Two Margin (`#1 - #2`):** **`0.04745`** over `STRAT_CEREAL_FORAGE` (`0.800353`)
- **Weight Sensitivity (`19` Scenarios Evaluated):**
  - **`stability_index`:** **`0.9474`** (`18 / 19` scenarios preserve `STRAT_SOIL_IMPROVEMENT` as `#1`)
  - **`preferred_strategy_stable`:** **`false`** (`winner_changes_count = 1`)
  - **Identified Crossover Scenario:** **`FOCUS_FARMER_PRIORITY_FIT`** (`0.65` weight on matching requested targets `TOMATO_IND` + `SUNFLOWER`) shifts Rank #1 from `STRAT_SOIL_IMPROVEMENT` to **`STRAT_IRRIGATED_CASH`** (`score = 0.649444`).
  - All twelve OAT `+/- 25%` perturbations, `EQUAL_ACTIVE_WEIGHTS`, and every biophysical focus (`FOCUS_WATER_EFFICIENCY`, `FOCUS_SOIL_IMPROVEMENT`, `FOCUS_NITROGEN_CONTRIBUTION`, `FOCUS_PEST_DISEASE_DISRUPTION`, `FOCUS_EROSION_PROTECTION`) maintain `STRAT_SOIL_IMPROVEMENT` at `#1`.
- **Climate Envelope Sensitivity (`GPM = 566.28 mm/yr` vs `NASA POWER = 736.84 mm/yr`):**
  - **`gpm_top_strategy_id`:** `STRAT_SOIL_IMPROVEMENT`
  - **`nasa_power_top_strategy_id`:** `STRAT_SOIL_IMPROVEMENT`
  - **`climate_dataset_agreement`:** **`ROBUST_GPM_AND_POWER`** (`power_ordered_strategy_ids`: `['STRAT_SOIL_IMPROVEMENT', 'STRAT_CEREAL_FORAGE', 'STRAT_TARGET_SUNFLOWER', 'STRAT_CEREAL_LEGUME', 'STRAT_IRRIGATED_CASH']` — note higher `NASA POWER` rainfall lets `STRAT_TARGET_SUNFLOWER` overtake `STRAT_CEREAL_LEGUME` at `#3` while leaving `#1` unchanged).
