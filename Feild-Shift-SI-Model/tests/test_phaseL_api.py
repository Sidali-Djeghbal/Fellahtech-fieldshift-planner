"""Phase L — End-to-End API, Persistence & Workflow Integration Tests.

Covers all 11 required Section 8 integration checks using FastAPI TestClient
and an isolated temporary SQLite repository (mirroring all 8 PostGIS entities):
1. Valid field submission + persistence + GET retrieval across 8 DB tables
2. Invalid Polygon & forbidden technical input rejection (HTTP 422)
3. Missing optional inputs allowed without blocking analysis
4. Distinct null vs [] behavior (crop_history, equipment_constraints, forage weight)
5. Unknown water availability fail-closed gating (TOMATO_IND unverified)
6. Infeasible rotation & excluded perennial (OLIVE) handling
7. No eligible recommendation -> suggested_strategy_id=null, NO_ELIGIBLE_STRATEGY
8. Partial geospatial Wilaya coverage warning & execution
9. Missing environmental datasets graceful degradation (SoilGrids / S2 unavailable)
10. Draft 2020-12 recommendation schema validation + reference/health/UI endpoints
11. Reproducibility of identical requests + distinct analysis_id on geometry/water change
"""

from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest import mock

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.repository import DatabaseUnavailableError, PostgresPostGISRepository, SQLiteAnalysisRepository
from src.output import validate_final_recommendation

POLY_BELKHEIR = {
    "type": "Polygon",
    "coordinates": [[[7.435, 36.443], [7.441, 36.443], [7.441, 36.447], [7.435, 36.447], [7.435, 36.443]]],
}
POLY_TAMLOUKA = {
    "type": "Polygon",
    "coordinates": [[[7.137, 36.128], [7.143, 36.128], [7.143, 36.132], [7.137, 36.132], [7.137, 36.128]]],
}
POLY_PARTIAL_BORDER = {
    "type": "Polygon",
    "coordinates": [[[7.78, 36.55], [7.83, 36.55], [7.83, 36.59], [7.78, 36.59], [7.78, 36.55]]],
}
POLY_OUTSIDE_GUELMA = {
    "type": "Polygon",
    "coordinates": [[[2.95, 36.70], [3.05, 36.70], [3.05, 36.75], [2.95, 36.75], [2.95, 36.70]]],
}
POLY_SELF_INTERSECT_BOWTIE = {
    "type": "Polygon",
    "coordinates": [[[7.43, 36.44], [7.44, 36.45], [7.44, 36.44], [7.43, 36.45], [7.43, 36.44]]],
}


def _base_payload(field_id: str = "L_FIELD_01", poly: Dict[str, Any] = POLY_BELKHEIR) -> Dict[str, Any]:
    return {
        "field": {
            "field_id": field_id,
            "field_name": "Phase L Integration Test Parcel",
            "geometry": poly,
        },
        "water": {
            "availability": "limited",
            "source": "rainfed",
            "irrigation_system": "none",
        },
        "crop_history": [
            {"season": "Autumn", "year": 2024, "planting_month": 11, "crop_name_raw": "Durum Wheat"}
        ],
        "planning": {
            "start_season": "Autumn",
            "start_year": 2025,
            "horizon_seasons": 3,
            "planning_mode": "HISTORICAL_SIMULATION",
        },
    }


class TestPhaseLApplicationIntegration(unittest.TestCase):
    """End-to-end backend API, repository, UI serving, and edge-case integration suite."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "phaseL_test.db"
        self.repo = SQLiteAnalysisRepository(self.db_path)
        self.app = create_app(repository=self.repo)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_01_health_reference_ui_and_postgres_disconnected_status(self) -> None:
        h = self.client.get("/api/v1/health")
        self.assertEqual(h.status_code, 200)
        hb = h.json()
        self.assertEqual(hb["status"], "ok")
        self.assertEqual(hb["knowledge_base"]["crops_count"], 13)
        self.assertEqual(hb["knowledge_base"]["crop_rules_count"], 15)
        self.assertEqual(hb["knowledge_base"]["sequence_rules_count"], 10)
        self.assertFalse(hb["geospatial_assets"]["gee_tasks_submitted"])
        self.assertEqual(hb["database"]["active_backend"], "sqlite_local")
        self.assertEqual(len(hb["database"]["entities_present"]), 8)

        # Reference endpoints + farmer UI HTML shell
        ref_b = self.client.get("/api/v1/reference/guelma-boundary")
        self.assertEqual(ref_b.status_code, 200)
        self.assertEqual(ref_b.json()["type"], "FeatureCollection")

        ref_c = self.client.get("/api/v1/reference/crops")
        self.assertEqual(ref_c.status_code, 200)
        self.assertEqual(len(ref_c.json()["crops"]), 13)

        ui_res = self.client.get("/")
        self.assertEqual(ui_res.status_code, 200)
        self.assertIn("Field Shift", ui_res.text)

        # Disconnected PostGIS adapter explicitly errors rather than pretending connection
        pg = PostgresPostGISRepository()
        self.assertEqual(pg.status_info()["active_backend"], "DISCONNECTED")
        with self.assertRaises(DatabaseUnavailableError):
            pg.get_analysis("ANAL_DOES_NOT_EXIST")

    def test_02_valid_field_submission_persistence_retrieval_and_schema(self) -> None:
        payload = _base_payload("L_VALID_01")
        v_res = self.client.post("/api/v1/fields/validate", json=payload)
        self.assertEqual(v_res.status_code, 200)
        vb = v_res.json()
        self.assertTrue(vb["valid"])
        self.assertGreater(vb["area_ha"], 20.0)
        self.assertEqual(vb["wilaya_overlap_pct"], 100.0)

        a_res = self.client.post("/api/v1/fields/analyze", json=payload)
        self.assertEqual(a_res.status_code, 200)
        ab = a_res.json()
        self.assertFalse(ab["reused_existing"])
        self.assertTrue(ab["analysis_id"].startswith("ANAL_"))
        val = validate_final_recommendation(ab["recommendation"])
        self.assertTrue(val["valid"], val["errors"])

        # Retrieval via GET /api/v1/analyses/{analysis_id}
        g_res = self.client.get(f"/api/v1/analyses/{ab['analysis_id']}")
        self.assertEqual(g_res.status_code, 200)
        gb = g_res.json()
        self.assertEqual(gb["analysis_id"], ab["analysis_id"])
        self.assertEqual(gb["recommendation"], ab["recommendation"])
        self.assertEqual(gb["original_request"]["field"]["field_id"], "L_VALID_01")

        # Missing analysis returns 404
        missing_res = self.client.get("/api/v1/analyses/ANAL_DOES_NOT_EXIST")
        self.assertEqual(missing_res.status_code, 404)

        # Verify all 8 normalized SQLite tables received records
        conn = sqlite3.connect(self.db_path)
        for tbl in (
            "farmers_users",
            "fields",
            "analysis_requests",
            "crop_history_records",
            "field_profiles",
            "recommendation_results",
            "candidate_strategies",
            "data_provenance_quality_metadata",
        ):
            cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            self.assertGreaterEqual(cnt, 1, f"Expected >=1 row in {tbl}")
        conn.close()

    def test_03_invalid_polygons_and_forbidden_technical_fields_rejected(self) -> None:
        # 1. Self-intersecting bowtie Polygon -> 422
        bowtie = _base_payload("L_BOWTIE", POLY_SELF_INTERSECT_BOWTIE)
        self.assertEqual(self.client.post("/api/v1/fields/validate", json=bowtie).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/fields/analyze", json=bowtie).status_code, 422)

        # 2. Outside Guelma Wilaya -> 422
        outside = _base_payload("L_OUTSIDE", POLY_OUTSIDE_GUELMA)
        r_out = self.client.post("/api/v1/fields/validate", json=outside)
        self.assertEqual(r_out.status_code, 422)
        self.assertEqual(r_out.json()["error_code"], "INVALID_FIELD_POLYGON")
        self.assertIn("outside Guelma", r_out.json()["message"])
        self.assertIsInstance(r_out.json()["details"], list)

        # 3. MultiPolygon rejected -> 422
        multi = _base_payload("L_MULTI")
        multi["field"]["geometry"] = {"type": "MultiPolygon", "coordinates": [POLY_BELKHEIR["coordinates"]]}
        self.assertEqual(self.client.post("/api/v1/fields/validate", json=multi).status_code, 422)

        # 4. Forbidden technical input (soil_ph / ndvi) rejected -> 422
        tech = _base_payload("L_FORBIDDEN_TECH")
        tech["soil_ph"] = 7.2
        r_tech = self.client.post("/api/v1/fields/analyze", json=tech)
        self.assertEqual(r_tech.status_code, 422)
        self.assertEqual(r_tech.json()["error_code"], "INVALID_FARMER_INPUT")

    def test_04_missing_optional_inputs_and_null_vs_empty_list_distinction(self) -> None:
        # 1. Completely omitted optional sections (no crop_history, no preferences)
        minimal = {
            "field": {"field_id": "L_MINIMAL", "geometry": POLY_TAMLOUKA},
            "water": {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
            "planning": {
            "start_season": "Autumn",
            "start_year": 2025,
            "horizon_seasons": 3,
            "planning_mode": "HISTORICAL_SIMULATION",
        },
        }
        r_min = self.client.post("/api/v1/fields/analyze", json=minimal)
        self.assertEqual(r_min.status_code, 200)
        flags_min = r_min.json()["recommendation"]["field_plans"][0]["data_quality"]["input_completeness_flags"]
        self.assertEqual(flags_min["crop_history"], "NOT_PROVIDED")
        self.assertEqual(flags_min["equipment_constraints"], "NOT_PROVIDED")
        self.assertEqual(flags_min["forage_value_weight"], "NOT_PROVIDED")

        # 2. Explicit [] empty list & explicit 0.0 forage weight (paired with positive priorities) vs null
        explicit_empty = copy.deepcopy(minimal)
        explicit_empty["field"]["field_id"] = "L_EMPTY_LISTS"
        explicit_empty["crop_history"] = []
        explicit_empty["preferences"] = {
            "equipment_constraints": [],
            "water_saving_weight": 0.50,
            "soil_improvement_weight": 0.50,
            "forage_value_weight": 0.0,
        }
        r_emp = self.client.post("/api/v1/fields/analyze", json=explicit_empty)
        self.assertEqual(r_emp.status_code, 200)
        flags_emp = r_emp.json()["recommendation"]["field_plans"][0]["data_quality"]["input_completeness_flags"]
        self.assertEqual(flags_emp["crop_history"], "EXPLICITLY_CONFIRMED_EMPTY")
        self.assertEqual(flags_emp["equipment_constraints"], "EXPLICITLY_CONFIRMED_EMPTY")
        self.assertEqual(flags_emp["forage_value_weight"], "PROVIDED")

        # 3. All-zero provided weights cleanly rejected as INVALID_PRIORITY_WEIGHTS (422)
        zero_weights = copy.deepcopy(minimal)
        zero_weights["preferences"] = {
            "water_saving_weight": 0.0,
            "soil_improvement_weight": 0.0,
            "income_weight": 0.0,
            "risk_reduction_weight": 0.0,
            "forage_value_weight": 0.0,
        }
        r_zero = self.client.post("/api/v1/fields/analyze", json=zero_weights)
        self.assertEqual(r_zero.status_code, 422)
        self.assertEqual(r_zero.json()["error_code"], "INVALID_PRIORITY_WEIGHTS")
        self.assertIn("message", r_zero.json())
        self.assertIsInstance(r_zero.json()["details"], list)

    def test_05_unknown_water_infeasible_targets_and_no_eligible_recommendation(self) -> None:
        # 1. Unknown water requesting TOMATO_IND + OLIVE -> never forced pass
        unk_req = _base_payload("L_UNK_WATER")
        unk_req["water"] = {"availability": "unknown", "source": "other", "irrigation_system": "unknown"}
        unk_req["preferences"] = {"target_crop_ids": ["TOMATO_IND", "OLIVE"]}
        r_unk = self.client.post("/api/v1/fields/analyze", json=unk_req)
        self.assertEqual(r_unk.status_code, 200)
        fplan = r_unk.json()["recommendation"]["field_plans"][0]
        self.assertTrue(validate_final_recommendation(r_unk.json()["recommendation"])["valid"])
        req_map = {r["crop_id"]: r for r in fplan["requested_crop_results"]}
        self.assertEqual(req_map["TOMATO_IND"]["outcome"], "unavailable_due_to_insufficient_evidence")
        self.assertEqual(req_map["OLIVE"]["outcome"], "excluded")

        # 2. Exclude all annual scope crops -> NO_ELIGIBLE_STRATEGY with null suggested_strategy_id
        none_elig_req = _base_payload("L_NO_ELIGIBLE")
        none_elig_req["preferences"] = {
            "excluded_crop_ids": [
                "DURUM_WHEAT",
                "SOFT_WHEAT",
                "BARLEY",
                "FABA_BEAN",
                "CHICKPEA_WINTER",
                "CHICKPEA_SPRING",
                "LENTIL",
                "VETCH_OAT",
                "TOMATO_IND",
                "POTATO",
                "SUNFLOWER",
                "BARE_FALLOW",
            ]
        }
        r_none = self.client.post("/api/v1/fields/analyze", json=none_elig_req)
        self.assertEqual(r_none.status_code, 200)
        rec_none = r_none.json()["recommendation"]
        self.assertTrue(validate_final_recommendation(rec_none)["valid"])
        self.assertIsNone(rec_none["field_plans"][0]["suggested_strategy_id"])
        self.assertEqual(rec_none["field_plans"][0]["status"], "NO_ELIGIBLE_STRATEGY")
        self.assertEqual(rec_none["field_plans"][0]["recommendation_status"], "NO_STRATEGY_RECOMMENDED_ALL_INFEASIBLE")

    def test_06_partial_geospatial_coverage_and_missing_environmental_datasets(self) -> None:
        # 1. Cross-border polygon inside/outside Guelma -> validation warnings preserved cleanly
        border_req = _base_payload("L_BORDER_CLIP", POLY_PARTIAL_BORDER)
        v_border = self.client.post("/api/v1/fields/validate", json=border_req)
        self.assertEqual(v_border.status_code, 200)
        self.assertLess(v_border.json()["wilaya_overlap_pct"], 99.0)
        self.assertTrue(len(v_border.json()["validation_warnings"]) >= 1)

        a_border = self.client.post("/api/v1/fields/analyze", json=border_req)
        self.assertEqual(a_border.status_code, 200)
        self.assertTrue(validate_final_recommendation(a_border.json()["recommendation"])["valid"])

        # 2. Simulated missing SoilGrids & Sentinel-2 layers -> clean degradation & lower completeness
        from field_geospatial_processor import extract_field_geospatial_context as real_extract

        def degraded_extract(geometry: Dict[str, Any], geometry_crs: str = "EPSG:4326") -> Dict[str, Any]:
            ctx = copy.deepcopy(real_extract(geometry, geometry_crs=geometry_crs))
            for k in ctx["extracted_datasets"]["soilgrids_v6"]:
                ctx["extracted_datasets"]["soilgrids_v6"][k]["value"] = None
                ctx["extracted_datasets"]["soilgrids_v6"][k]["quality_status"] = "UNAVAILABLE_NOT_INTEGRATED"
            for k in ctx["extracted_datasets"]["sentinel2"]:
                ctx["extracted_datasets"]["sentinel2"][k]["value"] = None
                ctx["extracted_datasets"]["sentinel2"][k]["quality_status"] = "UNAVAILABLE_NOT_INTEGRATED"
            return ctx

        with mock.patch("field_profile_builder.extract_field_geospatial_context", side_effect=degraded_extract):
            r_deg = self.client.post("/api/v1/fields/analyze", json=_base_payload("L_MISSING_LAYERS"))
        self.assertEqual(r_deg.status_code, 200)
        rec_deg = r_deg.json()["recommendation"]
        self.assertTrue(validate_final_recommendation(rec_deg)["valid"])
        fplan_deg = rec_deg["field_plans"][0]
        self.assertLess(fplan_deg["data_quality"]["completeness_score"], 0.60)
        top_sid = fplan_deg["suggested_strategy_id"]
        top_strat = next(s for s in fplan_deg["strategies"] if s["strategy_id"] == top_sid)
        self.assertEqual(top_strat["scores"]["soil_improvement"]["status"], "PARTIAL")

    def test_07_reproducibility_and_distinct_analysis_ids_for_same_field_id(self) -> None:
        req1 = _base_payload("L_SHARED_FIELD_ID", POLY_BELKHEIR)
        req2_identical = _base_payload("L_SHARED_FIELD_ID", POLY_BELKHEIR)
        req3_diff_poly = _base_payload("L_SHARED_FIELD_ID", POLY_TAMLOUKA)
        req4_diff_water = _base_payload("L_SHARED_FIELD_ID", POLY_BELKHEIR)
        req4_diff_water["water"] = {"availability": "abundant", "source": "reservoir", "irrigation_system": "drip"}

        r1 = self.client.post("/api/v1/fields/analyze", json=req1).json()
        r2 = self.client.post("/api/v1/fields/analyze", json=req2_identical).json()
        r3 = self.client.post("/api/v1/fields/analyze", json=req3_diff_poly).json()
        r4 = self.client.post("/api/v1/fields/analyze", json=req4_diff_water).json()

        # Identical requests replay reproducibly
        self.assertEqual(r1["analysis_id"], r2["analysis_id"])
        self.assertEqual(r1["payload_sha256"], r2["payload_sha256"])
        self.assertFalse(r1["reused_existing"])
        self.assertTrue(r2["reused_existing"])
        self.assertEqual(r1["recommendation"], r2["recommendation"])

        # Changing polygon or water with same field_id generates DISTINCT analysis_ids (prevents Phase J hash collision)
        self.assertNotEqual(r1["analysis_id"], r3["analysis_id"])
        self.assertNotEqual(r1["analysis_id"], r4["analysis_id"])
        self.assertNotEqual(r3["analysis_id"], r4["analysis_id"])


if __name__ == "__main__":
    unittest.main()
