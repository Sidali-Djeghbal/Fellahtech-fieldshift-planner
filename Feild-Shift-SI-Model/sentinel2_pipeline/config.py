"""Configuration constants and path definitions for the Sentinel-2 Guelma pipeline."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

BOUNDARY_FILE = (
    PROJECT_DIR
    / "data"
    / "boundaries"
    / "processed"
    / "guelma_wilaya_boundary.geojson.gpkg"
)

GEE_PROJECT = os.environ.get("GEE_PROJECT", "spry-framework-514800-j2")
GEE_ASSET_ID = os.environ.get(
    "GEE_ASSET_ID", f"projects/{GEE_PROJECT}/assets/guelma_wilaya_boundary"
)
S2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_PROB_ID = "COPERNICUS/S2_CLOUD_PROBABILITY"

SENTINEL2_DIR = PROJECT_DIR / "data" / "SENTINEL2"
RAW_DIR = SENTINEL2_DIR / "raw"
RAW_EXPORTS_DIR = RAW_DIR / "gee_exports"
RAW_METADATA_DIR = RAW_DIR / "gee_metadata"

PROCESSED_DIR = SENTINEL2_DIR / "processed"
MONTHLY_DIR = PROCESSED_DIR / "monthly"
MONTHLY_RASTERS_DIR = MONTHLY_DIR / "rasters"
SEASONAL_DIR = PROCESSED_DIR / "seasonal"
SEASONAL_RASTERS_DIR = SEASONAL_DIR / "rasters"
ANNUAL_DIR = PROCESSED_DIR / "annual"
ANNUAL_RASTERS_DIR = ANNUAL_DIR / "rasters"
SPATIAL_DIR = PROCESSED_DIR / "spatial"
MAPS_DIR = SPATIAL_DIR / "maps"
QUALITY_DIR = PROCESSED_DIR / "quality"
ANALYSIS_DIR = PROCESSED_DIR / "analysis"
FIGURES_DIR = ANALYSIS_DIR / "figures"
METADATA_DIR = PROCESSED_DIR / "metadata"

TARGET_CRS = "EPSG:32632"
GEOGRAPHIC_CRS = "EPSG:4326"
START_YEAR = 2017
END_YEAR = 2025
YEARS = list(range(START_YEAR, END_YEAR + 1))

REFLECTANCE_SCALE = 0.0001
CLOUD_PROB_THRESHOLD = 40
# Exclude negative surface reflectance and near-zero EVI denominators (measured D>0.10 removes extreme spikes)
EVI_DENOM_THRESHOLD = 0.10
NODATA_VALUE = -9999

# SCL classes excluded from valid surface observations
SCL_EXCLUDED_CLASSES = {
    0: "No data",
    1: "Saturated or defective",
    3: "Cloud shadows",
    8: "Cloud medium probability",
    9: "Cloud high probability",
    10: "Thin cirrus",
    11: "Snow or ice",
}
SCL_EVALUATED_RETAINED = {
    2: "Dark area pixels (retained by default to preserve topographic/moist soil signal; evaluated in QA)",
    4: "Vegetation",
    5: "Not vegetated",
    6: "Water",
    7: "Unclassified",
}

BAND_SPECS = {
    "B2": {"name": "Blue", "resolution_m": 10},
    "B3": {"name": "Green", "resolution_m": 10},
    "B4": {"name": "Red", "resolution_m": 10},
    "B5": {"name": "Red Edge 1", "resolution_m": 20},
    "B6": {"name": "Red Edge 2", "resolution_m": 20},
    "B7": {"name": "Red Edge 3", "resolution_m": 20},
    "B8": {"name": "Near Infrared (NIR)", "resolution_m": 10},
    "B8A": {"name": "Narrow NIR", "resolution_m": 20},
    "B11": {"name": "SWIR 1", "resolution_m": 20},
    "B12": {"name": "SWIR 2", "resolution_m": 20},
    "SCL": {"name": "Scene Classification Layer", "resolution_m": 20},
    "QA60": {"name": "Cloud mask bitmask", "resolution_m": 60},
}

INDEX_SPECS = {
    "NDVI": {
        "formula": "(B8 - B4) / (B8 + B4)",
        "bands": ["B8", "B4"],
        "analysis_resolution_m": 10,
        "physical_range": (-1.0, 1.0),
        "purpose": "Vegetation greenness and photosynthetic activity (not direct crop yield)",
    },
    "EVI": {
        "formula": "2.5 * (B8 - B4) / (B8 + 6*B4 - 7.5*B2 + 1)",
        "bands": ["B8", "B4", "B2"],
        "analysis_resolution_m": 10,
        "physical_range": (-1.0, 1.0),
        "purpose": "Vegetation canopy monitoring with reduced soil/atmospheric sensitivity",
    },
    "NDMI": {
        "formula": "(B8 - B11) / (B8 + B11)",
        "bands": ["B8", "B11"],
        "analysis_resolution_m": 20,
        "physical_range": (-1.0, 1.0),
        "purpose": "Vegetation moisture content indicator (B8 aggregated to 20 m; NOT direct soil moisture)",
    },
    "NDRE": {
        "formula": "(B8A - B5) / (B8A + B5)",
        "bands": ["B8A", "B5"],
        "analysis_resolution_m": 20,
        "physical_range": (-1.0, 1.0),
        "purpose": "Red-edge canopy chlorophyll/nitrogen sensitivity at native 20 m resolution",
    },
}

SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]


def ensure_directories() -> None:
    """Create the standardized data/SENTINEL2 directory tree."""
    for d in (
        SENTINEL2_DIR,
        RAW_DIR,
        RAW_EXPORTS_DIR,
        RAW_METADATA_DIR,
        PROCESSED_DIR,
        MONTHLY_DIR,
        MONTHLY_RASTERS_DIR,
        SEASONAL_DIR,
        SEASONAL_RASTERS_DIR,
        ANNUAL_DIR,
        ANNUAL_RASTERS_DIR,
        SPATIAL_DIR,
        MAPS_DIR,
        QUALITY_DIR,
        ANALYSIS_DIR,
        FIGURES_DIR,
        METADATA_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
