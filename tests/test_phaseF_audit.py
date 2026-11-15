"""Phase F Scientific & Geospatial Audit Test Suite for Field Shift.

Covers all 10 audit verification categories without modifying Phases A-E
or submitting any Earth Engine jobs:
1. Small field polygon (~0.2 ha)
2. Large field polygon (~1,073 ha + performance guard)
3. Partial Wilaya overlap & out-of-Wilaya rejection
4. NoData / masked pixel preservation (SoilGrids urban NaN & SOC-NaN)
5. CRS transformations (EPSG:4326 vs EPSG:3857 vs EPSG:32632 parity)
6. Invalid geometry rejection (bowtie / self-intersecting / empty / non-Polygon)
7. Missing raster & CSV dataset resilience (graceful UNAVAILABLE_NOT_INTEGRATED)
8. Optional farmer inputs contract (null/omitted vs [] vs 0.0)
9. Regional vs field classification & NASA POWER meteorological Winter season_year accuracy
10. Determinism / reproducibility + independent area-weighted raster math audit
"""

from __future__ import annotations

import copy
import math
import time
import unittest
from pathlib import Path
from unittest import mock

import geopandas as gpd
import numpy as np
import pyproj
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box

import field_geospatial_processor as fgp
from field_geospatial_processor import extract_field_geospatial_context, validate_and_project_polygon
from field_profile_builder import (
    FarmerInputValidationError,
    build_field_profile,
    render_field_analysis_report_md,
    validate_farmer_input,
)
from fieldshift_integration.config import S2_PHASEA_10M_TIF


def _rect_wgs84(lon0: float, lat0: float, dlon: float, dlat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon0, lat0],
            [lon0 + dlon, lat0],
            [lon0 + dlon, lat0 + dlat],
            [lon0, lat0 + dlat],
            [lon0, lat0],
        ]],
    }


def _minimal_payload(geometry: dict, geometry_crs: str = "EPSG:4326") -> dict:
    return {
        "field": {
            "field_id": "AUDIT_FIELD_01",
            "field_name": "Audit Plot",
            "geometry": geometry,
            "geometry_crs": geometry_crs,
        },
        "water": {
            "availability": "moderate",
            "source": "rainfed",
            "irrigation_system": "none",
        },
        "planning": {
            "start_season": "Winter",
            "start_year": 2025,
            "horizon_seasons": 3,
        },
    }


class TestPhaseFAudit(unittest.TestCase):
    def test_01_small_field_polygon_extraction(self):
        tiny = _rect_wgs84(7.5080, 36.4698, 0.0005, 0.0004)  # ~0.20 ha in Boumahra Ahmed
        geo = extract_field_geospatial_context(tiny)
        sv = geo["spatial_validation"]
        self.assertTrue(0.1 < sv["area_ha"] < 0.35)
        self.assertEqual(sv["wilaya_overlap_pct"], 100.0)
        self.assertEqual(sv["primary_commune"]["name_2"], "Boumahra Ahmed")

        ds = geo["extracted_datasets"]
        self.assertGreaterEqual(ds["sentinel2"]["s2_2024_03_ndvi_10m"]["valid_pixel_count"], 20)
        self.assertEqual(ds["sentinel2"]["s2_2024_03_ndvi_10m"]["polygon_coverage_pct"], 100.0)
        self.assertGreaterEqual(ds["soilgrids_v6"]["clay_0_30cm"]["valid_pixel_count"], 1)

    def test_02_large_polygon_and_runtime_efficiency(self):
        # First warm up coarse CSV cache cleanly so benchmark measures geospatial window cost
        large = _rect_wgs84(7.4600, 36.4750, 0.0450, 0.0240)  # ~1,073 ha plain
        fgp._load_coarse_tables()
        t0 = time.perf_counter()
        geo = extract_field_geospatial_context(large)
        dt = time.perf_counter() - t0

        sv = geo["spatial_validation"]
        self.assertGreater(sv["area_ha"], 900.0)
        self.assertEqual(sv["wilaya_overlap_pct"], 100.0)
        self.assertLess(dt, 20.0, f"Large polygon (~1,073 ha) took {dt:.2f}s (prepared geometry fast path expected)")
        self.assertGreater(geo["extracted_datasets"]["sentinel2"]["s2_2024_03_ndvi_10m"]["valid_pixel_count"], 50000)

    def test_03_partial_wilaya_coverage_and_outside_rejection(self):
        # Straddles Guelma perimeter around Roknia / north-west edge
        wilaya = gpd.read_file(fgp.WILAYA_GPKG).geometry.iloc[0]
        ext = list(wilaya.exterior.coords) if wilaya.geom_type == "Polygon" else list(list(wilaya.geoms)[0].exterior.coords)
        bx, by = ext[len(ext) // 4]
        tf_wgs = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
        b_utm = box(bx - 250.0, by - 250.0, bx + 250.0, by + 250.0)
        border_poly = {"type": "Polygon", "coordinates": [[list(tf_wgs.transform(x, y)) for x, y in b_utm.exterior.coords]]}

        geo = extract_field_geospatial_context(border_poly)
        sv = geo["spatial_validation"]
        self.assertGreater(sv["wilaya_overlap_pct"], 0.0)
        self.assertLess(sv["wilaya_overlap_pct"], 99.0)
        self.assertTrue(any("outside Guelma" in w for w in sv["validation_warnings"]))

        outside = _rect_wgs84(2.9, 36.7, 0.01, 0.01)
        with self.assertRaises(ValueError):
            extract_field_geospatial_context(outside)

    def test_04_nodata_and_soilgrids_soc_nan_preservation(self):
        tf_wgs = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

        # Known internal masked urban/water pixel inside Bouati Mahmoud (UTM 347875, 4058375)
        b_masked = box(347875.0 - 50.0, 4058375.0 - 50.0, 347875.0 + 50.0, 4058375.0 + 50.0)
        poly_masked = {"type": "Polygon", "coordinates": [[list(tf_wgs.transform(x, y)) for x, y in b_masked.exterior.coords]]}
        profile_masked = build_field_profile(_minimal_payload(poly_masked))
        sg_masked = profile_masked["section_b_extracted_geospatial"]["extracted_datasets"]["soilgrids_v6"]
        self.assertIsNone(sg_masked["clay_0_30cm"]["value"])
        self.assertEqual(sg_masked["clay_0_30cm"]["quality_status"], "UNAVAILABLE_MASKED_PIXEL")
        self.assertIsNone(sg_masked["usda_texture_0_5cm"]["value"])
        self.assertEqual(sg_masked["usda_texture_0_5cm"]["quality_status"], "UNAVAILABLE_MASKED_PIXEL")
        md = render_field_analysis_report_md(profile_masked)
        self.assertIn("Field Analysis Report", md)

        # Known internal Clay-valid / SOC-NaN location inside Bouati Mahmoud (UTM 348375, 4057375)
        b_soc_nan = box(348375.0 - 80.0, 4057375.0 - 80.0, 348375.0 + 80.0, 4057375.0 + 80.0)
        poly_soc_nan = {"type": "Polygon", "coordinates": [[list(tf_wgs.transform(x, y)) for x, y in b_soc_nan.exterior.coords]]}
        geo_soc = extract_field_geospatial_context(poly_soc_nan)["extracted_datasets"]["soilgrids_v6"]
        self.assertIsNotNone(geo_soc["clay_0_30cm"]["value"])
        self.assertEqual(geo_soc["clay_0_30cm"]["quality_status"], "MODELED_SPATIAL_ESTIMATE")
        self.assertIsNone(geo_soc["soc_0_30cm"]["value"])
        self.assertEqual(geo_soc["soc_0_30cm"]["quality_status"], "UNAVAILABLE_MASKED_PIXEL")

    def test_05_crs_transformations_parity(self):
        poly_4326 = _rect_wgs84(7.5075, 36.4691, 0.0020, 0.0020)
        tf_3857 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        tf_32632 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)

        ring = poly_4326["coordinates"][0]
        poly_3857 = {"type": "Polygon", "coordinates": [[list(tf_3857.transform(x, y)) for x, y in ring]]}
        poly_32632 = {"type": "Polygon", "coordinates": [[list(tf_32632.transform(x, y)) for x, y in ring]]}

        res_4326 = extract_field_geospatial_context(poly_4326, geometry_crs="EPSG:4326")
        res_3857 = extract_field_geospatial_context(poly_3857, geometry_crs="EPSG:3857")
        res_32632 = extract_field_geospatial_context(poly_32632, geometry_crs="EPSG:32632")

        a0 = res_4326["spatial_validation"]["area_ha"]
        self.assertAlmostEqual(a0, res_3857["spatial_validation"]["area_ha"], places=3)
        self.assertAlmostEqual(a0, res_32632["spatial_validation"]["area_ha"], places=3)
        self.assertEqual(
            res_4326["extracted_datasets"]["soilgrids_v6"]["clay_0_30cm"]["value"],
            res_32632["extracted_datasets"]["soilgrids_v6"]["clay_0_30cm"]["value"],
        )
        self.assertAlmostEqual(
            res_4326["extracted_datasets"]["sentinel2"]["s2_2024_03_ndvi_10m"]["value"],
            res_3857["extracted_datasets"]["sentinel2"]["s2_2024_03_ndvi_10m"]["value"],
            places=3,
        )

    def test_06_invalid_geometry_strict_rejection(self):
        # Self-intersecting bowtie must be rejected strictly (NOT silently repaired)
        bowtie = {
            "type": "Polygon",
            "coordinates": [[
                [7.5075, 36.4691],
                [7.5095, 36.4711],
                [7.5095, 36.4691],
                [7.5075, 36.4711],
                [7.5075, 36.4691],
            ]],
        }
        with self.assertRaises(ValueError):
            validate_and_project_polygon(bowtie)

        # MultiPolygon must be rejected strictly
        multi = {
            "type": "MultiPolygon",
            "coordinates": [[[[7.5075, 36.4691], [7.5085, 36.4691], [7.5085, 36.4701], [7.5075, 36.4701], [7.5075, 36.4691]]]],
        }
        with self.assertRaises(ValueError):
            validate_and_project_polygon(multi)

        # Degenerate collinear zero-area polygon
        collinear = {
            "type": "Polygon",
            "coordinates": [[[7.5075, 36.4691], [7.5085, 36.4691], [7.5095, 36.4691], [7.5075, 36.4691]]],
        }
        with self.assertRaises(ValueError):
            validate_and_project_polygon(collinear)

    def test_07_missing_dataset_files_degrade_gracefully(self):
        missing = Path("/tmp/definitely_missing_fieldshift_asset_xyz")
        poly = _rect_wgs84(7.5075, 36.4691, 0.0020, 0.0020)
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
                profile = build_field_profile(_minimal_payload(poly))
                ds = profile["section_b_extracted_geospatial"]["extracted_datasets"]
                # Verify full schema keys exist even when every dataset asset is missing
                self.assertIn("clay_0_30cm", ds["soilgrids_v6"])
                self.assertIn("usda_texture_0_5cm", ds["soilgrids_v6"])
                self.assertEqual(ds["soilgrids_v6"]["clay_0_30cm"]["quality_status"], "UNAVAILABLE_NOT_INTEGRATED")
                self.assertEqual(ds["soilgrids_v6"]["nitrogen_0_30cm"]["quality_status"], "UNVALIDATED_EXCLUDED")
                self.assertEqual(ds["modis"]["modis_ndvi_spring_2016_2025_mean"]["quality_status"], "UNAVAILABLE_NOT_INTEGRATED")
                self.assertEqual(ds["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["quality_status"], "UNAVAILABLE_NOT_INTEGRATED")
                self.assertEqual(ds["nasa_power"]["nasa_power_t2m_2016_2025_mean_c"]["quality_status"], "UNAVAILABLE_NOT_INTEGRATED")
                md = render_field_analysis_report_md(profile)
                self.assertIn("UNAVAILABLE_NOT_INTEGRATED", md)
        finally:
            fgp._load_coarse_tables.cache_clear()

    def test_08_optional_farmer_inputs_null_vs_empty_list(self):
        poly = _rect_wgs84(7.5075, 36.4691, 0.0020, 0.0020)
        # Case A: Minimal only (crop_history & preferences omitted -> NOT_PROVIDED)
        p_omitted = _minimal_payload(poly)
        norm_a = validate_farmer_input(p_omitted)
        self.assertIsNone(norm_a["crop_history"])
        self.assertIsNone(norm_a["preferences"])
        self.assertEqual(norm_a["input_completeness_flags"]["crop_history"], "NOT_PROVIDED")
        self.assertEqual(norm_a["input_completeness_flags"]["preferences_block"], "NOT_PROVIDED")
        self.assertEqual(norm_a["input_completeness_flags"]["forage_value_weight"], "NOT_PROVIDED")
        self.assertEqual(norm_a["input_completeness_flags"]["equipment_constraints"], "NOT_PROVIDED")

        # Case B: Explicit [] and explicit 0.0 vs null forage/equipment
        p_explicit = copy.deepcopy(p_omitted)
        p_explicit["crop_history"] = []
        p_explicit["preferences"] = {
            "target_crop_ids": None,
            "excluded_crop_ids": [],
            "equipment_constraints": [],
            "forage_value_weight": 0.0,
        }
        norm_b = validate_farmer_input(p_explicit)
        self.assertEqual(norm_b["crop_history"], [])
        self.assertEqual(norm_b["input_completeness_flags"]["crop_history"], "EXPLICITLY_CONFIRMED_EMPTY")
        self.assertEqual(norm_b["input_completeness_flags"]["target_crop_ids"], "NOT_PROVIDED")
        self.assertEqual(norm_b["input_completeness_flags"]["excluded_crop_ids"], "EXPLICITLY_CONFIRMED_EMPTY")
        self.assertEqual(norm_b["input_completeness_flags"]["equipment_constraints"], "EXPLICITLY_CONFIRMED_EMPTY")
        self.assertEqual(norm_b["input_completeness_flags"]["forage_value_weight"], "PROVIDED")
        self.assertEqual(norm_b["preferences"]["forage_value_weight"], 0.0)

        # Full profile runs cleanly without preferences or crop_history & counts USER_REPORTED honestly (3 vs 5)
        prof_a = build_field_profile(p_omitted)
        self.assertEqual(prof_a["section_d_quality_and_uncertainty"]["quality_status_counts"]["USER_REPORTED"], 3)
        self.assertIsNone(prof_a["section_c_agronomic_knowledge_base"]["resolved_history_summary"])

        # Technical fields inside optional preferences remain forbidden
        p_bad = copy.deepcopy(p_omitted)
        p_bad["preferences"] = {"clay_pct": 33.0}
        with self.assertRaises(FarmerInputValidationError):
            validate_farmer_input(p_bad)

    def test_09_regional_vs_field_distinction_and_winter_season_year_fix(self):
        # Verify Boumahra (wet plain) vs Tamlouka (semi-arid south) hydro-climate difference
        boumahra = _rect_wgs84(7.5075, 36.4691, 0.0020, 0.0020)
        tamlouka = _rect_wgs84(7.1390, 36.1350, 0.0033, 0.0027)

        geo_b = extract_field_geospatial_context(boumahra)["extracted_datasets"]
        geo_t = extract_field_geospatial_context(tamlouka)["extracted_datasets"]

        # Regional vs Field provenance guarantees
        self.assertEqual(geo_b["sentinel2"]["s2_wilaya_spring_ndvi_climatology_2017_2025"]["quality_status"], "REGIONAL_FALLBACK_ONLY")
        self.assertEqual(geo_b["soilgrids_v6"]["clay_0_30cm"]["quality_status"], "MODELED_SPATIAL_ESTIMATE")
        self.assertEqual(geo_b["soilgrids_v6"]["nitrogen_0_30cm"]["quality_status"], "UNVALIDATED_EXCLUDED")
        self.assertIsNone(geo_b["soilgrids_v6"]["nitrogen_0_30cm"]["value"])

        # Dry vs Wet climate gradient
        self.assertGreater(
            geo_b["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["value"],
            geo_t["gpm_and_smap"]["gpm_annual_precip_2016_2025_mean_mm"]["value"] + 100.0,
        )

        # Verify meteorological season_year Winter computation excludes incomplete Winter 2016 / 2026
        np_p = geo_b["nasa_power"]["nasa_power_annual_precip_2016_2025_mean_mm"]
        self.assertIn("9 complete DJF winters 2017-2025", np_p["temporal_coverage"])
        winter_mm = np_p["stats"]["winter"]
        # Direct pandas ground truth on AG cell matching Boumahra using season_year
        import pandas as pd
        df = pd.read_csv(fgp.NASA_POWER_DAILY_CELLS_CSV)
        tables = fgp._load_coarse_tables()
        geom_utm = validate_and_project_polygon(boumahra)["geom_utm"]
        ag_hits = [str(r.cell_id) for r in tables["ag_gdf"].itertuples() if geom_utm.intersection(r.geometry).area > 0]
        self.assertEqual(len(ag_hits), 1)
        sub = df[(df["community"] == "AG") & (df["cell_id"].astype(str) == ag_hits[0]) & (df["variable"] == "PRECTOTCORR")].copy()
        sub["season_year"] = np.where(sub["month"] == 12, sub["year"] + 1, sub["year"])
        w_df = sub[(sub["season"] == "Winter") & (sub["season_year"].between(2017, 2025))]
        expected_winter_mm = round(float(w_df.groupby("season_year")["value"].sum().mean()), 2)
        self.assertEqual(winter_mm, expected_winter_mm)

    def test_10_determinism_and_independent_area_weighted_math(self):
        poly = _rect_wgs84(7.5075, 36.4691, 0.0020, 0.0020)
        g1 = extract_field_geospatial_context(poly)
        g2 = extract_field_geospatial_context(poly)
        self.assertEqual(g1, g2)

        # Verify s2_2024_03_ndvi_10m against independent rasterio + shapely brute-force loop
        geom_utm = validate_and_project_polygon(poly)["geom_utm"]
        with rasterio.open(S2_PHASEA_10M_TIF) as ids, rasterio.open(fgp.S2_PHASEA_VALID_10M_TIF) as vds:
            minx, miny, maxx, maxy = geom_utm.bounds
            win = from_bounds(minx, miny, maxx, maxy, transform=ids.transform)
            rw = rasterio.windows.Window(
                max(0, int(math.floor(win.col_off))),
                max(0, int(math.floor(win.row_off))),
                int(math.ceil(win.col_off + win.width)) - max(0, int(math.floor(win.col_off))),
                int(math.ceil(win.row_off + win.height)) - max(0, int(math.floor(win.row_off))),
            )
            arr = ids.read(1, window=rw).astype("float64")
            varr = vds.read(1, window=rw)
            tf = ids.window_transform(rw)
            num, den = 0.0, 0.0
            for r in range(rw.height):
                for c in range(rw.width):
                    v = arr[r, c]
                    if np.isfinite(v) and v != -9999.0 and varr[r, c] > 0:
                        px = box(tf.c + c * tf.a, tf.f + (r + 1) * tf.e, tf.c + (c + 1) * tf.a, tf.f + r * tf.e)
                        w = geom_utm.intersection(px).area
                        if w > 0:
                            num += v * w
                            den += w
            indep_ndvi = round(num / den, 4)
        self.assertEqual(g1["extracted_datasets"]["sentinel2"]["s2_2024_03_ndvi_10m"]["value"], indep_ndvi)


if __name__ == "__main__":
    unittest.main()
