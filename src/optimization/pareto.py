"""Pareto dominance analysis for evidence-aware crop rotation strategies.

Handles active scorable objectives strictly while preventing UNKNOWN or
NOT_APPLICABLE objectives from being coerced to zero or causing false dominance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

ACTIVE_SCORE_STATUSES = ("SCORED", "PARTIAL")


def identify_common_active_objectives(
    eligible_strategies: Sequence[Dict[str, Any]],
    objective_order: Sequence[str],
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Return objectives that are numerically scorable (SCORED or PARTIAL) across all eligible strategies."""
    active: List[str] = []
    excluded_reasons: Dict[str, List[str]] = {}
    if not eligible_strategies:
        return active, excluded_reasons

    for obj_id in objective_order:
        reasons: List[str] = []
        all_scorable = True
        for strat in eligible_strategies:
            obj_eval = strat["scores"].get(obj_id, {})
            status = obj_eval.get("status", "UNKNOWN")
            val = obj_eval.get("score")
            if status not in ACTIVE_SCORE_STATUSES or val is None:
                all_scorable = False
                reasons.append(f"{strat['strategy_id']}: status={status}")
        if all_scorable:
            active.append(obj_id)
        else:
            excluded_reasons[obj_id] = reasons
    return active, excluded_reasons


def check_dominance(
    scores_a: Dict[str, Dict[str, Any]],
    scores_b: Dict[str, Dict[str, Any]],
    objective_ids: Sequence[str],
    eps: float = 1e-9,
) -> Tuple[bool, bool, Dict[str, float]]:
    """Evaluate pairwise Pareto dominance of strategy A over strategy B (higher is better).

    Returns `(dominates, equal_tie, margins)` over the common scorable subset of `objective_ids`.
    If strategies share zero scorable objectives, returns `(False, False, {})`.
    """
    shared: List[str] = []
    for k in objective_ids:
        a_obj = scores_a.get(k, {})
        b_obj = scores_b.get(k, {})
        if (
            a_obj.get("status") in ACTIVE_SCORE_STATUSES
            and b_obj.get("status") in ACTIVE_SCORE_STATUSES
            and a_obj.get("score") is not None
            and b_obj.get("score") is not None
        ):
            shared.append(k)

    if not shared:
        return False, False, {}

    margins = {k: round(float(scores_a[k]["score"]) - float(scores_b[k]["score"]), 6) for k in shared}
    all_ge = all(float(scores_a[k]["score"]) >= float(scores_b[k]["score"]) - eps for k in shared)
    any_gt = any(float(scores_a[k]["score"]) > float(scores_b[k]["score"]) + eps for k in shared)
    all_eq = all(abs(float(scores_a[k]["score"]) - float(scores_b[k]["score"])) <= eps for k in shared)
    return (all_ge and any_gt), all_eq, margins


def compute_pareto_front(
    eligible_strategies: Sequence[Dict[str, Any]],
    objective_order: Sequence[str],
    eps: float = 1e-9,
) -> Dict[str, Any]:
    """Partition feasible/conditional strategies into non-dominated Pareto front vs dominated options."""
    active_objs, inactive_pareto = identify_common_active_objectives(eligible_strategies, objective_order)

    if not eligible_strategies or not active_objs:
        return {
            "active_pareto_objectives": active_objs,
            "excluded_from_pareto_objectives": inactive_pareto,
            "front_strategy_ids": [],
            "dominated_strategy_ids": [],
            "dominance_relations": [],
            "equal_objective_ties": [],
            "strategy_pareto_map": {
                s["strategy_id"]: {
                    "pareto_status": "UNRANKED_INSUFFICIENT_DATA",
                    "dominated_by": [],
                    "dominates": [],
                }
                for s in eligible_strategies
            },
        }

    dominated_by: Dict[str, List[str]] = {s["strategy_id"]: [] for s in eligible_strategies}
    dominates_map: Dict[str, List[str]] = {s["strategy_id"]: [] for s in eligible_strategies}
    relations: List[Dict[str, Any]] = []
    equal_ties: List[Dict[str, Any]] = []

    n = len(eligible_strategies)
    for i in range(n):
        for j in range(i + 1, n):
            sa = eligible_strategies[i]
            sb = eligible_strategies[j]
            sid_a = sa["strategy_id"]
            sid_b = sb["strategy_id"]

            a_dom_b, eq_ab, margins_ab = check_dominance(sa["scores"], sb["scores"], active_objs, eps=eps)
            if eq_ab:
                equal_ties.append(
                    {
                        "strategy_a": sid_a,
                        "strategy_b": sid_b,
                        "compared_objectives": list(margins_ab.keys()),
                    }
                )
                continue

            if a_dom_b:
                dominated_by[sid_b].append(sid_a)
                dominates_map[sid_a].append(sid_b)
                relations.append(
                    {
                        "dominator": sid_a,
                        "dominated": sid_b,
                        "objective_margins": margins_ab,
                    }
                )
            else:
                b_dom_a, _, margins_ba = check_dominance(sb["scores"], sa["scores"], active_objs, eps=eps)
                if b_dom_a:
                    dominated_by[sid_a].append(sid_b)
                    dominates_map[sid_b].append(sid_a)
                    relations.append(
                        {
                            "dominator": sid_b,
                            "dominated": sid_a,
                            "objective_margins": margins_ba,
                        }
                    )

    front_ids: List[str] = []
    dominated_ids: List[str] = []
    strat_map: Dict[str, Dict[str, Any]] = {}

    for s in eligible_strategies:
        sid = s["strategy_id"]
        doms = dominated_by[sid]
        if not doms:
            front_ids.append(sid)
            pstatus = "NON_DOMINATED_PARETO_FRONT"
        else:
            dominated_ids.append(sid)
            pstatus = "DOMINATED"
        strat_map[sid] = {
            "pareto_status": pstatus,
            "dominated_by": sorted(doms),
            "dominates": sorted(dominates_map[sid]),
        }

    return {
        "active_pareto_objectives": active_objs,
        "excluded_from_pareto_objectives": inactive_pareto,
        "front_strategy_ids": front_ids,
        "dominated_strategy_ids": dominated_ids,
        "dominance_relations": relations,
        "equal_objective_ties": equal_ties,
        "strategy_pareto_map": strat_map,
    }
