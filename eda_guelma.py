from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = Path("data/guelma_integrated_field_monthly_2024_2025.csv")
FIG_DIR = Path("outputs/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["month"] + "-01")
df = df.sort_values(["field_id", "date"])

print("\n===== DATASET OVERVIEW =====")
print("Shape:", df.shape)
print("Fields:", sorted(df["field_id"].dropna().unique()))
print("Date range:", df["date"].min().date(), "to", df["date"].max().date())
print("\nRows per field:")
print(df.groupby("field_id").size())

print("\n===== DUPLICATE CHECK =====")
print("Duplicate field-month rows:",
      df.duplicated(subset=["field_id", "month"]).sum())

print("\n===== MISSING VALUES =====")
missing = df.isna().sum()
print(missing[missing > 0] if (missing > 0).any() else "No missing values.")

key_vars = [
    "NDVI", "EVI", "NDMI",
    "climate_T2M_mean_C", "climate_T2M_MAX_mean_C",
    "climate_T2M_MIN_mean_C", "climate_rain_sum_mm",
    "climate_RH2M_mean_pct", "climate_solar_MJ_m2_day"
]
print("\n===== VEGETATION AND CLIMATE SUMMARY =====")
print(df[key_vars].describe().round(3))

soil_vars = [
    "clay_pct_0_5", "sand_pct_0_5", "silt_pct_0_5",
    "soc_g_kg_0_5", "ph_0_5", "cec_cmol_kg_0_5",
    "nitrogen_g_kg_0_5"
]
soil_vars = [col for col in soil_vars if col in df.columns]

print("\n===== SOIL DATA CHECK =====")
if soil_vars:
    print(df.groupby("field_id")[soil_vars].first().round(3))
else:
    print("Expected soil columns were not found. Available columns:")
    print(df.columns.tolist())

# Check whether sampled soil coordinates exist in this integrated file.
coordinate_cols = [
    col for col in df.columns
    if any(token in col.lower() for token in ["longitude", "latitude", ".geo"])
]
print("\nSoil/sample coordinate columns found:", coordinate_cols or "None")
if not coordinate_cols:
    print("The integrated CSV does not retain sample coordinates. "
          "Use the original SoilGrids CSV to compare sample coordinates.")

# Climate is one shared point series, so deduplicate by month before summary.
climate = (
    df[["date", "climate_rain_sum_mm", "climate_T2M_mean_C"]]
    .drop_duplicates("date")
    .sort_values("date")
)

print("\n===== MONTHLY CLIMATE SUMMARY (UNIQUE MONTHS) =====")
print(climate[["climate_rain_sum_mm", "climate_T2M_mean_C"]].describe().round(3))

# Plot 1: NDVI by field.
fig, ax = plt.subplots(figsize=(12, 5))
for field_id, group in df.groupby("field_id"):
    ax.plot(group["date"], group["NDVI"], marker="o",
            markersize=3, label=field_id)
ax.set_title("Monthly NDVI by Field (2024-2025)")
ax.set_xlabel("Month")
ax.set_ylabel("NDVI")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "ndvi_by_field.png", dpi=160)
plt.close(fig)

# Plot 2: unique monthly rainfall and temperature.
fig, ax1 = plt.subplots(figsize=(12, 5))
bars = ax1.bar(climate["date"], climate["climate_rain_sum_mm"],
               width=20, alpha=0.65, color="tab:blue", label="Rainfall (mm)")
ax1.set_xlabel("Month")
ax1.set_ylabel("Monthly rainfall (mm)", color="tab:blue")
ax1.grid(True, axis="y", alpha=0.3)
ax2 = ax1.twinx()
line = ax2.plot(climate["date"], climate["climate_T2M_mean_C"],
                marker="o", linewidth=1.8, color="tab:red", label="Mean Temp (°C)")
ax2.set_ylabel("Mean temperature (°C)", color="tab:red")
ax1.set_title("Monthly Climate Context at the NASA POWER Point")
handles = [bars, line[0]]
labels = [h.get_label() for h in handles]
ax1.legend(handles, labels, loc="upper right")
fig.tight_layout()
fig.savefig(FIG_DIR / "monthly_climate_context.png", dpi=160)
plt.close(fig)

# Plot 3: NDVI vs monthly rainfall by field.
fig, ax = plt.subplots(figsize=(10, 5))
for field_id, group in df.groupby("field_id"):
    ax.scatter(group["climate_rain_sum_mm"], group["NDVI"],
               alpha=0.75, label=field_id)
ax.set_title("Monthly NDVI vs. Rainfall by Field (2024-2025)")
ax.set_xlabel("Monthly rainfall (mm)")
ax.set_ylabel("NDVI")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(FIG_DIR / "ndvi_vs_rainfall.png", dpi=160)
plt.close(fig)