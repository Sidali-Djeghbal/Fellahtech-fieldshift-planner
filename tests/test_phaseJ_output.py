"""Automated test suite for Phase J Final Recommendation Output Engine."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, Dict

from field_profile_builder import build_field_profile
from src.optimization import rank_rotation_candidates
from src.output import (
    OutputValidationError,
    build_final_recommendation,
    load_output_schema,
    validate_final_recommendation,
)
from src.rotation import generate_rotation_candidates

POLY_BOUMAHRA = {
    "type": "Polygon",
    "coordinates": [[[7.48, 36.46], [7.485, 36.46], [7.485, 36.465], [7.48, 36.465], [7.48, 36.46]]],
}
POLY_TAMLOUKA = {
    "type": "Polygon",
    "coordinates": [[[7.14, 36.13], [7.145, 36.13], [7.145, 36.135], [7.14, 36.135], [7.14, 36.13]]],
}


def _run_pipeline(
    payload: Dict[str, Any],
    *,
    economic_data: Dict[str, Dict[str, float]] | None = None,
    language: str = "en",
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    fp = build_field_profile(payload)
    cand = generate_rotation_candidates(fp)
    ranked = rank_rotation_candidates(cand, field_profile=fp, economic_data=economic_data)
    final_out = build_final_recommendation(fp, cand, ranked, language=language)
    return fp, cand, ranked, final_out


class TestPhaseJOutputEngine(unittest.TestCase):
    """Comprehensive tests for Phase J Final Recommendation Assembly and Schema Validation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_final = json.loads(
            Path("docs/phaseJ/sample_final_recommendation.json").read_text(encoding="utf-8")
        )

    def test_01_sample_partial_output_validates_schema_and_contract(self) -> None:
        res = validate_final_recommendation(self.sample_final)
        self.assertTrue(res["valid"])
        self.assertEqual(res["schema_draft"], "2020-12")
        self.assertEqual(self.sample_final["status"], "PARTIAL")
        fp = self.sample_final["field_plans"][0]
        self.assertEqual(fp["status"], "PARTIAL")
        self.assertIsNotNone(fp["partial_reason"])
        self.assertEqual(fp["suggested_strategy_id"], "STRAT_SOIL_IMPROVEMENT")
        self.assertEqual(fp["recommendation_status"], "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION")
        self.assertIsNotNone(fp["data_quality"]["completeness_score"])
        self.assertGreater(len(fp["data_quality"]["missing_data"]), 0)

    def test_02_complete_output_when_all_layers_and_budgets_present(self) -> None:
        payload = {
            "field": {"field_id": "F_COMPLETE_01", "field_name": "Full Parcel", "geometry": POLY_BOUMAHRA},
            "water": {"availability": "abundant", "source": "rainfed", "irrigation_system": "none"},
            "crop_history": [
                {"season": "Autumn", "year": 2024, "planting_month": 11, "crop_name_raw": "Ble dur"},
                {"season": "Autumn", "year": 2025, "planting_month": 11, "crop_name_raw": "Faba bean"},
            ],
            "planning": {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 2, "planting_month": 11},
            "preferences": {
                "equipment_constraints": [],
                "water_saving_weight": 0.25,
                "soil_improvement_weight": 0.25,
                "income_weight": 0.25,
                "risk_reduction_weight": 0.15,
                "forage_value_weight": 0.10,
            },
        }
        fp = build_field_profile(payload)
        # Inject verified complete local DEM & remove N quarantine in synthetic full-readiness profile
        ds = fp["section_b_extracted_geospatial"]["extracted_datasets"]
        ds["terrain_dem"]["dem_slope_pct"]["value"] = 2.1
        ds["terrain_dem"]["dem_slope_pct"]["quality_status"] = "REMOTE_SENSING_DERIVED"
        ds["terrain_dem"]["dem_elevation_m"]["value"] = 215.0
        ds["terrain_dem"]["dem_elevation_m"]["quality_status"] = "REMOTE_SENSING_DERIVED"
        ds["soilgrids_v6"]["nitrogen_0_30cm"]["quality_status"] = "MEASURED_OR_OBSERVED"
        ds["soilgrids_v6"]["nitrogen_0_30cm"]["value"] = 1.4
        fp["section_d_quality_and_uncertainty"]["quality_status_counts"]["UNAVAILABLE_NOT_INTEGRATED"] = 0
        fp["section_d_quality_and_uncertainty"]["quality_status_counts"]["UNVALIDATED_EXCLUDED"] = 0

        cand = generate_rotation_candidates(fp)
        # Simulate one FEASIBLE_PASS candidate with all warnings/unknowns resolved
        s0 = cand["strategies"][0]
        s0["feasible"] = True
        s0["feasibility_status"] = "FEASIBLE_PASS"
        s0["needs_local_review"] = False
        s0["information_gaps"] = []
        s0["constraint_evaluations"]["overall_status_counts"] = {"PASS": 40, "WARNING": 0, "FAIL": 0, "UNKNOWN": 0}

        econ = {
            c: {"net_margin_per_ha": 100000.0 + idx * 10000.0}
            for idx, c in enumerate(["DURUM_WHEAT", "BARLEY", "SOFT_WHEAT", "FABA_BEAN", "CHICKPEA_WINTER", "VETCH_OAT"])
        }
        ranked = rank_rotation_candidates(cand, field_profile=fp, economic_data=econ)
        final_out = build_final_recommendation(fp, cand, ranked)
        val = validate_final_recommendation(final_out)
        self.assertTrue(val["valid"])
        self.assertEqual(final_out["status"], "COMPLETE")
        self.assertEqual(final_out["field_plans"][0]["status"], "COMPLETE")
        self.assertIsNone(final_out["field_plans"][0]["partial_reason"])

    def test_03_missing_field_data_and_unknown_not_applicable_scores(self) -> None:
        _, _, _, final_out = _run_pipeline(
            {
                "field": {"field_id": "F_TAM_MISSING", "geometry": POLY_TAMLOUKA},
                "water": {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
                "crop_history": None,
                "planning": {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                "preferences": None,
            }
        )
        self.assertTrue(validate_final_recommendation(final_out)["valid"])
        fp = final_out["field_plans"][0]
        self.assertEqual(fp["data_quality"]["input_completeness_flags"]["crop_history"], "NOT_PROVIDED")
        self.assertEqual(fp["data_quality"]["input_completeness_flags"]["forage_value_weight"], "NOT_PROVIDED")
        for s in fp["strategies"]:
            self.assertIsNone(s["scores"]["income_potential"]["score"])
            self.assertEqual(s["scores"]["income_potential"]["status"], "UNKNOWN")
            self.assertIsNone(s["scores"]["forage_value"]["score"])
            self.assertEqual(s["scores"]["forage_value"]["status"], "NOT_APPLICABLE")
            self.assertEqual(s["scores"]["pest_disease_disruption"]["status"], "PARTIAL")

    def test_04_infeasible_exclusion_and_no_eligible_strategy(self) -> None:
        fp_plan = self.sample_final["field_plans"][0]
        infeas = [s for s in fp_plan["strategies"] if s["feasibility_status"] == "INFEASIBLE_HARD_CONSTRAINT"]
        self.assertEqual(len(infeas), 2)
        for inf in infeas:
            self.assertIsNone(inf["rank"])
            self.assertIsNone(inf["weighted_score"])
            self.assertEqual(inf["pareto_status"], "EXCLUDED_INFEASIBLE")
            self.assertNotEqual(fp_plan["suggested_strategy_id"], inf["strategy_id"])

        # Synthetic zero eligible pool
        fp_in = build_field_profile(
            {
                "field": {"field_id": "F_NONE_ELIG", "geometry": POLY_BOUMAHRA},
                "water": {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
                "planning": {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 2},
            }
        )
        cand = generate_rotation_candidates(fp_in)
        for s in cand["strategies"]:
            s["feasible"] = False
            s["feasibility_status"] = "INFEASIBLE_HARD_CONSTRAINT"
            s["constraint_evaluations"]["hard_fail_reasons"] = ["FORCED_TEST_FAIL"]
        ranked = rank_rotation_candidates(cand, field_profile=fp_in)
        final_none = build_final_recommendation(fp_in, cand, ranked)
        self.assertTrue(validate_final_recommendation(final_none)["valid"])
        self.assertIsNone(final_none["field_plans"][0]["suggested_strategy_id"])
        self.assertEqual(final_none["field_plans"][0]["status"], "NO_ELIGIBLE_STRATEGY")

    def test_05_requested_crop_results_all_four_outcomes(self) -> None:
        # 1. Sample output covers included (TOMATO_IND, SUNFLOWER) & excluded (OLIVE)
        req_res = {r["crop_id"]: r["outcome"] for r in self.sample_final["field_plans"][0]["requested_crop_results"]}
        self.assertEqual(req_res["TOMATO_IND"], "included")
        self.assertEqual(req_res["SUNFLOWER"], "included")
        self.assertEqual(req_res["OLIVE"], "excluded")

        # 2. Unknown water with TOMATO_IND -> unavailable_due_to_insufficient_evidence
        _, _, _, out_unk = _run_pipeline(
            {
                "field": {"field_id": "F_UNK_WATER_TOM", "geometry": POLY_BOUMAHRA},
                "water": {"availability": "unknown", "source": "other", "irrigation_system": "unknown"},
                "planning": {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                "preferences": {"target_crop_ids": ["TOMATO_IND", "NONEXISTENT_CROP"]},
            }
        )
        self.assertTrue(validate_final_recommendation(out_unk)["valid"])
        req_unk = {r["crop_id"]: r["outcome"] for r in out_unk["field_plans"][0]["requested_crop_results"]}
        self.assertEqual(req_unk["TOMATO_IND"], "unavailable_due_to_insufficient_evidence")
        self.assertEqual(req_unk["NONEXISTENT_CROP"], "not_evaluated")

    def test_06_evidence_provenance_pareto_and_sensitivity_metadata(self) -> None:
        fp = self.sample_final["field_plans"][0]
        # Pareto & Sensitivity metadata intact
        self.assertEqual(
            set(fp["pareto_summary"]["front_strategy_ids"]),
            {"STRAT_SOIL_IMPROVEMENT", "STRAT_IRRIGATED_CASH", "STRAT_TARGET_SUNFLOWER"},
        )
        self.assertIn("stability_index", fp["sensitivity_summary"])
        self.assertIn("climate_sensitivity", fp["sensitivity_summary"])
        self.assertIn("non_confidence_note", fp["sensitivity_summary"])

        # Structured EvidenceItem provenance check
        for s in fp["strategies"]:
            ev_list = s["explanation"]["evidence"]
            self.assertGreaterEqual(len(ev_list), 15)
            for item in ev_list:
                self.assertIn("data_source", item)
                self.assertIn("parameter", item)
                self.assertIn("observed_value", item)
                self.assertIn("unit", item)
                self.assertIn("period", item)
                self.assertIsInstance(item["derived"], bool)
                self.assertIn("interpretation", item)

    def test_07_schema_draft_2020_12_and_semantic_validator_catches_violations(self) -> None:
        schema = load_output_schema()
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

        # Mutate 1: Null score coerced to 0.0 must fail validator
        bad_zero = copy.deepcopy(self.sample_final)
        bad_zero["field_plans"][0]["strategies"][0]["scores"]["income_potential"]["score"] = 0.0
        with self.assertRaises(OutputValidationError):
            validate_final_recommendation(bad_zero)

        # Mutate 2: Recommending infeasible baseline must fail validator
        bad_sugg = copy.deepcopy(self.sample_final)
        bad_sugg["field_plans"][0]["suggested_strategy_id"] = "STRAT_EXISTING_BASELINE"
        with self.assertRaises(OutputValidationError):
            validate_final_recommendation(bad_sugg)

        # Mutate 3: Non-JSON float NaN must fail strict RFC-8259 check
        bad_nan = copy.deepcopy(self.sample_final)
        bad_nan["field_plans"][0]["data_quality"]["completeness_score"] = float("nan")
        with self.assertRaises(OutputValidationError):
            validate_final_recommendation(bad_nan)

    def test_08_deterministic_output_reproducibility(self) -> None:
        payload = {
            "field": {"field_id": "F_DET_CHECK", "geometry": POLY_TAMLOUKA},
            "water": {"availability": "moderate", "source": "well", "irrigation_system": "drip"},
            "crop_history": [],
            "planning": {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
        }
        fp1 = build_field_profile(payload)
        c1 = generate_rotation_candidates(fp1)
        r1 = rank_rotation_candidates(c1, field_profile=fp1)
        out1 = build_final_recommendation(fp1, c1, r1, generated_at="2026-11-15T00:00:00+00:00")

        fp2 = build_field_profile(payload)
        c2 = generate_rotation_candidates(fp2)
        r2 = rank_rotation_candidates(c2, field_profile=fp2)
        out2 = build_final_recommendation(fp2, c2, r2, generated_at="2026-11-15T00:00:00+00:00")

        self.assertEqual(json.dumps(out1, sort_keys=True), json.dumps(out2, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
