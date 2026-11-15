# Phase M — Pilot Evaluation Metrics Specification

> **Executable Implementation:** [`compute_pilot_metrics`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L277) in `src/pilot/models.py`  
> **Non-Fabrication Rule:** Software usability metrics, expert agreement rates, and longitudinal empirical outcomes are reported **strictly separately**. Yield `RMSE` / `R²` **cannot** be computed unless `>= 15` paired real harvest observations (`crop_yield_t_ha`) exist.

---

## 1. Eight Separated Pilot Metric Categories

| # | Metric Family | Operational Formula / Estimator | Data Source | What It Measures — And What It Does NOT |
|---:|---|---|---|---|
| 1 | **Input Usability** | `completion_rate = N(intake completed unassisted or minor help) / N(sessions)`; `median intake_duration_seconds` | `PilotExecutionSession` (`Section A` log) | UI clarity & form length (`NOT` recommendation quality) |
| 2 | **Polygon Validation Reliability** | `poly_valid_rate = N(polygon passed EPSG:32632 & Guelma check cleanly) / N(sessions)` | `/api/v1/fields/validate` telemetry | Cadastre polygon drawing robustness & overlap warning frequency |
| 3 | **Field Profile Data Availability** | `mean(data_quality.completeness_score)` + count of `SoilGrids clay/soc = null` masks across `< 5 ha` vs larger plots | Phase J `data_quality` + DB metadata | Availability of existing remote/modeled inputs (`NOT` statistical confidence or lab accuracy) |
| 4 | **Agronomic Expert Agreement** | `strict_accept = N(ACCEPTED) / N(reviews)`; `usable_or_modified = N(ACCEPTED + MODIFIED) / N(reviews)`; `reject_rate = N(REJECTED) / N(reviews)`; + root-cause distribution (`disagreement_investigation_code`) | `ExpertReviewRecord` (`Section B`) | Consensus among `ITGC`/`DSA`/`ONID` advisors (`not` quantitative plot yield gain) |
| 5 | **Constraint Detection** | `mean(constraint_detection_rating)` (`1..5`) + `agronomic_safety_pass_rate = N(safety_pass=true)/N(reviews)` + `local_constraints_flagged` miss rate | `ExpertReviewRecord` (`Section B`) | Ability of Phase G/H gates to surface real drought/salinity/rotation blockers |
| 6 | **Recommendation Feasibility** | `feasibility_rate = N(eligible_strategies_count > 0) / N(sessions)` (tracking `NO_ELIGIBLE_STRATEGY` vs conditional vs modified plans) | Phase L API telemetry & expert disposition | Whether locally seed- and machinery-viable options remain after hard exclusions |
| 7 | **Explanation Quality & Uncertainty** | `mean(explanation_quality_rating)` (`1..5`) + `uncertainty_clarity_rate = N(uncertainty_communication_clear=true)/N(reviews)` | `ExpertReviewRecord` (`Section B`) | Whether evidence sources, `DEM`/`ECe` gaps, and non-yield scope stay transparent |
| 8 | **System Execution Time** | `p50(execution_latency_ms)` & `p95(execution_latency_ms)` across `/api/v1/fields/analyze` (cold vs warm raster cache) | API server / session telemetry | Computational responsiveness for field tablet / office workflows |

---

## 2. Hard Prohibitions on Longitudinal & Predictive Claims

[`compute_pilot_metrics`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L277) inspects real `MeasuredFieldObservation.crop_yield_t_ha` records (`Section C`) and explicitly outputs:
- `predictive_yield_validation_status = "NOT_VALIDATABLE_INSUFFICIENT_YIELD_LABELS"` and `predictive_yield_accuracy_claimable = false` whenever fewer than `min_yield_pairs_for_accuracy` (`15` paired plots) carry measured harvest yields.
- Even when single-season yields or soil lab cores (`ECe`, `pH`, `SOC`, texture) are collected, the pilot benchmark evaluates **SoilGrids vs lab error (`RMSE`/`bias`)** and **observed baseline feasibility**—never claiming improved multi-year yield, farmer profit (`DZD/ha`), or soil organic carbon accumulation without controlled multi-season longitudinal trials.
