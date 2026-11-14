from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = Path("data/guelma_integrated_field_monthly_2024_2025.csv")
OUT_DIR = Path("outputs/temporal_analysis_v2")
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH)
required = {"field_id", "month", "NDVI", "EVI", "NDMI",
            "climate_rain_sum_mm", "image_count"}
missing = required - set(df.columns)
if missing:
    raise ValueError(f"Missing required columns: {sorted(missing)}")

df["date"] = pd.to_datetime(df["month"] + "-01")
df["year"] = df["date"].dt.year
df["month_number"] = df["date"].dt.month
df = df.sort_values(["field_id", "date"]).copy()

# Meteorological seasons in the Northern Hemisphere.
season_map = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Autumn", 10: "Autumn", 11: "Autumn"
}
df["season"] = df["month_number"].map(season_map)

# Assign December to the winter season that ends in the following year.
df["season_year"] = df["year"]
df.loc[df["month_number"] == 12, "season_year"] += 1

print("\n===== 1. DATA AND SENTINEL-2 COLLECTION COUNT QC =====")
print("Dataset shape:", df.shape)
print("Unique fields:", df["field_id"].nunique())
print("Unique months:", df["month"].nunique())
print("Date range:", df["date"].min().date(), "to", df["date"].max().date())
print("Duplicate field-month rows:",
      df.duplicated(["field_id", "month"]).sum())

# image_count in this export is identical for all fields within a month.
# Report it once per month, and do not mislabel it as valid-pixel count.
image_qc = (
    df[["month", "image_count"]]
    .drop_duplicates("month")
    .sort_values("month")
)
print("\nMonthly Sentinel-2 collection image_count:")
print(image_qc.to_string(index=False))
print("\nimage_count summary:")
print(image_qc["image_count"].describe().round(2).to_string())
print("Note: image_count is the number of images in the monthly collection, "
      "not the number of valid/cloud-free pixels in each field.")

# 2. Correct seasonal summary, with completeness flags.
season_order = ["Winter", "Spring", "Summer", "Autumn"]
seasonal = (
    df.groupby(["field_id", "season_year", "season"], as_index=False)
      .agg(
          NDVI_mean=("NDVI", "mean"),
          NDVI_min=("NDVI", "min"),
          NDVI_max=("NDVI", "max"),
          EVI_mean=("EVI", "mean"),
          NDMI_mean=("NDMI", "mean"),
          months_observed=("month", "nunique")
      )
)
seasonal["season_complete"] = seasonal.apply(
    lambda r: r["months_observed"] == 3, axis=1
)
seasonal["season"] = pd.Categorical(
    seasonal["season"], categories=season_order, ordered=True
)
seasonal = seasonal.sort_values(["field_id", "season_year", "season"])
seasonal.to_csv(OUT_DIR / "seasonal_vegetation_corrected.csv", index=False)

print("\n===== 2. CORRECTED SEASONAL NDVI =====")
print(seasonal.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print("\nSeasons with fewer than 3 months are incomplete.")
print("In this dataset, Winter 2024 contains Jan-Feb 2024 only; "
      "Winter 2025 contains Dec 2024-Feb 2025.")

# Plot season x season-year by field; incomplete season is still shown but flagged in CSV.
for field_id, group in seasonal.groupby("field_id", observed=True):
    pivot = group.pivot(index="season_year", columns="season", values="NDVI_mean")
    pivot = pivot.reindex(columns=season_order)
    ax = pivot.plot(kind="bar", figsize=(10, 4))
    ax.set_title(f"Seasonal NDVI by Season-Year — {field_id}")
    ax.set_xlabel("Season year (winter ends in this year)")
    ax.set_ylabel("Mean NDVI")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(FIG_DIR / f"{field_id.lower()}_seasonal_ndvi.png", dpi=160)
    plt.close()

# 3. Year-to-year comparison only for Spring, Summer, Autumn;
# Winter is not directly comparable because Winter 2024 is incomplete.
comparable = seasonal[
    seasonal["season"].isin(["Spring", "Summer", "Autumn"])
].copy()
year_comparison = (
    comparable.pivot_table(
        index=["field_id", "season"],
        columns="season_year",
        values="NDVI_mean",
        observed=True
    )
    .reset_index()
)
year_cols = [c for c in [2024, 2025] if c in year_comparison.columns]
if 2024 in year_comparison.columns and 2025 in year_comparison.columns:
    year_comparison["NDVI_change_2025_minus_2024"] = (
        year_comparison[2025] - year_comparison[2024]
    )
year_comparison.to_csv(
    OUT_DIR / "seasonal_year_comparison_corrected.csv", index=False
)
print("\n===== 3. YEAR COMPARISON (SPRING/SUMMER/AUTUMN ONLY) =====")
print(year_comparison.to_string(index=False))

# 4. Rainfall lag correlation, calculated using one unique climate value per month.
climate = (
    df[["date", "climate_rain_sum_mm"]]
    .drop_duplicates("date")
    .sort_values("date")
    .set_index("date")
)
climate["rain_lag_0"] = climate["climate_rain_sum_mm"]
climate["rain_lag_1"] = climate["climate_rain_sum_mm"].shift(1)
climate["rain_lag_2"] = climate["climate_rain_sum_mm"].shift(2)
rain_lags = climate[["rain_lag_0", "rain_lag_1", "rain_lag_2"]].reset_index()

lag_results = []
for field_id, group in df.groupby("field_id"):
    joined = group[["date", "NDVI"]].merge(rain_lags, on="date", how="left")
    for lag in [0, 1, 2]:
        col = f"rain_lag_{lag}"
        valid = joined[["NDVI", col]].dropna()
        lag_results.append({
            "field_id": field_id,
            "rainfall_lag_months": lag,
            "pearson_r": valid["NDVI"].corr(valid[col]) if len(valid) >= 3 else float("nan"),
            "n_months": len(valid)
        })
lag_df = pd.DataFrame(lag_results)
lag_df.to_csv(OUT_DIR / "rainfall_ndvi_lag_correlations.csv", index=False)
print("\n===== 4. RAINFALL-NDVI LAG CORRELATIONS =====")
print(lag_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print("These are exploratory correlations, not causal evidence. "
      "The effective climate time series has 24 monthly observations.")

# 5. Monthly NDVI anomalies relative to the same calendar month
# across the available two-year period. With only two years, treat as preliminary.
monthly_baseline = (
    df.groupby(["field_id", "month_number"])["NDVI"]
      .mean()
      .rename("same_month_mean_2024_2025")
)
df = df.join(monthly_baseline, on=["field_id", "month_number"])
df["same_month_NDVI_anomaly"] = (
    df["NDVI"] - df["same_month_mean_2024_2025"]
)
anomaly_cols = [
    "field_id", "month", "month_number", "NDVI",
    "same_month_mean_2024_2025", "same_month_NDVI_anomaly"
]
anomalies = df[anomaly_cols].copy()
anomalies.to_csv(OUT_DIR / "ndvi_same_month_anomalies.csv", index=False)

print("\n===== 5. SAME-CALENDAR-MONTH NDVI ANOMALIES =====")
print("Largest negative deviations:")
print(anomalies.nsmallest(8, "same_month_NDVI_anomaly").to_string(
    index=False, float_format=lambda x: f"{x:.3f}"
))
print("\nLargest positive deviations:")
print(anomalies.nlargest(8, "same_month_NDVI_anomaly").to_string(
    index=False, float_format=lambda x: f"{x:.3f}"
))

# 6. One chart showing field-level monthly NDVI deviations from their
# own same-calendar-month two-year means.
fig, ax = plt.subplots(figsize=(12, 5))
for field_id, group in df.groupby("field_id"):
    ax.plot(
        group["date"], group["same_month_NDVI_anomaly"],
        marker="o", markersize=3, label=field_id
    )
ax.axhline(0, linewidth=1)
ax.set_title("NDVI Deviation from Same Calendar Month Mean (2024-2025)")
ax.set_xlabel("Month")
ax.set_ylabel("NDVI deviation")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "ndvi_same_month_anomalies.png", dpi=160)
plt.close(fig)

print("\n===== LIMITATIONS =====")
print("- Four polygons are spatial analysis units; crop/land-use identity is unverified.")
print("- The four fields are nearby; climate values are shared across fields.")
print("- SoilGrids estimates are not field soil tests.")
print("- image_count is not a per-field valid-pixel/cloud-free observation count.")
print("- Two years are insufficient to establish a stable long-term seasonal baseline.")
print("- NDVI anomaly does not identify crop type, crop failure, or its cause.")

print(f"\nCompleted. Results saved in: {OUT_DIR.resolve()}")
