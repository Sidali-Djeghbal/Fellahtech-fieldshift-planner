"""Phase Q Regression Tests — Critical Decision Engine Remediation.

Verifies fixes for verified Phase P defects without altering agronomic rules,
DEFAULT_FARMER_WEIGHTS, or fabricating missing data:
- CRITICAL-01: Soil pH soft-constraint failure (`INFEASIBLE_CONSTRAINT`) schema compliance + HTTP 500 error handling
- CRITICAL-02: Single canonical `critical_data_adequacy` blocking endorsement (`EXPLORATORY_ONLY`) while distinguishing PARTIAL
- HIGH-01: Unsupported `income_weight` without economic data never zeroes omitted core weights + emits explicit warnings
- MEDIUM-01: Modeled equipment warnings strictly penalize `farmer_priority_fit` below UNKNOWN baseline
- MEDIUM-02: FAO-56 readiness resolves `centroid_lon_lat` `[lon, lat]` accurately and gates `COMPUTED_FULL` strictly
- End-to-end determinism, `FieldProfile` immutability, zero cross-request leakage, and unmocked HTTP API checks
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional
from unittest import mock

from fastapi.testclient import TestClient

import field_geospatial_processor as fgp
import field_profile_builder as fpb
from src.agronomic import (
    BLOCKING_ADEQUACY_STATUSES,
    assess_critical_data_adequacy,
    evaluate_crop_for_field,
    evaluate_crop_sequence,
    load_knowledge_base,
)
from src.api.app import create_app
from src.api.repository import SQLiteAnalysisRepository
from src.optimization import (
    assess_water_balance_readiness,
    rank_rotation_candidates,
)
from src.output import OutputValidationError, build_final_recommendation, validate_final_recommendation
from src.rotation import generate_rotation_candidates

REF_DATE = date(2026, 11, 15)

POLY_BELKHEIR_NORTH = [[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]]
POLY_PERIURBAN = [[[7.435, 36.443], [7.441, 36.443], [7.441, 36.447], [7.435, 36.447], [7.435, 36.443]]]


def _base_request(
    *,
    field_id: str = "FLD_PHASEQ",
    coords: Any = POLY_BELKHEIR_NORTH,
    water: Optional[Dict[str, Any]] = None,
    crop_history: Any = None,
    preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req: Dict[str, Any] = {
        "field": {
            "field_id": field_id,
            "field_name": f"Phase Q Test {field_id}",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "geometry_crs": "EPSG:4326",
        },
        "water": water or {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
        "crop_history": crop_history,
        "planning": {
            "start_season": "Autumn",
            "start_year": 2026,
            "horizon_seasons": 3,
            "planning_mode": "HISTORICAL_SIMULATION",
        },
    }
    if preferences is not None:
        req["preferences"] = preferences
    return req


def _set_metric(
    geo: Dict[str, Any],
    ds: str,
    key: str,
    val: Any,
    *,
    cov: Optional[float] = None,
    qstatus: Optional[str] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> None:
    metric = geo["extracted_datasets"][ds][key]
    metric["value"] = val
    if cov is not None:
        metric["polygon_coverage_pct"] = cov
    if qstatus is not None:
        metric["quality_status"] = qstatus
    if stats is not None:
        metric["stats"] = stats


def _mask_all_soilgrids(
    geo: Dict[str, Any],
    *,
    wilaya_pct: Optional[float] = None,
    cf: Optional[float] = None,
) -> None:
    for k in ("clay_0_30cm", "sand_0_30cm", "silt_0_30cm", "ph_0_30cm", "soc_0_30cm", "cec_0_30cm"):
        _set_metric(geo, "soilgrids_v6", k, None, cov=0.0, qstatus="UNAVAILABLE_MASKED_PIXEL")
    if wilaya_pct is not None:
        geo["spatial_validation"]["wilaya_overlap_pct"] = wilaya_pct
    if cf is not None:
        st = dict(geo["extracted_datasets"]["crop_frequency"]["crop_frequency_2021_2025"].get("stats") or {})
        st["cropland_share_ge_05_pct"] = round(cf * 100.0, 2)
        _set_metric(geo, "crop_frequency", "crop_frequency_2021_2025", cf, stats=st)


class _PhaseQTestBase(unittest.TestCase):
    base_geo: Dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.kb = load_knowledge_base()
        cls.base_geo = fgp.extract_field_geospatial_context({"type": "Polygon", "coordinates": POLY_BELKHEIR_NORTH})

    def _run_api_with_geo(self, geo: Dict[str, Any], payload: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteAnalysisRepository(db_path=Path(tmpdir) / "phaseQ.sqlite")
            app = create_app(repository=repo)
            client = TestClient(app, raise_server_exceptions=False)
            with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(geo)):
                resp = client.post("/api/v1/fields/analyze", json=payload)
            return resp.status_code, resp.json()

    def _build_direct_pipeline(
        self,
        geo: Dict[str, Any],
        payload: Dict[str, Any],
        *,
        economic_data: Optional[Dict[str, Dict[str, float]]] = None,
        priority_weights: Optional[Dict[str, Optional[float]]] = None,
    ) -> Dict[str, Any]:
        with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(geo)):
            fp = fpb.build_field_profile(copy.deepcopy(payload), reference_date=REF_DATE)
        cand = generate_rotation_candidates(fp, kb=self.kb, reference_date=REF_DATE)
        rank = rank_rotation_candidates(
            cand,
            field_profile=fp,
            priority_weights=priority_weights,
            economic_data=economic_data,
            kb=self.kb,
        )
        rec = build_final_recommendation(fp, cand, rank, kb=self.kb)
        val = validate_final_recommendation(rec, raise_on_error=False)
        return {"fp": fp, "cand": cand, "rank": rank, "rec": rec, "validation": val}


class TestPhaseQCritical01SoilPH(_PhaseQTestBase):
    """Task 1: Soft pH failures emit schema-valid INFEASIBLE_CONSTRAINT distinct from hard failures."""

    def test_01_ph_8_6_rainfed_returns_http200_valid_infeasible_constraint(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _set_metric(geo, "soilgrids_v6", "ph_0_30cm", 8.6)
        status, body = self._run_api_with_geo(geo, _base_request(field_id="Q_PH_86"))
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertEqual(fp0["status"], "NO_ELIGIBLE_STRATEGY")
        self.assertIsNone(fp0["suggested_strategy_id"])
        self.assertEqual(fp0["decision_gate"]["decision_status"], "INFEASIBLE")
        self.assertIsNone(fp0["decision_gate"]["endorsed_recommendation_id"])
        self.assertEqual(fp0["data_quality"]["critical_data_adequacy"]["adequacy_status"], "INSUFFICIENT")
        for s in fp0["strategies"]:
            self.assertEqual(s["feasibility_status"], "INFEASIBLE_CONSTRAINT")
            self.assertIn("INFEASIBLE_CONSTRAINT", s["explanation"]["summary"])
            self.assertIn("RULE_SOIL_PH_SUITABILITY", s["explanation"]["summary"])

    def test_02_ph_9_1_rainfed_returns_http200_valid_infeasible_constraint(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _set_metric(geo, "soilgrids_v6", "ph_0_30cm", 9.1)
        status, body = self._run_api_with_geo(geo, _base_request(field_id="Q_PH_91"))
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertEqual(fp0["decision_gate"]["decision_status"], "INFEASIBLE")
        self.assertIsNone(fp0["decision_gate"]["endorsed_recommendation_id"])
        self.assertTrue(all(s["feasibility_status"] == "INFEASIBLE_CONSTRAINT" for s in fp0["strategies"]))

    def test_03_ph_7_8_drip_target_tomato_soft_fails_tomato_strategy_only(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _set_metric(geo, "soilgrids_v6", "ph_0_30cm", 7.8)
        req = _base_request(
            field_id="Q_PH_78_TOM",
            water={"availability": "abundant", "source": "well", "irrigation_system": "drip"},
            preferences={"target_crop_ids": ["TOMATO_IND"]},
        )
        status, body = self._run_api_with_geo(geo, req)
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        by_id = {s["strategy_id"]: s for s in fp0["strategies"]}
        self.assertIn("STRAT_IRRIGATED_CASH", by_id)
        self.assertEqual(by_id["STRAT_IRRIGATED_CASH"]["feasibility_status"], "INFEASIBLE_CONSTRAINT")
        self.assertIsNotNone(fp0["suggested_strategy_id"])
        self.assertEqual(fp0["decision_gate"]["decision_status"], "REQUIRES_LOCAL_VERIFICATION")
        req_map = {r["crop_id"]: r for r in fp0["requested_crop_results"]}
        self.assertEqual(req_map["TOMATO_IND"]["outcome"], "excluded")
        self.assertIn("tolerance/constraint rule", req_map["TOMATO_IND"]["reason"])

    def test_04_normal_ph_7_2_remains_eligible(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _set_metric(geo, "soilgrids_v6", "ph_0_30cm", 7.2)
        status, body = self._run_api_with_geo(geo, _base_request(field_id="Q_PH_72"))
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertEqual(fp0["decision_gate"]["decision_status"], "REQUIRES_LOCAL_VERIFICATION")
        self.assertIsNotNone(fp0["decision_gate"]["endorsed_recommendation_id"])

    def test_05_hard_constraint_failure_uses_infeasible_hard_constraint(self) -> None:
        with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(self.base_geo)):
            fp_rain = fpb.build_field_profile(_base_request(field_id="Q_HARD_FAIL"), reference_date=REF_DATE)
        fp_high_ph = copy.deepcopy(fp_rain)
        fp_high_ph["section_b_extracted_geospatial"]["extracted_datasets"]["soilgrids_v6"]["ph_0_30cm"]["value"] = 8.6

        # Hard water failure on TOMATO_IND under rainfed conditions -> INFEASIBLE_HARD_CONSTRAINT
        ev_tom_hard = evaluate_crop_for_field(fp_rain, "TOMATO_IND", target_season="Spring", kb=self.kb)
        self.assertEqual(ev_tom_hard["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")
        self.assertIn("RULE_WATER_IRRIGATION_GATE", ev_tom_hard["hard_fail_rules"])
        self.assertEqual(ev_tom_hard["soft_fail_rules"], [])

        # Soft pH failure at pH 8.6 on DURUM_WHEAT -> INFEASIBLE_CONSTRAINT (preserving SOFT_CONSTRAINT severity)
        ev_ph_soft = evaluate_crop_for_field(fp_high_ph, "DURUM_WHEAT", kb=self.kb)
        self.assertEqual(ev_ph_soft["feasibility_status"], "INFEASIBLE_CONSTRAINT")
        self.assertEqual(ev_ph_soft["hard_fail_rules"], [])
        self.assertIn("RULE_SOIL_PH_SUITABILITY", ev_ph_soft["soft_fail_rules"])

        seq_hard = evaluate_crop_sequence(
            fp_rain,
            ["TOMATO_IND", "BARLEY"],
            slot_seasons=["Spring", "Autumn"],
            kb=self.kb,
        )
        self.assertEqual(seq_hard["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")

    def test_06_api_output_validation_error_returns_http500_not_422(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteAnalysisRepository(db_path=Path(tmpdir) / "phaseQ_err.sqlite")
            app = create_app(repository=repo)
            client = TestClient(app, raise_server_exceptions=False)
            with (
                mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(self.base_geo)),
                mock.patch("src.api.pipeline_service.validate_final_recommendation", side_effect=OutputValidationError(["synthetic schema break"])),
            ):
                resp = client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_OUT_ERR"))
        self.assertEqual(resp.status_code, 500)
        body = resp.json()
        self.assertEqual(body["error_code"], "INTERNAL_OUTPUT_VALIDATION_ERROR")


class TestPhaseQCritical02DataAdequacyGate(_PhaseQTestBase):
    """Task 2: Canonical critical_data_adequacy enforces EXPLORATORY_ONLY without conflating PARTIAL."""

    def test_07_soilgrids_cov_0_wilaya_95_gates_exploratory_only(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _mask_all_soilgrids(geo, wilaya_pct=95.0)
        status, body = self._run_api_with_geo(geo, _base_request(field_id="Q_SG0_W95"))
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertEqual(fp0["data_quality"]["critical_data_adequacy"]["adequacy_status"], "INSUFFICIENT")
        self.assertEqual(fp0["recommendation_status"], "EXPLORATORY_ONLY")
        gate = fp0["decision_gate"]
        self.assertEqual(gate["decision_status"], "EXPLORATORY_ONLY")
        self.assertIsNone(gate["endorsed_recommendation_id"])
        self.assertFalse(gate["suggested_strategy_endorsed"])
        self.assertTrue(gate["provisional_only"])
        self.assertIsNotNone(gate["exploratory_candidate_id"])
        self.assertTrue(any(s["weighted_score"] is not None for s in fp0["strategies"]))
        self.assertTrue(all(s["provisional"] is True for s in fp0["strategies"]))

    def test_08_soilgrids_cov_0_crop_freq_020_gates_exploratory_only(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _mask_all_soilgrids(geo, cf=0.20)
        status, body = self._run_api_with_geo(geo, _base_request(field_id="Q_SG0_CF20"))
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertEqual(fp0["land_use_assessment"]["status"], "LAND_USE_LOW_EVIDENCE")
        self.assertEqual(fp0["data_quality"]["critical_data_adequacy"]["adequacy_status"], "INSUFFICIENT")
        self.assertEqual(fp0["decision_gate"]["decision_status"], "EXPLORATORY_ONLY")
        self.assertIsNone(fp0["decision_gate"]["endorsed_recommendation_id"])
        self.assertTrue(any(s["weighted_score"] is not None for s in fp0["strategies"]))

    def test_09_partial_adequacy_belkheir_is_distinct_from_insufficient(self) -> None:
        res = self._build_direct_pipeline(self.base_geo, _base_request(field_id="Q_PARTIAL_OK"))
        self.assertTrue(res["validation"]["valid"])
        fp0 = res["rec"]["field_plans"][0]
        self.assertEqual(fp0["data_quality"]["critical_data_adequacy"]["adequacy_status"], "PARTIAL")
        self.assertEqual(fp0["decision_gate"]["decision_status"], "REQUIRES_LOCAL_VERIFICATION")
        self.assertEqual(fp0["decision_gate"]["endorsed_recommendation_id"], fp0["suggested_strategy_id"])
        self.assertFalse(fp0["decision_gate"]["provisional_only"])

    def test_10_not_assessable_missing_climate_gates_exploratory_only(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _set_metric(geo, "gpm_and_smap", "gpm_annual_precip_2016_2025_mean_mm", None, cov=0.0, qstatus="UNAVAILABLE")
        _set_metric(geo, "nasa_power", "nasa_power_annual_precip_2016_2025_mean_mm", None, cov=0.0, qstatus="UNAVAILABLE")
        status, body = self._run_api_with_geo(geo, _base_request(field_id="Q_NO_CLIMATE"))
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertEqual(fp0["data_quality"]["critical_data_adequacy"]["adequacy_status"], "NOT_ASSESSABLE")
        self.assertEqual(fp0["decision_gate"]["decision_status"], "EXPLORATORY_ONLY")
        self.assertIsNone(fp0["decision_gate"]["endorsed_recommendation_id"])

    def test_11_single_source_of_truth_and_validator_blocks_desync(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        _mask_all_soilgrids(geo, wilaya_pct=95.0)
        res = self._build_direct_pipeline(geo, _base_request(field_id="Q_SSOT"))
        self.assertTrue(res["validation"]["valid"])
        fp0 = res["rec"]["field_plans"][0]
        self.assertEqual(
            res["rank"]["critical_data_adequacy"]["adequacy_status"],
            fp0["data_quality"]["critical_data_adequacy"]["adequacy_status"],
        )
        self.assertEqual(
            res["rank"]["critical_data_adequacy"]["critical_blocker_count"],
            fp0["data_quality"]["critical_data_adequacy"]["critical_blocker_count"],
        )
        canonical = assess_critical_data_adequacy(field_profile=res["fp"], eligible_for_ranking_count=4)
        self.assertIn(canonical["adequacy_status"], BLOCKING_ADEQUACY_STATUSES)

        tampered = copy.deepcopy(res["rec"])
        tampered["field_plans"][0]["decision_gate"]["decision_status"] = "REQUIRES_LOCAL_VERIFICATION"
        tampered["field_plans"][0]["decision_gate"]["endorsed_recommendation_id"] = "STRAT_SOIL_IMPROVEMENT"
        tampered["field_plans"][0]["decision_gate"]["provisional_only"] = False
        bad = validate_final_recommendation(tampered, raise_on_error=False)
        self.assertFalse(bad["valid"])
        self.assertTrue(any("critical_data_adequacy" in e for e in bad["errors"]))


class TestPhaseQHigh01UnsupportedIncomeWeight(_PhaseQTestBase):
    """Task 3: Positive income_weight without economic_data preserves core weights & warns loudly."""

    def test_12_solo_income_weight_preserves_core_defaults_and_warns(self) -> None:
        status, body = self._run_api_with_geo(
            self.base_geo,
            _base_request(field_id="Q_INC_SOLO", preferences={"income_weight": 0.80}),
        )
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        self.assertIsNotNone(fp0["suggested_strategy_id"])
        self.assertEqual(fp0["decision_gate"]["decision_status"], "REQUIRES_LOCAL_VERIFICATION")
        self.assertIsNotNone(fp0["decision_gate"]["endorsed_recommendation_id"])

        rm = fp0["ranking_methodology"]
        self.assertEqual(rm["income_weight_status"], "IGNORED_UNAVAILABLE_ECONOMIC_DATA_DEFAULT_CORE_PRESERVED")
        self.assertEqual(rm["requested_income_weight"], 0.8)
        self.assertAlmostEqual(rm["normalized_active_weight_sum"], 1.0, places=5)
        self.assertTrue(len(rm["weight_warnings"]) >= 1)
        self.assertEqual(
            rm["inactive_objectives_audit"]["income_potential"]["reason"],
            "INCOME_POTENTIAL_UNAVAILABLE_WITHOUT_ECONOMIC_DATA",
        )
        self.assertTrue(
            any("INCOME_WEIGHT_IGNORED_UNAVAILABLE_ECONOMIC_DATA" in w for w in fp0["data_quality"]["warnings"])
        )

    def test_13_mixed_income_and_core_weights_renormalize_with_warning(self) -> None:
        prefs = {
            "water_saving_weight": 0.10,
            "soil_improvement_weight": 0.10,
            "risk_reduction_weight": 0.10,
            "income_weight": 0.70,
        }
        status, body = self._run_api_with_geo(
            self.base_geo,
            _base_request(field_id="Q_INC_MIX", preferences=prefs),
        )
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        fp0 = rec["field_plans"][0]
        rm = fp0["ranking_methodology"]
        self.assertEqual(rm["income_weight_status"], "IGNORED_UNAVAILABLE_ECONOMIC_DATA_RENORMALIZED")
        self.assertAlmostEqual(rm["normalized_active_weight_sum"], 1.0, places=5)
        self.assertTrue(len(rm["weight_warnings"]) >= 1)
        self.assertTrue(
            any("INCOME_WEIGHT_IGNORED_UNAVAILABLE_ECONOMIC_DATA" in w for w in fp0["data_quality"]["warnings"])
        )

    def test_14_income_weight_activates_when_economic_data_supplied(self) -> None:
        econ_mock = {
            c: {"expected_yield_t_ha": 4.0, "price_per_t": 50000.0, "cost_per_ha": 80000.0}
            for c in self.kb.crops
        }
        econ_mock["FABA_BEAN"] = {"expected_yield_t_ha": 8.0, "price_per_t": 120000.0, "cost_per_ha": 90000.0}
        res = self._build_direct_pipeline(
            self.base_geo,
            _base_request(field_id="Q_INC_SCORED", preferences={"income_weight": 0.80}),
            economic_data=econ_mock,
            priority_weights={"income_weight": 0.80},
        )
        self.assertTrue(res["validation"]["valid"])
        rm = res["rec"]["field_plans"][0]["ranking_methodology"]
        self.assertEqual(rm["income_weight_status"], "APPLIED_VERIFIED_ECONOMIC_DATA")
        self.assertEqual(rm["weight_warnings"], [])
        self.assertEqual(rm["active_weighted_objectives"], ["income_potential"])
        self.assertAlmostEqual(rm["normalized_active_weights"]["income_potential"], 1.0, places=5)

    def test_15_forage_weight_alone_keeps_core_weights_without_income_warning(self) -> None:
        status, body = self._run_api_with_geo(
            self.base_geo,
            _base_request(field_id="Q_FORAGE", preferences={"forage_value_weight": 0.50}),
        )
        self.assertEqual(status, 200)
        rec = body["recommendation"]
        self.assertTrue(validate_final_recommendation(rec, raise_on_error=False)["valid"])
        rm = rec["field_plans"][0]["ranking_methodology"]
        self.assertIn("forage_value", rm["active_weighted_objectives"])
        self.assertIn("water_efficiency", rm["active_weighted_objectives"])
        self.assertEqual(rm["income_weight_status"], "DEFAULT_UNAVAILABLE_ECONOMIC_DATA")
        self.assertEqual(rm["weight_warnings"], [])

    def test_16_all_zero_custom_weights_still_rejected_422(self) -> None:
        for idx, prefs in enumerate(
            [
                {
                    "water_saving_weight": 0.0,
                    "soil_improvement_weight": 0.0,
                    "income_weight": 0.0,
                    "risk_reduction_weight": 0.0,
                },
                {"income_weight": 0.0},
            ]
        ):
            status, body = self._run_api_with_geo(
                self.base_geo,
                _base_request(field_id=f"Q_ZERO_{idx}", preferences=prefs),
            )
            self.assertEqual(status, 422)
            self.assertEqual(body["error_code"], "INVALID_PRIORITY_WEIGHTS")


class TestPhaseQMedium01EquipmentParadox(_PhaseQTestBase):
    """Task 4: Essential equipment warning penalties always rank strictly below UNKNOWN (`null`)."""

    @staticmethod
    def _pref_fit_score(api_body: Dict[str, Any], strat_id: str) -> float:
        by_id = {s["strategy_id"]: s for s in api_body["recommendation"]["field_plans"][0]["strategies"]}
        return float(by_id[strat_id]["scores"]["farmer_priority_fit"]["score"])

    def test_17_modeled_hay_equipment_warnings_score_strictly_below_null_and_empty(self) -> None:
        res_empty = self._run_api_with_geo(self.base_geo, _base_request(field_id="Q_EQ_EMPTY", preferences={"equipment_constraints": []}))
        res_null = self._run_api_with_geo(self.base_geo, _base_request(field_id="Q_EQ_NULL", preferences={"equipment_constraints": None}))
        res_baler = self._run_api_with_geo(self.base_geo, _base_request(field_id="Q_EQ_BALER", preferences={"equipment_constraints": ["no_hay_baler"]}))
        res_both = self._run_api_with_geo(
            self.base_geo,
            _base_request(field_id="Q_EQ_BOTH", preferences={"equipment_constraints": ["no_hay_baler", "no_mower"]}),
        )
        for st, _ in (res_empty, res_null, res_baler, res_both):
            self.assertEqual(st, 200)

        sc_empty = self._pref_fit_score(res_empty[1], "STRAT_SOIL_IMPROVEMENT")
        sc_null = self._pref_fit_score(res_null[1], "STRAT_SOIL_IMPROVEMENT")
        sc_baler = self._pref_fit_score(res_baler[1], "STRAT_SOIL_IMPROVEMENT")
        sc_both = self._pref_fit_score(res_both[1], "STRAT_SOIL_IMPROVEMENT")

        self.assertGreater(sc_empty, sc_null)
        self.assertLess(sc_baler, sc_null)
        self.assertLessEqual(sc_both, sc_baler)
        self.assertLess(sc_both, sc_null)

    def test_18_irrigated_cash_equipment_warnings_score_strictly_below_null(self) -> None:
        drip = {"availability": "abundant", "source": "well", "irrigation_system": "drip"}
        st_empty, b_empty = self._run_api_with_geo(
            self.base_geo, _base_request(field_id="Q_DRIP_EMPTY", water=drip, preferences={"equipment_constraints": []})
        )
        st_null, b_null = self._run_api_with_geo(
            self.base_geo, _base_request(field_id="Q_DRIP_NULL", water=drip, preferences={"equipment_constraints": None})
        )
        st_warn, b_warn = self._run_api_with_geo(
            self.base_geo,
            _base_request(
                field_id="Q_DRIP_WARN",
                water=drip,
                preferences={"equipment_constraints": ["no_drip_irrigation", "no_potato_harvester"]},
            ),
        )
        self.assertEqual((st_empty, st_null, st_warn), (200, 200, 200))
        s_empty = self._pref_fit_score(b_empty, "STRAT_IRRIGATED_CASH")
        s_null = self._pref_fit_score(b_null, "STRAT_IRRIGATED_CASH")
        s_warn = self._pref_fit_score(b_warn, "STRAT_IRRIGATED_CASH")
        self.assertGreater(s_empty, s_null)
        self.assertLess(s_warn, s_null)

    def test_19_unmodeled_equipment_tags_stay_unknown_and_warn(self) -> None:
        st_null, b_null = self._run_api_with_geo(
            self.base_geo, _base_request(field_id="Q_EQ_UNK_BASE", preferences={"equipment_constraints": None})
        )
        st_unm, b_unm = self._run_api_with_geo(
            self.base_geo,
            _base_request(field_id="Q_EQ_UNMOD", preferences={"equipment_constraints": ["no_sprayer", "manual_only"]}),
        )
        self.assertEqual((st_null, st_unm), (200, 200))
        self.assertEqual(
            self._pref_fit_score(b_unm, "STRAT_SOIL_IMPROVEMENT"),
            self._pref_fit_score(b_null, "STRAT_SOIL_IMPROVEMENT"),
        )
        self.assertTrue(
            any("UNSUPPORTED_EQUIPMENT_TAG" in w for w in b_unm["recommendation"]["field_plans"][0]["data_quality"]["warnings"])
        )


class TestPhaseQMedium02WaterBalance(_PhaseQTestBase):
    """Task 5: Water balance resolves `centroid_lon_lat` accurately and strictly gates `COMPUTED_FULL`."""

    def test_20_centroid_lon_lat_from_real_profile_extracts_latitude_deg(self) -> None:
        with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(self.base_geo)):
            fp = fpb.build_field_profile(_base_request(field_id="Q_WB_LAT"), reference_date=REF_DATE)
        wb = assess_water_balance_readiness(fp, self.kb.crops)
        expected_lat = round(float(self.base_geo["spatial_validation"]["centroid_lon_lat"][1]), 6)
        self.assertIsNotNone(wb["climate_inputs_present"]["latitude_deg"])
        self.assertAlmostEqual(wb["climate_inputs_present"]["latitude_deg"], expected_lat, places=5)
        self.assertNotIn("centroid_latitude_deg (missing valid parcel centroid latitude in spatial_validation)", wb["missing_inputs"])

    def test_21_legacy_centroid_formats_and_invalid_latitude_guard(self) -> None:
        with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(self.base_geo)):
            fp = fpb.build_field_profile(_base_request(field_id="Q_WB_FMT"), reference_date=REF_DATE)

        fp_dict = copy.deepcopy(fp)
        sv = fp_dict["section_b_extracted_geospatial"]["spatial_validation"]
        sv.pop("centroid_lon_lat", None)
        sv["centroid_lat_lon"] = {"lat": 36.472, "lon": 7.483}
        wb_dict = assess_water_balance_readiness(fp_dict, self.kb.crops)
        self.assertAlmostEqual(wb_dict["climate_inputs_present"]["latitude_deg"], 36.472, places=4)

        fp_bad = copy.deepcopy(fp)
        fp_bad["section_b_extracted_geospatial"]["spatial_validation"]["centroid_lon_lat"] = [7.483, 95.0]
        wb_bad = assess_water_balance_readiness(fp_bad, self.kb.crops)
        self.assertIsNone(wb_bad["climate_inputs_present"]["latitude_deg"])
        self.assertTrue(any("centroid_latitude_deg" in m for m in wb_bad["missing_inputs"]))

    def test_22_strict_computed_full_gating_requires_all_inputs(self) -> None:
        with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(self.base_geo)):
            fp = fpb.build_field_profile(_base_request(field_id="Q_WB_FULL"), reference_date=REF_DATE)
        full_hydro = {
            "wind_speed_2m_ms": 2.1,
            "elevation_m": 250.0,
            "monthly_precipitation_series_mm": [75.0, 65.0, 55.0, 45.0],
            "soil_fc_vol_pct": 32.0,
            "soil_pwp_vol_pct": 16.0,
        }
        wb_kb = assess_water_balance_readiness(fp, self.kb.crops, local_hydrology_inputs=full_hydro)
        self.assertEqual(wb_kb["fao56_water_balance_status"], "PARTIAL")
        self.assertIsNotNone(wb_kb["reference_et0_mm_day"])
        self.assertIsNotNone(wb_kb["effective_precipitation_mm"])

        # Synthetic crop profile with complete Kc + stage lengths allows COMPUTED_FULL (rainfed)
        complete_crops = {
            "DURUM_WHEAT": {
                "crop_id": "DURUM_WHEAT",
                "parameters": {
                    "kc_profile": {"value": {"kc_ini": 0.3, "kc_mid": 1.15, "kc_end": 0.25}},
                    "fao56_stage_lengths_days": {"value": {"l_ini": 30, "l_dev": 45, "l_mid": 65, "l_late": 40}},
                },
            }
        }
        wb_full = assess_water_balance_readiness(fp, complete_crops, local_hydrology_inputs=full_hydro)
        self.assertEqual(wb_full["fao56_water_balance_status"], "COMPUTED_FULL")
        self.assertEqual(wb_full["kc_parameter_readiness_summary"]["crops_with_literature_kc"], 1)

        # Crops with unavailable Kc params must NOT allow COMPUTED_FULL even when empty stage errors=0
        unavailable_crops = {"UNKNOWN_CROP": {"crop_id": "UNKNOWN_CROP", "parameters": {}}}
        wb_unavail_kc = assess_water_balance_readiness(fp, unavailable_crops, local_hydrology_inputs=full_hydro)
        self.assertEqual(wb_unavail_kc["fao56_water_balance_status"], "PARTIAL")

        wb_no_kc = assess_water_balance_readiness(fp, {}, local_hydrology_inputs=full_hydro)
        self.assertNotEqual(wb_no_kc["fao56_water_balance_status"], "COMPUTED_FULL")


class TestPhaseQPlatformDeterminismAndAPI(_PhaseQTestBase):
    """Determinism, FieldProfile immutability, zero cross-request leakage, and unmocked API check."""

    def test_23_determinism_immutability_and_zero_cross_request_leakage(self) -> None:
        geo = copy.deepcopy(self.base_geo)
        with mock.patch("field_profile_builder.extract_field_geospatial_context", return_value=copy.deepcopy(geo)):
            fp = fpb.build_field_profile(_base_request(field_id="Q_IMMUT"), reference_date=REF_DATE)
        sec_b_snap = copy.deepcopy(fp["section_b_extracted_geospatial"])
        cand = generate_rotation_candidates(fp, kb=self.kb, reference_date=REF_DATE)
        rank = rank_rotation_candidates(cand, field_profile=fp, kb=self.kb)
        build_final_recommendation(fp, cand, rank, kb=self.kb)
        self.assertEqual(fp["section_b_extracted_geospatial"], sec_b_snap)

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteAnalysisRepository(db_path=Path(tmpdir) / "phaseQ_seq.sqlite")
            app = create_app(repository=repo)
            client = TestClient(app, raise_server_exceptions=False)

            r_base1 = client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_UNMOCK_BASE1"))
            self.assertEqual(r_base1.status_code, 200)
            rec1 = r_base1.json()["recommendation"]
            self.assertTrue(validate_final_recommendation(rec1, raise_on_error=False)["valid"])

            with mock.patch("field_profile_builder.extract_field_geospatial_context") as m_geo:
                g_ph = copy.deepcopy(geo)
                _set_metric(g_ph, "soilgrids_v6", "ph_0_30cm", 8.6)
                m_geo.return_value = g_ph
                self.assertEqual(client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_SEQ_PH")).status_code, 200)

                m_geo.return_value = copy.deepcopy(geo)
                self.assertEqual(
                    client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_SEQ_INC", preferences={"income_weight": 0.8})).status_code,
                    200,
                )
                self.assertEqual(
                    client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_SEQ_EQ", preferences={"equipment_constraints": ["no_hay_baler"]})).status_code,
                    200,
                )

            r_pu = client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_UNMOCK_PU", coords=POLY_PERIURBAN))
            self.assertEqual(r_pu.status_code, 200)
            rec_pu = r_pu.json()["recommendation"]
            self.assertTrue(validate_final_recommendation(rec_pu, raise_on_error=False)["valid"])
            self.assertEqual(rec_pu["field_plans"][0]["decision_gate"]["decision_status"], "EXPLORATORY_ONLY")
            self.assertIsNone(rec_pu["field_plans"][0]["decision_gate"]["endorsed_recommendation_id"])

            r_base2 = client.post("/api/v1/fields/analyze", json=_base_request(field_id="Q_UNMOCK_BASE2"))
            self.assertEqual(r_base2.status_code, 200)
            rec2 = r_base2.json()["recommendation"]
            self.assertEqual(
                [s["weighted_score"] for s in rec1["field_plans"][0]["strategies"]],
                [s["weighted_score"] for s in rec2["field_plans"][0]["strategies"]],
            )
            self.assertEqual(rec1["field_plans"][0]["decision_gate"], rec2["field_plans"][0]["decision_gate"])
            self.assertEqual(rec1["field_plans"][0]["data_quality"]["critical_data_adequacy"], rec2["field_plans"][0]["data_quality"]["critical_data_adequacy"])
            self.assertEqual(rec1["field_plans"][0]["ranking_methodology"], rec2["field_plans"][0]["ranking_methodology"])


if __name__ == "__main__":
    unittest.main()
