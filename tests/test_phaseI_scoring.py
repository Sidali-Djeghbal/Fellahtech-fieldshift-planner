"""Automated test suite for Phase I Multi-Objective Scoring & Ranking Engine."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path
from typing import Any, Dict

from field_profile_builder import build_field_profile
from src.optimization import OBJECTIVE_ORDER, check_dominance, compute_pareto_front, rank_rotation_candidates
from src.rotation.candidate_generator import generate_rotation_candidates

POLY_BOUMAHRA = {
    "type": "Polygon",
    "coordinates": [[[7.48, 36.46], [7.485, 36.46], [7.485, 36.465], [7.48, 36.465], [7.48, 36.46]]],
}
POLY_TAMLOUKA = {
    "type": "Polygon",
    "coordinates": [[[7.14, 36.13], [7.145, 36.13], [7.145, 36.135], [7.14, 36.135], [7.14, 36.13]]],
}


def _build_phase_h_fixture(
    *,
    geometry: Dict[str, Any] = POLY_BOUMAHRA,
    water: Dict[str, Any] | None = None,
    crop_history: Any = None,
    preferences: Dict[str, Any] | None = None,
    horizon: int = 3,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    payload = {
        "field": {"field_id": "F_PHASEI_TEST", "field_name": "Test Parcel", "geometry": geometry},
        "water": water or {"availability": "abundant", "source": "reservoir", "irrigation_system": "drip"},
        "crop_history": crop_history,
        "planning": {
            "start_season": "Autumn",
            "start_year": 2026,
            "horizon_seasons": horizon,
            "planting_month": 11,
        },
        "preferences": preferences,
    }
    fp = build_field_profile(payload)
    cand = generate_rotation_candidates(fp)
    return fp, cand


class TestPhaseIMultiObjectiveScoring(unittest.TestCase):
    """Comprehensive tests for Phase I scoring, Pareto dominance, and sensitivity."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_cand = json.loads(
            Path("docs/phaseH/sample_candidate_generation_output.json").read_text(encoding="utf-8")
        )
        cls.sample_ranked = rank_rotation_candidates(cls.sample_cand)

    def test_01_infeasible_candidate_excluded_never_recommended(self) -> None:
        # STRAT_EXISTING_BASELINE is INFEASIBLE_HARD_CONSTRAINT in sample_cand
        ranked = self.sample_ranked
        self.assertIn("STRAT_EXISTING_BASELINE", ranked["excluded_infeasible_strategy_ids"])
        self.assertNotIn("STRAT_EXISTING_BASELINE", ranked["ranked_strategy_ids"])
        self.assertNotEqual(ranked["suggested_strategy_id"], "STRAT_EXISTING_BASELINE")
        base_strat = [s for s in ranked["strategies"] if s["strategy_id"] == "STRAT_EXISTING_BASELINE"][0]
        self.assertIsNone(base_strat["rank"])
        self.assertEqual(base_strat["pareto_status"], "EXCLUDED_INFEASIBLE")
        self.assertIsNone(base_strat["weighted_score"])

    def test_02_conditional_feasibility_preserves_warnings_and_no_clean_pass_notice(self) -> None:
        ranked = self.sample_ranked
        self.assertEqual(ranked["feasibility_gate_summary"]["feasible_pass_count"], 0)
        self.assertTrue(ranked["all_candidates_conditional"])
        self.assertEqual(ranked["recommendation_status"], "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION")
        self.assertIn("zero clean FEASIBLE_PASS", ranked["feasibility_gate_summary"]["notice"])
        winner = [s for s in ranked["strategies"] if s["strategy_id"] == ranked["suggested_strategy_id"]][0]
        self.assertEqual(winner["feasibility_status"], "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS")
        self.assertTrue(winner["needs_local_review"])
        self.assertGreater(len(winner["information_gaps"]), 0)

    def test_03_pareto_dominance_and_equal_objective_values(self) -> None:
        # Synthetic strategies testing dominance AND exact equal tie handling
        s_a = {
            "strategy_id": "S_A",
            "scores": {
                "water_efficiency": {"score": 0.80, "status": "SCORED"},
                "soil_improvement": {"score": 0.70, "status": "SCORED"},
                "income_potential": {"score": None, "status": "UNKNOWN"},
            },
        }
        s_b = {
            "strategy_id": "S_B_DOMINATED",
            "scores": {
                "water_efficiency": {"score": 0.70, "status": "SCORED"},
                "soil_improvement": {"score": 0.60, "status": "SCORED"},
                "income_potential": {"score": None, "status": "UNKNOWN"},
            },
        }
        s_c = {
            "strategy_id": "S_C_TIE",
            "scores": {
                "water_efficiency": {"score": 0.80, "status": "SCORED"},
                "soil_improvement": {"score": 0.70, "status": "SCORED"},
                "income_potential": {"score": None, "status": "UNKNOWN"},
            },
        }
        s_d = {
            "strategy_id": "S_D_TRADEOFF",
            "scores": {
                "water_efficiency": {"score": 0.65, "status": "SCORED"},
                "soil_improvement": {"score": 0.90, "status": "SCORED"},
                "income_potential": {"score": None, "status": "UNKNOWN"},
            },
        }
        res = compute_pareto_front([s_a, s_b, s_c, s_d], ["water_efficiency", "soil_improvement", "income_potential"])
        self.assertNotIn("income_potential", res["active_pareto_objectives"])
        self.assertEqual(set(res["front_strategy_ids"]), {"S_A", "S_C_TIE", "S_D_TRADEOFF"})
        self.assertEqual(res["dominated_strategy_ids"], ["S_B_DOMINATED"])
        self.assertEqual(len(res["equal_objective_ties"]), 1)
        dom_ab, eq_ab, _ = check_dominance(s_a["scores"], s_c["scores"], ["water_efficiency", "soil_improvement"])
        self.assertFalse(dom_ab)
        self.assertTrue(eq_ab)

    def test_04_missing_income_unavailable_and_complete_income_activation(self) -> None:
        # Without economic_data -> income_potential is UNKNOWN, score=None, inactive weight=0.0
        for s in self.sample_ranked["strategies"]:
            inc = s["scores"]["income_potential"]
            self.assertEqual(inc["status"], "UNKNOWN")
            self.assertIsNone(inc["score"])
            self.assertIn("qualitative_market_tiers", inc)
            self.assertFalse(inc["active_in_ranking"])
            self.assertEqual(inc["normalized_weight"], 0.0)

        # With complete verified local budget -> income_potential switches cleanly to SCORED
        verified_econ = {
            "DURUM_WHEAT": {"expected_yield_t_ha": 3.5, "price_per_t": 60000.0, "cost_per_ha": 95000.0},
            "CHICKPEA_WINTER": {"net_margin_per_ha": 85000.0},
            "VETCH_OAT": {"net_margin_per_ha": 70000.0},
            "TOMATO_IND": {"expected_yield_t_ha": 55.0, "price_per_t": 22000.0, "cost_per_ha": 480000.0},
            "FABA_BEAN": {"net_margin_per_ha": 90000.0},
            "SUNFLOWER": {"net_margin_per_ha": 110000.0},
        }
        ranked_econ = rank_rotation_candidates(self.sample_cand, economic_data=verified_econ)
        self.assertIn("income_potential", ranked_econ["ranking_methodology"]["active_weighted_objectives"])
        self.assertAlmostEqual(ranked_econ["ranking_methodology"]["normalized_active_weight_sum"], 1.0, places=5)
        for sid in ranked_econ["ranked_strategy_ids"]:
            s = [x for x in ranked_econ["strategies"] if x["strategy_id"] == sid][0]
            self.assertEqual(s["scores"]["income_potential"]["status"], "SCORED")
            self.assertIsNotNone(s["scores"]["income_potential"]["score"])

    def test_05_forage_null_vs_zero_vs_positive_weight(self) -> None:
        # Default sample_cand has forage_value_weight = None (NOT_PROVIDED) -> NOT_APPLICABLE
        w0 = self.sample_ranked["strategies"][0]["scores"]["forage_value"]
        self.assertEqual(w0["status"], "NOT_APPLICABLE")
        self.assertIsNone(w0["score"])
        self.assertFalse(w0["active_in_ranking"])

        # Explicit 0.0 forage weight -> also NOT_APPLICABLE & inactive, remaining active weights sum to 1.0
        _, cand_zero_forage = _build_phase_h_fixture(
            preferences={
                "water_saving_weight": 0.4,
                "soil_improvement_weight": 0.4,
                "risk_reduction_weight": 0.2,
                "forage_value_weight": 0.0,
            }
        )
        ranked_zero = rank_rotation_candidates(
            cand_zero_forage,
            priority_weights={"water_saving_weight": 0.4, "soil_improvement_weight": 0.4, "risk_reduction_weight": 0.2, "forage_value_weight": 0.0},
        )
        self.assertEqual(ranked_zero["strategies"][0]["scores"]["forage_value"]["status"], "NOT_APPLICABLE")
        self.assertEqual(ranked_zero["ranking_methodology"]["normalized_active_weights"]["forage_value"], 0.0)
        self.assertAlmostEqual(ranked_zero["ranking_methodology"]["normalized_active_weight_sum"], 1.0, places=5)

        # Positive forage_value_weight via field_profile -> SCORED and VETCH_OAT sequence gets top forage score
        fp_pos, cand_pos = _build_phase_h_fixture(
            preferences={
                "water_saving_weight": 0.2,
                "soil_improvement_weight": 0.2,
                "risk_reduction_weight": 0.2,
                "forage_value_weight": 0.4,
            }
        )
        ranked_pos = rank_rotation_candidates(cand_pos, field_profile=fp_pos)
        self.assertIn("forage_value", ranked_pos["ranking_methodology"]["active_weighted_objectives"])
        self.assertAlmostEqual(ranked_pos["ranking_methodology"]["normalized_active_weight_sum"], 1.0, places=5)
        for sid in ranked_pos["ranked_strategy_ids"]:
            s = [x for x in ranked_pos["strategies"] if x["strategy_id"] == sid][0]
            self.assertEqual(s["scores"]["forage_value"]["status"], "SCORED")
            self.assertIsNotNone(s["scores"]["forage_value"]["score"])

    def test_06_weight_validation_invalid_and_all_zero_weights(self) -> None:
        bad_weight_cases = [
            {"water_saving_weight": -0.1, "soil_improvement_weight": 0.5},
            {"water_saving_weight": 1.2, "soil_improvement_weight": 0.5},
            {"water_saving_weight": True, "soil_improvement_weight": 0.5},
            {"water_saving_weight": float("nan"), "soil_improvement_weight": 0.5},
            {"unknown_priority_key": 0.5},
            {"water_saving_weight": 0.0, "soil_improvement_weight": 0.0, "income_weight": 0.0, "risk_reduction_weight": 0.0, "forage_value_weight": 0.0},
            {"water_efficiency": 0.5, "water_saving_weight": 0.5},
        ]
        for bad_w in bad_weight_cases:
            with self.assertRaises(ValueError):
                rank_rotation_candidates(self.sample_cand, priority_weights=bad_w)

    def test_07_weight_normalization_and_missing_objective_exclusion(self) -> None:
        ranked = rank_rotation_candidates(
            self.sample_cand,
            priority_weights={
                "water_saving_weight": 0.40,
                "soil_improvement_weight": 0.20,
                "income_weight": 0.20,  # Unknown income -> dropped from denominator!
                "risk_reduction_weight": 0.20,
                "forage_value_weight": None,
            },
        )
        rm = ranked["ranking_methodology"]
        self.assertAlmostEqual(rm["normalized_active_weight_sum"], 1.0, places=5)
        # Water weight 0.40 / (0.40 + 0.20 + 0.20) = 0.50
        self.assertAlmostEqual(rm["normalized_active_weights"]["water_efficiency"], 0.50, places=4)
        self.assertEqual(rm["normalized_active_weights"]["income_potential"], 0.0)
        self.assertEqual(rm["normalized_active_weights"]["forage_value"], 0.0)

    def test_08_sensitivity_analysis_and_climate_envelope(self) -> None:
        sens = self.sample_ranked["sensitivity_analysis"]
        self.assertEqual(sens["status"], "COMPLETED")
        self.assertGreaterEqual(sens["scenarios_evaluated_count"], 15)
        self.assertIsNotNone(sens["stability_index"])
        # Under FOCUS_FARMER_PRIORITY_FIT, STRAT_IRRIGATED_CASH takes rank #1
        self.assertFalse(sens["preferred_strategy_stable"])
        self.assertGreaterEqual(sens["winner_changes_count"], 1)
        self.assertTrue(any(w["scenario_id"] == "FOCUS_FARMER_PRIORITY_FIT" for w in sens["winner_change_scenarios"]))
        self.assertEqual(sens["climate_sensitivity"]["status"], "EVALUATED")
        self.assertIn(
            sens["climate_sensitivity"]["climate_dataset_agreement"],
            ("ROBUST_GPM_AND_POWER", "PRECIP_SENSITIVE_RANK_SHIFT"),
        )

    def test_09_all_infeasible_candidates_returns_no_recommended_strategy(self) -> None:
        all_bad = copy.deepcopy(self.sample_cand)
        for s in all_bad["strategies"]:
            s["feasible"] = False
            s["feasibility_status"] = "INFEASIBLE_HARD_CONSTRAINT"
            s["constraint_evaluations"]["hard_fail_reasons"] = ["TEST_FORCED_HARD_BLOCKER"]
        ranked_none = rank_rotation_candidates(all_bad)
        self.assertIsNone(ranked_none["suggested_strategy_id"])
        self.assertEqual(ranked_none["recommendation_status"], "NO_STRATEGY_RECOMMENDED_ALL_INFEASIBLE")
        self.assertEqual(ranked_none["ranked_strategy_ids"], [])
        self.assertEqual(len(ranked_none["excluded_infeasible_strategy_ids"]), len(all_bad["strategies"]))

    def test_10_reproducibility_and_end_to_end_f_g_h_contract(self) -> None:
        fp_tam, cand_tam = _build_phase_h_fixture(
            geometry=POLY_TAMLOUKA,
            water={"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
            crop_history=None,
            preferences={"excluded_crop_ids": ["OLIVE"], "equipment_constraints": None},
        )
        r1 = rank_rotation_candidates(cand_tam, field_profile=fp_tam)
        r2 = rank_rotation_candidates(cand_tam, field_profile=fp_tam)

        r1_cmp = {k: v for k, v in r1.items() if k != "generated_at_utc"}
        r2_cmp = {k: v for k, v in r2.items() if k != "generated_at_utc"}
        self.assertEqual(r1_cmp, r2_cmp)

        # Verify top-level and per-strategy Section 7 contract fields verbatim
        self.assertIn("suggested_strategy_id", r1)
        self.assertIsNotNone(r1["suggested_strategy_id"])
        required_strategy_keys = {
            "strategy_id",
            "feasibility_status",
            "scores",
            "confidence",
            "explanation",
            "reasons",
            "evidence",
            "benefits",
            "risks",
            "assumptions",
            "information_gaps",
            "needs_local_review",
            "pareto_status",
        }
        for s in r1["strategies"]:
            self.assertTrue(required_strategy_keys.issubset(s.keys()))
            self.assertEqual(tuple(s["scores"].keys()), OBJECTIVE_ORDER)
            # Without crop_history and equipment_constraints, pest_disease_disruption & farmer_priority_fit must be PARTIAL
            self.assertEqual(s["scores"]["pest_disease_disruption"]["status"], "PARTIAL")
            self.assertEqual(s["scores"]["farmer_priority_fit"]["status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
