"""Phase G Automated Verification Suite: Agronomic Knowledge Base & Constraint Engine.

Tests all 11 Phase G verification targets:
1. All 13 crop profiles & full parameter provenance structure
2. Honest preservation of missing agronomic parameters (value=None, UNKNOWN)
3. Strict evidence classifications (HARD_CONSTRAINT, SOFT_CONSTRAINT, EXPERT_ASSUMPTION, UNKNOWN)
4. Hard & soft constraint evaluation & feasibility separation
5. Unknown constraints never auto-converted into PASS
6. Repeated cereal sequences, Solanaceae, pulse & bare-fallow hard/soft violations
7. Legume break & Vetch-Oat fallow-replacement compatibility
8. Perennial crop (Olive) exclusion from annual rotation scope
9. Optional farmer inputs (null/NOT_PROVIDED vs []/EXPLICITLY_CONFIRMED_EMPTY vs PROVIDED)
10. Missing Field Profile datasets & SoilGrids SOC-NaN handling
11. Strict determinism & non-modification of quarantined nitrogen_0_30cm
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import pyproj
from shapely.geometry import box

import field_geospatial_processor as fgp
from field_profile_builder import build_field_profile
from src.agronomic.constraint_engine import (
    EVIDENCE_CLASSES,
    EVALUATION_STATUSES,
    evaluate_all_crops_for_field,
    evaluate_crop_for_field,
    evaluate_crop_sequence,
    load_knowledge_base,
)


def _boumahra_payload(
    availability: str = "moderate",
    source: str = "reservoir",
    irrigation_system: str = "drip",
    crop_history=None,
    preferences=None,
) -> dict:
    payload = {
        "field": {
            "field_id": "G_TEST_BM",
            "field_name": "Boumahra Test Plot",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [7.5075, 36.4691],
                    [7.5095, 36.4691],
                    [7.5095, 36.4711],
                    [7.5075, 36.4711],
                    [7.5075, 36.4691],
                ]],
            },
        },
        "water": {
            "availability": availability,
            "source": source,
            "irrigation_system": irrigation_system,
        },
        "planning": {
            "start_season": "Winter",
            "start_year": 2025,
            "horizon_seasons": 3,
        },
    }
    if crop_history is not None:
        payload["crop_history"] = crop_history
    if preferences is not None:
        payload["preferences"] = preferences
    return payload


def _tamlouka_rainfed_payload() -> dict:
    return {
        "field": {
            "field_id": "G_TEST_TAM",
            "field_name": "Tamlouka Semi-Arid Plot",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [7.1390, 36.1350],
                    [7.1423, 36.1350],
                    [7.1423, 36.1377],
                    [7.1390, 36.1377],
                    [7.1390, 36.1350],
                ]],
            },
        },
        "water": {
            "availability": "limited",
            "source": "rainfed",
            "irrigation_system": "none",
        },
        "crop_history": [
            {"season": "Winter", "year": 2024, "crop_name_raw": "Barley"},
        ],
        "planning": {
            "start_season": "Winter",
            "start_year": 2025,
            "horizon_seasons": 3,
        },
        "preferences": {
            "equipment_constraints": [],
            "forage_value_weight": 0.5,
        },
    }


def _rules_by_id(eval_res: dict) -> dict:
    if "rule_evaluations" in eval_res:
        return {r["rule_id"]: r for r in eval_res["rule_evaluations"]}
    return {r["rule_id"]: r for r in eval_res["sequence_rule_evaluations"]}


class TestPhaseGKnowledgeAndConstraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.kb = load_knowledge_base()
        cls.prof_irrig = build_field_profile(_boumahra_payload(
            crop_history=[{"season": "Winter", "year": 2024, "crop_name_raw": "Blé dur"}],
            preferences={"equipment_constraints": [], "forage_value_weight": 0.0},
        ))
        cls.prof_rainfed = build_field_profile(_boumahra_payload(
            availability="limited", source="rainfed", irrigation_system="none",
            crop_history=[{"season": "Winter", "year": 2024, "crop_name_raw": "Blé dur"}],
            preferences={"equipment_constraints": [], "forage_value_weight": 0.5},
        ))
        cls.prof_tamlouka = build_field_profile(_tamlouka_rainfed_payload())

    def test_01_all_13_crop_profiles_and_parameter_traceability(self):
        expected_crops = {
            "DURUM_WHEAT", "SOFT_WHEAT", "BARLEY", "FABA_BEAN",
            "CHICKPEA_WINTER", "CHICKPEA_SPRING", "LENTIL", "VETCH_OAT",
            "TOMATO_IND", "POTATO", "SUNFLOWER", "OLIVE", "BARE_FALLOW",
        }
        self.assertEqual(set(self.kb.crops.keys()), expected_crops)
        req_meta = {"value", "unit", "source", "evidence_classification", "confidence", "geographic_applicability"}
        for cid, crop in self.kb.crops.items():
            self.assertGreaterEqual(len(crop["parameters"]), 15, f"{cid} parameter count too low")
            for pname, pdict in crop["parameters"].items():
                self.assertEqual(set(pdict.keys()), req_meta, f"Bad metadata keys on {cid}.{pname}")
                self.assertIn(pdict["evidence_classification"], EVIDENCE_CLASSES)
                self.assertTrue(str(pdict["source"]).strip(), f"Empty source on {cid}.{pname}")

        dd = pd.read_csv("agronomic_knowledge/knowledge_data_dictionary.csv")
        self.assertGreaterEqual(len(dd), 20)

    def test_02_missing_agronomic_parameters_never_fabricated(self):
        # Exact quantitative N-P-K fertilizer curves are uncalibrated locally -> null & UNKNOWN
        for cid in ("DURUM_WHEAT", "FABA_BEAN", "CHICKPEA_WINTER", "TOMATO_IND", "POTATO", "SUNFLOWER"):
            npk = self.kb.crops[cid]["parameters"]["nutrient_requirements_quantitative"]
            self.assertIsNone(npk["value"])
            self.assertEqual(npk["evidence_classification"], "UNKNOWN")
            self.assertEqual(npk["confidence"], "UNMEASURED_UNKNOWN")

        # Chickpea / Lentil / Vetch-Oat quantitative kg N/ha fixation is null/UNKNOWN (only Faba bean has Phase E cited range 100-200)
        for cid in ("CHICKPEA_WINTER", "CHICKPEA_SPRING", "LENTIL", "VETCH_OAT"):
            nfix = self.kb.crops[cid]["parameters"]["nitrogen_fixation_potential_kg_n_ha"]
            self.assertIsNone(nfix["value"])
            self.assertEqual(nfix["evidence_classification"], "UNKNOWN")
        self.assertEqual(self.kb.crops["FABA_BEAN"]["parameters"]["nitrogen_fixation_potential_kg_n_ha"]["value"], {"min": 100.0, "max": 200.0})

    def test_03_evidence_classification_and_nitrogen_quarantine(self):
        self.assertEqual(self.kb.rules_catalog["RULE_PERENNIAL_EXCLUSION"]["evidence_classification"], "HARD_CONSTRAINT")
        self.assertEqual(self.kb.rules_catalog["RULE_WATER_IRRIGATION_GATE"]["evidence_classification"], "HARD_CONSTRAINT")
        self.assertEqual(self.kb.rules_catalog["RULE_SOIL_PH_SUITABILITY"]["evidence_classification"], "SOFT_CONSTRAINT")
        self.assertEqual(self.kb.rules_catalog["RULE_DEM_DRAINAGE_UNCERTAINTY"]["evidence_classification"], "EXPERT_ASSUMPTION")
        self.assertEqual(self.kb.rules_catalog["RULE_SALINITY_UNMEASURED_IRRIGATION"]["evidence_classification"], "UNKNOWN")

        res = evaluate_crop_for_field(self.prof_irrig, "DURUM_WHEAT")
        self.assertEqual(res["quarantined_excluded"], ["soilgrids_v6.nitrogen_0_30cm"])
        for rule in res["rule_evaluations"]:
            self.assertIn(rule["evidence_classification"], EVIDENCE_CLASSES)
            self.assertIn(rule["status"], EVALUATION_STATUSES)
            self.assertNotIn("nitrogen_0_30cm", rule["observed_inputs"])

    def test_04_hard_and_soft_constraints_gate_cleanly(self):
        # Processing tomato in Spring on Boumahra rainfed -> HARD FAIL on water gate
        tom_rainfed = evaluate_crop_for_field(self.prof_rainfed, "TOMATO_IND", target_season="Spring")
        self.assertFalse(tom_rainfed["feasible"])
        self.assertEqual(tom_rainfed["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")
        self.assertEqual(_rules_by_id(tom_rainfed)["RULE_WATER_IRRIGATION_GATE"]["status"], "FAIL")

        # Processing tomato in Winter on irrigated plot -> HARD FAIL on planting season
        tom_winter = evaluate_crop_for_field(self.prof_irrig, "TOMATO_IND", target_season="Winter")
        self.assertFalse(tom_winter["feasible"])
        self.assertEqual(_rules_by_id(tom_winter)["RULE_PLANTING_SEASON_COMPATIBILITY"]["status"], "FAIL")

        # Processing tomato in Spring on drip-irrigated Boumahra -> PASS water & season (still conditioned by salinity/DEM UNKNOWNs)
        tom_spring = evaluate_crop_for_field(self.prof_irrig, "TOMATO_IND", target_season="Spring")
        self.assertTrue(tom_spring["feasible"])
        self.assertEqual(_rules_by_id(tom_spring)["RULE_WATER_IRRIGATION_GATE"]["status"], "PASS")

        # Potato on Boumahra pH > 6.5 -> SOFT WARNING for common scab + HYPOTHESIS_NEEDS_DSA_CHECK WARNING
        pot_spring = evaluate_crop_for_field(self.prof_irrig, "POTATO", target_season="Spring")
        r_pot = _rules_by_id(pot_spring)
        self.assertEqual(r_pot["RULE_SOIL_PH_SUITABILITY"]["status"], "WARNING")
        self.assertEqual(r_pot["RULE_HYPOTHESIS_LOCAL_EVIDENCE_STATUS"]["status"], "WARNING")

        # Tamlouka cross-product precipitation straddle (GPM 440 < 450 <= NASA POWER 508) for rainfed Faba Bean -> WARNING
        fb_tam = evaluate_crop_for_field(self.prof_tamlouka, "FABA_BEAN", target_season="Winter")
        self.assertEqual(_rules_by_id(fb_tam)["RULE_PRECIPITATION_REGIME"]["status"], "WARNING")

    def test_05_unknown_constraints_never_auto_pass(self):
        # Water availability='unknown' + irrigation_system='unknown' for strictly irrigated Tomato -> UNKNOWN (feasible=False)
        prof_unk_wat = build_field_profile(_boumahra_payload(
            availability="unknown", source="well", irrigation_system="unknown",
            crop_history=[], preferences={"equipment_constraints": [], "forage_value_weight": 0.0},
        ))
        tom_unk = evaluate_crop_for_field(prof_unk_wat, "TOMATO_IND", target_season="Spring")
        self.assertFalse(tom_unk["feasible"])
        self.assertEqual(tom_unk["feasibility_status"], "UNVERIFIED_HARD_UNKNOWN")
        self.assertEqual(_rules_by_id(tom_unk)["RULE_WATER_IRRIGATION_GATE"]["status"], "UNKNOWN")

        # Missing DEM -> LENTIL drainage rule MUST be UNKNOWN (not PASS)
        len_res = evaluate_crop_for_field(self.prof_rainfed, "LENTIL", target_season="Winter")
        self.assertEqual(_rules_by_id(len_res)["RULE_DEM_DRAINAGE_UNCERTAINTY"]["status"], "UNKNOWN")

        # Irrigated reservoir parcel -> Salinity unmeasured -> UNKNOWN for TOMATO_IND
        tom_ir = evaluate_crop_for_field(self.prof_irrig, "TOMATO_IND", target_season="Spring")
        self.assertEqual(_rules_by_id(tom_ir)["RULE_SALINITY_UNMEASURED_IRRIGATION"]["status"], "UNKNOWN")

    def test_06_repeated_cereals_solanaceae_pulses_and_bare_fallow(self):
        # Clean prior Faba Bean baseline
        prof_after_faba = build_field_profile(_boumahra_payload(
            crop_history=[{"season": "Winter", "year": 2024, "crop_name_raw": "Fava bean"}],
            preferences={"equipment_constraints": [], "forage_value_weight": 0.2},
        ))

        # 2 consecutive cereals -> WARNING (feasible with caution)
        seq_c2 = evaluate_crop_sequence(prof_after_faba, ["DURUM_WHEAT", "BARLEY", "VETCH_OAT"])
        self.assertTrue(seq_c2["feasible"])
        self.assertEqual(_rules_by_id(seq_c2)["SEQ_02_CEREAL_REPETITION"]["status"], "WARNING")

        # 3 consecutive cereals -> FAIL INFEASIBLE_HARD_CONSTRAINT
        seq_c3 = evaluate_crop_sequence(prof_after_faba, ["DURUM_WHEAT", "SOFT_WHEAT", "BARLEY"])
        self.assertFalse(seq_c3["feasible"])
        self.assertEqual(seq_c3["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")
        self.assertEqual(_rules_by_id(seq_c3)["SEQ_02_CEREAL_REPETITION"]["status"], "FAIL")

        # Also 2 planned Wheat after 2024 Durum Wheat history = 3 consecutive -> FAIL
        seq_hist_c3 = evaluate_crop_sequence(self.prof_irrig, ["DURUM_WHEAT", "DURUM_WHEAT", "FABA_BEAN"])
        self.assertFalse(seq_hist_c3["feasible"])
        self.assertEqual(_rules_by_id(seq_hist_c3)["SEQ_02_CEREAL_REPETITION"]["status"], "FAIL")

        # Tomato -> Potato consecutive (Solanaceae < 3 yr) -> FAIL
        seq_sol = evaluate_crop_sequence(prof_after_faba, ["TOMATO_IND", "POTATO", "DURUM_WHEAT"])
        self.assertFalse(seq_sol["feasible"])
        self.assertEqual(_rules_by_id(seq_sol)["SEQ_03_SOLANACEAE_BREAK"]["status"], "FAIL")

        # Repeated Faba Bean -> Lentil (< 3 yr Orobanche hazard) -> FAIL
        seq_pulse = evaluate_crop_sequence(prof_after_faba, ["FABA_BEAN", "LENTIL", "DURUM_WHEAT"])
        self.assertFalse(seq_pulse["feasible"])
        self.assertEqual(_rules_by_id(seq_pulse)["SEQ_04_PULSE_BROOMRAPE_BREAK"]["status"], "FAIL")

        # Consecutive Bare Fallow -> FAIL
        seq_fal = evaluate_crop_sequence(prof_after_faba, ["BARE_FALLOW", "BARE_FALLOW", "DURUM_WHEAT"])
        self.assertFalse(seq_fal["feasible"])
        self.assertEqual(_rules_by_id(seq_fal)["SEQ_08_BARE_FALLOW_COVER"]["status"], "FAIL")

    def test_07_legume_breaks_and_vetch_oat_synergy(self):
        # Faba bean in 2024 -> Durum Wheat -> Chickpea -> Durum Wheat (valid legume break)
        prof_fresh = build_field_profile(_boumahra_payload(
            availability="limited", source="rainfed", irrigation_system="none",
            crop_history=[{"season": "Winter", "year": 2024, "crop_name_raw": "Orge"}],
            preferences={"equipment_constraints": [], "forage_value_weight": 0.5},
        ))
        seq_ok = evaluate_crop_sequence(prof_fresh, ["FABA_BEAN", "DURUM_WHEAT", "CHICKPEA_WINTER"])
        self.assertTrue(seq_ok["feasible"])
        r_seq = _rules_by_id(seq_ok)
        self.assertEqual(r_seq["SEQ_02_CEREAL_REPETITION"]["status"], "PASS")
        self.assertEqual(r_seq["SEQ_07_LEGUME_CEREAL_SYNERGY"]["status"], "PASS")
        self.assertEqual(r_seq["SEQ_10_UNKNOWN_PREDECESSOR_GUARD"]["status"], "PASS")

        # Vetch-Oat fallow replacement after wheat
        seq_vo = evaluate_crop_sequence(self.prof_rainfed, ["VETCH_OAT", "DURUM_WHEAT", "FABA_BEAN"])
        self.assertTrue(seq_vo["feasible"])
        self.assertEqual(_rules_by_id(seq_vo)["SEQ_06_VETCH_OAT_ROLE_AND_REPEAT"]["status"], "PASS")
        self.assertEqual(_rules_by_id(seq_vo)["SEQ_07_LEGUME_CEREAL_SYNERGY"]["status"], "PASS")

    def test_08_perennial_olive_handling(self):
        olive_res = evaluate_crop_for_field(self.prof_rainfed, "OLIVE")
        self.assertFalse(olive_res["feasible"])
        self.assertEqual(olive_res["feasibility_status"], "INFEASIBLE_HARD_CONSTRAINT")
        self.assertEqual(_rules_by_id(olive_res)["RULE_PERENNIAL_EXCLUSION"]["status"], "FAIL")

        seq_olive = evaluate_crop_sequence(self.prof_rainfed, ["DURUM_WHEAT", "OLIVE", "FABA_BEAN"])
        self.assertFalse(seq_olive["feasible"])
        self.assertEqual(_rules_by_id(seq_olive)["SEQ_01_PERENNIAL_GUARD"]["status"], "FAIL")

    def test_09_optional_farmer_inputs_null_vs_empty(self):
        # Omitted / null preferences & omitted history -> optional constraints return UNKNOWN (NOT PASS!)
        prof_null = build_field_profile(_boumahra_payload(crop_history=None, preferences=None))
        dur_null = evaluate_crop_for_field(prof_null, "DURUM_WHEAT")
        r_null = _rules_by_id(dur_null)
        self.assertEqual(r_null["RULE_EQUIPMENT_CONSTRAINT_CHECK"]["status"], "UNKNOWN")
        self.assertEqual(r_null["RULE_FORAGE_REQUIREMENT_ALIGNMENT"]["status"], "UNKNOWN")
        seq_null = evaluate_crop_sequence(prof_null, ["FABA_BEAN", "DURUM_WHEAT"])
        self.assertEqual(_rules_by_id(seq_null)["SEQ_10_UNKNOWN_PREDECESSOR_GUARD"]["status"], "UNKNOWN")

        # Explicit [] equipment & explicit 0.0 forage weight -> PASS (distinguished cleanly from null)
        prof_empty = build_field_profile(_boumahra_payload(
            crop_history=[],
            preferences={"equipment_constraints": [], "forage_value_weight": 0.0},
        ))
        dur_empty = evaluate_crop_for_field(prof_empty, "DURUM_WHEAT")
        r_empty = _rules_by_id(dur_empty)
        self.assertEqual(r_empty["RULE_EQUIPMENT_CONSTRAINT_CHECK"]["status"], "PASS")
        self.assertEqual(r_empty["RULE_FORAGE_REQUIREMENT_ALIGNMENT"]["status"], "PASS")

        # Declared no_hay_baler conflicts with VETCH_OAT -> WARNING
        prof_baler = build_field_profile(_boumahra_payload(
            crop_history=[{"season": "Winter", "year": 2024, "crop_name_raw": "Blé dur"}],
            preferences={"equipment_constraints": ["no_hay_baler"], "forage_value_weight": 0.6},
        ))
        vo_res = evaluate_crop_for_field(prof_baler, "VETCH_OAT")
        self.assertEqual(_rules_by_id(vo_res)["RULE_EQUIPMENT_CONSTRAINT_CHECK"]["status"], "WARNING")
        bf_res = evaluate_crop_for_field(prof_baler, "BARE_FALLOW")
        self.assertEqual(_rules_by_id(bf_res)["RULE_FORAGE_REQUIREMENT_ALIGNMENT"]["status"], "WARNING")

    def test_10_missing_field_data_and_soc_nan_degradation(self):
        # SoilGrids SOC-NaN pixel (UTM 348375, 4057375) -> SOC rule returns UNKNOWN, Clay returns PASS/MODELED
        tf_wgs = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
        b_soc = box(348375.0 - 80.0, 4057375.0 - 80.0, 348375.0 + 80.0, 4057375.0 + 80.0)
        p_soc = _boumahra_payload()
        p_soc["field"]["geometry"] = {"type": "Polygon", "coordinates": [[list(tf_wgs.transform(x, y)) for x, y in b_soc.exterior.coords]]}
        prof_soc_nan = build_field_profile(p_soc)
        dur_soc_nan = evaluate_crop_for_field(prof_soc_nan, "DURUM_WHEAT")
        self.assertEqual(_rules_by_id(dur_soc_nan)["RULE_SOIL_SOC_PRIORITY"]["status"], "UNKNOWN")

        # All spatial datasets missing -> engine remains robust, returning UNKNOWN across all missing layers
        missing = Path("/tmp/definitely_missing_phaseg_asset")
        try:
            fgp._load_coarse_tables.cache_clear()
            with mock.patch.multiple(
                fgp,
                SOILGRIDS_V6_ZIP=missing / "sg.zip",
                SOILGRIDS_USDA_TIF=missing / "usda.tif",
                CROP_FREQ_ALIGNED_10M_TIF=missing / "cf1.tif",
                CROP_FREQ_RAW_TIF=missing / "cf2.tif",
                S2_PHASEA_10M_TIF=missing / "s2_10.tif",
                S2_PHASEA_20M_TIF=missing / "s2_20.tif",
                MODIS_SEASONAL_DIR=missing,
                GPM_SEASONAL_CSV=missing / "gpm.csv",
                SMAP_SEASONAL_CSV=missing / "smap.csv",
                GRID_11KM_CSV=missing / "grid11.csv",
                NASA_POWER_AG_GPKG=missing / "ag.gpkg",
                NASA_POWER_RE_GPKG=missing / "re.gpkg",
                NASA_POWER_DAILY_CELLS_CSV=missing / "np.csv",
                WILAYA_MONTHLY_CSV=missing / "wm.csv",
            ):
                fgp._load_coarse_tables.cache_clear()
                prof_empty_geo = build_field_profile(_boumahra_payload(
                    availability="moderate", source="rainfed", irrigation_system="none",
                ))
        finally:
            fgp._load_coarse_tables.cache_clear()

        res_miss = evaluate_crop_for_field(prof_empty_geo, "DURUM_WHEAT")
        r_miss = _rules_by_id(res_miss)
        for rid in (
            "RULE_PRECIPITATION_REGIME",
            "RULE_THERMAL_HEAT_FROST",
            "RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT",
            "RULE_SOIL_TEXTURE_WORKABILITY",
            "RULE_SOIL_PH_SUITABILITY",
            "RULE_SOIL_SOC_PRIORITY",
            "RULE_CROPLAND_VEG_CONTEXT",
        ):
            self.assertEqual(r_miss[rid]["status"], "UNKNOWN", f"{rid} should be UNKNOWN when datasets are missing")

    def test_11_deterministic_reproducibility(self):
        a1 = evaluate_all_crops_for_field(self.prof_irrig, target_season="Winter")
        a2 = evaluate_all_crops_for_field(self.prof_irrig, target_season="Winter")
        self.assertEqual(a1, a2)

        s1 = evaluate_crop_sequence(self.prof_irrig, ["FABA_BEAN", "DURUM_WHEAT", "TOMATO_IND"])
        s2 = evaluate_crop_sequence(self.prof_irrig, ["FABA_BEAN", "DURUM_WHEAT", "TOMATO_IND"])
        self.assertEqual(s1, s2)


if __name__ == "__main__":
    unittest.main()
