"""Phase C Orchestrator: Scenario 3 Resumable Batch Execution, Ledger & Verification."""

import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from .config import (
    BOUNDARY_FILE,
    CLOUD_PROB_THRESHOLD,
    END_YEAR,
    EVI_DENOM_THRESHOLD,
    GEE_PROJECT,
    NODATA_VALUE,
    QUALITY_DIR,
    RAW_DIR,
    RAW_EXPORTS_DIR,
    RAW_METADATA_DIR,
    REFLECTANCE_SCALE,
    S2_CLOUD_PROB_ID,
    S2_COLLECTION_ID,
    SCL_EXCLUDED_CLASSES,
    START_YEAR,
    TARGET_CRS,
)
from .drive_export_manager import (
    download_and_verify_task_outputs,
    ensure_single_drive_folder,
)
from .phase2_gee_client import (
    _build_boundary_masks,
    _compute_static_boundary_counts,
    _get_guelma_geometry,
    _import_and_init_ee,
)

PHASE_C_RAW_DIR = RAW_DIR / "phaseC_2017_2025"
DRIVE_FOLDER_NAME = "FieldShift_Sentinel2_PhaseC_2017_2025"
LEDGER_PATH = QUALITY_DIR / "phaseC_ledger.json"
PHASE_B_MONTHLY_BENCHMARK_EECU = 5823.6221

QUARTERS = [
    ("Q1", [1, 2, 3]),
    ("Q2", [4, 5, 6]),
    ("Q3", [7, 8, 9]),
    ("Q4", [10, 11, 12]),
]

SEASONS_DEF = [
    ("Winter", -1, 12, 0, 3),
    ("Spring", 0, 3, 0, 6),
    ("Summer", 0, 6, 0, 9),
    ("Autumn", 0, 9, 0, 12),
]

# Representative contrasting months anchored to Guelma climate extremes (2017-2025)
SELECTED_MONTHLY_RASTERS = [
    ("2019-04", "Wet-year peak spring (2019: 1,010 mm)"),
    ("2022-07", "Dry-year peak summer drought (2022: 503 mm)"),
    ("2024-03", "Phase B validated spring benchmark (2024: 529 mm)"),
    ("2025-04", "Latest year peak spring (2025: 718 mm)"),
]


def _load_ledger() -> Dict:
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    PHASE_C_RAW_DIR.mkdir(parents=True, exist_ok=True)
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {
        "gee_project": GEE_PROJECT,
        "drive_folder_name": DRIVE_FOLDER_NAME,
        "drive_folder_id": None,
        "evi_denom_threshold": EVI_DENOM_THRESHOLD,
        "nodata_value": NODATA_VALUE,
        "static_counts": {},
        "preflight": {},
        "batches": {},
        "total_measured_eecu_seconds": 0.0,
    }


def _save_ledger(ledger: Dict) -> None:
    total_eecu = sum(
        float(b.get("batch_eecu_usage_seconds") or 0.0)
        for b in ledger.get("batches", {}).values()
    )
    ledger["total_measured_eecu_seconds"] = round(total_eecu, 4)
    ledger["updated_utc"] = datetime.now(timezone.utc).isoformat()
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")


def _check_quota_warnings(warn_list: List[str]) -> None:
    for msg in warn_list:
        low = msg.lower()
        if "restricted mode" in low or "quota" in low or "limit exceeded" in low:
            raise RuntimeError(f"GEE quota/restricted-mode warning detected — stopping immediately: {msg}")


def _poll_tasks(tasks: List[Dict], captured_warnings: List, poll_sec: int = 15, timeout_sec: int = 3600) -> List[Dict]:
    t0 = time.monotonic()
    statuses = {}
    terminal = {"COMPLETED", "FAILED", "CANCELLED", "CANCEL_REQUESTED"}

    while True:
        _check_quota_warnings([str(w.message) for w in captured_warnings])
        all_done = True
        for item in tasks:
            name = item["name"]
            if name in statuses and statuses[name].get("state") in terminal:
                continue
            st = item["task"].status()
            statuses[name] = st
            state = st.get("state", "UNKNOWN")
            err = str(st.get("error_message") or "")
            if state == "FAILED" and ("quota" in err.lower() or "restricted" in err.lower()):
                raise RuntimeError(f"Task {name} halted due to quota/restriction: {err}")
            if state not in terminal:
                all_done = False

        print(
            f"  [t+{int(time.monotonic() - t0)}s] "
            + ", ".join(f"{k}={v.get('state')}" for k, v in statuses.items()),
            flush=True,
        )
        if all_done:
            break
        if time.monotonic() - t0 > timeout_sec:
            raise TimeoutError(f"Tasks timed out after {timeout_sec}s")
        time.sleep(poll_sec)

    out = []
    for item in tasks:
        st = statuses[item["name"]]
        cre, sta, upd = st.get("creation_timestamp_ms"), st.get("start_timestamp_ms"), st.get("update_timestamp_ms")
        out.append(
            {
                "name": item["name"],
                "file_prefix": item["file_prefix"],
                "kind": item["kind"],
                "task_id": st.get("id"),
                "state": st.get("state"),
                "error_message": st.get("error_message"),
                "batch_eecu_usage_seconds": st.get("batch_eecu_usage_seconds"),
                "run_seconds": round((upd - sta) / 1000.0, 2) if sta and upd else None,
                "total_wall_seconds": round((upd - cre) / 1000.0, 2) if cre and upd else None,
                "destination_uris": st.get("destination_uris"),
            }
        )
    return out


def _build_prepared_joined_s2(ee, guelma_geom, start_iso: str, end_iso: str):
    """Build cloud-masked, scaled S2 + Cloud Probability collection for [start_iso, end_iso)."""
    s2 = (
        ee.ImageCollection(S2_COLLECTION_ID)
        .filterBounds(guelma_geom)
        .filterDate(start_iso, end_iso)
    )
    cp = (
        ee.ImageCollection(S2_CLOUD_PROB_ID)
        .filterBounds(guelma_geom)
        .filterDate(start_iso, end_iso)
    )
    joined = ee.ImageCollection(
        ee.Join.saveFirst(matchKey="cloud_prob_img", outer=True).apply(
            s2,
            cp,
            ee.Filter.equals(leftField="system:index", rightField="system:index"),
        )
    )
    excluded_codes = list(SCL_EXCLUDED_CLASSES.keys())

    def _prep(img):
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
        cmask = valid_scl.And(valid_cp)

        blue = img.select("B2").multiply(REFLECTANCE_SCALE)
        green = img.select("B3").multiply(REFLECTANCE_SCALE)
        red = img.select("B4").multiply(REFLECTANCE_SCALE)
        re1 = img.select("B5").multiply(REFLECTANCE_SCALE)
        nir = img.select("B8").multiply(REFLECTANCE_SCALE)
        nir_narrow = img.select("B8A").multiply(REFLECTANCE_SCALE)
        swir1 = img.select("B11").multiply(REFLECTANCE_SCALE)

        ndvi_den = nir.add(red)
        ndvi = nir.subtract(red).divide(ndvi_den.where(ndvi_den.eq(0), 1e-6)).rename("NDVI")

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
            ee.Image.cat([blue.rename("B2"), green.rename("B3"), red.rename("B4"), nir.rename("B8"), ndvi, evi, ndmi, ndre, is_scl2])
            .updateMask(cmask)
            .copyProperties(img, ["system:time_start"])
        )

    return s2, joined, joined.map(_prep)


def _build_stacked_summary_feature(ee, guelma_geom, mask_10m, mask_20m, total_px_10: int, total_px_20: int, start_iso: str, end_iso: str, extra_props: Dict):
    """Build one period Feature using Phase B validated 2-pass stacked unweighted reductions."""
    s2_raw, joined, s2_prep = _build_prepared_joined_s2(ee, guelma_geom, start_iso, end_iso)
    img_count = s2_raw.size()
    cp_matched = joined.filter(ee.Filter.notNull(["cloud_prob_img"])).size()

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

    def _s10():
        t10 = s2_prep.select(["NDVI", "EVI"]).reduce(temp_reducer)
        obs10 = t10.select("NDVI_count").unmask(0).rename("valid_obs_10m")
        evi_obs = t10.select("EVI_count").unmask(0).rename("evi_valid_obs_10m")
        return ee.Image.cat(
            [
                t10.select(["NDVI_median", "EVI_median"]).rename(["NDVI", "EVI"]),
                obs10,
                evi_obs,
            ]
        ).updateMask(mask_10m)

    def _s20():
        t20 = s2_prep.select(["NDMI", "NDRE"]).reduce(temp_reducer)
        scl2 = s2_prep.select("is_scl2").reduce(scl2_reducer)
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

    stack10 = ee.Image(ee.Algorithms.If(img_count.gt(0), _s10(), empty_10m))
    stack20 = ee.Image(ee.Algorithms.If(img_count.gt(0), _s20(), empty_20m))

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
        .set("cloud_prob_matched_images", cp_matched)
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


def _derive_summary_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for idx, res in (("NDVI", 10), ("EVI", 10), ("NDMI", 20), ("NDRE", 20)):
        tot = pd.to_numeric(out[f"total_pixels_{res}m"], errors="coerce")
        cnt = pd.to_numeric(out[f"{idx}_count"], errors="coerce").fillna(0)
        out[f"{idx}_valid_pixels"] = cnt.astype(int)
        out[f"{idx}_valid_pct"] = (cnt / tot * 100.0).round(4)
        out[f"{idx}_missing_pct"] = (100.0 - out[f"{idx}_valid_pct"]).round(4)

    out["EVI_excluded_composite_pixels"] = (out["NDVI_valid_pixels"] - out["EVI_valid_pixels"]).astype(int)
    if {"valid_obs_10m_mean", "valid_obs_10m_count", "evi_valid_obs_10m_mean", "evi_valid_obs_10m_count"}.issubset(out.columns):
        tot_ndvi_obs = pd.to_numeric(out["valid_obs_10m_mean"], errors="coerce") * pd.to_numeric(out["valid_obs_10m_count"], errors="coerce")
        tot_evi_obs = pd.to_numeric(out["evi_valid_obs_10m_mean"], errors="coerce") * pd.to_numeric(out["evi_valid_obs_10m_count"], errors="coerce")
        out["evi_obs_excluded_total_10m"] = (tot_ndvi_obs - tot_evi_obs).round(0).fillna(0).astype("int64")
    if {"scl2_obs_mean", "scl2_obs_count", "valid_obs_20m_mean", "valid_obs_20m_count"}.issubset(out.columns):
        scl2_tot = pd.to_numeric(out["scl2_obs_mean"], errors="coerce") * pd.to_numeric(out["scl2_obs_count"], errors="coerce")
        ret_tot = pd.to_numeric(out["valid_obs_20m_mean"], errors="coerce") * pd.to_numeric(out["valid_obs_20m_count"], errors="coerce")
        out["scl2_total_obs_20m"] = scl2_tot.round(0).fillna(0).astype("int64")
        out["retained_total_obs_20m"] = ret_tot.round(0).fillna(0).astype("int64")
        out["scl2_share_pct"] = np.where(ret_tot > 0, (scl2_tot / ret_tot * 100.0).round(4), 0.0)
    return out


def _validate_summary_csv(csv_path: Path, expected_rows: int) -> Dict:
    df = pd.read_csv(csv_path)
    df = _derive_summary_metrics(df)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    max_cov = float(df[["NDVI_valid_pct", "EVI_valid_pct", "NDMI_valid_pct", "NDRE_valid_pct"]].max().max())
    min_cov = float(df[["NDVI_valid_pct", "EVI_valid_pct", "NDMI_valid_pct", "NDRE_valid_pct"]].min().min())
    if len(df) != expected_rows:
        raise AssertionError(f"{csv_path.name}: expected {expected_rows} rows, got {len(df)}")
    if max_cov > 100.0 + 1e-4 or min_cov < 0.0:
        raise AssertionError(f"{csv_path.name}: coverage out of [0, 100]%: [{min_cov}, {max_cov}]")
    return {
        "rows": len(df),
        "min_coverage_pct": min_cov,
        "max_coverage_pct": max_cov,
        "evi_excluded_composite_pixels_sum": int(df["EVI_excluded_composite_pixels"].sum()),
        "evi_obs_excluded_total_10m_sum": int(df.get("evi_obs_excluded_total_10m", pd.Series([0])).sum()),
    }


def _validate_geotiff_local(tif_path: Path, expected_scale_m: float, expected_bands: int) -> Dict:
    gdf = gpd.read_file(BOUNDARY_FILE).to_crs(TARGET_CRS)
    geoms = list(gdf.geometry)
    with rasterio.open(tif_path) as src:
        res_x, res_y = float(src.res[0]), float(src.res[1])
        crs_str = str(src.crs)
        nodata_tag = src.nodata
        bands = src.count
        outside = geometry_mask(geoms, out_shape=(src.height, src.width), transform=src.transform, all_touched=True)
        b1 = src.read(1)
        ext_vals = b1[outside]
        zero_ext = int(np.sum(ext_vals == 0))
        non_nd_ext = int(np.sum(ext_vals != NODATA_VALUE))
        in_vals = b1[~outside]
        valid_in = in_vals[in_vals != NODATA_VALUE]
        if crs_str != TARGET_CRS or abs(res_x - expected_scale_m) > 1e-4 or abs(res_y - expected_scale_m) > 1e-4:
            raise AssertionError(f"{tif_path.name}: CRS/scale mismatch ({crs_str}, {res_x}x{res_y})")
        if bands != expected_bands:
            raise AssertionError(f"{tif_path.name}: expected {expected_bands} bands, got {bands}")
        if nodata_tag != NODATA_VALUE or zero_ext > 0 or non_nd_ext > 0:
            raise AssertionError(f"{tif_path.name}: exterior NoData defect (nodata={nodata_tag}, zeros={zero_ext}, non_-9999={non_nd_ext})")
        return {
            "crs": crs_str,
            "res_m": [res_x, res_y],
            "shape": [src.height, src.width],
            "bands": bands,
            "nodata": nodata_tag,
            "outside_zero_count": zero_ext,
            "outside_non_nodata_count": non_nd_ext,
            "inside_valid_pixels": int(valid_in.size),
            "inside_band1_min": float(np.min(valid_in)) if valid_in.size else None,
            "inside_band1_max": float(np.max(valid_in)) if valid_in.size else None,
        }


def step_preflight() -> Dict:
    """Verify GEE project registration, quota restrictions, Drive folder, and static counts."""
    ledger = _load_ledger()
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        guelma_geom, boundary_source, asset_props = _get_guelma_geometry(ee)
        folder_id = ensure_single_drive_folder(ee, DRIVE_FOLDER_NAME)
        mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)
        c10, c20 = _compute_static_boundary_counts(ee, guelma_geom, mask_10m, mask_20m)

        # Tiny access check: recent 10-day S2 count + project registration
        probe_cnt = int(
            ee.ImageCollection(S2_COLLECTION_ID)
            .filterBounds(guelma_geom)
            .filterDate("2024-03-01", "2024-03-11")
            .size()
            .getInfo()
        )
        warn_msgs = [str(w.message) for w in captured_warnings]
        _check_quota_warnings(warn_msgs)

    ledger["drive_folder_id"] = folder_id
    ledger["static_counts"] = {"total_pixels_10m": c10, "total_pixels_20m": c20}
    ledger["preflight"] = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "gee_project": GEE_PROJECT,
        "boundary_source": boundary_source,
        "asset_properties_sample": bool(asset_props),
        "probe_2024_03_01_10_s2_count": probe_cnt,
        "warnings": warn_msgs,
        "status": "READY_UNRESTRICTED",
    }
    _save_ledger(ledger)
    print(f"[Phase C Preflight] OK | project={GEE_PROJECT} | folder={folder_id} | px10={c10} | px20={c20} | warnings={len(warn_msgs)}")
    return ledger


def _run_table_batches(jobs: List[Dict], validate_fn_map: Dict) -> Dict:
    """Execute one or more GEE table export batches with ledger tracking and MD5 verification."""
    ledger = _load_ledger()
    if not ledger.get("drive_folder_id") or not ledger.get("static_counts"):
        ledger = step_preflight()

    folder_id = ledger["drive_folder_id"]
    c10 = int(ledger["static_counts"]["total_pixels_10m"])
    c20 = int(ledger["static_counts"]["total_pixels_20m"])

    pending = []
    for job in jobs:
        bname = job["name"]
        rec = ledger["batches"].get(bname)
        if rec and rec.get("state") == "COMPLETED" and rec.get("checksum_verified"):
            local_p = PHASE_C_RAW_DIR / f"{bname}.csv"
            if local_p.exists():
                print(f"  [Skip] {bname} already COMPLETED and MD5 verified.")
                continue
        pending.append(job)

    if not pending:
        return ledger

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        guelma_geom, _, _ = _get_guelma_geometry(ee)
        mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)

        launched = []
        for job in pending:
            fc = job["build_fc"](ee, guelma_geom, mask_10m, mask_20m, c10, c20)
            task = ee.batch.Export.table.toDrive(
                collection=fc,
                description=job["name"],
                folder=DRIVE_FOLDER_NAME,
                fileNamePrefix=job["name"],
                fileFormat="CSV",
            )
            task.start()
            launched.append(
                {
                    "name": job["name"],
                    "file_prefix": job["name"],
                    "kind": "table",
                    "task": task,
                    "expected_rows": job["expected_rows"],
                    "meta": job.get("meta", {}),
                }
            )

        print(f"[Phase C] Polling {len(launched)} batch task(s): {[x['name'] for x in launched]}")
        results = _poll_tasks(launched, captured_warnings)
        failed = [r for r in results if r["state"] != "COMPLETED"]
        if failed:
            for r in failed:
                ledger["batches"][r["name"]] = r
            _save_ledger(ledger)
            raise RuntimeError(f"Phase C batch task(s) failed: {failed}")

        downloaded = download_and_verify_task_outputs(ee, results, PHASE_C_RAW_DIR, fallback_folder_id=folder_id)
        warn_msgs = [str(w.message) for w in captured_warnings]
        _check_quota_warnings(warn_msgs)

    for res, job in zip(results, launched):
        bname = res["name"]
        dl = downloaded[f"{bname}.csv"]
        qa_summary = validate_fn_map[bname](Path(dl["path"]), job["expected_rows"])
        ledger["batches"][bname] = {
            **res,
            **job["meta"],
            "file": dl["path"],
            "size_bytes": dl["size_bytes"],
            "md5_checksum": dl["md5_checksum"],
            "checksum_verified": dl["checksum_verified"],
            "local_validation": qa_summary,
            "warnings": warn_msgs,
        }
        eecu = float(res["batch_eecu_usage_seconds"] or 0.0)
        print(f"  [Verified] {bname}: {eecu:.2f} EECU-s | {qa_summary}")

    _save_ledger(ledger)
    return ledger


def step_scenes() -> Dict:
    """Export full 2016-12 to 2025-12 Sentinel-2 scene metadata inventory in 1 lightweight task."""
    def _build_scenes_fc(ee, guelma_geom, *_args):
        s2 = ee.ImageCollection(S2_COLLECTION_ID).filterBounds(guelma_geom).filterDate("2016-12-01", f"{END_YEAR + 1}-01-01")
        cp = ee.ImageCollection(S2_CLOUD_PROB_ID).filterBounds(guelma_geom).filterDate("2016-12-01", f"{END_YEAR + 1}-01-01")
        joined = ee.ImageCollection(
            ee.Join.saveFirst(matchKey="cloud_prob_img", outer=True).apply(
                s2, cp, ee.Filter.equals(leftField="system:index", rightField="system:index")
            )
        )

        def _feat(im):
            im = ee.Image(im)
            dt = ee.Date(im.get("system:time_start"))
            return ee.Feature(
                None,
                {
                    "system_index": im.get("system:index"),
                    "date": dt.format("YYYY-MM-dd"),
                    "year": dt.get("year"),
                    "month": dt.get("month"),
                    "mgrs_tile": im.get("MGRS_TILE"),
                    "spacecraft": im.get("SPACECRAFT_NAME"),
                    "cloudy_pixel_percentage": im.get("CLOUDY_PIXEL_PERCENTAGE"),
                    "has_cloud_prob": ee.Algorithms.If(im.get("cloud_prob_img"), 1, 0),
                },
            )

        return joined.map(_feat)

    def _val_scenes(csv_path: Path, _expected):
        df = pd.read_csv(csv_path)
        return {
            "total_scenes": len(df),
            "scenes_2017_2025": int(df[df["year"].between(START_YEAR, END_YEAR)].shape[0]),
            "cloud_prob_matched": int(df["has_cloud_prob"].sum()),
        }

    job = {
        "name": "sentinel2_scenes_2017_2025",
        "expected_rows": -1,
        "meta": {"kind_group": "scenes_inventory"},
        "build_fc": _build_scenes_fc,
    }
    return _run_table_batches([job], {"sentinel2_scenes_2017_2025": _val_scenes})


def _make_monthly_quarter_job(year: int, qname: str, months: List[int]) -> Dict:
    bname = f"phaseC_monthly_{year}_{qname}"

    def _build(ee, guelma_geom, mask_10m, mask_20m, c10, c20):
        feats = []
        for m in months:
            st = ee.Date.fromYMD(year, m, 1)
            en = st.advance(1, "month")
            feats.append(
                _build_stacked_summary_feature(
                    ee,
                    guelma_geom,
                    mask_10m,
                    mask_20m,
                    c10,
                    c20,
                    st.format("YYYY-MM-dd"),
                    en.format("YYYY-MM-dd"),
                    {
                        "year": year,
                        "month": m,
                        "year_month": f"{year}-{m:02d}",
                        "start_date": st.format("YYYY-MM-dd"),
                        "end_date": en.advance(-1, "day").format("YYYY-MM-dd"),
                    },
                )
            )
        return ee.FeatureCollection(feats)

    return {
        "name": bname,
        "expected_rows": len(months),
        "meta": {"kind_group": "monthly", "year": year, "quarter": qname, "months": months},
        "build_fc": _build,
    }


def step_monthly_quarters(year_quarters: List[Tuple[int, str, List[int]]]) -> Dict:
    jobs = [_make_monthly_quarter_job(y, qn, ms) for y, qn, ms in year_quarters]
    val_map = {j["name"]: _validate_summary_csv for j in jobs}
    return _run_table_batches(jobs, val_map)


def step_seasonal_years(years: List[int]) -> Dict:
    jobs = []
    val_map = {}
    for sy in years:
        bname = f"phaseC_seasonal_{sy}"

        def _build(ee, guelma_geom, mask_10m, mask_20m, c10, c20, season_year=sy):
            feats = []
            for sname, oy, sm, ey, em in SEASONS_DEF:
                st = ee.Date.fromYMD(season_year + oy, sm, 1)
                en = ee.Date.fromYMD(season_year + ey, em, 1)
                feats.append(
                    _build_stacked_summary_feature(
                        ee,
                        guelma_geom,
                        mask_10m,
                        mask_20m,
                        c10,
                        c20,
                        st.format("YYYY-MM-dd"),
                        en.format("YYYY-MM-dd"),
                        {
                            "season_year": season_year,
                            "season": sname,
                            "start_date": st.format("YYYY-MM-dd"),
                            "end_date": en.advance(-1, "day").format("YYYY-MM-dd"),
                        },
                    )
                )
            return ee.FeatureCollection(feats)

        jobs.append(
            {
                "name": bname,
                "expected_rows": 4,
                "meta": {"kind_group": "seasonal", "season_year": sy},
                "build_fc": _build,
            }
        )
        val_map[bname] = _validate_summary_csv
    return _run_table_batches(jobs, val_map)


def step_annual_years(years: List[int], chunk_label: Optional[str] = None) -> Dict:
    bname = chunk_label or f"phaseC_annual_{'_'.join(str(y) for y in years)}"

    def _build(ee, guelma_geom, mask_10m, mask_20m, c10, c20):
        feats = []
        for ay in years:
            st = ee.Date.fromYMD(ay, 1, 1)
            en = ee.Date.fromYMD(ay + 1, 1, 1)
            feats.append(
                _build_stacked_summary_feature(
                    ee,
                    guelma_geom,
                    mask_10m,
                    mask_20m,
                    c10,
                    c20,
                    st.format("YYYY-MM-dd"),
                    en.format("YYYY-MM-dd"),
                    {
                        "year": ay,
                        "start_date": st.format("YYYY-MM-dd"),
                        "end_date": en.advance(-1, "day").format("YYYY-MM-dd"),
                    },
                )
            )
        return ee.FeatureCollection(feats)

    job = {
        "name": bname,
        "expected_rows": len(years),
        "meta": {"kind_group": "annual", "years": years},
        "build_fc": _build,
    }
    return _run_table_batches([job], {bname: _validate_summary_csv})


def _run_raster_jobs(jobs: List[Dict]) -> Dict:
    ledger = _load_ledger()
    if not ledger.get("drive_folder_id") or not ledger.get("static_counts"):
        ledger = step_preflight()
    folder_id = ledger["drive_folder_id"]

    pending = []
    for job in jobs:
        bname = job["name"]
        rec = ledger["batches"].get(bname)
        if rec and rec.get("state") == "COMPLETED" and rec.get("checksum_verified"):
            local_p = PHASE_C_RAW_DIR / f"{bname}.tif"
            if local_p.exists():
                print(f"  [Skip] {bname}.tif already COMPLETED and MD5 verified.")
                continue
        pending.append(job)

    if not pending:
        return ledger

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        guelma_geom, _, _ = _get_guelma_geometry(ee)
        mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)

        launched = []
        for job in pending:
            scale = job["scale"]
            bmask = mask_10m if scale == 10 else mask_20m
            img = job["build_img"](ee, guelma_geom).updateMask(bmask).unmask(NODATA_VALUE, False)
            img = img.toInt32() if job.get("is_int") else img.toFloat()
            task = ee.batch.Export.image.toDrive(
                image=img,
                description=job["name"],
                folder=DRIVE_FOLDER_NAME,
                fileNamePrefix=job["name"],
                region=guelma_geom,
                scale=scale,
                crs=TARGET_CRS,
                maxPixels=1e10,
                fileFormat="GeoTIFF",
                formatOptions={"cloudOptimized": True, "noData": NODATA_VALUE},
            )
            task.start()
            launched.append(
                {
                    "name": job["name"],
                    "file_prefix": job["name"],
                    "kind": "image",
                    "task": task,
                    "scale": scale,
                    "bands": job["bands"],
                    "meta": job.get("meta", {}),
                }
            )

        print(f"[Phase C] Polling {len(launched)} GeoTIFF task(s): {[x['name'] for x in launched]}")
        results = _poll_tasks(launched, captured_warnings)
        failed = [r for r in results if r["state"] != "COMPLETED"]
        if failed:
            for r in failed:
                ledger["batches"][r["name"]] = r
            _save_ledger(ledger)
            raise RuntimeError(f"Phase C raster task(s) failed: {failed}")

        downloaded = download_and_verify_task_outputs(ee, results, PHASE_C_RAW_DIR, fallback_folder_id=folder_id)
        warn_msgs = [str(w.message) for w in captured_warnings]
        _check_quota_warnings(warn_msgs)

    for res, job in zip(results, launched):
        bname = res["name"]
        dl = downloaded[f"{bname}.tif"]
        qa = _validate_geotiff_local(Path(dl["path"]), job["scale"], job["bands"])
        ledger["batches"][bname] = {
            **res,
            **job["meta"],
            "file": dl["path"],
            "size_bytes": dl["size_bytes"],
            "md5_checksum": dl["md5_checksum"],
            "checksum_verified": dl["checksum_verified"],
            "local_validation": qa,
            "warnings": warn_msgs,
        }
        print(f"  [Verified Raster] {bname}.tif: {float(res['batch_eecu_usage_seconds'] or 0):.2f} EECU-s | {qa}")

    _save_ledger(ledger)
    return ledger


def step_rasters_monthly(ym_list: Optional[List[str]] = None) -> Dict:
    targets = [ym for ym, _ in SELECTED_MONTHLY_RASTERS] if not ym_list else ym_list
    jobs = []
    for ym in targets:
        y, m = int(ym.split("-")[0]), int(ym.split("-")[1])
        st_iso = f"{y}-{m:02d}-01"
        en_iso = f"{y + (1 if m == 12 else 0)}-{(m % 12) + 1:02d}-01"

        def _b10(ee, geom, s=st_iso, e=en_iso):
            _, _, prep = _build_prepared_joined_s2(ee, geom, s, e)
            return prep.select(["NDVI", "EVI"]).median()

        def _b20(ee, geom, s=st_iso, e=en_iso):
            _, _, prep = _build_prepared_joined_s2(ee, geom, s, e)
            return prep.select(["NDMI", "NDRE"]).median()

        jobs.extend(
            [
                {
                    "name": f"sentinel2_{y}_{m:02d}_indices_10m",
                    "scale": 10,
                    "bands": 2,
                    "meta": {"kind_group": "monthly_raster", "year_month": ym},
                    "build_img": _b10,
                },
                {
                    "name": f"sentinel2_{y}_{m:02d}_indices_20m",
                    "scale": 20,
                    "bands": 2,
                    "meta": {"kind_group": "monthly_raster", "year_month": ym},
                    "build_img": _b20,
                },
            ]
        )
    return _run_raster_jobs(jobs)


def step_rasters_annual(years: List[int] = [2017, 2025]) -> Dict:
    jobs = []
    for ay in years:
        s_iso, e_iso = f"{ay}-01-01", f"{ay + 1}-01-01"

        def _b10(ee, geom, s=s_iso, e=e_iso):
            _, _, prep = _build_prepared_joined_s2(ee, geom, s, e)
            return prep.select(["B4", "B3", "B2", "B8", "NDVI", "EVI"]).median()

        def _b20(ee, geom, s=s_iso, e=e_iso):
            _, _, prep = _build_prepared_joined_s2(ee, geom, s, e)
            return prep.select(["NDMI", "NDRE"]).median()

        jobs.extend(
            [
                {
                    "name": f"sentinel2_annual_{ay}_10m",
                    "scale": 10,
                    "bands": 6,
                    "meta": {"kind_group": "annual_raster", "year": ay},
                    "build_img": _b10,
                },
                {
                    "name": f"sentinel2_annual_{ay}_20m",
                    "scale": 20,
                    "bands": 2,
                    "meta": {"kind_group": "annual_raster", "year": ay},
                    "build_img": _b20,
                },
            ]
        )
    return _run_raster_jobs(jobs)


def step_rasters_seasonal(seasons: Optional[List[str]] = None) -> Dict:
    target_names = [s.lower() for s in seasons] if seasons else ["winter", "spring", "summer", "autumn"]
    jobs = []
    for sname, oy, sm, ey, em in SEASONS_DEF:
        if sname.lower() not in target_names:
            continue

        def _make_col(ee, geom, o_y=oy, s_m=sm, e_y=ey, e_m=em):
            col = ee.ImageCollection([])
            for sy in range(2018, END_YEAR + 1):
                st = ee.Date.fromYMD(sy + o_y, s_m, 1)
                en = ee.Date.fromYMD(sy + e_y, e_m, 1)
                _, _, p = _build_prepared_joined_s2(ee, geom, st.format("YYYY-MM-dd"), en.format("YYYY-MM-dd"))
                col = col.merge(p)
            return col

        def _b10(ee, geom, o_y=oy, s_m=sm, e_y=ey, e_m=em):
            return _make_col(ee, geom, o_y, s_m, e_y, e_m).select(["NDVI", "EVI"]).median()

        def _b20(ee, geom, o_y=oy, s_m=sm, e_y=ey, e_m=em):
            return _make_col(ee, geom, o_y, s_m, e_y, e_m).select(["NDMI", "NDRE"]).median()

        jobs.extend(
            [
                {
                    "name": f"sentinel2_seasonal_{sname.lower()}_10m",
                    "scale": 10,
                    "bands": 2,
                    "meta": {"kind_group": "seasonal_raster", "season": sname, "years": "2018-2025"},
                    "build_img": _b10,
                },
                {
                    "name": f"sentinel2_seasonal_{sname.lower()}_20m",
                    "scale": 20,
                    "bands": 2,
                    "meta": {"kind_group": "seasonal_raster", "season": sname, "years": "2018-2025"},
                    "build_img": _b20,
                },
            ]
        )
    return _run_raster_jobs(jobs)


def step_rasters_coverage() -> Dict:
    def _cov20(ee, geom):
        _, _, prep = _build_prepared_joined_s2(ee, geom, f"{START_YEAR}-01-01", f"{END_YEAR + 1}-01-01")
        cnt = prep.select("NDMI").count()
        return ee.Image(0).where(cnt.gt(0), cnt).rename("valid_obs_count")

    job = {
        "name": "sentinel2_valid_obs_count_2017_2025_20m",
        "scale": 20,
        "bands": 1,
        "is_int": True,
        "meta": {"kind_group": "coverage_raster", "years": "2017-2025"},
        "build_img": _cov20,
    }
    return _run_raster_jobs([job])


def step_collect_completed_monthly() -> Dict:
    """Collect already-COMPLETED GEE monthly CSV tasks without launching any new computation."""
    ledger = _load_ledger()
    folder_id = ledger.get("drive_folder_id")
    ee = _import_and_init_ee()
    tasks_raw = ee.batch.Task.list()[:30]

    to_collect = []
    for t in tasks_raw:
        st = t.status()
        desc = st.get("description", "")
        if not desc.startswith("phaseC_monthly_"):
            continue
        rec = ledger["batches"].get(desc)
        if rec and rec.get("state") == "COMPLETED" and rec.get("checksum_verified") and (PHASE_C_RAW_DIR / f"{desc}.csv").exists():
            continue
        if st.get("state") == "COMPLETED":
            cre, sta, upd = st.get("creation_timestamp_ms"), st.get("start_timestamp_ms"), st.get("update_timestamp_ms")
            to_collect.append(
                {
                    "name": desc,
                    "file_prefix": desc,
                    "kind": "table",
                    "task_id": st.get("id"),
                    "state": st.get("state"),
                    "error_message": st.get("error_message"),
                    "batch_eecu_usage_seconds": st.get("batch_eecu_usage_seconds"),
                    "run_seconds": round((upd - sta) / 1000.0, 2) if sta and upd else None,
                    "total_wall_seconds": round((upd - cre) / 1000.0, 2) if cre and upd else None,
                    "destination_uris": st.get("destination_uris"),
                }
            )

    if to_collect:
        downloaded = download_and_verify_task_outputs(ee, to_collect, PHASE_C_RAW_DIR, fallback_folder_id=folder_id)
        for res in to_collect:
            bname = res["name"]
            parts = bname.split("_")
            y = int(parts[2])
            qn = parts[3]
            ms = dict(QUARTERS)[qn]
            dl = downloaded[f"{bname}.csv"]
            qa = _validate_summary_csv(Path(dl["path"]), len(ms))
            ledger["batches"][bname] = {
                **res,
                "kind_group": "monthly",
                "year": y,
                "quarter": qn,
                "months": ms,
                "file": dl["path"],
                "size_bytes": dl["size_bytes"],
                "md5_checksum": dl["md5_checksum"],
                "checksum_verified": dl["checksum_verified"],
                "local_validation": qa,
                "warnings": ["Collected after noncommercial quota restricted_mode notice"],
            }
            print(f"  [Collected & Verified] {bname}: {float(res['batch_eecu_usage_seconds'] or 0):.2f} EECU-s | {qa}")

    ledger["quota_halt"] = {
        "detected_utc": datetime.now(timezone.utc).isoformat(),
        "project": GEE_PROJECT,
        "state": "RESTRICTED_MODE_QUOTA_EXCEEDED",
        "message": "Your project has exceeded its noncommercial compute quota and is now in restricted mode.",
        "pending_tasks_not_launched": [
            "phaseC_seasonal_2017..2025 (9 annual batches = 36 seasons)",
            "phaseC_annual_2017..2025 (9 annual summary rows)",
            "selected monthly GeoTIFFs (2019-04, 2022-07, 2024-03, 2025-04 at 10m/20m)",
            "annual GeoTIFFs (2017, 2025 at 10m/20m)",
            "multi-year seasonal GeoTIFFs (winter/spring/summer/autumn 2018-2025 at 10m/20m)",
            "valid_obs_count_2017_2025_20m GeoTIFF",
        ],
    }
    _save_ledger(ledger)
    print(f"[Phase C Collect] Verified batches={len(ledger['batches'])} | Total measured Phase C EECU-s={ledger['total_measured_eecu_seconds']}")
    return ledger


def step_assemble_raw_exports() -> Dict:
    """Combine verified Phase C CSVs and GeoTIFFs into RAW_EXPORTS_DIR cleanly."""
    RAW_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    m_files = sorted(PHASE_C_RAW_DIR.glob("phaseC_monthly_*.csv"))
    s_files = sorted(PHASE_C_RAW_DIR.glob("phaseC_seasonal_*.csv"))
    a_files = sorted(PHASE_C_RAW_DIR.glob("phaseC_annual_*.csv"))

    m_rows = 0
    if m_files:
        m_df = pd.concat([pd.read_csv(p) for p in m_files], ignore_index=True).drop_duplicates(subset=["year", "month"]).sort_values(["year", "month"]).reset_index(drop=True)
        m_df.to_csv(RAW_EXPORTS_DIR / "gee_monthly_indices_raw.csv", index=False, encoding="utf-8")
        m_rows = len(m_df)

    s_rows = 0
    if s_files:
        s_df = pd.concat([pd.read_csv(p) for p in s_files], ignore_index=True).drop_duplicates(subset=["season_year", "season"]).reset_index(drop=True)
        s_df.to_csv(RAW_EXPORTS_DIR / "gee_seasonal_indices_raw.csv", index=False, encoding="utf-8")
        s_rows = len(s_df)

    a_rows = 0
    if a_files:
        a_df = pd.concat([pd.read_csv(p) for p in a_files], ignore_index=True).drop_duplicates(subset=["year"]).sort_values("year").reset_index(drop=True)
        a_df.to_csv(RAW_EXPORTS_DIR / "gee_annual_indices_raw.csv", index=False, encoding="utf-8")
        a_rows = len(a_df)

    sc_src = PHASE_C_RAW_DIR / "sentinel2_scenes_2017_2025.csv"
    if sc_src.exists():
        (RAW_EXPORTS_DIR / "sentinel2_scenes_2017_2025.csv").write_bytes(sc_src.read_bytes())

    copied_tifs = []
    for tif in sorted(PHASE_C_RAW_DIR.glob("*.tif")):
        dest = RAW_EXPORTS_DIR / tif.name
        if not dest.exists() or dest.stat().st_size != tif.stat().st_size:
            dest.write_bytes(tif.read_bytes())
        copied_tifs.append(tif.name)

    print(
        f"[Phase C Assemble] monthly={m_rows} rows, seasonal={s_rows} rows, "
        f"annual={a_rows} rows, rasters={len(copied_tifs)}"
    )
    return {"monthly": m_rows, "seasonal": s_rows, "annual": a_rows, "rasters": copied_tifs}


def build_deferred_task_catalog() -> List[Dict]:
    """Return authoritative catalog of deferred Phase C GEE tasks and EECU estimates."""
    rows: List[Dict] = []
    # 1. Selected representative monthly GeoTIFFs (recommended priority #1)
    for ym, note in SELECTED_MONTHLY_RASTERS:
        y_s, m_s = ym.split("-")
        for scale_m, bands, lo, hi in [(10, "NDVI,EVI", 4500, 5600), (20, "NDMI,NDRE", 1250, 1400)]:
            rows.append(
                {
                    "task_name": f"sentinel2_{y_s}_{m_s}_indices_{scale_m}m",
                    "group": "rasters-monthly",
                    "output_type": "GeoTIFF",
                    "period": ym,
                    "resolution_m": scale_m,
                    "bands_or_rows": bands,
                    "priority": 1,
                    "est_eecu_min": lo,
                    "est_eecu_max": hi,
                    "notes": f"{note}; exported with -9999 NoData & EVI denom>0.1 guard",
                }
            )

    # 2. Annual 2017 & 2025 composite GeoTIFFs + 2017-2025 20m valid observation count GeoTIFF (priority #2)
    for ay in (2017, 2025):
        for scale_m, bands, lo, hi in [
            (10, "B4,B3,B2,B8,NDVI,EVI", 18000, 35000),
            (20, "NDMI,NDRE", 6000, 12000),
        ]:
            rows.append(
                {
                    "task_name": f"sentinel2_annual_{ay}_{scale_m}m",
                    "group": "rasters-annual",
                    "output_type": "GeoTIFF",
                    "period": str(ay),
                    "resolution_m": scale_m,
                    "bands_or_rows": bands,
                    "priority": 2,
                    "est_eecu_min": lo,
                    "est_eecu_max": hi,
                    "notes": "2017 partial Jan (1 scene)" if ay == 2017 else "Full-year 2025 baseline comparison",
                }
            )
    rows.append(
        {
            "task_name": "sentinel2_valid_obs_count_2017_2025_20m",
            "group": "rasters-coverage",
            "output_type": "GeoTIFF (Int32)",
            "period": "2017-01..2025-12",
            "resolution_m": 20,
            "bands_or_rows": "valid_obs_count",
            "priority": 2,
            "est_eecu_min": 12000,
            "est_eecu_max": 22000,
            "notes": "9-year multi-year clear observation count map at 20m",
        }
    )

    # 3. Multi-year seasonal composite GeoTIFFs (2018-2025 complete seasons, priority #3)
    for sname, _, _, _, _ in SEASONS_DEF:
        for scale_m, bands, lo, hi in [(10, "NDVI,EVI", 11000, 22000), (20, "NDMI,NDRE", 4000, 8000)]:
            rows.append(
                {
                    "task_name": f"sentinel2_seasonal_{sname.lower()}_{scale_m}m",
                    "group": "rasters-seasonal",
                    "output_type": "GeoTIFF",
                    "period": f"2018-2025 {sname}",
                    "resolution_m": scale_m,
                    "bands_or_rows": bands,
                    "priority": 3,
                    "est_eecu_min": lo,
                    "est_eecu_max": hi,
                    "notes": "Pixel-level multi-year seasonal median composite (excludes incomplete Winter 2017)",
                }
            )

    # 4. Server-side pixel-level seasonal & annual statistical CSVs (priority #4, atomic per year)
    for sy in range(START_YEAR, END_YEAR + 1):
        rows.append(
            {
                "task_name": f"phaseC_seasonal_{sy}",
                "group": "seasonal-tables",
                "output_type": "CSV Table",
                "period": f"{sy} (4 seasons)",
                "resolution_m": "10+20",
                "bands_or_rows": "4 rows",
                "priority": 4,
                "est_eecu_min": 22000,
                "est_eecu_max": 35000,
                "notes": "Winter 2017 incomplete (Dec2016+Jan2017 1 scene each); 2018-2025 complete",
            }
        )
    for ay in range(START_YEAR, END_YEAR + 1):
        rows.append(
            {
                "task_name": f"phaseC_annual_{ay}",
                "group": "annual-tables",
                "output_type": "CSV Table",
                "period": str(ay),
                "resolution_m": "10+20",
                "bands_or_rows": "1 row",
                "priority": 4,
                "est_eecu_min": 24000,
                "est_eecu_max": 38000,
                "notes": "Pixel-level annual median composite summary across full calendar year",
            }
        )
    return rows


def _is_batch_locally_verified(ledger: Dict, task_name: str, is_raster: bool) -> bool:
    rec = ledger.get("batches", {}).get(task_name)
    if not (rec and rec.get("state") == "COMPLETED" and rec.get("checksum_verified")):
        return False
    ext = "tif" if is_raster else "csv"
    return (PHASE_C_RAW_DIR / f"{task_name}.{ext}").exists()


def step_status_offline() -> Dict:
    """Inspect ledger and local files offline (zero GEE API calls)."""
    ledger = _load_ledger()
    completed_monthly = [
        f"phaseC_monthly_{y}_{qn}"
        for y in range(START_YEAR, END_YEAR + 1)
        for qn, _ in QUARTERS
        if _is_batch_locally_verified(ledger, f"phaseC_monthly_{y}_{qn}", is_raster=False)
    ]
    scenes_ok = _is_batch_locally_verified(ledger, "sentinel2_scenes_2017_2025", is_raster=False)

    catalog = build_deferred_task_catalog()
    pending_deferred = []
    done_deferred = []
    for item in catalog:
        is_tif = "GeoTIFF" in item["output_type"]
        if _is_batch_locally_verified(ledger, item["task_name"], is_raster=is_tif):
            done_deferred.append(item)
        else:
            pending_deferred.append(item)

    est_lo = sum(x["est_eecu_min"] for x in pending_deferred)
    est_hi = sum(x["est_eecu_max"] for x in pending_deferred)
    summary = {
        "gee_project": GEE_PROJECT,
        "completed_monthly_batches": f"{len(completed_monthly)}/36",
        "completed_scenes_batch": scenes_ok,
        "total_completed_and_verified": len(completed_monthly) + (1 if scenes_ok else 0) + len(done_deferred),
        "total_measured_eecu_seconds": ledger.get("total_measured_eecu_seconds", 0.0),
        "quota_halt_state": ledger.get("quota_halt", {}).get("state", "NONE"),
        "pending_deferred_tasks": len(pending_deferred),
        "pending_deferred_by_group": {
            g: sum(1 for x in pending_deferred if x["group"] == g)
            for g in ["rasters-monthly", "rasters-annual", "rasters-coverage", "rasters-seasonal", "seasonal-tables", "annual-tables"]
        },
        "est_remaining_eecu_seconds": [est_lo, est_hi],
    }
    print("[Phase C Offline Status]", json.dumps(summary, indent=2))
    return {"summary": summary, "pending_deferred": pending_deferred}


def step_resume_deferred(group: str = "all", dry_run: bool = True) -> Dict:
    """Resume ONLY missing deferred Phase C tasks without repeating completed monthly/scenes batches."""
    st = step_status_offline()
    pending = st["pending_deferred"]
    if group == "rasters":
        target_groups = {"rasters-monthly", "rasters-annual", "rasters-coverage", "rasters-seasonal"}
    elif group == "tables":
        target_groups = {"seasonal-tables", "annual-tables"}
    elif group == "all":
        target_groups = {"rasters-monthly", "rasters-annual", "rasters-coverage", "rasters-seasonal", "seasonal-tables", "annual-tables"}
    else:
        target_groups = {group}

    selected = [x for x in pending if x["group"] in target_groups]
    if dry_run:
        print(
            f"[Dry-Run Resume Deferred] group={group} | queued={len(selected)} task(s) | "
            f"completed_monthly_skipped={st['summary']['completed_monthly_batches']} | "
            f"est_eecu_s={sum(x['est_eecu_min'] for x in selected)}..{sum(x['est_eecu_max'] for x in selected)}"
        )
        for item in selected:
            print(f"  - P{item['priority']} [{item['group']}] {item['task_name']} ({item['est_eecu_min']}-{item['est_eecu_max']} EECU-s)")
        return {"dry_run": True, "queued": selected}

    # Live execution order: lowest-cost high-value rasters first, then tables one year at a time
    if "rasters-monthly" in target_groups and any(x["group"] == "rasters-monthly" for x in selected):
        step_rasters_monthly()
    if "rasters-annual" in target_groups and any(x["group"] == "rasters-annual" for x in selected):
        step_rasters_annual([2017, 2025])
    if "rasters-coverage" in target_groups and any(x["group"] == "rasters-coverage" for x in selected):
        step_rasters_coverage()
    if "rasters-seasonal" in target_groups and any(x["group"] == "rasters-seasonal" for x in selected):
        step_rasters_seasonal()
    if "seasonal-tables" in target_groups:
        for item in [x for x in selected if x["group"] == "seasonal-tables"]:
            sy = int(item["task_name"].split("_")[-1])
            step_seasonal_years([sy])
    if "annual-tables" in target_groups:
        for item in [x for x in selected if x["group"] == "annual-tables"]:
            ay = int(item["task_name"].split("_")[-1])
            step_annual_years([ay], chunk_label=f"phaseC_annual_{ay}")
    step_assemble_raw_exports()
    return {"dry_run": False, "executed_groups": sorted(target_groups)}


if __name__ == "__main__":
    step = sys.argv[sys.argv.index("--step") + 1] if "--step" in sys.argv else "status"
    if step == "status":
        step_status_offline()
    elif step == "resume-deferred":
        grp = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else "all"
        is_live = "--live" in sys.argv
        step_resume_deferred(group=grp, dry_run=not is_live)
    elif step == "preflight":
        step_preflight()
    elif step == "collect-monthly":
        step_collect_completed_monthly()
        step_assemble_raw_exports()
    elif step == "scenes":
        step_scenes()
    elif step == "monthly-init":
        step_monthly_quarters([(2024, "Q1", [1, 2, 3])])
    elif step == "monthly-years":
        yrs = [int(y) for y in sys.argv[sys.argv.index("--years") + 1].split(",")]
        reqs = [(y, qn, ms) for y in yrs for qn, ms in QUARTERS]
        step_monthly_quarters(reqs)
    elif step == "seasonal-years":
        yrs = [int(y) for y in sys.argv[sys.argv.index("--years") + 1].split(",")]
        step_seasonal_years(yrs)
    elif step == "annual-years":
        yrs = [int(y) for y in sys.argv[sys.argv.index("--years") + 1].split(",")]
        lbl = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else None
        step_annual_years(yrs, chunk_label=lbl)
    elif step == "rasters-monthly":
        yms = sys.argv[sys.argv.index("--months") + 1].split(",") if "--months" in sys.argv else None
        step_rasters_monthly(yms)
    elif step == "rasters-annual":
        yrs = [int(y) for y in sys.argv[sys.argv.index("--years") + 1].split(",")] if "--years" in sys.argv else [2017, 2025]
        step_rasters_annual(yrs)
    elif step == "rasters-seasonal":
        ss = sys.argv[sys.argv.index("--seasons") + 1].split(",") if "--seasons" in sys.argv else None
        step_rasters_seasonal(ss)
    elif step == "rasters-coverage":
        step_rasters_coverage()
    elif step == "assemble":
        step_assemble_raw_exports()
    else:
        raise ValueError(f"Unknown --step: {step}")
