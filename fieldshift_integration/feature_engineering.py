"""Task 5 & 6: Defensive Feature Engineering with Strict Leakage & Scale Controls."""

from typing import Dict

import numpy as np
import pandas as pd

from .config import (
    CANONICAL_DIR,
    FEATURES_DIR,
    SEASON_ORDER,
    SPATIAL_INT_DIR,
)


def build_feature_tables() -> Dict[str, int]:
    """Generate documented, leakage-controlled feature tables across temporal and spatial tiers."""
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}

    # 1. Wilaya Monthly Analytical Panel (2016-01..2025-12 = 120 months; causal climate lags + S2 2017-2025)
    np_m = pd.read_csv(CANONICAL_DIR / "climate_observations" / "nasa_power_monthly_canonical.csv").sort_values(["year", "month"]).reset_index(drop=True)
    s2_m = pd.read_csv(CANONICAL_DIR / "vegetation_observations" / "sentinel2_monthly_wilaya_canonical.csv")

    s2_cols = [
        "year_month",
        "image_count",
        "cloud_prob_matched_images",
        "NDVI_mean",
        "NDVI_median",
        "NDVI_stdDev",
        "NDVI_p5",
        "NDVI_p95",
        "EVI_mean",
        "EVI_median",
        "EVI_stdDev",
        "EVI_p5",
        "EVI_p95",
        "NDMI_mean",
        "NDMI_median",
        "NDRE_mean",
        "NDRE_median",
        "NDVI_valid_pixels",
        "NDVI_valid_pct",
        "NDMI_valid_pct",
        "mean_valid_obs_per_px_10m",
        "mean_valid_obs_per_px_20m",
        "EVI_excluded_composite_pixels",
        "evi_obs_excluded_total_10m",
        "scl2_share_pct",
        "completeness_status",
        "is_model_eligible_monthly",
    ]
    s2_sub = s2_m[s2_cols].copy()
    s2_rename = {c: f"s2_{c}" for c in s2_sub.columns if c != "year_month"}
    s2_sub = s2_sub.rename(columns=s2_rename)
    s2_sub["s2_ndvi_iqr_p95_p5"] = (s2_sub["s2_NDVI_p95"] - s2_sub["s2_NDVI_p5"]).round(6)
    s2_sub["s2_evi_iqr_p95_p5"] = (s2_sub["s2_EVI_p95"] - s2_sub["s2_EVI_p5"]).round(6)

    wm = np_m.merge(s2_sub, on="year_month", how="left")
    wm["diurnal_temp_range_mean_c"] = (wm["T2M_MAX_mean_C"] - wm["T2M_MIN_mean_C"]).round(4)

    # Strictly causal antecedent lags (computed from past months t-1..t-3 ONLY; zero look-ahead)
    wm["prectot_lag1_mm"] = wm["PRECTOTCORR_sum_mm"].shift(1).round(4)
    wm["prectot_lag2_mm"] = wm["PRECTOTCORR_sum_mm"].shift(2).round(4)
    wm["prectot_antecedent_3m_sum_mm"] = wm["PRECTOTCORR_sum_mm"].shift(1).rolling(3, min_periods=3).sum().round(4)
    wm["t2m_lag1_mean_c"] = wm["T2M_mean_C"].shift(1).round(4)
    wm["rh2m_lag1_mean_pct"] = wm["RH2M_mean_pct"].shift(1).round(4)

    # Explicit availability, missingness & leakage guards
    wm["sentinel2_available"] = wm["s2_image_count"].notna()
    wm["s2_is_model_eligible_monthly"] = wm["s2_is_model_eligible_monthly"].astype("boolean").fillna(False)
    wm["gpm_monthly_available_on_disk"] = False
    wm["smap_monthly_available_on_disk"] = False
    wm["spatial_unit"] = "wilaya_3683.2311km2"
    wm["climate_spatial_support"] = "AG:0.5x0.625deg_RE:1.0x1.0deg_regional"
    wm["contemporaneous_vi_leakage_risk"] = "HIGH_IF_S2_USED_AS_SAME_MONTH_PREDICTOR_WITHOUT_LAG"
    wm.to_csv(FEATURES_DIR / "wilaya_monthly_panel_2016_2025.csv", index=False, encoding="utf-8")
    counts["wilaya_monthly_panel"] = len(wm)

    # 2. Wilaya Seasonal Analytical Panel (All dynamic sources aligned at DJF/MAM/JJA/SON)
    np_s = pd.read_csv(CANONICAL_DIR / "climate_observations" / "nasa_power_seasonal_canonical.csv")
    np_s = np_s[np_s["season_year"].between(2016, 2025)].copy()
    mod_s = pd.read_csv(CANONICAL_DIR / "vegetation_observations" / "modis_seasonal_wilaya_canonical.csv")
    gpm_s = pd.read_csv(CANONICAL_DIR / "precipitation_observations" / "gpm_seasonal_11km_canonical.csv")
    smap_s = pd.read_csv(CANONICAL_DIR / "soil_moisture_observations" / "smap_seasonal_11km_canonical.csv")
    s2_s = pd.read_csv(CANONICAL_DIR / "vegetation_observations" / "sentinel2_seasonal_from_monthly_canonical.csv")

    gpm_w = gpm_s.groupby(["season_year", "season"], as_index=False)["gpm_precip_mm"].agg(
        gpm_precip_cell_mean_mm="mean", gpm_precip_cell_std_mm="std"
    )
    smap_w = smap_s.groupby(["season_year", "season"], as_index=False).agg(
        smap_sm_surface_m3m3=("smap_sm_surface_m3m3", "mean"),
        smap_sm_rootzone_m3m3=("smap_sm_rootzone_m3m3", "mean"),
    )
    s2_s_sub = s2_s[
        [
            "season_year",
            "season",
            "months_included",
            "min_month_valid_pct_10m",
            "NDVI_median_of_months",
            "EVI_median_of_months",
            "NDMI_median_of_months",
            "NDRE_median_of_months",
            "completeness_status",
            "is_complete_season",
            "aggregation_basis",
        ]
    ].rename(
        columns={
            "months_included": "s2_months_included",
            "min_month_valid_pct_10m": "s2_min_month_valid_pct_10m",
            "NDVI_median_of_months": "s2_ndvi_median_of_months",
            "EVI_median_of_months": "s2_evi_median_of_months",
            "NDMI_median_of_months": "s2_ndmi_median_of_months",
            "NDRE_median_of_months": "s2_ndre_median_of_months",
            "completeness_status": "s2_completeness_status",
            "is_complete_season": "s2_is_complete_season",
            "aggregation_basis": "s2_aggregation_basis",
        }
    )

    ws = (
        np_s.merge(gpm_w, on=["season_year", "season"], how="left")
        .merge(smap_w, on=["season_year", "season"], how="left")
        .merge(mod_s, on=["season_year", "season"], how="left")
        .merge(s2_s_sub, on=["season_year", "season"], how="left")
    )
    s_rank = {s: i for i, s in enumerate(SEASON_ORDER)}
    ws["_s_ord"] = ws["season"].map(s_rank)
    ws = ws.sort_values(["season_year", "_s_ord"]).drop(columns=["_s_ord"]).reset_index(drop=True)

    # Strictly causal 1-season antecedent climate & moisture lags
    ws["np_prectot_lag1_season_mm"] = ws["PRECTOTCORR_sum_mm"].shift(1).round(4)
    ws["gpm_precip_lag1_season_mm"] = ws["gpm_precip_cell_mean_mm"].shift(1).round(4)
    ws["smap_rootzone_lag1_season_m3m3"] = ws["smap_sm_rootzone_m3m3"].shift(1).round(4)
    ws["s2_is_complete_season"] = ws["s2_is_complete_season"].astype("boolean").fillna(False)
    ws["sentinel2_pixel_composite_deferred"] = True
    ws["is_winter_2017_incomplete"] = (ws["season_year"] == 2017) & (ws["season"] == "Winter")
    ws.to_csv(FEATURES_DIR / "wilaya_seasonal_panel_2016_2025.csv", index=False, encoding="utf-8")
    counts["wilaya_seasonal_panel"] = len(ws)

    # 3. Commune Static & Multi-Year Features (n=34 Communes)
    c_static = pd.read_csv(SPATIAL_INT_DIR / "commune_static_layers.csv")
    c_sea = pd.read_csv(SPATIAL_INT_DIR / "commune_seasonal_merged.csv")
    c_sea_complete = c_sea[c_sea["is_complete_season"]].copy()
    c_clim_spring = (
        c_sea_complete[c_sea_complete["season"] == "Spring"]
        .groupby("commune_num_id", as_index=False)
        .agg(
            modis_ndvi_spring_2016_2025_mean=("modis_ndvi_mean", "mean"),
            modis_evi_spring_2016_2025_mean=("modis_evi_mean", "mean"),
            gpm_spring_precip_2016_2025_mean_mm=("gpm_precip_mm", "mean"),
            smap_spring_rootzone_2016_2025_mean=("smap_sm_rootzone_m3m3", "mean"),
            np_spring_t2m_2016_2025_mean_c=("np_t2m_mean_c", "mean"),
        )
        .round(4)
    )
    c_clim_ann = (
        c_sea_complete.groupby(["commune_num_id", "season_year"], as_index=False)["gpm_precip_mm"]
        .sum()
        .groupby("commune_num_id", as_index=False)["gpm_precip_mm"]
        .mean()
        .rename(columns={"gpm_precip_mm": "gpm_annual_2017_2025_mean_mm"})
        .round(2)
    )
    commune_feat = c_static.merge(c_clim_spring, on="commune_num_id").merge(c_clim_ann, on="commune_num_id")
    commune_feat["spatial_unit"] = "commune_gadm_polygon"
    commune_feat["macro_climate_scale_warning"] = "GPM_SMAP_POWER_AT_11_111KM_MACRO_CONTEXT_ONLY"
    commune_feat["nitrogen_scaling_flag"] = "UNVALIDATED_TRACEABILITY_ONLY"
    commune_feat.to_csv(FEATURES_DIR / "commune_static_soil_and_land_features.csv", index=False, encoding="utf-8")
    counts["commune_static_features"] = len(commune_feat)

    # 4. Commune Seasonal Panel (34 communes x 40 seasons = 1,360 rows with causal lags)
    c_sea = c_sea.sort_values(["commune_num_id", "season_year", "season"], key=lambda s: s.map({k: i for i, k in enumerate(SEASON_ORDER)}) if s.name == "season" else s).reset_index(drop=True)
    c_sea["gpm_precip_lag1_season_mm"] = c_sea.groupby("commune_num_id")["gpm_precip_mm"].shift(1).round(4)
    c_sea["smap_rootzone_lag1_season_m3m3"] = c_sea.groupby("commune_num_id")["smap_sm_rootzone_m3m3"].shift(1).round(4)
    c_sea["np_prectot_lag1_season_mm"] = c_sea.groupby("commune_num_id")["np_prectot_sum_mm"].shift(1).round(4)
    c_sea["crop_freq_usable_for_year"] = c_sea["season_year"] >= 2021
    c_sea.to_csv(FEATURES_DIR / "commune_seasonal_panel_2016_2025.csv", index=False, encoding="utf-8")
    counts["commune_seasonal_panel"] = len(c_sea)

    # 5. Landscape 250m Feature Table (59,050 valid UTM32N 250m cells: Soil + MODIS + downward-aggregated 10m/20m)
    soil_250 = pd.read_csv(CANONICAL_DIR / "soil_properties" / "soilgrids_250m_canonical.csv")
    sp_250 = pd.read_csv(SPATIAL_INT_DIR / "landscape_250m_spatial_layers.csv")
    soil_keep = [
        "grid_250m_id",
        "row_250m",
        "col_250m",
        "x_utm32n_m",
        "y_utm32n_m",
        "commune_gid_2",
        "commune_name",
        "commune_num_id",
        "clay_0_30cm",
        "sand_0_30cm",
        "silt_0_30cm",
        "ph_0_30cm",
        "soc_0_30cm",
        "cec_0_30cm",
        "clay_30_100cm",
        "ph_30_100cm",
        "soc_30_100cm",
        "cec_30_100cm",
        "nitrogen_0_30cm",
        "usda_texture_0_5cm",
        "usda_texture_0_5cm_label",
        "nitrogen_scaling_flag",
    ]
    land_250 = soil_250[soil_keep].merge(sp_250, on="grid_250m_id", how="inner")
    land_250 = land_250.rename(columns={"nitrogen_0_30cm": "soil_nitrogen_0_30cm_unvalidated"})
    land_250["spatial_unit"] = "grid_250m_epsg32632"
    land_250["crop_freq_temporal_validity"] = "2021_2025_ONLY_LOOKAHEAD_RISK_FOR_2017_2020"
    land_250["s2_snapshot_temporal_validity"] = "2024_03_SINGLE_MONTH_BASELINE_ONLY"
    land_250.to_csv(FEATURES_DIR / "landscape_250m_static_features.csv", index=False, encoding="utf-8")
    counts["landscape_250m_features"] = len(land_250)

    return counts
