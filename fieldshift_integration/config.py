"""Authoritative configuration, verified source paths, and scale/leakage constants for Phase D."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Canonical Phase D Output Root (non-destructive; original raw files untouched)
INTEGRATED_DIR = DATA_DIR / "INTEGRATED"
CANONICAL_DIR = INTEGRATED_DIR / "canonical"
SPATIAL_INT_DIR = INTEGRATED_DIR / "spatial"
FEATURES_DIR = INTEGRATED_DIR / "features"
QUALITY_INT_DIR = INTEGRATED_DIR / "quality"
METADATA_INT_DIR = INTEGRATED_DIR / "metadata"
DOCS_INT_DIR = INTEGRATED_DIR / "docs"

# Authoritative Spatial Reference & Temporal Scope
TARGET_CRS = "EPSG:32632"
STUDY_START_YEAR = 2016
STUDY_END_YEAR = 2025
S2_OVERLAP_START_YEAR = 2017
S2_COMPLETE_SEASONAL_START_YEAR = 2018
SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]
NODATA_VALUE = -9999.0

# Boundaries
BOUNDARY_WILAYA_GPKG = DATA_DIR / "boundaries" / "processed" / "guelma_wilaya_boundary.geojson.gpkg"
BOUNDARY_COMMUNES_GPKG = DATA_DIR / "boundaries" / "processed" / "guelma_communes_boundaries.gpkg"

# NASA POWER (2016-2025, AG=0.5x0.625 deg, RE=1.0x1.0 deg)
NASA_POWER_DAILY_CSV = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "daily" / "nasa_power_daily_guelma.csv"
NASA_POWER_DAILY_CELLS_CSV = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "daily" / "nasa_power_daily_cell_values.csv"
NASA_POWER_MONTHLY_CSV = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "monthly" / "nasa_power_monthly_guelma.csv"
NASA_POWER_SEASONAL_CSV = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "seasonal" / "nasa_power_seasonal_guelma.csv"
NASA_POWER_ANNUAL_CSV = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "annual" / "nasa_power_annual_guelma.csv"
NASA_POWER_AG_GPKG = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "spatial" / "nasa_power_AG_intersections.gpkg"
NASA_POWER_RE_GPKG = DATA_DIR / "NASA_POWER_REGIONAL" / "processed" / "spatial" / "nasa_power_RE_intersections.gpkg"

# GPM IMERG (2016-2025, Annual 9.63 km + Seasonal on 11 km aligned stack; NO monthly on disk)
GPM_ANNUAL_STACK_TIF = DATA_DIR / "GPM" / "guelma_gpm_annual_rainfall_2016_2025_utm32n_files" / "guelma_gpm_annual_rainfall_2016_2025_utm32n_stack.tif"
GPM_ANNUAL_SUMMARY_CSV = DATA_DIR / "GPM" / "guelma_gpm_annual_rainfall_2016_2025_utm32n_files" / "guelma_gpm_annual_rainfall_summary_2016_2025.csv"

# SMAP L4 (2016-2025, Annual 11 km 20 bands + Seasonal aligned stack; NO monthly on disk)
SMAP_ANNUAL_STACK_TIF = DATA_DIR / "SMAP" / "guelma_smap_soil_moisture_2016_2025_package" / "guelma_smap_soil_moisture_2016_2025_20bands.tif"
SMAP_ANNUAL_SUMMARY_CSV = DATA_DIR / "SMAP" / "guelma_smap_soil_moisture_2016_2025_package" / "guelma_smap_soil_moisture_summary_2016_2025.csv"

# Seasonal Aligned Package (11 km x 11 km, 8x9, GPM + SMAP + downward-aggregated MODIS)
SEASONAL_ALIGNED_DIR = DATA_DIR / "seasonal" / "guelma_environmental_seasonal_aligned_2016_2025_package"
SEASONAL_ALIGNED_CSV = SEASONAL_ALIGNED_DIR / "guelma_environmental_spatiotemporal_dataset_2016_2025.csv"

# MODIS MOD13Q1 (2016-2025, Annual & Seasonal 250 m UTM32N; NO 16-day/monthly on disk)
MODIS_SEASONAL_DIR = DATA_DIR / "seasonal" / "guelma_modis_seasonal_2016_2025_analysis"
MODIS_SEASONAL_SUMMARY_CSV = MODIS_SEASONAL_DIR / "guelma_modis_seasonal_summary_2016_2025.csv"
MODIS_ANNUAL_SUMMARY_CSV = DATA_DIR / "tables" / "guelma_modis_vegetation_summary_2016_2025.csv"

# SoilGrids 2.0 (Static 250 m; NOTE: drive-download 42-band ESRI:54009 is empty/all-NaN; V6 ZIP holds valid UTM32N 42-band raster)
SOILGRIDS_RAW_ESRI_EMPTY_TIF = DATA_DIR / "SoilGrids" / "drive-download-20261114T174721Z-1-001" / "guelma_soilgrids_42bands_250m.tif"
SOILGRIDS_V6_ZIP = DATA_DIR / "SoilGrids" / "guelma_soilgrids_V6_complete_package.zip"
SOILGRIDS_V6_MERGED_MEMBER = "guelma_soilgrids_42bands_250m_V6_MERGED.tif"
SOILGRIDS_USDA_TIF = DATA_DIR / "SoilGrids" / "guelma_USDA_texture_classes_6depths_250m.tif"
SOILGRIDS_CLEAN_CSV = DATA_DIR / "SoilGrids" / "guelma_soilgrids_pixel_dataset_250m_clean.csv"
SOILGRIDS_V6_QA_CSV = DATA_DIR / "SoilGrids" / "guelma_soilgrids_V6_quality_assessment.csv"

# ESA / GEE Crop Frequency (2021-2025 static 10 m; origin offset vs Sentinel-2 10 m)
CROP_FREQ_RAW_TIF = DATA_DIR / "land_cover" / "guelma_crop_frequency_2021_2025_utm32n.tif"
CROP_FREQ_ALIGNED_10M_TIF = SPATIAL_INT_DIR / "guelma_crop_frequency_2021_2025_aligned_s2_10m.tif"

# Sentinel-2 Phase C (108 monthly summaries + 3,593 scenes; March 2024 baseline GeoTIFFs in Phase A)
S2_MONTHLY_CSV = DATA_DIR / "SENTINEL2" / "processed" / "monthly" / "sentinel2_monthly_indices_2017_2025.csv"
S2_SEASONAL_MONTHLY_DERIVED_CSV = DATA_DIR / "SENTINEL2" / "processed" / "seasonal" / "sentinel2_seasonal_from_monthly_2017_2025.csv"
S2_ANNUAL_MONTHLY_DERIVED_CSV = DATA_DIR / "SENTINEL2" / "processed" / "annual" / "sentinel2_annual_from_monthly_2017_2025.csv"
S2_SCENES_CSV = DATA_DIR / "SENTINEL2" / "raw" / "phaseC_2017_2025" / "sentinel2_scenes_2017_2025.csv"
S2_PHASEA_10M_TIF = DATA_DIR / "SENTINEL2" / "raw" / "phaseA_2024_03" / "sentinel2_2024_03_indices_10m.tif"
S2_PHASEA_20M_TIF = DATA_DIR / "SENTINEL2" / "raw" / "phaseA_2024_03" / "sentinel2_2024_03_indices_20m.tif"

# SoilGrids Horizon Depth Intervals (cm) for vertical weighting
SOIL_DEPTH_THICKNESS_CM = {
    "0-5cm": 5.0,
    "5-15cm": 10.0,
    "15-30cm": 15.0,
    "30-60cm": 30.0,
    "60-100cm": 40.0,
    "100-200cm": 100.0,
}

USDA_TEXTURE_NAMES = {
    0: "Unclassified / Missing",
    1: "Sand",
    2: "Loamy sand",
    3: "Sandy loam",
    4: "Loam",
    5: "Silt loam",
    6: "Silt",
    7: "Sandy clay loam",
    8: "Clay loam",
    9: "Silty clay loam",
    10: "Sandy clay",
    11: "Silty clay",
    12: "Clay",
}
