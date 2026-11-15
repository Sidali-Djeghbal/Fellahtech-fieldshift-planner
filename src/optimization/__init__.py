"""Phase I — Multi-Objective Scoring, Pareto Dominance, and Sensitivity Engine."""

from src.optimization.pareto import check_dominance, compute_pareto_front
from src.optimization.scoring_engine import (
    DEFAULT_FARMER_WEIGHTS,
    FARMER_WEIGHT_KEYS,
    OBJECTIVE_ORDER,
    rank_rotation_candidates,
)
from src.optimization.sensitivity import MarginThresholds, classify_margin_status, run_sensitivity_analysis
from src.optimization.water_balance import (
    assess_water_balance_readiness,
    compute_effective_precip_usda_scs_monthly,
    compute_fao56_penman_monteith_et0_daily,
    extract_crop_fao56_parameters,
)

__all__ = [
    "DEFAULT_FARMER_WEIGHTS",
    "FARMER_WEIGHT_KEYS",
    "OBJECTIVE_ORDER",
    "MarginThresholds",
    "assess_water_balance_readiness",
    "check_dominance",
    "classify_margin_status",
    "compute_effective_precip_usda_scs_monthly",
    "compute_fao56_penman_monteith_et0_daily",
    "compute_pareto_front",
    "extract_crop_fao56_parameters",
    "rank_rotation_candidates",
    "run_sensitivity_analysis",
]
