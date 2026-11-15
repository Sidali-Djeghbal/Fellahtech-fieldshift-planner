"""Comprehensive Phase N verification tests: Decision Reliability & Scientific Hardening."""

from __future__ import annotations

import copy
import unittest
from datetime import date

from fastapi.testclient import TestClient

from field_profile_builder import FarmerInputValidationError, build_field_profile, validate_farmer_input
from src.agronomic import (
    LAND_USE_CONFLICTING_EVIDENCE,
    LAND_USE_DATA_UNAVAILABLE,
    LAND_USE_LOW_EVIDENCE,
    LAND_USE_SUPPORTED,
    LAND_USE_UNVERIFIED,
    PLANNING_MODE_CURRENT,
    PLANNING_MODE_HISTORICAL,
    TemporalPlanningError,
    assess_land_use,
    evaluate_crop_sequence,
    load_knowledge_base,
    validate_and_build_planning_timeline,
)
from src.api import SQLiteAnalysisRepository, create_app
from src.optimization import (
    MarginThresholds,
    assess_water_balance_readiness,
    classify_margin_status,
    compute_effective_precip_usda_scs_monthly,
    compute_fao56_penman_monteith_et0_daily,
    rank_rotation_candidates,
    run_sensitivity_analysis,
)
from src.output import OutputValidationError, build_final_recommendation, validate_final_recommendation
from src.rotation import generate_rotation_candidates

# Actual ANAL_248892E4C4DFE796 polygon (peri-urban Guelma south-east fringe)
POLY_ANAL_248892_PERIURBAN = {
    "type": "Polygon",
    "coordinates": [[[7.435, 36.443], [7.441, 36.443], [7.441, 36.447], [7.435, 36.447], [7.435, 36.443]]],
}

# Verified Seybouse/Belkheir agricultural alluvial parcel
POLY_BELKHEIR_CROPLAND = {
    "type": "Polygon",
    "coordinates": [[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]],
}


def _payload(
    *,
    field_id: str,
    geometry: dict,
    planning: dict,
    water: dict | None = None,
    crop_history=None,
    preferences=None,
) -> dict:
    req = {
        "field": {"field_id": field_id, "field_name": field_id, "geometry": geometry},
        "water": water or {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
        "planning": planning,
    }
    if crop_history is not None:
        req["crop_history"] = crop_history
    if preferences is not None:
        req["preferences"] = preferences
    return req


def _synthetic_mock_profile(
    *,
    cf_val: float | None,
    cf_share: float | None = None,
    cf_status: str = "REMOTE_SENSING_DERIVED",
    sg_cov: float | None = 100.0,
    sg_val: float | None = 38.0,
    sg_status: str = "MODELED_SOILGRIDS",
    s2_ndvi: float | None = 0.45,
    modis_spring: float | None = 0.45,
    crop_history=None,
    wilaya_overlap_pct: float = 100.0,
    area_ha: float = 20.0,
) -> dict:
    return {
        "section_a_farmer_provided": {
            "field": {"field_id": "SYNTH_LU"},
            "water": {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
            "crop_history": crop_history,
        },
        "section_b_extracted_geospatial": {
            "spatial_validation": {
                "area_ha": area_ha,
                "wilaya_overlap_pct": wilaya_overlap_pct,
                "centroid_lat_lon": {"lat": 36.46, "lon": 7.48},
            },
            "extracted_datasets": {
                "crop_frequency": {
                    "crop_frequency_2021_2025": {
                        "value": cf_val,
                        "quality_status": cf_status,
                        "valid_pixel_count": 2000 if cf_val is not None else 0,
                        "polygon_coverage_pct": 100.0 if cf_val is not None else 0.0,
                        "stats": {"cropland_share_ge_05_pct": cf_share} if cf_share is not None else {},
                    }
                },
                "soilgrids_v6": {
                    "clay_0_30cm": {
                        "value": sg_val,
                        "quality_status": sg_status,
                        "valid_pixel_count": 8 if sg_val is not None else 0,
                        "polygon_coverage_pct": sg_cov,
                    },
                    "nitrogen_0_30cm": {"value": None, "quality_status": "UNVALIDATED_EXCLUDED"},
                },
                "sentinel2": {"s2_2024_03_ndvi_10m": {"value": s2_ndvi}},
                "modis": {
                    "modis_ndvi_spring_2016_2025_mean": {"value": modis_spring},
                    "modis_ndvi_winter_2016_2025_mean": {"value": modis_spring},
                },
                "nasa_power": {
                    "nasa_power_t2m_min_2016_2025_mean_c": {"value": 10.5},
                    "nasa_power_t2m_max_2016_2025_mean_c": {"value": 24.5},
                    "nasa_power_rh2m_2016_2025_mean_pct": {"value": 64.0},
                    "nasa_power_solar_sw_2016_2025_mean_kwh_m2_day": {"value": 4.9},
                    "nasa_power_annual_precip_2016_2025_mean_mm": {"value": 720.0},
                },
                "terrain_dem": {"dem_elevation_m": {"value": None, "quality_status": "UNAVAILABLE_NOT_INTEGRATED"}},
            },
        },
    }


def _fixed_clock() -> date:
    return date(2026, 11, 15)


class TestPhaseNHardening(unittest.TestCase):
    """Phase N scientific hardening and decision reliability tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kb = load_knowledge_base()
        cls.ref_clock = staticmethod(_fixed_clock)

    def test_01_anal_248892_periurban_regression_vs_real_belkheir(self) -> None:
        # 1A: ANAL_248892 polygon WITH claimed cropping history -> LAND_USE_CONFLICTING_EVIDENCE & EXPLORATORY_ONLY
        fp_conflict = build_field_profile(
            _payload(
                field_id="ANAL_248892_CONFLICT",
                geometry=POLY_ANAL_248892_PERIURBAN,
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                crop_history=[{"season": "Autumn", "year": 2024, "crop_name_raw": "Durum Wheat"}],
            ),
            clock=self.ref_clock,
        )
        lu_conflict = fp_conflict["section_c_agronomic_knowledge_base"]["land_use_assessment"]
        self.assertEqual(lu_conflict["status"], LAND_USE_CONFLICTING_EVIDENCE)
        self.assertTrue(lu_conflict["is_provisional"])
        self.assertTrue(lu_conflict["soilgrids_urban_masked_suspected"])

        cand = generate_rotation_candidates(fp_conflict, kb=self.kb, clock=self.ref_clock)
        ranked = rank_rotation_candidates(cand, field_profile=fp_conflict, kb=self.kb)
        final_out = build_final_recommendation(fp_conflict, cand, ranked, kb=self.kb)
        val = validate_final_recommendation(final_out)
        self.assertTrue(val["valid"], val["errors"])

        fplan = final_out["field_plans"][0]
        self.assertEqual(fplan["recommendation_status"], "EXPLORATORY_ONLY")
        self.assertEqual(fplan["decision_gate"]["decision_status"], "EXPLORATORY_ONLY")
        self.assertIsNone(fplan["decision_gate"]["endorsed_recommendation_id"])
        self.assertTrue(fplan["decision_gate"]["provisional_only"])
        self.assertIsNotNone(fplan["decision_gate"]["exploratory_candidate_id"])
        self.assertTrue(all(s["provisional"] for s in fplan["strategies"]))
        self.assertGreater(fplan["data_quality"]["completeness_score"], 0.70)
        self.assertEqual(fplan["data_quality"]["critical_data_adequacy"]["adequacy_status"], "INSUFFICIENT")

        # 1B: ANAL_248892 polygon WITHOUT crop history -> LAND_USE_UNVERIFIED & EXPLORATORY_ONLY
        fp_unver = build_field_profile(
            _payload(
                field_id="ANAL_248892_UNVER",
                geometry=POLY_ANAL_248892_PERIURBAN,
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
            ),
            clock=self.ref_clock,
        )
        self.assertEqual(
            fp_unver["section_c_agronomic_knowledge_base"]["land_use_assessment"]["status"],
            LAND_USE_UNVERIFIED,
        )

        # 1C: Verified Belkheir Seybouse farmland -> LAND_USE_SUPPORTED & non-exploratory
        fp_belkheir = build_field_profile(
            _payload(
                field_id="BELKHEIR_VERIFIED",
                geometry=POLY_BELKHEIR_CROPLAND,
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                crop_history=[{"season": "Autumn", "year": 2024, "crop_name_raw": "Durum Wheat"}],
            ),
            clock=self.ref_clock,
        )
        lu_ok = fp_belkheir["section_c_agronomic_knowledge_base"]["land_use_assessment"]
        self.assertEqual(lu_ok["status"], LAND_USE_SUPPORTED)
        self.assertGreater(lu_ok["crop_frequency_mean"], 0.80)
        self.assertEqual(lu_ok["soilgrids_clay_coverage_pct"], 100.0)
        self.assertFalse(lu_ok["is_provisional"])

        cand_b = generate_rotation_candidates(fp_belkheir, kb=self.kb, clock=self.ref_clock)
        rank_b = rank_rotation_candidates(cand_b, field_profile=fp_belkheir, kb=self.kb)
        out_b = build_final_recommendation(fp_belkheir, cand_b, rank_b, kb=self.kb)
        self.assertTrue(validate_final_recommendation(out_b)["valid"])
        gate_b = out_b["field_plans"][0]["decision_gate"]
        self.assertNotEqual(gate_b["decision_status"], "EXPLORATORY_ONLY")
        self.assertEqual(gate_b["endorsed_recommendation_id"], out_b["field_plans"][0]["suggested_strategy_id"])

    def test_02_all_five_land_use_states_unit(self) -> None:
        self.assertEqual(
            assess_land_use(_synthetic_mock_profile(cf_val=0.82, cf_share=86.0, sg_cov=100.0))["status"],
            LAND_USE_SUPPORTED,
        )
        self.assertEqual(
            assess_land_use(_synthetic_mock_profile(cf_val=0.18, cf_share=16.0, sg_cov=90.0))["status"],
            LAND_USE_LOW_EVIDENCE,
        )
        self.assertEqual(
            assess_land_use(_synthetic_mock_profile(cf_val=0.01, cf_share=0.0, sg_cov=4.0, s2_ndvi=0.18, modis_spring=0.20))["status"],
            LAND_USE_UNVERIFIED,
        )
        # Near-zero crop frequency + high NDVI or farmer history -> CONFLICTING
        self.assertEqual(
            assess_land_use(_synthetic_mock_profile(cf_val=0.01, cf_share=0.0, sg_cov=80.0, s2_ndvi=0.62))["status"],
            LAND_USE_CONFLICTING_EVIDENCE,
        )
        # High crop frequency + severely SoilGrids masked interior (<25%) -> CONFLICTING
        self.assertEqual(
            assess_land_use(_synthetic_mock_profile(cf_val=0.75, cf_share=78.0, sg_cov=8.0, sg_status="MODELED_SOILGRIDS"))["status"],
            LAND_USE_CONFLICTING_EVIDENCE,
        )
        self.assertEqual(
            assess_land_use(_synthetic_mock_profile(cf_val=None, cf_status="UNAVAILABLE_NOT_INTEGRATED"))["status"],
            LAND_USE_DATA_UNAVAILABLE,
        )

    def test_03_temporal_current_planning_vs_historical_simulation(self) -> None:
        ref = date(2026, 11, 15)
        for bad_season, bad_yr in (("Autumn", 2025), ("Winter", 2026), ("Spring", 2026), ("Summer", 2026)):
            with self.assertRaises(FarmerInputValidationError) as ctx:
                validate_farmer_input(
                    _payload(
                        field_id="T_PAST",
                        geometry=POLY_BELKHEIR_CROPLAND,
                        planning={"start_season": bad_season, "start_year": bad_yr, "horizon_seasons": 3},
                    ),
                    reference_date=ref,
                )
            self.assertEqual(ctx.exception.error_code, "PAST_PLANNING_SEASON")
            self.assertEqual(ctx.exception.details["recommended_start_season"], "Autumn")
            self.assertEqual(ctx.exception.details["recommended_start_year"], 2026)

        # Past planting_month in active Autumn 2026
        with self.assertRaises(TemporalPlanningError) as mctx:
            validate_and_build_planning_timeline(
                {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3, "planting_month": 10},
                reference_date=ref,
            )
        self.assertEqual(mctx.exception.error_code, "PAST_PLANTING_MONTH")

        # Chronologically impossible crop history after planning start
        with self.assertRaises(TemporalPlanningError) as hctx:
            validate_and_build_planning_timeline(
                {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                crop_history=[{"season": "Winter", "year": 2027, "crop_name_raw": "Wheat"}],
                reference_date=ref,
            )
        self.assertEqual(hctx.exception.error_code, "CROP_HISTORY_AFTER_PLANNING_START")

        # Valid CURRENT_PLANNING windows & chronological slot advancement
        t_aut = validate_and_build_planning_timeline(
            {"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3, "planting_month": 11},
            reference_date=ref,
        )
        self.assertEqual(t_aut["planning_mode"], PLANNING_MODE_CURRENT)
        self.assertEqual(t_aut["temporal_status"], "VALID_CURRENT_WINDOW")
        self.assertEqual([(s["season"], s["year"]) for s in t_aut["slots"]], [("Autumn", 2026), ("Autumn", 2027), ("Autumn", 2028)])

        t_win = validate_and_build_planning_timeline(
            {"start_season": "Winter", "start_year": 2027, "horizon_seasons": 3},
            reference_date=ref,
        )
        self.assertEqual(t_win["temporal_status"], "VALID_FUTURE_WINDOW")
        self.assertEqual([(s["season"], s["year"]) for s in t_win["slots"]], [("Winter", 2027), ("Autumn", 2027), ("Autumn", 2028)])

        # Explicit HISTORICAL_SIMULATION permitted + flagged
        fp_hist = build_field_profile(
            _payload(
                field_id="T_HIST",
                geometry=POLY_BELKHEIR_CROPLAND,
                planning={"start_season": "Autumn", "start_year": 2025, "horizon_seasons": 3, "planning_mode": PLANNING_MODE_HISTORICAL},
            ),
            reference_date=ref,
        )
        tv = fp_hist["section_a_farmer_provided"]["planning"]["temporal_validation"]
        self.assertEqual(tv["temporal_status"], "HISTORICAL_SIMULATION_PAST_HORIZON")
        self.assertTrue(tv["is_historical_simulation"])

    def test_04_agronomic_seq04_seq06_and_scoring_bugfixes(self) -> None:
        fp = build_field_profile(
            _payload(
                field_id="SEQ_AUDIT",
                geometry=POLY_BELKHEIR_CROPLAND,
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                preferences={"equipment_constraints": ["no_precision_planter"], "water_saving_weight": 0.2, "soil_improvement_weight": 0.3, "risk_reduction_weight": 0.5},
            ),
            clock=self.ref_clock,
        )
        # SEQ_04: Cross-pulse 2yr -> WARNING (feasible with caution); same-pulse 2yr -> FAIL
        ev_cross = evaluate_crop_sequence(fp, ["FABA_BEAN", "DURUM_WHEAT", "CHICKPEA_WINTER"], kb=self.kb)
        r04_cross = [r for r in ev_cross["sequence_rule_evaluations"] if r["rule_id"] == "SEQ_04_PULSE_BROOMRAPE_BREAK"][0]
        self.assertEqual(r04_cross["status"], "WARNING")
        self.assertEqual(r04_cross["observed_inputs"]["rule_tier"], "SOFT_WARNING_CROSS_PULSE_2YR")
        self.assertTrue(r04_cross["observed_inputs"]["kb_provenance_verified"])

        ev_same = evaluate_crop_sequence(fp, ["FABA_BEAN", "DURUM_WHEAT", "FABA_BEAN"], kb=self.kb)
        r04_same = [r for r in ev_same["sequence_rule_evaluations"] if r["rule_id"] == "SEQ_04_PULSE_BROOMRAPE_BREAK"][0]
        self.assertEqual(r04_same["status"], "FAIL")

        # SEQ_06: Single Vetch-Oat PASS vs 2yr repeat WARNING vs consecutive WARNING
        ev_vo1 = evaluate_crop_sequence(fp, ["VETCH_OAT", "DURUM_WHEAT", "FABA_BEAN"], kb=self.kb)
        r06_1 = [r for r in ev_vo1["sequence_rule_evaluations"] if r["rule_id"] == "SEQ_06_VETCH_OAT_ROLE_AND_REPEAT"][0]
        self.assertEqual(r06_1["status"], "PASS")
        self.assertEqual(r06_1["observed_inputs"]["repeat_mode"], "SINGLE_BREAK")

        ev_vo2 = evaluate_crop_sequence(fp, ["VETCH_OAT", "DURUM_WHEAT", "VETCH_OAT"], kb=self.kb)
        r06_2 = [r for r in ev_vo2["sequence_rule_evaluations"] if r["rule_id"] == "SEQ_06_VETCH_OAT_ROLE_AND_REPEAT"][0]
        self.assertEqual(r06_2["status"], "WARNING")
        self.assertEqual(r06_2["observed_inputs"]["repeat_mode"], "FREQUENT_2YR_CYCLE")

        ev_vo_consec = evaluate_crop_sequence(fp, ["VETCH_OAT", "VETCH_OAT", "DURUM_WHEAT"], kb=self.kb)
        r06_consec = [r for r in ev_vo_consec["sequence_rule_evaluations"] if r["rule_id"] == "SEQ_06_VETCH_OAT_ROLE_AND_REPEAT"][0]
        self.assertEqual(r06_consec["status"], "WARNING")
        self.assertEqual(r06_consec["observed_inputs"]["repeat_mode"], "CONSECUTIVE_1YR")

        # Verify SEQ_07 transitions fix & RULE_EQUIPMENT_CONSTRAINT_CHECK fix are active in scoring
        cand = generate_rotation_candidates(fp, kb=self.kb, clock=self.ref_clock)
        ranked = rank_rotation_candidates(cand, field_profile=fp, kb=self.kb)
        soil_strat = [s for s in ranked["strategies"] if s["strategy_id"] == "STRAT_SOIL_IMPROVEMENT"][0]
        self.assertGreater(soil_strat["scores"]["nitrogen_contribution"]["score"], 0.60)
        self.assertIn(
            "Beneficial legume/forage -> cereal transitions: 1.",
            soil_strat["scores"]["nitrogen_contribution"]["evidence"],
        )
        forage_strat = [s for s in ranked["strategies"] if s["strategy_id"] == "STRAT_CEREAL_FORAGE"][0]
        self.assertGreater(forage_strat["scores"]["nitrogen_contribution"]["score"], 0.31)
        self.assertTrue(
            any("hay" in m.lower() for m in forage_strat["scores"]["nitrogen_contribution"]["missing_information"])
        )
        self.assertEqual(forage_strat["scores"]["farmer_priority_fit"]["status"], "SCORED")

        # Verify equipment_constraints=['no_precision_planter'] vs [] measurably lowers farmer_priority_fit on Sunflower
        fp_irrig_eq = build_field_profile(
            _payload(
                field_id="EQ_CHECK",
                geometry=POLY_BELKHEIR_CROPLAND,
                water={"availability": "abundant", "source": "reservoir", "irrigation_system": "drip"},
                planning={"start_season": "Spring", "start_year": 2027, "horizon_seasons": 2},
                preferences={"target_crop_ids": ["SUNFLOWER"], "equipment_constraints": ["no_precision_planter"]},
            ),
            clock=self.ref_clock,
        )
        fp_irrig_clear = copy.deepcopy(fp_irrig_eq)
        fp_irrig_clear["section_a_farmer_provided"]["preferences"]["equipment_constraints"] = []
        fp_irrig_clear["section_d_quality_and_uncertainty"]["input_completeness_flags"]["equipment_constraints"] = "EXPLICITLY_CONFIRMED_EMPTY"
        r_eq = rank_rotation_candidates(generate_rotation_candidates(fp_irrig_eq, kb=self.kb, clock=self.ref_clock), field_profile=fp_irrig_eq, kb=self.kb)
        r_clr = rank_rotation_candidates(generate_rotation_candidates(fp_irrig_clear, kb=self.kb, clock=self.ref_clock), field_profile=fp_irrig_clear, kb=self.kb)
        sun_eq = [s for s in r_eq["strategies"] if s["feasible"] and any(sl["crop_id"] == "SUNFLOWER" for sl in s["seasons"])]
        sun_clr = [s for s in r_clr["strategies"] if s["feasible"] and any(sl["crop_id"] == "SUNFLOWER" for sl in s["seasons"])]
        if sun_eq and sun_clr:
            self.assertLess(sun_eq[0]["scores"]["farmer_priority_fit"]["score"], sun_clr[0]["scores"]["farmer_priority_fit"]["score"])

    def test_05_near_tie_margins_stability_metrics_and_sensitivity_limitations(self) -> None:
        self.assertEqual(classify_margin_status(0.900, 0.897, MarginThresholds())[2], "NEAR_TIE")
        self.assertEqual(classify_margin_status(0.900, 0.875, MarginThresholds())[2], "NARROW_MARGIN")
        self.assertEqual(classify_margin_status(0.900, 0.800, MarginThresholds())[2], "CLEAR_MARGIN")

        def _fake_strat(sid: str, w: float, s: float, n: float, p: float, e: float, f: float) -> dict:
            return {
                "strategy_id": sid,
                "constraint_evaluations": {"overall_status_counts": {"PASS": 35}},
                "scores": {
                    "water_efficiency": {"score": w},
                    "soil_improvement": {"score": s},
                    "nitrogen_contribution": {"score": n},
                    "pest_disease_disruption": {"score": p},
                    "erosion_protection": {"score": e},
                    "farmer_priority_fit": {"score": f},
                },
            }

        strats = [
            _fake_strat("S_A", 0.85, 0.90, 0.72, 0.90, 0.85, 0.82),
            _fake_strat("S_B", 0.96, 0.83, 0.62, 0.88, 0.84, 0.82),
        ]
        objs = ["water_efficiency", "soil_improvement", "nitrogen_contribution", "pest_disease_disruption", "erosion_protection", "farmer_priority_fit"]
        weights = {o: round(1.0 / len(objs), 6) for o in objs}
        sens = run_sensitivity_analysis(
            strats,
            weights,
            objs,
            ["S_A", "S_B"],
            "S_A",
            power_water_scores={"S_A": 0.86, "S_B": 0.97},
            precip_spread_mm=160.0,
        )
        self.assertIn(sens["margin_status"], ("NEAR_TIE", "NARROW_MARGIN"))
        self.assertTrue(sens["near_tie_detected"])
        self.assertTrue(len(sens["plausible_alternatives"]) >= 1)
        self.assertIn("S_A", sens["per_strategy_stability"])
        for metric in ("winner_frequency", "top_1_retention", "top_2_frequency", "rank_change_counts"):
            self.assertIn(metric, sens["per_strategy_stability"]["S_A"])
        self.assertIn("conservative_dry_top_strategy_id", sens["climate_sensitivity"])
        self.assertIn("disagreement_stress_top_strategy_id", sens["climate_sensitivity"])
        self.assertIn("empirical yield confidence", sens["non_confidence_note"])

    def test_06_water_balance_fao56_non_fabrication_and_quantitative_mode(self) -> None:
        mock_fp = _synthetic_mock_profile(cf_val=0.80, cf_share=82.0)
        wb_missing = assess_water_balance_readiness(mock_fp, crop_profiles=self.kb.crops)
        self.assertEqual(wb_missing["current_scoring_method"], "ORDINAL_REGIME_SUITABILITY")
        self.assertIn(wb_missing["fao56_water_balance_status"], ("UNKNOWN", "PARTIAL"))
        self.assertIsNone(wb_missing["reference_et0_mm_day"])
        self.assertIsNone(wb_missing["effective_precipitation_mm"])
        self.assertTrue(any("WS2M" in item for item in wb_missing["missing_inputs"]))

        # When verified complete wind, DEM, monthly precip, and soil FC/PWP ARE supplied -> exact computation
        et0 = compute_fao56_penman_monteith_et0_daily(
            tmin_c=10.5,
            tmax_c=24.5,
            rh_mean_pct=64.0,
            rs_mj_m2_day=18.0,
            u2_ms=2.2,
            elevation_m=220.0,
            latitude_deg=36.46,
            day_of_year=105,
        )
        peff = compute_effective_precip_usda_scs_monthly(65.0)
        self.assertGreater(et0, 2.0)
        self.assertLess(et0, 7.0)
        self.assertGreater(peff, 40.0)
        self.assertLess(peff, 65.0)

        wb_local = assess_water_balance_readiness(
            mock_fp,
            crop_profiles=self.kb.crops,
            local_hydrology_inputs={
                "wind_speed_2m_ms": 2.2,
                "elevation_m": 220.0,
                "monthly_precipitation_series_mm": [65.0, 55.0],
                "soil_fc_vol_pct": 34.0,
                "soil_pwp_vol_pct": 18.0,
                "application_efficiency_ea": 0.85,
            },
        )
        self.assertGreater(wb_local["reference_et0_mm_day"], 0.0)
        self.assertGreater(wb_local["effective_precipitation_mm"], 0.0)
        self.assertEqual(wb_local["soil_water_storage_status"], "PROVIDED_LOCAL_FC_PWP")

    def test_07_api_temporal_422_and_decision_gate_validator_invariants(self) -> None:
        app = create_app(repository=SQLiteAnalysisRepository(":memory:"))
        client = TestClient(app)

        # Past planning year under default CURRENT_PLANNING rejected via structured HTTP 422
        r_past = client.post(
            "/api/v1/fields/analyze",
            json=_payload(
                field_id="API_PAST",
                geometry=POLY_BELKHEIR_CROPLAND,
                planning={"start_season": "Autumn", "start_year": 2025, "horizon_seasons": 3},
            ),
        )
        self.assertEqual(r_past.status_code, 422)
        body = r_past.json()
        self.assertEqual(body["error_code"], "PAST_PLANNING_SEASON")
        self.assertTrue(body["details"])

        # Same request in explicit HISTORICAL_SIMULATION executes cleanly
        r_hist = client.post(
            "/api/v1/fields/analyze",
            json=_payload(
                field_id="API_HIST",
                geometry=POLY_BELKHEIR_CROPLAND,
                planning={
                    "start_season": "Autumn",
                    "start_year": 2025,
                    "horizon_seasons": 3,
                    "planning_mode": "HISTORICAL_SIMULATION",
                },
            ),
        )
        self.assertEqual(r_hist.status_code, 200, r_hist.text)
        rec = r_hist.json()["recommendation"]
        fplan = rec["field_plans"][0]
        self.assertEqual(fplan["decision_gate"]["decision_status"], "REQUIRES_LOCAL_VERIFICATION")
        self.assertEqual(fplan["data_quality"]["critical_data_adequacy"]["adequacy_status"], "PARTIAL")

        # Validator invariant rejects EXPLORATORY_ONLY with endorsed_recommendation_id set
        tampered = copy.deepcopy(rec)
        tampered["field_plans"][0]["decision_gate"]["decision_status"] = "EXPLORATORY_ONLY"
        tampered["field_plans"][0]["decision_gate"]["endorsed_recommendation_id"] = "STRAT_SOIL_IMPROVEMENT"
        val_bad = validate_final_recommendation(tampered, raise_on_error=False)
        self.assertFalse(val_bad["valid"])
        self.assertTrue(any("EXPLORATORY_ONLY" in e for e in val_bad["errors"]))
        with self.assertRaises(OutputValidationError):
            validate_final_recommendation(tampered)

        # Verify ANAL_248892 peri-urban polygon via HTTP 200 API returns EXPLORATORY_ONLY + INSUFFICIENT adequacy
        r_pu = client.post(
            "/api/v1/fields/analyze",
            json=_payload(
                field_id="API_ANAL_248892",
                geometry=POLY_ANAL_248892_PERIURBAN,
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3},
                crop_history=[{"season": "Autumn", "year": 2024, "crop_name_raw": "Durum Wheat"}],
            ),
        )
        self.assertEqual(r_pu.status_code, 200, r_pu.text)
        fplan_pu = r_pu.json()["recommendation"]["field_plans"][0]
        self.assertEqual(fplan_pu["decision_gate"]["decision_status"], "EXPLORATORY_ONLY")
        self.assertIsNone(fplan_pu["decision_gate"]["endorsed_recommendation_id"])
        self.assertEqual(fplan_pu["data_quality"]["critical_data_adequacy"]["adequacy_status"], "INSUFFICIENT")

        # Verify INFEASIBLE decision gate when zero candidates pass feasibility
        fp_b = build_field_profile(
            _payload(
                field_id="GATE_INF",
                geometry=POLY_BELKHEIR_CROPLAND,
                planning={"start_season": "Autumn", "start_year": 2026, "horizon_seasons": 2},
            ),
            clock=self.ref_clock,
        )
        cand_b = generate_rotation_candidates(fp_b, kb=self.kb, clock=self.ref_clock)
        cand_inf = copy.deepcopy(cand_b)
        for st in cand_inf["strategies"]:
            st["feasible"] = False
            st["feasibility_status"] = "INFEASIBLE_HARD_CONSTRAINT"
        rank_inf = rank_rotation_candidates(cand_inf, field_profile=fp_b, kb=self.kb)
        self.assertEqual(rank_inf["decision_gate"]["decision_status"], "INFEASIBLE")
        self.assertIsNone(rank_inf["decision_gate"]["endorsed_recommendation_id"])
        out_inf = build_final_recommendation(fp_b, cand_inf, rank_inf, kb=self.kb)
        self.assertTrue(validate_final_recommendation(out_inf)["valid"])
        self.assertEqual(out_inf["field_plans"][0]["decision_gate"]["decision_status"], "INFEASIBLE")

        if app.state.repository._conn_memory is not None:
            app.state.repository._conn_memory.close()


if __name__ == "__main__":
    unittest.main()
