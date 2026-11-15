"""Task 4: Multi-Resolution Spatial Harmonization & Grid Alignment (zero fake upsampling)."""

import gc
from typing import Dict

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject
from shapely.geometry import box

from .config import (
    CANONICAL_DIR,
    CROP_FREQ_ALIGNED_10M_TIF,
    CROP_FREQ_RAW_TIF,
    GPM_ANNUAL_STACK_TIF,
    MODIS_SEASONAL_DIR,
    NASA_POWER_AG_GPKG,
    NASA_POWER_DAILY_CELLS_CSV,
    NASA_POWER_RE_GPKG,
    NODATA_VALUE,
    S2_PHASEA_10M_TIF,
    S2_PHASEA_20M_TIF,
    SEASON_ORDER,
    SEASONAL_ALIGNED_CSV,
    SEASONAL_ALIGNED_DIR,
    SMAP_ANNUAL_STACK_TIF,
    SPATIAL_INT_DIR,
    STUDY_END_YEAR,
    STUDY_START_YEAR,
    TARGET_CRS,
)


def align_crop_frequency_to_s2_10m() -> Dict:
    """Fix the ~5.12m/1.97m origin shift by snapping ESA Crop Frequency (10m) onto exact S2 10m grid."""
    SPATIAL_INT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(S2_PHASEA_10M_TIF) as ref, rasterio.open(CROP_FREQ_RAW_TIF) as src:
        dst_arr = np.full((ref.height, ref.width), NODATA_VALUE, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst_arr,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            dst_nodata=NODATA_VALUE,
            resampling=Resampling.nearest,
        )
        profile = ref.profile.copy()
        profile.update(count=1, dtype="float32", nodata=NODATA_VALUE, compress="lzw")
        with rasterio.open(CROP_FREQ_ALIGNED_10M_TIF, "w", **profile) as dst:
            dst.write(dst_arr, 1)
            dst.set_band_description(1, "crop_frequency_2021_2025_aligned_s2_10m")

        valid_cnt = int((dst_arr != NODATA_VALUE).sum())
        shift_x = round(abs(src.transform.c - ref.transform.c), 3)
        shift_y = round(abs(src.transform.f - ref.transform.f), 3)
        del dst_arr
        gc.collect()
        return {
            "raw_origin": [round(src.transform.c, 2), round(src.transform.f, 2)],
            "s2_10m_origin": [round(ref.transform.c, 2), round(ref.transform.f, 2)],
            "origin_shift_before_fix_m": [shift_x, shift_y],
            "aligned_shape_hw": [ref.height, ref.width],
            "aligned_valid_pixels": valid_cnt,
        }


def _downward_aggregate_to_250m(grid250: pd.DataFrame) -> pd.DataFrame:
    """Downwardly aggregate fine 10m/20m layers onto the canonical 250m SoilGrids/MODIS grid."""
    mod_ref = MODIS_SEASONAL_DIR / "guelma_modis_seasonal_2025.tif"
    with rasterio.open(mod_ref) as r250:
        t250, w250, h250 = r250.transform, r250.width, r250.height
        crs250 = r250.crs

    rr = grid250["row_250m"].to_numpy(dtype=np.int32)
    cc = grid250["col_250m"].to_numpy(dtype=np.int32)
    out = pd.DataFrame({"grid_250m_id": grid250["grid_250m_id"]})

    # 1. Downwardly aggregate aligned 10m Crop Frequency (2021-2025) to 250m via Resampling.average
    with rasterio.open(CROP_FREQ_ALIGNED_10M_TIF) as cf:
        cf_250 = np.full((h250, w250), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(cf, 1),
            destination=cf_250,
            src_transform=cf.transform,
            src_crs=cf.crs,
            src_nodata=cf.nodata,
            dst_transform=t250,
            dst_crs=crs250,
            dst_nodata=np.nan,
            resampling=Resampling.average,
        )
    out["crop_freq_2021_2025_mean_250m"] = np.round(cf_250[rr, cc].astype("float64"), 4)
    out["is_cropland_ge_05_2021_2025"] = out["crop_freq_2021_2025_mean_250m"] >= 0.5
    del cf_250

    # 2. Downwardly aggregate March 2024 Sentinel-2 baseline (10m NDVI/EVI & 20m NDMI/NDRE) to 250m
    boundary = gpd.read_file(CANONICAL_DIR / "spatial_reference" / "guelma_wilaya_utm32n.gpkg")
    geoms = list(boundary.geometry)

    for src_path, b_names in [(S2_PHASEA_10M_TIF, ["s2_2024_03_ndvi_250m", "s2_2024_03_evi_250m"]), (S2_PHASEA_20M_TIF, ["s2_2024_03_ndmi_250m", "s2_2024_03_ndre_250m"])]:
        with rasterio.open(src_path) as s_src:
            outside = geometry_mask(geoms, out_shape=(s_src.height, s_src.width), transform=s_src.transform, all_touched=False)
            for b_idx, col_name in enumerate(b_names, start=1):
                arr = s_src.read(b_idx).astype("float32")
                # Pre-Phase-B 2024-03 snapshot used 0 outside boundary; mask outside cleanly before average
                arr[outside] = np.nan
                if s_src.nodata is not None:
                    arr[arr == s_src.nodata] = np.nan
                dst_250 = np.full((h250, w250), np.nan, dtype=np.float32)
                reproject(
                    source=arr,
                    destination=dst_250,
                    src_transform=s_src.transform,
                    src_crs=s_src.crs,
                    src_nodata=np.nan,
                    dst_transform=t250,
                    dst_crs=crs250,
                    dst_nodata=np.nan,
                    resampling=Resampling.average,
                )
                out[col_name] = np.round(dst_250[rr, cc].astype("float64"), 4)
                del arr, dst_250
            del outside
            gc.collect()

    # 3. Sample native 250m MODIS seasonal climatology (2016-2025) on the exact same (286, 367) grid
    for s_idx, sname in enumerate(SEASON_ORDER):
        ndvi_stack = []
        evi_stack = []
        for yr in range(STUDY_START_YEAR, STUDY_END_YEAR + 1):
            mpath = MODIS_SEASONAL_DIR / f"guelma_modis_seasonal_{yr}.tif"
            with rasterio.open(mpath) as ms:
                b_ndvi = s_idx * 3 + 1
                b_evi = s_idx * 3 + 2
                n_arr = ms.read(b_ndvi).astype("float32")
                e_arr = ms.read(b_evi).astype("float32")
                n_arr[n_arr == NODATA_VALUE] = np.nan
                e_arr[e_arr == NODATA_VALUE] = np.nan
                ndvi_stack.append(n_arr[rr, cc])
                evi_stack.append(e_arr[rr, cc])
        out[f"modis_ndvi_{sname.lower()}_2016_2025_mean"] = np.round(np.nanmean(np.vstack(ndvi_stack), axis=0), 4)
        out[f"modis_evi_{sname.lower()}_2016_2025_mean"] = np.round(np.nanmean(np.vstack(evi_stack), axis=0), 4)

    out.to_csv(SPATIAL_INT_DIR / "landscape_250m_spatial_layers.csv", index=False, encoding="utf-8")
    return out


def _area_weighted_grid_to_communes(communes: gpd.GeoDataFrame, grid_polys: gpd.GeoDataFrame, id_col: str, val_df: pd.DataFrame, group_cols: list, val_cols: list) -> pd.DataFrame:
    """Exact polygon intersection area-weighted aggregation from coarse cells onto 34 communes."""
    inter = gpd.overlay(communes[["commune_num_id", "GID_2", "NAME_2", "geometry"]], grid_polys[[id_col, "geometry"]], how="intersection")
    inter["inter_area_m2"] = inter.geometry.area
    w_df = inter[["commune_num_id", "GID_2", "NAME_2", id_col, "inter_area_m2"]].copy()

    merged = w_df.merge(val_df, on=id_col, how="inner")
    records = []
    # Vectorized weighted aggregation per commune (+ group_cols)
    for vc in val_cols:
        merged[f"_wv_{vc}"] = merged[vc] * merged["inter_area_m2"]
        merged[f"_wa_{vc}"] = np.where(np.isfinite(merged[vc]), merged["inter_area_m2"], 0.0)

    g_cols = ["commune_num_id", "GID_2", "NAME_2"] + group_cols
    agg_dict = {f"_wv_{vc}": "sum" for vc in val_cols}
    agg_dict.update({f"_wa_{vc}": "sum" for vc in val_cols})
    agg_dict["inter_area_m2"] = "sum"
    grp = merged.groupby(g_cols, as_index=False).agg(agg_dict)
    for vc in val_cols:
        grp[vc] = np.where(grp[f"_wa_{vc}"] > 0, grp[f"_wv_{vc}"] / grp[f"_wa_{vc}"], np.nan)
        grp = grp.drop(columns=[f"_wv_{vc}", f"_wa_{vc}"])
    return grp.rename(columns={"inter_area_m2": "covered_area_m2"})


def _build_commune_zonal_tables() -> Dict[str, int]:
    """Compute commune-level (n=34) zonal tables preserving exact native support metadata."""
    communes = gpd.read_file(CANONICAL_DIR / "spatial_reference" / "guelma_communes_utm32n.gpkg")
    soil_250 = pd.read_csv(CANONICAL_DIR / "soil_properties" / "soilgrids_250m_canonical.csv")
    c_geoms = [(geom, int(cid)) for geom, cid in zip(communes.geometry, communes["commune_num_id"])]

    # 1. SoilGrids (250m -> 34 Communes via within/centroid assignment + valid fraction check)
    # Count total 250m grid cells intersecting each commune polygon
    with rasterio.open(MODIS_SEASONAL_DIR / "guelma_modis_seasonal_2025.tif") as r250:
        cid_raster_250 = rasterize(c_geoms, out_shape=(r250.height, r250.width), transform=r250.transform, fill=0, dtype="uint8", all_touched=False)
        tot_250_by_c = {int(c): int((cid_raster_250 == c).sum()) for c in communes["commune_num_id"]}

    soil_props_0_30 = ["clay_0_30cm", "sand_0_30cm", "silt_0_30cm", "ph_0_30cm", "soc_0_30cm", "cec_0_30cm", "nitrogen_0_30cm"]
    soil_props_30_100 = ["clay_30_100cm", "sand_30_100cm", "silt_30_100cm", "ph_30_100cm", "soc_30_100cm", "cec_30_100cm"]
    s_valid = soil_250.dropna(subset=["commune_num_id"]).copy()
    s_valid["commune_num_id"] = s_valid["commune_num_id"].astype(int)
    c_soil = s_valid.groupby("commune_num_id", as_index=False)[soil_props_0_30 + soil_props_30_100].mean().round(4)
    c_soil_cnt = s_valid.groupby("commune_num_id", as_index=False)["grid_250m_id"].count().rename(columns={"grid_250m_id": "soil_valid_250m_px"})
    c_soil = communes[["commune_num_id", "GID_2", "NAME_2", "area_km2"]].merge(c_soil_cnt, on="commune_num_id").merge(c_soil, on="commune_num_id")
    c_soil["commune_total_250m_px"] = c_soil["commune_num_id"].map(tot_250_by_c)
    c_soil["soil_valid_fraction"] = (c_soil["soil_valid_250m_px"] / c_soil["commune_total_250m_px"]).round(4)
    c_soil = c_soil.rename(columns={"nitrogen_0_30cm": "soil_nitrogen_0_30cm_unvalidated"})

    # 2. Crop Frequency (aligned 10m -> 34 Communes) & March 2024 Sentinel-2 (10m & 20m -> 34 Communes)
    cf_rows = []
    with rasterio.open(CROP_FREQ_ALIGNED_10M_TIF) as cf:
        cid_10 = rasterize(c_geoms, out_shape=(cf.height, cf.width), transform=cf.transform, fill=0, dtype="uint8", all_touched=False)
        cf_arr = cf.read(1)
        for c in communes["commune_num_id"]:
            m_c = cid_10 == int(c)
            vals = cf_arr[m_c]
            v = vals[vals != NODATA_VALUE]
            cf_rows.append(
                {
                    "commune_num_id": int(c),
                    "crop_freq_2021_2025_mean": round(float(np.mean(v)), 4) if v.size else np.nan,
                    "crop_share_ge_05_2021_2025_pct": round(float(np.mean(v >= 0.5) * 100.0), 2) if v.size else np.nan,
                }
            )
        del cf_arr

    with rasterio.open(S2_PHASEA_10M_TIF) as s10:
        assert (s10.height, s10.width) == cid_10.shape
        ndvi_10 = s10.read(1)
        evi_10 = s10.read(2)
        s2_rows = []
        for idx_r, c in enumerate(communes["commune_num_id"]):
            m_c = cid_10 == int(c)
            nv = ndvi_10[m_c]
            ev = evi_10[m_c]
            nv = nv[np.isfinite(nv) & (nv != 0)]
            ev = ev[np.isfinite(ev) & (ev != 0)]
            s2_rows.append(
                {
                    "commune_num_id": int(c),
                    "s2_2024_03_ndvi_median": round(float(np.median(nv)), 4) if nv.size else np.nan,
                    "s2_2024_03_evi_median": round(float(np.median(ev)), 4) if ev.size else np.nan,
                }
            )
        del ndvi_10, evi_10, cid_10
        gc.collect()

    with rasterio.open(S2_PHASEA_20M_TIF) as s20:
        cid_20 = rasterize(c_geoms, out_shape=(s20.height, s20.width), transform=s20.transform, fill=0, dtype="uint8", all_touched=False)
        ndmi_20 = s20.read(1)
        ndre_20 = s20.read(2)
        for idx_r, c in enumerate(communes["commune_num_id"]):
            m_c = cid_20 == int(c)
            mv = ndmi_20[m_c]
            rv = ndre_20[m_c]
            mv = mv[np.isfinite(mv) & (mv != 0)]
            rv = rv[np.isfinite(rv) & (rv != 0)]
            s2_rows[idx_r]["s2_2024_03_ndmi_median"] = round(float(np.median(mv)), 4) if mv.size else np.nan
            s2_rows[idx_r]["s2_2024_03_ndre_median"] = round(float(np.median(rv)), 4) if rv.size else np.nan
        del ndmi_20, ndre_20, cid_20
        gc.collect()

    c_static = c_soil.merge(pd.DataFrame(cf_rows), on="commune_num_id").merge(pd.DataFrame(s2_rows), on="commune_num_id")
    c_static["crop_freq_temporal_validity"] = "2021_2025_ONLY_DO_NOT_USE_FOR_2017_2020"
    c_static["s2_snapshot_note"] = "Single-month 2024-03 Phase A baseline; multi-year S2 rasters pending GEE quota"
    c_static.to_csv(SPATIAL_INT_DIR / "commune_static_layers.csv", index=False, encoding="utf-8")

    # 3. MODIS Seasonal (250m -> 34 Communes x 40 seasons = 1,360 rows)
    mod_records = []
    for yr in range(STUDY_START_YEAR, STUDY_END_YEAR + 1):
        with rasterio.open(MODIS_SEASONAL_DIR / f"guelma_modis_seasonal_{yr}.tif") as ms:
            for s_idx, sname in enumerate(SEASON_ORDER):
                n_arr = ms.read(s_idx * 3 + 1)
                e_arr = ms.read(s_idx * 3 + 2)
                o_arr = ms.read(s_idx * 3 + 3)
                for c in communes["commune_num_id"]:
                    m_c = cid_raster_250 == int(c)
                    vn = n_arr[m_c]
                    ve = e_arr[m_c]
                    vo = o_arr[m_c]
                    valid_n = vn[vn != NODATA_VALUE]
                    valid_e = ve[ve != NODATA_VALUE]
                    valid_o = vo[vo != NODATA_VALUE]
                    mod_records.append(
                        {
                            "commune_num_id": int(c),
                            "season_year": yr,
                            "season": sname,
                            "modis_ndvi_mean": round(float(np.mean(valid_n)), 4) if valid_n.size else np.nan,
                            "modis_evi_mean": round(float(np.mean(valid_e)), 4) if valid_e.size else np.nan,
                            "modis_valid_obs_mean": round(float(np.mean(valid_o)), 2) if valid_o.size else np.nan,
                            "modis_valid_250m_px": int(valid_n.size),
                        }
                    )
    c_mod_sea = pd.DataFrame(mod_records)

    # 4. Coarse 11km Aligned (GPM + SMAP) exact area-weighted polygon intersection to 34 Communes
    env_aligned = pd.read_csv(SEASONAL_ALIGNED_CSV)
    env_aligned["cell_id"] = env_aligned["Cell_Row"].astype(str) + "_" + env_aligned["Cell_Col"].astype(str)
    g11 = env_aligned[["cell_id", "X_UTM32N_m", "Y_UTM32N_m"]].drop_duplicates().copy()
    g11["geometry"] = [box(x - 5500.0, y - 5500.0, x + 5500.0, y + 5500.0) for x, y in zip(g11["X_UTM32N_m"], g11["Y_UTM32N_m"])]
    g11_gdf = gpd.GeoDataFrame(g11, crs=TARGET_CRS)

    env_val = env_aligned.rename(columns={"Year": "season_year", "Season": "season", "Rainfall_mm": "gpm_precip_mm", "Surface_SM_m3m3": "smap_sm_surface_m3m3", "Rootzone_SM_m3m3": "smap_sm_rootzone_m3m3"})
    c_coarse_sea = _area_weighted_grid_to_communes(
        communes,
        g11_gdf,
        "cell_id",
        env_val[["cell_id", "season_year", "season", "gpm_precip_mm", "smap_sm_surface_m3m3", "smap_sm_rootzone_m3m3"]],
        ["season_year", "season"],
        ["gpm_precip_mm", "smap_sm_surface_m3m3", "smap_sm_rootzone_m3m3"],
    ).rename(columns={"covered_area_m2": "coarse_11km_covered_m2"})

    # 5. NASA POWER AG (0.5x0.625 deg) & RE (1.0x1.0 deg) seasonal cell area-weighted intersection to 34 Communes
    np_cells = pd.read_csv(NASA_POWER_DAILY_CELLS_CSV)
    # Assign Dec to year+1 for meteorological Winter consistency with NASA POWER seasonal & GPM/SMAP
    np_cells["season_year"] = np.where(np_cells["month"] == 12, np_cells["year"] + 1, np_cells["year"])
    np_cells = np_cells[np_cells["season_year"].between(STUDY_START_YEAR, STUDY_END_YEAR)]
    np_cells_sea = np_cells.groupby(["cell_id", "community", "variable", "season_year", "season"], as_index=False)["value"].agg(["mean", "sum", "count"])

    ag_cells_gdf = gpd.read_file(NASA_POWER_AG_GPKG, layer="intersections")[["cell_id", "geometry"]]
    re_cells_gdf = gpd.read_file(NASA_POWER_RE_GPKG, layer="intersections")[["cell_id", "geometry"]]

    # Pivot AG seasonal variables per cell
    ag_sub = np_cells_sea[np_cells_sea["community"] == "AG"].copy()
    ag_piv = ag_sub.pivot(index=["cell_id", "season_year", "season"], columns="variable", values="mean").reset_index()
    ag_prec = ag_sub[ag_sub["variable"] == "PRECTOTCORR"][["cell_id", "season_year", "season", "sum"]].rename(columns={"sum": "PRECTOTCORR_sum_mm"})
    ag_piv = ag_piv.merge(ag_prec, on=["cell_id", "season_year", "season"]).rename(
        columns={"T2M": "np_t2m_mean_c", "T2M_MAX": "np_t2m_max_c", "T2M_MIN": "np_t2m_min_c", "RH2M": "np_rh2m_mean_pct", "PRECTOTCORR_sum_mm": "np_prectot_sum_mm"}
    )
    c_ag_sea = _area_weighted_grid_to_communes(
        communes,
        ag_cells_gdf,
        "cell_id",
        ag_piv[["cell_id", "season_year", "season", "np_t2m_mean_c", "np_t2m_max_c", "np_t2m_min_c", "np_rh2m_mean_pct", "np_prectot_sum_mm"]],
        ["season_year", "season"],
        ["np_t2m_mean_c", "np_t2m_max_c", "np_t2m_min_c", "np_rh2m_mean_pct", "np_prectot_sum_mm"],
    ).drop(columns=["covered_area_m2"])

    re_sub = np_cells_sea[np_cells_sea["community"] == "RE"].rename(columns={"mean": "np_sw_dwn_mean_kwh_m2_day"})
    c_re_sea = _area_weighted_grid_to_communes(
        communes,
        re_cells_gdf,
        "cell_id",
        re_sub[["cell_id", "season_year", "season", "np_sw_dwn_mean_kwh_m2_day"]],
        ["season_year", "season"],
        ["np_sw_dwn_mean_kwh_m2_day"],
    ).drop(columns=["covered_area_m2"])

    c_sea = (
        c_mod_sea.merge(communes[["commune_num_id", "GID_2", "NAME_2", "area_km2"]], on="commune_num_id")
        .merge(c_coarse_sea, on=["commune_num_id", "GID_2", "NAME_2", "season_year", "season"])
        .merge(c_ag_sea, on=["commune_num_id", "GID_2", "NAME_2", "season_year", "season"])
        .merge(c_re_sea, on=["commune_num_id", "GID_2", "NAME_2", "season_year", "season"])
    )
    for col in ["gpm_precip_mm", "smap_sm_surface_m3m3", "smap_sm_rootzone_m3m3", "np_t2m_mean_c", "np_t2m_max_c", "np_t2m_min_c", "np_rh2m_mean_pct", "np_prectot_sum_mm", "np_sw_dwn_mean_kwh_m2_day"]:
        c_sea[col] = c_sea[col].round(4)

    c_sea["is_complete_season"] = ~((c_sea["season_year"] == 2016) & (c_sea["season"] == "Winter"))
    c_sea["fine_veg_support_m"] = 250
    c_sea["gpm_smap_support_tag"] = "COARSE_11KM_MACRO_CONTEXT_NOT_LOCAL"
    c_sea["nasa_power_support_tag"] = "REGIONAL_55_111KM_MACRO_CONTEXT_NOT_LOCAL"
    c_sea.to_csv(SPATIAL_INT_DIR / "commune_seasonal_merged.csv", index=False, encoding="utf-8")

    return {
        "commune_static_rows": len(c_static),
        "commune_seasonal_rows": len(c_sea),
    }


def run_spatial_harmonization() -> Dict:
    SPATIAL_INT_DIR.mkdir(parents=True, exist_ok=True)
    grid250 = pd.read_csv(CANONICAL_DIR / "spatial_reference" / "grid_250m_utm32n_master.csv")
    align_info = align_crop_frequency_to_s2_10m()
    d250 = _downward_aggregate_to_250m(grid250)
    cz = _build_commune_zonal_tables()
    return {"crop_freq_align": align_info, "landscape_250m_rows": len(d250), **cz}
