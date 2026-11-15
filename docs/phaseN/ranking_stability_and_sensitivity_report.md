# Phase N — Ranking Stability, Near-Tie Margin & Sensitivity Analysis Report

## 1. Diagnosis of Legacy Sensitivity Behavior (`ANAL_248892E4C4DFE796`)

In the legacy `FieldShift-PhaseFJ-1.0.0` DB record for `ANAL_248892E4C4DFE796`:
- `#1 STRAT_WATER_CONSCIOUS` scored **`0.895228`** vs `#2 STRAT_CEREAL_FORAGE` at **`0.891834`** (absolute margin **`0.003394`**, `~0.38%`).
- Across `19` perturbed priority-weight scenarios, the top rank flipped in **`6`** scenarios (`stability_index = 0.6842` for the #1 winner): uniform equal weights (`EQUAL_ACTIVE_WEIGHTS`), soil (`FOCUS_SOIL_IMPROVEMENT`), pest (`FOCUS_PEST_DISEASE_DISRUPTION`), erosion (`FOCUS_EROSION_PROTECTION`), and priority-fit (`FOCUS_FARMER_PRIORITY_FIT`) shifted top place to `STRAT_CEREAL_FORAGE`, while `FOCUS_NITROGEN_CONTRIBUTION` shifted top place to `STRAT_SOIL_IMPROVEMENT`.
- Despite a `0.0034` margin and `6/19` winner flips, v1.0.0 lacked configurable tie classification and structured near-tie UI/API exposure.

---

## 2. Configurable Margin Classification (`src/optimization/sensitivity.py`)

Phase N introduces `MarginThresholds` (`DEFAULT_MARGIN_THRESHOLDS`):
- `near_tie_abs = 0.015`, `near_tie_rel_pct = 2.5%` → **`NEAR_TIE`**
- `narrow_abs = 0.04`, `narrow_rel_pct = 6.0%` → **`NARROW_MARGIN`**
- Above both thresholds → **`CLEAR_MARGIN`** (or `SINGLE_CANDIDATE` if `< 2` eligible strategies)

Implemented in `classify_margin_status(top_score, second_score, thresholds)`:
- **`near_tie_detected`:** `True` whenever `margin_status in ("NEAR_TIE", "NARROW_MARGIN")`.
- **`plausible_alternatives`:** Reports every non-#1 eligible strategy within the narrow/near-tie band (`gap`, `relative_gap_pct`, `is_near_tie`) OR holding `winner_frequency > 0` across weight perturbations OR winning either the NASA POWER / conservative-dry climate scenario.

---

## 3. Per-Strategy Stability Metrics & Expanded Climate Envelope

`run_sensitivity_analysis(...)` now computes `per_strategy_stability[sid]` containing:
- `baseline_rank`, `baseline_score`
- `winner_frequency` (share of evaluated weight perturbation scenarios where `sid` takes rank #1)
- `top_1_retention` (`winner_frequency` for baseline #1)
- `top_2_frequency` (share of scenarios where `sid` finishes #1 or #2)
- `rank_change_counts`, `min_rank`, `max_rank`, `winning_scenario_ids`

These per-strategy metrics propagate into `recommendation.field_plans[0].strategies[*].stability_metrics`.

Climate sensitivity checks now evaluate **four** hydro-climatic stress points whenever both GPM and NASA POWER exist:
1. `gpm_top_strategy_id` (conservative lower precip bound, 11 km)
2. `nasa_power_top_strategy_id` (~55–69 km regional climate)
3. `conservative_dry_top_strategy_id` (minimum of GPM/POWER minus `0.08` dry buffer)
4. `disagreement_stress_top_strategy_id` (penalizing source spread when `precip_spread_mm > 100.0`)

`overall_climate_robustness` reports `"ROBUST_ACROSS_ENVELOPE"` vs `"SENSITIVE_TO_PRECIP_UNCERTAINTY"`.

---

## 4. Observed Differentiation Across Guelma Parcels (v1.1.0)

- **`BELKHEIR_CROPLAND` (`23.86 ha`):** `CLEAR_MARGIN` (`Δ = 0.066135`, `7.52%`, `stability_index = 1.0`, `plausible_alternatives = []`).
- **`TAMLOUKA_SEMIARID` (`23.97 ha`):** **`NEAR_TIE`** (`Δ = 0.014253`, `1.67%`, `stability_index = 0.8947`)—jointly surfaces `STRAT_WATER_CONSCIOUS` (`winner_frequency = 0.1053`, `top_2_frequency = 0.8421`) so farmers/advisors see both top choices when rainfall scarcity and soil conservation closely balance.

---

## 5. Non-Confidence Guardrail

Every sensitivity block and strategy card now carries explicit **`non_confidence_note`** and **`sensitivity_limitations`**: perturbation invariance across active ordinal weights does **not** incorporate unmeasured `income_potential`, daily FAO-56 ETc, or field lab N/P/K/ECe, and **never implies statistical probability or empirical yield validation**.
