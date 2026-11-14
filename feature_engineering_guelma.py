from pathlib import Path
import pandas as pd
import numpy as np

# ------------------------------------------------------------
# Guelma Field Shift SI Model
# Feature Engineering from the already integrated dataset
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data" / "guelma_integrated_field_monthly_2024_2025.csv"
OUTPUT_DIR = BASE_DIR / "outputs" / "feature_engineering"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}\n"
        "Check that the integrated CSV is inside the data/ folder."
    )

df = pd.read_csv(INPUT_FILE)

required = [
    "field_id", "month", "area_ha", "NDVI", "EVI", "NDMI", "image_count",
    "climate_T2M_mean_C", "climate_T2M_MAX_mean_C",
    "climate_T2M_MIN_mean_C", "climate_rain_sum_mm",
    "climate_RH2M_mean_pct", "climate_solar_MJ_m2_day",
    "climate_rainy_days_ge_1mm", "ph_0_5", "soc_g_kg_0_5",
    "clay_pct_0_5", "sand_pct_0_5", "silt_pct_0_5",
    "cec_cmol_kg_0_5", "nitrogen_g_kg_0_5"
]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing required columns: {missing}")

# 1. Parse dates and validate the analysis unit: field x month
df["month"] = pd.to_datetime(df["month"], errors="coerce")
if df["month"].isna().any():
    bad = df.loc[df["month"].isna()].index.tolist()[:10]
    raise ValueError(f"Unparseable month values at rows: {bad}")

df["year"] = df["month"].dt.year
df["month_number"] = df["month"].dt.month

duplicate_count = int(df.duplicated(["field_id", "month"]).sum())
if duplicate_count:
    raise ValueError(
        f"Found {duplicate_count} duplicate field-month rows. "
        "Resolve duplicates before feature engineering."
    )

df = df.sort_values(["field_id", "month"]).reset_index(drop=True)

# 2. Temporal features
month = df["month_number"]
df["season"] = np.select(
    [month.isin([12, 1, 2]), month.isin([3, 4, 5]),
     month.isin([6, 7, 8]), month.isin([9, 10, 11])],
    ["Winter", "Spring", "Summer", "Autumn"],
    default="Unknown"
)
# Winter season-year is the year in which January/February occur.
df["season_year"] = df["year"] + (month == 12).astype(int)
df["month_sin"] = np.sin(2 * np.pi * month / 12)
df["month_cos"] = np.cos(2 * np.pi * month / 12)

# 3. Vegetation dynamics
grouped = df.groupby("field_id", sort=False)
df["NDVI_change_1m"] = grouped["NDVI"].diff()
df["EVI_change_1m"] = grouped["EVI"].diff()
df["NDMI_change_1m"] = grouped["NDMI"].diff()

# 4. Recent rainfall and temperature context
# Climate data are shared across the four nearby fields. These rolling
# variables are contextual climate indicators, not independent field readings.
for window in (3,):
    df[f"rain_sum_previous_{window}m"] = grouped["climate_rain_sum_mm"].transform(
        lambda s: s.shift(1).rolling(window=window, min_periods=window).sum()
    )
    df[f"rain_mean_previous_{window}m"] = grouped["climate_rain_sum_mm"].transform(
        lambda s: s.shift(1).rolling(window=window, min_periods=window).mean()
    )
    df[f"temp_mean_previous_{window}m"] = grouped["climate_T2M_mean_C"].transform(
        lambda s: s.shift(1).rolling(window=window, min_periods=window).mean()
    )

# 5. Data-quality flags. Do not drop observations automatically.
df["sentinel_image_count_low_flag"] = (df["image_count"] < 6).astype(int)
df["sentinel_image_count_moderate_flag"] = df["image_count"].between(6, 9).astype(int)
df["vegetation_missing_flag"] = df[["NDVI", "EVI", "NDMI"]].isna().any(axis=1).astype(int)

# 6. Soil texture consistency check
texture_sum = df[["clay_pct_0_5", "sand_pct_0_5", "silt_pct_0_5"]].sum(axis=1, min_count=3)
df["soil_texture_sum_pct_0_5"] = texture_sum
df["soil_texture_sum_check_flag"] = (
    texture_sum.notna() & (~texture_sum.between(95, 105))
).astype(int)

# 7. Explicit provenance / interpretation flags
# SoilGrids are gridded model estimates, not laboratory samples.
df["soil_data_type"] = "SoilGrids gridded estimate; not field laboratory measurement"
# land_use in the source table was previously marked unverified.
if "land_use" in df.columns:
    df["land_use_status"] = "Unverified label; do not use as confirmed crop identity"

# 8. Save monthly feature table
monthly_out = OUTPUT_DIR / "guelma_field_month_features.csv"
df.to_csv(monthly_out, index=False)

# 9. Seasonal summary, only seasons with at least 2 monthly observations
seasonal = (
    df.groupby(["field_id", "season_year", "season"], as_index=False)
      .agg(
          months_observed=("month", "nunique"),
          NDVI_mean=("NDVI", "mean"),
          NDVI_std=("NDVI", "std"),
          EVI_mean=("EVI", "mean"),
          NDMI_mean=("NDMI", "mean"),
          rainfall_sum_mm=("climate_rain_sum_mm", "sum"),
          temperature_mean_C=("climate_T2M_mean_C", "mean"),
          max_temperature_mean_C=("climate_T2M_MAX_mean_C", "mean"),
          humidity_mean_pct=("climate_RH2M_mean_pct", "mean"),
          solar_mean_MJ_m2_day=("climate_solar_MJ_m2_day", "mean"),
          image_count_mean=("image_count", "mean"),
      )
)
seasonal["season_complete"] = seasonal["months_observed"].eq(3)
seasonal_out = OUTPUT_DIR / "guelma_field_season_features.csv"
seasonal.to_csv(seasonal_out, index=False)

# 10. Print validation report
print("\n===== FEATURE ENGINEERING COMPLETE =====")
print(f"Input rows: {len(df)}")
print(f"Fields: {df['field_id'].nunique()} -> {sorted(df['field_id'].unique())}")
print(f"Date range: {df['month'].min():%Y-%m} to {df['month'].max():%Y-%m}")
print(f"Duplicate field-month rows: {duplicate_count}")
print(f"Monthly feature columns: {len(df.columns)}")
print(f"Seasonal feature rows: {len(seasonal)}")
print("\nRows per field:")
print(df.groupby("field_id").size().to_string())
print("\nMissing values in key input variables:")
print(df[["NDVI", "EVI", "NDMI", "climate_rain_sum_mm",
          "climate_T2M_mean_C", "ph_0_5", "soc_g_kg_0_5"]].isna().sum().to_string())
print("\nSoil texture sum check (0-5 cm):")
print(df.groupby("field_id")["soil_texture_sum_pct_0_5"].first().round(2).to_string())
print("\nSaved:")
print(monthly_out)
print(seasonal_out)
print("\nIMPORTANT: These are engineered predictors, not an SI score or a crop recommendation.")
print("Do not treat land_use as verified crop identity or SoilGrids as lab soil tests.")
