import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

from shapely.geometry import box
from shapely.ops import unary_union


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

RAW_DIR = PROJECT_DIR / "data" / "NASA_POWER_REGIONAL" / "raw"

BOUNDARY_FILE = (
    PROJECT_DIR
    / "data"
    / "boundaries"
    / "processed"
    / "guelma_wilaya_boundary.geojson.gpkg"
)

OUTPUT_DIR = (
    PROJECT_DIR
    / "data"
    / "NASA_POWER_REGIONAL"
    / "spatial_analysis"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = range(2016, 2026)

VARIABLES = {
    "T2M": {
        "community": "AG",
        "unit": "C",
    },
    "T2M_MAX": {
        "community": "AG",
        "unit": "C",
    },
    "T2M_MIN": {
        "community": "AG",
        "unit": "C",
    },
    "PRECTOTCORR": {
        "community": "AG",
        "unit": "mm/day",
    },
    "RH2M": {
        "community": "AG",
        "unit": "%",
    },
    "ALLSKY_SFC_SW_DWN": {
        "community": "RE",
        "unit": "kWh/m2/day",
    },
}

NODATA_VALUES = {-999, -999.0, -9999, -9999.0}

# UTM Zone 32N: suitable for Guelma
AREA_CRS = "EPSG:32632"


# ============================================================
# 2. LOAD GUELMA BOUNDARY
# ============================================================

print("=" * 70)
print("NASA POWER SPATIAL PROCESSING")
print("=" * 70)

if not BOUNDARY_FILE.exists():
    raise FileNotFoundError(
        f"Boundary file not found:\n{BOUNDARY_FILE}"
    )

boundary_gdf = gpd.read_file(BOUNDARY_FILE)

if boundary_gdf.empty:
    raise ValueError("The boundary file is empty.")

if boundary_gdf.crs is None:
    raise ValueError(
        "The boundary file has no CRS. "
        "Please define its correct coordinate reference system."
    )

boundary_gdf = boundary_gdf.to_crs(AREA_CRS)

guelma_geometry = unary_union(boundary_gdf.geometry)

if guelma_geometry.is_empty:
    raise ValueError("Could not create the Guelma boundary geometry.")

guelma_area_km2 = guelma_geometry.area / 1_000_000

print(f"\nBoundary loaded: {BOUNDARY_FILE.name}")
print(f"Guelma area: {guelma_area_km2:.2f} km2")


# ============================================================
# 3. READ NASA POWER JSON FILES
# ============================================================

all_features = {}
all_cell_coordinates = {}

print("\nReading NASA POWER JSON files...")

for variable, config in VARIABLES.items():

    community = config["community"]

    all_features[variable] = []

    for year in YEARS:

        json_path = (
            RAW_DIR
            / variable
            / f"{variable}_{year}.json"
        )

        if not json_path.exists():
            raise FileNotFoundError(
                f"Missing NASA POWER file: {json_path}"
            )

        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        features = data.get("features", [])

        if not features:
            raise ValueError(
                f"No features found in {json_path}"
            )

        for feature in features:

            coordinates = feature["geometry"]["coordinates"]

            lon = float(coordinates[0])
            lat = float(coordinates[1])

            cell_key = (
                community,
                round(lon, 6),
                round(lat, 6),
            )

            properties = (
                feature.get("properties", {})
                .get("parameter", {})
                .get(variable, {})
            )

            if not properties:
                raise ValueError(
                    f"No values for {variable} in {json_path}"
                )

            all_features[variable].append({
                "year": year,
                "cell_key": cell_key,
                "lon": lon,
                "lat": lat,
                "values": properties,
            })

            all_cell_coordinates[cell_key] = {
                "community": community,
                "lon": lon,
                "lat": lat,
            }

    print(
        f"[OK] {variable}: "
        f"{len(all_features[variable])} feature-year records"
    )


# ============================================================
# 4. ESTIMATE GRID CELL BOUNDARIES
# ============================================================

def calculate_axis_edges(values):
    """
    Estimate cell edges from sorted cell-center coordinates.

    Internal edges are midpoints between adjacent centers.
    External edges are extrapolated by half the nearest spacing.
    """

    values = sorted(set(round(float(v), 8) for v in values))

    if len(values) < 2:
        raise ValueError(
            "At least two distinct grid centers are required "
            "on each axis to estimate cell boundaries."
        )

    values = np.array(values, dtype=float)

    differences = np.diff(values)

    if np.any(differences <= 0):
        raise ValueError("Invalid grid coordinates.")

    edges = np.zeros(len(values) + 1)

    edges[1:-1] = (
        values[:-1] + values[1:]
    ) / 2

    edges[0] = values[0] - differences[0] / 2
    edges[-1] = values[-1] + differences[-1] / 2

    return {
        round(float(center), 6): (
            float(edges[i]),
            float(edges[i + 1]),
        )
        for i, center in enumerate(values)
    }


def build_community_cells(community):

    coordinates = [
        value
        for key, value in all_cell_coordinates.items()
        if value["community"] == community
    ]

    if not coordinates:
        raise ValueError(
            f"No coordinates found for community {community}"
        )

    longitudes = [
        item["lon"] for item in coordinates
    ]

    latitudes = [
        item["lat"] for item in coordinates
    ]

    lon_edges = calculate_axis_edges(longitudes)
    lat_edges = calculate_axis_edges(latitudes)

    cells = []

    for item in coordinates:

        lon = round(item["lon"], 6)
        lat = round(item["lat"], 6)

        west, east = lon_edges[lon]
        south, north = lat_edges[lat]

        cell_polygon = box(
            west,
            south,
            east,
            north,
        )

        cells.append({
            "cell_key": (
                community,
                lon,
                lat,
            ),
            "community": community,
            "lon": lon,
            "lat": lat,
            "cell_polygon": cell_polygon,
        })

    return cells


# ============================================================
# 5. INTERSECT GRID CELLS WITH GUELMA
# ============================================================

print("\nCalculating spatial intersections...")

community_cells = {}

for community in ["AG", "RE"]:

    cells = build_community_cells(community)

    cells_gdf = gpd.GeoDataFrame(
        cells,
        geometry="cell_polygon",
        crs="EPSG:4326",
    )

    cells_gdf = cells_gdf.to_crs(AREA_CRS)

    intersected_cells = []

    for _, row in cells_gdf.iterrows():

        intersection = row["cell_polygon"].intersection(
            guelma_geometry
        )

        if intersection.is_empty:
            continue

        intersection_area = intersection.area

        if intersection_area <= 0:
            continue

        intersected_cells.append({
            "cell_key": row["cell_key"],
            "community": community,
            "longitude": row["lon"],
            "latitude": row["lat"],
            "intersection_area_km2": (
                intersection_area / 1_000_000
            ),
            "intersection_geometry": intersection,
        })

    if not intersected_cells:
        raise ValueError(
            f"No cells intersect Guelma for community {community}"
        )

    total_intersection_area = sum(
        item["intersection_area_km2"]
        for item in intersected_cells
    )

    for item in intersected_cells:
        item["area_weight"] = (
            item["intersection_area_km2"]
            / total_intersection_area
        )

    community_cells[community] = intersected_cells

    print(f"\nCommunity: {community}")
    print(f"Grid cells: {len(cells)}")
    print(f"Intersecting cells: {len(intersected_cells)}")
    print(
        "Sum of intersection areas: "
        f"{total_intersection_area:.2f} km2"
    )


# ============================================================
# 6. CREATE CELL INTERSECTION TABLE
# ============================================================

intersection_rows = []

for community, cells in community_cells.items():

    for item in cells:

        intersection_rows.append({
            "community": community,
            "cell_id": (
                f"{community}_"
                f"{item['longitude']:.6f}_"
                f"{item['latitude']:.6f}"
            ),
            "longitude": item["longitude"],
            "latitude": item["latitude"],
            "intersection_area_km2": (
                item["intersection_area_km2"]
            ),
            "area_weight": item["area_weight"],
        })

intersection_df = pd.DataFrame(intersection_rows)

intersection_path = (
    OUTPUT_DIR / "nasa_power_cell_intersections.csv"
)

intersection_df.to_csv(
    intersection_path,
    index=False,
    encoding="utf-8",
)


# ============================================================
# 7. EXTRACT DAILY VALUES FOR INTERSECTING CELLS
# ============================================================

print("\nExtracting daily values...")

daily_rows = []

for variable, config in VARIABLES.items():

    community = config["community"]
    unit = config["unit"]

    selected_cells = {
        item["cell_key"]: item
        for item in community_cells[community]
    }

    for feature_record in all_features[variable]:

        cell_key = feature_record["cell_key"]

        # Exclude cells that do not intersect Guelma.
        if cell_key not in selected_cells:
            continue

        cell_info = selected_cells[cell_key]

        for date_string, raw_value in (
            feature_record["values"].items()
        ):

            value = float(raw_value)

            if (
                not math.isfinite(value)
                or value in NODATA_VALUES
            ):
                value = np.nan

            date = pd.to_datetime(
                date_string,
                format="%Y%m%d",
                errors="coerce",
            )

            if pd.isna(date):
                raise ValueError(
                    f"Invalid date: {date_string}"
                )

            daily_rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "year": date.year,
                "month": date.month,
                "day": date.day,
                "season": (
                    "Winter" if date.month in [12, 1, 2]
                    else "Spring" if date.month in [3, 4, 5]
                    else "Summer" if date.month in [6, 7, 8]
                    else "Autumn"
                ),
                "variable": variable,
                "community": community,
                "cell_id": (
                    f"{community}_"
                    f"{feature_record['lon']:.6f}_"
                    f"{feature_record['lat']:.6f}"
                ),
                "longitude": feature_record["lon"],
                "latitude": feature_record["lat"],
                "value": value,
                "unit": unit,
                "intersection_area_km2": (
                    cell_info["intersection_area_km2"]
                ),
                "area_weight": cell_info["area_weight"],
            })


daily_cells_df = pd.DataFrame(daily_rows)

if daily_cells_df.empty:
    raise ValueError(
        "No daily records were produced. "
        "Check the boundary and grid coordinates."
    )

daily_cells_path = (
    OUTPUT_DIR / "nasa_power_daily_cell_values.csv"
)

daily_cells_df.to_csv(
    daily_cells_path,
    index=False,
    encoding="utf-8",
)

print(
    f"\nDaily cell records: "
    f"{len(daily_cells_df):,}"
)


# ============================================================
# 8. CALCULATE AREA-WEIGHTED DAILY WILAYA VALUES
# ============================================================

print("\nCalculating daily area-weighted values...")

def weighted_mean(group):

    valid = group[
        group["value"].notna()
    ].copy()

    if valid.empty:
        return pd.Series({
            "weighted_mean": np.nan,
            "valid_cells": 0,
            "available_area_km2": 0.0,
            "available_area_fraction": 0.0,
        })

    weights = valid["intersection_area_km2"].to_numpy()
    values = valid["value"].to_numpy()

    weighted_average = np.average(
        values,
        weights=weights,
    )

    available_area = weights.sum()

    total_area = valid["intersection_area_km2"].sum()

    return pd.Series({
        "weighted_mean": weighted_average,
        "valid_cells": len(valid),
        "available_area_km2": available_area,
        "available_area_fraction": available_area / guelma_area_km2,
    })


daily_summary = (
    daily_cells_df
    .groupby(
        ["date", "year", "month", "day",
         "season", "variable", "community", "unit"],
        dropna=False,
    )
    .apply(weighted_mean, include_groups=False)
    .reset_index()
)

daily_summary_path = (
    OUTPUT_DIR / "nasa_power_daily_wilaya_weighted.csv"
)

daily_summary.to_csv(
    daily_summary_path,
    index=False,
    encoding="utf-8",
)


# ============================================================
# 9. SPATIAL COVERAGE SUMMARY
# ============================================================

coverage_rows = []

for variable, config in VARIABLES.items():

    community = config["community"]
    cells = community_cells[community]

    total_intersection_area = sum(
        item["intersection_area_km2"]
        for item in cells
    )

    coverage_rows.append({
        "variable": variable,
        "community": community,
        "total_grid_cells": len([
            key for key in all_cell_coordinates
            if all_cell_coordinates[key]["community"] == community
        ]),
        "intersecting_cells": len(cells),
        "intersection_area_km2": total_intersection_area,
        "guelma_area_km2": guelma_area_km2,
        "area_coverage_fraction": (
            total_intersection_area / guelma_area_km2
        ),
        "unit": config["unit"],
    })

coverage_df = pd.DataFrame(coverage_rows)

coverage_path = (
    OUTPUT_DIR / "nasa_power_spatial_summary.csv"
)

coverage_df.to_csv(
    coverage_path,
    index=False,
    encoding="utf-8",
)


# ============================================================
# 10. SAVE PROCESSING METADATA
# ============================================================

metadata = {
    "project": "Field Shift",
    "dataset": "NASA POWER Regional Daily",
    "period": "2016-2025",
    "study_area": "Guelma Wilaya, Algeria",
    "boundary_file": str(BOUNDARY_FILE),
    "boundary_area_km2": guelma_area_km2,
    "area_crs": AREA_CRS,
    "cell_boundary_method": (
        "Estimated from midpoint distances between grid centers; "
        "outer edges extrapolated by half the nearest spacing."
    ),
    "intersection_method": (
        "Cell polygons intersected with the Guelma boundary "
        "in projected EPSG:32632."
    ),
    "aggregation_method": (
        "Area-weighted mean using cell intersection areas. "
        "Weights are renormalized over available valid cells."
    ),
    "important_limitations": [
        "NASA POWER grid-cell boundaries are estimated, not official.",
        "AG and RE have different spatial grids.",
        "Spatial resolution is too coarse for field-level decisions.",
        "Area coverage should be reviewed before interpreting averages.",
        "NASA POWER values are regional environmental context."
    ],
    "variables": VARIABLES,
}

metadata_path = (
    OUTPUT_DIR / "nasa_power_spatial_metadata.json"
)

with open(metadata_path, "w", encoding="utf-8") as file:
    json.dump(
        metadata,
        file,
        ensure_ascii=False,
        indent=4,
    )


# ============================================================
# 11. FINAL REPORT
# ============================================================

print("\n" + "=" * 70)
print("SPATIAL PROCESSING COMPLETED")
print("=" * 70)

print("\nSpatial coverage:")
print(
    coverage_df.to_string(index=False)
)

print("\nDaily records by variable:")
print(
    daily_cells_df
    .groupby("variable")
    .size()
    .to_string()
)

print("\nOutput directory:")
print(OUTPUT_DIR)

print("\nGenerated files:")
for path in sorted(OUTPUT_DIR.iterdir()):
    print(f" - {path.name}")

print("\nProcessing completed successfully.")