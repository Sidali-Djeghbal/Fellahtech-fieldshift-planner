"""Phases 2-9: Google Earth Engine inspection, masking, index computation, and exports."""

import io
import json
import math
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.merge import merge as rio_merge
from shapely.geometry import box, mapping

from .config import (
    BOUNDARY_FILE,
    CLOUD_PROB_THRESHOLD,
    END_YEAR,
    EVI_DENOM_THRESHOLD,
    GEE_ASSET_ID,
    GEE_PROJECT,
    NODATA_VALUE,
    PROJECT_DIR,
    RAW_EXPORTS_DIR,
    RAW_METADATA_DIR,
    REFLECTANCE_SCALE,
    S2_CLOUD_PROB_ID,
    S2_COLLECTION_ID,
    SCL_EXCLUDED_CLASSES,
    START_YEAR,
    TARGET_CRS,
)
from .drive_export_manager import ensure_single_drive_folder


def _import_and_init_ee():
    """Import ee and initialize using existing persistent GEE authentication."""
    try:
        import ee  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "earthengine-api is not installed in this environment. "
            "Install it with: ./venv/bin/pip install earthengine-api"
        ) from exc

    try:
        ee.Initialize(project=GEE_PROJECT)
    except Exception as exc:
        raise RuntimeError(
            "Google Earth Engine is not authenticated on this machine.\n"
            "Run `./venv/bin/earthengine authenticate` in a terminal, then rerun this pipeline.\n"
            f"Original error: {exc}"
        ) from exc
    return ee


def _with_retry(fn, retries: int = 3, delay_sec: float = 3.0):
    """Execute a GEE call with bounded retries for transient network/computation errors."""
    last_err = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(delay_sec * (attempt + 1))
    raise last_err


def _get_guelma_geometry(ee):
    """Resolve Guelma geometry from GEE asset if accessible, else from verified local GeoPackage."""
    try:
        ee.data.getAsset(GEE_ASSET_ID)
        fc = ee.FeatureCollection(GEE_ASSET_ID)
        return fc.geometry(), GEE_ASSET_ID, int(fc.size().getInfo())
    except Exception:
        gdf = gpd.read_file(BOUNDARY_FILE).to_crs("EPSG:4326")
        union_geom = gdf.geometry.union_all()
        ee_geom = ee.Geometry(mapping(union_geom))
        return ee_geom, f"local:{BOUNDARY_FILE.relative_to(PROJECT_DIR)}", int(len(gdf))


def inspect_gee_collection_metadata() -> Dict:
    """Inspect Guelma asset, S2_SR_HARMONIZED & S2_CLOUD_PROBABILITY availability, join match rate, and SCL=2 share."""
    ee = _import_and_init_ee()

    guelma_geom, boundary_source, asset_count = _get_guelma_geometry(ee)
    asset_area_km2 = guelma_geom.area(maxError=1).divide(1e6).getInfo()

    # Include Dec 2016 to evaluate Winter 2017 (DJF) completeness
    s2 = (
        ee.ImageCollection(S2_COLLECTION_ID)
        .filterBounds(guelma_geom)
        .filterDate("2016-12-01", f"{END_YEAR + 1}-01-01")
    )
    s2_2017_2025 = s2.filterDate(f"{START_YEAR}-01-01", f"{END_YEAR + 1}-01-01")
    cp = (
        ee.ImageCollection(S2_CLOUD_PROB_ID)
        .filterBounds(guelma_geom)
        .filterDate("2016-12-01", f"{END_YEAR + 1}-01-01")
    )

    total_s2 = int(s2.size().getInfo())
    total_s2_main = int(s2_2017_2025.size().getInfo())
    total_cp = int(cp.size().getInfo())

    # Check inner join coverage between S2_SR_HARMONIZED and S2_CLOUD_PROBABILITY
    inner_joined = ee.Join.inner().apply(
        s2,
        cp,
        ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    matched_cp_count = int(inner_joined.size().getInfo())

    sample_img = ee.Image(s2.first())
    band_names = sample_img.bandNames().getInfo()
    band_scales = {
        b: sample_img.select(b).projection().nominalScale().getInfo()
        for b in ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12", "SCL", "QA60"]
        if b in band_names
    }

    # Vectorized server-side monthly image count over 2016-12 .. 2025-12 (109 months)
    check_months = [(2016, 12)] + [(y, m) for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)]
    ee_months = ee.List([[y, m] for y, m in check_months])

    def _count_month(ym):
        ym = ee.List(ym)
        y = ee.Number(ym.get(0))
        m = ee.Number(ym.get(1))
        st = ee.Date.fromYMD(y, m, 1)
        en = st.advance(1, "month")
        return ee.Dictionary(
            {
                "year": y,
                "month": m,
                "image_count": s2.filterDate(st, en).size(),
            }
        )

    monthly_counts = ee_months.map(_count_month).getInfo()

    # Evaluate SCL class 2 ("Dark area pixels") fraction in representative Winter and Summer periods at 20 m
    scl2_eval = {}
    for label, st_str, en_str in [
        ("winter_2023_01", "2023-01-01", "2023-02-01"),
        ("spring_2023_04", "2023-04-01", "2023-05-01"),
        ("summer_2023_07", "2023-07-01", "2023-08-01"),
    ]:
        sub = s2.filterDate(st_str, en_str)

        def _scl_flags(img):
            scl = img.select("SCL")
            non_cloud = (
                scl.neq(0)
                .And(scl.neq(1))
                .And(scl.neq(3))
                .And(scl.neq(8))
                .And(scl.neq(9))
                .And(scl.neq(10))
                .And(scl.neq(11))
            )
            is_scl2 = scl.eq(2).And(non_cloud)
            return ee.Image.cat([is_scl2.rename("scl2"), non_cloud.rename("retained")]).clip(guelma_geom)

        sums = (
            sub.map(_scl_flags)
            .sum()
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=guelma_geom,
                scale=20,
                crs=TARGET_CRS,
                maxPixels=1e10,
                tileScale=4,
            )
            .getInfo()
        )
        ret = float(sums.get("retained") or 0.0)
        s2_dark = float(sums.get("scl2") or 0.0)
        scl2_eval[label] = {
            "retained_pixel_obs": int(ret),
            "scl2_pixel_obs": int(s2_dark),
            "scl2_share_of_retained_pct": round((s2_dark / ret * 100.0) if ret > 0 else 0.0, 3),
        }

    meta = {
        "gee_project": GEE_PROJECT,
        "gee_asset": boundary_source,
        "asset_feature_count": asset_count,
        "asset_area_km2": round(float(asset_area_km2), 4),
        "s2_collection": S2_COLLECTION_ID,
        "cloud_prob_collection": S2_CLOUD_PROB_ID,
        "total_s2_images_2016_12_to_2025_12": total_s2,
        "total_s2_images_2017_01_to_2025_12": total_s2_main,
        "total_cloud_prob_images": total_cp,
        "s2_images_with_cloud_prob_match": matched_cp_count,
        "cloud_prob_match_pct": round(matched_cp_count / total_s2 * 100.0, 2) if total_s2 else 0.0,
        "available_bands": band_names,
        "band_native_scales_m": band_scales,
        "scl_class_2_evaluation": scl2_eval,
        "monthly_image_availability": monthly_counts,
    }

    with open(RAW_METADATA_DIR / "gee_collection_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def _build_boundary_masks(ee, guelma_geom):
    """Build deterministic binary interior masks at exact native 10 m and 20 m EPSG:32632 grids."""
    base_mask = ee.Image.constant(1).clip(guelma_geom).mask().gte(0.5)
    mask_10m = base_mask.reproject(crs=TARGET_CRS, scale=10).selfMask()
    mask_20m = base_mask.reproject(crs=TARGET_CRS, scale=20).selfMask()
    return mask_10m, mask_20m


def _compute_static_boundary_counts(ee, guelma_geom, mask_10m, mask_20m) -> Tuple[int, int]:
    """Compute static Guelma pixel counts once outside monthly/seasonal/annual summaries."""
    total_px_10 = int(
        mask_10m.rename("total_px")
        .reduceRegion(
            reducer=ee.Reducer.count().unweighted(),
            geometry=guelma_geom,
            scale=10,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=2,
        )
        .get("total_px")
        .getInfo()
    )
    total_px_20 = int(
        mask_20m.rename("total_px")
        .reduceRegion(
            reducer=ee.Reducer.count().unweighted(),
            geometry=guelma_geom,
            scale=20,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=2,
        )
        .get("total_px")
        .getInfo()
    )
    return total_px_10, total_px_20


def _build_prepared_s2_collection(ee, guelma_geom):
    """Build cloud-masked, scaled S2_SR_HARMONIZED collection with NDVI, EVI, NDMI, NDRE."""
    s2 = (
        ee.ImageCollection(S2_COLLECTION_ID)
        .filterBounds(guelma_geom)
        .filterDate("2016-12-01", f"{END_YEAR + 1}-01-01")
    )
    cp = (
        ee.ImageCollection(S2_CLOUD_PROB_ID)
        .filterBounds(guelma_geom)
        .filterDate("2016-12-01", f"{END_YEAR + 1}-01-01")
    )

    joined = ee.Join.saveFirst(matchKey="cloud_prob_img", outer=True).apply(
        s2,
        cp,
        ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )

    excluded_codes = list(SCL_EXCLUDED_CLASSES.keys())

    def _mask_and_indices(img):
        img = ee.Image(img)
        scl = img.select("SCL")

        valid_scl = ee.Image(1)
        for code in excluded_codes:
            valid_scl = valid_scl.And(scl.neq(code))

        cp_obj = img.get("cloud_prob_img")
        valid_cp = ee.Image(
            ee.Algorithms.If(
                cp_obj,
                ee.Image(cp_obj).select("probability").lt(CLOUD_PROB_THRESHOLD),
                ee.Image(1),
            )
        )
        mask = valid_scl.And(valid_cp)

        blue = img.select("B2").multiply(REFLECTANCE_SCALE)
        green = img.select("B3").multiply(REFLECTANCE_SCALE)
        red = img.select("B4").multiply(REFLECTANCE_SCALE)
        re1 = img.select("B5").multiply(REFLECTANCE_SCALE)
        nir = img.select("B8").multiply(REFLECTANCE_SCALE)
        nir_narrow = img.select("B8A").multiply(REFLECTANCE_SCALE)
        swir1 = img.select("B11").multiply(REFLECTANCE_SCALE)

        ndvi_den = nir.add(red)
        ndvi = nir.subtract(red).divide(ndvi_den.where(ndvi_den.eq(0), 1e-6)).rename("NDVI")

        # Mask physically invalid reflectance (<0) and small EVI denominators without clipping EVI
        evi_denom = nir.add(red.multiply(6.0)).subtract(blue.multiply(7.5)).add(1.0)
        evi_valid = (
            blue.gte(0)
            .And(red.gte(0))
            .And(nir.gte(0))
            .And(evi_denom.gt(EVI_DENOM_THRESHOLD))
        )
        evi = (
            nir.subtract(red)
            .multiply(2.5)
            .divide(evi_denom.where(evi_denom.lte(EVI_DENOM_THRESHOLD), 1.0))
            .updateMask(evi_valid)
            .rename("EVI")
        )

        ndmi_den = nir.add(swir1)
        ndmi = nir.subtract(swir1).divide(ndmi_den.where(ndmi_den.eq(0), 1e-6)).rename("NDMI")

        ndre_den = nir_narrow.add(re1)
        ndre = nir_narrow.subtract(re1).divide(ndre_den.where(ndre_den.eq(0), 1e-6)).rename("NDRE")

        is_scl2 = scl.eq(2).toFloat().rename("is_scl2")

        return (
            img.select(["B2", "B3", "B4", "B8"])
            .multiply(REFLECTANCE_SCALE)
            .addBands([ndvi, evi, ndmi, ndre, is_scl2])
            .updateMask(mask)
            .copyProperties(img, ["system:time_start", "CLOUDY_PIXEL_PERCENTAGE"])
        )

    return ee.ImageCollection(joined).map(_mask_and_indices)


def run_gee_summary_exports() -> Tuple[str, str, str]:
    """Compute monthly, seasonal, and annual summaries using stacked 2-pass GEE reductions."""
    ee = _import_and_init_ee()
    guelma_geom, _, _ = _get_guelma_geometry(ee)
    s2_prep = _build_prepared_s2_collection(ee, guelma_geom)

    mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)
    total_px_10, total_px_20 = _compute_static_boundary_counts(ee, guelma_geom, mask_10m, mask_20m)

    temp_reducer = ee.Reducer.median().combine(ee.Reducer.count(), "", True)
    scl2_reducer = ee.Reducer.mean().combine(ee.Reducer.count(), "", True)
    reg_reducer = (
        ee.Reducer.percentile([5, 50, 95])
        .combine(ee.Reducer.mean(), "", True)
        .combine(ee.Reducer.stdDev(), "", True)
        .combine(ee.Reducer.minMax(), "", True)
        .combine(ee.Reducer.count(), "", True)
        .unweighted()
    )

    def _summarize(col, extra_props: Dict):
        img_count = col.size()
        empty_10m = (
            ee.Image.constant([0, 0, 0, 0])
            .toFloat()
            .rename(["NDVI", "EVI", "valid_obs_10m", "evi_valid_obs_10m"])
            .updateMask(ee.Image(0))
        )
        empty_20m = (
            ee.Image.constant([0, 0, 0, 0])
            .toFloat()
            .rename(["NDMI", "NDRE", "valid_obs_20m", "scl2_obs"])
            .updateMask(ee.Image(0))
        )

        def _build_stack_10m():
            t10 = col.select(["NDVI", "EVI"]).reduce(temp_reducer)
            obs10 = t10.select("NDVI_count").unmask(0).rename("valid_obs_10m")
            evi_obs = t10.select("EVI_count").unmask(0).rename("evi_valid_obs_10m")
            return ee.Image.cat(
                [
                    t10.select(["NDVI_median", "EVI_median"]).rename(["NDVI", "EVI"]),
                    obs10,
                    evi_obs,
                ]
            ).updateMask(mask_10m)

        def _build_stack_20m():
            t20 = col.select(["NDMI", "NDRE"]).reduce(temp_reducer)
            scl2 = col.select("is_scl2").reduce(scl2_reducer)
            obs20 = t20.select("NDMI_count").unmask(0).rename("valid_obs_20m")
            scl2_sum = (
                scl2.select("is_scl2_mean")
                .multiply(scl2.select("is_scl2_count"))
                .unmask(0)
                .rename("scl2_obs")
            )
            return ee.Image.cat(
                [
                    t20.select(["NDMI_median", "NDRE_median"]).rename(["NDMI", "NDRE"]),
                    obs20,
                    scl2_sum,
                ]
            ).updateMask(mask_20m)

        stack10 = ee.Image(ee.Algorithms.If(img_count.gt(0), _build_stack_10m(), empty_10m))
        stack20 = ee.Image(ee.Algorithms.If(img_count.gt(0), _build_stack_20m(), empty_20m))

        stats10 = stack10.reduceRegion(
            reducer=reg_reducer,
            geometry=guelma_geom,
            scale=10,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=4,
        )
        stats20 = stack20.reduceRegion(
            reducer=reg_reducer,
            geometry=guelma_geom,
            scale=20,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=4,
        )
        props = (
            ee.Dictionary(extra_props)
            .set("image_count", img_count)
            .set("total_pixels_10m", total_px_10)
            .set("total_pixels_20m", total_px_20)
            .set("evi_denom_threshold", EVI_DENOM_THRESHOLD)
            .set("mean_valid_obs_per_px_10m", stats10.get("valid_obs_10m_mean"))
            .set("mean_valid_obs_per_px_20m", stats20.get("valid_obs_20m_mean"))
            .set("NDVI_median", stats10.get("NDVI_p50"))
            .set("EVI_median", stats10.get("EVI_p50"))
            .set("NDMI_median", stats20.get("NDMI_p50"))
            .set("NDRE_median", stats20.get("NDRE_p50"))
            .combine(stats10)
            .combine(stats20)
        )
        return ee.Feature(None, props)

    def _eval_features_chunked(feat_builders: List, chunk_size: int = 3, label: str = "chunk") -> pd.DataFrame:
        rows = []
        for idx in range(0, len(feat_builders), chunk_size):
            batch = feat_builders[idx : idx + chunk_size]
            try:
                info = _with_retry(lambda b=batch: ee.FeatureCollection(b).getInfo(), retries=2, delay_sec=4.0)
                rows.extend([ft["properties"] for ft in info["features"]])
            except Exception as exc:
                print(f"    [{label}] batch {idx}-{idx+len(batch)-1} fallback to single-feature calls ({exc})")
                for single in batch:
                    info = _with_retry(lambda s=single: ee.Feature(s).getInfo(), retries=3, delay_sec=5.0)
                    rows.append(info["properties"])
        return pd.DataFrame(rows)

    # 1. Monthly (108 months: 2017-01 .. 2025-12) in 3-month batches
    monthly_csv = RAW_EXPORTS_DIR / "gee_monthly_indices_raw.csv"
    if not monthly_csv.exists():
        m_feats = []
        for y in range(START_YEAR, END_YEAR + 1):
            for m in range(1, 13):
                st = ee.Date.fromYMD(y, m, 1)
                en = st.advance(1, "month")
                m_feats.append(
                    _summarize(
                        s2_prep.filterDate(st, en),
                        {
                            "year": y,
                            "month": m,
                            "start_date": st.format("YYYY-MM-dd"),
                            "end_date": en.advance(-1, "day").format("YYYY-MM-dd"),
                        },
                    )
                )
        print(f"  Computing 108 monthly composites in GEE (scale=10m/20m, crs={TARGET_CRS})...")
        _eval_features_chunked(m_feats, chunk_size=3, label="monthly").to_csv(
            monthly_csv, index=False, encoding="utf-8"
        )
    else:
        print(f"  Using existing {monthly_csv.name}")

    # 2. Seasonal (36 seasons: Winter/Spring/Summer/Autumn for 2017..2025)
    seasonal_csv = RAW_EXPORTS_DIR / "gee_seasonal_indices_raw.csv"
    if not seasonal_csv.exists():
        seasons_def = [
            ("Winter", -1, 12, 0, 3),
            ("Spring", 0, 3, 0, 6),
            ("Summer", 0, 6, 0, 9),
            ("Autumn", 0, 9, 0, 12),
        ]
        s_feats = []
        for sy in range(START_YEAR, END_YEAR + 1):
            for name, oy, sm, ey, em in seasons_def:
                st = ee.Date.fromYMD(sy + oy, sm, 1)
                en = ee.Date.fromYMD(sy + ey, em, 1)
                s_feats.append(
                    _summarize(
                        s2_prep.filterDate(st, en),
                        {
                            "season_year": sy,
                            "season": name,
                            "start_date": st.format("YYYY-MM-dd"),
                            "end_date": en.advance(-1, "day").format("YYYY-MM-dd"),
                        },
                    )
                )
        print(f"  Computing 36 seasonal composites in GEE...")
        _eval_features_chunked(s_feats, chunk_size=2, label="seasonal").to_csv(
            seasonal_csv, index=False, encoding="utf-8"
        )
    else:
        print(f"  Using existing {seasonal_csv.name}")

    # 3. Annual (9 years: 2017..2025) one year at a time to stay well within interactive compute limits
    annual_csv = RAW_EXPORTS_DIR / "gee_annual_indices_raw.csv"
    if not annual_csv.exists():
        a_feats = []
        for ay in range(START_YEAR, END_YEAR + 1):
            st = ee.Date.fromYMD(ay, 1, 1)
            en = ee.Date.fromYMD(ay + 1, 1, 1)
            a_feats.append(
                _summarize(
                    s2_prep.filterDate(st, en),
                    {
                        "year": ay,
                        "start_date": st.format("YYYY-MM-dd"),
                        "end_date": en.advance(-1, "day").format("YYYY-MM-dd"),
                    },
                )
            )
        print(f"  Computing 9 annual composites in GEE...")
        _eval_features_chunked(a_feats, chunk_size=1, label="annual").to_csv(
            annual_csv, index=False, encoding="utf-8"
        )
    else:
        print(f"  Using existing {annual_csv.name}")

    return str(monthly_csv), str(seasonal_csv), str(annual_csv)


def _download_image_tiled(
    ee,
    image,
    band_names: Sequence[str],
    scale_m: int,
    out_path: Path,
    boundary_utm: gpd.GeoDataFrame,
    nodata_val: float = -9999.0,
    dtype_str: str = "float32",
) -> Path:
    """Download a GEE image at exact native scale (10m or 20m) via grid tiles and merge into one local GeoTIFF."""
    minx, miny, maxx, maxy = boundary_utm.total_bounds
    geom_union = boundary_utm.geometry.union_all()

    # Size tiles safely under GEE getDownloadURL 50MB uncompressed cap (~12-18 MB per tile max)
    # 10m with <=4 bands: ~11.5km x 12km tiles; 20m: ~23km x 24km tiles
    max_bytes_per_tile = 16 * 1024 * 1024
    bytes_per_pixel = 4 * len(band_names)
    max_pixels_per_tile = max(250_000, max_bytes_per_tile // max(bytes_per_pixel, 4))
    tile_side_m = int(math.sqrt(max_pixels_per_tile) * scale_m)
    # Snap tile_side_m to clean multiple of scale_m
    tile_side_m = max(scale_m * 100, (tile_side_m // scale_m) * scale_m)

    nx = int(math.ceil((maxx - minx) / tile_side_m))
    ny = int(math.ceil((maxy - miny) / tile_side_m))

    tile_paths: List[Path] = []
    tmp_dir = out_path.parent / f"_tmp_{out_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    prepared_img = image.select(list(band_names)).unmask(nodata_val, False)
    if dtype_str == "int32":
        prepared_img = prepared_img.toInt32()
    else:
        prepared_img = prepared_img.toFloat()

    tile_jobs = []
    for ix in range(nx):
        for iy in range(ny):
            tx0 = minx + ix * tile_side_m
            tx1 = min(maxx + scale_m, tx0 + tile_side_m)
            ty0 = miny + iy * tile_side_m
            ty1 = min(maxy + scale_m, ty0 + tile_side_m)
            tile_poly = box(tx0, ty0, tx1, ty1)
            if geom_union.intersects(tile_poly):
                tile_jobs.append((ix, iy, tx0, ty0, tx1, ty1))

    def _process_tile(job):
        ix, iy, tx0, ty0, tx1, ty1 = job
        tile_tif = tmp_dir / f"tile_{ix}_{iy}.tif"
        if tile_tif.exists() and tile_tif.stat().st_size > 0:
            return tile_tif
        tile_region = ee.Geometry.Rectangle([tx0, ty0, tx1, ty1], proj=TARGET_CRS, geodesic=False)

        def _fetch_tile() -> bytes:
            url = prepared_img.getDownloadURL(
                {
                    "name": f"tile_{ix}_{iy}",
                    "bands": list(band_names),
                    "region": tile_region,
                    "scale": scale_m,
                    "crs": TARGET_CRS,
                    "format": "GEO_TIFF",
                }
            )
            with urllib.request.urlopen(url, timeout=180) as resp:
                return resp.read()

        raw_bytes = _with_retry(_fetch_tile, retries=3, delay_sec=4.0)
        if raw_bytes[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                tif_members = [m for m in zf.namelist() if m.endswith(".tif")]
                tile_tif.write_bytes(zf.read(tif_members[0]))
        else:
            tile_tif.write_bytes(raw_bytes)
        return tile_tif

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_process_tile, j) for j in tile_jobs]
        for fut in as_completed(futures):
            tile_paths.append(fut.result())
    tile_paths.sort()

    # Mosaic tiles and clip tightly to Guelma polygon preserving NoData
    srcs = [rasterio.open(p) for p in tile_paths]
    try:
        mosaic, out_transform = rio_merge(srcs, nodata=nodata_val)
        meta = srcs[0].meta.copy()
        meta.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_transform,
                "crs": TARGET_CRS,
                "nodata": nodata_val,
                "compress": "DEFLATE",
            }
        )
        merged_tmp = tmp_dir / "merged_unclipped.tif"
        with rasterio.open(merged_tmp, "w", **meta) as dst:
            dst.write(mosaic)
    finally:
        for s in srcs:
            s.close()

    with rasterio.open(merged_tmp) as src:
        clipped, clipped_transform = rio_mask(
            src,
            list(boundary_utm.geometry),
            crop=True,
            nodata=nodata_val,
        )
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "height": clipped.shape[1],
                "width": clipped.shape[2],
                "transform": clipped_transform,
                "nodata": nodata_val,
                "compress": "DEFLATE",
            }
        )
        with rasterio.open(out_path, "w", **out_meta) as dst:
            dst.write(clipped)
            for idx, bname in enumerate(band_names, start=1):
                dst.set_band_description(idx, bname)

    # Clean up temporary tiles
    for p in tile_paths:
        p.unlink(missing_ok=True)
    merged_tmp.unlink(missing_ok=True)
    tmp_dir.rmdir()
    return out_path


def download_gee_rasters_local() -> List[str]:
    """Download core Sentinel-2 annual, seasonal, and coverage GeoTIFFs locally at native 10 m and 20 m."""
    ee = _import_and_init_ee()
    guelma_geom, _, _ = _get_guelma_geometry(ee)
    boundary_utm = gpd.read_file(BOUNDARY_FILE).to_crs(TARGET_CRS)
    s2_prep = _build_prepared_s2_collection(ee, guelma_geom)

    downloaded: List[str] = []

    # 1. Annual 2017 & 2025 (10 m and 20 m)
    for ay in (2017, 2025):
        sub = s2_prep.filterDate(f"{ay}-01-01", f"{ay + 1}-01-01")
        out_10 = RAW_EXPORTS_DIR / f"sentinel2_annual_{ay}_10m.tif"
        if not out_10.exists():
            print(f"  Downloading {out_10.name} (10 m, 6 bands)...")
            _download_image_tiled(
                ee,
                sub.select(["B4", "B3", "B2", "B8", "NDVI", "EVI"]).median(),
                ["B4", "B3", "B2", "B8", "NDVI", "EVI"],
                10,
                out_10,
                boundary_utm,
            )
        downloaded.append(str(out_10))

        out_20 = RAW_EXPORTS_DIR / f"sentinel2_annual_{ay}_20m.tif"
        if not out_20.exists():
            print(f"  Downloading {out_20.name} (20 m, 2 bands)...")
            _download_image_tiled(
                ee,
                sub.select(["NDMI", "NDRE"]).median(),
                ["NDMI", "NDRE"],
                20,
                out_20,
                boundary_utm,
            )
        downloaded.append(str(out_20))

    # 2. Multi-year complete seasonal composites (2018-2025) at 10 m and 20 m
    seasons_def = [
        ("winter", -1, 12, 0, 3),
        ("spring", 0, 3, 0, 6),
        ("summer", 0, 6, 0, 9),
        ("autumn", 0, 9, 0, 12),
    ]
    for name, oy, sm, ey, em in seasons_def:
        col = ee.ImageCollection([])
        for sy in range(2018, END_YEAR + 1):
            st = ee.Date.fromYMD(sy + oy, sm, 1)
            en = ee.Date.fromYMD(sy + ey, em, 1)
            col = col.merge(s2_prep.filterDate(st, en))

        out_s10 = RAW_EXPORTS_DIR / f"sentinel2_seasonal_{name}_10m.tif"
        if not out_s10.exists():
            print(f"  Downloading {out_s10.name} (10 m, 2 bands)...")
            _download_image_tiled(
                ee,
                col.select(["NDVI", "EVI"]).median(),
                ["NDVI", "EVI"],
                10,
                out_s10,
                boundary_utm,
            )
        downloaded.append(str(out_s10))

        out_s20 = RAW_EXPORTS_DIR / f"sentinel2_seasonal_{name}_20m.tif"
        if not out_s20.exists():
            print(f"  Downloading {out_s20.name} (20 m, 2 bands)...")
            _download_image_tiled(
                ee,
                col.select(["NDMI", "NDRE"]).median(),
                ["NDMI", "NDRE"],
                20,
                out_s20,
                boundary_utm,
            )
        downloaded.append(str(out_s20))

    # 3. Valid observation count (2017-2025) at 20 m
    out_cov = RAW_EXPORTS_DIR / "sentinel2_valid_obs_count_2017_2025_20m.tif"
    if not out_cov.exists():
        print(f"  Downloading {out_cov.name} (20 m, int32)...")
        valid_count = (
            s2_prep.filterDate("2017-01-01", f"{END_YEAR + 1}-01-01")
            .select("NDVI")
            .count()
            .rename("valid_obs_count")
        )
        _download_image_tiled(
            ee,
            valid_count,
            ["valid_obs_count"],
            20,
            out_cov,
            boundary_utm,
            nodata_val=-9999,
            dtype_str="int32",
        )
    downloaded.append(str(out_cov))

    return downloaded


def submit_gee_batch_raster_exports(drive_folder: str = "FieldShift_Sentinel2_Guelma") -> List[str]:
    """Launch GEE batch GeoTIFF exports to Google Drive with explicit -9999 NoData exterior masking."""
    ee = _import_and_init_ee()
    guelma_geom, _, _ = _get_guelma_geometry(ee)
    s2_prep = _build_prepared_s2_collection(ee, guelma_geom)
    mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)
    ensure_single_drive_folder(ee, drive_folder)

    tasks_launched = []

    def _launch(image, desc: str, scale: int, is_int: bool = False):
        bmask = mask_10m if scale == 10 else mask_20m
        export_img = image.updateMask(bmask).unmask(NODATA_VALUE, False)
        export_img = export_img.toInt32() if is_int else export_img.toFloat()
        task = ee.batch.Export.image.toDrive(
            image=export_img,
            description=desc,
            folder=drive_folder,
            fileNamePrefix=desc,
            region=guelma_geom,
            scale=scale,
            crs=TARGET_CRS,
            maxPixels=1e10,
            fileFormat="GeoTIFF",
            formatOptions={"cloudOptimized": True, "noData": NODATA_VALUE},
        )
        task.start()
        tasks_launched.append(f"{desc} ({task.id})")

    for ay in (2017, 2025):
        sub = s2_prep.filterDate(f"{ay}-01-01", f"{ay + 1}-01-01")
        _launch(sub.select(["B4", "B3", "B2", "B8", "NDVI", "EVI"]).median(), f"sentinel2_annual_{ay}_10m", 10)
        _launch(sub.select(["NDMI", "NDRE"]).median(), f"sentinel2_annual_{ay}_20m", 20)

    seasons_def = [
        ("winter", -1, 12, 0, 3),
        ("spring", 0, 3, 0, 6),
        ("summer", 0, 6, 0, 9),
        ("autumn", 0, 9, 0, 12),
    ]
    for name, oy, sm, ey, em in seasons_def:
        col = ee.ImageCollection([])
        for sy in range(2018, END_YEAR + 1):
            st = ee.Date.fromYMD(sy + oy, sm, 1)
            en = ee.Date.fromYMD(sy + ey, em, 1)
            col = col.merge(s2_prep.filterDate(st, en))
        _launch(col.select(["NDVI", "EVI"]).median(), f"sentinel2_seasonal_{name}_10m", 10)
        _launch(col.select(["NDMI", "NDRE"]).median(), f"sentinel2_seasonal_{name}_20m", 20)

    valid_count = s2_prep.filterDate("2017-01-01", f"{END_YEAR + 1}-01-01").select("NDVI").count()
    valid_count = ee.Image(0).where(valid_count.gt(0), valid_count).rename("valid_obs_count")
    _launch(valid_count, "sentinel2_valid_obs_count_2017_2025_20m", 20, is_int=True)

    return tasks_launched
