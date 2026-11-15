
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape, Point

BASE_DIR = Path(__file__).resolve().parent

GEOJSON_FILE = BASE_DIR / "guelma_wilaya_boundary.geojson"

NASA_FILE = (
    BASE_DIR
    / "data/NASA_POWER_REGIONAL/raw/T2M_MAX/T2M_MAX_2020.json"
)

OUTPUT_DIR = BASE_DIR / "data/NASA_POWER_REGIONAL/quality_check"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():

    print("=" * 60)
    print("NASA POWER SPATIAL GRID INSPECTION")
    print("=" * 60)

    # Load Guelma boundary
    with open(GEOJSON_FILE, encoding="utf-8") as f:
        geojson = json.load(f)

    polygons = [
        shape(feature["geometry"])
        for feature in geojson["features"]
    ]

    guelma_geometry = (
        polygons[0]
        if len(polygons) == 1
        else __import__("shapely").ops.unary_union(polygons)
    )

    # Load NASA POWER response
    with open(NASA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])

    records = []

    for feature in features:

        coords = feature["geometry"]["coordinates"]

        lon = coords[0]
        lat = coords[1]
        elevation = coords[2] if len(coords) > 2 else None

        point = Point(lon, lat)

        inside = guelma_geometry.covers(point)

        records.append({
            "longitude": lon,
            "latitude": lat,
            "elevation_m": elevation,
            "inside_guelma": inside,
        })

    df = pd.DataFrame(records)

    # Sort for easier inspection
    df = df.sort_values(
        ["latitude", "longitude"]
    ).reset_index(drop=True)

    # Unique grid spacing
    unique_lon = sorted(df["longitude"].unique())
    unique_lat = sorted(df["latitude"].unique())

    lon_steps = sorted(set(
        round(unique_lon[i + 1] - unique_lon[i], 6)
        for i in range(len(unique_lon) - 1)
    ))

    lat_steps = sorted(set(
        round(unique_lat[i + 1] - unique_lat[i], 6)
        for i in range(len(unique_lat) - 1)
    ))

    print("\nTotal NASA POWER cells:", len(df))

    print(
        "Cells whose center is inside Guelma:",
        int(df["inside_guelma"].sum())
    )

    print(
        "Cells whose center is outside Guelma:",
        int((~df["inside_guelma"]).sum())
    )

    print("\nUnique longitudes:", unique_lon)
    print("Unique latitudes:", unique_lat)

    print("\nLongitude spacing:", lon_steps)
    print("Latitude spacing:", lat_steps)

    print("\nCell inventory:")
    print(df.to_string(index=False))

    # Save complete inventory
    inventory_path = OUTPUT_DIR / "nasa_power_grid_inventory.csv"
    df.to_csv(inventory_path, index=False)

    # Save only points inside Guelma
    inside_path = OUTPUT_DIR / "nasa_power_grid_inside_guelma.csv"

    df[df["inside_guelma"]].to_csv(
        inside_path,
        index=False
    )

    print("\nSaved files:")
    print(inventory_path)
    print(inside_path)

    print("\nInspection completed.")


if __name__ == "__main__":
    main()
