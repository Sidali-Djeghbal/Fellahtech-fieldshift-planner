
from pathlib import Path
import json
import numpy as np
import pandas as pd
import geopandas as gpd

from shapely.geometry import box
from shapely.ops import unary_union


BASE_DIR = Path(__file__).resolve().parent

BOUNDARY_FILE = BASE_DIR / "guelma_wilaya_boundary.geojson"

NASA_FILE = (
    BASE_DIR
    / "data/NASA_POWER_REGIONAL/raw/"
    / "ALLSKY_SFC_SW_DWN/ALLSKY_SFC_SW_DWN_2020.json"
)

OUTPUT_DIR = (
    BASE_DIR
    / "data/NASA_POWER_REGIONAL/quality_check"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# 1. Load Guelma boundary
guelma = gpd.read_file(BOUNDARY_FILE)

if guelma.crs is None:
    raise ValueError("Boundary CRS is missing.")

guelma = guelma.to_crs("EPSG:4326")

guelma_geometry = unary_union(guelma.geometry)

if not guelma_geometry.is_valid:
    guelma_geometry = guelma_geometry.buffer(0)


# 2. Load RE grid
with open(NASA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data.get("features", [])

if not features:
    raise ValueError("No RE grid cells found.")

points = []

for i, feature in enumerate(features):

    coords = feature["geometry"]["coordinates"]

    points.append({
        "cell_id": f"RE_CELL_{i + 1:02d}",
        "longitude": float(coords[0]),
        "latitude": float(coords[1]),
        "elevation_m": (
            float(coords[2]) if len(coords) > 2 else np.nan
        )
    })

df = pd.DataFrame(points)

lon_values = np.sort(df.longitude.unique())
lat_values = np.sort(df.latitude.unique())

if len(lon_values) < 2 or len(lat_values) < 2:
    raise ValueError("Insufficient points to determine grid spacing.")

lon_spacing = float(np.median(np.diff(lon_values)))
lat_spacing = float(np.median(np.diff(lat_values)))

if not np.allclose(np.diff(lon_values), lon_spacing):
    raise ValueError("Irregular longitude grid.")

if not np.allclose(np.diff(lat_values), lat_spacing):
    raise ValueError("Irregular latitude grid.")

print("RE longitude spacing:", lon_spacing)
print("RE latitude spacing:", lat_spacing)


# 3. Construct approximate cell polygons
polygons = []

for _, row in df.iterrows():

    half_lon = lon_spacing / 2
    half_lat = lat_spacing / 2

    polygons.append(
        box(
            row.longitude - half_lon,
            row.latitude - half_lat,
            row.longitude + half_lon,
            row.latitude + half_lat
        )
    )

grid = gpd.GeoDataFrame(
    df,
    geometry=polygons,
    crs="EPSG:4326"
)


# 4. Project to UTM for area calculations
guelma_utm = gpd.GeoDataFrame(
    geometry=[guelma_geometry],
    crs="EPSG:4326"
).to_crs("EPSG:32632")

grid_utm = grid.to_crs("EPSG:32632")

guelma_utm_geometry = guelma_utm.geometry.iloc[0]

guelma_area = guelma_utm_geometry.area / 1_000_000


# 5. Calculate intersections
results = []

for _, row in grid_utm.iterrows():

    cell_area = row.geometry.area / 1_000_000

    intersection = row.geometry.intersection(
        guelma_utm_geometry
    )

    intersection_area = intersection.area / 1_000_000

    fraction_of_cell = (
        intersection_area / cell_area
        if cell_area > 0 else 0
    )

    fraction_of_guelma = (
        intersection_area / guelma_area
        if guelma_area > 0 else 0
    )

    results.append({
        "cell_id": row.cell_id,
        "longitude": row.longitude,
        "latitude": row.latitude,
        "elevation_m": row.elevation_m,
        "cell_area_km2": cell_area,
        "intersection_area_km2": intersection_area,
        "fraction_of_cell_in_guelma": fraction_of_cell,
        "fraction_of_guelma_area": fraction_of_guelma,
        "fraction_of_guelma_area_pct": fraction_of_guelma * 100,
        "intersects_guelma": intersection_area > 0
    })


# 6. Save results
results_df = pd.DataFrame(results)

intersecting = results_df[
    results_df.intersects_guelma
].copy()

results_df.to_csv(
    OUTPUT_DIR / "nasa_power_RE_intersections_all.csv",
    index=False
)

intersecting.to_csv(
    OUTPUT_DIR / "nasa_power_RE_intersections_guelma.csv",
    index=False
)


# 7. Print summary
print("\n" + "=" * 60)
print("NASA POWER RE INTERSECTION RESULTS")
print("=" * 60)

print(f"Guelma area: {guelma_area:.2f} km²")
print("Total RE cells:", len(results_df))
print("Intersecting cells:", len(intersecting))
print(
    "Total intersection area:",
    f"{results_df.intersection_area_km2.sum():.2f} km²"
)

print("\nIntersecting cells:")

print(
    intersecting[
        [
            "cell_id",
            "longitude",
            "latitude",
            "intersection_area_km2",
            "fraction_of_guelma_area_pct"
        ]
    ].to_string(index=False)
)

print(
    "\nSum of Guelma area percentages:",
    f"{intersecting.fraction_of_guelma_area_pct.sum():.4f}%"
)

print("\nFiles saved in:", OUTPUT_DIR)
