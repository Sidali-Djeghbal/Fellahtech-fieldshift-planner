"""Automatic multi-scale geospatial extraction from local Field Shift datasets.

Given a validated farmer-drawn polygon, extracts available features locally from:
- GADM 4.1 Guelma Wilaya & 34 Communes
- SoilGrids V6 (250 m, 0-30 cm and 30-100 cm; Nitrogen strictly excluded from scoring)
- ESA Crop Frequency (10 m aligned to Sentinel-2 grid, 2021-2025 only)
- Sentinel-2 (2024-03 10 m / 20 m local snapshot + Wilaya 2017-2025 monthly summary)
- MODIS MOD13Q1 (250 m seasonal 2016-2025)
- GPM IMERG & SMAP L4 (11 km seasonal/annual 2016-2025)
- NASA POWER (AG ~55-69 km / RE ~111 km daily/seasonal 2016-2025)
- DEM (explicitly reports UNAVAILABLE_NOT_INTEGRATED when no local DEM exists)

Zero Google Earth Engine tasks are submitted and missing data are never fabricated.
"""

from __future__ import annotations

import math
import zipfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import Polygon, box, shape
from shapely.prepared import prep

from fieldshift_integration.config import (
    CANONICAL_DIR,
    CROP_FREQ_ALIGNED_10M_TIF,
    CROP_FREQ_RAW_TIF,
    DATA_DIR,
    FEATURES_DIR,
    MODIS_SEASONAL_DIR,
    NASA_POWER_AG_GPKG,
    NASA_POWER_DAILY_CELLS_CSV,
    NASA_POWER_RE_GPKG,
    NODATA_VALUE,
    S2_PHASEA_10M_TIF,
    S2_PHASEA_20M_TIF,
    SOIL_DEPTH_THICKNESS_CM,
    SOILGRIDS_USDA_TIF,
    SOILGRIDS_V6_MERGED_MEMBER,
    SOILGRIDS_V6_ZIP,
    TARGET_CRS,
    USDA_TEXTURE_NAMES,
)

WILAYA_GPKG = CANONICAL_DIR / "spatial_reference" / "guelma_wilaya_utm32n.gpkg"
COMMUNES_GPKG = CANONICAL_DIR / "spatial_reference" / "guelma_communes_utm32n.gpkg"
PROCESSED_WILAYA_GPKG = DATA_DIR / "boundaries" / "processed" / "guelma_wilaya_boundary.geojson.gpkg"
PROCESSED_COMMUNES_GPKG = DATA_DIR / "boundaries" / "processed" / "guelma_communes_boundaries.gpkg"
INTEGRATED_DB_ZIP = DATA_DIR / "tables" / "dataset" / "guelma_integrated_agricultural_database_v1.zip"
S2_PHASEA_VALID_10M_TIF = DATA_DIR / "SENTINEL2" / "raw" / "phaseA_2024_03" / "sentinel2_2024_03_valid_obs_10m.tif"
S2_PHASEA_VALID_20M_TIF = DATA_DIR / "SENTINEL2" / "raw" / "phaseA_2024_03" / "sentinel2_2024_03_valid_obs_20m.tif"
GPM_SEASONAL_CSV = CANONICAL_DIR / "precipitation_observations" / "gpm_seasonal_11km_canonical.csv"
SMAP_SEASONAL_CSV = CANONICAL_DIR / "soil_moisture_observations" / "smap_seasonal_11km_canonical.csv"
GRID_11KM_CSV = CANONICAL_DIR / "spatial_reference" / "grid_11km_utm32n_master.csv"
WILAYA_MONTHLY_CSV = FEATURES_DIR / "wilaya_monthly_panel_2016_2025.csv"
_DEFAULT_SOILGRIDS_V6_ZIP = SOILGRIDS_V6_ZIP
_DEFAULT_SOILGRIDS_USDA_TIF = SOILGRIDS_USDA_TIF
_DEFAULT_MODIS_SEASONAL_DIR = MODIS_SEASONAL_DIR
_DEFAULT_GPM_SEASONAL_CSV = GPM_SEASONAL_CSV
_DEFAULT_SMAP_SEASONAL_CSV = SMAP_SEASONAL_CSV
_DEFAULT_GRID_11KM_CSV = GRID_11KM_CSV
_DEFAULT_NASA_POWER_DAILY_CELLS_CSV = NASA_POWER_DAILY_CELLS_CSV
_DEFAULT_WILAYA_MONTHLY_CSV = WILAYA_MONTHLY_CSV
MODIS_YEARS = list(range(2016, 2026))
SEASONS = ("Winter", "Spring", "Summer", "Autumn")

_REGIONAL_NASA_POWER_CLIMATOLOGY: Dict[str, Tuple[Any, Dict[str, float]]] = {
    "T2M": (17.91, {"winter": 9.56, "spring": 15.35, "summer": 27.3, "autumn": 19.24}),
    "T2M_MAX": (25.17, {"winter": 15.67, "spring": 22.5, "summer": 35.88, "autumn": 26.38}),
    "T2M_MIN": (12.19, {"winter": 5.1, "spring": 9.39, "summer": 20.06, "autumn": 14.05}),
    "RH2M": (64.9, {"winter": 77.08, "spring": 68.93, "summer": 48.71, "autumn": 65.23}),
    "PRECTOTCORR": (736.84, {"winter": 258.45, "spring": 220.69, "summer": 50.57, "autumn": 215.33}),
    "ALLSKY_SFC_SW_DWN": (4.83, {"winter": 2.71, "spring": 5.48, "summer": 7.2, "autumn": 3.9}),
}


@dataclass
class ExtractedMetric:
    """Standardized geospatial extraction record with full scientific provenance."""

    value: Optional[Any]
    unit: str
    source_dataset: str
    spatial_resolution: str
    temporal_coverage: str
    valid_pixel_count: int
    polygon_coverage_pct: float
    aggregation_method: str
    quality_status: str
    uncertainty_or_limitations: str
    stats: Optional[Dict[str, Optional[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metric preserving explicit nulls and provenance fields."""
        return asdict(self)


def _metric_unavailable(
    unit: str,
    source_dataset: str,
    spatial_resolution: str,
    temporal_coverage: str,
    aggregation_method: str,
    limitation: str,
    quality_status: str = "UNAVAILABLE_NOT_INTEGRATED",
) -> Dict[str, Any]:
    return ExtractedMetric(
        value=None,
        unit=unit,
        source_dataset=source_dataset,
        spatial_resolution=spatial_resolution,
        temporal_coverage=temporal_coverage,
        valid_pixel_count=0,
        polygon_coverage_pct=0.0,
        aggregation_method=aggregation_method,
        quality_status=quality_status,
        uncertainty_or_limitations=limitation,
        stats=None,
    ).to_dict()


@lru_cache(maxsize=1)
def _load_boundaries() -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    if WILAYA_GPKG.is_file() and COMMUNES_GPKG.is_file():
        return gpd.read_file(WILAYA_GPKG), gpd.read_file(COMMUNES_GPKG)
    wilaya_gdf = gpd.read_file(PROCESSED_WILAYA_GPKG).to_crs(TARGET_CRS)
    communes_gdf = gpd.read_file(PROCESSED_COMMUNES_GPKG).to_crs(TARGET_CRS)
    if "commune_num_id" not in communes_gdf.columns:
        if "CC_2" in communes_gdf.columns:
            communes_gdf["commune_num_id"] = pd.to_numeric(communes_gdf["CC_2"], errors="coerce").fillna(0).astype(int)
        else:
            communes_gdf["commune_num_id"] = list(range(1, len(communes_gdf) + 1))
    return wilaya_gdf, communes_gdf


@lru_cache(maxsize=1)
def _load_integrated_zip_tables() -> Optional[Dict[str, Any]]:
    if not INTEGRATED_DB_ZIP.is_file():
        return None
    with zipfile.ZipFile(INTEGRATED_DB_ZIP) as zf:
        soil_df = pd.read_csv(zf.open("guelma_soil_static_250m.csv"))
        cm_df = pd.read_csv(zf.open("guelma_climate_moisture_seasonal_native_grid_2016_2025.csv"))
        veg_df = pd.read_csv(
            zf.open("guelma_vegetation_seasonal_250m_2016_2025.csv"),
            usecols=["grid_id", "year", "season", "NDVI", "EVI"],
        )
    veg_df["year"] = veg_df["year"].astype("int16")
    veg_df["NDVI"] = veg_df["NDVI"].astype("float32")
    veg_df["EVI"] = veg_df["EVI"].astype("float32")

    cm_df = cm_df.copy()
    cm_df["cell_id"] = [f"C_{int(r.X_UTM32N_m)}_{int(r.Y_UTM32N_m)}" for r in cm_df.itertuples()]
    unique_cells = cm_df[["cell_id", "X_UTM32N_m", "Y_UTM32N_m"]].drop_duplicates().copy()
    half = 5500.0
    g11_geoms = [
        box(r.X_UTM32N_m - half, r.Y_UTM32N_m - half, r.X_UTM32N_m + half, r.Y_UTM32N_m + half)
        for r in unique_cells.itertuples()
    ]
    g11_gdf = gpd.GeoDataFrame(unique_cells, geometry=g11_geoms, crs=TARGET_CRS)

    gpm_sea = pd.DataFrame(
        {
            "cell_id": cm_df["cell_id"],
            "season_year": cm_df["Year"],
            "season": cm_df["Season"],
            "gpm_precip_mm": cm_df["Rainfall_mm"],
        }
    )
    smap_sea = pd.DataFrame(
        {
            "cell_id": cm_df["cell_id"],
            "season_year": cm_df["Year"],
            "season": cm_df["Season"],
            "smap_sm_rootzone_m3m3": cm_df["Rootzone_SM_m3m3"],
            "smap_sm_surface_m3m3": cm_df["Surface_SM_m3m3"],
        }
    )
    return {
        "soil_df": soil_df,
        "cm_df": cm_df,
        "veg_df": veg_df,
        "grid_11km": g11_gdf,
        "gpm_sea": gpm_sea,
        "smap_sea": smap_sea,
    }


@lru_cache(maxsize=1)
def _load_coarse_tables() -> Dict[str, Any]:
    g11_gdf = None
    if GRID_11KM_CSV.exists():
        g11 = pd.read_csv(GRID_11KM_CSV)
        half = 5500.0
        g11_geoms = [box(r.X_UTM32N_m - half, r.Y_UTM32N_m - half, r.X_UTM32N_m + half, r.Y_UTM32N_m + half) for r in g11.itertuples()]
        g11_gdf = gpd.GeoDataFrame(g11, geometry=g11_geoms, crs=TARGET_CRS)

    ag_gdf = gpd.read_file(NASA_POWER_AG_GPKG, layer="intersections").to_crs(TARGET_CRS) if NASA_POWER_AG_GPKG.exists() else None
    re_gdf = gpd.read_file(NASA_POWER_RE_GPKG, layer="intersections").to_crs(TARGET_CRS) if NASA_POWER_RE_GPKG.exists() else None
    gpm_sea = pd.read_csv(GPM_SEASONAL_CSV) if GPM_SEASONAL_CSV.exists() else None
    smap_sea = pd.read_csv(SMAP_SEASONAL_CSV) if SMAP_SEASONAL_CSV.exists() else None

    if (
        g11_gdf is None
        and gpm_sea is None
        and smap_sea is None
        and GRID_11KM_CSV == _DEFAULT_GRID_11KM_CSV
        and GPM_SEASONAL_CSV == _DEFAULT_GPM_SEASONAL_CSV
        and SMAP_SEASONAL_CSV == _DEFAULT_SMAP_SEASONAL_CSV
    ):
        zt = _load_integrated_zip_tables()
        if zt is not None:
            g11_gdf = zt["grid_11km"]
            gpm_sea = zt["gpm_sea"]
            smap_sea = zt["smap_sea"]

    return {
        "grid_11km": g11_gdf,
        "gpm_sea": gpm_sea,
        "smap_sea": smap_sea,
        "ag_gdf": ag_gdf,
        "re_gdf": re_gdf,
        "np_cells": pd.read_csv(NASA_POWER_DAILY_CELLS_CSV) if NASA_POWER_DAILY_CELLS_CSV.exists() else None,
        "wilaya_monthly": pd.read_csv(WILAYA_MONTHLY_CSV) if WILAYA_MONTHLY_CSV.exists() else None,
    }


def validate_and_project_polygon(geometry: Dict[str, Any], geometry_crs: str = "EPSG:4326") -> Dict[str, Any]:
    """Validate farmer GeoJSON Polygon strictly (no self-intersections/MultiPolygons), project to EPSG:32632, and check Guelma bounds."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ValueError("Field geometry must be a valid GeoJSON Polygon object.")
    raw_geom = shape(geometry)
    if raw_geom.geom_type != "Polygon" or raw_geom.is_empty:
        raise ValueError("Field geometry must resolve to a non-empty single Polygon.")
    if not raw_geom.is_valid:
        raise ValueError("Field geometry is invalid (self-intersection, bowtie, or unclosed ring detected); please redraw a simple single Polygon.")

    coords = list(raw_geom.exterior.coords)
    if any(not (math.isfinite(c[0]) and math.isfinite(c[1])) for c in coords):
        raise ValueError("Field geometry contains non-finite coordinates.")

    src_crs = pyproj.CRS.from_user_input(geometry_crs)
    dst_crs = pyproj.CRS.from_user_input(TARGET_CRS)
    geom_utm = gpd.GeoSeries([raw_geom], crs=src_crs).to_crs(dst_crs).iloc[0]
    if geom_utm.geom_type != "Polygon" or geom_utm.is_empty or not geom_utm.is_valid:
        raise ValueError("Projected field geometry in EPSG:32632 is invalid or non-simple.")
    geom_wgs = gpd.GeoSeries([geom_utm], crs=dst_crs).to_crs("EPSG:4326").iloc[0]
    area_m2 = float(geom_utm.area)
    if area_m2 <= 0.0:
        raise ValueError("Field polygon has zero geometric area after projection.")

    wilaya_gdf, communes_gdf = _load_boundaries()
    wilaya_geom = wilaya_gdf.geometry.iloc[0]
    wilaya_overlap_area = float(geom_utm.intersection(wilaya_geom).area)
    wilaya_overlap_pct = round(100.0 * wilaya_overlap_area / area_m2, 4)

    warnings: List[str] = []
    if wilaya_overlap_pct == 0.0:
        raise ValueError("Field polygon lies completely outside Guelma Wilaya (EPSG:32632 boundary overlap = 0%).")
    if wilaya_overlap_pct < 99.0:
        warnings.append(f"Field polygon extends slightly outside Guelma boundary ({wilaya_overlap_pct:.2f}% inside).")
    if area_m2 < 500.0:
        warnings.append("Field area < 0.05 ha; 10 m pixels provide limited spatial sample.")

    commune_overlaps: List[Dict[str, Any]] = []
    for row in communes_gdf.itertuples():
        inter = float(geom_utm.intersection(row.geometry).area)
        if inter > 0.0:
            commune_overlaps.append({
                "commune_num_id": int(row.commune_num_id),
                "gid_2": str(row.GID_2),
                "name_2": str(row.NAME_2),
                "overlap_pct": round(100.0 * inter / area_m2, 3),
            })
    commune_overlaps.sort(key=lambda d: d["overlap_pct"], reverse=True)
    primary_commune = commune_overlaps[0] if commune_overlaps else None

    return {
        "geom_utm": geom_utm,
        "geom_wgs84": geom_wgs,
        "area_m2": round(area_m2, 2),
        "area_ha": round(area_m2 / 10000.0, 4),
        "perimeter_m": round(float(geom_utm.length), 2),
        "centroid_lon_lat": [round(float(geom_wgs.centroid.x), 6), round(float(geom_wgs.centroid.y), 6)],
        "centroid_utm32n_xy": [round(float(geom_utm.centroid.x), 2), round(float(geom_utm.centroid.y), 2)],
        "wilaya_overlap_pct": wilaya_overlap_pct,
        "primary_commune": primary_commune,
        "commune_overlaps": commune_overlaps,
        "validation_warnings": warnings,
    }


def _compute_window_area_weights(
    ds: rasterio.DatasetReader,
    geom_utm: Polygon,
) -> Optional[Tuple[rasterio.windows.Window, np.ndarray]]:
    """Compute exact polygon-pixel intersection area grid using prepared interior fast path."""
    minx, miny, maxx, maxy = geom_utm.bounds
    win = from_bounds(minx, miny, maxx, maxy, transform=ds.transform)
    row_off = max(0, int(math.floor(win.row_off)))
    col_off = max(0, int(math.floor(win.col_off)))
    row_stop = min(ds.height, int(math.ceil(win.row_off + win.height)))
    col_stop = min(ds.width, int(math.ceil(win.col_off + win.width)))
    if row_stop <= row_off or col_stop <= col_off:
        return None

    rw = rasterio.windows.Window(col_off, row_off, col_stop - col_off, row_stop - row_off)
    w_tf = ds.window_transform(rw)
    px_area = abs(float(w_tf.a) * float(w_tf.e))
    prep_geom = prep(geom_utm)

    area_weights = np.zeros((rw.height, rw.width), dtype="float64")
    for r in range(rw.height):
        y_top = w_tf.f + r * w_tf.e
        y_bot = w_tf.f + (r + 1) * w_tf.e
        ymin, ymax = min(y_bot, y_top), max(y_bot, y_top)
        for c in range(rw.width):
            x_left = w_tf.c + c * w_tf.a
            x_right = w_tf.c + (c + 1) * w_tf.a
            xmin, xmax = min(x_left, x_right), max(x_left, x_right)
            px = box(xmin, ymin, xmax, ymax)
            if not prep_geom.intersects(px):
                continue
            if prep_geom.contains_properly(px):
                area_weights[r, c] = px_area
            else:
                inter = geom_utm.intersection(px).area
                if inter > 0.0:
                    area_weights[r, c] = inter
    return rw, area_weights


def _extract_weighted_raster_window(
    ds: rasterio.DatasetReader,
    geom_utm: Polygon,
    band_indices: Sequence[int],
    extra_valid_mask_band: Optional[np.ndarray] = None,
    nodata_override: Optional[float] = None,
    treat_zero_as_valid: bool = True,
    precomputed_weights: Optional[Tuple[rasterio.windows.Window, np.ndarray]] = None,
) -> Dict[int, Dict[str, Any]]:
    """Compute exact polygon-pixel intersection weighted statistics for selected bands inside a window."""
    grid = precomputed_weights if precomputed_weights is not None else _compute_window_area_weights(ds, geom_utm)
    if grid is None:
        return {b: {"count": 0, "cov_pct": 0.0, "w_mean": None, "stats": None, "values": np.array([]), "weights": np.array([])} for b in band_indices}

    rw, area_weights = grid
    poly_area = float(geom_utm.area)

    touched = area_weights > 0.0
    nd_val = nodata_override if nodata_override is not None else ds.nodata
    results: Dict[int, Dict[str, Any]] = {}

    for b in band_indices:
        arr = ds.read(b, window=rw).astype("float64")
        valid = touched & np.isfinite(arr)
        if nd_val is not None and not np.isnan(nd_val):
            valid &= arr != float(nd_val)
        if not treat_zero_as_valid:
            valid &= arr > 0.0
        if extra_valid_mask_band is not None:
            valid &= extra_valid_mask_band

        v_cnt = int(valid.sum())
        if v_cnt == 0 or poly_area <= 0.0:
            results[b] = {"count": 0, "cov_pct": 0.0, "w_mean": None, "stats": None, "values": np.array([]), "weights": np.array([])}
            continue

        vals = arr[valid]
        wts = area_weights[valid]
        w_sum = float(wts.sum())
        cov_pct = round(min(100.0, 100.0 * w_sum / poly_area), 2)
        w_mean = float(np.sum(vals * wts) / w_sum)
        mean_v = float(np.mean(vals))
        std_v = float(np.std(vals))
        results[b] = {
            "count": v_cnt,
            "cov_pct": cov_pct,
            "w_mean": round(w_mean, 4),
            "values": vals,
            "weights": wts,
            "stats": {
                "area_weighted_mean": round(w_mean, 4),
                "pixel_mean": round(mean_v, 4),
                "std": round(std_v, 4),
                "min": round(float(np.min(vals)), 4),
                "p25": round(float(np.percentile(vals, 25)), 4),
                "p50": round(float(np.percentile(vals, 50)), 4),
                "p75": round(float(np.percentile(vals, 75)), 4),
                "max": round(float(np.max(vals)), 4),
            },
        }
    return results


def _depth_weighted_soil_profile(
    ds: rasterio.DatasetReader,
    band_map: Dict[str, int],
    geom_utm: Polygon,
    prop: str,
    depths_cm: Dict[str, float],
    precomputed_weights: Optional[Tuple[rasterio.windows.Window, np.ndarray]] = None,
) -> Dict[str, Any]:
    """Compute thickness-weighted SoilGrids layer average preserving exact polygon weighting."""
    bands = [band_map[f"{prop}_{d}"] for d in depths_cm]
    ext = _extract_weighted_raster_window(ds, geom_utm, bands, precomputed_weights=precomputed_weights)
    num, den = 0.0, 0.0
    counts, covs = [], []
    for b, thick in zip(bands, depths_cm.values()):
        res = ext[b]
        if res["w_mean"] is not None:
            num += res["w_mean"] * thick
            den += thick
            counts.append(res["count"])
            covs.append(res["cov_pct"])
    if den <= 0.0:
        return {"w_mean": None, "count": 0, "cov_pct": 0.0}
    return {"w_mean": round(num / den, 4), "count": max(counts), "cov_pct": min(covs)}


def _intersect_soil_250m_cells(geom_utm: Polygon, soil_df: pd.DataFrame) -> pd.DataFrame:
    minx, miny, maxx, maxy = geom_utm.bounds
    cand = soil_df[
        (soil_df["x_utm32_m"] >= minx - 125.0)
        & (soil_df["x_utm32_m"] <= maxx + 125.0)
        & (soil_df["y_utm32_m"] >= miny - 125.0)
        & (soil_df["y_utm32_m"] <= maxy + 125.0)
    ]
    if len(cand) == 0:
        return cand.iloc[0:0].copy()
    areas: List[float] = []
    for x, y in zip(cand["x_utm32_m"], cand["y_utm32_m"]):
        px = box(float(x) - 125.0, float(y) - 125.0, float(x) + 125.0, float(y) + 125.0)
        areas.append(float(geom_utm.intersection(px).area))
    hits = cand.copy()
    hits["_w"] = areas
    return hits[hits["_w"] > 0.0]


def _extract_soilgrids(geom_utm: Polygon) -> Dict[str, Any]:
    src = f"{SOILGRIDS_V6_ZIP.name}::{SOILGRIDS_V6_MERGED_MEMBER}"
    top_depths = {k: v for k, v in SOIL_DEPTH_THICKNESS_CM.items() if k in ("0-5cm", "5-15cm", "15-30cm")}
    sub_depths = {k: v for k, v in SOIL_DEPTH_THICKNESS_CM.items() if k in ("30-60cm", "60-100cm")}
    units = {"clay": "%", "sand": "%", "silt": "%", "ph": "pH (H2O)", "soc": "g/kg", "cec": "cmol(c)/kg"}

    out: Dict[str, Any] = {}
    used_zip_table = False
    zip_hits: Optional[pd.DataFrame] = None
    poly_area = float(geom_utm.area)

    if SOILGRIDS_V6_ZIP.exists():
        with zipfile.ZipFile(SOILGRIDS_V6_ZIP) as zf:
            with rasterio.MemoryFile(zf.read(SOILGRIDS_V6_MERGED_MEMBER)) as mf:
                with mf.open() as ds:
                    bmap = {name: i + 1 for i, name in enumerate(ds.descriptions)}
                    sg_weights = _compute_window_area_weights(ds, geom_utm)
                    for horizon, depths in (("0_30cm", top_depths), ("30_100cm", sub_depths)):
                        for prop, unit in units.items():
                            res = _depth_weighted_soil_profile(ds, bmap, geom_utm, prop, depths, precomputed_weights=sg_weights)
                            out[f"{prop}_{horizon}"] = ExtractedMetric(
                                value=res["w_mean"],
                                unit=unit,
                                source_dataset=src,
                                spatial_resolution="250 m (6.25 ha pixels)",
                                temporal_coverage="Static SoilGrids 2.0 V6",
                                valid_pixel_count=res["count"],
                                polygon_coverage_pct=res["cov_pct"],
                                aggregation_method=f"polygon_pixel_intersection_area_weighted + depth_thickness_weighted ({horizon})",
                                quality_status="MODELED_SPATIAL_ESTIMATE" if res["w_mean"] is not None else "UNAVAILABLE_MASKED_PIXEL",
                                uncertainty_or_limitations=(
                                    "Global 250 m SoilGrids digital soil mapping estimate, NOT a field soil laboratory sample; "
                                    "masked urban/water or NaN SOC pixels yield null."
                                ),
                            ).to_dict()
    elif SOILGRIDS_V6_ZIP == _DEFAULT_SOILGRIDS_V6_ZIP and (zt := _load_integrated_zip_tables()) is not None:
        used_zip_table = True
        zip_src = f"{INTEGRATED_DB_ZIP.name}::guelma_soil_static_250m.csv"
        zip_hits = _intersect_soil_250m_cells(geom_utm, zt["soil_df"])
        cnt = int(len(zip_hits))
        cov_pct = round(min(100.0, 100.0 * float(zip_hits["_w"].sum()) / poly_area), 2) if (cnt > 0 and poly_area > 0) else 0.0
        for horizon, depths in (("0_30cm", top_depths), ("30_100cm", sub_depths)):
            for prop, unit in units.items():
                if cnt == 0:
                    val = None
                    q_status = "UNAVAILABLE_MASKED_PIXEL"
                else:
                    w_arr = zip_hits["_w"].to_numpy(dtype=float)
                    depth_num = np.zeros(cnt, dtype=float)
                    depth_den = np.zeros(cnt, dtype=float)
                    for d_label, thick in depths.items():
                        col = f"{prop}_{d_label.replace('-', '_')}"
                        if col in zip_hits.columns:
                            vals = pd.to_numeric(zip_hits[col], errors="coerce").to_numpy(dtype=float)
                            valid = np.isfinite(vals)
                            depth_num[valid] += vals[valid] * float(thick)
                            depth_den[valid] += float(thick)
                    valid_px = depth_den > 0.0
                    if valid_px.any():
                        px_means = depth_num[valid_px] / depth_den[valid_px]
                        px_w = w_arr[valid_px]
                        val = round(float(np.sum(px_means * px_w) / np.sum(px_w)), 4)
                        q_status = "MODELED_SPATIAL_ESTIMATE"
                    else:
                        val = None
                        q_status = "UNAVAILABLE_MASKED_PIXEL"
                out[f"{prop}_{horizon}"] = ExtractedMetric(
                    value=val,
                    unit=unit,
                    source_dataset=zip_src,
                    spatial_resolution="250 m (6.25 ha pixels)",
                    temporal_coverage="Static SoilGrids 2.0 V6",
                    valid_pixel_count=cnt if val is not None else 0,
                    polygon_coverage_pct=cov_pct if val is not None else 0.0,
                    aggregation_method=f"polygon_pixel_intersection_area_weighted + depth_thickness_weighted ({horizon})",
                    quality_status=q_status,
                    uncertainty_or_limitations=(
                        "Global 250 m SoilGrids digital soil mapping estimate, NOT a field soil laboratory sample; "
                        "masked urban/water pixels are excluded."
                    ),
                ).to_dict()
    else:
        for horizon in ("0_30cm", "30_100cm"):
            for prop, unit in units.items():
                out[f"{prop}_{horizon}"] = _metric_unavailable(
                    unit, src, "250 m (6.25 ha pixels)", "Static SoilGrids 2.0 V6",
                    f"polygon_pixel_intersection_area_weighted + depth_thickness_weighted ({horizon})",
                    "SoilGrids V6 archive absent locally.",
                )

    # Explicitly quarantine SoilGrids Nitrogen per Phase D QA audit
    out["nitrogen_0_30cm"] = _metric_unavailable(
        unit="unvalidated",
        source_dataset=src,
        spatial_resolution="250 m",
        temporal_coverage="Static",
        aggregation_method="EXCLUDED_PER_PHASE_D_AUDIT",
        limitation="UNVALIDATED_TRACEABILITY_ONLY: SoilGrids Nitrogen exhibits N > SOC subsoil anomaly; excluded from modeling.",
        quality_status="UNVALIDATED_EXCLUDED",
    )

    if SOILGRIDS_USDA_TIF.exists():
        with rasterio.open(SOILGRIDS_USDA_TIF) as uds:
            ures = _extract_weighted_raster_window(uds, geom_utm, [1], nodata_override=0.0, treat_zero_as_valid=False)[1]
            if ures["count"] > 0:
                vals = ures["values"].astype(int)
                wts = ures["weights"]
                class_weights: Dict[int, float] = {}
                for v, w in zip(vals, wts):
                    class_weights[int(v)] = class_weights.get(int(v), 0.0) + float(w)
                dom_code = max(class_weights, key=lambda k: class_weights[k])
                dom_label = USDA_TEXTURE_NAMES.get(dom_code, "Unknown")
            else:
                dom_code, dom_label = None, None
            out["usda_texture_0_5cm"] = ExtractedMetric(
                value=dom_label,
                unit="USDA texture class",
                source_dataset=SOILGRIDS_USDA_TIF.name,
                spatial_resolution="250 m",
                temporal_coverage="Static",
                valid_pixel_count=ures["count"],
                polygon_coverage_pct=ures["cov_pct"],
                aggregation_method="area_weighted_dominant_class",
                quality_status="MODELED_SPATIAL_ESTIMATE" if dom_label is not None else "UNAVAILABLE_MASKED_PIXEL",
                uncertainty_or_limitations="Derived from modeled 250 m SoilGrids sand/silt/clay fractions; verify local field tilth.",
                stats={"dominant_usda_code": float(dom_code)} if dom_code is not None else None,
            ).to_dict()
    elif used_zip_table and SOILGRIDS_USDA_TIF == _DEFAULT_SOILGRIDS_USDA_TIF and zip_hits is not None:
        zip_src = f"{INTEGRATED_DB_ZIP.name}::guelma_soil_static_250m.csv"
        cnt = int(len(zip_hits))
        cov_pct = round(min(100.0, 100.0 * float(zip_hits["_w"].sum()) / poly_area), 2) if (cnt > 0 and poly_area > 0) else 0.0
        dom_code: Optional[int] = None
        dom_label: Optional[str] = None
        if cnt > 0 and "usda_texture_0_5cm" in zip_hits.columns:
            class_weights = {}
            for code_raw, w in zip(zip_hits["usda_texture_0_5cm"], zip_hits["_w"]):
                if pd.notna(code_raw):
                    c_int = int(code_raw)
                    class_weights[c_int] = class_weights.get(c_int, 0.0) + float(w)
            if class_weights:
                dom_code = max(class_weights, key=lambda k: class_weights[k])
                dom_label = USDA_TEXTURE_NAMES.get(dom_code, "Unknown")
        out["usda_texture_0_5cm"] = ExtractedMetric(
            value=dom_label,
            unit="USDA texture class",
            source_dataset=zip_src,
            spatial_resolution="250 m",
            temporal_coverage="Static",
            valid_pixel_count=cnt if dom_label is not None else 0,
            polygon_coverage_pct=cov_pct if dom_label is not None else 0.0,
            aggregation_method="area_weighted_dominant_class",
            quality_status="MODELED_SPATIAL_ESTIMATE" if dom_label is not None else "UNAVAILABLE_MASKED_PIXEL",
            uncertainty_or_limitations="Derived from modeled 250 m SoilGrids sand/silt/clay fractions; verify local field tilth.",
            stats={"dominant_usda_code": float(dom_code)} if dom_code is not None else None,
        ).to_dict()
    else:
        out["usda_texture_0_5cm"] = _metric_unavailable(
            "USDA texture class", SOILGRIDS_USDA_TIF.name, "250 m", "Static",
            "area_weighted_dominant_class", "SoilGrids USDA texture raster absent locally.",
        )
    return out


def _extract_crop_frequency(geom_utm: Polygon) -> Dict[str, Any]:
    cf_path = CROP_FREQ_ALIGNED_10M_TIF if CROP_FREQ_ALIGNED_10M_TIF.exists() else CROP_FREQ_RAW_TIF
    if not cf_path.exists():
        return {"crop_frequency_2021_2025": _metric_unavailable("fraction [0..1]", "ESA Crop Frequency", "10 m", "2021-2025", "area_weighted", "Raster missing locally.")}
    with rasterio.open(cf_path) as ds:
        res = _extract_weighted_raster_window(ds, geom_utm, [1], nodata_override=NODATA_VALUE)[1]
        share_ge_05 = None
        if res["count"] > 0:
            wts = res["weights"]
            share_ge_05 = round(100.0 * float(wts[res["values"] >= 0.5].sum()) / float(wts.sum()), 2)
        return {
            "crop_frequency_2021_2025": ExtractedMetric(
                value=res["w_mean"],
                unit="fraction [0..1]",
                source_dataset=cf_path.name,
                spatial_resolution="10 m (origin aligned to Sentinel-2 10 m grid)",
                temporal_coverage="2021-2025 only",
                valid_pixel_count=res["count"],
                polygon_coverage_pct=res["cov_pct"],
                aggregation_method="polygon_pixel_intersection_area_weighted",
                quality_status="REMOTE_SENSING_DERIVED" if res["w_mean"] is not None else "UNAVAILABLE_MASKED_PIXEL",
                uncertainty_or_limitations="Represents 2021-2025 cropland detection frequency only; blocked from 2017-2020 historical attribution; share>=0.5 is included in stats.",
                stats={**(res["stats"] or {}), "cropland_share_ge_05_pct": share_ge_05} if res["stats"] else None,
            ).to_dict()
        }


def _extract_sentinel2(geom_utm: Polygon, tables: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    specs = [
        ("s2_2024_03_ndvi_10m", S2_PHASEA_10M_TIF, S2_PHASEA_VALID_10M_TIF, 1, "10 m"),
        ("s2_2024_03_evi_10m", S2_PHASEA_10M_TIF, S2_PHASEA_VALID_10M_TIF, 2, "10 m"),
        ("s2_2024_03_ndmi_20m", S2_PHASEA_20M_TIF, S2_PHASEA_VALID_20M_TIF, 1, "20 m"),
        ("s2_2024_03_ndre_20m", S2_PHASEA_20M_TIF, S2_PHASEA_VALID_20M_TIF, 2, "20 m"),
    ]
    grid_cache: Dict[str, Optional[Tuple[rasterio.windows.Window, np.ndarray]]] = {}
    for key, idx_path, val_path, band_i, res_label in specs:
        if not idx_path.exists():
            out[key] = _metric_unavailable("unitless", idx_path.name, res_label, "2024-03", "area_weighted", "March 2024 baseline GeoTIFF missing.")
            continue
        with rasterio.open(idx_path) as ids:
            if res_label not in grid_cache:
                grid_cache[res_label] = _compute_window_area_weights(ids, geom_utm)
            pre = grid_cache[res_label]
            mask_valid = None
            if pre is not None and val_path.exists():
                rw = pre[0]
                with rasterio.open(val_path) as vds:
                    if vds.shape == ids.shape and vds.transform == ids.transform:
                        mask_valid = vds.read(1, window=rw) > 0
            res = _extract_weighted_raster_window(ids, geom_utm, [band_i], extra_valid_mask_band=mask_valid, nodata_override=NODATA_VALUE, precomputed_weights=pre)[band_i]
            out[key] = ExtractedMetric(
                value=res["w_mean"],
                unit="unitless vegetation index",
                source_dataset=idx_path.name,
                spatial_resolution=f"{res_label} (March 2024 single-month median snapshot)",
                temporal_coverage="2024-03-01..2024-03-31",
                valid_pixel_count=res["count"],
                polygon_coverage_pct=res["cov_pct"],
                aggregation_method="polygon_pixel_intersection_area_weighted",
                quality_status="REMOTE_SENSING_DERIVED" if res["w_mean"] is not None else "UNAVAILABLE_MASKED_PIXEL",
                uncertainty_or_limitations="Single-month (March 2024) snapshot only; multi-year 2017-2025 10m/20m GeoTIFFs deferred under GEE Restricted Mode.",
                stats=res["stats"],
            ).to_dict()

    # Regional multi-year Wilaya S2 context (107 eligible months)
    wm = tables.get("wilaya_monthly")
    if wm is None and WILAYA_MONTHLY_CSV == _DEFAULT_WILAYA_MONTHLY_CSV and INTEGRATED_DB_ZIP.is_file():
        out["s2_wilaya_spring_ndvi_climatology_2017_2025"] = ExtractedMetric(
            value=0.6045,
            unit="unitless NDVI median",
            source_dataset="wilaya_monthly_panel_2016_2025_climatology_fallback",
            spatial_resolution="Wilaya (~3683.23 km2 regional fallback; 10 m pixel basis)",
            temporal_coverage="2017-03..2025-05 (27 Spring months; 2017-01 excluded globally)",
            valid_pixel_count=1,
            polygon_coverage_pct=100.0,
            aggregation_method="regional_wilaya_monthly_median_climatology",
            quality_status="REGIONAL_FALLBACK_ONLY",
            uncertainty_or_limitations="CRITICAL: Wilaya-wide regional average because multi-year 10 m/20 m Sentinel-2 GeoTIFFs were deferred; NOT field-level time series.",
        ).to_dict()
    elif wm is None or len(wm) == 0:
        out["s2_wilaya_spring_ndvi_climatology_2017_2025"] = _metric_unavailable(
            "unitless NDVI median", WILAYA_MONTHLY_CSV.name, "Wilaya regional fallback",
            "2017-03..2025-05", "regional_wilaya_monthly_median_climatology",
            "Wilaya monthly Sentinel-2 table absent locally.",
        )
    else:
        elig = wm[wm["s2_is_model_eligible_monthly"] == True]  # noqa: E712
        spring_elig = elig[elig["month"].isin([3, 4, 5])]
        out["s2_wilaya_spring_ndvi_climatology_2017_2025"] = ExtractedMetric(
            value=round(float(spring_elig["s2_NDVI_median"].mean()), 4),
            unit="unitless NDVI median",
            source_dataset=WILAYA_MONTHLY_CSV.name,
            spatial_resolution="Wilaya (~3683.23 km2 regional fallback; 10 m pixel basis)",
            temporal_coverage="2017-03..2025-05 (27 Spring months; 2017-01 excluded globally)",
            valid_pixel_count=1,
            polygon_coverage_pct=100.0,
            aggregation_method="regional_wilaya_monthly_median_climatology",
            quality_status="REGIONAL_FALLBACK_ONLY",
            uncertainty_or_limitations="CRITICAL: Wilaya-wide regional average because multi-year 10 m/20 m Sentinel-2 GeoTIFFs were deferred; NOT field-level time series.",
        ).to_dict()
    return out


def _extract_modis_seasonal(geom_utm: Polygon) -> Dict[str, Any]:
    season_vals: Dict[str, List[float]] = {s: [] for s in SEASONS}
    season_evi: Dict[str, List[float]] = {s: [] for s in SEASONS}
    last_cnt, last_cov = 0, 0.0
    files_found = 0
    modis_grid_key: Optional[Tuple[int, int, Any]] = None
    modis_weights: Optional[Tuple[rasterio.windows.Window, np.ndarray]] = None

    for yr in MODIS_YEARS:
        tif = MODIS_SEASONAL_DIR / f"guelma_modis_seasonal_{yr}.tif"
        if not tif.exists():
            continue
        files_found += 1
        with rasterio.open(tif) as ds:
            cur_key = (ds.height, ds.width, ds.transform)
            if modis_weights is None or cur_key != modis_grid_key:
                modis_weights = _compute_window_area_weights(ds, geom_utm)
                modis_grid_key = cur_key
            bmap = {name: i + 1 for i, name in enumerate(ds.descriptions)}
            for s in SEASONS:
                nb, eb = bmap[f"NDVI_{s}"], bmap[f"EVI_{s}"]
                res = _extract_weighted_raster_window(ds, geom_utm, [nb, eb], nodata_override=NODATA_VALUE, precomputed_weights=modis_weights)
                if res[nb]["w_mean"] is not None:
                    season_vals[s].append(res[nb]["w_mean"])
                    last_cnt = max(last_cnt, res[nb]["count"])
                    last_cov = max(last_cov, res[nb]["cov_pct"])
                if res[eb]["w_mean"] is not None:
                    season_evi[s].append(res[eb]["w_mean"])

    missing_files = files_found == 0
    if missing_files and MODIS_SEASONAL_DIR == _DEFAULT_MODIS_SEASONAL_DIR and (zt := _load_integrated_zip_tables()) is not None:
        zip_hits = _intersect_soil_250m_cells(geom_utm, zt["soil_df"])
        poly_area = float(geom_utm.area)
        out: Dict[str, Any] = {}
        if len(zip_hits) > 0:
            cnt = int(len(zip_hits))
            cov_pct = round(min(100.0, 100.0 * float(zip_hits["_w"].sum()) / poly_area), 2) if poly_area > 0 else 0.0
            w_df = pd.DataFrame({"grid_id": zip_hits["grid_id"].astype(str), "w": zip_hits["_w"] / float(zip_hits["_w"].sum())})
            veg_sub = zt["veg_df"].merge(w_df, on="grid_id", how="inner")
            src_label = f"{INTEGRATED_DB_ZIP.name}::guelma_vegetation_seasonal_250m_2016_2025.csv"
            for s in SEASONS:
                ssub = veg_sub[veg_sub["season"] == s]
                if len(ssub) > 0:
                    yr_ndvi = ssub.groupby("year").apply(lambda g: float(np.sum(g["NDVI"] * g["w"])), include_groups=False)
                    yr_evi = ssub.groupby("year").apply(lambda g: float(np.sum(g["EVI"] * g["w"])), include_groups=False)
                    ndvi_mean = round(float(yr_ndvi.mean()), 4)
                    evi_mean = round(float(yr_evi.mean()), 4)
                    ndvi_stats = {"min_yr": round(float(yr_ndvi.min()), 4), "max_yr": round(float(yr_ndvi.max()), 4)}
                else:
                    ndvi_mean, evi_mean, ndvi_stats = None, None, None
                out[f"modis_ndvi_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
                    value=ndvi_mean,
                    unit="unitless NDVI",
                    source_dataset=src_label,
                    spatial_resolution="250 m (6.25 ha mixed pixels)",
                    temporal_coverage="2016-2025 seasonal climatology (10 seasons)",
                    valid_pixel_count=cnt if ndvi_mean is not None else 0,
                    polygon_coverage_pct=cov_pct if ndvi_mean is not None else 0.0,
                    aggregation_method="polygon_pixel_intersection_area_weighted + 10yr_seasonal_mean",
                    quality_status="REMOTE_SENSING_DERIVED" if ndvi_mean is not None else "UNAVAILABLE_MASKED_PIXEL",
                    uncertainty_or_limitations="250 m pixel often mixes adjacent parcels/hedgerows; no 16-day MODIS files locally.",
                    stats=ndvi_stats,
                ).to_dict()
                out[f"modis_evi_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
                    value=evi_mean,
                    unit="unitless EVI",
                    source_dataset=src_label,
                    spatial_resolution="250 m",
                    temporal_coverage="2016-2025 seasonal climatology",
                    valid_pixel_count=cnt if evi_mean is not None else 0,
                    polygon_coverage_pct=cov_pct if evi_mean is not None else 0.0,
                    aggregation_method="polygon_pixel_intersection_area_weighted + 10yr_seasonal_mean",
                    quality_status="REMOTE_SENSING_DERIVED" if evi_mean is not None else "UNAVAILABLE_MASKED_PIXEL",
                    uncertainty_or_limitations="250 m mixed-pixel seasonal EVI greenness proxy; not crop species or yield.",
                ).to_dict()
            return out

        # Urban/masked 250 m parcel fallback to overlapping/nearest 11 km native grid MODIS climatology
        g11 = zt["grid_11km"]
        cm_df = zt["cm_df"]
        weights_11: Dict[str, float] = {}
        for row in g11.itertuples():
            inter = float(geom_utm.intersection(row.geometry).area)
            if inter > 0.0:
                weights_11[str(row.cell_id)] = inter
        if not weights_11 and len(g11) > 0:
            c = geom_utm.centroid
            dists = g11.geometry.centroid.distance(c)
            weights_11[str(g11.loc[dists.idxmin(), "cell_id"])] = poly_area
        tot11 = sum(weights_11.values()) or 1.0
        w11_df = pd.DataFrame([{"cell_id": k, "w": v / tot11} for k, v in weights_11.items()])
        cm_sub = cm_df.merge(w11_df, on="cell_id", how="inner")
        src_cm = f"{INTEGRATED_DB_ZIP.name}::guelma_climate_moisture_seasonal_native_grid_2016_2025.csv"
        for s in SEASONS:
            ssub = cm_sub[cm_sub["Season"] == s]
            yr_ndvi = ssub.groupby("Year").apply(lambda g: float(np.sum(g["NDVI"] * g["w"])), include_groups=False)
            yr_evi = ssub.groupby("Year").apply(lambda g: float(np.sum(g["EVI"] * g["w"])), include_groups=False)
            out[f"modis_ndvi_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
                value=round(float(yr_ndvi.mean()), 4) if len(yr_ndvi) else None,
                unit="unitless NDVI",
                source_dataset=src_cm,
                spatial_resolution="11 km regional MODIS grid fallback (urban 250 m pixel masked)",
                temporal_coverage="2016-2025 seasonal climatology (10 seasons)",
                valid_pixel_count=len(weights_11),
                polygon_coverage_pct=100.0,
                aggregation_method="11km_polygon_intersection_area_weighted + 10yr_seasonal_mean",
                quality_status="REMOTE_SENSING_DERIVED",
                uncertainty_or_limitations="250 m MODIS soil/vegetation grid masked on this parcel; derived from enclosing 11 km native cell.",
                stats={"min_yr": round(float(yr_ndvi.min()), 4), "max_yr": round(float(yr_ndvi.max()), 4)} if len(yr_ndvi) else None,
            ).to_dict()
            out[f"modis_evi_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
                value=round(float(yr_evi.mean()), 4) if len(yr_evi) else None,
                unit="unitless EVI",
                source_dataset=src_cm,
                spatial_resolution="11 km regional MODIS grid fallback (urban 250 m pixel masked)",
                temporal_coverage="2016-2025 seasonal climatology",
                valid_pixel_count=len(weights_11),
                polygon_coverage_pct=100.0,
                aggregation_method="11km_polygon_intersection_area_weighted + 10yr_seasonal_mean",
                quality_status="REMOTE_SENSING_DERIVED",
                uncertainty_or_limitations="250 m MODIS soil/vegetation grid masked on this parcel; derived from enclosing 11 km native cell.",
            ).to_dict()
        return out

    out: Dict[str, Any] = {}
    for s in SEASONS:
        arr_n = season_vals[s]
        arr_e = season_evi[s]
        out[f"modis_ndvi_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
            value=round(float(np.mean(arr_n)), 4) if arr_n else None,
            unit="unitless NDVI",
            source_dataset="guelma_modis_seasonal_2016..2025.tif",
            spatial_resolution="250 m (6.25 ha mixed pixels)",
            temporal_coverage="2016-2025 seasonal climatology (10 seasons)",
            valid_pixel_count=last_cnt,
            polygon_coverage_pct=last_cov,
            aggregation_method="polygon_pixel_intersection_area_weighted + 10yr_seasonal_mean",
            quality_status="REMOTE_SENSING_DERIVED" if arr_n else ("UNAVAILABLE_NOT_INTEGRATED" if missing_files else "UNAVAILABLE_MASKED_PIXEL"),
            uncertainty_or_limitations="MODIS seasonal GeoTIFFs absent locally." if missing_files else "250 m pixel often mixes adjacent parcels/hedgerows; no 16-day MODIS files locally.",
            stats={"min_yr": round(min(arr_n), 4), "max_yr": round(max(arr_n), 4)} if arr_n else None,
        ).to_dict()
        out[f"modis_evi_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
            value=round(float(np.mean(arr_e)), 4) if arr_e else None,
            unit="unitless EVI",
            source_dataset="guelma_modis_seasonal_2016..2025.tif",
            spatial_resolution="250 m",
            temporal_coverage="2016-2025 seasonal climatology",
            valid_pixel_count=last_cnt,
            polygon_coverage_pct=last_cov,
            aggregation_method="polygon_pixel_intersection_area_weighted + 10yr_seasonal_mean",
            quality_status="REMOTE_SENSING_DERIVED" if arr_e else ("UNAVAILABLE_NOT_INTEGRATED" if missing_files else "UNAVAILABLE_MASKED_PIXEL"),
            uncertainty_or_limitations="MODIS seasonal GeoTIFFs absent locally." if missing_files else "250 m mixed-pixel seasonal EVI greenness proxy; not crop species or yield.",
        ).to_dict()
    return out


def _extract_gpm_smap(geom_utm: Polygon, tables: Dict[str, Any]) -> Dict[str, Any]:
    g11 = tables.get("grid_11km")
    gpm_raw = tables.get("gpm_sea")
    smap_raw = tables.get("smap_sea")
    out: Dict[str, Any] = {}

    if g11 is None or gpm_raw is None or smap_raw is None:
        out["gpm_annual_precip_2016_2025_mean_mm"] = _metric_unavailable("mm/year", GPM_SEASONAL_CSV.name, "11 km aligned", "2016-2025", "11km_polygon_intersection_area_weighted", "GPM/SMAP local canonical tables absent.")
        for s in SEASONS:
            out[f"gpm_precip_{s.lower()}_2016_2025_mean_mm"] = _metric_unavailable("mm/season", GPM_SEASONAL_CSV.name, "11 km aligned", "2016-2025", "11km_polygon_intersection_area_weighted", "GPM/SMAP local canonical tables absent.")
            out[f"smap_rootzone_sm_{s.lower()}_2016_2025_mean"] = _metric_unavailable("m3/m3", SMAP_SEASONAL_CSV.name, "11 km", "2016-2025", "11km_polygon_intersection_area_weighted", "GPM/SMAP local canonical tables absent.")
            out[f"smap_surface_sm_{s.lower()}_2016_2025_mean"] = _metric_unavailable("m3/m3", SMAP_SEASONAL_CSV.name, "11 km", "2016-2025", "11km_polygon_intersection_area_weighted", "GPM/SMAP local canonical tables absent.")
        return out

    poly_area = float(geom_utm.area)
    weights: Dict[str, float] = {}
    for row in g11.itertuples():
        inter = float(geom_utm.intersection(row.geometry).area)
        if inter > 0.0:
            weights[str(row.cell_id)] = inter

    if not weights and GRID_11KM_CSV == _DEFAULT_GRID_11KM_CSV and len(g11) > 0:
        c = geom_utm.centroid
        nearest_idx = g11.geometry.centroid.distance(c).idxmin()
        weights[str(g11.loc[nearest_idx, "cell_id"])] = poly_area

    tot_w = sum(weights.values())
    cov_pct = round(min(100.0, 100.0 * tot_w / poly_area), 2) if poly_area > 0 else 0.0
    if tot_w <= 0.0:
        out["gpm_annual_precip_2016_2025_mean_mm"] = _metric_unavailable("mm/year", GPM_SEASONAL_CSV.name, "11 km aligned", "2016-2025", "area_weighted", "No valid 11 km GPM cell intersection.")
        for s in SEASONS:
            out[f"gpm_precip_{s.lower()}_2016_2025_mean_mm"] = _metric_unavailable("mm/season", GPM_SEASONAL_CSV.name, "11 km aligned", "2016-2025", "area_weighted", "No valid 11 km GPM cell intersection.")
            out[f"smap_rootzone_sm_{s.lower()}_2016_2025_mean"] = _metric_unavailable("m3/m3", SMAP_SEASONAL_CSV.name, "11 km", "2016-2025", "area_weighted", "No valid 11 km SMAP cell intersection.")
            out[f"smap_surface_sm_{s.lower()}_2016_2025_mean"] = _metric_unavailable("m3/m3", SMAP_SEASONAL_CSV.name, "11 km", "2016-2025", "area_weighted", "No valid 11 km SMAP cell intersection.")
        return out

    w_df = pd.DataFrame([{"cell_id": k, "w": v / tot_w} for k, v in weights.items()])
    gpm = gpm_raw.merge(w_df, on="cell_id", how="inner")
    smap = smap_raw.merge(w_df, on="cell_id", how="inner")

    gpm_yr_s = gpm.groupby(["season_year", "season"], as_index=False).apply(lambda g: float(np.sum(g["gpm_precip_mm"] * g["w"])), include_groups=False).rename(columns={None: "val"})
    smap_yr_s = smap.groupby(["season_year", "season"], as_index=False).apply(lambda g: float(np.sum(g["smap_sm_rootzone_m3m3"] * g["w"])), include_groups=False).rename(columns={None: "val"})
    smap_surf = smap.groupby(["season_year", "season"], as_index=False).apply(lambda g: float(np.sum(g["smap_sm_surface_m3m3"] * g["w"])), include_groups=False).rename(columns={None: "val"})

    annual_gpm = gpm_yr_s.groupby("season_year")["val"].sum()
    out["gpm_annual_precip_2016_2025_mean_mm"] = ExtractedMetric(
        value=round(float(annual_gpm.mean()), 2),
        unit="mm/year",
        source_dataset=GPM_SEASONAL_CSV.name,
        spatial_resolution="11 km cell (from ~9.63 km IMERG; 12,100 ha cell vs field)",
        temporal_coverage="2016-2025 hydrologic annual sum (DJF+MAM+JJA+SON across Dec Y-1..Nov Y)",
        valid_pixel_count=len(weights),
        polygon_coverage_pct=cov_pct,
        aggregation_method="11km_polygon_intersection_area_weighted",
        quality_status="REMOTE_SENSING_DERIVED",
        uncertainty_or_limitations="Macro-regional ~10-11 km precipitation estimate (hydrologic year Dec..Nov sum); NO monthly GPM on disk; ~132 mm/yr drier on average than NASA POWER across Guelma.",
        stats={"min_yr_hydro": round(float(annual_gpm.min()), 2), "max_yr_hydro": round(float(annual_gpm.max()), 2)},
    ).to_dict()

    for s in SEASONS:
        g_sub = gpm_yr_s[gpm_yr_s["season"] == s]["val"]
        out[f"gpm_precip_{s.lower()}_2016_2025_mean_mm"] = ExtractedMetric(
            value=round(float(g_sub.mean()), 2),
            unit="mm/season",
            source_dataset=GPM_SEASONAL_CSV.name,
            spatial_resolution="11 km regional hydro-climate cell",
            temporal_coverage="2016-2025 (seasonal cadence ONLY; no monthly GPM locally)",
            valid_pixel_count=len(weights),
            polygon_coverage_pct=cov_pct,
            aggregation_method="11km_polygon_intersection_area_weighted",
            quality_status="REMOTE_SENSING_DERIVED",
            uncertainty_or_limitations="Coarse regional rainfall, NOT an on-farm rain gauge.",
            stats={"min_yr": round(float(g_sub.min()), 2), "max_yr": round(float(g_sub.max()), 2)},
        ).to_dict()

        sm_r = smap_yr_s[smap_yr_s["season"] == s]["val"]
        out[f"smap_rootzone_sm_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
            value=round(float(sm_r.mean()), 4),
            unit="m3/m3",
            source_dataset=SMAP_SEASONAL_CSV.name,
            spatial_resolution="11 km (SMAP L4 assimilated model rootzone 0-100 cm)",
            temporal_coverage="2016-2025 (seasonal cadence ONLY; no monthly SMAP locally)",
            valid_pixel_count=len(weights),
            polygon_coverage_pct=cov_pct,
            aggregation_method="11km_polygon_intersection_area_weighted",
            quality_status="MODELED_SPATIAL_ESTIMATE",
            uncertainty_or_limitations="Assimilated 11 km macro root-zone soil wetness, insensitive to field-level drip/irrigation scheduling.",
            stats={"min_yr": round(float(sm_r.min()), 4), "max_yr": round(float(sm_r.max()), 4)},
        ).to_dict()

        sm_s = smap_surf[smap_surf["season"] == s]["val"]
        out[f"smap_surface_sm_{s.lower()}_2016_2025_mean"] = ExtractedMetric(
            value=round(float(sm_s.mean()), 4),
            unit="m3/m3",
            source_dataset=SMAP_SEASONAL_CSV.name,
            spatial_resolution="11 km (SMAP L4 surface 0-5 cm)",
            temporal_coverage="2016-2025 seasonal",
            valid_pixel_count=len(weights),
            polygon_coverage_pct=cov_pct,
            aggregation_method="11km_polygon_intersection_area_weighted",
            quality_status="MODELED_SPATIAL_ESTIMATE",
            uncertainty_or_limitations="11 km surface moisture proxy; seasonal cadence only.",
        ).to_dict()
    return out


def _extract_nasa_power(geom_utm: Polygon, tables: Dict[str, Any]) -> Dict[str, Any]:
    ag_gdf = tables.get("ag_gdf")
    re_gdf = tables.get("re_gdf")
    np_df = tables.get("np_cells")
    ag_specs = [
        ("T2M", "nasa_power_t2m_2016_2025_mean_c", "degC", "mean"),
        ("T2M_MAX", "nasa_power_t2m_max_2016_2025_mean_c", "degC", "mean"),
        ("T2M_MIN", "nasa_power_t2m_min_2016_2025_mean_c", "degC", "mean"),
        ("RH2M", "nasa_power_rh2m_2016_2025_mean_pct", "%", "mean"),
        ("PRECTOTCORR", "nasa_power_annual_precip_2016_2025_mean_mm", "mm/year", "annual_sum_then_mean"),
    ]
    re_specs = [("ALLSKY_SFC_SW_DWN", "nasa_power_solar_sw_2016_2025_mean_kwh_m2_day", "kWh/m2/day", "mean")]

    out: Dict[str, Any] = {}
    poly_area = float(geom_utm.area)
    ag_w: Dict[str, float] = {}
    if ag_gdf is not None:
        for r in ag_gdf.itertuples():
            inter = float(geom_utm.intersection(r.geometry).area)
            if inter > 0.0:
                ag_w[str(r.cell_id)] = inter
    re_w: Dict[str, float] = {}
    if re_gdf is not None:
        for r in re_gdf.itertuples():
            inter = float(geom_utm.intersection(r.geometry).area)
            if inter > 0.0:
                re_w[str(r.cell_id)] = inter

    def _agg_community(cell_weights: Dict[str, float], community: str, var_specs: List[Tuple[str, str, str, str]]) -> None:
        tot = sum(cell_weights.values())
        cov_pct = round(min(100.0, 100.0 * tot / poly_area), 2) if poly_area > 0 else 0.0
        res_label = "0.5 x 0.625 deg (~55-69 km MERRA-2)" if community == "AG" else "1.0 x 1.0 deg (~111 km CERES SYN1deg)"
        if np_df is None or tot <= 0.0:
            if (
                np_df is None
                and NASA_POWER_DAILY_CELLS_CSV == _DEFAULT_NASA_POWER_DAILY_CELLS_CSV
                and INTEGRATED_DB_ZIP.is_file()
            ):
                for var_name, key, unit, _ in var_specs:
                    val, s_stats = _REGIONAL_NASA_POWER_CLIMATOLOGY[var_name]
                    out[key] = ExtractedMetric(
                        value=val,
                        unit=unit,
                        source_dataset="nasa_power_regional_climatology_2016_2025",
                        spatial_resolution=res_label,
                        temporal_coverage="2016-01-01..2025-12-31 (regional Wilaya climatology; 9 complete DJF winters 2017-2025)",
                        valid_pixel_count=1,
                        polygon_coverage_pct=100.0,
                        aggregation_method=f"regional_{community}_climatology_fallback",
                        quality_status="MODELED_SPATIAL_ESTIMATE",
                        uncertainty_or_limitations=(
                            "Coarse regional MERRA-2/CERES macro-climate baseline; does not resolve valley microclimate/frost pockets; "
                            "NASA POWER annual precip averages higher than GPM across Guelma."
                        ),
                        stats=dict(s_stats),
                    ).to_dict()
                return
            reason = "NASA POWER local table/geometry absent." if np_df is None or (ag_gdf is None and community == "AG") or (re_gdf is None and community == "RE") else f"No overlapping NASA POWER {community} cell."
            for _, key, unit, _ in var_specs:
                out[key] = _metric_unavailable(unit, NASA_POWER_DAILY_CELLS_CSV.name, res_label, "2016-2025", "cell_area_weighted", reason)
            return
        wmap = {cid: w / tot for cid, w in cell_weights.items()}
        sub = np_df[(np_df["community"] == community) & (np_df["cell_id"].astype(str).isin(wmap))].copy()
        sub["w"] = sub["cell_id"].astype(str).map(wmap)
        for var_name, key, unit, mode in var_specs:
            vdf = sub[sub["variable"] == var_name].copy()
            vdf["season_year"] = np.where(vdf["month"] == 12, vdf["year"] + 1, vdf["year"])
            daily = (
                vdf.groupby(["date", "year", "season_year", "season"], as_index=False)
                .apply(lambda g: float(np.sum(g["value"] * g["w"])), include_groups=False)
                .rename(columns={None: "val"})
            )
            # Keep only complete meteorological seasons (>= 80 days: drops partial Winter 2016 and Winter 2026)
            sy_counts = daily.groupby(["season", "season_year"])["val"].transform("count")
            complete_daily = daily[sy_counts >= 80]

            if mode == "annual_sum_then_mean":
                val = float(daily.groupby("year")["val"].sum().mean())
                season_stats = {
                    s.lower(): round(float(complete_daily[complete_daily["season"] == s].groupby("season_year")["val"].sum().mean()), 2)
                    for s in SEASONS
                }
            else:
                val = float(daily["val"].mean())
                season_stats = {
                    s.lower(): round(float(complete_daily[complete_daily["season"] == s]["val"].mean()), 2)
                    for s in SEASONS
                }
            out[key] = ExtractedMetric(
                value=round(val, 2),
                unit=unit,
                source_dataset=NASA_POWER_DAILY_CELLS_CSV.name,
                spatial_resolution=res_label,
                temporal_coverage="2016-01-01..2025-12-31 (3,653 days; seasonal winter averages over 9 complete DJF winters 2017-2025)",
                valid_pixel_count=len(cell_weights),
                polygon_coverage_pct=cov_pct,
                aggregation_method=f"polygon_intersection_{community}_cell_weighted",
                quality_status="MODELED_SPATIAL_ESTIMATE",
                uncertainty_or_limitations=(
                    "Coarse macro-climate reanalysis/satellite cell; does not resolve valley microclimate/frost pockets; "
                    "NASA POWER annual precip averages +132 mm/yr higher than GPM across Guelma."
                ),
                stats=season_stats,
            ).to_dict()

    _agg_community(ag_w, "AG", ag_specs)
    _agg_community(re_w, "RE", re_specs)
    return out


def _extract_dem_placeholder() -> Dict[str, Any]:
    """Return explicit unavailable DEM records rather than inventing elevation/slope."""
    note = "No local DEM integrated yet (SRTM 30 m planned); do not prompt farmer for slope degrees — verify drainage visually only if needed."
    return {
        "dem_elevation_m": _metric_unavailable("m", "NONE_INTEGRATED (SRTM 30 m planned)", "30 m (unavailable)", "Static", "none", note),
        "dem_slope_pct": _metric_unavailable("%", "NONE_INTEGRATED (SRTM 30 m planned)", "30 m (unavailable)", "Static", "none", note),
    }


def extract_field_geospatial_context(geometry: Dict[str, Any], geometry_crs: str = "EPSG:4326") -> Dict[str, Any]:
    """Validate farmer-drawn polygon and automatically extract all local multi-scale geospatial layers."""
    spatial = validate_and_project_polygon(geometry, geometry_crs=geometry_crs)
    geom_utm = spatial["geom_utm"]
    tables = _load_coarse_tables()

    extracted: Dict[str, Dict[str, Any]] = {
        "soilgrids_v6": _extract_soilgrids(geom_utm),
        "crop_frequency": _extract_crop_frequency(geom_utm),
        "sentinel2": _extract_sentinel2(geom_utm, tables),
        "modis": _extract_modis_seasonal(geom_utm),
        "gpm_and_smap": _extract_gpm_smap(geom_utm, tables),
        "nasa_power": _extract_nasa_power(geom_utm, tables),
        "terrain_dem": _extract_dem_placeholder(),
    }

    return {
        "spatial_validation": {k: v for k, v in spatial.items() if k not in ("geom_utm", "geom_wgs84")},
        "extracted_datasets": extracted,
    }
