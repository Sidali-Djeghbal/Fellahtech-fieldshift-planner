"""Phase 5: Comprehensive data quality, physical consistency, coverage, and aggregation QA."""

from typing import Dict, List

import numpy as np
import pandas as pd

from .config import END_YEAR, QUALITY_DIR, START_YEAR, VARIABLES


def run_quality_assurance(
    datasets: Dict[str, pd.DataFrame],
    audit_summary: Dict,
) -> Dict[str, pd.DataFrame]:
    """Run all 12 QA checks and save quality, coverage, and aggregation reports."""
    daily_cell = datasets["daily_cell"]
    daily_guelma = datasets["daily_guelma"]
    wide_daily = datasets["wide_daily"]
    monthly = datasets["monthly"]
    seasonal = datasets["seasonal"]
    annual = datasets["annual"]

    expected_dates = pd.date_range(
        f"{START_YEAR}-01-01", f"{END_YEAR}-12-31", freq="D"
    ).strftime("%Y-%m-%d")
    expected_n_days = len(expected_dates)

    qa_rows: List[Dict] = []
    anomaly_records: List[pd.DataFrame] = []

    # 1. Duplicate records
    dup_cell = int(daily_cell.duplicated(subset=["variable", "date", "cell_id"]).sum())
    dup_reg = int(daily_guelma.duplicated(subset=["variable", "date"]).sum())
    qa_rows.append(
        {
            "check_id": "QA_01_DUPLICATES",
            "scope": "daily_cell & daily_guelma",
            "metric": "duplicate_key_rows",
            "observed_value": dup_cell + dup_reg,
            "expected_value": "0",
            "status": "PASS" if (dup_cell + dup_reg) == 0 else "FAIL",
            "details": f"daily_cell_dups={dup_cell}, daily_guelma_dups={dup_reg}",
        }
    )

    # 2. Missing dates per variable
    missing_date_counts = {}
    for var in VARIABLES:
        seen_dates = set(daily_guelma.loc[daily_guelma["variable"] == var, "date"])
        missing_date_counts[var] = len(set(expected_dates) - seen_dates)
    total_missing_dates = sum(missing_date_counts.values())
    qa_rows.append(
        {
            "check_id": "QA_02_MISSING_DATES",
            "scope": f"{START_YEAR}-01-01..{END_YEAR}-12-31 ({expected_n_days} days/var)",
            "metric": "missing_variable_dates",
            "observed_value": total_missing_dates,
            "expected_value": "0",
            "status": "PASS" if total_missing_dates == 0 else "FAIL",
            "details": str(missing_date_counts),
        }
    )

    # 3. Missing cells per day/variable
    expected_cells_by_comm = {
        comm: audit_summary["grids"]["communities"][comm]["intersecting_cells"]
        for comm in ("AG", "RE")
    }
    daily_guelma_expected = daily_guelma["community"].map(expected_cells_by_comm)
    missing_cell_days = int((daily_guelma["valid_cells"] < daily_guelma_expected).sum())
    qa_rows.append(
        {
            "check_id": "QA_03_MISSING_CELLS",
            "scope": "daily_guelma",
            "metric": "days_with_fewer_than_expected_valid_cells",
            "observed_value": missing_cell_days,
            "expected_value": "0",
            "status": "PASS" if missing_cell_days == 0 else "FLAG",
            "details": f"Expected intersecting cells: {expected_cells_by_comm}",
        }
    )

    # 4. Invalid / missing numerical values
    nan_cell = int(daily_cell["value"].isna().sum())
    inf_cell = int(np.isinf(daily_cell["value"].dropna()).sum())
    nan_reg = int(daily_guelma["weighted_mean"].isna().sum())
    qa_rows.append(
        {
            "check_id": "QA_04_NUMERIC_VALIDITY",
            "scope": "daily_cell & daily_guelma",
            "metric": "nan_or_inf_values",
            "observed_value": nan_cell + inf_cell + nan_reg,
            "expected_value": "0",
            "status": "PASS" if (nan_cell + inf_cell + nan_reg) == 0 else "FAIL",
            "details": f"nan_cell={nan_cell}, inf_cell={inf_cell}, nan_reg={nan_reg}",
        }
    )

    # 5. Unit consistency across all 60 raw files
    units_map = audit_summary["grids"]["units_by_variable"]
    unit_issues = {
        var: units
        for var, units in units_map.items()
        if len(units) != 1 or not set(units).issubset(VARIABLES[var]["expected_raw_units"])
    }
    qa_rows.append(
        {
            "check_id": "QA_05_UNIT_CONSISTENCY",
            "scope": "60 raw JSON files",
            "metric": "variables_with_inconsistent_units",
            "observed_value": len(unit_issues),
            "expected_value": "0",
            "status": "PASS" if len(unit_issues) == 0 else "FAIL",
            "details": str(units_map if not unit_issues else unit_issues),
        }
    )

    # 6. Temperature physical order: T2M_MIN <= T2M <= T2M_MAX (cell-level and regional)
    cell_temp = (
        daily_cell[daily_cell["variable"].isin(["T2M", "T2M_MAX", "T2M_MIN"])]
        .pivot(index=["date", "cell_id"], columns="variable", values="value")
        .reset_index()
    )
    cell_temp_bad = cell_temp[
        (cell_temp["T2M_MIN"] > cell_temp["T2M"] + 1e-6)
        | (cell_temp["T2M"] > cell_temp["T2M_MAX"] + 1e-6)
        | (cell_temp["T2M_MIN"] > cell_temp["T2M_MAX"] + 1e-6)
    ].copy()
    if not cell_temp_bad.empty:
        cell_temp_bad["anomaly_type"] = "cell_temp_order_violation"
        anomaly_records.append(cell_temp_bad)

    reg_temp_bad = wide_daily[
        (wide_daily["T2M_MIN"] > wide_daily["T2M"] + 1e-6)
        | (wide_daily["T2M"] > wide_daily["T2M_MAX"] + 1e-6)
        | (wide_daily["T2M_MIN"] > wide_daily["T2M_MAX"] + 1e-6)
    ][["date", "T2M_MIN", "T2M", "T2M_MAX"]].copy()
    if not reg_temp_bad.empty:
        reg_temp_bad["anomaly_type"] = "regional_temp_order_violation"
        anomaly_records.append(reg_temp_bad)

    temp_violations = len(cell_temp_bad) + len(reg_temp_bad)
    qa_rows.append(
        {
            "check_id": "QA_06_TEMPERATURE_ORDER",
            "scope": "daily_cell & daily_guelma",
            "metric": "T2M_MIN <= T2M <= T2M_MAX violations",
            "observed_value": temp_violations,
            "expected_value": "0",
            "status": "PASS" if temp_violations == 0 else "FLAG",
            "details": f"cell_violations={len(cell_temp_bad)}, regional_violations={len(reg_temp_bad)}",
        }
    )

    # 7. Non-negative rainfall
    neg_rain_cell = int(
        (daily_cell.loc[daily_cell["variable"] == "PRECTOTCORR", "value"] < 0).sum()
    )
    neg_rain_reg = int(
        (daily_guelma.loc[daily_guelma["variable"] == "PRECTOTCORR", "weighted_mean"] < 0).sum()
    )
    qa_rows.append(
        {
            "check_id": "QA_07_RAINFALL_NONNEGATIVE",
            "scope": "PRECTOTCORR",
            "metric": "negative_precipitation_records",
            "observed_value": neg_rain_cell + neg_rain_reg,
            "expected_value": "0",
            "status": "PASS" if (neg_rain_cell + neg_rain_reg) == 0 else "FLAG",
            "details": f"cell={neg_rain_cell}, regional={neg_rain_reg}",
        }
    )

    # 8. Relative humidity in [0, 100]
    rh_vals = daily_cell.loc[daily_cell["variable"] == "RH2M", "value"]
    rh_out_cell = int(((rh_vals < 0) | (rh_vals > 100)).sum())
    rh_reg_vals = daily_guelma.loc[daily_guelma["variable"] == "RH2M", "weighted_mean"]
    rh_out_reg = int(((rh_reg_vals < 0) | (rh_reg_vals > 100)).sum())
    qa_rows.append(
        {
            "check_id": "QA_08_RH2M_BOUNDS",
            "scope": "RH2M",
            "metric": "values_outside_0_100_pct",
            "observed_value": rh_out_cell + rh_out_reg,
            "expected_value": "0",
            "status": "PASS" if (rh_out_cell + rh_out_reg) == 0 else "FLAG",
            "details": f"cell={rh_out_cell}, regional={rh_out_reg}, range=({rh_vals.min():.2f}, {rh_vals.max():.2f})",
        }
    )

    # 9. Non-negative solar radiation
    sol_cell = int(
        (daily_cell.loc[daily_cell["variable"] == "ALLSKY_SFC_SW_DWN", "value"] < 0).sum()
    )
    sol_reg = int(
        (daily_guelma.loc[daily_guelma["variable"] == "ALLSKY_SFC_SW_DWN", "weighted_mean"] < 0).sum()
    )
    qa_rows.append(
        {
            "check_id": "QA_09_SOLAR_NONNEGATIVE",
            "scope": "ALLSKY_SFC_SW_DWN",
            "metric": "negative_irradiance_records",
            "observed_value": sol_cell + sol_reg,
            "expected_value": "0",
            "status": "PASS" if (sol_cell + sol_reg) == 0 else "FLAG",
            "details": f"cell={sol_cell}, regional={sol_reg}",
        }
    )

    # 10. Aggregation consistency across daily -> monthly -> seasonal -> annual
    agg_checks = []
    # Check monthly rainfall sum == annual rainfall sum per year
    m_rain_by_y = monthly.groupby("year")["PRECTOTCORR_sum_mm"].sum()
    a_rain_by_y = annual.set_index("year")["PRECTOTCORR_sum_mm"]
    rain_diff_ma = float((m_rain_by_y - a_rain_by_y).abs().max())
    agg_checks.append(
        {
            "check": "monthly_sum_vs_annual_PRECTOTCORR",
            "max_abs_diff": rain_diff_ma,
            "status": "PASS" if rain_diff_ma < 1e-9 else "FAIL",
        }
    )

    # Check daily vs annual mean/sum for all 6 variables
    d_rain_by_y = wide_daily.groupby("year")["PRECTOTCORR"].sum()
    rain_diff_da = float((d_rain_by_y - a_rain_by_y).abs().max())
    agg_checks.append(
        {
            "check": "daily_sum_vs_annual_PRECTOTCORR",
            "max_abs_diff": rain_diff_da,
            "status": "PASS" if rain_diff_da < 1e-9 else "FAIL",
        }
    )

    for var, col in [
        ("T2M", "T2M_mean_C"),
        ("T2M_MAX", "T2M_MAX_mean_C"),
        ("T2M_MIN", "T2M_MIN_mean_C"),
        ("RH2M", "RH2M_mean_pct"),
        ("ALLSKY_SFC_SW_DWN", "ALLSKY_SFC_SW_DWN_mean_kwh_m2_day"),
    ]:
        d_m = wide_daily.groupby("year")[var].mean()
        a_m = annual.set_index("year")[col]
        diff = float((d_m - a_m).abs().max())
        agg_checks.append(
            {
                "check": f"daily_mean_vs_annual_{var}",
                "max_abs_diff": diff,
                "status": "PASS" if diff < 1e-9 else "FAIL",
            }
        )

    # Check seasonal sum vs daily sum over matching season_year + season
    s_rain = seasonal.set_index(["season_year", "season"])["PRECTOTCORR_sum_mm"]
    d_s_rain = wide_daily.groupby(["season_year", "season"])["PRECTOTCORR"].sum()
    diff_ds = float((s_rain - d_s_rain).abs().max())
    agg_checks.append(
        {
            "check": "daily_sum_vs_seasonal_PRECTOTCORR",
            "max_abs_diff": diff_ds,
            "status": "PASS" if diff_ds < 1e-9 else "FAIL",
        }
    )

    # Check day-weighted monthly T2M mean vs annual T2M mean
    m_weighted_t2m = (
        monthly.assign(weighted=monthly["T2M_mean_C"] * monthly["valid_days_AG"])
        .groupby("year")
        .agg(wsum=("weighted", "sum"), dsum=("valid_days_AG", "sum"))
    )
    m_to_a_t2m_diff = float(
        ((m_weighted_t2m["wsum"] / m_weighted_t2m["dsum"]) - annual.set_index("year")["T2M_mean_C"])
        .abs()
        .max()
    )
    agg_checks.append(
        {
            "check": "day_weighted_monthly_T2M_vs_annual",
            "max_abs_diff": m_to_a_t2m_diff,
            "status": "PASS" if m_to_a_t2m_diff < 1e-9 else "FAIL",
        }
    )

    agg_df = pd.DataFrame(agg_checks)
    agg_df.to_csv(QUALITY_DIR / "aggregation_validation_report.csv", index=False, encoding="utf-8")

    agg_failures = int((agg_df["status"] != "PASS").sum())
    qa_rows.append(
        {
            "check_id": "QA_10_AGGREGATION_CONSISTENCY",
            "scope": "daily -> monthly -> seasonal -> annual",
            "metric": "failed_consistency_checks",
            "observed_value": agg_failures,
            "expected_value": "0",
            "status": "PASS" if agg_failures == 0 else "FAIL",
            "details": f"max_diff={agg_df['max_abs_diff'].max():.3e}",
        }
    )

    # 11. Spatial coverage report per variable
    cov_report = (
        daily_guelma.groupby(["variable", "community"], as_index=False)
        .agg(
            total_days=("date", "count"),
            days_full_coverage=("coverage_fraction", lambda s: int((s >= 0.999999).sum())),
            days_incomplete_coverage=("coverage_fraction", lambda s: int((s < 0.999999).sum())),
            min_coverage_fraction=("coverage_fraction", "min"),
            mean_coverage_fraction=("coverage_fraction", "mean"),
            max_coverage_fraction=("coverage_fraction", "max"),
            min_valid_cells=("valid_cells", "min"),
            max_valid_cells=("valid_cells", "max"),
        )
    )
    cov_report.to_csv(QUALITY_DIR / "spatial_coverage_report.csv", index=False, encoding="utf-8")

    incomplete_cov_days = int(cov_report["days_incomplete_coverage"].sum())
    qa_rows.append(
        {
            "check_id": "QA_11_SPATIAL_COVERAGE",
            "scope": "daily_guelma",
            "metric": "variable_days_with_incomplete_coverage",
            "observed_value": incomplete_cov_days,
            "expected_value": "0",
            "status": "PASS" if incomplete_cov_days == 0 else "FLAG",
            "details": f"min_cov={cov_report['min_coverage_fraction'].min():.6f}",
        }
    )

    # 12. Coordinate consistency across all years
    coord_consistent = all(
        info["coordinate_consistent_across_all_files"]
        for info in audit_summary["grids"]["communities"].values()
    )
    qa_rows.append(
        {
            "check_id": "QA_12_COORDINATE_CONSISTENCY",
            "scope": "60 raw JSON files",
            "metric": "all_years_identical_coordinates_and_elevations",
            "observed_value": int(coord_consistent),
            "expected_value": "1",
            "status": "PASS" if coord_consistent else "FAIL",
            "details": "AG=25 cells (50 files), RE=4 cells (10 files)",
        }
    )

    qa_df = pd.DataFrame(qa_rows)
    qa_df.to_csv(QUALITY_DIR / "data_quality_report.csv", index=False, encoding="utf-8")

    if anomaly_records:
        anomalies_df = pd.concat(anomaly_records, ignore_index=True)
        anomalies_df.to_csv(QUALITY_DIR / "flagged_anomalies.csv", index=False, encoding="utf-8")

    return {
        "data_quality": qa_df,
        "spatial_coverage": cov_report,
        "aggregation_validation": agg_df,
    }
