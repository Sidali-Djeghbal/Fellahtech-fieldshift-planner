"""Weight and climate sensitivity analysis for Phase I rotation rankings."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _normalize_weights_dict(raw: Dict[str, float], active_objectives: Sequence[str]) -> Dict[str, float]:
    total = sum(max(0.0, float(raw.get(obj, 0.0))) for obj in active_objectives)
    if total <= 0.0:
        n = len(active_objectives)
        return {obj: (1.0 / n if n > 0 else 0.0) for obj in active_objectives}
    return {obj: round(max(0.0, float(raw.get(obj, 0.0))) / total, 6) for obj in active_objectives}


def _score_and_sort(
    eligible_strategies: Sequence[Dict[str, Any]],
    weights_norm: Dict[str, float],
    active_objectives: Sequence[str],
    pareto_front_ids: set,
    water_override_by_sid: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for s in eligible_strategies:
        sid = s["strategy_id"]
        total = 0.0
        for obj in active_objectives:
            val = float(s["scores"][obj]["score"])
            if obj == "water_efficiency" and water_override_by_sid and sid in water_override_by_sid:
                val = float(water_override_by_sid[sid])
            total += weights_norm[obj] * val
        is_front = 0 if sid in pareto_front_ids else 1
        pass_count = int(s["constraint_evaluations"]["overall_status_counts"].get("PASS", 0))
        rows.append(
            {
                "strategy_id": sid,
                "weighted_score": round(total, 6),
                "is_non_front": is_front,
                "pass_count": pass_count,
            }
        )
    rows.sort(key=lambda r: (-round(r["weighted_score"], 9), r["is_non_front"], -r["pass_count"], r["strategy_id"]))
    return rows


def run_sensitivity_analysis(
    eligible_strategies: Sequence[Dict[str, Any]],
    baseline_weights_norm: Dict[str, float],
    active_objectives: Sequence[str],
    pareto_front_ids: Sequence[str],
    baseline_winner_id: Optional[str],
    power_water_scores: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Evaluate ranking stability under weight perturbations, emphasis shifts, and climate envelope checks."""
    if len(eligible_strategies) <= 1 or not active_objectives or baseline_winner_id is None:
        return {
            "status": "NOT_APPLICABLE_INSUFFICIENT_STRATEGIES_OR_OBJECTIVES",
            "baseline_top_strategy_id": baseline_winner_id,
            "baseline_top_two_margin": None,
            "preferred_strategy_stable": False if baseline_winner_id is None else True,
            "stability_index": None,
            "scenarios_evaluated_count": 0,
            "winner_changes_count": 0,
            "winner_change_scenarios": [],
            "climate_sensitivity": {
                "status": "NOT_EVALUATED",
                "gpm_top_strategy_id": baseline_winner_id,
                "nasa_power_top_strategy_id": None,
                "climate_dataset_agreement": "INSUFFICIENT_DATA",
            },
            "scenario_results": [],
        }

    front_set = set(pareto_front_ids)
    base_rows = _score_and_sort(eligible_strategies, baseline_weights_norm, active_objectives, front_set)
    top_two_margin = round(base_rows[0]["weighted_score"] - base_rows[1]["weighted_score"], 6) if len(base_rows) >= 2 else None

    scenarios: List[Dict[str, Any]] = []

    # 1. Equal weights across active objectives
    scenarios.append(
        {
            "scenario_id": "EQUAL_ACTIVE_WEIGHTS",
            "description": "Uniform weight assigned equally across all active scorable objectives.",
            "weights": _normalize_weights_dict({k: 1.0 for k in active_objectives}, active_objectives),
        }
    )

    # 2. One-at-a-Time +/- 25% perturbations on each active weighted objective
    for obj in active_objectives:
        if baseline_weights_norm.get(obj, 0.0) <= 0.0:
            continue
        for sign_label, mult in (("PLUS_25PCT", 1.25), ("MINUS_25PCT", 0.75)):
            perturbed = dict(baseline_weights_norm)
            perturbed[obj] = perturbed[obj] * mult
            scenarios.append(
                {
                    "scenario_id": f"OAT_{obj.upper()}_{sign_label}",
                    "description": f"Perturb {obj} relative weight by {mult:.2f}x and renormalize active weights.",
                    "weights": _normalize_weights_dict(perturbed, active_objectives),
                }
            )

    # 3. Domain priority focus stress scenarios (only over active objectives)
    focus_templates = [
        ("FOCUS_WATER_EFFICIENCY", "Dominant emphasis (0.65) on water_efficiency.", "water_efficiency"),
        ("FOCUS_SOIL_IMPROVEMENT", "Dominant emphasis (0.65) on soil_improvement.", "soil_improvement"),
        ("FOCUS_NITROGEN_CONTRIBUTION", "Dominant emphasis (0.65) on nitrogen_contribution.", "nitrogen_contribution"),
        ("FOCUS_PEST_DISEASE_DISRUPTION", "Dominant emphasis (0.65) on pest_disease_disruption.", "pest_disease_disruption"),
        ("FOCUS_EROSION_PROTECTION", "Dominant emphasis (0.65) on erosion_protection.", "erosion_protection"),
        ("FOCUS_FORAGE_VALUE", "Dominant emphasis (0.65) on forage_value (active only).", "forage_value"),
        ("FOCUS_INCOME_POTENTIAL", "Dominant emphasis (0.65) on income_potential (active only).", "income_potential"),
        ("FOCUS_FARMER_PRIORITY_FIT", "Dominant emphasis (0.65) on farmer_priority_fit.", "farmer_priority_fit"),
    ]
    for sc_id, desc, target_obj in focus_templates:
        if target_obj not in active_objectives:
            continue
        rem = max(len(active_objectives) - 1, 1)
        focused = {obj: (0.65 if obj == target_obj else 0.35 / rem) for obj in active_objectives}
        scenarios.append(
            {
                "scenario_id": sc_id,
                "description": desc,
                "weights": _normalize_weights_dict(focused, active_objectives),
            }
        )

    scenario_results: List[Dict[str, Any]] = []
    winner_changes: List[Dict[str, Any]] = []
    same_winner = 0

    for sc in scenarios:
        ranked = _score_and_sort(eligible_strategies, sc["weights"], active_objectives, front_set)
        top_sid = ranked[0]["strategy_id"]
        runner_sid = ranked[1]["strategy_id"] if len(ranked) >= 2 else None
        changed = top_sid != baseline_winner_id
        if not changed:
            same_winner += 1
        else:
            winner_changes.append(
                {
                    "scenario_id": sc["scenario_id"],
                    "description": sc["description"],
                    "new_top_strategy_id": top_sid,
                    "baseline_top_strategy_id": baseline_winner_id,
                    "new_top_score": ranked[0]["weighted_score"],
                }
            )
        scenario_results.append(
            {
                "scenario_id": sc["scenario_id"],
                "description": sc["description"],
                "top_strategy_id": top_sid,
                "runner_up_strategy_id": runner_sid,
                "top_score": ranked[0]["weighted_score"],
                "winner_changed": changed,
                "ordered_strategy_ids": [r["strategy_id"] for r in ranked],
            }
        )

    # 4. Climate precipitation envelope sensitivity (GPM 11 km conservative vs NASA POWER 55-69 km wetter bound)
    if power_water_scores and "water_efficiency" in active_objectives:
        power_ranked = _score_and_sort(
            eligible_strategies,
            baseline_weights_norm,
            active_objectives,
            front_set,
            water_override_by_sid=power_water_scores,
        )
        power_top = power_ranked[0]["strategy_id"]
        clim_agree = power_top == baseline_winner_id
        climate_sens = {
            "status": "EVALUATED",
            "gpm_top_strategy_id": baseline_winner_id,
            "nasa_power_top_strategy_id": power_top,
            "climate_dataset_agreement": "ROBUST_GPM_AND_POWER" if clim_agree else "PRECIP_SENSITIVE_RANK_SHIFT",
            "power_ordered_strategy_ids": [r["strategy_id"] for r in power_ranked],
        }
    else:
        climate_sens = {
            "status": "NOT_EVALUATED",
            "gpm_top_strategy_id": baseline_winner_id,
            "nasa_power_top_strategy_id": None,
            "climate_dataset_agreement": "SINGLE_OR_MISSING_PRECIP_SOURCE",
        }

    total_sc = len(scenario_results)
    stability_idx = round(same_winner / total_sc, 4) if total_sc > 0 else 1.0

    return {
        "status": "COMPLETED",
        "baseline_top_strategy_id": baseline_winner_id,
        "baseline_top_two_margin": top_two_margin,
        "preferred_strategy_stable": len(winner_changes) == 0,
        "stability_index": stability_idx,
        "scenarios_evaluated_count": total_sc,
        "winner_changes_count": len(winner_changes),
        "winner_change_scenarios": winner_changes,
        "climate_sensitivity": climate_sens,
        "scenario_results": scenario_results,
    }
