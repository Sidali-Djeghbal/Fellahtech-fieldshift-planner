"""Automated unit & invariant tests for Field Shift Phase D integration outputs."""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parent.parent
INT = ROOT / "data" / "INTEGRATED"


class TestPhaseDIntegration(unittest.TestCase):
    def test_validation_report_zero_failures(self):
        rep = pd.read_csv(INT / "quality" / "phaseD_validation_report.csv")
        self.assertGreaterEqual(len(rep), 12)
        self.assertEqual(int((rep["status"] == "FAIL").sum()), 0)
        self.assertEqual(int((rep["status"] == "PASS").sum()), len(rep) - 1)

    def test_crop_frequency_aligned_to_s2_10m_grid(self):
        s2_p = ROOT / "data" / "SENTINEL2" / "raw" / "phaseA_2024_03" / "sentinel2_2024_03_indices_10m.tif"
        cf_p = INT / "spatial" / "guelma_crop_frequency_2021_2025_aligned_s2_10m.tif"
        with rasterio.open(s2_p) as s2, rasterio.open(cf_p) as cf:
            self.assertEqual(s2.shape, cf.shape)
            self.assertEqual(s2.transform, cf.transform)
            self.assertEqual(str(s2.crs), str(cf.crs))

    def test_wilaya_monthly_panel_chronology_and_jan2017_flag(self):
        wm = pd.read_csv(INT / "features" / "wilaya_monthly_panel_2016_2025.csv")
        self.assertEqual(len(wm), 120)
        self.assertEqual(int(wm["year_month"].duplicated().sum()), 0)
        jan17 = wm.loc[wm["year_month"] == "2017-01"].iloc[0]
        self.assertFalse(bool(jan17["s2_is_model_eligible_monthly"]))
        self.assertAlmostEqual(float(jan17["s2_NDVI_valid_pct"]), 1.4173, places=4)
        self.assertFalse(bool(wm["gpm_monthly_available_on_disk"].any()))
        self.assertFalse(bool(wm["smap_monthly_available_on_disk"].any()))
        self.assertTrue(np.isclose(wm["PRECTOTCORR_sum_mm"].shift(1).dropna(), wm["prectot_lag1_mm"].dropna(), atol=1e-4).all())

    def test_seasonal_and_leakage_guards(self):
        ws = pd.read_csv(INT / "features" / "wilaya_seasonal_panel_2016_2025.csv")
        w17 = ws.loc[ws["is_winter_2017_incomplete"]].iloc[0]
        self.assertFalse(bool(w17["s2_is_complete_season"]))
        c_sea = pd.read_csv(INT / "features" / "commune_seasonal_panel_2016_2025.csv")
        self.assertEqual(len(c_sea), 34 * 40)
        self.assertTrue((c_sea.loc[c_sea["season_year"] <= 2020, "crop_freq_usable_for_year"] == False).all())

    def test_soil_250m_clean_and_nitrogen_flagged(self):
        soil = pd.read_csv(INT / "canonical" / "soil_properties" / "soilgrids_250m_canonical.csv")
        self.assertEqual(len(soil), 59050)
        self.assertTrue((soil["nitrogen_scaling_flag"] == "UNVALIDATED_TRACEABILITY_ONLY_DO_NOT_USE_IN_SCORING").all())
        self.assertTrue(soil["ph_0_30cm"].between(5.0, 8.5).all())


if __name__ == "__main__":
    unittest.main()
