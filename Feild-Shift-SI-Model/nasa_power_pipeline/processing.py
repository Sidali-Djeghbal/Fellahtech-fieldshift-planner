"""Phases 3 & 4: Spatial aggregation and daily/monthly/seasonal/annual dataset creation."""

import calendar
import json
import math
from typing import Dict, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd

from .config import (
    ANNUAL_DIR,
    DAILY_DIR,
    MONTHLY_DIR,
    NODATA_VALUES,
    RAW_DIR,
    SEASON_ORDER,
    SEASONAL_DIR,
    VARIABLES,
    YEARS,
    month_to_season,
)


def _season_expected_days(season_year: int, season: str) -> int:
    """Return exact calendar day count for a meteorological season."""
    if season == "Winter":
        feb_days = 29 if calendar.isleap(season_year) else 28
        return 31 + 31 + feb_days  # Dec (season_year-1) + Jan + Feb
    if season == "Spring":
        return 31 + 30 + 31  # Mar + Apr + May
    if season == "Summer":
        return 30 + 31 + 31  # Jun + Jul + Aug
    return 30 + 31 + 30  # Sep + Oct + Nov


def build_daily_cell_dataset(
    intersections_by_comm: Dict[str, gpd.GeoDataFrame],
) -> pd.DataFrame:
    """Extract daily cell-level records for intersecting cells only."""
    cell_lookup: Dict[str, Dict[Tuple[float, float], Dict]] = {}
    for community, gdf in intersections_by_comm.items():
        cell_lookup[community] = {
            (round(float(row.longitude), 6), round(float(row.latitude), 6)): {
                "cell_id": row.cell_id,
                "longitude": round(float(row.longitude), 6),
                "latitude": round(float(row.latitude), 6),
                "elevation_m": float(row.elevation_m) if pd.notna(row.elevation_m) else np.nan,
                "intersection_area_km2": float(row.intersection_area_km2),
                "area_weight": float(row.area_weight),
            }
            for row in gdf.itertuples(index=False)
        }

    records = []
    for variable, cfg in VARIABLES.items():
        community = cfg["community"]
        canonical_unit = cfg["canonical_unit"]
        selected = cell_lookup[community]

        for year in YEARS:
            json_path = RAW_DIR / variable / f"{variable}_{year}.json"
            with open(json_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            for feature in payload.get("features", []):
                coords = feature["geometry"]["coordinates"]
                lon = round(float(coords[0]), 6)
                lat = round(float(coords[1]), 6)
                if (lon, lat) not in selected:
                    continue

                meta = selected[(lon, lat)]
                values_map = feature["properties"]["parameter"][variable]
                for date_str, raw_val in values_map.items():
                    val = float(raw_val)
                    if not math.isfinite(val) or val in NODATA_VALUES:
                        val = np.nan

                    records.append(
                        {
                            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                            "year": int(date_str[:4]),
                            "month": int(date_str[4:6]),
                            "day": int(date_str[6:8]),
                            "season": month_to_season(int(date_str[4:6])),
                            "variable": variable,
                            "community": community,
                            "cell_id": meta["cell_id"],
                            "longitude": meta["longitude"],
                            "latitude": meta["latitude"],
                            "elevation_m": meta["elevation_m"],
                            "value": val,
                            "unit": canonical_unit,
                            "intersection_area_km2": meta["intersection_area_km2"],
                            "area_weight": meta["area_weight"],
                        }
                    )

    daily_cell_df = pd.DataFrame(records)
    daily_cell_df = daily_cell_df.sort_values(
        ["variable", "date", "cell_id"]
    ).reset_index(drop=True)

    daily_cell_df.to_csv(
        DAILY_DIR / "nasa_power_daily_cell_values.csv",
        index=False,
        encoding="utf-8",
    )
    return daily_cell_df


def build_daily_guelma_dataset(
    daily_cell_df: pd.DataFrame,
    total_study_area_km2: float,
) -> pd.DataFrame:
    """Compute area-weighted daily Guelma regional series with explicit coverage tracking."""
    df = daily_cell_df.copy()
    is_valid = df["value"].notna()
    df["valid_area_i"] = np.where(is_valid, df["intersection_area_km2"], 0.0)
    df["weighted_val_i"] = np.where(is_valid, df["value"] * df["intersection_area_km2"], 0.0)
    df["valid_flag"] = is_valid.astype(int)

    grouped = (
        df.groupby(
            ["date", "year", "month", "day", "season", "variable", "community", "unit"],
            as_index=False,
            sort=True,
        )
        .agg(
            weighted_sum=("weighted_val_i", "sum"),
            valid_area_km2=("valid_area_i", "sum"),
            valid_cells=("valid_flag", "sum"),
        )
    )

    grouped["weighted_mean"] = np.where(
        grouped["valid_area_km2"] > 0.0,
        grouped["weighted_sum"] / grouped["valid_area_km2"],
        np.nan,
    )
    grouped["total_study_area_km2"] = float(total_study_area_km2)
    grouped["coverage_fraction"] = grouped["valid_area_km2"] / total_study_area_km2

    cols = [
        "date",
        "year",
        "month",
        "day",
        "season",
        "variable",
        "community",
        "weighted_mean",
        "valid_cells",
        "valid_area_km2",
        "total_study_area_km2",
        "coverage_fraction",
        "unit",
    ]
    daily_guelma_df = grouped[cols].sort_values(["variable", "date"]).reset_index(drop=True)
    daily_guelma_df.to_csv(
        DAILY_DIR / "nasa_power_daily_guelma.csv",
        index=False,
        encoding="utf-8",
    )
    return daily_guelma_df


def _pivot_daily_wide(daily_guelma_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot daily regional values and community coverage into a date-indexed wide table."""
    values_wide = daily_guelma_df.pivot(
        index=["date", "year", "month", "day", "season"],
        columns="variable",
        values="weighted_mean",
    )
    cov_comm = (
        daily_guelma_df.groupby(
            ["date", "year", "month", "day", "season", "community"],
            as_index=False,
        )["coverage_fraction"]
        .min()
        .pivot(
            index=["date", "year", "month", "day", "season"],
            columns="community",
            values="coverage_fraction",
        )
        .rename(columns={"AG": "coverage_AG", "RE": "coverage_RE"})
    )
    wide = values_wide.join(cov_comm, how="inner").reset_index()
    wide["year_month"] = wide["date"].str.slice(0, 7)
    wide["season_year"] = np.where(wide["month"] == 12, wide["year"] + 1, wide["year"])
    return wide


def build_monthly_dataset(wide_daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily regional values to monthly climate statistics."""
    monthly = (
        wide_daily.groupby(["year", "month", "year_month"], as_index=False)
        .agg(
            T2M_mean_C=("T2M", "mean"),
            T2M_MAX_mean_C=("T2M_MAX", "mean"),
            T2M_MIN_mean_C=("T2M_MIN", "mean"),
            PRECTOTCORR_sum_mm=("PRECTOTCORR", "sum"),
            RH2M_mean_pct=("RH2M", "mean"),
            ALLSKY_SFC_SW_DWN_mean_kwh_m2_day=("ALLSKY_SFC_SW_DWN", "mean"),
            ALLSKY_SFC_SW_DWN_sum_kwh_m2=("ALLSKY_SFC_SW_DWN", "sum"),
            valid_days_AG=("T2M", "count"),
            valid_days_RE=("ALLSKY_SFC_SW_DWN", "count"),
            min_coverage_fraction_AG=("coverage_AG", "min"),
            mean_coverage_fraction_AG=("coverage_AG", "mean"),
            min_coverage_fraction_RE=("coverage_RE", "min"),
            mean_coverage_fraction_RE=("coverage_RE", "mean"),
        )
        .sort_values(["year", "month"])
        .reset_index(drop=True)
    )
    monthly["expected_days"] = [
        calendar.monthrange(int(r.year), int(r.month))[1]
        for r in monthly.itertuples(index=False)
    ]
    monthly.to_csv(
        MONTHLY_DIR / "nasa_power_monthly_guelma.csv",
        index=False,
        encoding="utf-8",
    )
    return monthly


def build_seasonal_dataset(wide_daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily regional values to meteorological seasons (Dec assigned to next winter year)."""
    seasonal = (
        wide_daily.groupby(["season_year", "season"], as_index=False)
        .agg(
            T2M_mean_C=("T2M", "mean"),
            T2M_MAX_mean_C=("T2M_MAX", "mean"),
            T2M_MIN_mean_C=("T2M_MIN", "mean"),
            PRECTOTCORR_sum_mm=("PRECTOTCORR", "sum"),
            RH2M_mean_pct=("RH2M", "mean"),
            ALLSKY_SFC_SW_DWN_mean_kwh_m2_day=("ALLSKY_SFC_SW_DWN", "mean"),
            valid_days_AG=("T2M", "count"),
            valid_days_RE=("ALLSKY_SFC_SW_DWN", "count"),
            min_coverage_fraction_AG=("coverage_AG", "min"),
            mean_coverage_fraction_AG=("coverage_AG", "mean"),
            min_coverage_fraction_RE=("coverage_RE", "min"),
            mean_coverage_fraction_RE=("coverage_RE", "mean"),
        )
    )
    seasonal["expected_days"] = [
        _season_expected_days(int(r.season_year), r.season)
        for r in seasonal.itertuples(index=False)
    ]
    seasonal["is_complete_season"] = (
        (seasonal["valid_days_AG"] == seasonal["expected_days"])
        & (seasonal["valid_days_RE"] == seasonal["expected_days"])
    )
    seasonal["season_rank"] = seasonal["season"].map({s: i for i, s in enumerate(SEASON_ORDER)})
    seasonal = (
        seasonal.sort_values(["season_year", "season_rank"])
        .drop(columns=["season_rank"])
        .reset_index(drop=True)
    )
    seasonal.to_csv(
        SEASONAL_DIR / "nasa_power_seasonal_guelma.csv",
        index=False,
        encoding="utf-8",
    )
    return seasonal


def build_annual_dataset(wide_daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily regional values to annual statistics and 2016-2025 baseline anomalies."""
    annual = (
        wide_daily.groupby("year", as_index=False)
        .agg(
            T2M_mean_C=("T2M", "mean"),
            T2M_MAX_mean_C=("T2M_MAX", "mean"),
            T2M_MIN_mean_C=("T2M_MIN", "mean"),
            T2M_MAX_abs_C=("T2M_MAX", "max"),
            T2M_MIN_abs_C=("T2M_MIN", "min"),
            PRECTOTCORR_sum_mm=("PRECTOTCORR", "sum"),
            RH2M_mean_pct=("RH2M", "mean"),
            ALLSKY_SFC_SW_DWN_mean_kwh_m2_day=("ALLSKY_SFC_SW_DWN", "mean"),
            ALLSKY_SFC_SW_DWN_sum_kwh_m2=("ALLSKY_SFC_SW_DWN", "sum"),
            valid_days_AG=("T2M", "count"),
            valid_days_RE=("ALLSKY_SFC_SW_DWN", "count"),
            min_coverage_fraction_AG=("coverage_AG", "min"),
            mean_coverage_fraction_AG=("coverage_AG", "mean"),
            min_coverage_fraction_RE=("coverage_RE", "min"),
            mean_coverage_fraction_RE=("coverage_RE", "mean"),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )

    annual["annual_mean_diurnal_temp_range_C"] = (
        annual["T2M_MAX_mean_C"] - annual["T2M_MIN_mean_C"]
    )
    annual["annual_extreme_temp_range_C"] = (
        annual["T2M_MAX_abs_C"] - annual["T2M_MIN_abs_C"]
    )
    annual["expected_days"] = [366 if calendar.isleap(int(y)) else 365 for y in annual["year"]]

    precip_mean_2016_2025 = float(annual["PRECTOTCORR_sum_mm"].mean())
    temp_mean_2016_2025 = float(annual["T2M_mean_C"].mean())

    annual["PRECTOTCORR_anomaly_mm"] = annual["PRECTOTCORR_sum_mm"] - precip_mean_2016_2025
    annual["PRECTOTCORR_anomaly_pct"] = (
        annual["PRECTOTCORR_anomaly_mm"] / precip_mean_2016_2025 * 100.0
    )
    annual["T2M_anomaly_C"] = annual["T2M_mean_C"] - temp_mean_2016_2025

    annual.to_csv(
        ANNUAL_DIR / "nasa_power_annual_guelma.csv",
        index=False,
        encoding="utf-8",
    )
    return annual


def run_processing(
    intersections_by_comm: Dict[str, gpd.GeoDataFrame],
    total_study_area_km2: float,
) -> Dict[str, pd.DataFrame]:
    """Execute Phases 3 & 4 and return all produced DataFrames."""
    daily_cell_df = build_daily_cell_dataset(intersections_by_comm)
    daily_guelma_df = build_daily_guelma_dataset(daily_cell_df, total_study_area_km2)
    wide_daily = _pivot_daily_wide(daily_guelma_df)
    monthly_df = build_monthly_dataset(wide_daily)
    seasonal_df = build_seasonal_dataset(wide_daily)
    annual_df = build_annual_dataset(wide_daily)

    return {
        "daily_cell": daily_cell_df,
        "daily_guelma": daily_guelma_df,
        "wide_daily": wide_daily,
        "monthly": monthly_df,
        "seasonal": seasonal_df,
        "annual": annual_df,
    }
