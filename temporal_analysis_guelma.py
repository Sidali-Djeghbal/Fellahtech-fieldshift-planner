from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = Path("data/guelma_integrated_field_monthly_2024_2025.csv")
OUT_DIR = Path("outputs/temporal_analysis")
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH)
required = {"field_id", "month", "NDVI", "EVI", "NDMI", "climate_rain_sum_mm"}
missing = required - set(df.columns)
if missing:
    raise ValueError(f"Missing required columns: {sorted(missing)}")

df["date"] = pd.to_datetime(df["month"] + "-01")
df["year"] = df["date"].dt.year
m = df["date"].dt.month

# Northern Hemisphere meteorological seasons.
df["season"] = m.map({
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Autumn", 10: "Autumn", 11: "Autumn"
})

df = df.sort_values(["field_id", "date"])

print("\n===== 1. SENTINEL-2 IMAGE COUNT CHECK =====")
if "image_count" in df.columns:
    # image_count is a monthly collection count, not a per-field valid-pixel count.
    image_qc = (
        df[["month", "image_count"]]
        .drop_duplicates("month")
        .sort_values("month")
    )
    print(image_qc.to_string(index=False))
    print("\nImage-count summary:")
    print(image_qc["image_count"].describe().round(2))
    print("\nImportant: this is the monthly collection image count, "
          "not proof that every field had the same number of clear pixels.")
else:
    print("image_count column is not present in the integrated dataset.")

print("\n===== 2. SEASONAL NDVI SUMMARY =====")
seasonal = (
    df.groupby(["field_id", "year", "season"], as_index=False)
      .agg(
          NDVI_mean=("NDVI", "mean"),
          NDVI_min=("NDVI", "min"),
          NDVI_max=("NDVI", "max"),
          EVI_mean=("EVI", "mean"),
          NDMI_mean=("NDMI", "mean"),
          months_observed=("month", "nunique")
      )
)
seasonal.to_csv(OUT_DIR / "seasonal_vegetation_by_field.csv", index=False)
print(seasonal.round(3).to_string(index=False))

season_order = ["Winter", "Spring", "Summer", "Autumn"]
seasonal_plot = (
    df.groupby(["field_id", "season"])["NDVI"]
      .mean()
      .unstack("season")
      .reindex(columns=season_order)
)
ax = seasonal_plot.plot(kind="bar", figsize=(11, 5))
ax.set_title("Mean Seasonal NDVI by Field (2024-2025)")
ax.set_xlabel("Field")
ax.set_ylabel("Mean NDVI")
ax.grid(axis="y", alpha=0.3)
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(FIG_DIR / "seasonal_ndvi_by_field.png", dpi=160)
plt.close()

print("\n===== 3. YEAR-TO-YEAR SEASONAL COMPARISON =====")
year_season = (
    df.groupby(["field_id", "season", "year"])["NDVI"]
      .mean()
      .unstack("year")
)
if 2024 in year_season.columns and 2025 in year_season.columns:
    year_season["difference_2025_minus_2024"] = year_season[2025] - year_season[2024]
    print(year_season.round(3).to_string())
    year_season.to_csv(OUT_DIR / "seasonal_ndvi_year_comparison.csv")
else:
    print("Both 2024 and 2025 are not available for comparison.")

print("\n===== 4. RAINFALL-NDVI LAG CORRELATION =====")
# For lag 0: rainfall in month t vs NDVI in month t.
# For lag 1: rainfall in month t-1 vs NDVI in month t.
# For lag 2: rainfall in month t-2 vs NDVI in month t.
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
        corr = valid["NDVI"].corr(valid[col]) if len(valid) >= 3 else float("nan")
        lag_results.append({
            "field_id": field_id,
            "rainfall_lag_months": lag,
            "pearson_correlation": corr,
            "n_months": len(valid)
        })

lag_df = pd.DataFrame(lag_results)
lag_df.to_csv(OUT_DIR / "rainfall_ndvi_lag_correlations.csv", index=False)
print(lag_df.round(3).to_string(index=False))
print("Interpretation: correlations are exploratory, based on only 24 months, "
      "and do not establish causation.")

print("\n===== 5. WITHIN-FIELD NDVI ANOMALIES =====")
# Anomaly relative to each field's own 24-month mean.
field_stats = df.groupby("field_id")["NDVI"].agg(["mean", "std"]).rename(
    columns={"mean": "field_ndvi_mean", "std": "field_ndvi_std"}
)
df = df.join(field_stats, on="field_id")
df["NDVI_anomaly"] = df["NDVI"] - df["field_ndvi_mean"]
df["NDVI_zscore"] = df["NDVI_anomaly"] / df["field_ndvi_std"].replace(0, pd.NA)

anomalies = df[[
    "field_id", "month", "NDVI", "field_ndvi_mean",
    "NDVI_anomaly", "NDVI_zscore"
]].copy()
anomalies.to_csv(OUT_DIR / "ndvi_anomalies_by_field.csv", index=False)

print("\nMost negative NDVI anomalies:")
print(anomalies.nsmallest(10, "NDVI_anomaly").round(3).to_string(index=False))
print("\nMost positive NDVI anomalies:")
print(anomalies.nlargest(10, "NDVI_anomaly").round(3).to_string(index=False))

print("\n===== 6. DATA LIMITATIONS TO KEEP IN THE REPORT =====")
print("- Four nearby fields are spatial units, not confirmed crop classes.")
print("- NASA POWER climate values are shared across fields for each month.")
print("- image_count is a monthly collection count, not per-field valid-pixel coverage.")
print("- 24 months are insufficient for robust long-term climate or crop-cycle conclusions.")
print("- NDVI anomalies identify unusual greenness relative to this short period; "
      "they do not identify crop type or cause.")

print(f"\nFinished. Tables and figures saved in: {OUT_DIR.resolve()}")
