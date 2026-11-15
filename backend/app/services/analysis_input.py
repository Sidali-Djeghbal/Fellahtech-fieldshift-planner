"""Pre-queue input rules (`INPUT-01..03`), zero-PII `FarmAnalysisInput` assembly, and hashing."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.errors import ErrorCode, FieldShiftError
from app.ml_client.base import validate_contract_def
from app.models.farm import Farm
from app.models.field import Field, FieldCropHistory
from app.schemas.analysis import AnalysisSubmitRequest
from app.schemas.common import (
    DEMO_PARCEL_UNVERIFIED_MESSAGE,
    MVP_OUTSIDE_COVERAGE_MESSAGE,
    Season,
    WarningCode,
    WarningNotice,
)

SCHEMA_VERSION = "5.0"

_NORTHERN_SEASON_MONTHS: dict[Season, frozenset[int]] = {
    Season.WINTER: frozenset({12, 1, 2}),
    Season.SPRING: frozenset({3, 4, 5}),
    Season.SUMMER: frozenset({6, 7, 8}),
    Season.AUTUMN: frozenset({9, 10, 11}),
}

_SOUTHERN_SEASON_MONTHS: dict[Season, frozenset[int]] = {
    Season.WINTER: frozenset({6, 7, 8}),
    Season.SPRING: frozenset({9, 10, 11}),
    Season.SUMMER: frozenset({12, 1, 2}),
    Season.AUTUMN: frozenset({3, 4, 5}),
}

_CONTINUOUS_NUMERIC_KEYS: frozenset[str] = frozenset(
    {
        "latitude",
        "longitude",
        "area_hectares",
        "elevation_m",
        "yield_tons_per_hectare",
        "soil_ph",
        "organic_matter_percent",
        "temp_delta_c",
        "precip_pct_delta",
        "coordinates",
        "bbox",
    }
)


@dataclass(frozen=True, slots=True)
class FieldProjectionData:
    """Projected PostGIS parcel row paired with its computed coordinates and coverage flag."""

    field: Field
    latitude: float
    longitude: float
    boundary: dict[str, Any] | None
    outside_mvp_coverage: bool


@dataclass(frozen=True, slots=True)
class AssembledAnalysisField:
    """Projected owned parcel row + crop history ordered for `FarmAnalysisInput`."""

    projection: FieldProjectionData
    crop_history: tuple[FieldCropHistory, ...]


def aggregate_field_warnings(
    projections: Sequence[FieldProjectionData],
    *,
    include_outside_coverage: bool = True,
) -> list[WarningNotice]:
    """Aggregate deduplicated `WarningNotice.fields[]` across selected fields (`IMPL-019`)."""
    outside_fields: list[str] = []
    unverified_fields: list[str] = []
    seen_outside: set[str] = set()
    seen_unverified: set[str] = set()

    for proj in projections:
        fid = proj.field.external_field_id
        if include_outside_coverage and proj.outside_mvp_coverage and fid not in seen_outside:
            seen_outside.add(fid)
            outside_fields.append(fid)
        if proj.field.is_unverified_demo_parcel and fid not in seen_unverified:
            seen_unverified.add(fid)
            unverified_fields.append(fid)

    notices: list[WarningNotice] = []
    if outside_fields:
        notices.append(
            WarningNotice(
                code=WarningCode.MVP_OUTSIDE_COVERAGE,
                message=MVP_OUTSIDE_COVERAGE_MESSAGE,
                fields=outside_fields,
            )
        )
    if unverified_fields:
        notices.append(
            WarningNotice(
                code=WarningCode.DEMO_PARCEL_UNVERIFIED,
                message=DEMO_PARCEL_UNVERIFIED_MESSAGE,
                fields=unverified_fields,
            )
        )
    return notices


def validate_unique_field_ids(field_ids: Sequence[str]) -> list[str]:
    """Ensure submitted `field_ids[]` contain no duplicates (`400 INVALID_INPUT`)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for fid in field_ids:
        if fid in seen:
            raise FieldShiftError(
                ErrorCode.INVALID_INPUT,
                f"Duplicate field_id '{fid}' in field_ids.",
                details=[{"field": "field_ids", "reason": "duplicate_field_id", "field_id": fid}],
            )
        seen.add(fid)
        ordered.append(fid)
    return ordered


def validate_input_rules(
    payload: AnalysisSubmitRequest,
    projections: Sequence[FieldProjectionData],
) -> None:
    """Enforce Layer-0 synchronous `INPUT-01`, `INPUT-02`, and `INPUT-03` rules."""
    weights = payload.priorities.weights
    total_weight = (
        weights.water_saving
        + weights.soil_improvement
        + weights.income
        + weights.risk_reduction
        + weights.forage_value
    )
    if total_weight != 100:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            f"Priorities weights must sum to 100 (received {total_weight}).",
            details=[
                {
                    "field": "priorities.weights",
                    "reason": "weights_sum_not_100",
                    "sum": total_weight,
                }
            ],
        )

    overlap = sorted(
        set(payload.priorities.target_crop_ids) & set(payload.priorities.excluded_crop_ids)
    )
    if overlap:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "target_crop_ids and excluded_crop_ids must be disjoint.",
            details=[
                {
                    "field": "priorities",
                    "reason": "overlapping_target_and_excluded_crops",
                    "crops": overlap,
                }
            ],
        )

    # TODO(OQ-10): Support protected/greenhouse INPUT-03 override once Agronomy Lead defines rules.
    planting_month = payload.planning.planting_month
    if planting_month is None:
        return

    start_season = payload.planning.start_season
    for proj in projections:
        if proj.latitude >= 0.0:
            hemisphere = "northern"
            allowed_months = _NORTHERN_SEASON_MONTHS[start_season]
        else:
            hemisphere = "southern"
            allowed_months = _SOUTHERN_SEASON_MONTHS[start_season]

        if planting_month not in allowed_months:
            raise FieldShiftError(
                ErrorCode.INVALID_INPUT,
                (
                    f"planting_month {planting_month} is incompatible with {start_season.value} "
                    f"in the {hemisphere} hemisphere for field '{proj.field.external_field_id}'."
                ),
                details=[
                    {
                        "field": "planning.planting_month",
                        "reason": "incompatible_season_planting_month",
                        "field_id": proj.field.external_field_id,
                        "hemisphere": hemisphere,
                        "start_season": start_season.value,
                        "planting_month": planting_month,
                        "allowed_months": sorted(allowed_months),
                    }
                ],
            )


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def build_farm_analysis_input(
    *,
    request_id: uuid.UUID,
    catalog_version: str,
    dataset_version: str,
    farm: Farm,
    payload: AnalysisSubmitRequest,
    fields: Sequence[AssembledAnalysisField],
) -> dict[str, Any]:
    """Assemble strict allowlisted zero-PII `FarmAnalysisInput` JSON (`Workflow 3`)."""
    equipment_constraints = (
        list(payload.priorities.equipment_constraints)
        if payload.priorities.equipment_constraints is not None
        else []
    )
    assembled: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": str(request_id),
        "catalog_version": catalog_version,
        "dataset_version": dataset_version,
        "language": payload.language.value,
        "farm": {
            "farm_id": f"farm_{farm.id}",
            "farm_name": farm.farm_name,
            "country": farm.country,
            "region": farm.region,
            "commune": farm.commune,
        },
        "planning": {
            "start_season": payload.planning.start_season.value,
            "start_year": payload.planning.start_year,
            "horizon_seasons": payload.planning.horizon_seasons,
            "cycle_mode": payload.planning.cycle_mode.value,
            "planting_month": payload.planning.planting_month,
            "scenario_overrides": {
                "temp_delta_c": float(payload.planning.scenario_overrides.temp_delta_c),
                "precip_pct_delta": float(payload.planning.scenario_overrides.precip_pct_delta),
            },
        },
        "priorities": {
            "weights": {
                "water_saving": payload.priorities.weights.water_saving,
                "soil_improvement": payload.priorities.weights.soil_improvement,
                "income": payload.priorities.weights.income,
                "risk_reduction": payload.priorities.weights.risk_reduction,
                "forage_value": payload.priorities.weights.forage_value,
            },
            "market_preference": payload.priorities.market_preference.value,
            "target_crop_ids": list(payload.priorities.target_crop_ids),
            "excluded_crop_ids": list(payload.priorities.excluded_crop_ids),
            "equipment_constraints": equipment_constraints,
        },
        "fields": [
            {
                "field_id": item.projection.field.external_field_id,
                "field_name": item.projection.field.field_name,
                "is_unverified_demo_parcel": bool(
                    item.projection.field.is_unverified_demo_parcel
                ),
                "location": {
                    "latitude": item.projection.latitude,
                    "longitude": item.projection.longitude,
                    "boundary": copy.deepcopy(item.projection.boundary),
                },
                "area_hectares": float(item.projection.field.area_hectares),
                "elevation_m": _opt_float(item.projection.field.elevation_m),
                "crop_history": [
                    {
                        "season": ch.season,
                        "year": ch.year,
                        "planting_month": ch.planting_month,
                        "crop_id": ch.crop_id,
                        "crop_name_raw": ch.crop_name_raw,
                        "catalog_version": ch.catalog_version,
                        "yield_tons_per_hectare": _opt_float(ch.yield_tons_per_hectare),
                    }
                    for ch in item.crop_history
                ],
                "soil": {
                    "soil_type": item.projection.field.soil_type,
                    "source": item.projection.field.soil_source,
                    "soil_ph": _opt_float(item.projection.field.soil_ph),
                    "organic_matter_percent": _opt_float(
                        item.projection.field.organic_matter_percent
                    ),
                    "soil_test_date": (
                        item.projection.field.soil_test_date.isoformat()
                        if item.projection.field.soil_test_date is not None
                        else None
                    ),
                },
                "water": {
                    "availability": item.projection.field.water_availability,
                    "source": item.projection.field.water_source,
                    "source_other": item.projection.field.water_source_other,
                    "irrigation_system": item.projection.field.irrigation_system,
                },
            }
            for item in fields
        ],
    }

    errors = validate_contract_def(assembled, "FarmAnalysisInput")
    if errors:
        raise FieldShiftError(
            ErrorCode.INTERNAL_ERROR,
            "Assembled FarmAnalysisInput payload failed schema validation.",
            details=[{"reason": "contract_validation_failed", "errors": errors[:5]}],
        )
    return assembled


def _round_float6(value: float | int | Decimal) -> float:
    rounded = round(float(value), 6)
    return 0.0 if rounded == 0.0 else rounded


def _canonicalize_value(value: Any, *, key_name: str | None = None) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (float, Decimal)):
        return _round_float6(value)
    if isinstance(value, int):
        if key_name in _CONTINUOUS_NUMERIC_KEYS:
            return _round_float6(value)
        return value
    if isinstance(value, dict):
        return {
            str(k): _canonicalize_value(v, key_name=str(k))
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(item, key_name=key_name) for item in value]
    return value


def _crop_history_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    yield_val = item.get("yield_tons_per_hectare")
    return (
        int(item["year"]),
        str(item["season"]),
        int(item["planting_month"]) if item.get("planting_month") is not None else 0,
        str(item.get("crop_id") or ""),
        str(item.get("crop_name_raw") or ""),
        str(item.get("catalog_version") or ""),
        -1.0 if yield_val is None else float(yield_val),
    )


def _canonicalize_farm_input_for_hash(
    farm_input: Mapping[str, Any],
    *,
    include_what_if_axes: bool,
) -> dict[str, Any]:
    raw_norm = _canonicalize_value(copy.deepcopy(dict(farm_input)))
    assert isinstance(raw_norm, dict)
    normalized: dict[str, Any] = raw_norm
    normalized.pop("request_id", None)

    priorities = dict(normalized["priorities"])
    priorities["target_crop_ids"] = sorted(priorities.get("target_crop_ids", []))
    priorities["excluded_crop_ids"] = sorted(priorities.get("excluded_crop_ids", []))
    priorities["equipment_constraints"] = sorted(priorities.get("equipment_constraints") or [])
    if not include_what_if_axes:
        priorities.pop("weights", None)
    normalized["priorities"] = priorities

    planning = dict(normalized["planning"])
    if not include_what_if_axes:
        planning.pop("scenario_overrides", None)
    normalized["planning"] = planning

    canonical_fields: list[dict[str, Any]] = []
    for raw_field in normalized.get("fields", []):
        field_copy = dict(raw_field)
        field_copy["crop_history"] = sorted(
            field_copy.get("crop_history", []),
            key=_crop_history_sort_key,
        )
        canonical_fields.append(field_copy)
    canonical_fields.sort(key=lambda item: str(item["field_id"]))
    normalized["fields"] = canonical_fields
    return normalized


def _sha256_canonical(obj: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_analysis_hashes(farm_input: Mapping[str, Any]) -> tuple[str, str]:
    """Return `(input_hash, full_input_hash)` using `IMPL-003` deterministic canonical JSON."""
    what_if_obj = _canonicalize_farm_input_for_hash(farm_input, include_what_if_axes=False)
    full_obj = _canonicalize_farm_input_for_hash(farm_input, include_what_if_axes=True)
    return _sha256_canonical(what_if_obj), _sha256_canonical(full_obj)


def compress_analysis_snapshot(farm_input: Mapping[str, Any]) -> bytes:
    """Serialize compact UTF-8 JSON and gzip with `mtime=0` for `input_snapshot_gz`."""
    raw_json = json.dumps(
        farm_input,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return gzip.compress(raw_json, mtime=0)
