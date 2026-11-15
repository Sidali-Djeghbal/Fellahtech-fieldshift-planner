"""Automated test suite for Phase H Crop Rotation Candidate Generator."""

from __future__ import annotations

import unittest
from typing import Any, Dict

from field_profile_builder import FarmerInputValidationError, build_field_profile
from src.rotation.candidate_generator import GenerationConfig, generate_rotation_candidates

POLY_BOUMAHRA = {
    "type": "Polygon",
    "coordinates": [[[7.48, 36.46], [7.485, 36.46], [7.485, 36.465], [7.48, 36.465], [7.48, 36.46]]],
}
POLY_TAMLOUKA = {
    "type": "Polygon",
    "coordinates": [[[7.14, 36.13], [7.145, 36.13], [7.145, 36.135], [7.14, 36.135], [7.14, 36.13]]],
}


def _make_payload(
    *,
    field_id: str = "TEST_FIELD_01",
    geometry: Dict[str, Any] = POLY_BOUMAHRA,
    water: Dict[str, Any] | None = None,
    crop_history: Any = None,
    planning: Dict[str, Any] | None = None,
    preferences: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "field": {
            "field_id": field_id,
            "field_name": f"Parcel {field_id}",
            "geometry": geometry,
        },
        "water": water
        or {
            "availability": "limited",
            "source": "rainfed",
            "irrigation_system": "none",
        },
        "crop_history": crop_history,
        "planning": planning
        or {
            "start_season": "Autumn",
            "start_year": 2026,
            "horizon_seasons": 3,
            "planting_month": 11,
        },
        "preferences": preferences,
    }


class TestPhaseHCandidateGenerator(unittest.TestCase):
    """Comprehensive tests for Phase H candidate generation."""

    def test_valid_horizons_2_3_4_and_invalid_horizon_rejected(self) -> None:
        for h in (2, 3, 4):
            fp = build_field_profile(
                _make_payload(
                    field_id=f"H_{h}",
                    planning={
                        "start_season": "Autumn",
                        "start_year": 2026,
                        "horizon_seasons": h,
                        "planting_month": 11,
                    },
                )
            )
            out = generate_rotation_candidates(fp)
            self.assertGreaterEqual(len(out["strategies"]), 3)
            for strat in out["strategies"]:
                self.assertEqual(len(strat["seasons"]), h)
                self.assertEqual([s["season_order"] for s in strat["seasons"]], list(range(1, h + 1)))
                self.assertEqual([s["calendar_year"] for s in strat["seasons"]], [2026 + i for i in range(h)])

        # Invalid horizon outside 2..4 rejected both at input and generator guard
        with self.assertRaises(FarmerInputValidationError):
            build_field_profile(
                _make_payload(planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 5})
            )
        fp_valid = build_field_profile(_make_payload())
        fp_valid["section_a_farmer_provided"]["planning"]["horizon_seasons"] = 1
        with self.assertRaises(ValueError):
            generate_rotation_candidates(fp_valid)

    def test_missing_vs_empty_crop_history_preserves_unknown_and_omits_baseline(self) -> None:
        for flag_expected, raw_hist in (("NOT_PROVIDED", None), ("EXPLICITLY_CONFIRMED_EMPTY", [])):
            fp = build_field_profile(_make_payload(crop_history=raw_hist))
            out = generate_rotation_candidates(fp)
            self.assertEqual(out["history_assessment"]["completeness_flag"], flag_expected)
            self.assertFalse(out["history_assessment"]["sufficient_for_existing_baseline"])
            self.assertFalse(out["generation_summary"]["existing_baseline_generated"])
            self.assertTrue(all(not s["is_existing_rotation"] for s in out["strategies"]))
            # SEQ_10 predecessor unknown must remain UNKNOWN, never collapsed into PASS
            for strat in out["strategies"]:
                seq10 = [
                    r for r in strat["constraint_evaluations"]["sequence_rules"] if r["rule_id"] == "SEQ_10_UNKNOWN_PREDECESSOR_GUARD"
                ][0]
                self.assertEqual(seq10["status"], "UNKNOWN")

    def test_complete_history_generates_existing_baseline_and_enforces_t_minus_1_break(self) -> None:
        # 2024 Faba bean, 2025 Ble dur -> predecessor is DURUM_WHEAT
        fp = build_field_profile(
            _make_payload(
                crop_history=[
                    {"season": "Autumn", "year": 2024, "planting_month": 11, "crop_name_raw": "Faba bean"},
                    {"season": "Autumn", "year": 2025, "planting_month": 11, "crop_name_raw": "Ble dur"},
                ]
            )
        )
        out = generate_rotation_candidates(fp)
        self.assertTrue(out["history_assessment"]["sufficient_for_existing_baseline"])
        self.assertTrue(out["generation_summary"]["existing_baseline_generated"])
        baselines = [s for s in out["strategies"] if s["is_existing_rotation"]]
        self.assertEqual(len(baselines), 1)
        self.assertEqual(baselines[0]["pattern_id"], "EXISTING_ROTATION_BASELINE")
        self.assertEqual([x["crop_id"] for x in baselines[0]["seasons"]], ["FABA_BEAN", "DURUM_WHEAT", "FABA_BEAN"])
        # Because T-1 (2025) was DURUM_WHEAT, all new eligible cereal-led candidates must avoid back-to-back cereal at slot 1
        eligible = [s for s in out["strategies"] if s["selection_status"] == "SELECTED_CANDIDATE_ELIGIBLE"]
        for s in eligible:
            seq02 = [r for r in s["constraint_evaluations"]["sequence_rules"] if r["rule_id"] == "SEQ_02_CEREAL_REPETITION"][0]
            self.assertEqual(seq02["status"], "PASS")

    def test_existing_baseline_broomrape_violation_flagged_infeasible(self) -> None:
        # 2024 Ble dur, 2025 Faba bean -> projecting [DURUM_WHEAT, FABA_BEAN, DURUM_WHEAT] puts Faba bean in 2025 and 2027 (<3 yrs)
        fp = build_field_profile(
            _make_payload(
                water={"availability": "abundant", "source": "reservoir", "irrigation_system": "drip"},
                crop_history=[
                    {"season": "Autumn", "year": 2024, "planting_month": 11, "crop_name_raw": "Ble dur"},
                    {"season": "Autumn", "year": 2025, "planting_month": 11, "crop_name_raw": "Faba bean"},
                ],
            )
        )
        out = generate_rotation_candidates(fp)
        baseline = [s for s in out["strategies"] if s["is_existing_rotation"]][0]
        self.assertFalse(baseline["feasible"])
        self.assertEqual(baseline["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")
        self.assertTrue(any("SEQ_04_PULSE_BROOMRAPE_BREAK" in msg for msg in baseline["constraint_evaluations"]["hard_fail_reasons"]))

    def test_excluded_and_target_crop_handling_and_precedence(self) -> None:
        fp = build_field_profile(
            _make_payload(
                water={"availability": "abundant", "source": "well", "irrigation_system": "drip"},
                preferences={
                    "target_crop_ids": ["TOMATO_IND", "BARLEY", "OLIVE"],
                    "excluded_crop_ids": ["BARLEY", "LENTIL"],
                },
            )
        )
        out = generate_rotation_candidates(fp)
        eligible = [s for s in out["strategies"] if s["selection_status"] == "SELECTED_CANDIDATE_ELIGIBLE"]
        for strat in eligible:
            crops = {s["crop_id"] for s in strat["seasons"]}
            self.assertNotIn("BARLEY", crops)
            self.assertNotIn("LENTIL", crops)
            self.assertNotIn("OLIVE", crops)

        t_rep = out["preference_handling"]["target_crop_report"]
        self.assertIn("TOMATO_IND", t_rep["included_targets"])
        self.assertIn("BARLEY", t_rep["not_included_reasons"])
        self.assertIn("OLIVE", t_rep["not_included_reasons"])
        self.assertNotIn("OLIVE", t_rep["included_targets"])
        olive_cf = [s for s in out["strategies"] if s["pattern_id"] == "REQUESTED_TARGET_OLIVE"]
        self.assertEqual(len(olive_cf), 1)
        self.assertFalse(olive_cf[0]["feasible"])
        self.assertEqual(olive_cf[0]["selection_status"], "SELECTED_INFEASIBLE_COUNTERFACTUAL")

    def test_optional_forage_and_equipment_null_vs_empty_preserved(self) -> None:
        fp_null = build_field_profile(_make_payload(preferences=None))
        fp_empty = build_field_profile(
            _make_payload(
                preferences={
                    "equipment_constraints": [],
                    "forage_value_weight": None,
                }
            )
        )
        out_null = generate_rotation_candidates(fp_null)
        out_empty = generate_rotation_candidates(fp_empty)
        self.assertEqual(out_null["preference_handling"]["optional_input_completeness"]["equipment_constraints"], "NOT_PROVIDED")
        self.assertEqual(out_null["preference_handling"]["optional_input_completeness"]["forage_value_weight"], "NOT_PROVIDED")
        self.assertEqual(
            out_empty["preference_handling"]["optional_input_completeness"]["equipment_constraints"],
            "EXPLICITLY_CONFIRMED_EMPTY",
        )
        self.assertEqual(out_empty["preference_handling"]["optional_input_completeness"]["forage_value_weight"], "NOT_PROVIDED")

    def test_hard_constraint_failure_and_unknown_water_gating(self) -> None:
        # Rainfed field requesting TOMATO_IND -> hard FAIL
        fp_rainfed = build_field_profile(
            _make_payload(
                water={"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
                preferences={"target_crop_ids": ["TOMATO_IND"]},
            )
        )
        out_rf = generate_rotation_candidates(fp_rainfed)
        tom_rf = [s for s in out_rf["strategies"] if any(x["crop_id"] == "TOMATO_IND" for x in s["seasons"])][0]
        self.assertFalse(tom_rf["feasible"])
        self.assertEqual(tom_rf["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")

        # Unknown water field requesting TOMATO_IND -> UNVERIFIED_HARD_UNKNOWN, feasible=False (never PASS)
        fp_unk = build_field_profile(
            _make_payload(
                water={"availability": "unknown", "source": "other", "irrigation_system": "unknown"},
                preferences={"target_crop_ids": ["TOMATO_IND"]},
            )
        )
        out_unk = generate_rotation_candidates(fp_unk)
        tom_unk = [s for s in out_unk["strategies"] if any(x["crop_id"] == "TOMATO_IND" for x in s["seasons"])][0]
        self.assertFalse(tom_unk["feasible"])
        self.assertEqual(tom_unk["feasibility_status"], "UNVERIFIED_HARD_UNKNOWN")
        self.assertTrue(len(tom_unk["constraint_evaluations"]["hard_unknown_reasons"]) >= 1)

    def test_duplicate_prevention_sequential_ids_and_determinism(self) -> None:
        fp = build_field_profile(
            _make_payload(
                geometry=POLY_TAMLOUKA,
                water={"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
                crop_history=[
                    {"season": "Autumn", "year": 2024, "planting_month": 11, "crop_name_raw": "Barley"},
                    {"season": "Autumn", "year": 2025, "planting_month": 11, "crop_name_raw": "Winter Chickpea"},
                ],
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 4, "planting_month": 11},
            )
        )
        out1 = generate_rotation_candidates(fp)
        out2 = generate_rotation_candidates(fp)

        seqs = [tuple(x["crop_id"] for x in s["seasons"]) for s in out1["strategies"]]
        self.assertEqual(len(seqs), len(set(seqs)))
        self.assertEqual([s["candidate_id"] for s in out1["strategies"]], [f"CAND_{i:02d}" for i in range(1, len(seqs) + 1)])

        # Sequential candidate_ids hold even when include_infeasible_existing_baseline=False
        fp_fail_base = build_field_profile(
            _make_payload(
                water={"availability": "abundant", "source": "reservoir", "irrigation_system": "drip"},
                crop_history=[
                    {"season": "Autumn", "year": 2024, "planting_month": 11, "crop_name_raw": "Ble dur"},
                    {"season": "Autumn", "year": 2025, "planting_month": 11, "crop_name_raw": "Faba bean"},
                ],
            )
        )
        out_nobase = generate_rotation_candidates(fp_fail_base, config=GenerationConfig(include_infeasible_existing_baseline=False))
        self.assertEqual(
            [s["candidate_id"] for s in out_nobase["strategies"]],
            [f"CAND_{i:02d}" for i in range(1, len(out_nobase["strategies"]) + 1)],
        )

        # Deterministic ignoring timestamp
        out1_cmp = {k: v for k, v in out1.items() if k != "generated_at_utc"}
        out2_cmp = {k: v for k, v in out2.items() if k != "generated_at_utc"}
        self.assertEqual(out1_cmp, out2_cmp)

    def test_one_field_per_request_and_no_phase_i_ranking(self) -> None:
        with self.assertRaises((FarmerInputValidationError, ValueError)):
            build_field_profile(
                _make_payload(
                    geometry={
                        "type": "FeatureCollection",
                        "features": [
                            {"type": "Feature", "geometry": POLY_BOUMAHRA, "properties": {}},
                            {"type": "Feature", "geometry": POLY_TAMLOUKA, "properties": {}},
                        ],
                    }
                )
            )
        fp = build_field_profile(_make_payload())
        out = generate_rotation_candidates(fp)
        self.assertIsInstance(out["field_id"], str)
        for strat in out["strategies"]:
            for forbidden_phase_i_key in ("rank", "overall_score", "composite_score", "multi_objective_score"):
                self.assertNotIn(forbidden_phase_i_key, strat)

    def test_spring_start_season_compatibility(self) -> None:
        fp = build_field_profile(
            _make_payload(
                water={"availability": "abundant", "source": "reservoir", "irrigation_system": "drip"},
                planning={
                    "start_season": "Spring",
                    "start_year": 2026,
                    "horizon_seasons": 3,
                    "planting_month": 3,
                    "planning_mode": "HISTORICAL_SIMULATION",
                },
                preferences={"target_crop_ids": ["SUNFLOWER"]},
            )
        )
        out = generate_rotation_candidates(fp)
        eligible = [s for s in out["strategies"] if s["selection_status"] == "SELECTED_CANDIDATE_ELIGIBLE"]
        self.assertGreaterEqual(len(eligible), 4)
        for strat in eligible:
            self.assertEqual(strat["seasons"][0]["agricultural_season"], "Spring")
            slot0_season_rule = [
                r
                for r in strat["seasons"][0]["slot_constraint_evaluations"]
                if r["rule_id"] == "RULE_PLANTING_SEASON_COMPATIBILITY"
            ][0]
            self.assertEqual(slot0_season_rule["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
