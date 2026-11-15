# Deferred Google Earth Engine Task Inventory — Phase C Recovery Plan

**GEE Project:** `spry-framework-514800-j2` (`REGISTERED_NOT_COMMERCIALLY`)  
**Current Project State:** `RESTRICTED_MODE_QUOTA_EXCEEDED` (captured `2026-11-15T01:55:50Z` in [phaseC_ledger.json](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/quality/phaseC_ledger.json))  
**Drive Export Destination:** Folder `FieldShift_Sentinel2_PhaseC_2017_2025` (`1ow-VqcUKfTORTlkf1js88ovF6GXVyoRE`)  
**Machine-Readable Inventory:** [deferred_gee_task_inventory.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/quality/deferred_gee_task_inventory.csv)  
**Compliance Policy:** **No GEE jobs submitted while in restricted mode; no account or project switching.**

---

## 1. Guarantee Against Re-Running Completed Work

Before any Phase C task runs, [phaseC_runner.py](file:///home/lokman/Desktop/FeildShit-SI-Model/sentinel2_pipeline/phaseC_runner.py) checks `_is_batch_locally_verified()` against both [phaseC_ledger.json](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/quality/phaseC_ledger.json) (`state == "COMPLETED"` and `checksum_verified == True`) and local file existence in `data/SENTINEL2/raw/phaseC_2017_2025/`:

- **`36 / 36` Quarterly Monthly CSV Batches (`108` months, `2017-Q1`..`2025-Q4`):** **PERMANENTLY SKIPPED** (`COMPLETED` & MD5-verified).
- **`1 / 1` Global Scene Inventory (`3,593` scenes, `2016-12`..`2025-12`):** **PERMANENTLY SKIPPED** (`COMPLETED` & MD5-verified).
- **Offline Verification Command (Zero GEE API Calls):**
  ```bash
  /home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step status
  /home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group all
  ```
  *Note: `--step resume-deferred` runs in `--dry-run` mode by default and requires explicit `--live` once quota resets.*

---

## 2. Deferred Task Summary by Execution Priority (`39` Tasks Total)

| Priority | Group Flag (`--group`) | Deferred Task Scope | Task Count | Estimated EECU-s Range | Scientific / Analytical Value |
|---:|---|---|---:|---:|---|
| **1 (Highest ROI)** | `rasters-monthly` | Selected representative monthly GeoTIFFs (`2019-04` wet spring, `2022-07` drought summer, `2024-03` Phase B clean, `2025-04` latest spring) at `10 m` & `20 m` | `8` GeoTIFFs | `23,000 – 28,000` | Contrasting hydro-climatic spatial maps with validated `-9999` NoData and `EVI denom>0.1` guard (`<5%` of Phase C budget) |
| **2** | `rasters-annual` + `rasters-coverage` | Annual pixel-median GeoTIFFs (`2017`, `2025`; `10 m` 6-band + `20 m` 2-band) & 9-yr `20 m` `valid_obs_count` map | `5` GeoTIFFs | `60,000 – 116,000` | Long-term baseline comparison (`2017` vs `2025`) & spatial observation density audit map |
| **3** | `rasters-seasonal` | Multi-year pixel-median seasonal GeoTIFFs (`winter, spring, summer, autumn` across `2018–2025` complete seasons at `10 m` & `20 m`) | `8` GeoTIFFs | `60,000 – 120,000` | High-SNR spatial phenology composites excluding incomplete `Winter 2017` |
| **4 (Optional Heavy)** | `seasonal-tables` + `annual-tables` | Pixel-level seasonal CSVs (`phaseC_seasonal_2017..2025`, `36` rows) & annual CSVs (`phaseC_annual_2017..2025`, `9` rows) | `18` CSV batches | `414,000 – 657,000` | True multi-month pixel medians (`median_xy(median_t)`); run one year at a time to stay within quota windows |
| **Total Deferred** | `all` | **21 GeoTIFFs + 18 CSV table batches** | **`39` tasks** | **`557,000 – 921,000`** | **All `21` Priority 1–3 GeoTIFFs cost only `~143k – 264k` EECU-s combined** |

---

## 3. Recommended Safe Resumption Commands (Only After Quota Resets)

Run one group at a time in priority order, verifying quota warnings and MD5 checksums after each batch:

```bash
# 0. Verify project has exited restricted mode cleanly first:
/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step preflight

# 1. Priority 1: Selected Monthly GeoTIFFs (~23k-28k EECU-s):
/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group rasters-monthly --live

# 2. Priority 2: Annual 2017 & 2025 GeoTIFFs + 2017-2025 20m Coverage GeoTIFF (~60k-116k EECU-s):
/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group rasters-annual --live
/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group rasters-coverage --live

# 3. Priority 3: Multi-year Seasonal GeoTIFFs 2018-2025 (~60k-120k EECU-s):
/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group rasters-seasonal --live

# 4. Priority 4 (atomic year-by-year): Pixel-level Seasonal & Annual CSV tables:
/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m sentinel2_pipeline.phaseC_runner --step seasonal-years --years 2024
```
