"""Phase O — Input Sensitivity & Regression Test Suite (Tasks 7–8).

Covers all six Phase O targeted fixes without weakening existing agronomic guards:
1. water.source = 'unknown' across JSON schema, Pydantic contract, validator, DB DDL, UI, and Phase G/H/I.
2. equipment_constraints alignment: 6 KB tags in UI/engine + explicit UNKNOWN (never PASS) for unmodeled tags.
3. forage_value_weight semantics: preserving DEFAULT_FARMER_WEIGHTS when core weights are omitted, 0.0 -> NOT_APPLICABLE,
   null -> NOT_PROVIDED, single normalization in Phase I, explicit zero-total 422, and UI/API payload parity.
4. crop_history chronological semantics (Winter < Spring < Summer < Autumn), completeness flags
   (NOT_PROVIDED / EXPLICITLY_CONFIRMED_EMPTY / PROVIDED_PARTIAL / PROVIDED_COMPLETE), and concurrent/future 422 rejection.
5. target_crop_ids & excluded_crop_ids intersection rejected cleanly with HTTP 422 TARGET_EXCLUDED_CROP_CONFLICT.
6. Standardized HTTP 422 JSON envelope ({error_code, message, details}) across all validation paths,
   plus baseline determinism, geospatial invariance, and zero cross-request cache leakage.
"""

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

from field_profile_builder import (
    FarmerInputValidationError,
    build_field_profile,
    validate_farmer_input,
    validate_target_excluded_conflict,
)
from src.agronomic import evaluate_crop_for_field, evaluate_crop_sequence, load_knowledge_base
from src.agronomic.temporal_planning import (
    PLANNING_MODE_HISTORICAL,
    SEASON_ORDER,
    TemporalPlanningError,
    assess_crop_history_completeness,
    season_sort_key,
    validate_and_build_planning_timeline,
)
from src.api.app import create_app
from src.api.repository import SQLiteAnalysisRepository
from src.optimization import DEFAULT_FARMER_WEIGHTS, rank_rotation_candidates
from src.output import validate_final_recommendation
from src.rotation import generate_rotation_candidates

REPO_ROOT = Path(__file__).resolve().parent.parent
BELKHEIR_COORDS = [[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]]
REF_DATE = date(2026, 11, 15)


def _belkheir_payload(
    *,
    field_id: str = "FLD_GUELMA_PILOT_01",
    water: Optional[Dict[str, Any]] = None,
    crop_history: Any = None,
    planning: Optional[Dict[str, Any]] = None,
    preferences: Any = "DEFAULT",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "field": {
            "field_id": field_id,
            "field_name": "Belkheir Valley",
            "geometry": {"type": "Polygon", "coordinates": BELKHEIR_COORDS},
            "geometry_crs": "EPSG:4326",
        },
        "water": water or {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
        "crop_history": crop_history,
        "planning": planning
        or {
            "start_season": "Autumn",
            "start_year": 2026,
            "horizon_seasons": 3,
            "planning_mode": PLANNING_MODE_HISTORICAL,
        },
    }
    if preferences == "DEFAULT":
        payload["preferences"] = {
            "target_crop_ids": [],
            "excluded_crop_ids": [],
            "equipment_constraints": None,
            "forage_value_weight": None,
        }
    elif preferences is not None:
        payload["preferences"] = preferences
    return payload


class TestPhaseOUnitFixes(unittest.TestCase):
    """Fast unit tests for Fixes 1–5."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kb = load_knowledge_base()
        cls.fp_rainfed = build_field_profile(_belkheir_payload(), reference_date=REF_DATE)

    def test_01_water_source_unknown_accepted_distinct_and_conservative(self) -> None:
        # 1. Schema + PostGIS SQL + Frontend include 'unknown' cleanly alongside 'other'
        schema = json.loads((REPO_ROOT / "field_input_schema.json").read_text(encoding="utf-8"))
        water_src_enum = schema["properties"]["water"]["properties"]["source"]["enum"]
        self.assertIn("unknown", water_src_enum)
        self.assertIn("other", water_src_enum)

        ddl = (REPO_ROOT / "db" / "schema_postgis.sql").read_text(encoding="utf-8")
        self.assertIn("'unknown'", ddl)
        self.assertIn("'PROVIDED_PARTIAL'", ddl)
        self.assertIn("'PROVIDED_COMPLETE'", ddl)

        html = (REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<option value="unknown">Unknown</option>', html)

        # 2. Unknown water source with moderate/drip NEVER confirms strictly irrigated TOMATO_IND
        fp_src_unk = build_field_profile(
            _belkheir_payload(water={"availability": "moderate", "source": "unknown", "irrigation_system": "drip"}),
            reference_date=REF_DATE,
        )
        tom_eval = evaluate_crop_for_field(fp_src_unk, "TOMATO_IND", target_season="Spring", kb=self.kb)
        rules_tom = {r["rule_id"]: r["status"] for r in tom_eval["rule_evaluations"]}
        self.assertEqual(rules_tom["RULE_WATER_IRRIGATION_GATE"], "UNKNOWN")
        self.assertEqual(rules_tom["RULE_SALINITY_UNMEASURED_IRRIGATION"], "UNKNOWN")
        self.assertFalse(tom_eval["feasible"])

        cand_unk = generate_rotation_candidates(fp_src_unk, kb=self.kb, reference_date=REF_DATE)
        ir_strats = [s for s in cand_unk["strategies"] if s["pattern_id"] == "IRRIGATED_CASH_BREAK"]
        self.assertEqual(ir_strats, [])

        # 3. 'other' with drip stays distinct from 'unknown' and passes irrigation gate (while still UNKNOWN local ECe)
        fp_other = build_field_profile(
            _belkheir_payload(water={"availability": "moderate", "source": "other", "irrigation_system": "drip"}),
            reference_date=REF_DATE,
        )
        tom_other = evaluate_crop_for_field(fp_other, "TOMATO_IND", target_season="Spring", kb=self.kb)
        rules_other = {r["rule_id"]: r["status"] for r in tom_other["rule_evaluations"]}
        self.assertEqual(rules_other["RULE_WATER_IRRIGATION_GATE"], "PASS")
        self.assertEqual(rules_other["RULE_SALINITY_UNMEASURED_IRRIGATION"], "UNKNOWN")

    def test_02_equipment_constraints_kb_alignment_and_unsupported_tags(self) -> None:
        html = (REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        # Dead frontend options replaced by the 6 KB-supported equipment tags
        self.assertNotIn('value="no_sprayer"', html)
        self.assertNotIn('value="no_harvester"', html)
        expected_kb_tags = {
            "no_hay_baler",
            "no_mower",
            "no_drip_irrigation",
            "no_precision_planter",
            "no_potato_harvester",
            "no_sunflower_header",
        }
        actual_kb_tags = {
            tag
            for c in self.kb.crops.values()
            for tag in ((c["parameters"]["machinery_and_operations"]["value"] or {}).get("equipment_tags_sensitive") or [])
        }
        self.assertEqual(actual_kb_tags, expected_kb_tags)
        for tag in expected_kb_tags:
            self.assertIn(f'value="{tag}"', html)

        # Each of the 6 KB tags triggers WARNING on its sensitive crop(s) and PASS on cereal
        tag_target_pairs = [
            ("no_hay_baler", "VETCH_OAT"),
            ("no_mower", "VETCH_OAT"),
            ("no_drip_irrigation", "TOMATO_IND"),
            ("no_precision_planter", "POTATO"),
            ("no_potato_harvester", "POTATO"),
            ("no_sunflower_header", "SUNFLOWER"),
        ]
        for kb_tag, target_cid in tag_target_pairs:
            fp_tag = build_field_profile(
                _belkheir_payload(
                    water={"availability": "moderate", "source": "well", "irrigation_system": "drip"},
                    preferences={"equipment_constraints": [kb_tag]},
                ),
                reference_date=REF_DATE,
            )
            ev_tgt = evaluate_crop_for_field(fp_tag, target_cid, kb=self.kb)
            ev_dw = evaluate_crop_for_field(fp_tag, "DURUM_WHEAT", kb=self.kb)
            self.assertEqual(
                {r["rule_id"]: r["status"] for r in ev_tgt["rule_evaluations"]}["RULE_EQUIPMENT_CONSTRAINT_CHECK"],
                "WARNING",
                f"Expected WARNING for {kb_tag} on {target_cid}",
            )
            self.assertEqual(
                {r["rule_id"]: r["status"] for r in ev_dw["rule_evaluations"]}["RULE_EQUIPMENT_CONSTRAINT_CHECK"],
                "PASS",
            )

        # Unsupported API tags ('no_sprayer', 'no_harvester') return UNKNOWN (NEVER coerced to PASS) & do not invert ranking
        fp_sprayer = build_field_profile(
            _belkheir_payload(preferences={"equipment_constraints": ["no_sprayer"]}),
            reference_date=REF_DATE,
        )
        fp_harv = build_field_profile(
            _belkheir_payload(preferences={"equipment_constraints": ["no_harvester"]}),
            reference_date=REF_DATE,
        )
        for fp_u, tag in ((fp_sprayer, "no_sprayer"), (fp_harv, "no_harvester")):
            ev_dw = evaluate_crop_for_field(fp_u, "DURUM_WHEAT", kb=self.kb)
            ev_vo = evaluate_crop_for_field(fp_u, "VETCH_OAT", kb=self.kb)
            r_dw = [r for r in ev_dw["rule_evaluations"] if r["rule_id"] == "RULE_EQUIPMENT_CONSTRAINT_CHECK"][0]
            r_vo = [r for r in ev_vo["rule_evaluations"] if r["rule_id"] == "RULE_EQUIPMENT_CONSTRAINT_CHECK"][0]
            self.assertEqual(r_dw["status"], "UNKNOWN")
            self.assertEqual(r_vo["status"], "UNKNOWN")  # Never mapped to no_mower / no_hay_baler
            self.assertEqual(r_dw["observed_inputs"]["unsupported_equipment_tags"], [tag])

        rank_sprayer = rank_rotation_candidates(generate_rotation_candidates(fp_sprayer, kb=self.kb), field_profile=fp_sprayer, kb=self.kb)
        rank_harv = rank_rotation_candidates(generate_rotation_candidates(fp_harv, kb=self.kb), field_profile=fp_harv, kb=self.kb)
        self.assertEqual(rank_sprayer["ranked_strategy_ids"], rank_harv["ranked_strategy_ids"])
        self.assertEqual(rank_sprayer["strategies"][0]["scores"]["farmer_priority_fit"]["status"], "PARTIAL")

    def test_03_forage_weight_and_core_weight_preservation(self) -> None:
        # 1. Isolated forage_value_weight=0.0 preserves DEFAULT_FARMER_WEIGHTS (forage inactive NOT_APPLICABLE)
        fp_iso0 = build_field_profile(
            _belkheir_payload(preferences={"forage_value_weight": 0.0}),
            reference_date=REF_DATE,
        )
        cand_iso0 = generate_rotation_candidates(fp_iso0, kb=self.kb, reference_date=REF_DATE)
        rank_iso0 = rank_rotation_candidates(cand_iso0, field_profile=fp_iso0, kb=self.kb)

        fp_base = build_field_profile(_belkheir_payload(), reference_date=REF_DATE)
        rank_base = rank_rotation_candidates(
            generate_rotation_candidates(fp_base, kb=self.kb, reference_date=REF_DATE),
            field_profile=fp_base,
            kb=self.kb,
        )
        self.assertEqual(
            rank_iso0["ranking_methodology"]["raw_farmer_weights"]["water_saving_weight"],
            DEFAULT_FARMER_WEIGHTS["water_saving_weight"],
        )
        self.assertEqual(rank_iso0["ranking_methodology"]["normalized_active_weights"], rank_base["ranking_methodology"]["normalized_active_weights"])
        self.assertEqual(rank_iso0["ranked_strategy_ids"], rank_base["ranked_strategy_ids"])
        self.assertEqual(rank_iso0["strategies"][0]["scores"]["forage_value"]["status"], "NOT_APPLICABLE")

        # 2. Isolated forage_value_weight=0.30 and 0.60 preserve DEFAULT_FARMER_WEIGHTS and score forage SCORED
        for fw in (0.30, 0.60):
            fp_fw = build_field_profile(_belkheir_payload(preferences={"forage_value_weight": fw}), reference_date=REF_DATE)
            rank_fw = rank_rotation_candidates(
                generate_rotation_candidates(fp_fw, kb=self.kb, reference_date=REF_DATE),
                field_profile=fp_fw,
                kb=self.kb,
            )
            rm = rank_fw["ranking_methodology"]
            for ck in ("water_saving_weight", "soil_improvement_weight", "income_weight", "risk_reduction_weight"):
                self.assertEqual(rm["raw_farmer_weights"][ck], DEFAULT_FARMER_WEIGHTS[ck])
            self.assertIn("forage_value", rm["active_weighted_objectives"])
            self.assertAlmostEqual(rm["normalized_active_weight_sum"], 1.0, places=5)
            # income_potential (0.20) is UNKNOWN, so active raw sum is (0.80 + fw)
            self.assertAlmostEqual(rm["normalized_active_weights"]["forage_value"], fw / (0.80 + fw), places=4)

        # 3. Frontend JS no longer injects conflicting core weights (Frontend/API parity)
        app_js = (REPO_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("prefs.water_saving_weight", app_js)
        self.assertNotIn("prefs.soil_improvement_weight", app_js)

        # 4. Zero-total when custom core weight explicitly 0.0 -> ValueError / FarmerInputValidationError
        with self.assertRaises(FarmerInputValidationError) as ctx_z:
            validate_farmer_input(
                _belkheir_payload(
                    preferences={
                        "water_saving_weight": 0.0,
                        "soil_improvement_weight": 0.0,
                        "income_weight": 0.0,
                        "risk_reduction_weight": 0.0,
                        "forage_value_weight": 0.0,
                    }
                ),
                reference_date=REF_DATE,
            )
        self.assertEqual(ctx_z.exception.error_code, "INVALID_PRIORITY_WEIGHTS")

    def test_04_crop_history_chronological_order_and_completeness_states(self) -> None:
        self.assertEqual(SEASON_ORDER, ("Winter", "Spring", "Summer", "Autumn"))
        self.assertLess(season_sort_key(2026, "Winter"), season_sort_key(2026, "Spring"))
        self.assertLess(season_sort_key(2026, "Spring"), season_sort_key(2026, "Summer"))
        self.assertLess(season_sort_key(2026, "Summer"), season_sort_key(2026, "Autumn"))

        # Within-year 2026 predecessors (Winter, Spring, Summer 2026) BEFORE Autumn 2026 -> SEQ_10 == PASS
        for ssn, cname, expected_cid in (
            ("Winter", "Durum Wheat", "DURUM_WHEAT"),
            ("Spring", "Spring Chickpea", "CHICKPEA_SPRING"),
            ("Summer", "Processing Tomato", "TOMATO_IND"),
            ("Autumn", "Barley", "BARLEY"),
        ):
            yr = 2025 if ssn == "Autumn" else 2026
            fp_h = build_field_profile(
                _belkheir_payload(crop_history=[{"season": ssn, "year": yr, "crop_name_raw": cname}]),
                reference_date=REF_DATE,
            )
            self.assertEqual(fp_h["section_a_farmer_provided"]["input_completeness_flags"]["crop_history"], "PROVIDED_PARTIAL")
            cand_h = generate_rotation_candidates(fp_h, kb=self.kb, reference_date=REF_DATE)
            self.assertEqual(cand_h["history_assessment"]["most_recent_predecessor"], expected_cid)
            seq_eval = evaluate_crop_sequence(fp_h, ["DURUM_WHEAT", "FABA_BEAN", "BARLEY"], kb=self.kb)
            seq10 = [r for r in seq_eval["sequence_rule_evaluations"] if r["rule_id"] == "SEQ_10_UNKNOWN_PREDECESSOR_GUARD"][0]
            self.assertEqual(seq10["status"], "PASS")
            self.assertEqual(seq10["observed_inputs"]["prev_year_crop"], expected_cid)

        # Out-of-order multi-season history resolves chronologically to latest season (Spring 2026 > Winter 2026)
        fp_2 = build_field_profile(
            _belkheir_payload(
                crop_history=[
                    {"season": "Spring", "year": 2026, "crop_name_raw": "Spring Chickpea"},
                    {"season": "Winter", "year": 2026, "crop_name_raw": "Durum Wheat"},
                ]
            ),
            reference_date=REF_DATE,
        )
        self.assertEqual(fp_2["section_a_farmer_provided"]["input_completeness_flags"]["crop_history"], "PROVIDED_COMPLETE")
        cand_2 = generate_rotation_candidates(fp_2, kb=self.kb, reference_date=REF_DATE)
        self.assertEqual(cand_2["history_assessment"]["most_recent_predecessor"], "CHICKPEA_SPRING")
        self.assertTrue(cand_2["history_assessment"]["sufficient_for_existing_baseline"])

        # Unresolved crop name -> PROVIDED_PARTIAL & SEQ_10 == UNKNOWN
        fp_unres = build_field_profile(
            _belkheir_payload(crop_history=[{"season": "Autumn", "year": 2025, "crop_name_raw": "Unknown Herb X"}]),
            reference_date=REF_DATE,
        )
        self.assertEqual(fp_unres["section_a_farmer_provided"]["input_completeness_flags"]["crop_history"], "PROVIDED_PARTIAL")
        seq10_u = [
            r for r in evaluate_crop_sequence(fp_unres, ["DURUM_WHEAT", "FABA_BEAN"], kb=self.kb)["sequence_rule_evaluations"]
            if r["rule_id"] == "SEQ_10_UNKNOWN_PREDECESSOR_GUARD"
        ][0]
        self.assertEqual(seq10_u["status"], "UNKNOWN")

        # Null vs [] remain strictly distinct & baseline withheld
        fp_empty = build_field_profile(_belkheir_payload(crop_history=[]), reference_date=REF_DATE)
        self.assertEqual(fp_empty["section_a_farmer_provided"]["input_completeness_flags"]["crop_history"], "EXPLICITLY_CONFIRMED_EMPTY")
        self.assertEqual(self.fp_rainfed["section_a_farmer_provided"]["input_completeness_flags"]["crop_history"], "NOT_PROVIDED")

        # Concurrent (Autumn 2026) and future (Winter 2027) rejected cleanly
        for bad_ssn, bad_yr in (("Autumn", 2026), ("Winter", 2027), ("Spring", 2027)):
            with self.assertRaises(TemporalPlanningError) as tctx:
                validate_and_build_planning_timeline(
                    {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                    crop_history=[{"season": bad_ssn, "year": bad_yr, "crop_name_raw": "Wheat"}],
                    reference_date=REF_DATE,
                )
            self.assertEqual(tctx.exception.error_code, "CROP_HISTORY_AFTER_PLANNING_START")

        # assess_crop_history_completeness never skips an unresolved recent entry to promote 2024
        stale_masked = assess_crop_history_completeness(
            [
                {"season": "Autumn", "year": 2024, "crop_id_resolved": "DURUM_WHEAT"},
                {"season": "Autumn", "year": 2025, "crop_id_resolved": None},
            ],
            "Autumn",
            2026,
        )
        self.assertEqual(stale_masked["completeness_flag"], "PROVIDED_PARTIAL")
        self.assertIsNone(stale_masked["most_recent_predecessor"])


class TestPhaseOAPIFixesAndInvariance(unittest.TestCase):
    """End-to-end API contract, standardized 422 envelope, determinism, and invariance tests."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "phaseO_test.db"
        self.repo = SQLiteAnalysisRepository(self.db_path)
        self.app = create_app(repository=self.repo)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _assert_unified_422(self, resp_json: Dict[str, Any], expected_code: Optional[str] = None) -> None:
        self.assertNotIn("detail", resp_json)
        self.assertIn("error_code", resp_json)
        self.assertIn("message", resp_json)
        self.assertIn("details", resp_json)
        self.assertIsInstance(resp_json["details"], list)
        if expected_code is not None:
            self.assertEqual(resp_json["error_code"], expected_code)

    def test_01_standardized_422_conflicts_and_temporal_errors(self) -> None:
        # 1. Target & excluded conflict -> 422 TARGET_EXCLUDED_CROP_CONFLICT on both /validate and /analyze
        conflict_req = _belkheir_payload(
            preferences={"target_crop_ids": ["FABA_BEAN", "BARLEY"], "excluded_crop_ids": ["FABA_BEAN"]}
        )
        for endpoint in ("/api/v1/fields/validate", "/api/v1/fields/analyze"):
            resp = self.client.post(endpoint, json=conflict_req)
            self.assertEqual(resp.status_code, 422)
            body = resp.json()
            self._assert_unified_422(body, "TARGET_EXCLUDED_CROP_CONFLICT")
            self.assertEqual(body["details"][0]["conflicting_crop_ids"], ["FABA_BEAN"])

        # 2. All-zero custom weights -> 422 INVALID_PRIORITY_WEIGHTS (no 'detail' wrapper)
        zero_req = _belkheir_payload(
            preferences={"water_saving_weight": 0.0, "soil_improvement_weight": 0.0, "forage_value_weight": 0.0}
        )
        r_zero = self.client.post("/api/v1/fields/analyze", json=zero_req)
        self.assertEqual(r_zero.status_code, 422)
        self._assert_unified_422(r_zero.json(), "INVALID_PRIORITY_WEIGHTS")

        # 3. Concurrent / future crop_history -> 422 CROP_HISTORY_AFTER_PLANNING_START
        conc_req = _belkheir_payload(crop_history=[{"season": "Autumn", "year": 2026, "crop_name_raw": "Wheat"}])
        r_conc = self.client.post("/api/v1/fields/validate", json=conc_req)
        self.assertEqual(r_conc.status_code, 422)
        self._assert_unified_422(r_conc.json(), "CROP_HISTORY_AFTER_PLANNING_START")

    def test_02_api_water_unknown_equipment_forage_history_determinism_and_invariance(self) -> None:
        base_req = _belkheir_payload()
        r_base1 = self.client.post("/api/v1/fields/analyze", json=base_req)
        r_base2 = self.client.post("/api/v1/fields/analyze", json=base_req)
        self.assertEqual(r_base1.status_code, 200)
        self.assertEqual(r_base2.status_code, 200)
        b1, b2 = r_base1.json(), r_base2.json()
        self.assertTrue(b1["analysis_id"].startswith("ANAL_"))
        self.assertEqual(b1["analysis_id"], b2["analysis_id"])
        self.assertEqual(b1["payload_sha256"], b2["payload_sha256"])
        self.assertFalse(b1["reused_existing"])
        self.assertTrue(b2["reused_existing"])

        base_geo = b1["field_profile_summary"]["extracted_summary"]
        variants = [
            ("unknown_water", _belkheir_payload(water={"availability": "unknown", "source": "unknown", "irrigation_system": "unknown"})),
            ("winter_2026_hist", _belkheir_payload(crop_history=[{"season": "Winter", "year": 2026, "crop_name_raw": "Durum Wheat"}])),
            ("forage_iso_060", _belkheir_payload(preferences={"forage_value_weight": 0.60})),
            ("equip_no_sprayer", _belkheir_payload(preferences={"equipment_constraints": ["no_sprayer"]})),
        ]
        seen_ids = {b1["analysis_id"]}
        for label, req in variants:
            resp = self.client.post("/api/v1/fields/analyze", json=req)
            self.assertEqual(resp.status_code, 200, f"{label} failed: {resp.text}")
            data = resp.json()
            self.assertTrue(validate_final_recommendation(data["recommendation"])["valid"], f"{label} schema invalid")
            self.assertNotIn(data["analysis_id"], seen_ids, f"Cache leakage / hash collision on {label}")
            seen_ids.add(data["analysis_id"])
            # Strict geospatial invariance across every operational parameter variation
            self.assertEqual(data["field_profile_summary"]["extracted_summary"], base_geo)
            if label == "equip_no_sprayer":
                dq = data["recommendation"]["field_plans"][0]["data_quality"]
                self.assertTrue(any("no_sprayer" in w for w in dq["warnings"]))


if __name__ == "__main__":
    unittest.main()
