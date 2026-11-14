
from pathlib import Path
import json
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "NASA_POWER_REGIONAL" / "raw"

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "NASA_POWER_REGIONAL"
    / "quality_check"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES = {
    "AG": RAW_DIR / "T2M_MAX" / "T2M_MAX_2020.json",
    "RE": RAW_DIR / "ALLSKY_SFC_SW_DWN" / "ALLSKY_SFC_SW_DWN_2020.json"
}

all_grids = []

print("=" * 65)
print("NASA POWER - COMMUNITY GRID INSPECTION")
print("=" * 65)

for community, filepath in SAMPLES.items():

    print(f"\n{'=' * 55}")
    print(f"COMMUNITY: {community}")
    print(f"FILE: {filepath.name}")
    print("=" * 55)

    if not filepath.exists():
        print(f"WARNING: File not found: {filepath}")
        continue

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])

    points = []

    for feature in features:

        coordinates = feature["geometry"]["coordinates"]

        points.append({
            "community": community,
            "longitude": float(coordinates[0]),
            "latitude": float(coordinates[1]),
            "elevation_m": (
                float(coordinates[2])
                if len(coordinates) > 2
                else np.nan
            )
        })

    df = pd.DataFrame(points)

    if df.empty:
        print("No points found.")
        continue

    lon_values = np.sort(df["longitude"].unique())
    lat_values = np.sort(df["latitude"].unique())

    lon_spacing = np.diff(lon_values)
    lat_spacing = np.diff(lat_values)

    print("Number of grid cells:", len(df))
    print("Unique longitudes:", lon_values.tolist())
    print("Unique latitudes:", lat_values.tolist())

    print(
        "Longitude spacing:",
        np.median(lon_spacing) if len(lon_spacing) else "Unknown"
    )

    print(
        "Latitude spacing:",
        np.median(lat_spacing) if len(lat_spacing) else "Unknown"
    )

    print("\nGrid coordinates:")
    print(
        df[
            ["longitude", "latitude", "elevation_m"]
        ].to_string(index=False)
    )

    all_grids.extend(points)

output_csv = OUTPUT_DIR / "nasa_power_community_grid_inventory.csv"

pd.DataFrame(all_grids).to_csv(output_csv, index=False)

print("\n" + "=" * 65)
print("Inspection completed.")
print("Saved:", output_csv)
