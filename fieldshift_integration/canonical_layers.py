"""Task 2 & 3: Canonical Data Model Builder (6 normalized layers, zero source overwrite)."""

import json
import zipfile
from typing import Dict

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy as rio_xy
from shapely.geometry import Point

from .config import (
    BOUNDARY_COMMUNES_GPKG,
    BOUNDARY_WILAYA_GPKG,
    CANONICAL_DIR,
    GPM_ANNUAL_SUMMARY_CSV,
    MODIS_ANNUAL_SUMMARY_CSV,
    MODIS_SEASONAL_SUMMARY_CSV,
    NASA_POWER_ANNUAL_CSV,
    NASA_POWER_DAILY_CSV,
    NASA_POWER_MONTHLY_CSV,
    NASA_POWER_SEASONAL_CSV,
    S2_ANNUAL_MONTHLY_DERIVED_CSV,
    S2_MONTHLY_CSV,
    S2_SCENES_CSV,
    S2_SEASONAL_MONTHLY_DERIVED_CSV,
    SEASONAL_ALIGNED_CSV,
    SMAP_ANNUAL_SUMMARY_CSV,
    SOIL_DEPTH_THICKNESS_CM,
    SOILGRIDS_USDA_TIF,
    SOILGRIDS_V6_MERGED_MEMBER,
    SOILGRIDS_V6_ZIP,
    TARGET_CRS,
    USDA_TEXTURE_NAMES,
)


def _weighted_depth_mean(df: pd.DataFrame, prop: str, depths: Dict[str, float]) -> pd.Series:
    num = np.zeros(len(df), dtype="float64")
    den = np.zeros(len(df), dtype="float64")
    for d_key, thick in depths.items():
        col = f"{prop}_{d_key.replace('-', '_')}"
        vals = df[col].to_numpy(dtype="float64")
        valid = np.isfinite(vals)
        num += np.where(valid, vals * thick, 0.0)
        den += np.where(valid, thick, 0.0)
    out = np.divide(num, den, out=np.full_like(num, np.nan), where=den > 0)
    return pd.Series(out, index=df.index)


def build_canonical_layers() -> Dict[str, int]:
    """Create the 6 normalized canonical data layers under data/INTEGRATED/canonical/."""
    dirs = {
        "spatial": CANONICAL_DIR / "spatial_reference",
        "climate": CANONICAL_DIR / "climate_observations",
        "precip": CANONICAL_DIR / "precipitation_observations",
        "soilm": CANONICAL_DIR / "soil_moisture_observations",
        "soil": CANONICAL_DIR / "soil_properties",
        "veg": CANONICAL_DIR / "vegetation_observations",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    counts: Dict[str, int] = {}

    # 1. Spatial Reference & Administrative Boundaries (EPSG:32632)
    wilaya = gpd.read_file(BOUNDARY_WILAYA_GPKG).to_crs(TARGET_CRS)
    wilaya["area_km2"] = (wilaya.geometry.area / 1e6).round(4)
    wilaya["spatial_unit_id"] = "GUELMA_WILAYA"
    wilaya.to_file(dirs["spatial"] / "guelma_wilaya_utm32n.gpkg", layer="wilaya", driver="GPKG")

    communes = gpd.read_file(BOUNDARY_COMMUNES_GPKG).to_crs(TARGET_CRS).sort_values("GID_2").reset_index(drop=True)
    communes["commune_num_id"] = np.arange(1, len(communes) + 1, dtype=np.int32)
    communes["area_km2"] = (communes.geometry.area / 1e6).round(4)
    communes["area_weight_wilaya"] = (communes["area_km2"] / communes["area_km2"].sum()).round(6)
    communes.to_file(dirs["spatial"] / "guelma_communes_utm32n.gpkg", layer="communes", driver="GPKG")
    communes.drop(columns="geometry").to_csv(dirs["spatial"] / "guelma_communes_metadata.csv", index=False, encoding="utf-8")
    counts["communes"] = len(communes)

    # 2. Climate Observations (NASA POWER Daily & Monthly Canonical)
    np_daily = pd.read_csv(NASA_POWER_DAILY_CSV)
    np_daily_wide = (
        np_daily.pivot(index=["date", "year", "month", "day", "season"], columns="variable", values="weighted_mean")
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )
    cov_ag = np_daily[np_daily["community"] == "AG"].groupby("date")["coverage_fraction"].min().rename("coverage_fraction_ag")
    cov_re = np_daily[np_daily["community"] == "RE"].groupby("date")["coverage_fraction"].min().rename("coverage_fraction_re")
    np_daily_wide = np_daily_wide.merge(cov_ag, on="date").merge(cov_re, on="date")
    np_daily_wide["spatial_support"] = "AG:0.5x0.625deg_RE:1.0x1.0deg_regional"
    np_daily_wide.to_csv(dirs["climate"] / "nasa_power_daily_canonical.csv", index=False, encoding="utf-8")
    counts["climate_daily"] = len(np_daily_wide)

    np_mo = pd.read_csv(NASA_POWER_MONTHLY_CSV).sort_values(["year", "month"]).reset_index(drop=True)
    np_mo["spatial_support"] = "AG:0.5x0.625deg_RE:1.0x1.0deg_regional"
    np_mo.to_csv(dirs["climate"] / "nasa_power_monthly_canonical.csv", index=False, encoding="utf-8")
    counts["climate_monthly"] = len(np_mo)

    np_sea = pd.read_csv(NASA_POWER_SEASONAL_CSV)
    np_sea["spatial_support"] = "AG:0.5x0.625deg_RE:1.0x1.0deg_regional"
    np_sea.to_csv(dirs["climate"] / "nasa_power_seasonal_canonical.csv", index=False, encoding="utf-8")

    np_ann = pd.read_csv(NASA_POWER_ANNUAL_CSV)
    np_ann["spatial_support"] = "AG:0.5x0.625deg_RE:1.0x1.0deg_regional"
    np_ann.to_csv(dirs["climate"] / "nasa_power_annual_canonical.csv", index=False, encoding="utf-8")

    # 3. Precipitation Observations (GPM Annual + Seasonal 11 km; monthly explicitly unavailable)
    gpm_ann = pd.read_csv(GPM_ANNUAL_SUMMARY_CSV).sort_values("year").reset_index(drop=True)
    gpm_ann["spatial_resolution_m"] = 9633.88
    gpm_ann["monthly_cadence_available_on_disk"] = False
    gpm_ann.to_csv(dirs["precip"] / "gpm_annual_wilaya_canonical.csv", index=False, encoding="utf-8")

    env_aligned = pd.read_csv(SEASONAL_ALIGNED_CSV)
    gpm_sea = env_aligned[["Year", "Season", "Cell_Row", "Cell_Col", "X_UTM32N_m", "Y_UTM32N_m", "Rainfall_mm"]].copy()
    gpm_sea = gpm_sea.rename(columns={"Year": "season_year", "Season": "season", "Rainfall_mm": "gpm_precip_mm"})
    gpm_sea["cell_id"] = gpm_sea["Cell_Row"].astype(str) + "_" + gpm_sea["Cell_Col"].astype(str)
    gpm_sea["spatial_resolution_m"] = 11000
    gpm_sea["source_native_resolution_m"] = 9633.88
    gpm_sea["monthly_cadence_available_on_disk"] = False
    gpm_sea.to_csv(dirs["precip"] / "gpm_seasonal_11km_canonical.csv", index=False, encoding="utf-8")
    counts["precip_seasonal_11km"] = len(gpm_sea)

    # 4. Soil Moisture Observations (SMAP Annual + Seasonal 11 km; monthly explicitly unavailable)
    smap_ann = pd.read_csv(SMAP_ANNUAL_SUMMARY_CSV)
    smap_ann_w = (
        smap_ann.pivot(index="year", columns="variable", values="mean_m3_m3")
        .reset_index()
        .rename(columns={"sm_surface_mean": "smap_sm_surface_m3m3", "sm_rootzone_mean": "smap_sm_rootzone_m3m3"})
        .sort_values("year")
        .reset_index(drop=True)
    )
    smap_ann_w["spatial_resolution_m"] = 11000
    smap_ann_w["monthly_cadence_available_on_disk"] = False
    smap_ann_w.to_csv(dirs["soilm"] / "smap_annual_wilaya_canonical.csv", index=False, encoding="utf-8")

    smap_sea = env_aligned[["Year", "Season", "Cell_Row", "Cell_Col", "X_UTM32N_m", "Y_UTM32N_m", "Surface_SM_m3m3", "Rootzone_SM_m3m3"]].copy()
    smap_sea = smap_sea.rename(
        columns={
            "Year": "season_year",
            "Season": "season",
            "Surface_SM_m3m3": "smap_sm_surface_m3m3",
            "Rootzone_SM_m3m3": "smap_sm_rootzone_m3m3",
        }
    )
    smap_sea["cell_id"] = smap_sea["Cell_Row"].astype(str) + "_" + smap_sea["Cell_Col"].astype(str)
    smap_sea["spatial_resolution_m"] = 11000
    smap_sea["monthly_cadence_available_on_disk"] = False
    smap_sea.to_csv(dirs["soilm"] / "smap_seasonal_11km_canonical.csv", index=False, encoding="utf-8")
    counts["soilm_seasonal_11km"] = len(smap_sea)

    # Build canonical 11 km grid reference
    grid11 = smap_sea[["cell_id", "Cell_Row", "Cell_Col", "X_UTM32N_m", "Y_UTM32N_m"]].drop_duplicates().sort_values(["Cell_Row", "Cell_Col"]).reset_index(drop=True)
    grid11.to_csv(dirs["spatial"] / "grid_11km_utm32n_master.csv", index=False, encoding="utf-8")
    counts["grid_11km_cells"] = len(grid11)

    # 5. Soil Properties (Extracted directly from valid V6_MERGED UTM32N 42-band raster + USDA Texture 250m)
    with zipfile.ZipFile(SOILGRIDS_V6_ZIP) as zf:
        v6_bytes = zf.read(SOILGRIDS_V6_MERGED_MEMBER)
    with rasterio.MemoryFile(v6_bytes) as mf, mf.open() as s_v6, rasterio.open(SOILGRIDS_USDA_TIF) as s_usda:
        assert s_v6.shape == s_usda.shape and s_v6.transform == s_usda.transform, "SoilGrids V6 & USDA grid mismatch"
        stack = s_v6.read()  # (42, H, W)
        usda_stack = s_usda.read()  # (6, H, W)
        valid_mask = np.isfinite(stack[0])  # clay_0-5cm defines the 59,050 valid UTM32N pixels
        rr, cc = np.where(valid_mask)
        xs, ys = rio_xy(s_v6.transform, rr, cc, offset="center")

        soil_dict = {
            "grid_250m_id": [f"R{int(r):03d}_C{int(c):03d}" for r, c in zip(rr, cc)],
            "row_250m": rr.astype(np.int32),
            "col_250m": cc.astype(np.int32),
            "x_utm32n_m": np.round(xs, 2),
            "y_utm32n_m": np.round(ys, 2),
        }
        for idx_b, desc in enumerate(s_v6.descriptions):
            col_clean = desc.replace("-", "_")
            soil_dict[col_clean] = np.round(stack[idx_b, rr, cc].astype("float64"), 4)
        for idx_u, desc_u in enumerate(s_usda.descriptions):
            col_u = desc_u.lower().replace("-", "_")
            soil_dict[col_u] = usda_stack[idx_u, rr, cc].astype(np.int16)

    soil_df = pd.DataFrame(soil_dict)
    # Assign primary GADM Commune to each 250m pixel center (and record outside-border pixels cleanly if center sits marginally outside)
    pts = gpd.GeoDataFrame(
        {"grid_250m_id": soil_df["grid_250m_id"]},
        geometry=[Point(x, y) for x, y in zip(soil_df["x_utm32n_m"], soil_df["y_utm32n_m"])],
        crs=TARGET_CRS,
    )
    joined_pts = gpd.sjoin(pts, communes[["GID_2", "NAME_2", "commune_num_id", "geometry"]], how="left", predicate="within")
    joined_pts = joined_pts.drop_duplicates(subset=["grid_250m_id"]).set_index("grid_250m_id")
    soil_df["commune_gid_2"] = soil_df["grid_250m_id"].map(joined_pts["GID_2"])
    soil_df["commune_name"] = soil_df["grid_250m_id"].map(joined_pts["NAME_2"])
    soil_df["commune_num_id"] = soil_df["grid_250m_id"].map(joined_pts["commune_num_id"])

    # Compute horizon thickness-weighted 0-30cm and 30-100cm aggregates (non-nitrogen validated properties)
    d_0_30 = {k: SOIL_DEPTH_THICKNESS_CM[k] for k in ["0-5cm", "5-15cm", "15-30cm"]}
    d_30_100 = {k: SOIL_DEPTH_THICKNESS_CM[k] for k in ["30-60cm", "60-100cm"]}
    for prop in ["clay", "sand", "silt", "ph", "soc", "cec", "nitrogen"]:
        soil_df[f"{prop}_0_30cm"] = _weighted_depth_mean(soil_df, prop, d_0_30).round(4)
        soil_df[f"{prop}_30_100cm"] = _weighted_depth_mean(soil_df, prop, d_30_100).round(4)

    soil_df["usda_texture_0_5cm_label"] = soil_df["usda_texture_0_5cm"].map(USDA_TEXTURE_NAMES)
    soil_df["nitrogen_scaling_flag"] = "UNVALIDATED_TRACEABILITY_ONLY_DO_NOT_USE_IN_SCORING"
    soil_df["source_note"] = "Extracted from guelma_soilgrids_42bands_250m_V6_MERGED.tif (EPSG:32632); modelled estimates"
    soil_df.to_csv(dirs["soil"] / "soilgrids_250m_canonical.csv", index=False, encoding="utf-8")
    counts["soilgrids_250m_pixels"] = len(soil_df)

    # Save 250m master grid index
    soil_df[["grid_250m_id", "row_250m", "col_250m", "x_utm32n_m", "y_utm32n_m", "commune_gid_2", "commune_name", "commune_num_id"]].to_csv(
        dirs["spatial"] / "grid_250m_utm32n_master.csv", index=False, encoding="utf-8"
    )

    # 6. Vegetation Observations (Sentinel-2 Monthly + MODIS Seasonal/Annual + S2 Scenes + Exploratory Monthly-Derived Flags)
    s2_m = pd.read_csv(S2_MONTHLY_CSV).sort_values("year_month").reset_index(drop=True)
    if ".geo" in s2_m.columns:
        s2_m = s2_m.drop(columns=[".geo"])
    s2_m["is_model_eligible_monthly"] = (s2_m["completeness_status"] == "COMPLETE") & (s2_m["NDVI_valid_pct"] >= 90.0)
    s2_m["resolution_ndvi_evi_m"] = 10
    s2_m["resolution_ndmi_ndre_m"] = 20
    s2_m["is_proxy_only_no_species_or_yield"] = True
    s2_m.to_csv(dirs["veg"] / "sentinel2_monthly_wilaya_canonical.csv", index=False, encoding="utf-8")
    counts["s2_monthly_rows"] = len(s2_m)

    s2_s = pd.read_csv(S2_SEASONAL_MONTHLY_DERIVED_CSV)
    s2_s["is_pixel_composite"] = False
    s2_s["is_complete_season"] = s2_s["completeness_status"] == "COMPLETE_MONTHLY_SET"
    s2_s.to_csv(dirs["veg"] / "sentinel2_seasonal_from_monthly_canonical.csv", index=False, encoding="utf-8")

    s2_a = pd.read_csv(S2_ANNUAL_MONTHLY_DERIVED_CSV)
    s2_a["is_pixel_composite"] = False
    s2_a["is_complete_year"] = s2_a["completeness_status"] == "COMPLETE_12_MONTHS"
    s2_a.to_csv(dirs["veg"] / "sentinel2_annual_from_monthly_canonical.csv", index=False, encoding="utf-8")

    s2_sc = pd.read_csv(S2_SCENES_CSV)
    s2_sc.to_csv(dirs["veg"] / "sentinel2_scenes_canonical.csv", index=False, encoding="utf-8")

    mod_s = pd.read_csv(MODIS_SEASONAL_SUMMARY_CSV)
    mod_s_w = (
        mod_s.pivot(index=["year", "season"], columns="variable", values="spatial_mean")
        .reset_index()
        .rename(columns={"NDVI": "modis_ndvi_mean", "EVI": "modis_evi_mean", "valid_obs_count": "modis_valid_obs_mean"})
    )
    mod_s_med = mod_s.pivot(index=["year", "season"], columns="variable", values="spatial_median").reset_index().rename(
        columns={"NDVI": "modis_ndvi_median", "EVI": "modis_evi_median"}
    )[["year", "season", "modis_ndvi_median", "modis_evi_median"]]
    mod_s_w = mod_s_w.merge(mod_s_med, on=["year", "season"]).rename(columns={"year": "season_year"})
    mod_s_w["spatial_resolution_m"] = 250
    mod_s_w.to_csv(dirs["veg"] / "modis_seasonal_wilaya_canonical.csv", index=False, encoding="utf-8")
    counts["modis_seasonal_wilaya"] = len(mod_s_w)

    mod_a = pd.read_csv(MODIS_ANNUAL_SUMMARY_CSV)
    mod_a_w = mod_a.pivot(index="year", columns="band", values="mean").reset_index().rename(
        columns={"NDVI_mean": "modis_ndvi_mean", "EVI_mean": "modis_evi_mean", "valid_obs_count": "modis_valid_obs_mean"}
    )
    mod_a_w["spatial_resolution_m"] = 250
    mod_a_w.to_csv(dirs["veg"] / "modis_annual_wilaya_canonical.csv", index=False, encoding="utf-8")

    return counts
