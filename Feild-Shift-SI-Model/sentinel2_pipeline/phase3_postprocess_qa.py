"""Phases 8, 9 & 11: Post-processing, valid-pixel coverage, and 17-point quality assurance."""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from .config import (
    ANNUAL_DIR,
    ANNUAL_RASTERS_DIR,
    BOUNDARY_FILE,
    END_YEAR,
    INDEX_SPECS,
    MONTHLY_DIR,
    NODATA_VALUE,
    QUALITY_DIR,
    RAW_EXPORTS_DIR,
    RAW_METADATA_DIR,
    SEASON_ORDER,
    SEASONAL_DIR,
    SEASONAL_RASTERS_DIR,
    SPATIAL_DIR,
    START_YEAR,
    TARGET_CRS,
)


def _standardize_summary_df(df: pd.DataFrame) -> pd.DataFrame:
    """Compute valid_pixel_pct and missing_pixel_pct without masking NoData as zero."""
    out = df.copy()
    for idx, spec in INDEX_SPECS.items():
        res = spec["analysis_resolution_m"]
        total_col = f"total_pixels_{res}m"
        count_col = f"{idx}_count"
        if count_col in out.columns and total_col in out.columns:
            out[f"{idx}_valid_pixels"] = pd.to_numeric(out[count_col], errors="coerce").fillna(0).astype(int)
            out[f"{idx}_valid_pct"] = (
                out[f"{idx}_valid_pixels"] / out[total_col].replace(0, np.nan) * 100.0
            )
            out[f"{idx}_missing_pct"] = 100.0 - out[f"{idx}_valid_pct"]
    return out


def _organize_rasters() -> List[Dict]:
    """Copy or index GEE exported GeoTIFFs into processed raster directories and inspect metadata."""
    raster_records = []
    tif_files = sorted(RAW_EXPORTS_DIR.glob("*.tif"))
    for tif in tif_files:
        name = tif.name
        if "seasonal" in name:
            dest = SEASONAL_RASTERS_DIR / name
        elif "annual" in name:
            dest = ANNUAL_RASTERS_DIR / name
        else:
            dest = SPATIAL_DIR / name

        if not dest.exists():
            shutil.copy2(tif, dest)

        with rasterio.open(dest) as src:
            res_x, res_y = src.res
            raster_records.append(
                {
                    "file": str(dest),
                    "filename": name,
                    "crs": str(src.crs),
                    "res_x_m": round(float(res_x), 4),
                    "res_y_m": round(float(res_y), 4),
                    "height": src.height,
                    "width": src.width,
                    "bands": src.count,
                    "band_descriptions": list(src.descriptions),
                    "nodata": src.nodata,
                }
            )
    return raster_records


def run_postprocess_and_qa(
    local_audit: Dict,
    gee_meta: Optional[Dict] = None,
) -> Dict:
    """Process exported GEE tables and rasters and execute all 14 QA checks."""
    raw_monthly = RAW_EXPORTS_DIR / "gee_monthly_indices_raw.csv"
    raw_seasonal = RAW_EXPORTS_DIR / "gee_seasonal_indices_raw.csv"
    raw_annual = RAW_EXPORTS_DIR / "gee_annual_indices_raw.csv"

    for req in (raw_monthly, raw_seasonal, raw_annual):
        if not req.exists():
            raise FileNotFoundError(
                f"Required GEE export CSV not found: {req}\n"
                "Run GEE exports first (--mode gee-run or place GEE Drive CSVs in data/SENTINEL2/raw/gee_exports/)."
            )

    monthly_df = _standardize_summary_df(pd.read_csv(raw_monthly))
    monthly_df["year_month"] = (
        monthly_df["year"].astype(int).astype(str)
        + "-"
        + monthly_df["month"].astype(int).astype(str).str.zfill(2)
    )
    monthly_df["is_empty_composite"] = monthly_df["NDVI_valid_pixels"] == 0
    monthly_df = monthly_df.sort_values(["year", "month"]).reset_index(drop=True)
    monthly_df.to_csv(MONTHLY_DIR / "sentinel2_monthly_indices_2017_2025.csv", index=False, encoding="utf-8")

    # Monthly spatial coverage table
    cov_cols = [
        "year",
        "month",
        "year_month",
        "image_count",
        "total_pixels_10m",
        "NDVI_valid_pixels",
        "NDVI_valid_pct",
        "NDVI_missing_pct",
        "NDVI_mean",
        "NDVI_median",
        "NDVI_stdDev",
        "total_pixels_20m",
        "NDMI_valid_pixels",
        "NDMI_valid_pct",
        "NDMI_missing_pct",
        "NDMI_mean",
        "NDMI_median",
        "NDMI_stdDev",
        "mean_valid_obs_per_px_10m",
        "mean_valid_obs_per_px_20m",
        "is_empty_composite",
    ]
    existing_cov_cols = [c for c in cov_cols if c in monthly_df.columns]
    monthly_cov = monthly_df[existing_cov_cols].copy()
    monthly_cov.to_csv(QUALITY_DIR / "sentinel2_monthly_coverage.csv", index=False, encoding="utf-8")

    # Seasonal dataset with explicit completeness status (Winter 2017 check)
    seasonal_df = _standardize_summary_df(pd.read_csv(raw_seasonal))
    dec2016_count = 0
    if gee_meta and "monthly_image_availability" in gee_meta:
        for item in gee_meta["monthly_image_availability"]:
            if item["year"] == 2016 and item["month"] == 12:
                dec2016_count = int(item["image_count"])
    elif (RAW_METADATA_DIR / "gee_collection_metadata.json").exists():
        with open(RAW_METADATA_DIR / "gee_collection_metadata.json", "r", encoding="utf-8") as f:
            gm = json.load(f)
        for item in gm.get("monthly_image_availability", []):
            if item["year"] == 2016 and item["month"] == 12:
                dec2016_count = int(item["image_count"])

    completeness = []
    for row in seasonal_df.itertuples(index=False):
        if row.NDVI_valid_pixels == 0:
            completeness.append("EMPTY")
        elif row.season == "Winter" and int(row.season_year) == START_YEAR and dec2016_count == 0:
            completeness.append("INCOMPLETE_NO_DEC2016_L2A")
        elif row.NDVI_valid_pct < 50.0:
            completeness.append("PARTIAL_LOW_COVERAGE")
        else:
            completeness.append("COMPLETE")

    seasonal_df["completeness_status"] = completeness
    seasonal_df["season_rank"] = seasonal_df["season"].map({s: i for i, s in enumerate(SEASON_ORDER)})
    seasonal_df = (
        seasonal_df.sort_values(["season_year", "season_rank"])
        .drop(columns=["season_rank"])
        .reset_index(drop=True)
    )
    seasonal_df.to_csv(SEASONAL_DIR / "sentinel2_seasonal_indices_2017_2025.csv", index=False, encoding="utf-8")

    # Annual dataset
    annual_df = _standardize_summary_df(pd.read_csv(raw_annual)).sort_values("year").reset_index(drop=True)
    annual_df.to_csv(ANNUAL_DIR / "sentinel2_annual_indices_2017_2025.csv", index=False, encoding="utf-8")

    # Temporal coverage report
    temp_rows = [
        {"level": "monthly", "expected_periods": 108, "observed_records": len(monthly_df), "non_empty_records": int((~monthly_df["is_empty_composite"]).sum())},
        {"level": "seasonal", "expected_periods": 36, "observed_records": len(seasonal_df), "non_empty_records": int((seasonal_df["completeness_status"] != "EMPTY").sum())},
        {"level": "annual", "expected_periods": 9, "observed_records": len(annual_df), "non_empty_records": int((annual_df["NDVI_valid_pixels"] > 0).sum())},
    ]
    pd.DataFrame(temp_rows).to_csv(QUALITY_DIR / "sentinel2_temporal_coverage.csv", index=False, encoding="utf-8")

    # Raster organization & metadata audit
    raster_records = _organize_rasters()

    # Build spatial GeoPackage (boundary + summary attributes)
    boundary_utm = gpd.read_file(BOUNDARY_FILE).to_crs(TARGET_CRS)
    boundary_utm["study_area_km2"] = local_audit["utm_area_km2"]
    boundary_utm["s2_period"] = f"{START_YEAR}-{END_YEAR}"
    gpkg_path = SPATIAL_DIR / "sentinel2_guelma_vegetation_maps.gpkg"
    boundary_utm.to_file(gpkg_path, layer="guelma_boundary", driver="GPKG")

    # 14 mandatory QA checks
    qa_rows: List[Dict] = []

    def _add_qa(cid: str, metric: str, observed, expected, status: str, details: str):
        qa_rows.append(
            {
                "check_id": cid,
                "metric": metric,
                "observed_value": str(observed),
                "expected_value": str(expected),
                "status": status,
                "details": details,
            }
        )

    # 1. Collection availability
    _add_qa(
        "QA_01_COLLECTION_AVAILABILITY",
        "non_empty_monthly_composites",
        int((monthly_df["image_count"] > 0).sum()),
        "108",
        "PASS" if (monthly_df["image_count"] > 0).sum() == 108 else "CHECK",
        f"Empty image months={int((monthly_df['image_count'] == 0).sum())}",
    )

    # 2. Missing months
    expected_ym = {f"{y}-{m:02d}" for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)}
    missing_ym = sorted(expected_ym - set(monthly_df["year_month"]))
    _add_qa(
        "QA_02_MISSING_MONTHS",
        "missing_year_months",
        len(missing_ym),
        "0",
        "PASS" if not missing_ym else "FAIL",
        f"missing={missing_ym}",
    )

    # 3. Missing seasons
    incomplete_seasons = seasonal_df[seasonal_df["completeness_status"] != "COMPLETE"][["season_year", "season", "completeness_status"]]
    _add_qa(
        "QA_03_SEASONAL_COMPLETENESS",
        "incomplete_or_empty_seasons",
        len(incomplete_seasons),
        "0 (or documented boundary Winter 2017)",
        "PASS" if len(incomplete_seasons) == 0 else "CHECK",
        incomplete_seasons.to_dict(orient="records"),
    )

    # 4. Missing years
    missing_years = sorted(set(range(START_YEAR, END_YEAR + 1)) - set(annual_df["year"].astype(int)))
    _add_qa(
        "QA_04_MISSING_YEARS",
        "missing_years",
        len(missing_years),
        "0",
        "PASS" if not missing_years else "FAIL",
        f"missing={missing_years}",
    )

    # 5. Cloud-mask effectiveness (check months with <50% valid pixels)
    low_cov_months = monthly_df[monthly_df["NDVI_valid_pct"] < 50.0]["year_month"].tolist()
    _add_qa(
        "QA_05_CLOUD_MASK_COVERAGE",
        "months_below_50pct_valid_pixels",
        len(low_cov_months),
        "0",
        "PASS" if not low_cov_months else "CHECK",
        f"low_coverage_months={low_cov_months}",
    )

    # 6. Valid observation counts
    min_obs_10 = float(monthly_df["mean_valid_obs_per_px_10m"].min())
    _add_qa(
        "QA_06_VALID_OBSERVATION_COUNTS",
        "min_monthly_mean_valid_obs_per_px_10m",
        round(min_obs_10, 3),
        "> 0",
        "PASS" if min_obs_10 > 0 else "CHECK",
        f"median={monthly_df['mean_valid_obs_per_px_10m'].median():.2f}",
    )

    # 7. Spatial coverage (enforce consistent polygon-raster domain <= 100.0%)
    min_cov_pct = float(monthly_df["NDVI_valid_pct"].min())
    max_cov_pct = float(monthly_df["NDVI_valid_pct"].max())
    if max_cov_pct > 100.0 + 1e-6:
        cov_status = "FAIL"
    elif min_cov_pct >= 80.0:
        cov_status = "PASS"
    else:
        cov_status = "CHECK"
    _add_qa(
        "QA_07_SPATIAL_COVERAGE",
        "min_monthly_valid_pixel_pct_10m",
        round(min_cov_pct, 2),
        "0 < pct <= 100.0% (no domain mismatch)",
        cov_status,
        f"mean_valid_pct={monthly_df['NDVI_valid_pct'].mean():.2f}%, max_valid_pct={max_cov_pct:.4f}%",
    )

    # 8. NoData pixels
    mean_missing_pct = float(monthly_df["NDVI_missing_pct"].mean())
    _add_qa(
        "QA_08_NODATA_PIXELS",
        "mean_monthly_missing_pixel_pct",
        round(mean_missing_pct, 2),
        "Reported explicitly (not zero-filled)",
        "PASS" if mean_missing_pct < 20 else "CHECK",
        f"max_missing_pct={monthly_df['NDVI_missing_pct'].max():.2f}%",
    )

    # 9. Unexpected index values (diagnostic check without silent clipping)
    oob_issues = {}
    for idx in ("NDVI", "EVI", "NDMI", "NDRE"):
        col_med = f"{idx}_median"
        if col_med in monthly_df.columns:
            vals = monthly_df[col_med].dropna()
            oob = int(((vals < -1.0) | (vals > 1.0)).sum())
            if oob > 0:
                oob_issues[idx] = oob
    _add_qa(
        "QA_09_INDEX_PHYSICAL_RANGE",
        "monthly_medians_outside_-1_to_1",
        sum(oob_issues.values()),
        "0",
        "PASS" if not oob_issues else "CHECK",
        str(oob_issues if oob_issues else "All index medians within [-1, 1]"),
    )

    # 10. Reflectance scaling check (EVI denominator uses scaled reflectance 0..1)
    evi_med_max = float(monthly_df["EVI_median"].max())
    _add_qa(
        "QA_10_REFLECTANCE_SCALING",
        "max_monthly_EVI_median",
        round(evi_med_max, 4),
        "within [-1, 1] (confirms 1/10000 scaling)",
        "PASS" if -1.0 <= evi_med_max <= 1.0 else "FAIL",
        "Reflectance bands scaled by 0.0001 before index formulas",
    )

    # 11. Resolution consistency (10 m for NDVI/EVI; 20 m for NDMI/NDRE)
    bad_res = [
        r["filename"]
        for r in raster_records
        if ("_10m" in r["filename"] and r["res_x_m"] != 10.0)
        or ("_20m" in r["filename"] and r["res_x_m"] != 20.0)
    ]
    _add_qa(
        "QA_11_RESOLUTION_CONSISTENCY",
        "exported_rasters_matching_nominal_10m_20m",
        len(raster_records) - len(bad_res),
        f"{len(raster_records)} exported GeoTIFFs",
        "PASS" if not bad_res and len(raster_records) > 0 else ("CHECK" if not raster_records else "FAIL"),
        f"bad_res={bad_res}" if raster_records else "No GeoTIFFs in raw/gee_exports yet",
    )

    # 12. Projection consistency
    bad_crs = [r["filename"] for r in raster_records if r["crs"] != TARGET_CRS]
    _add_qa(
        "QA_12_PROJECTION_CONSISTENCY",
        "rasters_in_EPSG_32632",
        len(raster_records) - len(bad_crs),
        f"{len(raster_records)} in {TARGET_CRS}",
        "PASS" if not bad_crs and len(raster_records) > 0 else ("CHECK" if not raster_records else "FAIL"),
        f"bad_crs={bad_crs}" if raster_records else "No GeoTIFFs in raw/gee_exports yet",
    )

    # 13. Duplicate timestamps
    dup_ym = int(monthly_df.duplicated(subset=["year", "month"]).sum())
    dup_s = int(seasonal_df.duplicated(subset=["season_year", "season"]).sum())
    dup_a = int(annual_df.duplicated(subset=["year"]).sum())
    _add_qa(
        "QA_13_DUPLICATE_TIMESTAMPS",
        "duplicate_period_rows",
        dup_ym + dup_s + dup_a,
        "0",
        "PASS" if (dup_ym + dup_s + dup_a) == 0 else "FAIL",
        f"monthly={dup_ym}, seasonal={dup_s}, annual={dup_a}",
    )

    # 14. Empty composites
    empty_m = int(monthly_df["is_empty_composite"].sum())
    _add_qa(
        "QA_14_EMPTY_COMPOSITES",
        "empty_monthly_composites",
        empty_m,
        "0",
        "PASS" if empty_m == 0 else "CHECK",
        f"empty_months={monthly_df.loc[monthly_df['is_empty_composite'], 'year_month'].tolist()}",
    )

    # 15. Evaluate SCL Class 2 (Dark area pixels) share from GEE collection audit
    scl2_info = (gee_meta or {}).get("scl_class_2_evaluation", {})
    if scl2_info:
        shares = {k: v.get("scl2_share_of_retained_pct", 0.0) for k, v in scl2_info.items()}
        max_scl2_pct = max(shares.values()) if shares else 0.0
        _add_qa(
            "QA_15_SCL2_DARK_PIXEL_EVAL",
            "max_sample_scl2_share_pct",
            round(max_scl2_pct, 3),
            "Retained by default & monitored (<15% typical)",
            "PASS" if max_scl2_pct < 15.0 else "CHECK",
            f"Retained SCL=2 share of non-cloud pixels: {shares}",
        )

    # 16. Pixel-level raw min/max diagnostic across monthly composites (NDVI & EVI, unclipped)
    if "NDVI_min" in monthly_df.columns and "NDVI_max" in monthly_df.columns:
        ndvi_raw_min = float(monthly_df["NDVI_min"].min())
        ndvi_raw_max = float(monthly_df["NDVI_max"].max())
        evi_raw_min = float(monthly_df["EVI_min"].min()) if "EVI_min" in monthly_df.columns else float("nan")
        evi_raw_max = float(monthly_df["EVI_max"].max()) if "EVI_max" in monthly_df.columns else float("nan")
        oob_px_months = int(((monthly_df["NDVI_min"] < -1.0) | (monthly_df["NDVI_max"] > 1.0)).sum())
        _add_qa(
            "QA_16_PIXEL_EXTREMES_UNCLIPPED",
            "months_with_raw_ndvi_pixel_outside_-1_1",
            oob_px_months,
            "Diagnostic only (EVI denominator guard applied; no silent clipping)",
            "PASS" if oob_px_months == 0 else "CHECK",
            f"Raw NDVI=[{ndvi_raw_min:.4f}, {ndvi_raw_max:.4f}], Raw EVI=[{evi_raw_min:.4f}, {evi_raw_max:.4f}]",
        )

    # 17. Strict NoData exterior check on exported GeoTIFFs (must be -9999, never 0)
    if raster_records:
        boundary_utm = gpd.read_file(BOUNDARY_FILE).to_crs(TARGET_CRS)
        geoms_utm = list(boundary_utm.geometry)
        bad_exterior = []
        for rec in raster_records:
            with rasterio.open(rec["file"]) as src:
                outside = geometry_mask(
                    geoms_utm,
                    out_shape=(src.height, src.width),
                    transform=src.transform,
                    all_touched=True,
                )
                if np.any(outside):
                    band1 = src.read(1)[outside]
                    zero_ext = int(np.sum(band1 == 0))
                    non_nodata_ext = int(np.sum(band1 != NODATA_VALUE))
                    if rec["nodata"] != NODATA_VALUE or zero_ext > 0 or non_nodata_ext > 0:
                        bad_exterior.append(
                            f"{rec['filename']}(nodata={rec['nodata']},ext_zero={zero_ext},ext_bad={non_nodata_ext})"
                        )
        _add_qa(
            "QA_17_NODATA_EXTERIOR_CHECK",
            "rasters_failing_strict_-9999_exterior",
            len(bad_exterior),
            f"0 (strict exterior == {NODATA_VALUE}, zero-fill == 0)",
            "PASS" if not bad_exterior else "FAIL",
            f"bad={bad_exterior}" if bad_exterior else f"Verified {len(raster_records)} GeoTIFFs",
        )
    else:
        _add_qa(
            "QA_17_NODATA_EXTERIOR_CHECK",
            "rasters_failing_strict_-9999_exterior",
            0,
            f"0 (strict exterior == {NODATA_VALUE})",
            "CHECK",
            "No GeoTIFFs in raw/gee_exports yet",
        )

    qa_df = pd.DataFrame(qa_rows)
    qa_df.to_csv(QUALITY_DIR / "sentinel2_quality_report.csv", index=False, encoding="utf-8")

    return {
        "monthly": monthly_df,
        "seasonal": seasonal_df,
        "annual": annual_df,
        "qa": qa_df,
        "rasters": raster_records,
    }
