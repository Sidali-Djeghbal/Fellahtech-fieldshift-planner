"""Weight and climate sensitivity analysis for Phase I rotation rankings (Hardened Phase N).

Evaluates ranking stability, configurable near-tie score margins, per-strategy
winner/top-2 retention and rank changes across weight perturbations, plus
GPM / NASA POWER / conservative dry-bound climate envelope checks.

Explicit scientific caveat: sensitivity invariance measures perturbation stability of
this multi-criteria decision model ONLY — never empirical yield probability or scientific proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class MarginThresholds:
    """Configurable thresholds classifying baseline rank #1 vs #2 score closeness."""

    near_tie_abs: float = 0.015
    narrow_abs: float = 0.04
    near_tie_rel_pct: float = 2.5
    narrow_rel_pct: float = 6.0


DEFAULT_MARGIN_THRESHOLDS = MarginThresholds()


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


def classify_margin_status(
    top_score: Optional[float],
    second_score: Optional[float],
    thresholds: MarginThresholds = DEFAULT_MARGIN_THRESHOLDS,
) -> tuple[Optional[float], Optional[float], str]:
    """Classify rank #1 vs #2 margin as CLEAR_MARGIN, NARROW_MARGIN, or NEAR_TIE."""
    if top_score is None or second_score is None:
        return None, None, "SINGLE_CANDIDATE"
    abs_margin = round(max(0.0, float(top_score) - float(second_score)), 6)
    rel_pct = round((abs_margin / max(float(top_score), 1e-6)) * 100.0, 2)
    if abs_margin <= thresholds.near_tie_abs or rel_pct <= thresholds.near_tie_rel_pct:
        return abs_margin, rel_pct, "NEAR_TIE"
    if abs_margin <= thresholds.narrow_abs or rel_pct <= thresholds.narrow_rel_pct:
        return abs_margin, rel_pct, "NARROW_MARGIN"
    return abs_margin, rel_pct, "CLEAR_MARGIN"


def run_sensitivity_analysis(
    eligible_strategies: Sequence[Dict[str, Any]],
    baseline_weights_norm: Dict[str, float],
    active_objectives: Sequence[str],
    pareto_front_ids: Sequence[str],
    baseline_winner_id: Optional[str],
    power_water_scores: Optional[Dict[str, float]] = None,
    *,
    margin_thresholds: MarginThresholds = DEFAULT_MARGIN_THRESHOLDS,
    precip_spread_mm: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate ranking stability under weight perturbations, near-tie margins, and climate stress checks."""
    non_conf_note = (
        "Sensitivity stability_index measures ordinal rank invariance under modeled priority-weight and macro-climate "
        "perturbations ONLY; inactive/unmeasured objectives (e.g. income_potential, FAO-56 ETc, lab nutrients) are not "
        "perturbed and stability NEVER implies empirical yield confidence."
    )
    if len(eligible_strategies) <= 1 or not active_objectives or baseline_winner_id is None:
        single_status = "NO_CANDIDATE" if baseline_winner_id is None else "SINGLE_CANDIDATE"
        return {
            "status": "NOT_APPLICABLE_INSUFFICIENT_STRATEGIES_OR_OBJECTIVES",
            "baseline_top_strategy_id": baseline_winner_id,
            "baseline_top_two_margin": None,
            "relative_top_two_margin_pct": None,
            "margin_status": single_status,
            "near_tie_detected": False,
            "plausible_alternatives": [],
            "preferred_strategy_stable": False if baseline_winner_id is None else True,
            "stability_index": None,
            "top_1_retention": None,
            "per_strategy_stability": {},
            "scenarios_evaluated_count": 0,
            "winner_changes_count": 0,
            "winner_change_scenarios": [],
            "climate_sensitivity": {
                "status": "NOT_EVALUATED",
                "gpm_top_strategy_id": baseline_winner_id,
                "nasa_power_top_strategy_id": None,
                "climate_dataset_agreement": "INSUFFICIENT_DATA",
                "precip_spread_mm": precip_spread_mm,
            },
            "scenario_results": [],
            "non_confidence_note": non_conf_note,
            "sensitivity_limitations": [
                "Fewer than two rankable candidates available; comparative ranking sensitivity cannot be evaluated.",
                non_conf_note,
            ],
        }

    front_set = set(pareto_front_ids)
    base_rows = _score_and_sort(eligible_strategies, baseline_weights_norm, active_objectives, front_set)
    top_score = base_rows[0]["weighted_score"]
    second_score = base_rows[1]["weighted_score"] if len(base_rows) >= 2 else None
    top_two_margin, rel_margin_pct, margin_status = classify_margin_status(
        top_score, second_score, thresholds=margin_thresholds
    )
    baseline_ranks = {r["strategy_id"]: idx for idx, r in enumerate(base_rows, start=1)}
    baseline_scores = {r["strategy_id"]: r["weighted_score"] for r in base_rows}

    scenarios: List[Dict[str, Any]] = [
        {
            "scenario_id": "EQUAL_ACTIVE_WEIGHTS",
            "description": "Uniform weight assigned equally across all active scorable objectives.",
            "weights": _normalize_weights_dict({k: 1.0 for k in active_objectives}, active_objectives),
        }
    ]

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

    win_counts: Dict[str, int] = {r["strategy_id"]: 0 for r in base_rows}
    top2_counts: Dict[str, int] = {r["strategy_id"]: 0 for r in base_rows}
    rank_change_counts: Dict[str, int] = {r["strategy_id"]: 0 for r in base_rows}
    rank_histories: Dict[str, List[int]] = {r["strategy_id"]: [] for r in base_rows}
    wins_in_scenarios: Dict[str, List[str]] = {r["strategy_id"]: [] for r in base_rows}

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
        win_counts[top_sid] += 1
        wins_in_scenarios[top_sid].append(sc["scenario_id"])
        for pos, row in enumerate(ranked, start=1):
            rsid = row["strategy_id"]
            if pos <= 2:
                top2_counts[rsid] += 1
            if pos != baseline_ranks[rsid]:
                rank_change_counts[rsid] += 1
            rank_histories[rsid].append(pos)

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

    total_sc = len(scenario_results)
    per_strategy_stability: Dict[str, Dict[str, Any]] = {}
    for row in base_rows:
        sid = row["strategy_id"]
        hist = rank_histories[sid]
        win_freq = round(win_counts[sid] / total_sc, 4) if total_sc > 0 else 0.0
        per_strategy_stability[sid] = {
            "baseline_rank": baseline_ranks[sid],
            "baseline_score": baseline_scores[sid],
            "winner_frequency": win_freq,
            "top_1_retention": win_freq if sid == baseline_winner_id else 0.0,
            "top_2_frequency": round(top2_counts[sid] / total_sc, 4) if total_sc > 0 else 0.0,
            "rank_change_counts": rank_change_counts[sid],
            "min_rank": min(hist) if hist else baseline_ranks[sid],
            "max_rank": max(hist) if hist else baseline_ranks[sid],
            "winning_scenario_ids": wins_in_scenarios[sid],
        }

    # Climate precipitation & conservative dry/disagreement stress scenarios
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

        conservative_scores: Dict[str, float] = {}
        disagreement_scores: Dict[str, float] = {}
        for s in eligible_strategies:
            sid = s["strategy_id"]
            g_sc = float(s["scores"]["water_efficiency"]["score"])
            p_sc = float(power_water_scores.get(sid, g_sc))
            min_sc = min(g_sc, p_sc)
            # Conservative dry lower bound & source disagreement stress
            conservative_scores[sid] = round(max(0.05, min_sc - 0.08), 4)
            spread_penalty = min(0.15, abs(g_sc - p_sc)) if (precip_spread_mm is None or precip_spread_mm > 100.0) else 0.0
            disagreement_scores[sid] = round(max(0.05, 0.5 * (g_sc + p_sc) - spread_penalty), 4)

        cons_ranked = _score_and_sort(
            eligible_strategies, baseline_weights_norm, active_objectives, front_set, water_override_by_sid=conservative_scores
        )
        dis_ranked = _score_and_sort(
            eligible_strategies, baseline_weights_norm, active_objectives, front_set, water_override_by_sid=disagreement_scores
        )
        cons_top = cons_ranked[0]["strategy_id"]
        dis_top = dis_ranked[0]["strategy_id"]
        all_clim_agree = clim_agree and cons_top == baseline_winner_id and dis_top == baseline_winner_id
        climate_sens = {
            "status": "EVALUATED",
            "gpm_top_strategy_id": baseline_winner_id,
            "nasa_power_top_strategy_id": power_top,
            "conservative_dry_top_strategy_id": cons_top,
            "disagreement_stress_top_strategy_id": dis_top,
            "climate_dataset_agreement": "ROBUST_GPM_AND_POWER" if clim_agree else "PRECIP_SENSITIVE_RANK_SHIFT",
            "overall_climate_robustness": "ROBUST_ACROSS_ENVELOPE" if all_clim_agree else "SENSITIVE_TO_PRECIP_UNCERTAINTY",
            "precip_spread_mm": precip_spread_mm,
            "power_ordered_strategy_ids": [r["strategy_id"] for r in power_ranked],
            "conservative_ordered_strategy_ids": [r["strategy_id"] for r in cons_ranked],
            "disagreement_ordered_strategy_ids": [r["strategy_id"] for r in dis_ranked],
        }
    else:
        climate_sens = {
            "status": "NOT_EVALUATED",
            "gpm_top_strategy_id": baseline_winner_id,
            "nasa_power_top_strategy_id": None,
            "conservative_dry_top_strategy_id": None,
            "disagreement_stress_top_strategy_id": None,
            "climate_dataset_agreement": "SINGLE_OR_MISSING_PRECIP_SOURCE",
            "overall_climate_robustness": "UNVERIFIED_CLIMATE_ENVELOPE",
            "precip_spread_mm": precip_spread_mm,
        }

    plausible_alternatives: List[Dict[str, Any]] = []
    for row in base_rows[1:]:
        sid = row["strategy_id"]
        gap = round(top_score - row["weighted_score"], 6)
        rel_gap_pct = round((gap / max(top_score, 1e-6)) * 100.0, 2)
        is_near = gap <= margin_thresholds.near_tie_abs or rel_gap_pct <= margin_thresholds.near_tie_rel_pct
        is_narrow = gap <= margin_thresholds.narrow_abs or rel_gap_pct <= margin_thresholds.narrow_rel_pct
        wins = win_counts[sid]
        if is_narrow or wins > 0 or climate_sens.get("nasa_power_top_strategy_id") == sid or climate_sens.get("conservative_dry_top_strategy_id") == sid:
            plausible_alternatives.append(
                {
                    "strategy_id": sid,
                    "baseline_rank": baseline_ranks[sid],
                    "baseline_score": row["weighted_score"],
                    "score_gap_from_top": gap,
                    "relative_gap_pct": rel_gap_pct,
                    "is_near_tie": is_near,
                    "winner_frequency": per_strategy_stability[sid]["winner_frequency"],
                    "top_2_frequency": per_strategy_stability[sid]["top_2_frequency"],
                }
            )

    stability_idx = round(same_winner / total_sc, 4) if total_sc > 0 else 1.0
    near_tie_detected = margin_status in ("NEAR_TIE", "NARROW_MARGIN")

    limitations = [
        non_conf_note,
        f"Margin check: top-two spread = {top_two_margin} ({rel_margin_pct}%, class={margin_status}).",
        "Climate sensitivity perturbs annual GPM vs NASA POWER / dry stress bounds ONLY; daily ET0/soil water balance remains uncalibrated.",
    ]

    return {
        "status": "COMPLETED",
        "baseline_top_strategy_id": baseline_winner_id,
        "baseline_top_two_margin": top_two_margin,
        "relative_top_two_margin_pct": rel_margin_pct,
        "margin_status": margin_status,
        "margin_thresholds": {
            "near_tie_abs": margin_thresholds.near_tie_abs,
            "narrow_abs": margin_thresholds.narrow_abs,
            "near_tie_rel_pct": margin_thresholds.near_tie_rel_pct,
            "narrow_rel_pct": margin_thresholds.narrow_rel_pct,
        },
        "near_tie_detected": near_tie_detected,
        "plausible_alternatives": plausible_alternatives,
        "preferred_strategy_stable": len(winner_changes) == 0,
        "stability_index": stability_idx,
        "top_1_retention": stability_idx,
        "per_strategy_stability": per_strategy_stability,
        "scenarios_evaluated_count": total_sc,
        "winner_changes_count": len(winner_changes),
        "winner_change_scenarios": winner_changes,
        "climate_sensitivity": climate_sens,
        "scenario_results": scenario_results,
        "non_confidence_note": non_conf_note,
        "sensitivity_limitations": limitations,
    }
