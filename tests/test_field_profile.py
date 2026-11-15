"""Automated tests for Field Shift minimal farmer input & automatic Field Profile architecture."""

import copy
import unittest

import pandas as pd

from field_geospatial_processor import extract_field_geospatial_context
from field_profile_builder import (
    FarmerInputValidationError,
    build_field_profile,
    load_input_schema,
    render_field_analysis_report_md,
    validate_farmer_input,
)


def _sample_boumahra_payload() -> dict:
    # Real cropland parcel in Boumahra Ahmed (Guelma alluvial plain, EPSG:4326)
    return {
        "field": {
            "field_id": "PARCEL_BM_001",
            "field_name": "El Fedj Plain Plot",
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
            "availability": "moderate",
            "source": "reservoir",
            "irrigation_system": "drip",
        },
        "crop_history": [
            {
                "season": "Winter",
                "year": 2024,
                "planting_month": 11,
                "crop_id": None,
                "crop_name_raw": "Blé dur",
                "yield_tons_per_hectare": None,
                "notes": "Grown after cereal stubble",
            }
        ],
        "planning": {
            "start_season": "Winter",
            "start_year": 2025,
            "horizon_seasons": 3,
            "planting_month": 11,
            "planning_mode": "HISTORICAL_SIMULATION",
        },
        "preferences": {
            "target_crop_ids": ["DURUM_WHEAT", "FABA_BEAN", "TOMATO_IND"],
            "excluded_crop_ids": ["POTATO"],
            "equipment_constraints": ["no_precision_planter"],
            "water_saving_weight": 0.25,
            "soil_improvement_weight": 0.25,
            "income_weight": 0.20,
            "risk_reduction_weight": 0.20,
            "forage_value_weight": 0.10,
        },
    }


class TestFieldInputAndProfile(unittest.TestCase):
    def test_schema_exists_and_forbids_technical_inputs(self):
        schema = load_input_schema()
        self.assertEqual(schema["required"], ["field", "water", "planning"])
        self.assertFalse(schema["additionalProperties"])

        bad = _sample_boumahra_payload()
        bad["soil_ph"] = 7.1
        with self.assertRaises(FarmerInputValidationError):
            validate_farmer_input(bad)

        bad_nested = _sample_boumahra_payload()
        bad_nested["water"]["ndvi"] = 0.55
        with self.assertRaises(FarmerInputValidationError):
            validate_farmer_input(bad_nested)

    def test_raw_crop_alias_normalization_and_no_fake_yield(self):
        norm = validate_farmer_input(_sample_boumahra_payload())
        h0 = norm["crop_history"][0]
        self.assertEqual(h0["crop_name_raw"], "Blé dur")
        self.assertEqual(h0["crop_id_resolved"], "DURUM_WHEAT")
        self.assertEqual(h0["provenance"], "USER_REPORTED")
        self.assertIsNone(h0["yield_tons_per_hectare"])

    def test_geospatial_extraction_real_guelma_polygon_with_provenance(self):
        payload = _sample_boumahra_payload()
        geo = extract_field_geospatial_context(payload["field"]["geometry"])
        sv = geo["spatial_validation"]
        self.assertTrue(1.0 < sv["area_ha"] < 10.0)
        self.assertEqual(sv["wilaya_overlap_pct"], 100.0)
        self.assertEqual(sv["primary_commune"]["name_2"], "Boumahra Ahmed")

        ds = geo["extracted_datasets"]
        # SoilGrids V6 populated with modeled quality status & Nitrogen quarantined
        clay = ds["soilgrids_v6"]["clay_0_30cm"]
        self.assertIsNotNone(clay["value"])
        self.assertGreater(clay["valid_pixel_count"], 0)
        self.assertGreater(clay["polygon_coverage_pct"], 99.0)
        self.assertEqual(clay["quality_status"], "MODELED_SPATIAL_ESTIMATE")
        for req_key in (
            "value",
            "unit",
            "source_dataset",
            "spatial_resolution",
            "temporal_coverage",
            "valid_pixel_count",
            "polygon_coverage_pct",
            "aggregation_method",
            "quality_status",
            "uncertainty_or_limitations",
        ):
            self.assertIn(req_key, clay)

        self.assertIsNone(ds["soilgrids_v6"]["nitrogen_0_30cm"]["value"])
        self.assertEqual(ds["soilgrids_v6"]["nitrogen_0_30cm"]["quality_status"], "UNVALIDATED_EXCLUDED")

        # Sentinel-2 10m snapshot vs Wilaya multi-year fallback distinction
        self.assertIsNotNone(ds["sentinel2"]["s2_2024_03_ndvi_10m"]["value"])
        self.assertEqual(ds["sentinel2"]["s2_2024_03_ndvi_10m"]["quality_status"], "REMOTE_SENSING_DERIVED")
        self.assertEqual(ds["sentinel2"]["s2_wilaya_spring_ndvi_climatology_2017_2025"]["quality_status"], "REGIONAL_FALLBACK_ONLY")

        # MODIS, GPM, SMAP, NASA POWER extracted; DEM explicitly null & unavailable
        self.assertIsNotNone(ds["modis"]["modis_ndvi_spring_2016_2025_mean"]["value"])
        self.assertIsNotNone(ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["value"])
        self.assertIsNotNone(ds["gpm_and_smap"]["smap_rootzone_sm_spring_2016_2025_mean"]["value"])
        self.assertIsNotNone(ds["nasa_power"]["nasa_power_t2m_2016_2025_mean_c"]["value"])
        self.assertIsNone(ds["terrain_dem"]["dem_elevation_m"]["value"])
        self.assertEqual(ds["terrain_dem"]["dem_elevation_m"]["quality_status"], "UNAVAILABLE_NOT_INTEGRATED")

    def test_outside_guelma_polygon_rejected(self):
        outside = {
            "type": "Polygon",
            "coordinates": [[[3.0, 36.7], [3.01, 36.7], [3.01, 36.71], [3.0, 36.71], [3.0, 36.7]]],
        }
        with self.assertRaises(ValueError):
            extract_field_geospatial_context(outside)

    def test_full_profile_assembly_material_questions_and_dictionary(self):
        payload = _sample_boumahra_payload()
        payload["water"]["availability"] = "unknown"
        payload["crop_history"] = []
        payload["preferences"]["target_crop_ids"] = ["DURUM_WHEAT", "LENTIL"]

        profile = build_field_profile(payload)
        self.assertFalse(profile["section_c_agronomic_knowledge_base"]["optimization_executed"])
        q_ids = {q["question_id"] for q in profile["section_d_quality_and_uncertainty"]["conditional_follow_up_questions"]}
        self.assertIn("Q_WATER_MATERIAL", q_ids)
        self.assertIn("Q_LAST_CROP_MATERIAL", q_ids)
        self.assertIn("Q_DRAINAGE_QUALITATIVE", q_ids)

        md = render_field_analysis_report_md(profile)
        self.assertIn("Automatically Estimated Soil & Cropland Snapshot", md)
        self.assertIn("Boumahra Ahmed", md)

        dd = pd.read_csv("docs/field_profile/field_profile_data_dictionary.csv")
        self.assertGreaterEqual(len(dd), 20)


if __name__ == "__main__":
    unittest.main()
