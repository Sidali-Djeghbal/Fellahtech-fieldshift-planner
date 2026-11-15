"""Phase A: Single-Month (March 2024) Batch Export & Verification Test for Field Shift."""

import io
import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import rasterio
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .config import (
    CLOUD_PROB_THRESHOLD,
    RAW_DIR,
    REFLECTANCE_SCALE,
    S2_CLOUD_PROB_ID,
    S2_COLLECTION_ID,
    SCL_EXCLUDED_CLASSES,
    TARGET_CRS,
)
from .phase2_gee_client import _get_guelma_geometry, _import_and_init_ee

PHASE_A_DIR = RAW_DIR / "phaseA_2024_03"
DRIVE_FOLDER_NAME = "FieldShift_Sentinel2_PhaseA_2024_03"


def _build_march_2024_collection(ee, guelma_geom):
    """Retrieve March 2024 S2_SR_HARMONIZED + S2_CLOUD_PROBABILITY, mask clouds/shadows, compute native indices."""
    start_date = "2024-03-01"
    end_date = "2024-04-01"

    s2 = (
        ee.ImageCollection(S2_COLLECTION_ID)
        .filterBounds(guelma_geom)
        .filterDate(start_date, end_date)
    )
    cp = (
        ee.ImageCollection(S2_CLOUD_PROB_ID)
        .filterBounds(guelma_geom)
        .filterDate(start_date, end_date)
    )

    joined = ee.ImageCollection(
        ee.Join.saveFirst(matchKey="cloud_prob_img", outer=True).apply(
            s2,
            cp,
            ee.Filter.equals(leftField="system:index", rightField="system:index"),
        )
    )

    excluded_codes = list(SCL_EXCLUDED_CLASSES.keys())

    def _prepare(img):
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
        red = img.select("B4").multiply(REFLECTANCE_SCALE)
        re1 = img.select("B5").multiply(REFLECTANCE_SCALE)
        nir = img.select("B8").multiply(REFLECTANCE_SCALE)
        nir_narrow = img.select("B8A").multiply(REFLECTANCE_SCALE)
        swir1 = img.select("B11").multiply(REFLECTANCE_SCALE)

        ndvi_den = nir.add(red)
        ndvi = nir.subtract(red).divide(ndvi_den.where(ndvi_den.eq(0), 1e-6)).rename("NDVI")

        evi_denom = nir.add(red.multiply(6.0)).subtract(blue.multiply(7.5)).add(1.0)
        evi = (
            nir.subtract(red)
            .multiply(2.5)
            .divide(evi_denom.where(evi_denom.abs().lt(1e-6), 1e-6))
            .rename("EVI")
        )

        ndmi_den = nir.add(swir1)
        ndmi = nir.subtract(swir1).divide(ndmi_den.where(ndmi_den.eq(0), 1e-6)).rename("NDMI")

        ndre_den = nir_narrow.add(re1)
        ndre = nir_narrow.subtract(re1).divide(ndre_den.where(ndre_den.eq(0), 1e-6)).rename("NDRE")

        # Keep SCL class 2 diagnostic mask alongside retained non-cloud observations
        is_scl2 = scl.eq(2).And(valid_scl).And(valid_cp).rename("is_scl2")
        is_retained = mask.rename("is_retained")

        return (
            ee.Image.cat([ndvi, evi, ndmi, ndre])
            .updateMask(mask)
            .addBands([is_scl2.selfMask(), is_retained.selfMask()])
            .copyProperties(img, ["system:index", "system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "MGRS_TILE"])
        )

    return s2, joined, joined.map(_prepare)


def _submit_phase_a_tasks(ee, guelma_geom, s2_raw, joined_raw, s2_prep) -> List[Dict]:
    """Build summary/scene FeatureCollections & composites and launch GEE Batch Export tasks."""
    # Scene-level inventory table
    def _scene_feat(img):
        img = ee.Image(img)
        return ee.Feature(
            None,
            {
                "system_index": img.get("system:index"),
                "sensing_date": ee.Date(img.get("system:time_start")).format("YYYY-MM-dd HH:mm:ss"),
                "mgrs_tile": img.get("MGRS_TILE"),
                "cloudy_pixel_percentage": img.get("CLOUDY_PIXEL_PERCENTAGE"),
                "has_cloud_prob": ee.Algorithms.If(img.get("cloud_prob_img"), 1, 0),
            },
        )

    scenes_fc = ee.FeatureCollection(joined_raw.map(_scene_feat))

    # Total pixels inside Guelma polygon at 10 m and 20 m
    ones = ee.Image.constant(1).clip(guelma_geom).rename("total_px")
    total_px_10 = ones.reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=guelma_geom,
        scale=10,
        crs=TARGET_CRS,
        maxPixels=1e10,
        tileScale=4,
    ).get("total_px")
    total_px_20 = ones.reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=guelma_geom,
        scale=20,
        crs=TARGET_CRS,
        maxPixels=1e10,
        tileScale=4,
    ).get("total_px")

    # Monthly median composites (NoData stays masked until explicit -9999 unmask on raster export)
    comp_10m = s2_prep.select(["NDVI", "EVI"]).median().clip(guelma_geom)
    comp_20m = s2_prep.select(["NDMI", "NDRE"]).median().clip(guelma_geom)

    obs10_raw = s2_prep.select("NDVI").count().clip(guelma_geom)
    obs10 = ee.Image(0).clip(guelma_geom).where(obs10_raw.gt(0), obs10_raw).rename("valid_obs_10m")
    obs20_raw = s2_prep.select("NDMI").count().clip(guelma_geom)
    obs20 = ee.Image(0).clip(guelma_geom).where(obs20_raw.gt(0), obs20_raw).rename("valid_obs_20m")

    reducer = (
        ee.Reducer.median()
        .combine(ee.Reducer.mean(), "", True)
        .combine(ee.Reducer.stdDev(), "", True)
        .combine(ee.Reducer.minMax(), "", True)
        .combine(ee.Reducer.count(), "", True)
    )
    stats10 = comp_10m.reduceRegion(
        reducer=reducer, geometry=guelma_geom, scale=10, crs=TARGET_CRS, maxPixels=1e10, tileScale=8
    )
    stats20 = comp_20m.reduceRegion(
        reducer=reducer, geometry=guelma_geom, scale=20, crs=TARGET_CRS, maxPixels=1e10, tileScale=8
    )
    obs10_stats = obs10.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), "", True),
        geometry=guelma_geom,
        scale=10,
        crs=TARGET_CRS,
        maxPixels=1e10,
        tileScale=8,
    )
    obs20_stats = obs20.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), "", True),
        geometry=guelma_geom,
        scale=20,
        crs=TARGET_CRS,
        maxPixels=1e10,
        tileScale=8,
    )
    scl2_sums = (
        s2_prep.select(["is_scl2", "is_retained"])
        .sum()
        .clip(guelma_geom)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=guelma_geom,
            scale=20,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=8,
        )
    )

    summary_props = (
        ee.Dictionary(
            {
                "year_month": "2024-03",
                "start_date": "2024-03-01",
                "end_date": "2024-03-31",
                "image_count": s2_raw.size(),
                "cloud_prob_matched_images": joined_raw.filter(ee.Filter.notNull(["cloud_prob_img"])).size(),
                "total_pixels_10m": total_px_10,
                "total_pixels_20m": total_px_20,
                "scl2_pixel_obs_20m": scl2_sums.get("is_scl2"),
                "retained_pixel_obs_20m": scl2_sums.get("is_retained"),
            }
        )
        .combine(stats10)
        .combine(stats20)
        .combine(obs10_stats)
        .combine(obs20_stats)
    )
    summary_fc = ee.FeatureCollection([ee.Feature(None, summary_props)])

    tasks = []

    def _start_table(fc, name: str):
        t = ee.batch.Export.table.toDrive(
            collection=fc,
            description=name,
            folder=DRIVE_FOLDER_NAME,
            fileNamePrefix=name,
            fileFormat="CSV",
        )
        t.start()
        tasks.append({"name": name, "kind": "table", "task": t, "expected_file": f"{name}.csv"})

    def _start_image(img, name: str, scale_m: int, nodata_val, is_int: bool = False):
        out_img = img.clip(guelma_geom).unmask(nodata_val)
        out_img = out_img.toInt32() if is_int else out_img.toFloat()
        t = ee.batch.Export.image.toDrive(
            image=out_img,
            description=name,
            folder=DRIVE_FOLDER_NAME,
            fileNamePrefix=name,
            region=guelma_geom,
            scale=scale_m,
            crs=TARGET_CRS,
            maxPixels=1e10,
            fileFormat="GeoTIFF",
            formatOptions={"cloudOptimized": True, "noData": nodata_val},
        )
        t.start()
        tasks.append(
            {
                "name": name,
                "kind": "image",
                "scale_m": scale_m,
                "task": t,
                "expected_file": f"{name}.tif",
            }
        )

    _start_table(scenes_fc, "sentinel2_2024_03_scenes")
    _start_table(summary_fc, "sentinel2_2024_03_summary")
    _start_image(comp_10m, "sentinel2_2024_03_indices_10m", 10, -9999.0, is_int=False)
    _start_image(obs10, "sentinel2_2024_03_valid_obs_10m", 10, -9999, is_int=True)
    _start_image(comp_20m, "sentinel2_2024_03_indices_20m", 20, -9999.0, is_int=False)
    _start_image(obs20, "sentinel2_2024_03_valid_obs_20m", 20, -9999, is_int=True)

    return tasks


def _wait_for_batch_tasks(tasks: List[Dict], poll_sec: int = 15, timeout_sec: int = 1800) -> List[Dict]:
    """Poll GEE batch export tasks until all finish or a quota restriction occurs."""
    t0 = time.monotonic()
    statuses = {}
    terminal = {"COMPLETED", "FAILED", "CANCELLED", "CANCEL_REQUESTED"}

    while True:
        all_done = True
        for item in tasks:
            name = item["name"]
            if name in statuses and statuses[name].get("state") in terminal:
                continue
            st = item["task"].status()
            statuses[name] = st
            state = st.get("state", "UNKNOWN")
            if state not in terminal:
                all_done = False

        summary_line = ", ".join(f"{k}={v.get('state')}" for k, v in statuses.items())
        print(f"  [t+{int(time.monotonic() - t0)}s] {summary_line}", flush=True)

        if all_done:
            break
        if time.monotonic() - t0 > timeout_sec:
            raise TimeoutError(f"GEE batch tasks timed out after {timeout_sec}s: {summary_line}")
        time.sleep(poll_sec)

    results = []
    for item in tasks:
        st = statuses[item["name"]]
        start_ms = st.get("start_timestamp_ms")
        upd_ms = st.get("update_timestamp_ms")
        cre_ms = st.get("creation_timestamp_ms")
        run_sec = round((upd_ms - start_ms) / 1000.0, 2) if start_ms and upd_ms else None
        total_sec = round((upd_ms - cre_ms) / 1000.0, 2) if cre_ms and upd_ms else None
        results.append(
            {
                "name": item["name"],
                "kind": item["kind"],
                "expected_file": item["expected_file"],
                "task_id": st.get("id"),
                "state": st.get("state"),
                "error_message": st.get("error_message"),
                "batch_eecu_usage_seconds": st.get("batch_eecu_usage_seconds"),
                "run_seconds": run_sec,
                "total_wall_seconds": total_sec,
                "destination_uris": st.get("destination_uris"),
                "raw_status": st,
            }
        )
    return results


def _download_drive_folder_files(ee, expected_filenames: List[str]) -> Dict[str, Path]:
    """Locate Drive folder FieldShift_Sentinel2_PhaseA_2024_03 and download exported files locally."""
    PHASE_A_DIR.mkdir(parents=True, exist_ok=True)
    creds = ee.data.get_persistent_credentials().with_quota_project(None)
    drive = build("drive", "v3", credentials=creds)

    folders = (
        drive.files()
        .list(
            q=f"name = '{DRIVE_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc",
        )
        .execute()
        .get("files", [])
    )
    if not folders:
        raise FileNotFoundError(f"Google Drive folder '{DRIVE_FOLDER_NAME}' not found after GEE exports.")

    files = []
    for fld in folders:
        fld_files = (
            drive.files()
            .list(
                q=f"'{fld['id']}' in parents and trashed = false",
                fields="files(id, name, size, createdTime, md5Checksum)",
                orderBy="createdTime desc",
                pageSize=100,
            )
            .execute()
            .get("files", [])
        )
        files.extend(fld_files)

    files.sort(key=lambda x: x.get("createdTime", ""), reverse=True)

    downloaded: Dict[str, Path] = {}
    seen_names = set()
    for fmeta in files:
        fname = fmeta["name"]
        if fname in seen_names:
            continue
        if fname not in expected_filenames and not any(fname.startswith(Path(e).stem) for e in expected_filenames):
            continue
        seen_names.add(fname)
        local_path = PHASE_A_DIR / fname
        expected_size = int(fmeta.get("size") or 0)
        if local_path.exists() and expected_size > 0 and local_path.stat().st_size == expected_size:
            downloaded[fname] = local_path
            print(f"  Using existing local file -> {local_path} ({expected_size:,} bytes)", flush=True)
            continue
        request = drive.files().get_media(fileId=fmeta["id"])
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()
        downloaded[fname] = local_path
        print(f"  Downloaded from Drive -> {local_path} ({local_path.stat().st_size:,} bytes)", flush=True)

    return downloaded


def _verify_local_exports(downloaded: Dict[str, Path]) -> Dict:
    """Open every exported CSV and GeoTIFF locally and compute verification metrics."""
    file_checks = {}

    for fname, fpath in sorted(downloaded.items()):
        size_bytes = fpath.stat().st_size
        entry = {
            "path": str(fpath),
            "exists": fpath.exists(),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 4),
        }

        if fname.endswith(".csv"):
            df = pd.read_csv(fpath)
            entry["readable"] = True
            entry["rows"] = int(len(df))
            entry["columns"] = list(df.columns)
            if fname == "sentinel2_2024_03_summary.csv" and len(df) == 1:
                row = df.iloc[0].to_dict()
                tot10 = float(row.get("total_pixels_10m") or 0)
                tot20 = float(row.get("total_pixels_20m") or 0)
                ndvi_cnt = float(row.get("NDVI_count") or 0)
                evi_cnt = float(row.get("EVI_count") or 0)
                ndmi_cnt = float(row.get("NDMI_count") or 0)
                ndre_cnt = float(row.get("NDRE_count") or 0)
                row["NDVI_valid_pct"] = round(ndvi_cnt / tot10 * 100.0, 4) if tot10 else None
                row["NDVI_missing_pct"] = round(100.0 - row["NDVI_valid_pct"], 4) if tot10 else None
                row["EVI_valid_pct"] = round(evi_cnt / tot10 * 100.0, 4) if tot10 else None
                row["NDMI_valid_pct"] = round(ndmi_cnt / tot20 * 100.0, 4) if tot20 else None
                row["NDMI_missing_pct"] = round(100.0 - row["NDMI_valid_pct"], 4) if tot20 else None
                row["NDRE_valid_pct"] = round(ndre_cnt / tot20 * 100.0, 4) if tot20 else None
                ret20 = float(row.get("retained_pixel_obs_20m") or 0)
                scl2_20 = float(row.get("scl2_pixel_obs_20m") or 0)
                row["scl2_share_of_retained_pct"] = round(scl2_20 / ret20 * 100.0, 4) if ret20 else None
                entry["summary_metrics"] = row
            elif fname == "sentinel2_2024_03_scenes.csv":
                entry["unique_tiles"] = sorted(df["mgrs_tile"].dropna().unique().tolist()) if "mgrs_tile" in df.columns else []
                entry["cloud_prob_matched"] = int(df["has_cloud_prob"].sum()) if "has_cloud_prob" in df.columns else None

        elif fname.endswith(".tif"):
            with rasterio.open(fpath) as src:
                band_stats = []
                for b_idx in range(1, src.count + 1):
                    arr = src.read(b_idx).astype(np.float64)
                    nodata = src.nodata
                    valid_mask = np.isfinite(arr)
                    if nodata is not None:
                        valid_mask &= arr != nodata
                    vals = arr[valid_mask]
                    band_stats.append(
                        {
                            "band_index": b_idx,
                            "description": src.descriptions[b_idx - 1],
                            "valid_pixels": int(vals.size),
                            "nodata_pixels": int(arr.size - vals.size),
                            "zero_obs_pixels": int(np.sum(vals == 0)) if "valid_obs" in fname else None,
                            "min": round(float(np.min(vals)), 4) if vals.size else None,
                            "p05": round(float(np.percentile(vals, 5)), 4) if vals.size else None,
                            "median": round(float(np.median(vals)), 4) if vals.size else None,
                            "mean": round(float(np.mean(vals)), 4) if vals.size else None,
                            "p95": round(float(np.percentile(vals, 95)), 4) if vals.size else None,
                            "max": round(float(np.max(vals)), 4) if vals.size else None,
                        }
                    )
                entry.update(
                    {
                        "readable": True,
                        "crs": str(src.crs),
                        "res_x_m": round(float(src.res[0]), 4),
                        "res_y_m": round(float(src.res[1]), 4),
                        "width": int(src.width),
                        "height": int(src.height),
                        "band_count": int(src.count),
                        "dtypes": list(src.dtypes),
                        "nodata": src.nodata,
                        "band_stats": band_stats,
                    }
                )
        file_checks[fname] = entry

    return file_checks


def run_phase_a() -> Dict:
    """Execute Phase A (March 2024 single-month batch export test) and verify all outputs."""
    t_start = time.monotonic()
    PHASE_A_DIR.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        guelma_geom, boundary_source, _ = _get_guelma_geometry(ee)

        print("[Phase A] Building March 2024 (2024-03-01 .. 2024-04-01) Sentinel-2 workflow...")
        s2_raw, joined_raw, s2_prep = _build_march_2024_collection(ee, guelma_geom)

        print("[Phase A] Submitting 6 GEE Batch Export tasks (2 CSV tables + 4 GeoTIFFs) to Google Drive...")
        tasks = _submit_phase_a_tasks(ee, guelma_geom, s2_raw, joined_raw, s2_prep)

        print("[Phase A] Polling GEE batch task status...")
        task_results = _wait_for_batch_tasks(tasks, poll_sec=15, timeout_sec=1800)

        quota_warnings = [str(w.message) for w in captured_warnings]
        # Check for restricted-mode / quota warnings immediately
        if any("restricted mode" in msg.lower() or "quota" in msg.lower() for msg in quota_warnings):
            raise RuntimeError(f"GEE quota/restricted-mode warning encountered: {quota_warnings}")

        failed = [t for t in task_results if t["state"] != "COMPLETED"]
        if failed:
            raise RuntimeError(f"One or more Phase A GEE batch exports did not complete cleanly: {failed}")

        print("[Phase A] All 6 batch tasks COMPLETED. Downloading exported files from Drive for local verification...")
        expected_files = [t["expected_file"] for t in task_results]
        downloaded = _download_drive_folder_files(ee, expected_files)

    missing_files = [f for f in expected_files if f not in downloaded]
    if missing_files:
        raise FileNotFoundError(f"Missing expected Drive files after export: {missing_files}")

    print("[Phase A] Verifying local CSV and GeoTIFF files...")
    verification = _verify_local_exports(downloaded)

    total_eecu = sum(float(t["batch_eecu_usage_seconds"] or 0.0) for t in task_results)
    elapsed_sec = round(time.monotonic() - t_start, 2)

    report = {
        "phase": "Phase A — Single-Month Processing Test (March 2024)",
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "boundary_source": boundary_source,
        "target_crs": TARGET_CRS,
        "drive_folder": DRIVE_FOLDER_NAME,
        "total_wall_seconds": elapsed_sec,
        "total_batch_eecu_seconds": round(total_eecu, 4),
        "warnings": quota_warnings,
        "tasks": [
            {k: v for k, v in t.items() if k != "raw_status"}
            for t in task_results
        ],
        "verified_files": verification,
    }

    report_path = PHASE_A_DIR / "phaseA_2024_03_verification_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[Phase A] Verification report saved -> {report_path}")
    return report


def finalize_phase_a_from_existing() -> Dict:
    """Verify completed Phase A tasks from GEE Task.list(), fetch remaining Drive files, and write report."""
    expected_specs = [
        ("sentinel2_2024_03_scenes", "table", "sentinel2_2024_03_scenes.csv"),
        ("sentinel2_2024_03_summary", "table", "sentinel2_2024_03_summary.csv"),
        ("sentinel2_2024_03_indices_10m", "image", "sentinel2_2024_03_indices_10m.tif"),
        ("sentinel2_2024_03_valid_obs_10m", "image", "sentinel2_2024_03_valid_obs_10m.tif"),
        ("sentinel2_2024_03_indices_20m", "image", "sentinel2_2024_03_indices_20m.tif"),
        ("sentinel2_2024_03_valid_obs_20m", "image", "sentinel2_2024_03_valid_obs_20m.tif"),
    ]
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        all_tasks = ee.batch.Task.list()
        by_desc = {}
        for t in all_tasks:
            st = t.status()
            desc = st.get("description")
            if desc and desc not in by_desc:
                by_desc[desc] = st

        task_results = []
        for name, kind, expected_file in expected_specs:
            st = by_desc.get(name, {})
            start_ms = st.get("start_timestamp_ms")
            upd_ms = st.get("update_timestamp_ms")
            cre_ms = st.get("creation_timestamp_ms")
            task_results.append(
                {
                    "name": name,
                    "kind": kind,
                    "expected_file": expected_file,
                    "task_id": st.get("id"),
                    "state": st.get("state"),
                    "error_message": st.get("error_message"),
                    "batch_eecu_usage_seconds": st.get("batch_eecu_usage_seconds"),
                    "run_seconds": round((upd_ms - start_ms) / 1000.0, 2) if start_ms and upd_ms else None,
                    "total_wall_seconds": round((upd_ms - cre_ms) / 1000.0, 2) if cre_ms and upd_ms else None,
                    "destination_uris": st.get("destination_uris"),
                }
            )

        downloaded = _download_drive_folder_files(ee, [e[2] for e in expected_specs])
        quota_warnings = [str(w.message) for w in captured_warnings]

    missing_files = [e[2] for e in expected_specs if e[2] not in downloaded]
    if missing_files:
        raise FileNotFoundError(f"Still missing Drive files: {missing_files}")

    verification = _verify_local_exports(downloaded)
    total_eecu = sum(float(t["batch_eecu_usage_seconds"] or 0.0) for t in task_results)
    report = {
        "phase": "Phase A — Single-Month Processing Test (March 2024)",
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "boundary_source": "local:data/boundaries/processed/guelma_wilaya_boundary.geojson.gpkg",
        "target_crs": TARGET_CRS,
        "drive_folder": DRIVE_FOLDER_NAME,
        "total_batch_eecu_seconds": round(total_eecu, 4),
        "warnings": quota_warnings,
        "tasks": task_results,
        "verified_files": verification,
    }
    report_path = PHASE_A_DIR / "phaseA_2024_03_verification_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[Phase A] Verification report saved -> {report_path}")
    return report


if __name__ == "__main__":
    import sys
    if "--finalize" in sys.argv:
        finalize_phase_a_from_existing()
    else:
        run_phase_a()
