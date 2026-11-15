# Phase I — Multi-Objective Optimization & Output Contract

**Modules:** [`src/optimization/pareto.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/pareto.py), [`src/optimization/scoring_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py)  
**Verified Sample Output:** [`docs/phaseI/sample_ranking_output.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseI/sample_ranking_output.json)

---

## 1. Feasibility Gate & Conditional Handling

Phase I strictly preserves Phase G/H hard constraint verdicts (`feasible`, `feasibility_status`) and never promotes an infeasible candidate:
- **`feasible == False`** (`INFEASIBLE_HARD_CONSTRAINT` or `UNVERIFIED_HARD_UNKNOWN`) -> immediately placed in `excluded_infeasible_strategy_ids` with `rank = null`, `pareto_status = "EXCLUDED_INFEASIBLE"`, `weighted_score = null`. Never eligible for `suggested_strategy_id`.
- **`FEASIBLE_PASS` vs `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS`:**
  - Because Guelma field profiles currently lack integrated local DEM slope (`UNAVAILABLE_NOT_INTEGRATED`) and measured irrigation salinity (`ECe`/`ECw`), eligible strategies carry `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS`.
  - When `feasible_pass_count == 0` and `eligible_for_ranking_count > 0`, Phase I sets `all_candidates_conditional = true`, emits an explicit notice in `feasibility_gate_summary.notice`, and tags `recommendation_status = "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION"`.
  - When `eligible_for_ranking_count == 0` (all candidates infeasible) or all active weights sum to zero due to missing evidence, `suggested_strategy_id = null` rather than forcing an irresponsible winner.

---

## 2. Pareto Dominance (`src/optimization/pareto.py`)

### 2.1 Active Objective Filtering
Before pairwise dominance testing, `identify_common_active_objectives()` retains only objectives where **every** eligible strategy holds `status in {"SCORED", "PARTIAL"}` and `score is not null`. Objectives marked `UNKNOWN` (such as `income_potential` without local market budgets) or `NOT_APPLICABLE` (`forage_value` when `forage_value_weight` is `null` or `0.0`) are removed cleanly rather than replaced with `0.0`.

### 2.2 Dominance & Equal-Tie Rules
For eligible strategies $A$ and $B$ across shared active objectives $K$:
- $A$ Pareto-dominates $B$ iff $\forall k \in K, s_A(k) \ge s_B(k) - 10^{-9}$ and $\exists k \in K, s_A(k) > s_B(k) + 10^{-9}$.
- **Equal objective vectors** ($\forall k \in K, |s_A(k) - s_B(k)| \le 10^{-9}$): neither dominates; both remain `NON_DOMINATED_PARETO_FRONT` and are logged in `equal_objective_ties`.

---

## 3. Farmer Weight Mapping & Normalization

The 5 farmer-input weights from [`field_input_schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json) map deterministically onto the 8 Phase I objectives:

| Farmer Preference Key | Phase I Objective(s) | Split Ratio |
|---|---|---|
| `water_saving_weight` | `water_efficiency` | `1.00` |
| `soil_improvement_weight` | `soil_improvement`, `nitrogen_contribution`, `erosion_protection` | `0.50` / `0.25` / `0.25` |
| `income_weight` | `income_potential` | `1.00` |
| `risk_reduction_weight` | `pest_disease_disruption`, `farmer_priority_fit` | `0.65` / `0.35` |
| `forage_value_weight` | `forage_value` | `1.00` (`null` -> `NOT_APPLICABLE`) |

When the farmer supplies no weights, `DEFAULT_BALANCED_AGRONOMIC_WEIGHTS` (`0.25, 0.30, 0.20, 0.25, None`) is used and recorded under `weight_source = "DEFAULT_BALANCED_AGRONOMIC_WEIGHTS"`. Validation strictly rejects negative weights, values `> 1.0`, booleans, `NaN/Inf`, unknown keys, and all-zero active weight vectors (`ValueError`).

### Active Normalization Formula
Let $K_{\text{active}}$ be objectives that are both scorable (`SCORED` or `PARTIAL`) and carry raw weight $w_k > 0$:
$$w_k^{\text{norm}} = \begin{cases} \dfrac{w_k}{\sum_{j \in K_{\text{active}}} w_j}, & k \in K_{\text{active}} \\ 0.0, & \text{otherwise} \end{cases}, \qquad S_i = \sum_{k \in K_{\text{active}}} w_k^{\text{norm}} \cdot s_{i,k}$$
Inactive objectives receive `normalized_weight = 0.0` and an explicit reason inside `ranking_methodology.inactive_objectives_audit`. Deterministic tie-breaking follows `(-weighted_score, is_non_pareto_front, -pass_rule_count, strategy_id)`.

---

## 4. Verified Results on `F_BOU_SAMPLE_01` ([sample_ranking_output.json](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseI/sample_ranking_output.json))

- **Active Objectives Normalized (`sum = 1.0`):** `water_efficiency = 0.3125`, `soil_improvement = 0.1875`, `nitrogen_contribution = 0.09375`, `pest_disease_disruption = 0.203125`, `erosion_protection = 0.09375`, `farmer_priority_fit = 0.109375` (`income_potential = 0.0` [`UNKNOWN`], `forage_value = 0.0` [`NOT_APPLICABLE`]).
- **Pareto Front (`3` Non-Dominated):** `STRAT_SOIL_IMPROVEMENT`, `STRAT_IRRIGATED_CASH`, `STRAT_TARGET_SUNFLOWER`.
- **Pareto Dominated (`2`):** `STRAT_CEREAL_FORAGE` and `STRAT_CEREAL_LEGUME` (strictly outperformed or tied across all 6 active objectives by `STRAT_SOIL_IMPROVEMENT`).
- **Excluded Infeasible (`1`):** `STRAT_EXISTING_BASELINE` (`SEQ_04_PULSE_BROOMRAPE_BREAK` failure).
- **Weighted Ranking:**
  1. `#1` `STRAT_SOIL_IMPROVEMENT` (`0.847803`, `NON_DOMINATED_PARETO_FRONT`)
  2. `#2` `STRAT_CEREAL_FORAGE` (`0.800353`, `DOMINATED`)
  3. `#3` `STRAT_CEREAL_LEGUME` (`0.762741`, `DOMINATED`)
  4. `#4` `STRAT_TARGET_SUNFLOWER` (`0.742606`, `NON_DOMINATED_PARETO_FRONT`)
  5. `#5` `STRAT_IRRIGATED_CASH` (`0.726916`, `NON_DOMINATED_PARETO_FRONT`)
  - Excluded: `STRAT_EXISTING_BASELINE` (`rank = null`, `EXCLUDED_INFEASIBLE`).

---

## 5. Final JSON Output Contract Compatibility

Phase I preserves every required field in the established output contract:
- **Top level:** `suggested_strategy_id`, `recommendation_status`, `all_candidates_conditional`, `feasibility_gate_summary`, `ranking_methodology`, `pareto_analysis`, `sensitivity_analysis`, `ranked_strategy_ids`, `excluded_infeasible_strategy_ids`, `strategies`.
- **Per strategy:** `strategy_id`, `feasibility_status`, `scores`, `confidence`, `explanation`, `reasons`, `evidence`, `benefits`, `risks`, `assumptions`, `information_gaps`, `needs_local_review`, plus `rank`, `pareto_status`, `dominated_by`, and `weighted_score`.
