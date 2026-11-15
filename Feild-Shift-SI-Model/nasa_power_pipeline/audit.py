"""Phase 2: Spatial audit of NASA POWER raw grids, Guelma boundary, and maps."""

import json
import math
from typing import Dict, List, Tuple

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyproj
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .config import (
    AREA_CRS,
    COMMUNITY_SPECS,
    GEOGRAPHIC_CRS,
    RAW_DIR,
    SPATIAL_DIR,
    VARIABLES,
    YEARS,
    resolve_boundary_file,
)


def _densified_cell_polygon(
    west: float,
    south: float,
    east: float,
    north: float,
    samples_per_edge: int = 50,
) -> Polygon:
    """Build a geographic cell polygon with densified edges for accurate UTM projection."""
    xs = (
        list(np.linspace(west, east, samples_per_edge, endpoint=False))
        + [east] * samples_per_edge
        + list(np.linspace(east, west, samples_per_edge, endpoint=False))
        + [west] * samples_per_edge
    )
    ys = (
        [south] * samples_per_edge
        + list(np.linspace(south, north, samples_per_edge, endpoint=False))
        + [north] * samples_per_edge
        + list(np.linspace(north, south, samples_per_edge, endpoint=False))
    )
    return Polygon(zip(xs, ys))


def load_and_audit_boundary() -> Tuple[gpd.GeoDataFrame, object, Dict]:
    """Load the Guelma GeoPackage boundary and audit CRS, validity, and area."""
    boundary_path = resolve_boundary_file()
    gdf = gpd.read_file(boundary_path)
    if gdf.empty:
        raise ValueError(f"Boundary file is empty: {boundary_path}")
    if gdf.crs is None:
        raise ValueError(f"Boundary file has no CRS defined: {boundary_path}")

    source_crs = str(gdf.crs)
    raw_valid = bool(gdf.geometry.is_valid.all())
    if not raw_valid:
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.buffer(0)

    gdf_wgs84 = gdf.to_crs(GEOGRAPHIC_CRS)
    geom_wgs84 = unary_union(gdf_wgs84.geometry)

    # Confirm suitability of EPSG:32632 (UTM Zone 32N: 6E - 12E) against WGS84 geodesic area
    minx, miny, maxx, maxy = geom_wgs84.bounds
    if not (6.0 <= minx and maxx <= 12.0):
        raise ValueError(
            f"Study area longitude bounds ({minx:.3f}, {maxx:.3f}) fall outside UTM Zone 32N (6E-12E)."
        )

    geod = pyproj.Geod(ellps="WGS84")
    geodesic_area_m2, _ = geod.geometry_area_perimeter(geom_wgs84)
    geodesic_area_km2 = abs(geodesic_area_m2) / 1_000_000.0

    gdf_utm = gdf_wgs84.to_crs(AREA_CRS)
    geom_utm = unary_union(gdf_utm.geometry)
    utm_area_km2 = geom_utm.area / 1_000_000.0
    area_diff_pct = (utm_area_km2 - geodesic_area_km2) / geodesic_area_km2 * 100.0

    boundary_info = {
        "boundary_file": str(boundary_path),
        "source_crs": source_crs,
        "geometry_valid_original": raw_valid,
        "geometry_valid_final": bool(geom_utm.is_valid),
        "bounds_wgs84": {
            "west": float(minx),
            "south": float(miny),
            "east": float(maxx),
            "north": float(maxy),
        },
        "area_crs": AREA_CRS,
        "utm_area_km2": float(utm_area_km2),
        "geodesic_wgs84_area_km2": float(geodesic_area_km2),
        "utm_vs_geodesic_diff_pct": float(area_diff_pct),
    }
    return gdf_utm, geom_utm, boundary_info


def inspect_raw_grid_inventory() -> Tuple[Dict[str, pd.DataFrame], Dict]:
    """Read all 60 raw JSON files and audit coordinate, elevation, source, and unit consistency."""
    coord_signatures: Dict[str, Dict] = {"AG": {}, "RE": {}}
    sources_by_comm: Dict[str, set] = {"AG": set(), "RE": set()}
    units_by_var: Dict[str, set] = {var: set() for var in VARIABLES}
    file_count = 0

    for variable, cfg in VARIABLES.items():
        community = cfg["community"]
        for year in YEARS:
            json_path = RAW_DIR / variable / f"{variable}_{year}.json"
            if not json_path.exists():
                raise FileNotFoundError(f"Missing raw JSON file: {json_path}")

            with open(json_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            file_count += 1
            header = payload.get("header", {})
            sources_by_comm[community].update(header.get("sources", []))

            param_meta = payload.get("parameters", {}).get(variable, {})
            if isinstance(param_meta, dict) and "units" in param_meta:
                units_by_var[variable].add(str(param_meta["units"]))

            features = payload.get("features", [])
            if not features:
                raise ValueError(f"No features in {json_path}")

            pts = []
            for feature in features:
                coords = feature["geometry"]["coordinates"]
                lon = round(float(coords[0]), 6)
                lat = round(float(coords[1]), 6)
                elev = round(float(coords[2]), 4) if len(coords) > 2 else np.nan
                pts.append((lon, lat, elev))

            sig = tuple(sorted(pts))
            coord_signatures[community].setdefault(sig, []).append(f"{variable}_{year}")

    community_grids: Dict[str, pd.DataFrame] = {}
    grid_audit: Dict[str, Dict] = {}

    for community, sig_map in coord_signatures.items():
        if len(sig_map) != 1:
            raise ValueError(
                f"Coordinate/elevation inconsistency detected for {community}: "
                f"{len(sig_map)} distinct signatures across files."
            )

        sig, files = next(iter(sig_map.items()))
        df = pd.DataFrame(sig, columns=["longitude", "latitude", "elevation_m"])
        df = df.sort_values(["latitude", "longitude"]).reset_index(drop=True)
        df["community"] = community
        df["cell_id"] = [
            f"{community}_{row.longitude:.6f}_{row.latitude:.6f}"
            for row in df.itertuples(index=False)
        ]

        unique_lons = np.sort(df["longitude"].unique())
        unique_lats = np.sort(df["latitude"].unique())
        lon_diffs = np.round(np.diff(unique_lons), 6)
        lat_diffs = np.round(np.diff(unique_lats), 6)

        spec = COMMUNITY_SPECS[community]
        lon_regular = bool(
            len(lon_diffs) > 0 and np.allclose(lon_diffs, spec["nominal_lon_step"], atol=1e-6)
        )
        lat_regular = bool(
            len(lat_diffs) > 0 and np.allclose(lat_diffs, spec["nominal_lat_step"], atol=1e-6)
        )
        expected_grid_count = len(unique_lons) * len(unique_lats)
        is_complete_rect_grid = len(df) == expected_grid_count

        if not (lon_regular and lat_regular and is_complete_rect_grid):
            raise ValueError(
                f"Grid for {community} is irregular or incomplete: "
                f"lon_diffs={lon_diffs.tolist()}, lat_diffs={lat_diffs.tolist()}, "
                f"cells={len(df)} vs {expected_grid_count}"
            )

        community_grids[community] = df
        grid_audit[community] = {
            "files_inspected": len(files),
            "coordinate_consistent_across_all_files": True,
            "sources": sorted(sources_by_comm[community]),
            "cell_count": int(len(df)),
            "n_unique_lons": int(len(unique_lons)),
            "n_unique_lats": int(len(unique_lats)),
            "unique_lons": unique_lons.tolist(),
            "unique_lats": unique_lats.tolist(),
            "lon_spacing_deg": float(spec["nominal_lon_step"]),
            "lat_spacing_deg": float(spec["nominal_lat_step"]),
            "spacing_varies_with_lat_or_lon": False,
            "grid_regularity": "complete_regular_grid",
            "geometry_source_in_json": "Point (grid-cell center only; no official boundary polygons in payload)",
            "polygon_construction_method": "Approximate grid-center-derived cell bounds (+/- half nominal spacing, densified before UTM projection)",
        }

    return community_grids, {
        "total_json_files_audited": file_count,
        "units_by_variable": {k: sorted(v) for k, v in units_by_var.items()},
        "communities": grid_audit,
    }


def _add_scale_bar(ax, length_km: float = 20.0) -> None:
    """Draw a clean metric scale bar in the lower-left of an EPSG:32632 axes."""
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x0 = xlim[0] + 0.05 * (xlim[1] - xlim[0])
    y0 = ylim[0] + 0.06 * (ylim[1] - ylim[0])
    bar_m = length_km * 1000.0
    half_m = bar_m / 2.0
    h = 0.012 * (ylim[1] - ylim[0])

    ax.add_patch(mpatches.Rectangle((x0, y0), half_m, h, facecolor="black", edgecolor="black", zorder=10))
    ax.add_patch(mpatches.Rectangle((x0 + half_m, y0), half_m, h, facecolor="white", edgecolor="black", zorder=10))
    ax.text(x0, y0 + 1.5 * h, "0", fontsize=8, ha="center", va="bottom", zorder=10)
    ax.text(x0 + half_m, y0 + 1.5 * h, f"{int(length_km/2)}", fontsize=8, ha="center", va="bottom", zorder=10)
    ax.text(x0 + bar_m, y0 + 1.5 * h, f"{int(length_km)} km", fontsize=8, ha="center", va="bottom", fontweight="bold", zorder=10)


def _add_north_arrow(ax) -> None:
    """Draw a north arrow in the upper-right of an axes."""
    ax.annotate(
        "N",
        xy=(0.95, 0.94),
        xytext=(0.95, 0.84),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        arrowprops=dict(facecolor="black", width=3, headwidth=9),
        zorder=10,
    )


def _generate_community_map(
    community: str,
    grid_utm: gpd.GeoDataFrame,
    centers_utm: gpd.GeoDataFrame,
    intersections_utm: gpd.GeoDataFrame,
    guelma_utm: gpd.GeoDataFrame,
    guelma_area_km2: float,
    output_png,
) -> None:
    """Create a 2-panel cartographic audit map (full grid context + Guelma zoom)."""
    fig, (ax_ctx, ax_zoom) = plt.subplots(1, 2, figsize=(16, 7.5))

    spec = COMMUNITY_SPECS[community]
    # Left panel: full regional grid context
    grid_utm.plot(
        ax=ax_ctx,
        facecolor="#eef3f8",
        edgecolor="#4a6fa5",
        linestyle="--",
        linewidth=1.0,
        zorder=1,
    )
    intersections_utm.plot(
        ax=ax_ctx,
        column="area_weight",
        cmap="YlGnBu",
        vmin=0.0,
        vmax=max(0.65, float(intersections_utm["area_weight"].max())),
        alpha=0.75,
        edgecolor="#1b4332",
        linewidth=0.8,
        zorder=2,
    )
    guelma_utm.boundary.plot(ax=ax_ctx, color="#b00020", linewidth=2.0, zorder=4)
    centers_utm.plot(ax=ax_ctx, color="#d97706", edgecolor="black", markersize=36, zorder=5)

    for row in centers_utm.itertuples(index=False):
        ax_ctx.text(
            row.geometry.x,
            row.geometry.y + (3500 if community == "AG" else 6000),
            f"({row.longitude:.3g}, {row.latitude:.3g})",
            fontsize=6.5 if community == "AG" else 8,
            ha="center",
            va="bottom",
            color="#1f2937",
            zorder=6,
        )

    ax_ctx.set_title(
        f"Full {community} Grid Context ({len(grid_utm)} Cells, {spec['nominal_lat_step']}°×{spec['nominal_lon_step']}°)",
        fontsize=11,
        fontweight="bold",
    )
    ax_ctx.set_xlabel("Easting (m, UTM Zone 32N)")
    ax_ctx.set_ylabel("Northing (m, UTM Zone 32N)")
    ax_ctx.grid(True, alpha=0.25)
    _add_scale_bar(ax_ctx, length_km=50.0)
    _add_north_arrow(ax_ctx)

    # Right panel: zoom on Guelma + intersecting cells with full area/weight labels
    grid_utm.plot(
        ax=ax_zoom,
        facecolor="none",
        edgecolor="#4a6fa5",
        linestyle="--",
        linewidth=1.2,
        zorder=1,
    )
    intersections_utm.plot(
        ax=ax_zoom,
        column="area_weight",
        cmap="YlGnBu",
        vmin=0.0,
        vmax=max(0.65, float(intersections_utm["area_weight"].max())),
        alpha=0.82,
        edgecolor="#0f172a",
        linewidth=1.1,
        legend=True,
        legend_kwds={"label": "Area weight (fraction of Guelma)", "shrink": 0.78},
        zorder=2,
    )
    guelma_utm.boundary.plot(ax=ax_zoom, color="#b00020", linewidth=2.3, zorder=4)
    centers_utm.plot(ax=ax_zoom, color="#d97706", edgecolor="black", markersize=55, zorder=5)

    minx, miny, maxx, maxy = guelma_utm.total_bounds
    pad_x = (maxx - minx) * 0.25
    pad_y = (maxy - miny) * 0.25
    ax_zoom.set_xlim(minx - pad_x, maxx + pad_x)
    ax_zoom.set_ylim(miny - pad_y, maxy + pad_y)

    for row in intersections_utm.itertuples(index=False):
        rep = row.geometry.representative_point()
        short_id = f"{community} ({row.longitude:.3g}E, {row.latitude:.3g}N)"
        label = (
            f"{short_id}\n"
            f"Area: {row.intersection_area_km2:.1f} km²\n"
            f"Weight: {row.area_weight * 100:.2f}%"
        )
        # Offset small or closely spaced edge cells so labels never collide
        dx, dy = 0, 0
        if community == "RE" and row.area_weight < 0.05:
            dx, dy = -18000, 10000
        elif community == "AG" and row.area_weight < 0.06:
            dx, dy = 11000, -4000
        elif community == "AG" and row.latitude < 36.2 and row.longitude < 7.1:
            dx, dy = -16000, -7000
        elif community == "AG" and row.latitude < 36.2 and row.longitude >= 7.1:
            dx, dy = 18000, -7000

        if dx != 0 or dy != 0:
            ax_zoom.annotate(
                label,
                xy=(rep.x, rep.y),
                xytext=(rep.x + dx, rep.y + dy),
                fontsize=7.5,
                fontweight="bold",
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#334155", alpha=0.92),
                arrowprops=dict(arrowstyle="->", color="#334155", lw=1.0),
                zorder=8,
            )
        else:
            ax_zoom.text(
                rep.x,
                rep.y,
                label,
                fontsize=7.5,
                fontweight="bold",
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#334155", alpha=0.9),
                zorder=8,
            )

    ax_zoom.set_title(
        f"Guelma Intersections ({len(intersections_utm)} Intersecting Cells, Total = {guelma_area_km2:.2f} km²)",
        fontsize=11,
        fontweight="bold",
    )
    ax_zoom.set_xlabel("Easting (m, UTM Zone 32N)")
    ax_zoom.set_ylabel("Northing (m, UTM Zone 32N)")
    ax_zoom.grid(True, alpha=0.25)
    _add_scale_bar(ax_zoom, length_km=20.0)
    _add_north_arrow(ax_zoom)

    legend_handles = [
        mpatches.Patch(facecolor="none", edgecolor="#b00020", linewidth=2.0, label="Guelma Boundary"),
        mpatches.Patch(facecolor="#eef3f8", edgecolor="#4a6fa5", linestyle="--", label="Approx. Grid Cell"),
        mpatches.Patch(facecolor="#41b6c4", edgecolor="#0f172a", alpha=0.8, label="Clipped Intersection"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#d97706", markeredgecolor="black", markersize=8, label="NASA POWER Grid Center"),
    ]
    ax_ctx.legend(handles=legend_handles, loc="lower right", fontsize=8, framealpha=0.92)

    fig.suptitle(
        f"NASA POWER {community} ({spec['source_model']}) Spatial Audit — Guelma Wilaya | CRS: {AREA_CRS}\n"
        "Note: Grid cell polygons are approximations centered on NASA POWER Point coordinates (official polygons not provided in JSON)",
        fontsize=12,
        fontweight="bold",
        y=0.99,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_png, dpi=200)
    plt.close(fig)


def run_spatial_audit() -> Tuple[Dict[str, gpd.GeoDataFrame], Dict]:
    """Execute Phase 2 spatial audit, export GeoPackages, maps, and audit CSV."""
    guelma_utm_gdf, guelma_geom_utm, boundary_info = load_and_audit_boundary()
    guelma_area_km2 = boundary_info["utm_area_km2"]

    community_grids, raw_grid_audit = inspect_raw_grid_inventory()

    audit_rows: List[Dict] = []
    intersections_by_comm: Dict[str, gpd.GeoDataFrame] = {}

    for community, points_df in community_grids.items():
        spec = COMMUNITY_SPECS[community]
        half_lon = spec["nominal_lon_step"] / 2.0
        half_lat = spec["nominal_lat_step"] / 2.0

        cell_polys = [
            _densified_cell_polygon(
                row.longitude - half_lon,
                row.latitude - half_lat,
                row.longitude + half_lon,
                row.latitude + half_lat,
            )
            for row in points_df.itertuples(index=False)
        ]

        grid_wgs84 = gpd.GeoDataFrame(points_df.copy(), geometry=cell_polys, crs=GEOGRAPHIC_CRS)
        grid_wgs84["estimated_grid_approximation"] = True
        grid_wgs84["nominal_lon_step_deg"] = spec["nominal_lon_step"]
        grid_wgs84["nominal_lat_step_deg"] = spec["nominal_lat_step"]

        centers_wgs84 = gpd.GeoDataFrame(
            points_df.copy(),
            geometry=[Point(row.longitude, row.latitude) for row in points_df.itertuples(index=False)],
            crs=GEOGRAPHIC_CRS,
        )
        centers_wgs84["center_inside_guelma"] = centers_wgs84.to_crs(AREA_CRS).geometry.apply(
            lambda pt: bool(guelma_geom_utm.covers(pt))
        )

        grid_utm = grid_wgs84.to_crs(AREA_CRS)
        grid_utm["cell_area_km2"] = grid_utm.geometry.area / 1_000_000.0
        centers_utm = centers_wgs84.to_crs(AREA_CRS)

        inter_records = []
        for row in grid_utm.itertuples(index=False):
            clipped = row.geometry.intersection(guelma_geom_utm)
            if clipped.is_empty or clipped.area <= 0:
                continue
            inter_area_km2 = clipped.area / 1_000_000.0
            inter_records.append(
                {
                    "community": community,
                    "cell_id": row.cell_id,
                    "longitude": row.longitude,
                    "latitude": row.latitude,
                    "elevation_m": row.elevation_m,
                    "cell_area_km2": row.cell_area_km2,
                    "intersection_area_km2": inter_area_km2,
                    "fraction_of_cell": inter_area_km2 / row.cell_area_km2,
                    "area_weight": inter_area_km2 / guelma_area_km2,
                    "estimated_grid_approximation": True,
                    "geometry": clipped,
                }
            )

        inter_gdf = gpd.GeoDataFrame(inter_records, geometry="geometry", crs=AREA_CRS)
        if inter_gdf.empty:
            raise ValueError(f"No {community} cells intersect Guelma boundary.")

        # Topological checks: pairwise overlaps and union gap/excess vs Guelma
        geoms = list(inter_gdf.geometry)
        max_pairwise_overlap_m2 = 0.0
        sum_pairwise_overlap_m2 = 0.0
        for i in range(len(geoms)):
            for j in range(i + 1, len(geoms)):
                ov_area = geoms[i].intersection(geoms[j]).area
                max_pairwise_overlap_m2 = max(max_pairwise_overlap_m2, ov_area)
                sum_pairwise_overlap_m2 += ov_area

        union_inter = unary_union(geoms)
        union_area_km2 = union_inter.area / 1_000_000.0
        sum_inter_km2 = float(inter_gdf["intersection_area_km2"].sum())
        gap_area_m2 = guelma_geom_utm.difference(union_inter).area
        excess_area_m2 = union_inter.difference(guelma_geom_utm).area
        coverage_pct = union_area_km2 / guelma_area_km2 * 100.0
        area_diff_km2 = union_area_km2 - guelma_area_km2

        if max_pairwise_overlap_m2 > 1.0:
            raise ValueError(
                f"{community} intersecting polygons overlap by {max_pairwise_overlap_m2:.2f} m2."
            )

        # Save GeoPackages (grid + centers + boundary, and clipped intersections)
        grid_gpkg = SPATIAL_DIR / f"nasa_power_{community}_grid.gpkg"
        grid_utm.to_file(grid_gpkg, layer="grid_cells", driver="GPKG")
        centers_utm.to_file(grid_gpkg, layer="cell_centers", driver="GPKG")
        guelma_utm_gdf.to_file(grid_gpkg, layer="guelma_boundary", driver="GPKG")

        inter_gpkg = SPATIAL_DIR / f"nasa_power_{community}_intersections.gpkg"
        inter_gdf.to_file(inter_gpkg, layer="intersections", driver="GPKG")
        guelma_utm_gdf.to_file(inter_gpkg, layer="guelma_boundary", driver="GPKG")

        # Generate cartographic map
        map_png = SPATIAL_DIR / f"nasa_power_{community}_map.png"
        _generate_community_map(
            community=community,
            grid_utm=grid_utm,
            centers_utm=centers_utm,
            intersections_utm=inter_gdf,
            guelma_utm=guelma_utm_gdf,
            guelma_area_km2=guelma_area_km2,
            output_png=map_png,
        )

        intersections_by_comm[community] = inter_gdf
        raw_grid_audit["communities"][community].update(
            {
                "intersecting_cells": int(len(inter_gdf)),
                "centers_strictly_inside_guelma": int(centers_wgs84["center_inside_guelma"].sum()),
                "sum_intersection_area_km2": sum_inter_km2,
                "union_intersection_area_km2": float(union_area_km2),
                "guelma_area_km2": float(guelma_area_km2),
                "union_minus_guelma_km2": float(area_diff_km2),
                "gap_area_m2": float(gap_area_m2),
                "excess_area_m2": float(excess_area_m2),
                "max_pairwise_overlap_m2": float(max_pairwise_overlap_m2),
                "sum_pairwise_overlap_m2": float(sum_pairwise_overlap_m2),
                "coverage_pct": float(coverage_pct),
            }
        )

        audit_rows.append(
            {
                "community": community,
                "source_model": spec["source_model"],
                "nominal_resolution_deg": f"{spec['nominal_lat_step']}x{spec['nominal_lon_step']}",
                "total_grid_cells": len(grid_utm),
                "intersecting_cells": len(inter_gdf),
                "centers_inside_guelma": int(centers_wgs84["center_inside_guelma"].sum()),
                "guelma_utm_area_km2": round(guelma_area_km2, 6),
                "guelma_geodesic_area_km2": round(boundary_info["geodesic_wgs84_area_km2"], 6),
                "utm_vs_geodesic_diff_pct": round(boundary_info["utm_vs_geodesic_diff_pct"], 6),
                "sum_intersection_area_km2": round(sum_inter_km2, 6),
                "union_intersection_area_km2": round(union_area_km2, 6),
                "union_minus_guelma_km2": round(area_diff_km2, 9),
                "gap_area_m2": round(gap_area_m2, 9),
                "excess_area_m2": round(excess_area_m2, 9),
                "max_pairwise_overlap_m2": round(max_pairwise_overlap_m2, 9),
                "coverage_pct": round(coverage_pct, 6),
                "official_cell_boundaries_available": False,
                "grid_geometry_classification": "Approximate center-derived grid cells",
                "audit_status": "PASS",
            }
        )

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(SPATIAL_DIR / "spatial_audit_report.csv", index=False, encoding="utf-8")

    return intersections_by_comm, {
        "boundary": boundary_info,
        "grids": raw_grid_audit,
    }
