"""Phase B.1 & B.2: EVI Sensitivity Diagnostics, NoData Crop Validation, and Optimized March 2024 Summary Benchmark."""

import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from .config import (
    BOUNDARY_FILE,
    CLOUD_PROB_THRESHOLD,
    RAW_DIR,
    REFLECTANCE_SCALE,
    S2_CLOUD_PROB_ID,
    S2_COLLECTION_ID,
    SCL_EXCLUDED_CLASSES,
    TARGET_CRS,
)
from .drive_export_manager import (
    download_and_verify_task_outputs,
    ensure_single_drive_folder,
)
from .phase2_gee_client import _get_guelma_geometry, _import_and_init_ee

PHASE_B_DIR = RAW_DIR / "phaseB_benchmark_2024_03"
DRIVE_FOLDER_NAME = "FieldShift_Sentinel2_PhaseB_Benchmark_2024_03"
BASELINE_SUMMARY_EECU = 12221.3408203125


def _build_boundary_masks(ee, guelma_geom):
    """Build deterministic binary interior masks at exact native 10 m and 20 m grids."""
    base_mask = ee.Image.constant(1).clip(guelma_geom).mask().gte(0.5)
    mask_10m = base_mask.reproject(crs=TARGET_CRS, scale=10).selfMask()
    mask_20m = base_mask.reproject(crs=TARGET_CRS, scale=20).selfMask()
    return mask_10m, mask_20m


def _compute_static_boundary_counts(ee, guelma_geom, mask_10m, mask_20m) -> Dict[str, int]:
    """Compute static Guelma pixel counts once outside per-month summaries."""
    c10 = int(
        mask_10m.rename("px")
        .reduceRegion(
            reducer=ee.Reducer.count().unweighted(),
            geometry=guelma_geom,
            scale=10,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=2,
        )
        .get("px")
        .getInfo()
    )
    c20 = int(
        mask_20m.rename("px")
        .reduceRegion(
            reducer=ee.Reducer.count().unweighted(),
            geometry=guelma_geom,
            scale=20,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=2,
        )
        .get("px")
        .getInfo()
    )
    return {"total_pixels_10m": c10, "total_pixels_20m": c20}


def _build_march_2024_joined(ee, guelma_geom):
    """Retrieve March 2024 S2_SR_HARMONIZED + S2_CLOUD_PROBABILITY joined collection."""
    s2 = (
        ee.ImageCollection(S2_COLLECTION_ID)
        .filterBounds(guelma_geom)
        .filterDate("2024-03-01", "2024-04-01")
    )
    cp = (
        ee.ImageCollection(S2_CLOUD_PROB_ID)
        .filterBounds(guelma_geom)
        .filterDate("2024-03-01", "2024-04-01")
    )
    joined = ee.ImageCollection(
        ee.Join.saveFirst(matchKey="cloud_prob_img", outer=True).apply(
            s2,
            cp,
            ee.Filter.equals(leftField="system:index", rightField="system:index"),
        )
    )
    return s2, joined


def _cloud_mask_expr(ee, img):
    """Build combined SCL + S2_CLOUD_PROBABILITY valid-pixel mask."""
    scl = img.select("SCL")
    valid_scl = ee.Image(1)
    for code in SCL_EXCLUDED_CLASSES.keys():
        valid_scl = valid_scl.And(scl.neq(code))
    cp_obj = img.get("cloud_prob_img")
    valid_cp = ee.Image(
        ee.Algorithms.If(
            cp_obj,
            ee.Image(cp_obj).select("probability").lt(CLOUD_PROB_THRESHOLD),
            ee.Image(1),
        )
    )
    return valid_scl.And(valid_cp)


def _poll_tasks(tasks: List[Dict], captured_warnings: List, poll_sec: int = 12, timeout_sec: int = 1800) -> List[Dict]:
    """Wait for batch tasks while monitoring for any GEE restricted-mode / quota warnings."""
    t0 = time.monotonic()
    statuses = {}
    terminal = {"COMPLETED", "FAILED", "CANCELLED", "CANCEL_REQUESTED"}

    while True:
        warn_msgs = [str(w.message) for w in captured_warnings]
        if any("restricted mode" in m.lower() or "quota" in m.lower() for m in warn_msgs):
            raise RuntimeError(f"GEE quota/restricted-mode warning detected: {warn_msgs}")

        all_done = True
        for item in tasks:
            name = item["name"]
            if name in statuses and statuses[name].get("state") in terminal:
                continue
            st = item["task"].status()
            statuses[name] = st
            state = st.get("state", "UNKNOWN")
            if state == "FAILED" and "quota" in str(st.get("error_message", "")).lower():
                raise RuntimeError(f"Task {name} failed due to quota: {st.get('error_message')}")
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


def run_step_diag() -> Dict:
    """Step B.1: Run EVI threshold/reflectance diagnostics + small 10kmx10km boundary-crop NoData verification."""
    PHASE_B_DIR.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        guelma_geom, _, _ = _get_guelma_geometry(ee)
        folder_id = ensure_single_drive_folder(ee, DRIVE_FOLDER_NAME)
        print(f"[Phase B Diag] Canonical Drive folder '{DRIVE_FOLDER_NAME}' -> {folder_id}")

        mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)
        _, joined = _build_march_2024_joined(ee, guelma_geom)

        def _evi_diag_bands(img):
            img = ee.Image(img)
            cmask = _cloud_mask_expr(ee, img)
            blue = img.select("B2").multiply(REFLECTANCE_SCALE)
            red = img.select("B4").multiply(REFLECTANCE_SCALE)
            nir = img.select("B8").multiply(REFLECTANCE_SCALE)
            denom = nir.add(red.multiply(6.0)).subtract(blue.multiply(7.5)).add(1.0)
            num = nir.subtract(red).multiply(2.5)

            sr_nonneg = blue.gte(0).And(red.gte(0)).And(nir.gte(0))
            evi_base = num.divide(denom.where(denom.abs().lt(1e-6), 1e-6)).rename("evi_base")
            evi_t005 = evi_base.updateMask(sr_nonneg.And(denom.gt(0.05))).rename("evi_t005")
            evi_t010 = evi_base.updateMask(sr_nonneg.And(denom.gt(0.10))).rename("evi_t010")

            diag = ee.Image.cat(
                [
                    evi_base,
                    evi_t005,
                    evi_t010,
                    denom.rename("evi_denom"),
                    blue.lt(0).rename("b2_neg"),
                    red.lt(0).rename("b4_neg"),
                    nir.lt(0).rename("b8_neg"),
                    sr_nonneg.Not().rename("any_sr_neg"),
                    denom.lte(0.0).rename("denom_le_0"),
                    denom.lte(0.05).rename("denom_le_005"),
                    denom.lte(0.10).rename("denom_le_010"),
                    denom.lte(0.20).rename("denom_le_020"),
                    sr_nonneg.Not().Or(denom.lte(0.05)).rename("excl_sr_or_005"),
                    sr_nonneg.Not().Or(denom.lte(0.10)).rename("excl_sr_or_010"),
                    ee.Image.constant(1).rename("obs_total"),
                ]
            ).updateMask(cmask)
            return diag

        diag_col = joined.map(_evi_diag_bands)

        # 1) Observation-level counts summed over Guelma
        obs_flags = [
            "obs_total",
            "b2_neg",
            "b4_neg",
            "b8_neg",
            "any_sr_neg",
            "denom_le_0",
            "denom_le_005",
            "denom_le_010",
            "denom_le_020",
            "excl_sr_or_005",
            "excl_sr_or_010",
        ]
        obs_sum = (
            diag_col.select(obs_flags)
            .sum()
            .updateMask(mask_10m)
            .reduceRegion(
                reducer=ee.Reducer.sum().unweighted(),
                geometry=guelma_geom,
                scale=10,
                crs=TARGET_CRS,
                maxPixels=1e10,
                tileScale=4,
            )
        )

        # 2) Composite-level before vs after (t005 and t010) stats at 10 m
        comp_evi = diag_col.select(["evi_base", "evi_t005", "evi_t010"]).median().updateMask(mask_10m)
        comp_flagged = ee.Image.cat(
            [
                comp_evi,
                comp_evi.select("evi_base").abs().gt(2.0).rename("base_abs_gt_2"),
                comp_evi.select("evi_base").gt(1.0).rename("base_gt_1"),
                comp_evi.select("evi_base").lt(-1.0).rename("base_lt_m1"),
                comp_evi.select("evi_t005").abs().gt(2.0).rename("t005_abs_gt_2"),
                comp_evi.select("evi_t005").gt(1.0).rename("t005_gt_1"),
                comp_evi.select("evi_t005").lt(-1.0).rename("t005_lt_m1"),
                comp_evi.select("evi_t010").abs().gt(2.0).rename("t010_abs_gt_2"),
                comp_evi.select("evi_t010").gt(1.0).rename("t010_gt_1"),
                comp_evi.select("evi_t010").lt(-1.0).rename("t010_lt_m1"),
            ]
        )
        comp_stats = comp_flagged.select(["evi_base", "evi_t005", "evi_t010"]).reduceRegion(
            reducer=(
                ee.Reducer.percentile([1, 5, 50, 95, 99])
                .combine(ee.Reducer.mean(), "", True)
                .combine(ee.Reducer.stdDev(), "", True)
                .combine(ee.Reducer.minMax(), "", True)
                .combine(ee.Reducer.count(), "", True)
                .unweighted()
            ),
            geometry=guelma_geom,
            scale=10,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=4,
        )
        outlier_counts = comp_flagged.select(
            [
                "base_abs_gt_2",
                "base_gt_1",
                "base_lt_m1",
                "t005_abs_gt_2",
                "t005_gt_1",
                "t005_lt_m1",
                "t010_abs_gt_2",
                "t010_gt_1",
                "t010_lt_m1",
            ]
        ).reduceRegion(
            reducer=ee.Reducer.sum().unweighted(),
            geometry=guelma_geom,
            scale=10,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=4,
        )
        denom_pcts = (
            diag_col.select("evi_denom")
            .median()
            .updateMask(mask_10m)
            .reduceRegion(
                reducer=ee.Reducer.percentile([0.1, 1, 5, 50, 95, 99, 99.9]).combine(ee.Reducer.minMax(), "", True).unweighted(),
                geometry=guelma_geom,
                scale=10,
                crs=TARGET_CRS,
                maxPixels=1e10,
                tileScale=4,
            )
        )

        diag_fc = ee.FeatureCollection(
            [ee.Feature(None, ee.Dictionary(obs_sum).combine(comp_stats).combine(outlier_counts).combine(denom_pcts))]
        )

        # 3) Small 10 km x 10 km boundary-straddling crop for valid_obs NoData verification
        crop_geom = ee.Geometry.Rectangle([315000, 4020000, 325000, 4030000], proj=TARGET_CRS, geodesic=False)
        valid_obs_img = (
            joined.map(lambda im: im.select("B8").updateMask(_cloud_mask_expr(ee, im)).rename("valid_obs"))
            .count()
        )
        obs10_crop = (
            ee.Image(0)
            .where(valid_obs_img.gt(0), valid_obs_img)
            .updateMask(mask_10m)
            .unmask(-9999, False)
            .toInt32()
            .rename("valid_obs_10m")
        )
        obs20_crop = (
            ee.Image(0)
            .where(valid_obs_img.gt(0), valid_obs_img)
            .updateMask(mask_20m)
            .unmask(-9999, False)
            .toInt32()
            .rename("valid_obs_20m")
        )

        tasks = []
        t1 = ee.batch.Export.table.toDrive(
            collection=diag_fc,
            description="phaseB_2024_03_evi_diagnostics",
            folder=DRIVE_FOLDER_NAME,
            fileNamePrefix="phaseB_2024_03_evi_diagnostics",
            fileFormat="CSV",
        )
        t1.start()
        tasks.append({"name": "phaseB_2024_03_evi_diagnostics", "file_prefix": "phaseB_2024_03_evi_diagnostics", "kind": "table", "task": t1})

        for nm, im, sc in [
            ("phaseB_2024_03_crop_valid_obs_10m", obs10_crop, 10),
            ("phaseB_2024_03_crop_valid_obs_20m", obs20_crop, 20),
        ]:
            t = ee.batch.Export.image.toDrive(
                image=im,
                description=nm,
                folder=DRIVE_FOLDER_NAME,
                fileNamePrefix=nm,
                region=crop_geom,
                scale=sc,
                crs=TARGET_CRS,
                maxPixels=1e9,
                fileFormat="GeoTIFF",
                formatOptions={"cloudOptimized": True, "noData": -9999},
            )
            t.start()
            tasks.append({"name": nm, "file_prefix": nm, "kind": "image", "task": t})

        print("[Phase B Diag] Polling 3 diagnostic/validation tasks...")
        task_results = _poll_tasks(tasks, captured_warnings)
        failed = [x for x in task_results if x["state"] != "COMPLETED"]
        if failed:
            raise RuntimeError(f"Phase B diag tasks failed: {failed}")

        downloaded = download_and_verify_task_outputs(ee, task_results, PHASE_B_DIR, fallback_folder_id=folder_id)
        warn_list = [str(w.message) for w in captured_warnings]

    # Verify crops locally with rasterio + polygon mask
    gdf = gpd.read_file(BOUNDARY_FILE).to_crs(TARGET_CRS)
    crop_checks = {}
    for crop_name in ("phaseB_2024_03_crop_valid_obs_10m.tif", "phaseB_2024_03_crop_valid_obs_20m.tif"):
        cpath = Path(downloaded[crop_name]["path"])
        with rasterio.open(cpath) as src:
            arr = src.read(1)
            inside = ~geometry_mask(list(gdf.geometry), out_shape=src.shape, transform=src.transform, all_touched=False)
            out_vals = arr[~inside]
            in_vals = arr[inside]
            crop_checks[crop_name] = {
                "crs": str(src.crs),
                "res_m": [round(float(src.res[0]), 4), round(float(src.res[1]), 4)],
                "shape": list(src.shape),
                "nodata_tag": src.nodata,
                "outside_polygon_pixels": int(out_vals.size),
                "outside_polygon_all_equal_minus9999": bool(np.all(out_vals == -9999)),
                "outside_polygon_zero_count": int(np.sum(out_vals == 0)),
                "inside_polygon_pixels": int(in_vals.size),
                "inside_polygon_min_valid_obs": int(np.min(in_vals[in_vals != -9999])) if np.any(in_vals != -9999) else None,
                "inside_polygon_max_valid_obs": int(np.max(in_vals[in_vals != -9999])) if np.any(in_vals != -9999) else None,
                "inside_polygon_nodata_count": int(np.sum(in_vals == -9999)),
            }

    evi_df = pd.read_csv(downloaded["phaseB_2024_03_evi_diagnostics.csv"]["path"])
    out_report = {
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "drive_folder_id": folder_id,
        "warnings": warn_list,
        "tasks": task_results,
        "downloaded_files": downloaded,
        "evi_diagnostics_row": evi_df.iloc[0].to_dict(),
        "nodata_crop_checks": crop_checks,
    }
    (PHASE_B_DIR / "phaseB_diag_report.json").write_text(json.dumps(out_report, indent=2, default=str), encoding="utf-8")
    print("[Phase B Diag] Saved -> phaseB_diag_report.json")
    return out_report


def run_step_benchmark(evi_denom_threshold: float = 0.05) -> Dict:
    """Step B.2: Execute standalone optimized March 2024 summary batch export & compare vs 12,221.34 EECU-s."""
    PHASE_B_DIR.mkdir(parents=True, exist_ok=True)
    t_wall_start = time.monotonic()

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        ee = _import_and_init_ee()
        guelma_geom, boundary_source, _ = _get_guelma_geometry(ee)
        folder_id = ensure_single_drive_folder(ee, DRIVE_FOLDER_NAME)
        print(f"[Phase B Benchmark] Canonical Drive folder '{DRIVE_FOLDER_NAME}' -> {folder_id}")

        # 1) Pre-compute static boundary pixel counts ONCE outside the summary task
        mask_10m, mask_20m = _build_boundary_masks(ee, guelma_geom)
        static_counts = _compute_static_boundary_counts(ee, guelma_geom, mask_10m, mask_20m)
        print(f"[Phase B Benchmark] Static counts: {static_counts}")

        s2_raw, joined = _build_march_2024_joined(ee, guelma_geom)

        # 2) Single-pass image preparation combining indices & diagnostic masks
        def _prepare_opt(img):
            img = ee.Image(img)
            scl = img.select("SCL")
            cmask = _cloud_mask_expr(ee, img)

            blue = img.select("B2").multiply(REFLECTANCE_SCALE)
            red = img.select("B4").multiply(REFLECTANCE_SCALE)
            re1 = img.select("B5").multiply(REFLECTANCE_SCALE)
            nir = img.select("B8").multiply(REFLECTANCE_SCALE)
            nir_narrow = img.select("B8A").multiply(REFLECTANCE_SCALE)
            swir1 = img.select("B11").multiply(REFLECTANCE_SCALE)

            ndvi_den = nir.add(red)
            ndvi = nir.subtract(red).divide(ndvi_den.where(ndvi_den.eq(0), 1e-6)).rename("NDVI")

            evi_denom = nir.add(red.multiply(6.0)).subtract(blue.multiply(7.5)).add(1.0)
            evi_valid = blue.gte(0).And(red.gte(0)).And(nir.gte(0)).And(evi_denom.gt(evi_denom_threshold))
            evi = (
                nir.subtract(red)
                .multiply(2.5)
                .divide(evi_denom.where(evi_denom.lte(evi_denom_threshold), 1.0))
                .updateMask(evi_valid)
                .rename("EVI")
            )

            ndmi_den = nir.add(swir1)
            ndmi = nir.subtract(swir1).divide(ndmi_den.where(ndmi_den.eq(0), 1e-6)).rename("NDMI")

            ndre_den = nir_narrow.add(re1)
            ndre = nir_narrow.subtract(re1).divide(ndre_den.where(ndre_den.eq(0), 1e-6)).rename("NDRE")

            is_scl2 = scl.eq(2).toFloat().rename("is_scl2")

            return (
                ee.Image.cat([ndvi, evi, ndmi, ndre, is_scl2])
                .updateMask(cmask)
                .copyProperties(img, ["system:time_start"])
            )

        s2_prep = joined.map(_prepare_opt)

        # 3) Single temporal reduction per resolution: median + count in ONE pass
        temp_reducer = ee.Reducer.median().combine(ee.Reducer.count(), "", True)
        temp_10m = s2_prep.select(["NDVI", "EVI"]).reduce(temp_reducer)
        valid_obs_10m = temp_10m.select("NDVI_count").unmask(0).rename("valid_obs_10m")
        evi_obs_10m = temp_10m.select("EVI_count").unmask(0).rename("evi_valid_obs_10m")
        stack_10m = ee.Image.cat(
            [
                temp_10m.select(["NDVI_median", "EVI_median"]).rename(["NDVI", "EVI"]),
                valid_obs_10m,
                evi_obs_10m,
            ]
        ).updateMask(mask_10m)

        temp_20m = s2_prep.select(["NDMI", "NDRE"]).reduce(temp_reducer)
        scl2_stats = s2_prep.select("is_scl2").reduce(
            ee.Reducer.mean().combine(ee.Reducer.count(), "", True)
        )
        valid_obs_20m = temp_20m.select("NDMI_count").unmask(0).rename("valid_obs_20m")
        scl2_sum_px = (
            scl2_stats.select("is_scl2_mean")
            .multiply(scl2_stats.select("is_scl2_count"))
            .unmask(0)
            .rename("scl2_obs")
        )
        stack_20m = ee.Image.cat(
            [
                temp_20m.select(["NDMI_median", "NDRE_median"]).rename(["NDMI", "NDRE"]),
                valid_obs_20m,
                scl2_sum_px,
            ]
        ).updateMask(mask_20m)

        # 4) Combined unweighted regional stats: exactly TWO reduceRegion calls (one 10m, one 20m)
        reg_reducer = (
            ee.Reducer.percentile([5, 50, 95])
            .combine(ee.Reducer.mean(), "", True)
            .combine(ee.Reducer.stdDev(), "", True)
            .combine(ee.Reducer.minMax(), "", True)
            .combine(ee.Reducer.count(), "", True)
            .unweighted()
        )
        stats10 = stack_10m.reduceRegion(
            reducer=reg_reducer,
            geometry=guelma_geom,
            scale=10,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=4,
        )
        stats20 = stack_20m.reduceRegion(
            reducer=reg_reducer,
            geometry=guelma_geom,
            scale=20,
            crs=TARGET_CRS,
            maxPixels=1e10,
            tileScale=4,
        )

        # Also get total scl2 observation sum cleanly in the 20m pass? Wait: mean * count = exact sum!
        props = (
            ee.Dictionary(
                {
                    "year_month": "2024-03",
                    "start_date": "2024-03-01",
                    "end_date": "2024-03-31",
                    "image_count": s2_raw.size(),
                    "cloud_prob_matched_images": joined.filter(ee.Filter.notNull(["cloud_prob_img"])).size(),
                    "total_pixels_10m": static_counts["total_pixels_10m"],
                    "total_pixels_20m": static_counts["total_pixels_20m"],
                    "evi_denom_threshold": evi_denom_threshold,
                }
            )
            .combine(stats10)
            .combine(stats20)
        )
        summary_fc = ee.FeatureCollection([ee.Feature(None, props)])

        task = ee.batch.Export.table.toDrive(
            collection=summary_fc,
            description="phaseB_2024_03_summary_optimized",
            folder=DRIVE_FOLDER_NAME,
            fileNamePrefix="phaseB_2024_03_summary_optimized",
            fileFormat="CSV",
        )
        task.start()
        tasks = [
            {
                "name": "phaseB_2024_03_summary_optimized",
                "file_prefix": "phaseB_2024_03_summary_optimized",
                "kind": "table",
                "task": task,
            }
        ]
        print("[Phase B Benchmark] Polling optimized March 2024 summary task...")
        task_results = _poll_tasks(tasks, captured_warnings)
        if task_results[0]["state"] != "COMPLETED":
            raise RuntimeError(f"Optimized benchmark task failed: {task_results[0]}")

        downloaded = download_and_verify_task_outputs(ee, task_results, PHASE_B_DIR, fallback_folder_id=folder_id)
        warn_list = [str(w.message) for w in captured_warnings]

    df = pd.read_csv(downloaded["phaseB_2024_03_summary_optimized.csv"]["path"])
    row = df.iloc[0].to_dict()
    tot10 = float(row["total_pixels_10m"])
    tot20 = float(row["total_pixels_20m"])
    row["NDVI_valid_pct"] = round(float(row["NDVI_count"]) / tot10 * 100.0, 4)
    row["EVI_valid_pct"] = round(float(row["EVI_count"]) / tot10 * 100.0, 4)
    row["EVI_excluded_composite_pixels"] = int(tot10 - float(row["EVI_count"]))
    row["NDMI_valid_pct"] = round(float(row["NDMI_count"]) / tot20 * 100.0, 4)
    row["NDRE_valid_pct"] = round(float(row["NDRE_count"]) / tot20 * 100.0, 4)
    row["scl2_total_obs_20m"] = round(float(row["scl2_obs_mean"]) * float(row["scl2_obs_count"]), 2)
    row["retained_total_obs_20m"] = round(float(row["valid_obs_20m_mean"]) * float(row["valid_obs_20m_count"]), 2)
    row["scl2_share_pct"] = round(row["scl2_total_obs_20m"] / row["retained_total_obs_20m"] * 100.0, 4)

    opt_eecu = float(task_results[0]["batch_eecu_usage_seconds"])
    reduction_pct = (1.0 - opt_eecu / BASELINE_SUMMARY_EECU) * 100.0

    bench_report = {
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "boundary_source": boundary_source,
        "evi_denom_threshold": evi_denom_threshold,
        "regional_aggregation_passes": 2,
        "baseline_eecu_seconds": BASELINE_SUMMARY_EECU,
        "optimized_eecu_seconds": round(opt_eecu, 4),
        "eecu_reduction_pct": round(reduction_pct, 2),
        "wall_seconds_total": round(time.monotonic() - t_wall_start, 2),
        "warnings": warn_list,
        "task": task_results[0],
        "downloaded_files": downloaded,
        "summary_metrics": row,
    }
    (PHASE_B_DIR / "phaseB_benchmark_report.json").write_text(
        json.dumps(bench_report, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"[Phase B Benchmark] Baseline={BASELINE_SUMMARY_EECU:.2f} EECU-s | "
        f"Optimized={opt_eecu:.2f} EECU-s | Reduction={reduction_pct:.2f}%"
    )
    return bench_report


if __name__ == "__main__":
    import sys

    if "--step" in sys.argv:
        idx = sys.argv.index("--step")
        step = sys.argv[idx + 1]
    else:
        step = "diag"

    if step == "diag":
        run_step_diag()
    elif step in ("benchmark", "collect-benchmark"):
        thr = 0.05
        if "--evi-threshold" in sys.argv:
            thr = float(sys.argv[sys.argv.index("--evi-threshold") + 1])
        if step == "collect-benchmark":
            PHASE_B_DIR.mkdir(parents=True, exist_ok=True)
            t_wall_start = time.monotonic()
            with warnings.catch_warnings(record=True) as captured_warnings:
                warnings.simplefilter("always")
                ee = _import_and_init_ee()
                _, boundary_source, _ = _get_guelma_geometry(ee)
                folder_id = ensure_single_drive_folder(ee, DRIVE_FOLDER_NAME)
                recent = [t for t in ee.batch.Task.list()[:15] if t.status().get("description") == "phaseB_2024_03_summary_optimized"]
                if not recent:
                    raise RuntimeError("No phaseB_2024_03_summary_optimized task found")
                st = recent[0].status()
                if st.get("state") != "COMPLETED":
                    raise RuntimeError(f"Task not COMPLETED: {st}")
                cre, sta, upd = st.get("creation_timestamp_ms"), st.get("start_timestamp_ms"), st.get("update_timestamp_ms")
                task_rec = {
                    "name": "phaseB_2024_03_summary_optimized",
                    "file_prefix": "phaseB_2024_03_summary_optimized",
                    "kind": "table",
                    "task_id": st.get("id"),
                    "state": st.get("state"),
                    "error_message": st.get("error_message"),
                    "batch_eecu_usage_seconds": st.get("batch_eecu_usage_seconds"),
                    "run_seconds": round((upd - sta) / 1000.0, 2) if sta and upd else None,
                    "total_wall_seconds": round((upd - cre) / 1000.0, 2) if cre and upd else None,
                    "destination_uris": st.get("destination_uris"),
                }
                downloaded = download_and_verify_task_outputs(ee, [task_rec], PHASE_B_DIR, fallback_folder_id=folder_id)
                warn_list = [str(w.message) for w in captured_warnings]
            df = pd.read_csv(downloaded["phaseB_2024_03_summary_optimized.csv"]["path"])
            row = df.iloc[0].to_dict()
            tot10 = float(row["total_pixels_10m"])
            tot20 = float(row["total_pixels_20m"])
            row["NDVI_valid_pct"] = round(float(row["NDVI_count"]) / tot10 * 100.0, 4)
            row["EVI_valid_pct"] = round(float(row["EVI_count"]) / tot10 * 100.0, 4)
            row["EVI_excluded_composite_pixels"] = int(tot10 - float(row["EVI_count"]))
            row["NDMI_valid_pct"] = round(float(row["NDMI_count"]) / tot20 * 100.0, 4)
            row["NDRE_valid_pct"] = round(float(row["NDRE_count"]) / tot20 * 100.0, 4)
            row["scl2_total_obs_20m"] = round(float(row["scl2_obs_mean"]) * float(row["scl2_obs_count"]), 2)
            row["retained_total_obs_20m"] = round(float(row["valid_obs_20m_mean"]) * float(row["valid_obs_20m_count"]), 2)
            row["scl2_share_pct"] = round(row["scl2_total_obs_20m"] / row["retained_total_obs_20m"] * 100.0, 4)
            opt_eecu = float(task_rec["batch_eecu_usage_seconds"])
            reduction_pct = (1.0 - opt_eecu / BASELINE_SUMMARY_EECU) * 100.0
            bench_report = {
                "executed_utc": datetime.now(timezone.utc).isoformat(),
                "boundary_source": boundary_source,
                "evi_denom_threshold": thr,
                "regional_aggregation_passes": 2,
                "baseline_eecu_seconds": BASELINE_SUMMARY_EECU,
                "optimized_eecu_seconds": round(opt_eecu, 4),
                "eecu_reduction_pct": round(reduction_pct, 2),
                "wall_seconds_total": round(time.monotonic() - t_wall_start, 2),
                "warnings": warn_list,
                "task": task_rec,
                "downloaded_files": downloaded,
                "summary_metrics": row,
            }
            (PHASE_B_DIR / "phaseB_benchmark_report.json").write_text(
                json.dumps(bench_report, indent=2, default=str), encoding="utf-8"
            )
            print(
                f"[Phase B Benchmark] Baseline={BASELINE_SUMMARY_EECU:.2f} EECU-s | "
                f"Optimized={opt_eecu:.2f} EECU-s | Reduction={reduction_pct:.2f}%"
            )
        else:
            run_step_benchmark(evi_denom_threshold=thr)
    else:
        raise ValueError(f"Unknown --step: {step}")
