"""Configuration and path discovery for the NASA POWER Guelma pipeline."""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_DIR / "data" / "NASA_POWER_REGIONAL" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "NASA_POWER_REGIONAL" / "processed"

SPATIAL_DIR = PROCESSED_DIR / "spatial"
DAILY_DIR = PROCESSED_DIR / "daily"
MONTHLY_DIR = PROCESSED_DIR / "monthly"
SEASONAL_DIR = PROCESSED_DIR / "seasonal"
ANNUAL_DIR = PROCESSED_DIR / "annual"
QUALITY_DIR = PROCESSED_DIR / "quality"
ANALYSIS_DIR = PROCESSED_DIR / "analysis"
FIGURES_DIR = ANALYSIS_DIR / "figures"
METADATA_DIR = PROCESSED_DIR / "metadata"

BOUNDARY_CANDIDATES = [
    PROJECT_DIR / "data" / "boundaries" / "processed" / "guelma_wilaya_boundary.geojson.gpkg",
    PROJECT_DIR / "data" / "boundaries" / "guelma_wilaya_boundary.gpkg",
    PROJECT_DIR / "guelma_wilaya_boundary.geojson",
]

START_YEAR = 2016
END_YEAR = 2025
YEARS = list(range(START_YEAR, END_YEAR + 1))

AREA_CRS = "EPSG:32632"
GEOGRAPHIC_CRS = "EPSG:4326"
NODATA_VALUES = {-999, -999.0, -9999, -9999.0}

VARIABLES = {
    "T2M": {
        "community": "AG",
        "source_model": "MERRA-2",
        "canonical_unit": "C",
        "expected_raw_units": {"C"},
        "nominal_lat_step": 0.5,
        "nominal_lon_step": 0.625,
        "aggregation": "mean",
        "longname": "Temperature at 2 Meters",
    },
    "T2M_MAX": {
        "community": "AG",
        "source_model": "MERRA-2",
        "canonical_unit": "C",
        "expected_raw_units": {"C"},
        "nominal_lat_step": 0.5,
        "nominal_lon_step": 0.625,
        "aggregation": "mean",
        "longname": "Maximum Temperature at 2 Meters",
    },
    "T2M_MIN": {
        "community": "AG",
        "source_model": "MERRA-2",
        "canonical_unit": "C",
        "expected_raw_units": {"C"},
        "nominal_lat_step": 0.5,
        "nominal_lon_step": 0.625,
        "aggregation": "mean",
        "longname": "Minimum Temperature at 2 Meters",
    },
    "PRECTOTCORR": {
        "community": "AG",
        "source_model": "MERRA-2",
        "canonical_unit": "mm/day",
        "expected_raw_units": {"mm/day"},
        "nominal_lat_step": 0.5,
        "nominal_lon_step": 0.625,
        "aggregation": "sum",
        "longname": "Bias-Corrected Total Precipitation",
    },
    "RH2M": {
        "community": "AG",
        "source_model": "MERRA-2 (POWER derived)",
        "canonical_unit": "%",
        "expected_raw_units": {"%"},
        "nominal_lat_step": 0.5,
        "nominal_lon_step": 0.625,
        "aggregation": "mean",
        "longname": "Relative Humidity at 2 Meters",
    },
    "ALLSKY_SFC_SW_DWN": {
        "community": "RE",
        "source_model": "CERES SYN1deg",
        "canonical_unit": "kWh/m2/day",
        "expected_raw_units": {"kW-hr/m^2/day", "kWh/m2/day"},
        "nominal_lat_step": 1.0,
        "nominal_lon_step": 1.0,
        "aggregation": "mean",
        "longname": "All Sky Surface Shortwave Downward Irradiance",
    },
}

COMMUNITY_SPECS = {
    "AG": {
        "source_model": "MERRA-2",
        "nominal_lat_step": 0.5,
        "nominal_lon_step": 0.625,
        "description": "Agroclimatology (MERRA-2 0.5° lat × 0.625° lon native grid)",
    },
    "RE": {
        "source_model": "CERES SYN1deg",
        "nominal_lat_step": 1.0,
        "nominal_lon_step": 1.0,
        "description": "Renewable Energy (CERES SYN1deg 1.0° lat × 1.0° lon native grid)",
    },
}

SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]


def resolve_boundary_file() -> Path:
    """Locate the Guelma administrative boundary file in the project."""
    for candidate in BOUNDARY_CANDIDATES:
        if candidate.exists():
            return candidate
    searched = "\n".join(f" - {path}" for path in BOUNDARY_CANDIDATES)
    raise FileNotFoundError(
        f"Could not locate Guelma boundary file. Searched:\n{searched}"
    )


def ensure_output_dirs() -> None:
    """Create all processed output directories."""
    for directory in (
        PROCESSED_DIR,
        SPATIAL_DIR,
        DAILY_DIR,
        MONTHLY_DIR,
        SEASONAL_DIR,
        ANNUAL_DIR,
        QUALITY_DIR,
        ANALYSIS_DIR,
        FIGURES_DIR,
        METADATA_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def month_to_season(month: int) -> str:
    """Map calendar month (1-12) to meteorological season."""
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Autumn"
