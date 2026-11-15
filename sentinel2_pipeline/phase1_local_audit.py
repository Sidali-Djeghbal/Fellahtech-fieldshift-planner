"""Phase 1: Audit local Guelma boundary and existing Field Shift environmental datasets."""

from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import pandas as pd
import pyproj
import rasterio
from shapely.ops import unary_union

from .config import BOUNDARY_FILE, GEOGRAPHIC_CRS, PROJECT_DIR, TARGET_CRS


def audit_local_boundary() -> Dict:
    """Verify local GeoPackage boundary CRS, geometry validity, and area."""
    if not BOUNDARY_FILE.exists():
        raise FileNotFoundError(f"Local boundary file not found: {BOUNDARY_FILE}")

    gdf = gpd.read_file(BOUNDARY_FILE)
    if gdf.empty:
        raise ValueError(f"Boundary file is empty: {BOUNDARY_FILE}")
    if gdf.crs is None:
        raise ValueError(f"Boundary file has no CRS: {BOUNDARY_FILE}")

    source_crs = str(gdf.crs)
    is_valid = bool(gdf.geometry.is_valid.all())
    gdf_wgs = gdf.to_crs(GEOGRAPHIC_CRS)
    geom_wgs = unary_union(gdf_wgs.geometry)

    geod = pyproj.Geod(ellps="WGS84")
    geod_area_km2 = abs(geod.geometry_area_perimeter(geom_wgs)[0]) / 1_000_000.0

    gdf_utm = gdf_wgs.to_crs(TARGET_CRS)
    geom_utm = unary_union(gdf_utm.geometry)
    utm_area_km2 = geom_utm.area / 1_000_000.0

    return {
        "boundary_file": str(BOUNDARY_FILE.relative_to(PROJECT_DIR)),
        "source_crs": source_crs,
        "target_crs": TARGET_CRS,
        "geometry_valid": is_valid,
        "bounds_wgs84": [round(float(x), 6) for x in geom_wgs.bounds],
        "bounds_utm32n": [round(float(x), 2) for x in geom_utm.bounds],
        "utm_area_km2": round(float(utm_area_km2), 4),
        "geodesic_area_km2": round(float(geod_area_km2), 4),
    }


def audit_existing_datasets() -> List[Dict]:
    """Inspect CRS, spatial resolution, shape, and period of existing Field Shift datasets."""
    specs = [
        (
            "Sentinel-2 (Target)",
            "COPERNICUS/S2_SR_HARMONIZED",
            "NDVI, EVI (10 m); NDMI, NDRE (20 m)",
            "2017-2025",
            None,
            "10 m / 20 m",
            "EPSG:32632",
        ),
        (
            "Crop Frequency (ESA/GEE)",
            "data/land_cover/guelma_crop_frequency_2021_2025_utm32n.tif",
            "Crop frequency",
            "2021-2025",
            PROJECT_DIR / "data/land_cover/guelma_crop_frequency_2021_2025_utm32n.tif",
            None,
            None,
        ),
        (
            "MODIS MOD13Q1",
            "data/land_cover/guelma_modis_vegetation_2016.tif",
            "NDVI, EVI (16-day / seasonal / annual)",
            "2016-2025",
            PROJECT_DIR / "data/land_cover/guelma_modis_vegetation_2016.tif",
            None,
            None,
        ),
        (
            "SoilGrids 2.0",
            "data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif",
            "Clay, Sand, Silt, pH, SOC, CEC, Nitrogen (6 depths)",
            "Static",
            PROJECT_DIR / "data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif",
            None,
            None,
        ),
        (
            "SMAP L4 Soil Moisture",
            "data/land_cover/guelma_smap_soil_moisture_2016.tif",
            "Surface & Rootzone Soil Moisture",
            "2016-2025",
            PROJECT_DIR / "data/land_cover/guelma_smap_soil_moisture_2016.tif",
            None,
            None,
        ),
        (
            "GPM IMERG Precipitation",
            "data/land_cover/guelma_gpm_annual_rainfall_2016_2025_utm32n_stack.tif",
            "Annual & Seasonal Precipitation",
            "2016-2025",
            PROJECT_DIR / "data/land_cover/guelma_gpm_annual_rainfall_2016_2025_utm32n_stack.tif",
            None,
            None,
        ),
    ]

    inventory = []
    for name, path_label, variables, period, tif_path, default_res, default_crs in specs:
        if tif_path is not None and Path(tif_path).exists():
            with rasterio.open(tif_path) as src:
                res_x, res_y = src.res
                inventory.append(
                    {
                        "dataset": name,
                        "source_file": path_label,
                        "variables": variables,
                        "period": period,
                        "crs": str(src.crs),
                        "resolution": f"{round(res_x, 2)} m x {round(res_y, 2)} m",
                        "grid_shape": f"{src.height} x {src.width} ({src.count} bands)",
                    }
                )
        else:
            inventory.append(
                {
                    "dataset": name,
                    "source_file": path_label,
                    "variables": variables,
                    "period": period,
                    "crs": default_crs or "Unknown",
                    "resolution": default_res or "Unknown",
                    "grid_shape": "N/A",
                }
            )

    # Append NASA POWER from processed spatial audit if available
    np_audit = PROJECT_DIR / "data/NASA_POWER_REGIONAL/processed/spatial/spatial_audit_report.csv"
    if np_audit.exists():
        df_np = pd.read_csv(np_audit)
        for row in df_np.itertuples(index=False):
            inventory.append(
                {
                    "dataset": f"NASA POWER ({row.community} — {row.source_model})",
                    "source_file": "data/NASA_POWER_REGIONAL/processed/",
                    "variables": "T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M" if row.community == "AG" else "ALLSKY_SFC_SW_DWN",
                    "period": "2016-2025",
                    "crs": "EPSG:4326 (area in EPSG:32632)",
                    "resolution": f"{row.nominal_resolution_deg} deg (~55-111 km)",
                    "grid_shape": f"{row.intersecting_cells} intersecting cells",
                }
            )

    return inventory
