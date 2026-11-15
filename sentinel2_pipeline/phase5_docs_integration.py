"""Phases 12 & 13: Metadata, data dictionary, integration-readiness report, and README."""

import json
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import pyproj
import rasterio
import shapely

from .config import (
    BAND_SPECS,
    CLOUD_PROB_THRESHOLD,
    END_YEAR,
    GEE_ASSET_ID,
    GEE_PROJECT,
    INDEX_SPECS,
    METADATA_DIR,
    REFLECTANCE_SCALE,
    S2_CLOUD_PROB_ID,
    S2_COLLECTION_ID,
    SCL_EVALUATED_RETAINED,
    SCL_EXCLUDED_CLASSES,
    SENTINEL2_DIR,
    START_YEAR,
    TARGET_CRS,
)


def _package_versions() -> Dict[str, str]:
    versions = {
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "geopandas": gpd.__version__,
        "shapely": shapely.__version__,
        "pyproj": pyproj.__version__,
        "rasterio": rasterio.__version__,
        "matplotlib": matplotlib.__version__,
    }
    for pkg in ("scipy", "ee"):
        try:
            m = __import__(pkg)
            versions[pkg] = getattr(m, "__version__", "installed")
        except ImportError:
            versions[pkg] = "not_installed"
    return versions


def write_integration_readiness_report(
    boundary_audit: Dict,
    dataset_inventory: List[Dict],
) -> Path:
    """Phase 13: Write Field Shift multi-source resolution & integration-readiness report."""
    inv_df = pd.DataFrame(dataset_inventory)
    table_md = inv_df.to_string(index=False)

    report = f"""# Field Shift Integration-Readiness Report (Sentinel-2 & Existing Datasets)

**Study Area:** Guelma Wilaya, Algeria (`{boundary_audit['utm_area_km2']} km²` in `{TARGET_CRS}`)  
**Objective:** Define a scientifically defensible strategy for integrating Sentinel-2 (`10 m / 20 m`) with existing environmental layers without falsifying spatial resolution.

---

## 1. Verified Spatial Resolution & Grid Comparison

```text
{table_md}
```

---

## 2. Scale Disparity & Anti-Resampling Rules

1. **Do NOT upsample coarse climate/soil-moisture grids to 10 m or 20 m**:
   - Upsampling NASA POWER (`~55–111 km`), SMAP (`11 km`), or GPM (`~9.6 km`) to `10 m` or `20 m` creates a false appearance of field-level variation where only 2 to 61 independent spatial measurements exist over all of Guelma.
2. **Preserve native grids inside Sentinel-2**:
   - Keep `NDVI` and `EVI` at `10 m`, and `NDMI` and `NDRE` at `20 m`.
   - When a single multi-index Sentinel-2 analysis grid is required, aggregate `NDVI` and `EVI` (`10 m`) **down** to `20 m` (mean/median of `2 × 2` blocks) rather than upsampling `NDMI`/`NDRE` (`20 m`) to `10 m`.
3. **SoilGrids 2.0 (`250 m`, `ESRI:54009`) & MODIS (`250 m`, `EPSG:32632`)**:
   - Reproject SoilGrids cleanly to `EPSG:32632` using nearest/bilinear only to align to a common **`250 m` agricultural landscape grid** (matching MODIS `250 m` and SoilGrids `250 m`), where Sentinel-2 (`10 m / 20 m`) can be summarized via zonal statistics (mean, median, IQR, valid pixel %) per `250 m` cell or per field polygon!

---

## 3. Recommended Defensible Common Analysis Units for Field Shift

| Modeling Level | Common Spatial Unit | How Each Source Enters |
|---|---|---|
| **Field / Parcel Monitoring** | Verified field polygon (or `20 m` Sentinel-2 pixel) | Sentinel-2 (`10 m` & `20 m`) + Crop Frequency (`10 m`) native; coarse layers attached strictly as **regional/mesoscale covariates** with explicit scale tags |
| **Wilaya Landscape Grid** | `250 m × 250 m` (`EPSG:32632`, aligned to MODIS/SoilGrids) | Sentinel-2 aggregated (`10 m / 20 m → 250 m` mean + std + valid %); MODIS & SoilGrids at native `250 m`; SMAP/GPM/NASA POWER joined as coarse context |
| **Coarse Spatiotemporal Modeling** | `11 km` UTM32N grid (`guelma_environmental_spatiotemporal_dataset_2016_2025.csv`) | Sentinel-2 aggregated to `11 km` (mean, median, IQR of vegetated pixels); SMAP & GPM native `~10-11 km`; NASA POWER area-weighted regional context |
"""
    out_path = METADATA_DIR / "integration_readiness_report.md"
    out_path.write_text(report, encoding="utf-8")
    return out_path


def write_metadata_and_docs(
    boundary_audit: Dict,
    dataset_inventory: List[Dict],
    gee_meta: Optional[Dict] = None,
    qa_outputs: Optional[Dict] = None,
    analysis_outputs: Optional[Dict] = None,
) -> None:
    """Save processing_metadata.json, data_dictionary.csv, integration report, and README."""
    write_integration_readiness_report(boundary_audit, dataset_inventory)

    metadata = {
        "project": "Field Shift (NASA Space Apps Challenge 2026)",
        "study_area": "Guelma Wilaya, Algeria",
        "period": f"{START_YEAR}-01-01 to {END_YEAR}-12-31",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "package_versions": _package_versions(),
        "local_boundary_audit": boundary_audit,
        "gee_config": {
            "project": GEE_PROJECT,
            "asset_id": GEE_ASSET_ID,
            "collection": S2_COLLECTION_ID,
            "cloud_probability_collection": S2_CLOUD_PROB_ID,
            "target_crs": TARGET_CRS,
            "reflectance_scale_factor": REFLECTANCE_SCALE,
            "cloud_probability_threshold_pct": CLOUD_PROB_THRESHOLD,
            "scl_excluded_classes": SCL_EXCLUDED_CLASSES,
            "scl_retained_classes": SCL_EVALUATED_RETAINED,
        },
        "bands": BAND_SPECS,
        "indices": INDEX_SPECS,
        "gee_collection_audit": gee_meta,
        "existing_datasets_inventory": dataset_inventory,
    }
    if qa_outputs is not None:
        metadata["dataset_row_counts"] = {
            "monthly": int(len(qa_outputs["monthly"])),
            "seasonal": int(len(qa_outputs["seasonal"])),
            "annual": int(len(qa_outputs["annual"])),
        }
        metadata["quality_assurance_summary"] = qa_outputs["qa"].to_dict(orient="records")
        metadata["exported_rasters"] = qa_outputs["rasters"]
    if analysis_outputs is not None:
        metadata["maps_created"] = analysis_outputs["maps_created"]

    with open(METADATA_DIR / "processing_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    dd_rows = [
        ("sentinel2_monthly_indices_2017_2025.csv", "year_month", "string (YYYY-MM)", "-", "Calendar year-month"),
        ("sentinel2_monthly_indices_2017_2025.csv", "image_count", "int", "count", "Source Sentinel-2 scenes intersecting Guelma in period"),
        ("sentinel2_monthly_indices_2017_2025.csv", "NDVI_median", "float", "unitless", "Monthly spatial median NDVI at 10 m"),
        ("sentinel2_monthly_indices_2017_2025.csv", "EVI_median", "float", "unitless", "Monthly spatial median EVI at 10 m"),
        ("sentinel2_monthly_indices_2017_2025.csv", "NDMI_median", "float", "unitless", "Monthly spatial median NDMI at 20 m (canopy water indicator)"),
        ("sentinel2_monthly_indices_2017_2025.csv", "NDRE_median", "float", "unitless", "Monthly spatial median NDRE at 20 m (B8A, B5)"),
        ("sentinel2_monthly_indices_2017_2025.csv", "NDVI_valid_pixels", "int", "pixels", "Valid unmasked 10 m pixels in composite"),
        ("sentinel2_monthly_indices_2017_2025.csv", "NDVI_valid_pct", "float", "%", "Percentage of Guelma 10 m pixels with valid observations"),
        ("sentinel2_seasonal_indices_2017_2025.csv", "completeness_status", "string", "-", "COMPLETE, INCOMPLETE_NO_DEC2016_L2A, PARTIAL_LOW_COVERAGE, or EMPTY"),
    ]
    pd.DataFrame(dd_rows, columns=["dataset", "column_name", "dtype", "unit", "description"]).to_csv(
        METADATA_DIR / "data_dictionary.csv", index=False, encoding="utf-8"
    )

    gee_status = "EXECUTED" if qa_outputs is not None else "PENDING_GEE_AUTHENTICATION"
    readme = f"""# Sentinel-2 Vegetation Monitoring Pipeline — Guelma Wilaya (2017–2025)

**Status:** `{gee_status}`  
**Collection:** `{S2_COLLECTION_ID}` (paired with `{S2_CLOUD_PROB_ID}`)  
**Boundary:** `{boundary_audit['boundary_file']}` (`{boundary_audit['utm_area_km2']} km²` in `{TARGET_CRS}`)

## Resolution & Masking Policy
- **Reflectance scaling:** `DN × 0.0001` applied before all index calculations.
- **Cloud & shadow masking:** Exclude `SCL` classes `{list(SCL_EXCLUDED_CLASSES.keys())}` plus `S2_CLOUD_PROBABILITY >= {CLOUD_PROB_THRESHOLD}%` (where matched by `system:index`). `SCL` Class 2 (`Dark area pixels`) is retained by default to preserve mountain/moist-soil pixels.
- **Spatial resolution:**
  - `NDVI` (`B8, B4`) & `EVI` (`B8, B4, B2`): native **`10 m`** (`EPSG:32632`).
  - `NDMI` (`B8, B11`) & `NDRE` (`B8A, B5`): native **`20 m`** (`EPSG:32632`; `B8` aggregated to 20 m, never upsampled to 10 m).

## Pipeline Scripts
- GEE JavaScript Code Editor script: `gee/sentinel2_guelma_2017_2025.js`
- Python pipeline runner: `python run_sentinel2_pipeline.py`

## Integration Readiness
See `processed/metadata/integration_readiness_report.md` for full resolution comparison across Sentinel-2, MODIS, SoilGrids, SMAP, GPM, and NASA POWER.
"""
    (SENTINEL2_DIR / "README.md").write_text(readme, encoding="utf-8")
