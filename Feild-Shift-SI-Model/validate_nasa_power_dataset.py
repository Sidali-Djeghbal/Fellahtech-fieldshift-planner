
from pathlib import Path
import json
import calendar
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "NASA_POWER_REGIONAL" / "raw"

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "NASA_POWER_REGIONAL"
    / "quality_check"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2016, 2026))

VARIABLES = {
    "T2M": "AG",
    "T2M_MAX": "AG",
    "T2M_MIN": "AG",
    "PRECTOTCORR": "AG",
    "RH2M": "AG",
    "ALLSKY_SFC_SW_DWN": "RE"
}

EXPECTED_CELLS = {
    "AG": 25,
    "RE": 4
}

FILL_VALUES = {-999, -999.0}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def extract_metadata(parameter_metadata):
    """Extract unit and description from parameter metadata."""

    if not isinstance(parameter_metadata, dict):
        return None, None

    unit = None
    description = None

    for key, value in parameter_metadata.items():

        key_lower = str(key).lower()

        if key_lower in ["units", "unit"]:
            unit = str(value)

        elif key_lower in ["longname", "long_name", "description"]:
            description = str(value)

    return unit, description


def get_parameter_metadata(data, variable):
    """Find parameter metadata safely."""

    parameters = data.get("parameters", {})

    if isinstance(parameters, dict):
        return parameters.get(variable, {})

    return {}


def get_expected_dates(year):
    return {
        date.strftime("%Y%m%d")
        for date in pd.date_range(
            start=f"{year}-01-01",
            end=f"{year}-12-31",
            freq="D"
        )
    }


def read_coordinates(features):
    """Extract unique coordinates from JSON features."""

    coordinates = []

    for feature in features:

        coords = feature["geometry"]["coordinates"]

        coordinates.append((
            round(float(coords[0]), 6),
            round(float(coords[1]), 6)
        ))

    return sorted(set(coordinates))


# ============================================================
# MAIN VALIDATION
# ============================================================

print("=" * 75)
print("NASA POWER DATASET QUALITY VALIDATION")
print("=" * 75)

file_summaries = []
coordinate_records = []
daily_records = []
global_errors = []

for variable, community in VARIABLES.items():

    print("\n" + "=" * 65)
    print(f"VARIABLE: {variable} | COMMUNITY: {community}")
    print("=" * 65)

    reference_coordinates = None

    for year in YEARS:

        filepath = (
            RAW_DIR
            / variable
            / f"{variable}_{year}.json"
        )

        errors = []

        if not filepath.exists():

            message = f"Missing file: {filepath}"

            print(f"[ERROR] {message}")
            global_errors.append(message)
            continue

        try:

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

        except Exception as error:

            message = f"Cannot read {filepath.name}: {error}"

            print(f"[ERROR] {message}")
            global_errors.append(message)
            continue

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = data.get("header", {})

        start_date = str(header.get("start", ""))
        end_date = str(header.get("end", ""))

        fill_value = header.get("fill_value", -999)

        # ----------------------------------------------------
        # FEATURES AND COORDINATES
        # ----------------------------------------------------

        features = data.get("features", [])

        coordinates = read_coordinates(features)

        cell_count = len(features)

        expected_cells = EXPECTED_CELLS[community]

        if cell_count != expected_cells:
            errors.append(
                f"Expected {expected_cells} cells, got {cell_count}"
            )

        if len(coordinates) != cell_count:
            errors.append("Duplicate grid coordinates detected")

        if reference_coordinates is None:
            reference_coordinates = coordinates

        elif coordinates != reference_coordinates:
            errors.append(
                "Grid coordinates differ from other years "
                "for this variable"
            )

        # ----------------------------------------------------
        # PARAMETER AND UNIT
        # ----------------------------------------------------

        parameter_metadata = get_parameter_metadata(
            data,
            variable
        )

        unit, description = extract_metadata(
            parameter_metadata
        )

        # ----------------------------------------------------
        # DAILY DATA VALIDATION
        # ----------------------------------------------------

        expected_dates = get_expected_dates(year)

        all_dates = set()
        missing_values = 0
        valid_values = 0
        total_values = 0
        invalid_values = 0

        cell_date_counts = []

        for feature_index, feature in enumerate(features):

            parameters = (
                feature
                .get("properties", {})
                .get("parameter", {})
            )

            if variable not in parameters:

                errors.append(
                    f"Variable {variable} missing in cell "
                    f"{feature_index + 1}"
                )

                continue

            values = parameters[variable]

            if not isinstance(values, dict):

                errors.append(
                    f"Unexpected daily data structure in "
                    f"cell {feature_index + 1}"
                )

                continue

            cell_dates = set(values.keys())

            all_dates.update(cell_dates)

            cell_date_counts.append(len(cell_dates))

            missing_dates = expected_dates - cell_dates

            if missing_dates:

                errors.append(
                    f"Cell {feature_index + 1}: "
                    f"{len(missing_dates)} missing dates"
                )

            for date, value in values.items():

                total_values += 1

                try:
                    numeric_value = float(value)

                except (ValueError, TypeError):

                    invalid_values += 1
                    continue

                if not np.isfinite(numeric_value):
                    missing_values += 1

                elif numeric_value in FILL_VALUES:
                    missing_values += 1

                else:
                    valid_values += 1

        # ----------------------------------------------------
        # DATE COVERAGE
        # ----------------------------------------------------

        expected_count = len(expected_dates)

        unique_date_count = len(all_dates)

        unexpected_dates = all_dates - expected_dates

        missing_unique_dates = expected_dates - all_dates

        if unique_date_count != expected_count:
            errors.append(
                f"Unique dates: {unique_date_count}, "
                f"expected: {expected_count}"
            )

        if unexpected_dates:
            errors.append(
                f"{len(unexpected_dates)} unexpected dates"
            )

        # ----------------------------------------------------
        # HEADER CHECK
        # ----------------------------------------------------

        expected_start = f"{year}0101"
        expected_end = f"{year}1231"

        if start_date != expected_start:
            errors.append(
                f"Unexpected start date: {start_date}"
            )

        if end_date != expected_end:
            errors.append(
                f"Unexpected end date: {end_date}"
            )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        status = "PASS" if len(errors) == 0 else "CHECK"

        print(
            f"[{status}] {year} | "
            f"Cells: {cell_count} | "
            f"Dates: {unique_date_count}/{expected_count} | "
            f"Valid: {valid_values} | "
            f"Missing: {missing_values} | "
            f"Invalid: {invalid_values}"
        )

        for error in errors:
            print("   WARNING:", error)

        file_summaries.append({
            "variable": variable,
            "community": community,
            "year": year,
            "file": filepath.name,
            "status": status,
            "cell_count": cell_count,
            "expected_cells": expected_cells,
            "unique_dates": unique_date_count,
            "expected_dates": expected_count,
            "missing_unique_dates": len(missing_unique_dates),
            "valid_values": valid_values,
            "missing_values": missing_values,
            "invalid_values": invalid_values,
            "total_values": total_values,
            "fill_value": fill_value,
            "unit": unit,
            "description": description,
            "errors": " | ".join(errors)
        })

        for longitude, latitude in coordinates:

            coordinate_records.append({
                "variable": variable,
                "community": community,
                "year": year,
                "longitude": longitude,
                "latitude": latitude
            })

        daily_records.append({
            "variable": variable,
            "community": community,
            "year": year,
            "dates": unique_date_count,
            "expected_dates": expected_count,
            "valid_values": valid_values,
            "missing_values": missing_values
        })

        for error in errors:

            global_errors.append(
                f"{variable} {year}: {error}"
            )


# ============================================================
# SAVE REPORTS
# ============================================================

summary_df = pd.DataFrame(file_summaries)

coordinates_df = pd.DataFrame(coordinate_records)

daily_df = pd.DataFrame(daily_records)

summary_file = OUTPUT_DIR / "nasa_power_validation_summary.csv"

coordinates_file = OUTPUT_DIR / "nasa_power_validation_coordinates.csv"

daily_file = OUTPUT_DIR / "nasa_power_validation_daily_coverage.csv"

summary_df.to_csv(summary_file, index=False)

coordinates_df.to_csv(coordinates_file, index=False)

daily_df.to_csv(daily_file, index=False)


# ============================================================
# FINAL REPORT
# ============================================================

print("\n" + "=" * 75)
print("FINAL VALIDATION REPORT")
print("=" * 75)

print("Expected files:", len(VARIABLES) * len(YEARS))
print("Files inspected:", len(summary_df))

if not summary_df.empty:

    passed = (summary_df["status"] == "PASS").sum()

    checked = (summary_df["status"] == "CHECK").sum()

    print("PASS:", passed)
    print("CHECK:", checked)

    print(
        "Total valid values:",
        int(summary_df["valid_values"].sum())
    )

    print(
        "Total missing values:",
        int(summary_df["missing_values"].sum())
    )

    print(
        "Total invalid values:",
        int(summary_df["invalid_values"].sum())
    )

    print("\nUnits by variable:")

    print(
        summary_df[
            ["variable", "unit"]
        ].drop_duplicates().to_string(index=False)
    )

print("\nGlobal errors:", len(global_errors))

for error in global_errors:
    print("-", error)

print("\nReports saved:")
print(summary_file)
print(coordinates_file)
print(daily_file)

print("\nValidation completed.")
