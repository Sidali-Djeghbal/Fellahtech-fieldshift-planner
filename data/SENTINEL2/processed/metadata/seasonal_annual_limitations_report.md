# Seasonal and Annual Aggregation Limitations Report — Sentinel-2 (`2017–2025`)

**Audited Tables:**
- [sentinel2_seasonal_from_monthly_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/seasonal/sentinel2_seasonal_from_monthly_2017_2025.csv) (`36` rows: `2017–2025 × 4 seasons`)
- [sentinel2_annual_from_monthly_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/annual/sentinel2_annual_from_monthly_2017_2025.csv) (`9` rows: `2017–2025`)
- Derived summaries: [vegetation_trends.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/analysis/vegetation_trends.csv), [seasonal_vegetation_patterns.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/analysis/seasonal_vegetation_patterns.csv)

---

## 1. Explicit Methodological Distinction (`Mean of Monthly Summaries` ≠ `Pixel-Level Median Composite`)

Because GEE project `spry-framework-514800-j2` entered noncommercial `restricted mode` immediately after completing the `108` monthly statistical summaries, server-side GEE pixel-level seasonal and annual median composites (`step_seasonal_years`, `step_annual_years`, and their corresponding GeoTIFFs) were **halted and NOT fabricated**.

Instead, the existing seasonal and annual CSVs were derived strictly by aggregating the `108` verified monthly regional summaries:

- **What these tables ACTUALLY contain (`aggregation_basis` column):**
  - `NDVI_median_of_months`, `EVI_median_of_months`, `NDMI_median_of_months`, `NDRE_median_of_months`: **Arithmetic mean of 3 (or 12) monthly regional spatial medians** (`mean(median_px_m)`).
  - `NDVI_mean_of_months`, `EVI_mean_of_months`: **Arithmetic mean of 3 (or 12) monthly regional spatial means**.
- **What these tables DO NOT represent:**
  - They are **NOT** true GEE pixel-level temporal median composites (`reduceRegion(median(collection_3months))`).
  - Mathematically, an average of monthly spatial medians (`mean_t(median_xy(X))`) can diverge systematically from the spatial median of a multi-month pixel median (`median_xy(median_t(X))`) because:
    1. Equal monthly weighting ignores uneven cloud-free observation counts across months (e.g., `2017-01` with `1.42%` coverage would weight `1/3` of `Winter` or `1/12` of `2017` unless filtered!).
    2. Phenological asymmetry across a season (e.g., March–April–May cereal green-up) makes a pixel-level 3-month median track middle-month greenness while the mean of monthly medians tracks the linear average across early, peak, and late stages.
    3. Spatial heterogeneity between irrigated valleys and upland bare soils creates non-commuting spatial/temporal medians.

---

## 2. Incomplete Periods Audit & Preserved Flags

All incomplete periods remain explicitly flagged in `completeness_status` and excluded from multi-year baseline statistics where appropriate:

| Period | Dataset | Flagged Status | Empirical Issue | Mandatory Handling Rule |
|---|---|---|---|---|
| **`2017-01`** | Monthly | `PARTIAL_LOW_COVERAGE` | `1` scene (`1.4173%` coverage at `10 m`) | Filter out before monthly trend / anomaly calculation |
| **`Winter 2017`** (`Dec 2016 – Feb 2017`) | Seasonal | `INCOMPLETE_DEC2016(1scene)_AND_JAN2017(1.42%)` | `2016-12` not in monthly series (`1` L2A scene in scene inventory only); `2017-01` covers only `1.42%` (`mean_month_valid_pct_10m = 50.36%`) | Excluded automatically from `seasonal_vegetation_patterns.csv` & boxplots (`complete_years = 8`, `2018–2025`) |
| **`Annual 2017`** (`Jan–Dec 2017`) | Annual | `PARTIAL_JAN_1SCENE` | Includes `1.42%`-coverage `2017-01` as `1/12` of annual mean | Reported separately (`2018–2025` `8`-yr trend evaluated independently in `vegetation_trends.csv`) |

---

## 3. Documentation & Schema Compliance Audit

A full text and schema audit across `data/SENTINEL2/` confirms that **zero downstream artifacts misclassify these tables as true pixel-level seasonal or annual composites**:
- Column names end explicitly in `_of_months` (`NDVI_median_of_months`, etc.), avoiding ambiguous collision with server-computed GEE composite columns.
- Every row carries the explicit `aggregation_basis` string:
  - Seasonal: `"Mean of GEE 10m/20m monthly spatial summaries (pixel-level GEE seasonal composite pending quota reset)"`
  - Annual: `"Mean of 12 GEE monthly spatial summaries (pixel-level GEE annual composite pending quota reset)"`
- `data_dictionary.csv`, `vegetation_trends.csv`, `integration_readiness_report.md`, `phaseC_final_execution_report.md`, `README.md`, and figure titles (`seasonal_ndvi_ndmi_comparison.png`, `annual_vegetation_index_changes.png`) all explicitly state `derived from monthly medians` / `monthly-aggregated` and point to deferred GEE tasks for pixel-level seasonal/annual products.

---

## 4. Recommended Analytical Usage Until Quota Reset

1. **Prefer Monthly Time-Series Directly (`2017-02` – `2025-12`, `107` complete months):** Monthly composites are full GEE pixel-level temporal medians evaluated at native `10 m`/`20 m` over Guelma.
2. **Use `2018–2025` for Inter-Annual & Seasonal Monthly-Aggregated Comparisons:** All `8` years (`32` seasons, `96` months) have `>=95.94%` spatial coverage in every month.
3. **Trigger `step_seasonal_years` / `step_annual_years` After Quota Recovery** (see [deferred_gee_task_inventory.md](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/quality/deferred_gee_task_inventory.md)) when true pixel-level seasonal/annual distributions or spatial maps are required for spatial modeling.
