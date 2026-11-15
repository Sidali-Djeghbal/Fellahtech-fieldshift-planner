"""Phase 6: Exploratory climate analysis, trend statistics, anomalies, and figures."""

import math
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import ANALYSIS_DIR, FIGURES_DIR, SEASON_ORDER


def _mann_kendall_and_sen(years: np.ndarray, values: np.ndarray) -> Tuple[float, float, float]:
    """Compute Theil-Sen slope, Mann-Kendall S, and normal-approx two-sided p-value."""
    n = len(values)
    slopes = []
    s_stat = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            if diff > 0:
                s_stat += 1
            elif diff < 0:
                s_stat -= 1
            dt = years[j] - years[i]
            if dt != 0:
                slopes.append(diff / dt)

    sen_slope = float(np.median(slopes)) if slopes else np.nan
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    if var_s <= 0:
        return sen_slope, float(s_stat), np.nan

    if s_stat > 0:
        z = (s_stat - 1.0) / math.sqrt(var_s)
    elif s_stat < 0:
        z = (s_stat + 1.0) / math.sqrt(var_s)
    else:
        z = 0.0

    # Two-sided p-value from standard normal CDF via erfc
    p_value = math.erfc(abs(z) / math.sqrt(2.0))
    return sen_slope, float(s_stat), float(p_value)


def _ols_trend(years: np.ndarray, values: np.ndarray) -> Tuple[float, float, float]:
    """Compute OLS linear slope (per year), intercept, and R^2."""
    slope, intercept = np.polyfit(years.astype(float), values.astype(float), 1)
    y_hat = slope * years + intercept
    ss_res = float(np.sum((values - y_hat) ** 2))
    ss_tot = float(np.sum((values - np.mean(values)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else np.nan
    return float(slope), float(intercept), float(r2)


def _max_consecutive_dry_days(precip_series: pd.Series, threshold_mm: float = 1.0) -> int:
    """Compute maximum run length of consecutive days with precipitation < threshold_mm."""
    max_run = 0
    current = 0
    for val in precip_series:
        if pd.notna(val) and val < threshold_mm:
            current += 1
            if current > max_run:
                max_run = current
        else:
            current = 0
    return int(max_run)


def compute_trends(annual_df: pd.DataFrame) -> pd.DataFrame:
    """Compute OLS and Mann-Kendall / Theil-Sen annual trends for 2016-2025."""
    years = annual_df["year"].to_numpy(dtype=float)
    targets = [
        ("T2M_mean_C", "C/year"),
        ("T2M_MAX_mean_C", "C/year"),
        ("T2M_MIN_mean_C", "C/year"),
        ("PRECTOTCORR_sum_mm", "mm/year"),
        ("RH2M_mean_pct", "%/year"),
        ("ALLSKY_SFC_SW_DWN_mean_kwh_m2_day", "kWh/m2/day per year"),
    ]

    rows = []
    for col, slope_unit in targets:
        vals = annual_df[col].to_numpy(dtype=float)
        ols_slope, ols_intercept, r2 = _ols_trend(years, vals)
        sen_slope, mk_s, mk_p = _mann_kendall_and_sen(years, vals)
        rows.append(
            {
                "indicator": col,
                "n_years": len(years),
                "period": "2016-2025",
                "mean_2016_2025": round(float(np.mean(vals)), 4),
                "std_2016_2025": round(float(np.std(vals, ddof=1)), 4),
                "ols_slope": round(ols_slope, 6),
                "ols_intercept": round(ols_intercept, 4),
                "ols_r2": round(r2, 4),
                "theil_sen_slope": round(sen_slope, 6),
                "mann_kendall_S": int(mk_s),
                "mann_kendall_p_approx": round(mk_p, 4),
                "slope_unit": slope_unit,
                "statistical_note": (
                    "10-year exploratory series (n=10); low statistical power; "
                    "not a 30-year WMO climate normal; regional grid scale."
                ),
            }
        )

    trends_df = pd.DataFrame(rows)
    trends_df.to_csv(ANALYSIS_DIR / "climate_trends.csv", index=False, encoding="utf-8")
    return trends_df


def compute_anomalies_and_drought_indicators(
    annual_df: pd.DataFrame,
    wide_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Compute annual anomalies and descriptive dry-spell / extreme indicators."""
    drought_rows = []
    for year, grp in wide_daily.groupby("year"):
        grp = grp.sort_values("date")
        drought_rows.append(
            {
                "year": int(year),
                "dry_days_lt_1mm": int((grp["PRECTOTCORR"] < 1.0).sum()),
                "very_dry_days_lt_0_1mm": int((grp["PRECTOTCORR"] < 0.1).sum()),
                "wet_days_ge_1mm": int((grp["PRECTOTCORR"] >= 1.0).sum()),
                "heavy_rain_days_ge_10mm": int((grp["PRECTOTCORR"] >= 10.0).sum()),
                "max_consecutive_dry_days_lt_1mm": _max_consecutive_dry_days(grp["PRECTOTCORR"], 1.0),
                "hot_days_tmax_ge_35C": int((grp["T2M_MAX"] >= 35.0).sum()),
                "very_hot_days_tmax_ge_40C": int((grp["T2M_MAX"] >= 40.0).sum()),
                "frost_days_tmin_le_0C": int((grp["T2M_MIN"] <= 0.0).sum()),
            }
        )

    drought_df = pd.DataFrame(drought_rows)
    merged = annual_df.merge(drought_df, on="year", how="inner")

    rain_std = float(merged["PRECTOTCORR_sum_mm"].std(ddof=1))
    temp_std = float(merged["T2M_mean_C"].std(ddof=1))
    merged["PRECTOTCORR_standardized_anomaly_z"] = (
        merged["PRECTOTCORR_anomaly_mm"] / rain_std if rain_std > 0 else np.nan
    )
    merged["T2M_standardized_anomaly_z"] = (
        merged["T2M_anomaly_C"] / temp_std if temp_std > 0 else np.nan
    )

    cols = [
        "year",
        "T2M_mean_C",
        "T2M_anomaly_C",
        "T2M_standardized_anomaly_z",
        "PRECTOTCORR_sum_mm",
        "PRECTOTCORR_anomaly_mm",
        "PRECTOTCORR_anomaly_pct",
        "PRECTOTCORR_standardized_anomaly_z",
        "RH2M_mean_pct",
        "ALLSKY_SFC_SW_DWN_mean_kwh_m2_day",
        "dry_days_lt_1mm",
        "very_dry_days_lt_0_1mm",
        "wet_days_ge_1mm",
        "heavy_rain_days_ge_10mm",
        "max_consecutive_dry_days_lt_1mm",
        "hot_days_tmax_ge_35C",
        "very_hot_days_tmax_ge_40C",
        "frost_days_tmin_le_0C",
    ]
    anomalies_df = merged[cols].sort_values("year").reset_index(drop=True)
    anomalies_df.to_csv(ANALYSIS_DIR / "climate_anomalies.csv", index=False, encoding="utf-8")
    return anomalies_df


def _generate_figures(
    anomalies_df: pd.DataFrame,
    trends_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    seasonal_df: pd.DataFrame,
) -> None:
    """Create exploratory climate analysis figures."""
    years = anomalies_df["year"].to_numpy()

    # 1. Annual temperature trend
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.plot(years, anomalies_df["T2M_mean_C"], marker="o", lw=2, color="#b91c1c", label="T2M Mean (°C)")
    t2m_row = trends_df.loc[trends_df["indicator"] == "T2M_mean_C"].iloc[0]
    ax.plot(
        years,
        t2m_row["ols_slope"] * years + t2m_row["ols_intercept"],
        linestyle="--",
        color="#7f1d1d",
        label=f"OLS Trend: {t2m_row['ols_slope']:+.3f} °C/yr (MK p={t2m_row['mann_kendall_p_approx']:.3f})",
    )
    ax.axhline(anomalies_df["T2M_mean_C"].mean(), color="#6b7280", linestyle=":", lw=1.2, label="2016–2025 Mean")
    ax.set_title("Guelma Regional Annual Mean Temperature (2016–2025, NASA POWER AG)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Temperature (°C)")
    ax.set_xticks(years)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "annual_temperature_trend.png", dpi=180)
    plt.close(fig)

    # 2. Annual rainfall trend & anomalies
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    rain_row = trends_df.loc[trends_df["indicator"] == "PRECTOTCORR_sum_mm"].iloc[0]
    ax1.bar(years, anomalies_df["PRECTOTCORR_sum_mm"], color="#2563eb", alpha=0.8, label="Annual Total Precipitation")
    ax1.plot(
        years,
        rain_row["ols_slope"] * years + rain_row["ols_intercept"],
        color="#1e3a8a",
        linestyle="--",
        lw=1.8,
        label=f"OLS Trend: {rain_row['ols_slope']:+.1f} mm/yr (MK p={rain_row['mann_kendall_p_approx']:.3f})",
    )
    ax1.axhline(anomalies_df["PRECTOTCORR_sum_mm"].mean(), color="#374151", linestyle=":", label="2016–2025 Mean")
    ax1.set_ylabel("Precipitation (mm/year)")
    ax1.set_title("Guelma Regional Annual Precipitation & Anomalies vs. 2016–2025 Mean")
    ax1.grid(True, axis="y", alpha=0.3)
    ax1.legend()

    anom_colors = ["#16a34a" if v >= 0 else "#dc2626" for v in anomalies_df["PRECTOTCORR_anomaly_mm"]]
    ax2.bar(years, anomalies_df["PRECTOTCORR_anomaly_mm"], color=anom_colors, alpha=0.85)
    ax2.axhline(0, color="black", lw=1.0)
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Rainfall Anomaly (mm)")
    ax2.set_xticks(years)
    ax2.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "annual_rainfall_trend_and_anomalies.png", dpi=180)
    plt.close(fig)

    # 3. Monthly climatology & monthly rainfall distribution
    clim = (
        monthly_df.groupby("month", as_index=False)
        .agg(
            rain_mean=("PRECTOTCORR_sum_mm", "mean"),
            t2m_mean=("T2M_mean_C", "mean"),
            tmax_mean=("T2M_MAX_mean_C", "mean"),
            tmin_mean=("T2M_MIN_mean_C", "mean"),
        )
        .sort_values("month")
    )
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig, (ax_c, ax_box) = plt.subplots(1, 2, figsize=(15, 5.5))
    ax_c.bar(clim["month"], clim["rain_mean"], color="#60a5fa", alpha=0.8, label="Mean Monthly Rainfall (mm)")
    ax_c.set_xticks(range(1, 13))
    ax_c.set_xticklabels(month_labels)
    ax_c.set_ylabel("Rainfall (mm)", color="#1d4ed8")
    ax_c.grid(True, axis="y", alpha=0.3)
    ax_t = ax_c.twinx()
    ax_t.plot(clim["month"], clim["tmax_mean"], color="#dc2626", marker="^", lw=1.5, label="Mean T2M_MAX")
    ax_t.plot(clim["month"], clim["t2m_mean"], color="#b45309", marker="o", lw=2.0, label="Mean T2M")
    ax_t.plot(clim["month"], clim["tmin_mean"], color="#0284c7", marker="v", lw=1.5, label="Mean T2M_MIN")
    ax_t.set_ylabel("Temperature (°C)", color="#991b1b")
    ax_c.set_title("Monthly Climatology (2016–2025)")
    h1, l1 = ax_c.get_legend_handles_labels()
    h2, l2 = ax_t.get_legend_handles_labels()
    ax_c.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)

    rain_by_m = [monthly_df.loc[monthly_df["month"] == m, "PRECTOTCORR_sum_mm"].values for m in range(1, 13)]
    ax_box.boxplot(rain_by_m, tick_labels=month_labels, patch_artist=True,
                   boxprops=dict(facecolor="#bfdbfe", color="#1d4ed8"),
                   medianprops=dict(color="#1e3a8a", lw=1.8))
    ax_box.set_title("Monthly Rainfall Distribution Across Years (2016–2025)")
    ax_box.set_ylabel("Monthly Precipitation (mm)")
    ax_box.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "monthly_climatology.png", dpi=180)
    plt.close(fig)

    # 4. Seasonal rainfall & temperature variation (using complete seasons only for rainfall sums!)
    complete_s = seasonal_df[seasonal_df["is_complete_season"]].copy()
    fig, (ax_sr, ax_st) = plt.subplots(1, 2, figsize=(13, 5.2))
    rain_s = [complete_s.loc[complete_s["season"] == s, "PRECTOTCORR_sum_mm"].values for s in SEASON_ORDER]
    ax_sr.boxplot(rain_s, tick_labels=SEASON_ORDER, patch_artist=True,
                  boxprops=dict(facecolor="#93c5fd", color="#1d4ed8"),
                  medianprops=dict(color="#1e3a8a", lw=1.8))
    ax_sr.set_title("Seasonal Total Rainfall (Complete Seasons Only)")
    ax_sr.set_ylabel("Seasonal Precipitation (mm)")
    ax_sr.grid(True, axis="y", alpha=0.3)

    temp_s = [complete_s.loc[complete_s["season"] == s, "T2M_mean_C"].values for s in SEASON_ORDER]
    ax_st.boxplot(temp_s, tick_labels=SEASON_ORDER, patch_artist=True,
                  boxprops=dict(facecolor="#fecaca", color="#b91c1c"),
                  medianprops=dict(color="#7f1d1d", lw=1.8))
    ax_st.set_title("Seasonal Mean Temperature (Complete Seasons Only)")
    ax_st.set_ylabel("Temperature (°C)")
    ax_st.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "seasonal_distributions.png", dpi=180)
    plt.close(fig)

    # 5. Solar radiation & relative humidity seasonal pattern
    m_sol_rh = (
        monthly_df.groupby("month", as_index=False)
        .agg(
            solar_mean=("ALLSKY_SFC_SW_DWN_mean_kwh_m2_day", "mean"),
            solar_std=("ALLSKY_SFC_SW_DWN_mean_kwh_m2_day", "std"),
            rh_mean=("RH2M_mean_pct", "mean"),
            rh_std=("RH2M_mean_pct", "std"),
        )
        .sort_values("month")
    )
    fig, ax_s = plt.subplots(figsize=(10.5, 5.2))
    l_sol = ax_s.errorbar(
        m_sol_rh["month"], m_sol_rh["solar_mean"], yerr=m_sol_rh["solar_std"],
        marker="o", lw=2, capsize=3, color="#d97706", label="Solar Radiation (RE: kWh/m²/day ± 1 SD)"
    )
    ax_s.set_xticks(range(1, 13))
    ax_s.set_xticklabels(month_labels)
    ax_s.set_xlabel("Month")
    ax_s.set_ylabel("Solar Irradiance (kWh/m²/day)", color="#b45309")
    ax_s.grid(True, alpha=0.3)

    ax_rh = ax_s.twinx()
    l_rh = ax_rh.errorbar(
        m_sol_rh["month"], m_sol_rh["rh_mean"], yerr=m_sol_rh["rh_std"],
        marker="s", lw=2, capsize=3, color="#0d9488", label="Relative Humidity (AG: % ± 1 SD)"
    )
    ax_rh.set_ylabel("Relative Humidity (%)", color="#0f766e")
    ax_s.set_title("Guelma Monthly Solar Radiation (RE) & Relative Humidity (AG) Cycle (2016–2025)")
    ax_s.legend([l_sol, l_rh], [l_sol.get_label(), l_rh.get_label()], loc="upper right", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "solar_and_humidity_seasonal_pattern.png", dpi=180)
    plt.close(fig)

    # 6. Drought & thermal extreme indicators
    fig, (ax_d1, ax_d2) = plt.subplots(1, 2, figsize=(13.5, 5.0))
    ax_d1.bar(years, anomalies_df["max_consecutive_dry_days_lt_1mm"], color="#b45309", alpha=0.85)
    ax_d1.set_title("Max Consecutive Dry Days (< 1 mm/day)")
    ax_d1.set_xlabel("Year")
    ax_d1.set_ylabel("Days")
    ax_d1.set_xticks(years)
    ax_d1.grid(True, axis="y", alpha=0.3)

    ax_d2.bar(years, anomalies_df["hot_days_tmax_ge_35C"], color="#dc2626", alpha=0.85, label="Hot Days (Tmax ≥ 35°C)")
    ax_d2.set_title("Annual Hot Days (Tmax ≥ 35°C)")
    ax_d2.set_xlabel("Year")
    ax_d2.set_ylabel("Days")
    ax_d2.set_xticks(years)
    ax_d2.grid(True, axis="y", alpha=0.3)
    ax_d2.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "drought_and_extreme_indicators.png", dpi=180)
    plt.close(fig)


def run_climate_analysis(datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Execute Phase 6 exploratory climate analysis and save tables + figures."""
    trends_df = compute_trends(datasets["annual"])
    anomalies_df = compute_anomalies_and_drought_indicators(
        datasets["annual"], datasets["wide_daily"]
    )
    _generate_figures(
        anomalies_df=anomalies_df,
        trends_df=trends_df,
        monthly_df=datasets["monthly"],
        seasonal_df=datasets["seasonal"],
    )
    return {"trends": trends_df, "anomalies": anomalies_df}
