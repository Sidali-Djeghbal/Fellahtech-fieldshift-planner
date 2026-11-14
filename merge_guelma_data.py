import pandas as pd

# Keep the three source CSV files in the same folder as this script.
s2 = pd.read_csv("data/guelma_sentinel2_monthly.csv")
climate = pd.read_csv("data/guelma_nasa_power_monthly_2024_2025.csv")
soil = pd.read_csv("data/guelma_soilgrids_fields.csv")

# Sentinel-2: one record per field and month.
s2 = s2[[
    "field_id", "area_ha", "month", "NDVI", "EVI", "NDMI",
    "image_count", "land_use"
]].copy()
s2["year"] = s2["month"].str[:4].astype(int)
s2["month_number"] = s2["month"].str[5:7].astype(int)

# Climate: one record per month, shared by all four fields.
climate = climate.rename(columns={
    "month": "month_number",
    "T2M_mean_C": "climate_T2M_mean_C",
    "T2M_MAX_mean_C": "climate_T2M_MAX_mean_C",
    "T2M_MIN_mean_C": "climate_T2M_MIN_mean_C",
    "PRECTOTCORR_sum_mm": "climate_rain_sum_mm",
    "RH2M_mean_pct": "climate_RH2M_mean_pct",
    "ALLSKY_SFC_SW_DWN_mean_MJ_m2_day": "climate_solar_MJ_m2_day",
    "rainy_days_ge_1mm": "climate_rainy_days_ge_1mm",
    "daily_records": "climate_daily_records"
})

# Soil: static attributes per field. Drop geometry and technical index.
soil = soil.drop(columns=["system:index", ".geo"], errors="ignore")
soil = soil.rename(columns={"area_ha": "soil_area_ha"})

# Merge monthly climate with Sentinel-2 by year and month.
integrated = s2.merge(
    climate,
    on=["year", "month_number"],
    how="left",
    validate="many_to_one"
)

# Merge soil properties by field ID.
integrated = integrated.merge(
    soil,
    on="field_id",
    how="left",
    validate="many_to_one"
)

integrated = integrated.sort_values(["field_id", "month"]).reset_index(drop=True)

print("Dataset shape:", integrated.shape)
print("Rows per field:")
print(integrated.groupby("field_id").size())
print("Missing values:")
print(integrated.isna().sum())

integrated.to_csv(
    "data/guelma_integrated_field_monthly_2024_2025.csv",
    index=False
)
print("Saved integrated dataset.")
