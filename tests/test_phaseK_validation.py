"""Phase K — Scientific Validation, Causal Backtesting & Reliability Test Suite.

Non-destructive validation tests verifying:
1. Phase K validation documentation deliverables & honest verdict constraints.
2. Spatial agro-ecological contrast (humid Seybouse vs semi-arid southern Tamlouka).
3. Temporal non-leakage & 2022 drought climate divergence (`PRECIP_SENSITIVE_RANK_SHIFT`).
4. Graceful stress degradation (null SoilGrids, dropped Sentinel-2, unknown water, missing DEM/ECe).
5. Weight sensitivity & inactive-objective boundaries (`forage_value`, `income_potential`).
"""

from __future__ import annotations

import copy
import csv
import unittest
from pathlib import Path
from typing import Any, Dict

from field_profile_builder import build_field_profile
from src.optimization import rank_rotation_candidates
from src.output import build_final_recommendation, validate_final_recommendation
from src.rotation import generate_rotation_candidates

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASEK_DOCS = REPO_ROOT / "docs" / "phaseK"

# Representative Guelma test polygons verified inside Wilaya boundaries
POLY_BOUCHECOUF_CLAY = {
    "type": "Polygon",
    "coordinates": [[[7.725, 36.462], [7.732, 36.462], [7.732, 36.467], [7.725, 36.467], [7.725, 36.462]]],
}
POLY_BELKHEIR_PLAIN = {
    "type": "Polygon",
    "coordinates": [[[7.435, 36.443], [7.441, 36.443], [7.441, 36.447], [7.435, 36.447], [7.435, 36.443]]],
}
POLY_TAMLOUKA_SEMIARID = {
    "type": "Polygon",
    "coordinates": [[[7.137, 36.128], [7.143, 36.128], [7.143, 36.132], [7.137, 36.132], [7.137, 36.128]]],
}


def _make_request(
    field_id: str,
    polygon: Dict[str, Any],
    water: Dict[str, Any],
    crop_history: list | None = None,
    preferences: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    req: Dict[str, Any] = {
        "field": {"field_id": field_id, "geometry": polygon},
        "water": water,
        "crop_history": (
            crop_history
            if crop_history is not None
            else [
                {
                    "season": "Autumn",
                    "year": 2024,
                    "planting_month": 11,
                    "crop_name_raw": "Durum Wheat",
                }
            ]
        ),
        "planning": {"start_season": "Autumn", "start_year": 2025, "horizon_seasons": 3},
    }
    if preferences is not None:
        req["preferences"] = preferences
    return req


def _run_e2e_from_profile(fp: Dict[str, Any]) -> Dict[str, Any]:
    h_out = generate_rotation_candidates(fp)
    i_out = rank_rotation_candidates(h_out, field_profile=fp)
    j_out = build_final_recommendation(fp, h_out, i_out)
    val = validate_final_recommendation(j_out)
    return {"fp": fp, "h": h_out, "i": i_out, "j": j_out, "val": val}


class TestPhaseKScientificValidation(unittest.TestCase):
    """Independent validation, backtesting, stress-testing, and scorecard checks."""

    def test_phaseK_deliverables_and_honest_verdicts_exist(self) -> None:
        required_files = [
            "validation_scenarios.csv",
            "validation_scorecard.csv",
            "known_model_risks.md",
            "historical_backtesting_report.md",
            "sensitivity_validation_report.md",
            "scientific_validation_report.md",
        ]
        for fname in required_files:
            fpath = PHASEK_DOCS / fname
            self.assertTrue(fpath.is_file(), f"Missing Phase K deliverable: {fpath}")
            self.assertGreater(fpath.stat().st_size, 200, f"Phase K deliverable unexpectedly small: {fpath}")

        with (PHASEK_DOCS / "validation_scenarios.csv").open(encoding="utf-8") as f:
            scenario_rows = list(csv.DictReader(f))
        self.assertEqual(len(scenario_rows), 17)
        self.assertTrue(all(r["schema_valid"] == "True" for r in scenario_rows))
        self.assertTrue(any(r["climate_agreement"] == "PRECIP_SENSITIVE_RANK_SHIFT" for r in scenario_rows))

        with (PHASEK_DOCS / "validation_scorecard.csv").open(encoding="utf-8") as f:
            scorecard_rows = {r["component"]: r for r in csv.DictReader(f)}
        self.assertEqual(scorecard_rows["Empirical supervised yield & plot validation"]["verdict"], "NOT_VALIDATABLE")
        self.assertEqual(scorecard_rows["Overall system readiness"]["verdict"], "CONDITIONAL")
        self.assertIn("BLOCKED", scorecard_rows["Overall system readiness"]["real_world_field_validation_status"])

    def test_spatial_agroecological_differentiation_north_vs_south(self) -> None:
        # Compare humid northern Bouchekouf vs semi-arid southern Tamlouka under default & soil-conservation weights
        bou_req = _make_request(
            "K_TEST_BOUCHEKOUF_IRRIG",
            POLY_BOUCHECOUF_CLAY,
            {"availability": "moderate", "source": "reservoir", "irrigation_system": "drip"},
        )
        tam_req = _make_request(
            "K_TEST_TAMLOUKA_RAINFED",
            POLY_TAMLOUKA_SEMIARID,
            {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
        )

        bou_res = _run_e2e_from_profile(build_field_profile(bou_req))
        tam_res = _run_e2e_from_profile(build_field_profile(tam_req))

        self.assertTrue(bou_res["val"]["valid"], bou_res["val"]["errors"])
        self.assertTrue(tam_res["val"]["valid"], tam_res["val"]["errors"])

        bou_plan = bou_res["j"]["field_plans"][0]
        tam_plan = tam_res["j"]["field_plans"][0]
        self.assertNotEqual(bou_plan["suggested_strategy_id"], "STRAT_WATER_CONSCIOUS")
        self.assertEqual(tam_plan["suggested_strategy_id"], "STRAT_WATER_CONSCIOUS")
        self.assertEqual(
            bou_plan["recommendation_status"],
            "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION",
        )
        self.assertEqual(
            tam_plan["recommendation_status"],
            "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION",
        )

    def test_causal_backtest_non_leakage_and_2022_drought_rank_shift(self) -> None:
        base_fp = build_field_profile(
            _make_request(
                "K_BACKTEST_BOU_2022",
                POLY_BOUCHECOUF_CLAY,
                {"availability": "moderate", "source": "reservoir", "irrigation_system": "drip"},
            )
        )

        # Antecedent humid baseline (2017-2021 climatology, future rasters masked) -> ROBUST_GPM_AND_POWER
        pre22_fp = copy.deepcopy(base_fp)
        pre_ds = pre22_fp["section_b_extracted_geospatial"]["extracted_datasets"]
        pre_ds["crop_frequency"]["crop_frequency_2021_2025"]["value"] = None
        pre_ds["crop_frequency"]["crop_frequency_2021_2025"]["quality_status"] = "TEMPORAL_GUARD_EXCLUDED"
        for k in ("s2_2024_03_ndvi_10m", "s2_2024_03_evi_10m", "s2_2024_03_ndmi_20m", "s2_2024_03_ndre_20m"):
            if k in pre_ds["sentinel2"]:
                pre_ds["sentinel2"][k]["value"] = None
                pre_ds["sentinel2"][k]["quality_status"] = "TEMPORAL_GUARD_EXCLUDED"
        pre_ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["value"] = 616.72
        pre_ds["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"]["value"] = 810.15
        res_pre_22 = _run_e2e_from_profile(pre22_fp)
        self.assertTrue(res_pre_22["val"]["valid"], res_pre_22["val"]["errors"])
        pre_winner = res_pre_22["j"]["field_plans"][0]["suggested_strategy_id"]
        self.assertNotEqual(pre_winner, "STRAT_WATER_CONSCIOUS")
        self.assertEqual(
            res_pre_22["i"]["sensitivity_analysis"]["climate_sensitivity"]["climate_dataset_agreement"],
            "ROBUST_GPM_AND_POWER",
        )

        # 2022 drought realization -> GPM (444.04) flips winner to STRAT_WATER_CONSCIOUS while POWER stays humid
        dry22_fp = copy.deepcopy(pre22_fp)
        dry_ds = dry22_fp["section_b_extracted_geospatial"]["extracted_datasets"]
        dry_ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["value"] = 444.04
        dry_ds["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"]["value"] = 608.94

        res_bou_22 = _run_e2e_from_profile(dry22_fp)
        self.assertTrue(res_bou_22["val"]["valid"], res_bou_22["val"]["errors"])
        self.assertEqual(res_bou_22["j"]["field_plans"][0]["suggested_strategy_id"], "STRAT_WATER_CONSCIOUS")
        clim_sens = res_bou_22["i"]["sensitivity_analysis"]["climate_sensitivity"]
        self.assertEqual(clim_sens["climate_dataset_agreement"], "PRECIP_SENSITIVE_RANK_SHIFT")

        # Contrast with southern Tamlouka 2022 severe drought: both GPM & POWER agree on STRAT_WATER_CONSCIOUS
        tam_22_fp = copy.deepcopy(
            build_field_profile(
                _make_request(
                    "K_BACKTEST_TAM_2022",
                    POLY_TAMLOUKA_SEMIARID,
                    {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
                )
            )
        )
        tam_ds = tam_22_fp["section_b_extracted_geospatial"]["extracted_datasets"]
        tam_ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["value"] = 311.58
        tam_ds["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"]["value"] = 426.29

        res_tam_22 = _run_e2e_from_profile(tam_22_fp)
        self.assertTrue(res_tam_22["val"]["valid"], res_tam_22["val"]["errors"])
        self.assertEqual(res_tam_22["j"]["field_plans"][0]["suggested_strategy_id"], "STRAT_WATER_CONSCIOUS")
        self.assertEqual(
            res_tam_22["i"]["sensitivity_analysis"]["climate_sensitivity"]["climate_dataset_agreement"],
            "ROBUST_GPM_AND_POWER",
        )

    def test_degraded_inputs_soilgrids_s2_and_unknown_water_fail_safe(self) -> None:
        base_fp = build_field_profile(
            _make_request(
                "K_STRESS_BASE",
                POLY_BELKHEIR_PLAIN,
                {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
            )
        )

        # 1. Partial/masked SoilGrids (clay=None, soc=None) -> soil_improvement PARTIAL, zero schema errors
        soil_null_fp = copy.deepcopy(base_fp)
        soil = soil_null_fp["section_b_extracted_geospatial"]["extracted_datasets"]["soilgrids_v6"]
        soil["clay_0_30cm"]["value"] = None
        soil["clay_0_30cm"]["quality_status"] = "UNAVAILABLE_MASKED"
        soil["soc_0_30cm"]["value"] = None
        soil["soc_0_30cm"]["quality_status"] = "UNAVAILABLE_MASKED"
        res_soil = _run_e2e_from_profile(soil_null_fp)
        self.assertTrue(res_soil["val"]["valid"], res_soil["val"]["errors"])
        top_strat = next(
            s for s in res_soil["i"]["strategies"] if s["strategy_id"] == res_soil["i"]["suggested_strategy_id"]
        )
        self.assertEqual(top_strat["scores"]["soil_improvement"]["status"], "PARTIAL")

        # 2. Dropped Sentinel-2 snapshot -> schema valid, zero crashes
        s2_null_fp = copy.deepcopy(base_fp)
        s2_null_fp["section_b_extracted_geospatial"]["extracted_datasets"]["sentinel2"]["s2_2024_03_ndvi_10m"][
            "value"
        ] = None
        res_s2 = _run_e2e_from_profile(s2_null_fp)
        self.assertTrue(res_s2["val"]["valid"], res_s2["val"]["errors"])

        # 3. Unknown water + salinity requested TOMATO_IND -> strictly gated (never clean pass)
        unk_water_fp = build_field_profile(
            _make_request(
                "K_STRESS_UNKNOWN_WATER",
                POLY_BELKHEIR_PLAIN,
                {"availability": "unknown", "source": "other", "irrigation_system": "unknown"},
                preferences={"target_crop_ids": ["TOMATO_IND"]},
            )
        )
        res_unk = _run_e2e_from_profile(unk_water_fp)
        self.assertTrue(res_unk["val"]["valid"], res_unk["val"]["errors"])
        tomato_status = next(
            r for r in res_unk["j"]["field_plans"][0]["requested_crop_results"] if r["crop_id"] == "TOMATO_IND"
        )
        self.assertEqual(tomato_status["outcome"], "unavailable_due_to_insufficient_evidence")
        self.assertIn("UNVERIFIED_HARD_UNKNOWN", tomato_status["feasibility_statuses"])

    def test_forage_activation_and_unfabricated_income_boundary(self) -> None:
        high_forage_fp = build_field_profile(
            _make_request(
                "K_TEST_HIGH_FORAGE",
                POLY_BELKHEIR_PLAIN,
                {"availability": "limited", "source": "rainfed", "irrigation_system": "none"},
                preferences={
                    "water_saving_weight": 0.10,
                    "soil_improvement_weight": 0.15,
                    "income_weight": 0.05,
                    "risk_reduction_weight": 0.10,
                    "forage_value_weight": 0.60,
                },
            )
        )
        res_forage = _run_e2e_from_profile(high_forage_fp)
        self.assertTrue(res_forage["val"]["valid"], res_forage["val"]["errors"])
        self.assertEqual(res_forage["j"]["field_plans"][0]["suggested_strategy_id"], "STRAT_CEREAL_FORAGE")
        self.assertIn("forage_value", res_forage["i"]["ranking_methodology"]["active_weighted_objectives"])
        top_s = next(
            s for s in res_forage["i"]["strategies"] if s["strategy_id"] == res_forage["i"]["suggested_strategy_id"]
        )
        self.assertEqual(top_s["scores"]["income_potential"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
