
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NASA POWER Regional Daily Extraction
Study Area: Guelma Wilaya, Algeria
Period: 2016-2025

Features:
- Reads the actual Guelma GeoJSON boundary.
- Calculates the bounding box.
- Snaps regional bounds to the approximate native grid.
- Uses one parameter per regional request.
- Splits requests by year.
- Saves raw JSON responses.
- Logs HTTP errors and NASA POWER validation messages.
- Creates an extraction manifest.

IMPORTANT:
The bounding box includes areas outside the Wilaya polygon.
The returned data must subsequently be spatially filtered.
Do not resample coarse NASA POWER data to 250 m and treat
it as 250 m climate information.
"""

from pathlib import Path
import json
import math
import time
import sys
import requests


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BOUNDARY_FILE = BASE_DIR / "guelma_wilaya_boundary.geojson"

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "NASA_POWER_REGIONAL"
)

BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/"
    "daily/regional"
)

START_YEAR = 2016
END_YEAR = 2025

# Meteorological variables
MET_VARIABLES = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
]

# Solar radiation
SOLAR_VARIABLES = [
    "ALLSKY_SFC_SW_DWN",
]

# Approximate native spatial grid spacing
MET_LAT_STEP = 0.5
MET_LON_STEP = 0.625

SOLAR_LAT_STEP = 1.0
SOLAR_LON_STEP = 1.0

# NASA POWER regional daily endpoint requires >= 2 degrees in lat and lon.
MIN_REGIONAL_SPAN_DEG = 2.0

REQUEST_TIMEOUT = 180
REQUEST_DELAY = 2

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "FieldShift-Guelma-Research/1.0"
})


# ============================================================
# 2. LOAD GEOJSON
# ============================================================

def load_boundary():

    print("\n[1/6] Loading Guelma boundary...")

    if not BOUNDARY_FILE.exists():
        raise FileNotFoundError(
            f"Boundary file not found:\n{BOUNDARY_FILE}"
        )

    with open(
        BOUNDARY_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        geojson = json.load(file)

    if not geojson.get("features"):
        raise ValueError(
            "GeoJSON contains no features."
        )

    return geojson


# ============================================================
# 3. CALCULATE BOUNDING BOX
# ============================================================

def get_bbox(geojson):

    coordinates = []

    def walk(obj):

        if isinstance(obj, list):

            if (
                len(obj) >= 2
                and isinstance(obj[0], (int, float))
                and isinstance(obj[1], (int, float))
            ):

                coordinates.append(
                    (obj[0], obj[1])
                )

            else:

                for item in obj:
                    walk(item)

    for feature in geojson["features"]:

        geometry = feature.get("geometry")

        if geometry is None:
            continue

        walk(geometry["coordinates"])

    if not coordinates:
        raise ValueError(
            "No valid coordinates found in GeoJSON."
        )

    longitudes = [
        point[0] for point in coordinates
    ]

    latitudes = [
        point[1] for point in coordinates
    ]

    return {
        "west": min(longitudes),
        "east": max(longitudes),
        "south": min(latitudes),
        "north": max(latitudes),
    }


# ============================================================
# 4. SNAP BOUNDS TO GRID
# ============================================================

def snap_down(value, step):

    return round(
        math.floor(value / step) * step,
        6
    )


def snap_up(value, step):

    return round(
        math.ceil(value / step) * step,
        6
    )


def ensure_min_span(
    orig_min,
    orig_max,
    snapped_min,
    snapped_max,
    step,
    min_span
):
    """Expand snapped bounds by grid steps until span >= min_span."""
    while round(snapped_max - snapped_min, 6) < min_span:

        lower_margin = orig_min - snapped_min
        upper_margin = snapped_max - orig_max

        if lower_margin <= upper_margin:
            snapped_min = round(snapped_min - step, 6)
        else:
            snapped_max = round(snapped_max + step, 6)

    return snapped_min, snapped_max


def prepare_regional_bbox(
    bbox,
    lat_step,
    lon_step,
    min_span=MIN_REGIONAL_SPAN_DEG
):
    """Snap bbox to grid steps and enforce NASA POWER minimum regional span."""
    lat_min = snap_down(bbox["south"], lat_step)
    lat_max = snap_up(bbox["north"], lat_step)
    lon_min = snap_down(bbox["west"], lon_step)
    lon_max = snap_up(bbox["east"], lon_step)

    lat_min, lat_max = ensure_min_span(
        bbox["south"],
        bbox["north"],
        lat_min,
        lat_max,
        lat_step,
        min_span,
    )

    lon_min, lon_max = ensure_min_span(
        bbox["west"],
        bbox["east"],
        lon_min,
        lon_max,
        lon_step,
        min_span,
    )

    return {
        "latitude-min": lat_min,
        "latitude-max": lat_max,
        "longitude-min": lon_min,
        "longitude-max": lon_max,
    }


# ============================================================
# 5. DATE HELPERS
# ============================================================

def get_year_dates(year):

    return (
        f"{year}0101",
        f"{year}1231"
    )


# ============================================================
# 6. NASA POWER REQUEST
# ============================================================

def request_variable(
    variable,
    community,
    bbox,
    year
):

    start_date, end_date = get_year_dates(year)

    params = {
        "parameters": variable,
        "community": community,

        "latitude-min": bbox["latitude-min"],
        "latitude-max": bbox["latitude-max"],

        "longitude-min": bbox["longitude-min"],
        "longitude-max": bbox["longitude-max"],

        "start": start_date,
        "end": end_date,

        "format": "JSON",
        "time-standard": "UTC",
    }

    print("\n" + "-" * 65)

    print(
        f"Variable: {variable} | Year: {year}"
    )

    print("Community:", community)
    print("Request parameters:")
    print(json.dumps(params, indent=2))

    try:

        response = SESSION.get(
            BASE_URL,
            params=params,
            timeout=REQUEST_TIMEOUT
        )

    except requests.RequestException as error:

        print(
            f"NETWORK ERROR: {error}",
            file=sys.stderr
        )

        return None

    print(
        "HTTP status:",
        response.status_code
    )

    if response.status_code != 200:

        print("\nNASA POWER validation response:")

        print(response.text[:8000])

        error_file = (
            OUTPUT_DIR
            / "errors"
            / f"{variable}_{year}_error.txt"
        )

        error_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        error_file.write_text(
            response.text,
            encoding="utf-8"
        )

        return None

    try:

        data = response.json()

    except ValueError:

        print(
            "ERROR: NASA POWER returned invalid JSON."
        )

        print(response.text[:3000])

        return None

    # Save raw response
    output_file = (
        OUTPUT_DIR
        / "raw"
        / variable
        / f"{variable}_{year}.json"
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2
        )

    print("Saved:", output_file)

    print(
        "Top-level response keys:",
        list(data.keys())
    )

    return {
        "variable": variable,
        "year": year,
        "community": community,
        "file": str(output_file),
        "status": "success",
    }


# ============================================================
# 7. MAIN EXTRACTION
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("=" * 65)
    print("NASA POWER - GUELMA REGIONAL EXTRACTION")
    print("=" * 65)

    # Load boundary
    geojson = load_boundary()

    original_bbox = get_bbox(geojson)

    print("\nOriginal Wilaya bounding box:")

    print(
        json.dumps(
            original_bbox,
            indent=2
        )
    )

    # Prepare native-resolution bounding boxes
    met_bbox = prepare_regional_bbox(
        original_bbox,
        MET_LAT_STEP,
        MET_LON_STEP
    )

    solar_bbox = prepare_regional_bbox(
        original_bbox,
        SOLAR_LAT_STEP,
        SOLAR_LON_STEP
    )

    print("\nMeteorological bounding box:")

    print(
        json.dumps(
            met_bbox,
            indent=2
        )
    )

    print("\nSolar bounding box:")

    print(
        json.dumps(
            solar_bbox,
            indent=2
        )
    )

    results = []
    failures = []

    # --------------------------------------------------------
    # Meteorological extraction
    # --------------------------------------------------------

    print("\n[2/6] Meteorological extraction")

    for variable in MET_VARIABLES:

        for year in range(
            START_YEAR,
            END_YEAR + 1
        ):

            result = request_variable(
                variable=variable,
                community="AG",
                bbox=met_bbox,
                year=year
            )

            if result is not None:

                results.append(result)

            else:

                failures.append({
                    "variable": variable,
                    "year": year,
                    "community": "AG",
                })

            time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # Solar extraction
    # --------------------------------------------------------

    print("\n[3/6] Solar radiation extraction")

    for variable in SOLAR_VARIABLES:

        for year in range(
            START_YEAR,
            END_YEAR + 1
        ):

            result = request_variable(
                variable=variable,
                community="RE",
                bbox=solar_bbox,
                year=year
            )

            if result is not None:

                results.append(result)

            else:

                failures.append({
                    "variable": variable,
                    "year": year,
                    "community": "RE",
                })

            time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    print("\n[4/6] Saving metadata")

    metadata = {

        "project": "Field Shift",

        "study_area": "Guelma Wilaya, Algeria",

        "period": {
            "start_year": START_YEAR,
            "end_year": END_YEAR,
        },

        "api": BASE_URL,

        "original_bbox": original_bbox,

        "meteorological_bbox": met_bbox,

        "solar_bbox": solar_bbox,

        "meteorological_variables": MET_VARIABLES,

        "solar_variables": SOLAR_VARIABLES,

        "successful_requests": len(results),

        "failed_requests": len(failures),

        "successes": results,

        "failures": failures,

        "methodological_note": (
            "Regional bounding-box extraction. "
            "The bounding box is not identical to the "
            "Wilaya polygon. Spatial filtering is required. "
            "Native NASA POWER spatial resolution must "
            "be preserved."
        ),
    }

    metadata_file = (
        OUTPUT_DIR
        / "extraction_metadata.json"
    )

    with open(
        metadata_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n[5/6] EXTRACTION SUMMARY")

    print("=" * 65)

    expected = (
        (len(MET_VARIABLES) + len(SOLAR_VARIABLES))
        * (END_YEAR - START_YEAR + 1)
    )

    print("Expected requests:", expected)
    print("Successful requests:", len(results))
    print("Failed requests:", len(failures))

    print(
        "Success rate:",
        round(
            len(results) / expected * 100,
            2
        ),
        "%"
    )

    print("Output directory:", OUTPUT_DIR)

    print("Metadata:", metadata_file)

    print("=" * 65)

    # --------------------------------------------------------
    # Final status
    # --------------------------------------------------------

    print("\n[6/6] Finished.")

    if len(results) == 0:

        raise RuntimeError(
            "No NASA POWER requests succeeded. "
            "Inspect the files in the errors directory."
        )

    if failures:

        print(
            "\nWARNING: Some requests failed. "
            "Do not consider the extraction complete."
        )

    else:

        print(
            "\nAll requested variables and years "
            "were downloaded successfully."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
