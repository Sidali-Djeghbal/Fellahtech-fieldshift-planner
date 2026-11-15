"""Phase I — Multi-Objective Scoring, Pareto Dominance, and Sensitivity Engine."""

from src.optimization.pareto import check_dominance, compute_pareto_front
from src.optimization.scoring_engine import (
    DEFAULT_FARMER_WEIGHTS,
    FARMER_WEIGHT_KEYS,
    OBJECTIVE_ORDER,
    rank_rotation_candidates,
)
from src.optimization.sensitivity import run_sensitivity_analysis

__all__ = [
    "DEFAULT_FARMER_WEIGHTS",
    "FARMER_WEIGHT_KEYS",
    "OBJECTIVE_ORDER",
    "check_dominance",
    "compute_pareto_front",
    "rank_rotation_candidates",
    "run_sensitivity_analysis",
]
