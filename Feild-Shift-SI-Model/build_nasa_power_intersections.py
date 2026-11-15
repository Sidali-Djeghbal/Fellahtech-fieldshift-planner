
from pathlib import Path
import json
import numpy as np
import pandas as pd
import geopandas as gpd

from shapely.geometry import box
from shapely.ops import unary_union


# ============================================================
# 1. PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BOUNDARY_FILE = BASE_DIR / "guelma_wilaya_boundary.geojson"

NASA_FILE = (
    BASE_DIR
    / "data"
    / "NASA_POWER_REGIONAL"
    / "raw"
    / "T2M_MAX"
    / "T2M_MAX_2020.json"
)

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "NASA_POWER_REGIONAL"
    / "quality_check"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. LOAD GUELMA BOUNDARY
# ============================================================

print("=" * 65)
print("NASA POWER - SPATIAL INTERSECTION ANALYSIS")
print("=" * 65)

if not BOUNDARY_FILE.exists():
    raise FileNotFoundError(
        f"Boundary file not found:\n{BOUNDARY_FILE}\n"
        "Place guelma_wilaya_boundary.geojson in the project root."
    )

guelma_gdf = gpd.read_file(BOUNDARY_FILE)

if guelma_gdf.empty:
    raise ValueError("The Guelma boundary file is empty.")

if guelma_gdf.crs is None:
    raise ValueError(
        "The boundary file has no CRS. "
        "Assign its correct CRS before continuing."
    )

guelma_gdf = guelma_gdf.to_crs("EPSG:4326")

guelma_geometry = unary_union(guelma_gdf.geometry)

if not guelma_geometry.is_valid:
    guelma_geometry = guelma_geometry.buffer(0)

print("\nGuelma boundary loaded successfully.")
print("Boundary CRS:", guelma_gdf.crs)


# ============================================================
# 3. LOAD NASA POWER GRID POINTS
# ============================================================

if not NASA_FILE.exists():
    raise FileNotFoundError(
        f"NASA POWER file not found:\n{NASA_FILE}"
    )

with open(NASA_FILE, "r", encoding="utf-8") as file:
    nasa_data = json.load(file)

features = nasa_data.get("features", [])

if not features:
    raise ValueError("No grid features found in NASA POWER JSON.")

grid_points = []

for index, feature in enumerate(features):

    coordinates = feature["geometry"]["coordinates"]

    longitude = float(coordinates[0])
    latitude = float(coordinates[1])

    elevation = (
        float(coordinates[2])
        if len(coordinates) > 2
        else np.nan
    )

    grid_points.append({
        "cell_id": f"CELL_{index + 1:02d}",
        "longitude": longitude,
        "latitude": latitude,
        "elevation_m": elevation
    })

points_df = pd.DataFrame(grid_points)


# ============================================================
# 4. DETERMINE GRID SPACING
# ============================================================

unique_longitudes = np.sort(
    points_df["longitude"].unique()
)

unique_latitudes = np.sort(
    points_df["latitude"].unique()
)

longitude_diffs = np.diff(unique_longitudes)
latitude_diffs = np.diff(unique_latitudes)

if len(longitude_diffs) == 0 or len(latitude_diffs) == 0:
    raise ValueError(
        "Cannot determine grid spacing from the available points."
    )

longitude_spacing = float(np.median(longitude_diffs))
latitude_spacing = float(np.median(latitude_diffs))

# Verify regular spacing
if not np.allclose(
    longitude_diffs,
    longitude_spacing,
    atol=1e-6
):
    raise ValueError("Longitude grid is not regularly spaced.")

if not np.allclose(
    latitude_diffs,
    latitude_spacing,
    atol=1e-6
):
    raise ValueError("Latitude grid is not regularly spaced.")

print("\nGrid information:")
print(f"Number of cells: {len(points_df)}")
print(f"Longitude spacing: {longitude_spacing:.6f} degrees")
print(f"Latitude spacing: {latitude_spacing:.6f} degrees")


# ============================================================
# 5. BUILD APPROXIMATE GRID CELL POLYGONS
# ============================================================

cell_geometries = []

for _, row in points_df.iterrows():

    lon = row["longitude"]
    lat = row["latitude"]

    half_lon = longitude_spacing / 2
    half_lat = latitude_spacing / 2

    cell_polygon = box(
        lon - half_lon,
        lat - half_lat,
        lon + half_lon,
        lat + half_lat
    )

    cell_geometries.append(cell_polygon)

grid_gdf = gpd.GeoDataFrame(
    points_df.copy(),
    geometry=cell_geometries,
    crs="EPSG:4326"
)


# ============================================================
# 6. INTERSECT CELLS WITH GUELMA
# ============================================================

guelma_gdf_utm = gpd.GeoDataFrame(
    geometry=[guelma_geometry],
    crs="EPSG:4326"
).to_crs("EPSG:32632")

guelma_utm_geometry = guelma_gdf_utm.geometry.iloc[0]

grid_utm = grid_gdf.to_crs("EPSG:32632")

results = []

for _, row in grid_utm.iterrows():

    cell_geometry = row.geometry

    cell_area_km2 = cell_geometry.area / 1_000_000

    intersection = cell_geometry.intersection(
        guelma_utm_geometry
    )

    intersection_area_km2 = (
        intersection.area / 1_000_000
    )

    fraction_of_cell = (
        intersection_area_km2 / cell_area_km2
        if cell_area_km2 > 0
        else 0
    )

    results.append({
        "cell_id": row["cell_id"],
        "longitude": row["longitude"],
        "latitude": row["latitude"],
        "elevation_m": row["elevation_m"],
        "cell_area_km2": cell_area_km2,
        "intersection_area_km2": intersection_area_km2,
        "fraction_of_cell_in_guelma": fraction_of_cell,
        "intersects_guelma": intersection_area_km2 > 0,
        "center_inside_guelma": guelma_geometry.covers(
            __import__("shapely").geometry.Point(
                row["longitude"],
                row["latitude"]
            )
        )
    })

results_df = pd.DataFrame(results)


# ============================================================
# 7. CALCULATE CONTRIBUTION TO GUElMA AREA
# ============================================================

guelma_area_km2 = guelma_utm_geometry.area / 1_000_000

results_df["fraction_of_guelma_area"] = (
    results_df["intersection_area_km2"]
    / guelma_area_km2
)

results_df["fraction_of_guelma_area_pct"] = (
    results_df["fraction_of_guelma_area"] * 100
)


# ============================================================
# 8. SAVE CSV RESULTS
# ============================================================

all_cells_csv = OUTPUT_DIR / "nasa_power_grid_intersections_all.csv"

intersecting_csv = (
    OUTPUT_DIR / "nasa_power_grid_intersections_guelma.csv"
)

results_df.to_csv(all_cells_csv, index=False)

intersecting_df = results_df[
    results_df["intersects_guelma"]
].copy()

intersecting_df.to_csv(intersecting_csv, index=False)


# ============================================================
# 9. SAVE SPATIAL FILE
# ============================================================

grid_with_intersection = grid_utm.copy()

grid_with_intersection["intersection_area_km2"] = (
    results_df["intersection_area_km2"].values
)

grid_with_intersection["fraction_of_cell_in_guelma"] = (
    results_df["fraction_of_cell_in_guelma"].values
)

grid_with_intersection["intersects_guelma"] = (
    results_df["intersects_guelma"].values
)

grid_gpkg = OUTPUT_DIR / "nasa_power_grid_intersections.gpkg"

grid_with_intersection.to_file(
    grid_gpkg,
    layer="nasa_power_grid",
    driver="GPKG"
)


# ============================================================
# 10. PRINT SUMMARY
# ============================================================

print("\n" + "=" * 65)
print("SPATIAL INTERSECTION RESULTS")
print("=" * 65)

print(f"\nApproximate Guelma area: {guelma_area_km2:.2f} km²")

print(f"Total NASA POWER cells: {len(results_df)}")

print(
    "Cells intersecting Guelma:",
    len(intersecting_df)
)

print(
    "Cells not intersecting Guelma:",
    len(results_df) - len(intersecting_df)
)

print(
    "Cells with center inside Guelma:",
    int(results_df["center_inside_guelma"].sum())
)

print(
    "\nTotal intersection area: "
    f"{results_df['intersection_area_km2'].sum():.2f} km²"
)

print("\nIntersecting cells:")
print(
    intersecting_df[
        [
            "cell_id",
            "longitude",
            "latitude",
            "intersection_area_km2",
            "fraction_of_cell_in_guelma",
            "fraction_of_guelma_area_pct"
        ]
    ].to_string(index=False)
)

print("\nSaved files:")
print(all_cells_csv)
print(intersecting_csv)
print(grid_gpkg)

print("\nAnalysis completed.")
