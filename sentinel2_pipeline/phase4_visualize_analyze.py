"""Phases 10 & 12: Maps, time-series charts, trend stats, and agricultural interpretation."""

from pathlib import Path
from typing import Dict

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from scipy import stats

from .config import (
    ANALYSIS_DIR,
    ANNUAL_RASTERS_DIR,
    BOUNDARY_FILE,
    FIGURES_DIR,
    MAPS_DIR,
    SEASON_ORDER,
    SEASONAL_RASTERS_DIR,
    SPATIAL_DIR,
    TARGET_CRS,
)


def _compute_trends_and_seasons(
    monthly_df: pd.DataFrame,
    seasonal_df: pd.DataFrame,
    annual_df: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """Compute annual/monthly vegetation trends (OLS + Spearman/Theil-Sen) and seasonal summaries."""
    trend_rows = []
    valid_annual = annual_df.dropna(subset=["NDVI_median"]).copy()
    years = valid_annual["year"].to_numpy(dtype=float)

    for idx in ("NDVI", "EVI", "NDMI", "NDRE"):
        col = f"{idx}_median"
        vals = valid_annual[col].to_numpy(dtype=float)
        ols = stats.linregress(years, vals)
        sen = stats.theilslopes(vals, years)
        tau, mk_p = stats.kendalltau(years, vals)
        trend_rows.append(
            {
                "index": idx,
                "period": "2017-2025",
                "n_years": len(years),
                "mean_annual_median": round(float(np.mean(vals)), 4),
                "std_annual_median": round(float(np.std(vals, ddof=1)), 4),
                "ols_slope_per_year": round(float(ols.slope), 6),
                "ols_p_value": round(float(ols.pvalue), 4),
                "ols_r2": round(float(ols.rvalue ** 2), 4),
                "theil_sen_slope_per_year": round(float(sen.slope), 6),
                "kendall_tau": round(float(tau), 4),
                "kendall_p_value": round(float(mk_p), 4),
                "statistical_note": "9-year Sentinel-2 series (2017-2025); descriptive exploratory trend only.",
            }
        )

    trends_df = pd.DataFrame(trend_rows)
    trends_df.to_csv(ANALYSIS_DIR / "vegetation_trends.csv", index=False, encoding="utf-8")

    # Complete-season summary patterns (excluding incomplete Winter 2017 if flagged)
    complete_s = seasonal_df[seasonal_df["completeness_status"] == "COMPLETE"].copy()
    s_summary = (
        complete_s.groupby("season", as_index=False)
        .agg(
            complete_years=("season_year", "count"),
            NDVI_median_mean=("NDVI_median", "mean"),
            NDVI_median_std=("NDVI_median", "std"),
            EVI_median_mean=("EVI_median", "mean"),
            NDMI_median_mean=("NDMI_median", "mean"),
            NDRE_median_mean=("NDRE_median", "mean"),
            mean_valid_pct_10m=("NDVI_valid_pct", "mean"),
        )
    )
    s_summary["rank"] = s_summary["season"].map({s: i for i, s in enumerate(SEASON_ORDER)})
    s_summary = s_summary.sort_values("rank").drop(columns=["rank"]).reset_index(drop=True)
    s_summary.to_csv(ANALYSIS_DIR / "seasonal_vegetation_patterns.csv", index=False, encoding="utf-8")

    return {"trends": trends_df, "seasonal_patterns": s_summary}


def _generate_charts(
    monthly_df: pd.DataFrame,
    seasonal_df: pd.DataFrame,
    annual_df: pd.DataFrame,
) -> None:
    """Generate the 6 required temporal and seasonal vegetation charts."""
    dates = pd.to_datetime(monthly_df["year_month"] + "-01")

    # 1. Monthly NDVI trend
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(dates, monthly_df["NDVI_median"], color="#15803d", lw=1.6, marker="o", markersize=2.5, label="Monthly Median NDVI (10 m)")
    ax.fill_between(
        dates,
        monthly_df["NDVI_median"] - monthly_df["NDVI_stdDev"],
        monthly_df["NDVI_median"] + monthly_df["NDVI_stdDev"],
        color="#86efac",
        alpha=0.35,
        label="±1 Spatial SD across Guelma",
    )
    ax.set_title("Monthly Median NDVI Trajectory — Guelma Wilaya (2017–2025, Sentinel-2 SR)")
    ax.set_xlabel("Date")
    ax.set_ylabel("NDVI (unitless)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "monthly_ndvi_trend.png", dpi=180)
    plt.close(fig)

    # 2. Seasonal NDVI comparison (complete seasons only)
    complete_s = seasonal_df[seasonal_df["completeness_status"] == "COMPLETE"]
    fig, ax = plt.subplots(figsize=(9, 5))
    data_s = [complete_s.loc[complete_s["season"] == s, "NDVI_median"].dropna().values for s in SEASON_ORDER]
    ax.boxplot(
        data_s,
        tick_labels=SEASON_ORDER,
        patch_artist=True,
        boxprops=dict(facecolor="#bbf7d0", color="#166534"),
        medianprops=dict(color="#14532d", lw=2),
    )
    ax.set_title("Seasonal Median NDVI Distribution (Complete Seasons Only, 2017–2025)")
    ax.set_xlabel("Meteorological Season")
    ax.set_ylabel("Median NDVI")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "seasonal_ndvi_comparison.png", dpi=180)
    plt.close(fig)

    # 3. Annual NDVI trend
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    yrs = annual_df["year"].to_numpy()
    vals = annual_df["NDVI_median"].to_numpy()
    ax.plot(yrs, vals, marker="o", lw=2, color="#166534", label="Annual Median NDVI (10 m)")
    ols = stats.linregress(yrs, vals)
    ax.plot(yrs, ols.slope * yrs + ols.intercept, linestyle="--", color="#dc2626", label=f"OLS Trend: {ols.slope:+.4f}/yr (p={ols.pvalue:.3f})")
    ax.set_title("Annual Median NDVI Trend — Guelma Wilaya (2017–2025, Sentinel-2 10 m)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Median NDVI")
    ax.set_xticks(yrs)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "annual_ndvi_trend.png", dpi=180)
    plt.close(fig)

    # 4. Monthly EVI
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(dates, monthly_df["EVI_median"], color="#0284c7", lw=1.6, marker="o", markersize=2.5, label="Monthly Median EVI (10 m)")
    ax.set_title("Monthly Median EVI Trajectory — Guelma Wilaya (2017–2025, Sentinel-2 SR)")
    ax.set_xlabel("Date")
    ax.set_ylabel("EVI (unitless)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "monthly_evi.png", dpi=180)
    plt.close(fig)

    # 5. Seasonal NDMI
    fig, ax = plt.subplots(figsize=(9, 5))
    data_ndmi = [complete_s.loc[complete_s["season"] == s, "NDMI_median"].dropna().values for s in SEASON_ORDER]
    ax.boxplot(
        data_ndmi,
        tick_labels=SEASON_ORDER,
        patch_artist=True,
        boxprops=dict(facecolor="#bae6fd", color="#0369a1"),
        medianprops=dict(color="#0c4a6e", lw=2),
    )
    ax.set_title("Seasonal Median NDMI Distribution (20 m, Complete Seasons, 2017–2025)\nNote: NDMI reflects canopy moisture, not direct soil moisture")
    ax.set_xlabel("Meteorological Season")
    ax.set_ylabel("Median NDMI")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "seasonal_ndmi.png", dpi=180)
    plt.close(fig)

    # 6. Annual vegetation index changes (NDVI, EVI, NDMI, NDRE)
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    for idx, col, color in [
        ("NDVI (10 m)", "NDVI_median", "#15803d"),
        ("EVI (10 m)", "EVI_median", "#0284c7"),
        ("NDMI (20 m)", "NDMI_median", "#0f766e"),
        ("NDRE (20 m)", "NDRE_median", "#b45309"),
    ]:
        ax.plot(yrs, annual_df[col], marker="o", lw=1.8, color=color, label=idx)
    ax.set_title("Annual Median Sentinel-2 Vegetation Indices — Guelma (2017–2025)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Median Index Value")
    ax.set_xticks(yrs)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "annual_vegetation_index_changes.png", dpi=180)
    plt.close(fig)


def _plot_single_band_map(
    tif_path: Path,
    band_index: int,
    title: str,
    cbar_label: str,
    cmap: str,
    vmin: float,
    vmax: float,
    out_png: Path,
    boundary_gdf: gpd.GeoDataFrame,
) -> None:
    """Plot a GeoTIFF band with boundary overlay, CRS, colorbar, and attribution."""
    with rasterio.open(tif_path) as src:
        arr = src.read(band_index).astype(float)
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        res_m = int(round(src.res[0]))

    fig, ax = plt.subplots(figsize=(10, 7.5))
    im = ax.imshow(arr, extent=extent, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax)
    boundary_gdf.boundary.plot(ax=ax, color="black", linewidth=1.2)
    cbar = fig.colorbar(im, ax=ax, shrink=0.78)
    cbar.set_label(cbar_label)
    ax.set_title(f"{title}\nCRS: {TARGET_CRS} | Resolution: {res_m} m | Source: COPERNICUS/S2_SR_HARMONIZED", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("Easting (m, UTM Zone 32N)")
    ax.set_ylabel("Northing (m, UTM Zone 32N)")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def _plot_rgb_map(
    tif_path: Path,
    band_indices: tuple,
    title: str,
    out_png: Path,
    boundary_gdf: gpd.GeoDataFrame,
) -> None:
    """Plot an RGB (True or False Color) composite from scaled reflectance GeoTIFF."""
    with rasterio.open(tif_path) as src:
        r = src.read(band_indices[0]).astype(float)
        g = src.read(band_indices[1]).astype(float)
        b = src.read(band_indices[2]).astype(float)
        if src.nodata is not None:
            for band_arr in (r, g, b):
                band_arr[band_arr == src.nodata] = np.nan
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        res_m = int(round(src.res[0]))

    rgb = np.dstack([r, g, b])
    p2, p98 = np.nanpercentile(rgb, [2, 98])
    rgb_stretch = np.clip((rgb - p2) / max(p98 - p2, 1e-6), 0.0, 1.0)
    rgb_stretch = np.nan_to_num(rgb_stretch, nan=1.0)

    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.imshow(rgb_stretch, extent=extent, origin="upper")
    boundary_gdf.boundary.plot(ax=ax, color="#facc15", linewidth=1.3)
    ax.set_title(f"{title}\nCRS: {TARGET_CRS} | Resolution: {res_m} m | Source: COPERNICUS/S2_SR_HARMONIZED", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("Easting (m, UTM Zone 32N)")
    ax.set_ylabel("Northing (m, UTM Zone 32N)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def generate_maps_if_rasters_present() -> list:
    """Generate the 10 required cartographic maps from exported GeoTIFFs if present."""
    boundary_utm = gpd.read_file(BOUNDARY_FILE).to_crs(TARGET_CRS)
    generated = []

    ann_2025_10 = ANNUAL_RASTERS_DIR / "sentinel2_annual_2025_10m.tif"
    ann_2017_10 = ANNUAL_RASTERS_DIR / "sentinel2_annual_2017_10m.tif"
    ann_2025_20 = ANNUAL_RASTERS_DIR / "sentinel2_annual_2025_20m.tif"

    if ann_2025_10.exists():
        # 1. True-color (B4, B3, B2 = bands 1, 2, 3) & 2. False-color (B8, B4, B3 = bands 4, 1, 2)
        _plot_rgb_map(ann_2025_10, (1, 2, 3), "Guelma Sentinel-2 True-Color Composite (2025 Median)", MAPS_DIR / "01_true_color_2025.png", boundary_utm)
        _plot_rgb_map(ann_2025_10, (4, 1, 2), "Guelma Sentinel-2 False-Color Vegetation Composite (B8-B4-B3, 2025)", MAPS_DIR / "02_false_color_2025.png", boundary_utm)
        generated.extend(["01_true_color_2025.png", "02_false_color_2025.png"])

    for idx_num, s_name in [(3, "spring"), (4, "summer"), (5, "autumn"), (6, "winter")]:
        p = SEASONAL_RASTERS_DIR / f"sentinel2_seasonal_{s_name}_10m.tif"
        if p.exists():
            out_name = f"{idx_num:02d}_{s_name}_ndvi.png"
            _plot_single_band_map(p, 1, f"Guelma {s_name.title()} Median NDVI (2018–2025)", "NDVI", "YlGn", 0.0, 0.8, MAPS_DIR / out_name, boundary_utm)
            generated.append(out_name)

    if ann_2025_20.exists():
        _plot_single_band_map(ann_2025_20, 1, "Guelma Median NDMI (2025, 20 m)", "NDMI", "BrBG", -0.3, 0.5, MAPS_DIR / "07_ndmi_2025.png", boundary_utm)
        _plot_single_band_map(ann_2025_20, 2, "Guelma Median NDRE (2025, 20 m)", "NDRE", "YlGn", 0.0, 0.5, MAPS_DIR / "08_ndre_2025.png", boundary_utm)
        generated.extend(["07_ndmi_2025.png", "08_ndre_2025.png"])

    if ann_2017_10.exists() and ann_2025_10.exists():
        with rasterio.open(ann_2017_10) as s17, rasterio.open(ann_2025_10) as s25:
            a17 = s17.read(5).astype(float)
            a25 = s25.read(5).astype(float)
            if s17.nodata is not None:
                a17[a17 == s17.nodata] = np.nan
            if s25.nodata is not None:
                a25[a25 == s25.nodata] = np.nan
            ext = [s25.bounds.left, s25.bounds.right, s25.bounds.bottom, s25.bounds.top]
        fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
        for ax, arr, yr in [(axes[0], a17, 2017), (axes[1], a25, 2025)]:
            im = ax.imshow(arr, extent=ext, origin="upper", cmap="YlGn", vmin=0.0, vmax=0.8)
            boundary_utm.boundary.plot(ax=ax, color="black", linewidth=1.1)
            ax.set_title(f"Annual Median NDVI — {yr} (10 m)")
            ax.set_xlabel("Easting (m)")
            ax.set_ylabel("Northing (m)")
        fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.78, label="NDVI")
        fig.suptitle("Annual Sentinel-2 NDVI Comparison: 2017 vs. 2025 (Guelma Wilaya, EPSG:32632)", fontweight="bold")
        fig.tight_layout(rect=[0, 0, 1, 0.94])
        fig.savefig(MAPS_DIR / "09_annual_ndvi_2017_vs_2025.png", dpi=180)
        plt.close(fig)
        generated.append("09_annual_ndvi_2017_vs_2025.png")

    cov_tif = SPATIAL_DIR / "sentinel2_valid_obs_count_2017_2025_20m.tif"
    if cov_tif.exists():
        with rasterio.open(cov_tif) as src_cov:
            cov_arr = src_cov.read(1).astype(float)
            if src_cov.nodata is not None:
                cov_arr[cov_arr == src_cov.nodata] = np.nan
            vmax_cov = float(np.nanpercentile(cov_arr, 99.5))
        _plot_single_band_map(cov_tif, 1, "Sentinel-2 Cloud-Free Valid Observation Count (2017–2025, 20 m)", "Valid observations", "viridis", 0, max(vmax_cov, 100.0), MAPS_DIR / "10_valid_pixel_coverage.png", boundary_utm)
        generated.append("10_valid_pixel_coverage.png")

    return generated


def write_agricultural_interpretation(
    seasonal_patterns: pd.DataFrame,
    trends_df: pd.DataFrame,
) -> None:
    """Write conservative, observation-based agricultural interpretation report."""
    text = f"""# Agricultural Interpretation — Sentinel-2 Vegetation Dynamics in Guelma (2017–2025)

## 1. Observed Seasonal Patterns
{seasonal_patterns.to_string(index=False)}

## 2. Exploratory Annual Trends (2017–2025)
{trends_df.to_string(index=False)}

## 3. Careful Scientific Interpretation & Constraints
- **Seasonal vegetation activity**: Peak greenness (`NDVI`, `EVI`) in Mediterranean northern Algeria typically occurs in Spring (`MAM`), followed by summer senescence (`JJA`) under high evaporative demand and low rainfall.
- **Persistent vegetation vs. cropland**: High year-round `NDVI` on upland zones (e.g., Djebel Mahouna / forested highlands) reflects evergreen forest/maquis rather than annual cropland; greenness alone cannot separate forest, orchard, pasture, and annual crops without validated land-cover/crop-type ground truth.
- **Moisture-related indicators (`NDMI`, `NDRE`)**: `NDMI` (`20 m`) tracks canopy liquid water content and foliage density rather than direct soil water content; `NDRE` (`20 m`) adds red-edge sensitivity to chlorophyll status without directly measuring crop nitrogen fertilization or yield.
- **Non-causal caveats**: Any observed decline in `NDVI`/`NDMI` cannot be attributed solely to drought (management shifts, harvest timing, fallow rotation, cloud-mask residual bias, or fire/clearing can produce similar signals), and Sentinel-2 indices cannot infer crop species, rotation history, or yield without in-situ calibration data.
"""
    (ANALYSIS_DIR / "agricultural_interpretation.md").write_text(text, encoding="utf-8")


def run_visualization_and_analysis(qa_outputs: Dict) -> Dict:
    """Execute Phases 10 & 12 and return generated analysis metrics and map list."""
    monthly_df = qa_outputs["monthly"]
    seasonal_df = qa_outputs["seasonal"]
    annual_df = qa_outputs["annual"]

    stats_res = _compute_trends_and_seasons(monthly_df, seasonal_df, annual_df)
    _generate_charts(monthly_df, seasonal_df, annual_df)
    maps_created = generate_maps_if_rasters_present()
    write_agricultural_interpretation(stats_res["seasonal_patterns"], stats_res["trends"])

    return {
        "trends": stats_res["trends"],
        "seasonal_patterns": stats_res["seasonal_patterns"],
        "maps_created": maps_created,
    }
