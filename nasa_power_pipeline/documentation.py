"""Phase 7: Processing metadata, data dictionary, and README documentation."""

from datetime import datetime, timezone
import json
import sys
from typing import Dict

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import pyproj
import shapely

from .config import (
    AREA_CRS,
    END_YEAR,
    GEOGRAPHIC_CRS,
    METADATA_DIR,
    PROCESSED_DIR,
    START_YEAR,
    VARIABLES,
)


def _package_versions() -> Dict[str, str]:
    """Capture runtime Python and geospatial library versions."""
    return {
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "geopandas": gpd.__version__,
        "shapely": shapely.__version__,
        "pyproj": pyproj.__version__,
        "matplotlib": matplotlib.__version__,
    }


def save_processing_metadata(
    audit_summary: Dict,
    datasets: Dict[str, pd.DataFrame],
    qa_results: Dict[str, pd.DataFrame],
    analysis_results: Dict[str, pd.DataFrame],
) -> None:
    """Save comprehensive reproducible processing metadata JSON."""
    metadata = {
        "project": "Field Shift (NASA Space Apps Challenge 2026)",
        "study_area": "Guelma Wilaya, Algeria",
        "period": f"{START_YEAR}-01-01 to {END_YEAR}-12-31",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "package_versions": _package_versions(),
        "boundary_audit": audit_summary["boundary"],
        "grid_audit": audit_summary["grids"],
        "variables": {
            var: {
                key: (sorted(val) if isinstance(val, set) else val)
                for key, val in cfg.items()
            }
            for var, cfg in VARIABLES.items()
        },
        "spatial_aggregation": {
            "weighted_mean_formula": "sum(value_i * intersection_area_i) / sum(intersection_area_i) over valid observations",
            "coverage_fraction_formula": "valid_area_km2 / total_study_area_km2",
            "communities_kept_separate": True,
            "area_crs": AREA_CRS,
            "geographic_crs": GEOGRAPHIC_CRS,
        },
        "dataset_row_counts": {
            "daily_cell_values": int(len(datasets["daily_cell"])),
            "daily_guelma": int(len(datasets["daily_guelma"])),
            "monthly_guelma": int(len(datasets["monthly"])),
            "seasonal_guelma": int(len(datasets["seasonal"])),
            "annual_guelma": int(len(datasets["annual"])),
            "climate_trends": int(len(analysis_results["trends"])),
            "climate_anomalies": int(len(analysis_results["anomalies"])),
        },
        "quality_assurance_summary": qa_results["data_quality"].to_dict(orient="records"),
        "scientific_constraints_and_limitations": [
            "NASA POWER raw JSON responses provide Point coordinates (grid centers), not official cell boundary polygons; cell polygons are approximate footprints derived from nominal grid spacing.",
            "AG (MERRA-2, 0.5 x 0.625 deg) and RE (CERES SYN1deg, 1.0 x 1.0 deg) use distinct native grids and are processed separately.",
            "Data represent coarse regional environmental context, NOT field-level weather observations.",
            "The 2016-2025 record spans 10 years and is NOT a standard 30-year WMO climate normal.",
            "Winter 2016 (Jan-Feb 2016 only) and Winter 2026 (Dec 2025 only) are boundary-truncated partial seasons and are flagged via is_complete_season.",
            "Regional climate values cannot substitute for local soil or field measurements, nor infer crop species/rotations.",
        ],
    }

    with open(METADATA_DIR / "processing_metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def save_data_dictionary() -> None:
    """Save machine-readable data dictionary covering all processed tables."""
    rows = [
        # Daily cell
        ("nasa_power_daily_cell_values.csv", "date", "string (YYYY-MM-DD)", "-", "Calendar date (UTC)"),
        ("nasa_power_daily_cell_values.csv", "year", "int", "-", "Calendar year (2016-2025)"),
        ("nasa_power_daily_cell_values.csv", "month", "int", "-", "Calendar month (1-12)"),
        ("nasa_power_daily_cell_values.csv", "day", "int", "-", "Day of month"),
        ("nasa_power_daily_cell_values.csv", "season", "string", "-", "Meteorological season (Winter/Spring/Summer/Autumn)"),
        ("nasa_power_daily_cell_values.csv", "variable", "string", "-", "NASA POWER parameter code"),
        ("nasa_power_daily_cell_values.csv", "community", "string", "-", "NASA POWER community (AG or RE)"),
        ("nasa_power_daily_cell_values.csv", "cell_id", "string", "-", "Unique community-longitude-latitude cell identifier"),
        ("nasa_power_daily_cell_values.csv", "longitude", "float", "degrees_east", "Cell center longitude (EPSG:4326)"),
        ("nasa_power_daily_cell_values.csv", "latitude", "float", "degrees_north", "Cell center latitude (EPSG:4326)"),
        ("nasa_power_daily_cell_values.csv", "elevation_m", "float", "m", "Grid-cell elevation reported by NASA POWER"),
        ("nasa_power_daily_cell_values.csv", "value", "float", "variable unit", "Daily cell value"),
        ("nasa_power_daily_cell_values.csv", "unit", "string", "-", "Physical unit"),
        ("nasa_power_daily_cell_values.csv", "intersection_area_km2", "float", "km2", "Approximate cell intersection area with Guelma in EPSG:32632"),
        ("nasa_power_daily_cell_values.csv", "area_weight", "float", "fraction", "Cell intersection area divided by total Guelma area"),
        # Daily Guelma
        ("nasa_power_daily_guelma.csv", "weighted_mean", "float", "variable unit", "Area-weighted regional mean over valid intersecting cells"),
        ("nasa_power_daily_guelma.csv", "valid_cells", "int", "count", "Number of intersecting cells with valid observation"),
        ("nasa_power_daily_guelma.csv", "valid_area_km2", "float", "km2", "Sum of intersection areas of valid cells"),
        ("nasa_power_daily_guelma.csv", "total_study_area_km2", "float", "km2", "Total Guelma boundary area in EPSG:32632"),
        ("nasa_power_daily_guelma.csv", "coverage_fraction", "float", "fraction", "valid_area_km2 / total_study_area_km2"),
        # Monthly
        ("nasa_power_monthly_guelma.csv", "T2M_mean_C", "float", "C", "Monthly mean of daily T2M"),
        ("nasa_power_monthly_guelma.csv", "T2M_MAX_mean_C", "float", "C", "Monthly mean of daily T2M_MAX"),
        ("nasa_power_monthly_guelma.csv", "T2M_MIN_mean_C", "float", "C", "Monthly mean of daily T2M_MIN"),
        ("nasa_power_monthly_guelma.csv", "PRECTOTCORR_sum_mm", "float", "mm/month", "Monthly total precipitation"),
        ("nasa_power_monthly_guelma.csv", "RH2M_mean_pct", "float", "%", "Monthly mean relative humidity"),
        ("nasa_power_monthly_guelma.csv", "ALLSKY_SFC_SW_DWN_mean_kwh_m2_day", "float", "kWh/m2/day", "Monthly mean daily solar irradiance"),
        ("nasa_power_monthly_guelma.csv", "ALLSKY_SFC_SW_DWN_sum_kwh_m2", "float", "kWh/m2/month", "Monthly cumulative solar irradiance"),
        # Seasonal
        ("nasa_power_seasonal_guelma.csv", "season_year", "int", "-", "Seasonal year (December assigned to year+1 for Winter)"),
        ("nasa_power_seasonal_guelma.csv", "is_complete_season", "bool", "-", "True if valid_days equals full calendar season days"),
        # Annual
        ("nasa_power_annual_guelma.csv", "annual_mean_diurnal_temp_range_C", "float", "C", "Annual mean T2M_MAX minus annual mean T2M_MIN"),
        ("nasa_power_annual_guelma.csv", "annual_extreme_temp_range_C", "float", "C", "Annual max daily T2M_MAX minus min daily T2M_MIN"),
        ("nasa_power_annual_guelma.csv", "PRECTOTCORR_anomaly_mm", "float", "mm", "Annual rainfall minus 2016-2025 mean"),
        ("nasa_power_annual_guelma.csv", "PRECTOTCORR_anomaly_pct", "float", "%", "Percentage rainfall anomaly vs 2016-2025 mean"),
        ("nasa_power_annual_guelma.csv", "T2M_anomaly_C", "float", "C", "Annual mean T2M minus 2016-2025 mean"),
    ]
    df = pd.DataFrame(rows, columns=["dataset", "column_name", "dtype", "unit", "description"])
    df.to_csv(METADATA_DIR / "data_dictionary.csv", index=False, encoding="utf-8")


def save_readme(
    audit_summary: Dict,
    datasets: Dict[str, pd.DataFrame],
    qa_results: Dict[str, pd.DataFrame],
) -> None:
    """Generate comprehensive README.md for the processed NASA POWER datasets."""
    b = audit_summary["boundary"]
    ag = audit_summary["grids"]["communities"]["AG"]
    re = audit_summary["grids"]["communities"]["RE"]
    qa_table = qa_results["data_quality"][["check_id", "observed_value", "status", "details"]].to_string(index=False)

    readme = f"""# NASA POWER Regional Climate Processing — Guelma Wilaya (2016–2025)

**Project:** Field Shift (NASA Space Apps Challenge 2026)  
**Study Area:** Guelma Wilaya, Algeria (`{b['utm_area_km2']:.2f} km²` in `EPSG:32632`; `{b['geodesic_wgs84_area_km2']:.2f} km²` WGS84 geodesic, difference `{b['utm_vs_geodesic_diff_pct']:.4f}%`)  
**Period:** 2016-01-01 to 2025-12-31 (10 years, 3,653 days)

---

## 1. Data Sources & Variables

Raw daily JSON files (`60` files: `6` variables × `10` years) were extracted from the NASA POWER Daily Regional API:

| Variable | Community | Source Model | Native Grid | Unit |
|---|---|---|---|---|
| `T2M` | `AG` | MERRA-2 | `0.5° lat × 0.625° lon` | °C |
| `T2M_MAX` | `AG` | MERRA-2 | `0.5° lat × 0.625° lon` | °C |
| `T2M_MIN` | `AG` | MERRA-2 | `0.5° lat × 0.625° lon` | °C |
| `PRECTOTCORR` | `AG` | MERRA-2 | `0.5° lat × 0.625° lon` | mm/day |
| `RH2M` | `AG` | MERRA-2 (POWER derived) | `0.5° lat × 0.625° lon` | % |
| `ALLSKY_SFC_SW_DWN` | `RE` | CERES SYN1deg | `1.0° lat × 1.0° lon` | kWh/m²/day |

Administrative boundary source: `{b['boundary_file']}` (source CRS `{b['source_crs']}`, valid geometry).

---

## 2. Spatial Resolution & Audit Findings

- **AG (`MERRA-2`)**: `{ag['cell_count']}` extracted cells (`5 × 5` regular grid), `{ag['intersecting_cells']}` intersecting Guelma, `{ag['centers_strictly_inside_guelma']}` cell center strictly inside Guelma. Union intersection area: `{ag['union_intersection_area_km2']:.4f} km²` (`{ag['coverage_pct']:.4f}%`), pairwise overlap `{ag['max_pairwise_overlap_m2']:.2e} m²`, gap `{ag['gap_area_m2']:.2e} m²`.
- **RE (`CERES SYN1deg`)**: `{re['cell_count']}` extracted cells (`2 × 2` regular grid), `{re['intersecting_cells']}` intersecting Guelma, `{re['centers_strictly_inside_guelma']}` cell center strictly inside Guelma. Union intersection area: `{re['union_intersection_area_km2']:.4f} km²` (`{re['coverage_pct']:.4f}%`), pairwise overlap `{re['max_pairwise_overlap_m2']:.2e} m²`, gap `{re['gap_area_m2']:.2e} m²`.
- **Grid Geometry Caveat**: NASA POWER JSON payloads provide `Point` coordinates (grid-cell centers) and do not include official boundary polygons. Cell polygons were constructed as center-derived approximations (`± half nominal spacing`, densified along geographic edges prior to `EPSG:32632` projection).

---

## 3. Processing & Temporal Aggregation Methodology

- **Daily Area-Weighted Regional Mean**:
  `Weighted Mean = Σ(value_i × intersection_area_i) / Σ(intersection_area_i)` over valid cell observations.
- **Daily Spatial Coverage Fraction**:
  `Coverage Fraction = valid_area_km2 / total_study_area_km2` (fixed Guelma area denominator).
- **Communities Kept Separate**: `AG` and `RE` grids are processed and mapped independently.
- **Monthly**: Mean of daily `T2M`, `T2M_MAX`, `T2M_MIN`, `RH2M`, `ALLSKY_SFC_SW_DWN`; sum of daily `PRECTOTCORR` (plus clearly labeled cumulative solar radiation).
- **Seasonal**: `Winter` (DJF, with December assigned to `year + 1`), `Spring` (MAM), `Summer` (JJA), `Autumn` (SON). Boundary-truncated winters (`Winter 2016` = Jan–Feb 2016; `Winter 2026` = Dec 2025) are flagged with `is_complete_season = False`.
- **Annual**: Annual means/totals, diurnal & extreme temperature ranges, and anomalies relative to the 2016–2025 study-period baseline.

---

## 4. Dataset Inventory

- `daily/nasa_power_daily_cell_values.csv`: `{len(datasets['daily_cell']):,}` rows
- `daily/nasa_power_daily_guelma.csv`: `{len(datasets['daily_guelma']):,}` rows
- `monthly/nasa_power_monthly_guelma.csv`: `{len(datasets['monthly']):,}` rows
- `seasonal/nasa_power_seasonal_guelma.csv`: `{len(datasets['seasonal']):,}` rows
- `annual/nasa_power_annual_guelma.csv`: `{len(datasets['annual']):,}` rows

---

## 5. Quality-Control Summary

```text
{qa_table}
```

---

## 6. Scientific Limitations

1. NASA POWER data are coarse regional grid products (`0.5° × 0.625°` and `1.0° × 1.0°`) representing regional environmental context, **not** field-scale weather stations.
2. Grid-cell polygons are approximate footprints derived from grid-center coordinates.
3. The 2016–2025 span (`n = 10` years) is **not** a 30-year WMO climate normal; trend statistics have low statistical power and do not imply causality.
4. Regional climate series cannot substitute for in-situ soil/field measurements or infer crop species/rotations.

---

## 7. Reproducibility

Run the full pipeline from the project root:

```bash
python run_nasa_power_pipeline.py
```
"""

    (PROCESSED_DIR / "README.md").write_text(readme, encoding="utf-8")


def run_documentation(
    audit_summary: Dict,
    datasets: Dict[str, pd.DataFrame],
    qa_results: Dict[str, pd.DataFrame],
    analysis_results: Dict[str, pd.DataFrame],
) -> None:
    """Execute Phase 7 documentation and metadata generation."""
    save_processing_metadata(audit_summary, datasets, qa_results, analysis_results)
    save_data_dictionary()
    save_readme(audit_summary, datasets, qa_results)
