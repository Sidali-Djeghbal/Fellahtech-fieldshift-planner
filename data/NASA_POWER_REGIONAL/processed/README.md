# NASA POWER Regional Climate Processing — Guelma Wilaya (2016–2025)

**Project:** Field Shift (NASA Space Apps Challenge 2026)  
**Study Area:** Guelma Wilaya, Algeria (`3683.23 km²` in `EPSG:32632`; `3684.25 km²` WGS84 geodesic, difference `-0.0278%`)  
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

Administrative boundary source: `/home/lokman/Desktop/FeildShit-SI-Model/data/boundaries/processed/guelma_wilaya_boundary.geojson.gpkg` (source CRS `EPSG:4326`, valid geometry).

---

## 2. Spatial Resolution & Audit Findings

- **AG (`MERRA-2`)**: `25` extracted cells (`5 × 5` regular grid), `5` intersecting Guelma, `1` cell center strictly inside Guelma. Union intersection area: `3683.2311 km²` (`100.0000%`), pairwise overlap `0.00e+00 m²`, gap `2.01e-07 m²`.
- **RE (`CERES SYN1deg`)**: `4` extracted cells (`2 × 2` regular grid), `2` intersecting Guelma, `1` cell center strictly inside Guelma. Union intersection area: `3683.2311 km²` (`100.0000%`), pairwise overlap `0.00e+00 m²`, gap `0.00e+00 m²`.
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

- `daily/nasa_power_daily_cell_values.csv`: `98,631` rows
- `daily/nasa_power_daily_guelma.csv`: `21,918` rows
- `monthly/nasa_power_monthly_guelma.csv`: `120` rows
- `seasonal/nasa_power_seasonal_guelma.csv`: `41` rows
- `annual/nasa_power_annual_guelma.csv`: `10` rows

---

## 5. Quality-Control Summary

```text
                     check_id  observed_value status                                                                                                                              details
             QA_01_DUPLICATES               0   PASS                                                                                               daily_cell_dups=0, daily_guelma_dups=0
          QA_02_MISSING_DATES               0   PASS                                          {'T2M': 0, 'T2M_MAX': 0, 'T2M_MIN': 0, 'PRECTOTCORR': 0, 'RH2M': 0, 'ALLSKY_SFC_SW_DWN': 0}
          QA_03_MISSING_CELLS               0   PASS                                                                                      Expected intersecting cells: {'AG': 5, 'RE': 2}
       QA_04_NUMERIC_VALIDITY               0   PASS                                                                                                    nan_cell=0, inf_cell=0, nan_reg=0
       QA_05_UNIT_CONSISTENCY               0   PASS {'T2M': ['C'], 'T2M_MAX': ['C'], 'T2M_MIN': ['C'], 'PRECTOTCORR': ['mm/day'], 'RH2M': ['%'], 'ALLSKY_SFC_SW_DWN': ['kW-hr/m^2/day']}
      QA_06_TEMPERATURE_ORDER               0   PASS                                                                                             cell_violations=0, regional_violations=0
   QA_07_RAINFALL_NONNEGATIVE               0   PASS                                                                                                                   cell=0, regional=0
            QA_08_RH2M_BOUNDS               0   PASS                                                                                             cell=0, regional=0, range=(13.02, 97.12)
      QA_09_SOLAR_NONNEGATIVE               0   PASS                                                                                                                   cell=0, regional=0
QA_10_AGGREGATION_CONSISTENCY               0   PASS                                                                                                                   max_diff=1.137e-13
       QA_11_SPATIAL_COVERAGE               0   PASS                                                                                                                     min_cov=1.000000
 QA_12_COORDINATE_CONSISTENCY               1   PASS                                                                                        AG=25 cells (50 files), RE=4 cells (10 files)
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
