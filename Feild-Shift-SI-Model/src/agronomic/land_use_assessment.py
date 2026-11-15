"""Multi-signal Cropland & Land-Use Evidence Assessment (Phase N).

Evaluates ESA/annual crop-frequency fractions jointly with SoilGrids masking/coverage,
Sentinel-2 / MODIS vegetation indices, Wilaya spatial overlap, pixel-to-parcel scale,
and farmer-reported cropping history so low-frequency or peri-urban polygons are never
silently treated as verified annual cropland.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

LAND_USE_SUPPORTED = "LAND_USE_SUPPORTED"
LAND_USE_LOW_EVIDENCE = "LAND_USE_LOW_EVIDENCE"
LAND_USE_UNVERIFIED = "LAND_USE_UNVERIFIED"
LAND_USE_CONFLICTING_EVIDENCE = "LAND_USE_CONFLICTING_EVIDENCE"
LAND_USE_DATA_UNAVAILABLE = "LAND_USE_DATA_UNAVAILABLE"

LAND_USE_STATUSES = (
    LAND_USE_SUPPORTED,
    LAND_USE_LOW_EVIDENCE,
    LAND_USE_UNVERIFIED,
    LAND_USE_CONFLICTING_EVIDENCE,
    LAND_USE_DATA_UNAVAILABLE,
)

_UNAVAILABLE_QUALITY = {
    "UNAVAILABLE_NOT_INTEGRATED",
    "UNAVAILABLE_MASKED_PIXEL",
    "TEMPORAL_GUARD_EXCLUDED",
    "UNVALIDATED_EXCLUDED",
    "UNAVAILABLE",
}


@dataclass(frozen=True)
class LandUseThresholds:
    """Configurable thresholds for multi-signal cropland classification."""

    supported_min_crop_freq: float = 0.40
    supported_min_share_ge_05_pct: float = 40.0
    very_low_crop_freq: float = 0.05
    very_low_share_ge_05_pct: float = 5.0
    low_veg_ndvi: float = 0.24
    high_veg_ndvi: float = 0.40
    low_soilgrids_cov_pct: float = 25.0
    small_parcel_coarse_ha_threshold: float = 6.25  # 1 SoilGrids 250m pixel


DEFAULT_LAND_USE_THRESHOLDS = LandUseThresholds()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _farmer_reported_active_crops(field_profile: Dict[str, Any]) -> bool:
    """Return True if farmer submitted non-fallow recent crop history."""
    sec_a = field_profile.get("section_a_farmer_provided") or field_profile.get("section_a_farmer_inputs") or {}
    hist = sec_a.get("crop_history")
    if not isinstance(hist, list) or not hist:
        return False
    for row in hist:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("crop_id") or "").strip().upper()
        raw = str(row.get("crop_name_raw") or "").strip().lower()
        if cid == "BARE_FALLOW" or raw in {"fallow", "bare fallow", "jachere", "jachère"}:
            continue
        if cid or raw:
            return True
    return False


def assess_land_use(
    field_profile: Dict[str, Any],
    *,
    thresholds: LandUseThresholds = DEFAULT_LAND_USE_THRESHOLDS,
) -> Dict[str, Any]:
    """Assess multi-signal land-use support for annual crop rotation planning."""
    sec_a = field_profile.get("section_a_farmer_provided") or field_profile.get("section_a_farmer_inputs") or {}
    sec_b = field_profile.get("section_b_extracted_geospatial") or {}
    ds = sec_b.get("extracted_datasets") or {}
    spatial_val = sec_b.get("spatial_validation") or {}

    area_ha = _safe_float(spatial_val.get("area_ha"))
    wilaya_overlap_pct = _safe_float(spatial_val.get("wilaya_overlap_pct"))

    cf_block = (ds.get("crop_frequency") or {}).get("crop_frequency_2021_2025") or {}
    cf_val = _safe_float(cf_block.get("value"))
    cf_status = str(cf_block.get("quality_status") or "UNAVAILABLE")
    cf_stats = cf_block.get("stats") if isinstance(cf_block.get("stats"), dict) else {}
    share_ge_05 = _safe_float(cf_stats.get("cropland_share_ge_05_pct"))
    cf_valid_px = cf_block.get("valid_pixel_count")
    cf_cov_pct = _safe_float(cf_block.get("polygon_coverage_pct"))

    sg_clay = (ds.get("soilgrids_v6") or {}).get("clay_0_30cm") or {}
    sg_clay_status = str(sg_clay.get("quality_status") or "UNAVAILABLE")
    sg_clay_cov = _safe_float(sg_clay.get("polygon_coverage_pct"))
    sg_clay_px = sg_clay.get("valid_pixel_count")

    s2_ndvi_block = (ds.get("sentinel2") or {}).get("s2_2024_03_ndvi_10m") or {}
    s2_ndvi = _safe_float(s2_ndvi_block.get("value"))
    modis_spring = _safe_float(((ds.get("modis") or {}).get("modis_ndvi_spring_2016_2025_mean") or {}).get("value"))
    modis_winter = _safe_float(((ds.get("modis") or {}).get("modis_ndvi_winter_2016_2025_mean") or {}).get("value"))

    farmer_active_crop = _farmer_reported_active_crops(field_profile)
    # 10m pixel = 0.01 ha; SoilGrids 250m pixel = 6.25 ha
    s2_px_area_ratio = round(0.01 / area_ha, 4) if area_ha and area_ha > 0 else None
    sg_px_area_ratio = round(6.25 / area_ha, 4) if area_ha and area_ha > 0 else None

    sg_present_locally = sg_clay_status not in {"UNAVAILABLE_NOT_INTEGRATED", "TEMPORAL_GUARD_EXCLUDED"}
    sg_low_or_masked = sg_present_locally and (
        sg_clay_status == "UNAVAILABLE_MASKED_PIXEL"
        or (sg_clay_cov is not None and sg_clay_cov < thresholds.low_soilgrids_cov_pct)
    )

    partial_wilaya = wilaya_overlap_pct is not None and wilaya_overlap_pct < 99.0
    explanations: List[str] = []

    # 1. Unavailable / Masked / Temporally Blocked Crop Frequency
    if cf_val is None or cf_status in _UNAVAILABLE_QUALITY or (cf_valid_px is not None and int(cf_valid_px) == 0):
        status = LAND_USE_DATA_UNAVAILABLE
        confidence = "UNKNOWN"
        explanations.append(
            f"ESA 10m crop_frequency_2021_2025 is unavailable ({cf_status}); annual cropland use cannot be remotely verified."
        )
        provisional = False
        requires_verification = True
        gate_reason = "Crop frequency evidence unavailable; field arable status must be verified locally."

    else:
        has_high_ndvi = (s2_ndvi is not None and s2_ndvi >= thresholds.high_veg_ndvi) or (
            modis_spring is not None and modis_spring >= thresholds.high_veg_ndvi
        )
        has_low_ndvi = (s2_ndvi is not None and s2_ndvi < thresholds.low_veg_ndvi) and (
            modis_spring is None or modis_spring < thresholds.low_veg_ndvi
        )
        very_low_cf = (
            cf_val < thresholds.very_low_crop_freq
            and (share_ge_05 is None or share_ge_05 < thresholds.very_low_share_ge_05_pct)
        )
        strong_cf = (
            cf_val >= thresholds.supported_min_crop_freq
            or (share_ge_05 is not None and share_ge_05 >= thresholds.supported_min_share_ge_05_pct)
        )

        if very_low_cf:
            explanations.append(
                f"10m crop_frequency_2021_2025={cf_val:.4f} (share>=0.5: {share_ge_05 if share_ge_05 is not None else 'n/a'}%) "
                f"across {cf_valid_px} valid pixels ({cf_cov_pct}% polygon coverage) indicates near-zero detected annual cropland in 2021-2025."
            )
            if sg_low_or_masked:
                explanations.append(
                    f"SoilGrids 250m covers only {sg_clay_cov}% ({sg_clay_px} valid px; status={sg_clay_status}), "
                    "consistent with SoilGrids built-up/urban or non-soil surface masking inside the polygon."
                )
            if has_low_ndvi:
                explanations.append(
                    f"Low vegetation signature (Sentinel-2 Mar 2024 NDVI={s2_ndvi}, MODIS spring NDVI={modis_spring}) "
                    "further aligns with bare, built-up, fallow, or non-vegetated ground rather than active winter cereal/pulse cultivation."
                )
            if partial_wilaya:
                explanations.append(
                    f"Polygon only partially overlaps Guelma Wilaya mask ({wilaya_overlap_pct}%), depressing Wilaya-clipped cropland coverage."
                )

            if farmer_active_crop or has_high_ndvi:
                status = LAND_USE_CONFLICTING_EVIDENCE
                confidence = "VERY_LOW"
                if farmer_active_crop:
                    explanations.append(
                        "CONFLICT: Farmer reported recent annual crop history on this polygon, whereas 2021-2025 remote sensing "
                        "shows near-zero annual cropland frequency (possible boundary/coordinate offset, urban fringe overlap, or recent conversion)."
                    )
                if has_high_ndvi:
                    explanations.append(
                        "CONFLICT: Green vegetation NDVI is elevated despite near-zero annual cropland frequency "
                        "(possible permanent orchard/olive canopy, pasture, or unmapped garden parcel)."
                    )
                provisional = True
                requires_verification = True
                gate_reason = (
                    "Conflicting land-use signals: active cropping or high vegetation claimed alongside near-zero 2021-2025 cropland "
                    "frequency and/or masked soil data. Annual crop rotation ranking is exploratory only until parcel boundary and arable status are verified."
                )
            else:
                status = LAND_USE_UNVERIFIED
                confidence = "VERY_LOW"
                explanations.append(
                    "All available remote-sensing signals fail to verify active annual cropland (possible urban/peri-urban ground, "
                    "permanent trees, non-arable terrain, or misplaced polygon boundary)."
                )
                provisional = True
                requires_verification = True
                gate_reason = (
                    "Unverified cropland status (crop_frequency < 0.05): results are provisional and exploratory only until on-site arable land verification."
                )

        elif not strong_cf:
            explanations.append(
                f"10m crop_frequency_2021_2025={cf_val:.4f} (share>=0.5: {share_ge_05 if share_ge_05 is not None else 'n/a'}%) "
                "shows intermittent, mosaic, tree-mixed, or low-frequency annual cropping."
            )
            if sg_low_or_masked and not partial_wilaya:
                explanations.append(
                    f"SoilGrids 250m coverage is low ({sg_clay_cov}%), indicating possible partial urban/built-up or water masking."
                )
            if partial_wilaya:
                explanations.append(
                    f"Polygon overlaps Guelma Wilaya by {wilaya_overlap_pct}%; cross-border edge effects reduce raster coverage."
                )

            if sg_low_or_masked and farmer_active_crop and not partial_wilaya:
                status = LAND_USE_CONFLICTING_EVIDENCE
                confidence = "LOW"
                provisional = True
                requires_verification = True
                gate_reason = (
                    "Partial cropland signal paired with heavy SoilGrids masking inside the parcel; verify true arable boundary on site."
                )
            else:
                status = LAND_USE_LOW_EVIDENCE
                confidence = "LOW"
                provisional = False
                requires_verification = True
                gate_reason = (
                    "Low/intermittent cropland evidence (0.05 <= crop_frequency < 0.40); confirm arable cultivation vs permanent orchard/fallow locally."
                )

        else:
            # strong_cf (>= 0.40 or share>=0.5 >= 40%)
            if sg_low_or_masked and not partial_wilaya:
                status = LAND_USE_CONFLICTING_EVIDENCE
                confidence = "LOW"
                explanations.append(
                    f"High annual crop frequency ({cf_val:.4f}) conflicts with severe SoilGrids masking (coverage={sg_clay_cov}%); inspect parcel boundary."
                )
                provisional = True
                requires_verification = True
                gate_reason = "Strong crop frequency conflicts with SoilGrids surface masking; verify polygon boundary."
            else:
                status = LAND_USE_SUPPORTED
                confidence = "MODERATE_TO_HIGH" if (s2_ndvi is None or s2_ndvi >= thresholds.low_veg_ndvi) else "MODERATE"
                explanations.append(
                    f"2021-2025 annual crop_frequency={cf_val:.4f} (share>=0.5: {share_ge_05 if share_ge_05 is not None else 'n/a'}%) "
                    "supports active annual arable land use over the polygon."
                )
                if has_low_ndvi:
                    explanations.append(
                        f"Note: March 2024 Sentinel-2 NDVI={s2_ndvi} was low (possibly bare spring tillage, fallow rotation year, or late sowing)."
                    )
                provisional = False
                requires_verification = False
                gate_reason = None

    if area_ha is not None and area_ha < thresholds.small_parcel_coarse_ha_threshold:
        explanations.append(
            f"Scale note: Parcel area ({area_ha} ha) is smaller than one 250m SoilGrids cell (6.25 ha; pixel/parcel ratio={sg_px_area_ratio}); "
            "250m soil and 11-55km climate layers represent surrounding landscape averages rather than intra-parcel heterogeneity."
        )

    return {
        "status": status,
        "is_provisional": provisional,
        "requires_local_verification": requires_verification,
        "confidence": confidence,
        "crop_frequency_mean": cf_val,
        "cropland_share_ge_05_pct": share_ge_05,
        "crop_frequency_valid_pixels": int(cf_valid_px) if cf_valid_px is not None else None,
        "crop_frequency_coverage_pct": cf_cov_pct,
        "soilgrids_clay_coverage_pct": sg_clay_cov,
        "soilgrids_valid_pixels": int(sg_clay_px) if sg_clay_px is not None else None,
        "soilgrids_urban_masked_suspected": bool(sg_low_or_masked and not partial_wilaya),
        "s2_ndvi_spring_2024": s2_ndvi,
        "modis_ndvi_spring_mean": modis_spring,
        "modis_ndvi_winter_mean": modis_winter,
        "wilaya_overlap_pct": wilaya_overlap_pct,
        "polygon_area_ha": area_ha,
        "s2_pixel_to_polygon_area_ratio": s2_px_area_ratio,
        "soilgrids_pixel_to_polygon_area_ratio": sg_px_area_ratio,
        "farmer_reported_recent_cropping": farmer_active_crop,
        "explanations": explanations,
        "provisional_gating_reason": gate_reason,
    }
