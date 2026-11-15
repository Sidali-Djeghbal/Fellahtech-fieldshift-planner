"""Two-stage ML output validator: Stage 1 Draft 2020-12 & ADR-6 + Stage 2 SEM-01..07."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol, TypeGuard

import structlog

from app.core.errors import ErrorCode
from app.core.metrics import ML_UNKNOWN_FIELDS_OBSERVED_TOTAL
from app.ml_client.base import validate_contract_def

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "schema-v5.0.json"
_SUPPORTED_MAJOR_SCHEMA_VERSION_RE = re.compile(r"^5\.[0-9]+$")
_TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")

_SEASON_ORDER_RANK: dict[str, int] = {
    "winter": 0,
    "spring": 1,
    "summer": 2,
    "autumn": 3,
}

# Parameters belonging strictly to climate, satellite, or synthetic environmental datasets.
# `farmer_input` evidence citing any of these violates SEM-04 / KPI-03.
_DATASET_ONLY_PARAMS: frozenset[str] = frozenset(
    {
        "precipitation",
        "t2m",
        "t2m_max",
        "t2m_min",
        "rh2m",
        "wind_2m",
        "solar_radiation",
        "ndvi",
        "soil_moisture_surface",
        "precipitation_anomaly",
        "evaporative_stress_index",
        "groundwater_anomaly",
        "dataset_feature",
    }
)
_DATASET_ONLY_PREFIXES: tuple[str, ...] = (
    "era5_",
    "chirps_",
    "modis_",
    "nasa_power_",
    "climate_",
    "satellite_",
)

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ResultVerificationOutcome:
    """Validation result consumed by M8 basic check and M9 Stage 1 + SEM-01..07 verifier."""

    valid: bool
    result_status: Literal["ok", "partial", "invalid"]
    error_code: ErrorCode | None = None
    validation_errors: list[dict[str, Any]] = field(default_factory=list)


class ResultVerifier(Protocol):
    """Async/sync-friendly verifier contract invoked on parsed 200 OK ML responses."""

    async def __call__(
        self,
        result_payload: Mapping[str, Any],
        *,
        expected_dataset_version: str,
        input_snapshot: Mapping[str, Any],
    ) -> ResultVerificationOutcome: ...


@dataclass(frozen=True, slots=True)
class CatalogCropMeta:
    """Normalized catalog entry metadata needed for `SEM-03` and `SEM-06` checks."""

    crop_id: str
    category: str
    roles: tuple[str, ...]
    family: str = ""


@lru_cache(maxsize=1)
def _load_schema_defs() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = dict(raw.get("$defs", {}))
    root = dict(defs.get("AnalysisResult", {}))
    return root, defs


def _err(rule: str, path: str, message: str, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"rule": rule, "path": path, "message": message}
    item.update(extra)
    return item


def _coerce_catalog_crops(
    catalog_crops: (
        Mapping[str, CatalogCropMeta | tuple[str, tuple[str, ...], str] | Mapping[str, Any]]
        | None
    ),
) -> dict[str, CatalogCropMeta] | None:
    if catalog_crops is None:
        return None
    normalized: dict[str, CatalogCropMeta] = {}
    for raw_cid, entry in catalog_crops.items():
        cid = str(raw_cid)
        if isinstance(entry, CatalogCropMeta):
            normalized[cid] = entry
        elif isinstance(entry, tuple):
            category, roles, family = entry
            normalized[cid] = CatalogCropMeta(
                crop_id=cid,
                category=str(category),
                roles=tuple(str(r) for r in roles),
                family=str(family),
            )
        elif isinstance(entry, Mapping):
            normalized[cid] = CatalogCropMeta(
                crop_id=cid,
                category=str(entry.get("category", "")),
                roles=tuple(str(r) for r in entry.get("roles", ())),
                family=str(entry.get("family", "")),
            )
    return normalized


def _resolve_schema_node(node: Any, defs: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve `$ref` and merge declarative `properties` + `items` without evaluating `if`/`not`."""
    if not isinstance(node, Mapping):
        return {}
    merged: dict[str, Any] = {}
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = defs.get(ref.removeprefix("#/$defs/"))
        if isinstance(target, Mapping):
            merged.update(_resolve_schema_node(target, defs))

    props: dict[str, Any] = dict(merged.get("properties", {}))
    local_props = node.get("properties")
    if isinstance(local_props, Mapping):
        props.update(local_props)

    all_of = node.get("allOf")
    if isinstance(all_of, list):
        for branch in all_of:
            if not isinstance(branch, Mapping):
                continue
            # Conditional `if`/`then` blocks refine constraints rather than defining extra props.
            branch_resolved = _resolve_schema_node(branch, defs)
            branch_props = branch_resolved.get("properties")
            if isinstance(branch_props, Mapping):
                props.update(branch_props)

    merged.update({k: v for k, v in node.items() if k not in {"$ref", "allOf"}})
    if props:
        merged["properties"] = props
    return merged


def _collect_unknown_fields(
    instance: Any,
    schema_node: Any,
    defs: Mapping[str, Any],
    *,
    json_path: str = "$",
) -> list[tuple[str, str]]:
    """Walk payload against contract AST; flag extra keys ONLY on property-defined objects."""
    resolved = _resolve_schema_node(schema_node, defs)
    observed: list[tuple[str, str]] = []

    if isinstance(instance, Mapping):
        allowed_props = resolved.get("properties")
        # Leave arbitrary maps (e.g., `ReasonItem.params`, `comparison[]`) unflagged.
        if isinstance(allowed_props, Mapping) and allowed_props:
            for key, val in instance.items():
                key_str = str(key)
                child_path = f"{json_path}.{key_str}"
                if key_str not in allowed_props:
                    observed.append((child_path, key_str))
                else:
                    observed.extend(
                        _collect_unknown_fields(
                            val,
                            allowed_props[key_str],
                            defs,
                            json_path=child_path,
                        )
                    )
    elif isinstance(instance, list):
        items_schema = resolved.get("items")
        if isinstance(items_schema, Mapping):
            for idx, item in enumerate(instance):
                observed.extend(
                    _collect_unknown_fields(
                        item,
                        items_schema,
                        defs,
                        json_path=f"{json_path}[{idx}]",
                    )
                )

    return observed


def _extract_input_fields_map(
    input_snapshot: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    raw_fields = input_snapshot.get("fields")
    if not isinstance(raw_fields, list):
        return {}
    mapping: dict[str, Mapping[str, Any]] = {}
    for item in raw_fields:
        if isinstance(item, Mapping):
            fid = item.get("field_id")
            if isinstance(fid, str) and fid:
                mapping[fid] = item
    return mapping


def _check_sem01(
    result_payload: Mapping[str, Any],
    *,
    input_fields_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    field_plans = result_payload.get("field_plans")
    if not isinstance(field_plans, list):
        return [_err("SEM-01", "$.field_plans", "field_plans must be a non-empty array.")]

    seen_ids: set[str] = set()
    for idx, fp in enumerate(field_plans):
        path = f"$.field_plans[{idx}].field_id"
        if not isinstance(fp, Mapping):
            errors.append(_err("SEM-01", f"$.field_plans[{idx}]", "field_plan must be an object."))
            continue
        fid = fp.get("field_id")
        if not isinstance(fid, str) or not fid:
            errors.append(_err("SEM-01", path, "Missing or empty field_id."))
            continue
        if fid in seen_ids:
            errors.append(_err("SEM-01", path, f"Duplicate field_id '{fid}' in field_plans."))
            continue
        if fid not in input_fields_by_id:
            errors.append(
                _err("SEM-01", path, f"Unexpected field_id '{fid}' not present in input.")
            )
            continue
        seen_ids.add(fid)

    missing_ids = sorted(set(input_fields_by_id.keys()) - seen_ids)
    if missing_ids:
        errors.append(
            _err(
                "SEM-01",
                "$.field_plans",
                f"Missing field_plan(s) for input field_id(s): {missing_ids}.",
            )
        )
    return errors


def _check_strategy_horizon(
    strategy: Mapping[str, Any],
    *,
    base_path: str,
    horizon_seasons: int | None,
    min_start: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seasons = strategy.get("seasons")
    if not isinstance(seasons, list) or not seasons:
        return [_err("SEM-02", f"{base_path}.seasons", "Strategy must contain seasons.")]

    if horizon_seasons is not None and len(seasons) != horizon_seasons:
        errors.append(
            _err(
                "SEM-02",
                f"{base_path}.seasons",
                f"Expected {horizon_seasons} season slots, found {len(seasons)}.",
            )
        )

    orders = [slot.get("order") for slot in seasons if isinstance(slot, Mapping)]
    if orders != list(range(1, len(seasons) + 1)):
        errors.append(
            _err(
                "SEM-02",
                f"{base_path}.seasons",
                "Season orders must be sequential integers starting at 1.",
            )
        )

    prev_key: tuple[int, int] | None = None
    for s_idx, slot in enumerate(seasons):
        if not isinstance(slot, Mapping):
            errors.append(_err("SEM-02", f"{base_path}.seasons[{s_idx}]", "Invalid season entry."))
            continue
        season_name = slot.get("season")
        year_val = slot.get("year")
        if (
            not isinstance(season_name, str)
            or season_name not in _SEASON_ORDER_RANK
            or not isinstance(year_val, int)
            or isinstance(year_val, bool)
        ):
            errors.append(
                _err(
                    "SEM-02",
                    f"{base_path}.seasons[{s_idx}]",
                    "Invalid season/year chronological values.",
                )
            )
            continue

        curr_key = (year_val, _SEASON_ORDER_RANK[season_name])
        if s_idx == 0 and min_start is not None and curr_key < min_start:
            errors.append(
                _err(
                    "SEM-02",
                    f"{base_path}.seasons[0]",
                    "First season precedes planning start_season/start_year.",
                )
            )
        if prev_key is not None and curr_key <= prev_key:
            errors.append(
                _err(
                    "SEM-02",
                    f"{base_path}.seasons[{s_idx}]",
                    "Strategy seasons must progress strictly chronologically.",
                )
            )
        prev_key = curr_key
    return errors


def _check_sem02_field_plan(
    fp: Mapping[str, Any],
    *,
    fp_path: str,
    planning: Mapping[str, Any],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    status = fp.get("status")
    partial_reason = fp.get("partial_reason")
    strategies = fp.get("strategies")
    suggested_sid = fp.get("suggested_strategy_id")

    raw_horizon = planning.get("horizon_seasons")
    horizon = (
        raw_horizon
        if isinstance(raw_horizon, int) and not isinstance(raw_horizon, bool)
        else None
    )
    raw_start_season = planning.get("start_season")
    raw_start_year = planning.get("start_year")
    min_start: tuple[int, int] | None = None
    if (
        isinstance(raw_start_season, str)
        and raw_start_season in _SEASON_ORDER_RANK
        and isinstance(raw_start_year, int)
        and not isinstance(raw_start_year, bool)
    ):
        min_start = (raw_start_year, _SEASON_ORDER_RANK[raw_start_season])

    if not isinstance(strategies, list):
        return [_err("SEM-02", f"{fp_path}.strategies", "strategies must be an array.")]

    if status == "ok":
        if len(strategies) < 3:
            errors.append(
                _err(
                    "SEM-02",
                    f"{fp_path}.strategies",
                    "status='ok' requires at least 3 strategies (including baseline).",
                )
            )
        if partial_reason is not None:
            errors.append(
                _err(
                    "SEM-02",
                    f"{fp_path}.partial_reason",
                    "status='ok' requires partial_reason to be null.",
                )
            )
    elif status == "partial":
        if not isinstance(partial_reason, str) or not partial_reason.strip():
            errors.append(
                _err(
                    "SEM-02",
                    f"{fp_path}.partial_reason",
                    "status='partial' requires non-empty partial_reason.",
                )
            )

    seen_sids: set[str] = set()
    baseline_count = 0
    for s_idx, strat in enumerate(strategies):
        s_path = f"{fp_path}.strategies[{s_idx}]"
        if not isinstance(strat, Mapping):
            errors.append(_err("SEM-02", s_path, "Strategy entry must be an object."))
            continue
        sid = strat.get("strategy_id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(_err("SEM-02", f"{s_path}.strategy_id", "Empty strategy_id."))
        elif sid in seen_sids:
            errors.append(
                _err("SEM-02", f"{s_path}.strategy_id", f"Duplicate strategy_id '{sid}'.")
            )
        else:
            seen_sids.add(sid)

        if not str(strat.get("name", "")).strip():
            errors.append(_err("SEM-02", f"{s_path}.name", "Strategy name cannot be blank."))
        if not str(strat.get("description", "")).strip():
            errors.append(
                _err("SEM-02", f"{s_path}.description", "Strategy description cannot be blank.")
            )

        if strat.get("is_existing_rotation") is True:
            baseline_count += 1

        errors.extend(
            _check_strategy_horizon(
                strat,
                base_path=s_path,
                horizon_seasons=horizon,
                min_start=min_start,
            )
        )

    if status == "ok" and baseline_count != 1:
        errors.append(
            _err(
                "SEM-02",
                f"{fp_path}.strategies",
                f"Expected exactly 1 baseline (is_existing_rotation=true), found {baseline_count}.",
            )
        )
    elif baseline_count > 1:
        errors.append(
            _err(
                "SEM-02",
                f"{fp_path}.strategies",
                f"At most 1 baseline (is_existing_rotation=true) seen, found {baseline_count}.",
            )
        )

    if status == "ok":
        if not isinstance(suggested_sid, str) or suggested_sid not in seen_sids:
            errors.append(
                _err(
                    "SEM-02",
                    f"{fp_path}.suggested_strategy_id",
                    f"suggested_strategy_id '{suggested_sid}' not found in field strategies.",
                )
            )
    elif suggested_sid is not None and suggested_sid not in seen_sids:
        errors.append(
            _err(
                "SEM-02",
                f"{fp_path}.suggested_strategy_id",
                f"suggested_strategy_id '{suggested_sid}' not found in field strategies.",
            )
        )

    return errors


def _check_sem03_strategy_crops(
    strategy: Mapping[str, Any],
    *,
    base_path: str,
    catalog_crops: Mapping[str, CatalogCropMeta] | None,
    excluded_ids: set[str],
    check_exclusions: bool,
) -> list[dict[str, Any]]:
    # TODO(OQ-11): Coordinate shared ML/backend/frontend crop-role taxonomy enum updates.
    errors: list[dict[str, Any]] = []
    seasons = strategy.get("seasons")
    if not isinstance(seasons, list):
        return errors

    for idx, slot in enumerate(seasons):
        if not isinstance(slot, Mapping):
            continue
        cid = slot.get("crop_id")
        cat = slot.get("category")
        role = slot.get("role")
        slot_path = f"{base_path}.seasons[{idx}]"
        if not isinstance(cid, str) or not cid:
            errors.append(_err("SEM-03", f"{slot_path}.crop_id", "Missing crop_id in season slot."))
            continue

        if check_exclusions and cid in excluded_ids:
            errors.append(
                _err(
                    "SEM-03",
                    f"{slot_path}.crop_id",
                    f"Excluded crop_id '{cid}' cannot appear in recommended strategies.",
                )
            )

        if catalog_crops is not None:
            meta = catalog_crops.get(cid)
            if meta is None:
                errors.append(
                    _err(
                        "SEM-03",
                        f"{slot_path}.crop_id",
                        f"Crop ID '{cid}' does not exist in active crop_catalog snapshot.",
                    )
                )
                continue
            if cat != meta.category:
                errors.append(
                    _err(
                        "SEM-03",
                        f"{slot_path}.category",
                        f"Crop '{cid}' category '{cat}' mismatches catalog '{meta.category}'.",
                    )
                )
            if not isinstance(role, str) or role not in meta.roles:
                errors.append(
                    _err(
                        "SEM-03",
                        f"{slot_path}.role",
                        (
                            f"Crop '{cid}' role '{role}' not permitted by catalog roles "
                            f"{list(meta.roles)}."
                        ),
                    )
                )

    return errors


def _is_numeric_non_bool(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _resolve_expected_farmer_input(
    param: str,
    *,
    field_input: Mapping[str, Any],
) -> tuple[bool, Any]:
    """Return `(is_known_param, expected_value_or_none)` from original field snapshot."""
    raw_soil = field_input.get("soil")
    soil: Mapping[str, Any] = raw_soil if isinstance(raw_soil, Mapping) else {}
    raw_water = field_input.get("water")
    water: Mapping[str, Any] = raw_water if isinstance(raw_water, Mapping) else {}

    direct_map: dict[str, Any] = {
        "soil_ph": soil.get("soil_ph"),
        "organic_matter_percent": soil.get("organic_matter_percent"),
        "soil_type": soil.get("soil_type"),
        "water_availability": water.get("availability"),
        "elevation_m": field_input.get("elevation_m"),
    }
    if param in direct_map:
        return True, direct_map[param]

    history = field_input.get("crop_history")
    if isinstance(history, list) and param == "crop_history":
        valid_tokens: set[str] = set()
        for entry in history:
            if isinstance(entry, Mapping):
                if isinstance(entry.get("crop_id"), str) and entry["crop_id"]:
                    valid_tokens.add(entry["crop_id"].strip().lower())
                if isinstance(entry.get("crop_name_raw"), str) and entry["crop_name_raw"]:
                    valid_tokens.add(entry["crop_name_raw"].strip().lower())
        return True, (len(history), valid_tokens) if history else None

    return False, None


def _check_sem04_evidence_list(
    evidence_items: Any,
    *,
    base_path: str,
    field_input: Mapping[str, Any],
    sem04_tolerance: float,
) -> list[dict[str, Any]]:
    # TODO(OQ-3): Confirm physical/percentage rounding tolerances per farmer parameter.
    # TODO(OQ-D5): Align dataset `period` format (ISO interval/year) and derived metadata with ML.
    errors: list[dict[str, Any]] = []
    if not isinstance(evidence_items, list):
        return errors

    for idx, ev in enumerate(evidence_items):
        ev_path = f"{base_path}[{idx}]"
        if not isinstance(ev, Mapping):
            errors.append(_err("SEM-04", ev_path, "Evidence item must be an object."))
            continue

        param_raw = ev.get("parameter")
        param = str(param_raw).strip().lower() if isinstance(param_raw, str) else ""
        observed = ev.get("observed_value")
        period = ev.get("period")
        data_source = ev.get("data_source")
        derived = ev.get("derived")
        interpretation = ev.get("interpretation")

        if not isinstance(interpretation, str) or not interpretation.strip():
            errors.append(
                _err("SEM-04", f"{ev_path}.interpretation", "Evidence interpretation is blank.")
            )

        if data_source == "farmer_input":
            if param in _DATASET_ONLY_PARAMS or param.startswith(_DATASET_ONLY_PREFIXES):
                errors.append(
                    _err(
                        "SEM-04",
                        f"{ev_path}.parameter",
                        f"farmer_input evidence cannot cite climate/dataset parameter '{param}'.",
                    )
                )
                continue

            is_known, expected = _resolve_expected_farmer_input(
                param,
                field_input=field_input,
            )
            if not is_known:
                errors.append(
                    _err(
                        "SEM-04",
                        f"{ev_path}.parameter",
                        f"Unrecognized farmer_input evidence parameter '{param}'.",
                    )
                )
                continue

            if expected is None:
                errors.append(
                    _err(
                        "SEM-04",
                        f"{ev_path}.observed_value",
                        f"Fabricated farmer_input evidence: '{param}' is null/absent in input.",
                    )
                )
                continue

            if isinstance(expected, tuple):
                hist_count, valid_tokens = expected
                matches_count = _is_numeric_non_bool(observed) and int(observed) == hist_count
                matches_crop = isinstance(observed, str) and (
                    observed.strip().lower() in valid_tokens
                )
                if not (matches_count or matches_crop):
                    errors.append(
                        _err(
                            "SEM-04",
                            f"{ev_path}.observed_value",
                            (
                                f"farmer_input '{param}' value '{observed}' "
                                "not present in crop_history."
                            ),
                        )
                    )
            elif _is_numeric_non_bool(expected):
                if not _is_numeric_non_bool(observed):
                    errors.append(
                        _err(
                            "SEM-04",
                            f"{ev_path}.observed_value",
                            f"farmer_input '{param}' expects numeric observed_value.",
                        )
                    )
                elif abs(float(observed) - float(expected)) > sem04_tolerance:
                    errors.append(
                        _err(
                            "SEM-04",
                            f"{ev_path}.observed_value",
                            (
                                f"farmer_input '{param}'={observed} diverges from input {expected} "
                                f"beyond tolerance {sem04_tolerance}."
                            ),
                        )
                    )
            elif isinstance(expected, str):
                if (
                    not isinstance(observed, str)
                    or observed.strip().lower() != expected.strip().lower()
                ):
                    errors.append(
                        _err(
                            "SEM-04",
                            f"{ev_path}.observed_value",
                            (
                                f"farmer_input '{param}'='{observed}' does not match "
                                f"input '{expected}'."
                            ),
                        )
                    )

        elif data_source == "dataset":
            if not isinstance(period, str) or not period.strip():
                errors.append(
                    _err(
                        "SEM-04",
                        f"{ev_path}.period",
                        "dataset evidence must include a non-empty period.",
                    )
                )
            if derived is not True:
                errors.append(
                    _err(
                        "SEM-04",
                        f"{ev_path}.derived",
                        "dataset evidence must set derived=true.",
                    )
                )

    return errors


def _check_sem05_explanation(
    explanation: Any,
    *,
    base_path: str,
) -> list[dict[str, Any]]:
    # TODO(OQ-11): Verify reason codes & placeholders against shared ML translation table.
    errors: list[dict[str, Any]] = []
    if not isinstance(explanation, Mapping):
        return [_err("SEM-05", base_path, "Strategy explanation must be an object.")]

    benefits = explanation.get("benefits")
    seen_benefits: set[str] = set()
    if not isinstance(benefits, list) or not benefits:
        errors.append(_err("SEM-05", f"{base_path}.benefits", "Requires >= 1 benefit item."))
    else:
        for b_idx, item in enumerate(benefits):
            b_path = f"{base_path}.benefits[{b_idx}]"
            if not isinstance(item, Mapping):
                continue
            bid = str(item.get("benefit_id", "")).strip()
            if not bid or bid in seen_benefits:
                errors.append(_err("SEM-05", b_path, "benefit_id must be non-empty and unique."))
            else:
                seen_benefits.add(bid)
            if (
                not str(item.get("title", "")).strip()
                or not str(item.get("description", "")).strip()
            ):
                errors.append(
                    _err("SEM-05", b_path, "benefit title/description cannot be blank.")
                )

    risks = explanation.get("risks")
    seen_risks: set[str] = set()
    if not isinstance(risks, list) or not risks:
        errors.append(_err("SEM-05", f"{base_path}.risks", "Requires >= 1 risk item."))
    else:
        for r_idx, item in enumerate(risks):
            r_path = f"{base_path}.risks[{r_idx}]"
            if not isinstance(item, Mapping):
                continue
            rid = str(item.get("risk_id", "")).strip()
            if not rid or rid in seen_risks:
                errors.append(_err("SEM-05", r_path, "risk_id must be non-empty and unique."))
            else:
                seen_risks.add(rid)
            for key in ("title", "description", "mitigation"):
                if not str(item.get(key, "")).strip():
                    errors.append(_err("SEM-05", f"{r_path}.{key}", f"risk {key} cannot be blank."))

    reasons = explanation.get("reasons")
    seen_reason_codes: set[str] = set()
    if not isinstance(reasons, list) or not reasons:
        errors.append(_err("SEM-05", f"{base_path}.reasons", "Requires >= 1 reason item."))
    else:
        for rs_idx, item in enumerate(reasons):
            rs_path = f"{base_path}.reasons[{rs_idx}]"
            if not isinstance(item, Mapping):
                continue
            code = item.get("code")
            text = item.get("text")
            params = item.get("params")
            if not isinstance(code, str) or not code.strip():
                errors.append(_err("SEM-05", f"{rs_path}.code", "Reason code cannot be blank."))
            else:
                if code in seen_reason_codes:
                    errors.append(
                        _err("SEM-05", f"{rs_path}.code", f"Duplicate reason code '{code}'.")
                    )
                seen_reason_codes.add(code)
            if not isinstance(text, str) or not text.strip():
                errors.append(_err("SEM-05", f"{rs_path}.text", "Reason text cannot be blank."))
                continue
            if not isinstance(params, Mapping):
                errors.append(
                    _err("SEM-05", f"{rs_path}.params", "Reason params must be an object.")
                )
                continue
            unescaped = text.replace("{{", "").replace("}}", "")
            needed_keys = {m.group(1) for m in _TEMPLATE_PLACEHOLDER_RE.finditer(unescaped)}
            missing_keys = sorted(needed_keys - {str(k) for k in params.keys()})
            if missing_keys:
                errors.append(
                    _err(
                        "SEM-05",
                        f"{rs_path}.params",
                        f"Missing reason params for template placeholders: {missing_keys}.",
                    )
                )

    evidence = explanation.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(
            _err(
                "SEM-05",
                f"{base_path}.evidence",
                "Explanation must provide at least one evidence item.",
            )
        )
    return errors


def _check_sem06_requested_crops(
    fp: Mapping[str, Any],
    *,
    fp_path: str,
    target_crop_ids: list[str],
    excluded_ids: set[str],
    catalog_crops: Mapping[str, CatalogCropMeta] | None,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    strategies = fp.get("strategies")
    if not isinstance(strategies, list):
        return errors

    strategy_crop_map: dict[str, set[str]] = {}
    for strat in strategies:
        if not isinstance(strat, Mapping):
            continue
        if strat.get("is_existing_rotation") is True:
            continue
        sid = strat.get("strategy_id")
        if isinstance(sid, str) and sid:
            seasons = strat.get("seasons")
            crops = {
                str(slot["crop_id"])
                for slot in (seasons if isinstance(seasons, list) else [])
                if isinstance(slot, Mapping) and isinstance(slot.get("crop_id"), str)
            }
            strategy_crop_map[sid] = crops

    evals = fp.get("requested_crop_results")
    if not isinstance(evals, list):
        return [
            _err(
                "SEM-06",
                f"{fp_path}.requested_crop_results",
                "requested_crop_results must be an array.",
            )
        ]

    expected_unique = list(dict.fromkeys(target_crop_ids))
    seen_targets: set[str] = set()
    all_recommended_crops = (
        set().union(*strategy_crop_map.values()) if strategy_crop_map else set()
    )

    for idx, ev in enumerate(evals):
        ev_path = f"{fp_path}.requested_crop_results[{idx}]"
        if not isinstance(ev, Mapping):
            errors.append(_err("SEM-06", ev_path, "RequestedCropEvaluation must be an object."))
            continue
        tid = ev.get("requested_crop_id")
        if not isinstance(tid, str) or not tid:
            errors.append(
                _err("SEM-06", f"{ev_path}.requested_crop_id", "Missing requested_crop_id.")
            )
            continue
        if tid in seen_targets:
            errors.append(
                _err("SEM-06", f"{ev_path}.requested_crop_id", f"Duplicate target crop '{tid}'.")
            )
            continue
        seen_targets.add(tid)

        outcome = ev.get("outcome")
        inc_ids_raw = ev.get("included_in_strategy_ids")
        inc_ids = list(inc_ids_raw) if isinstance(inc_ids_raw, list) else []
        replaced_by = ev.get("replaced_by_crop_id")
        expl = ev.get("explanation")
        if not isinstance(expl, str) or not expl.strip():
            errors.append(_err("SEM-06", f"{ev_path}.explanation", "Target explanation is blank."))

        actual_containing_sids = {sid for sid, cset in strategy_crop_map.items() if tid in cset}

        if outcome == "included":
            if tid in excluded_ids:
                errors.append(
                    _err(
                        "SEM-06",
                        f"{ev_path}.outcome",
                        f"Excluded crop '{tid}' cannot have outcome='included'.",
                    )
                )
            if not inc_ids or len(inc_ids) != len(set(inc_ids)):
                errors.append(
                    _err(
                        "SEM-06",
                        f"{ev_path}.included_in_strategy_ids",
                        "outcome='included' requires non-empty unique included_in_strategy_ids.",
                    )
                )
            elif {str(sid) for sid in inc_ids} != actual_containing_sids:
                errors.append(
                    _err(
                        "SEM-06",
                        f"{ev_path}.included_in_strategy_ids",
                        (
                            f"included_in_strategy_ids {inc_ids} mismatches actual strategies "
                            f"{sorted(actual_containing_sids)} containing '{tid}'."
                        ),
                    )
                )
            if replaced_by is not None:
                errors.append(
                    _err(
                        "SEM-06",
                        f"{ev_path}.replaced_by_crop_id",
                        "outcome='included' requires replaced_by_crop_id=null.",
                    )
                )
        elif outcome in {"excluded", "replaced"}:
            if inc_ids:
                errors.append(
                    _err(
                        "SEM-06",
                        f"{ev_path}.included_in_strategy_ids",
                        f"outcome='{outcome}' requires included_in_strategy_ids=[].",
                    )
                )
            if actual_containing_sids:
                errors.append(
                    _err(
                        "SEM-06",
                        f"{ev_path}.outcome",
                        (
                            f"Crop '{tid}' marked '{outcome}' still appears in recommended "
                            f"strategies {sorted(actual_containing_sids)}."
                        ),
                    )
                )
            if outcome == "replaced":
                if not isinstance(replaced_by, str) or not replaced_by.strip():
                    errors.append(
                        _err(
                            "SEM-06",
                            f"{ev_path}.replaced_by_crop_id",
                            "outcome='replaced' requires non-empty replaced_by_crop_id.",
                        )
                    )
                else:
                    if replaced_by == tid:
                        errors.append(
                            _err(
                                "SEM-06",
                                f"{ev_path}.replaced_by_crop_id",
                                "replaced_by_crop_id cannot equal requested_crop_id.",
                            )
                        )
                    if replaced_by in excluded_ids:
                        errors.append(
                            _err(
                                "SEM-06",
                                f"{ev_path}.replaced_by_crop_id",
                                f"Replacement crop '{replaced_by}' is in excluded_crop_ids.",
                            )
                        )
                    if catalog_crops is not None and replaced_by not in catalog_crops:
                        errors.append(
                            _err(
                                "SEM-06",
                                f"{ev_path}.replaced_by_crop_id",
                                f"Replacement crop '{replaced_by}' missing from catalog.",
                            )
                        )
                    if all_recommended_crops and replaced_by not in all_recommended_crops:
                        errors.append(
                            _err(
                                "SEM-06",
                                f"{ev_path}.replaced_by_crop_id",
                                (
                                    f"Replacement crop '{replaced_by}' absent from "
                                    "recommended strategies."
                                ),
                            )
                        )
            elif replaced_by is not None:
                if replaced_by == tid or replaced_by in excluded_ids:
                    errors.append(
                        _err(
                            "SEM-06",
                            f"{ev_path}.replaced_by_crop_id",
                            f"Invalid fallback replaced_by_crop_id '{replaced_by}'.",
                        )
                    )
                elif catalog_crops is not None and replaced_by not in catalog_crops:
                    errors.append(
                        _err(
                            "SEM-06",
                            f"{ev_path}.replaced_by_crop_id",
                            f"Replacement crop '{replaced_by}' missing from catalog.",
                        )
                    )

    if seen_targets != set(expected_unique):
        missing = sorted(set(expected_unique) - seen_targets)
        extra = sorted(seen_targets - set(expected_unique))
        errors.append(
            _err(
                "SEM-06",
                f"{fp_path}.requested_crop_results",
                (
                    f"requested_crop_results mismatch vs target_crop_ids "
                    f"(missing={missing}, extra={extra})."
                ),
            )
        )

    return errors


def verify_analysis_result_sync(
    result_payload: Mapping[str, Any],
    *,
    expected_dataset_version: str,
    input_snapshot: Mapping[str, Any],
    catalog_crops: (
        Mapping[str, CatalogCropMeta | tuple[str, tuple[str, ...], str] | Mapping[str, Any]]
        | None
    ) = None,
    sem04_tolerance: float = 0.001,
) -> ResultVerificationOutcome:
    """Validate Stage 1 (`schema-v5.0.json` + ADR-6 tolerant reader) & Stage 2 (`SEM-01..07`)."""
    if not isinstance(result_payload, Mapping):
        return ResultVerificationOutcome(
            valid=False,
            result_status="invalid",
            error_code=ErrorCode.ML_INVALID_RESPONSE,
            validation_errors=[
                _err("STAGE1", "$", "ML response payload must be a JSON object."),
            ],
        )

    schema_version = result_payload.get("schema_version")
    if (
        not isinstance(schema_version, str)
        or not _SUPPORTED_MAJOR_SCHEMA_VERSION_RE.match(schema_version)
    ):
        return ResultVerificationOutcome(
            valid=False,
            result_status="invalid",
            error_code=ErrorCode.ML_INVALID_RESPONSE,
            validation_errors=[
                _err(
                    "STAGE1",
                    "$.schema_version",
                    f"Unsupported or invalid schema_version '{schema_version}'; expected '5.x'.",
                )
            ],
        )

    stage1_errors = validate_contract_def(dict(result_payload), "AnalysisResult")
    if stage1_errors:
        return ResultVerificationOutcome(
            valid=False,
            result_status="invalid",
            error_code=ErrorCode.ML_INVALID_RESPONSE,
            validation_errors=[_err("STAGE1", "$", msg) for msg in stage1_errors[:10]],
        )

    # ADR-6 tolerant reader: emit warning log & metric counter for unknown properties in 5.x.
    root_schema, schema_defs = _load_schema_defs()
    unknown_fields = _collect_unknown_fields(result_payload, root_schema, schema_defs)
    for field_path, field_name in unknown_fields:
        _logger.warning(
            "ml_tolerant_reader_unknown_field",
            path=field_path,
            field_name=field_name,
            schema_version=schema_version,
        )
        ML_UNKNOWN_FIELDS_OBSERVED_TOTAL.inc()

    # Stage 2: SEM-01 .. SEM-07
    sem_errors: list[dict[str, Any]] = []
    sem07_failed = False

    if not str(result_payload.get("overall_summary", "")).strip():
        sem_errors.append(_err("SEM-05", "$.overall_summary", "overall_summary cannot be blank."))

    actual_ds = result_payload.get("dataset_version_used")
    if actual_ds != expected_dataset_version:
        sem07_failed = True
        sem_errors.append(
            _err(
                "SEM-07",
                "$.dataset_version_used",
                (
                    f"Dataset version mismatch: expected '{expected_dataset_version}', "
                    f"got '{actual_ds}'."
                ),
            )
        )

    input_fields_by_id = _extract_input_fields_map(input_snapshot)
    sem_errors.extend(_check_sem01(result_payload, input_fields_by_id=input_fields_by_id))

    normalized_catalog = _coerce_catalog_crops(catalog_crops)
    raw_priorities = input_snapshot.get("priorities")
    priorities: Mapping[str, Any] = (
        raw_priorities if isinstance(raw_priorities, Mapping) else {}
    )
    raw_planning = input_snapshot.get("planning")
    planning: Mapping[str, Any] = (
        raw_planning if isinstance(raw_planning, Mapping) else {}
    )
    excluded_ids = {str(c) for c in priorities.get("excluded_crop_ids", [])}
    target_crop_ids = [str(c) for c in priorities.get("target_crop_ids", [])]

    field_plans = result_payload.get("field_plans", [])
    has_partial = False
    if isinstance(field_plans, list):
        for fp_idx, fp in enumerate(field_plans):
            if not isinstance(fp, Mapping):
                continue
            fp_path = f"$.field_plans[{fp_idx}]"
            if fp.get("status") == "partial":
                has_partial = True

            fid = str(fp.get("field_id", ""))
            field_input = input_fields_by_id.get(fid, {})

            sem_errors.extend(_check_sem02_field_plan(fp, fp_path=fp_path, planning=planning))

            strategies = fp.get("strategies", [])
            if isinstance(strategies, list):
                for s_idx, strat in enumerate(strategies):
                    if not isinstance(strat, Mapping):
                        continue
                    s_path = f"{fp_path}.strategies[{s_idx}]"
                    is_baseline = bool(strat.get("is_existing_rotation", False))
                    sem_errors.extend(
                        _check_sem03_strategy_crops(
                            strat,
                            base_path=s_path,
                            catalog_crops=normalized_catalog,
                            excluded_ids=excluded_ids,
                            check_exclusions=not is_baseline,
                        )
                    )
                    expl = strat.get("explanation")
                    sem_errors.extend(
                        _check_sem05_explanation(expl, base_path=f"{s_path}.explanation")
                    )
                    if isinstance(expl, Mapping):
                        sem_errors.extend(
                            _check_sem04_evidence_list(
                                expl.get("evidence"),
                                base_path=f"{s_path}.explanation.evidence",
                                field_input=field_input,
                                sem04_tolerance=sem04_tolerance,
                            )
                        )

            sem_errors.extend(
                _check_sem06_requested_crops(
                    fp,
                    fp_path=fp_path,
                    target_crop_ids=target_crop_ids,
                    excluded_ids=excluded_ids,
                    catalog_crops=normalized_catalog,
                )
            )
            req_evals = fp.get("requested_crop_results")
            if isinstance(req_evals, list):
                for r_idx, req_eval in enumerate(req_evals):
                    if isinstance(req_eval, Mapping):
                        sem_errors.extend(
                            _check_sem04_evidence_list(
                                req_eval.get("evidence"),
                                base_path=f"{fp_path}.requested_crop_results[{r_idx}].evidence",
                                field_input=field_input,
                                sem04_tolerance=sem04_tolerance,
                            )
                        )

    if sem_errors:
        # IMPL-007: Stage-1-valid payload failing SEM-07 surfaces DATASET_VERSION_UNAVAILABLE.
        err_code = (
            ErrorCode.DATASET_VERSION_UNAVAILABLE
            if sem07_failed
            else ErrorCode.ML_INVALID_RESPONSE
        )
        return ResultVerificationOutcome(
            valid=False,
            result_status="invalid",
            error_code=err_code,
            validation_errors=sem_errors,
        )

    final_status: Literal["ok", "partial"] = "partial" if has_partial else "ok"
    return ResultVerificationOutcome(
        valid=True,
        result_status=final_status,
        error_code=None,
        validation_errors=[],
    )


async def verify_analysis_result(
    result_payload: Mapping[str, Any],
    *,
    expected_dataset_version: str,
    input_snapshot: Mapping[str, Any],
    catalog_crops: (
        Mapping[str, CatalogCropMeta | tuple[str, tuple[str, ...], str] | Mapping[str, Any]]
        | None
    ) = None,
    sem04_tolerance: float = 0.001,
) -> ResultVerificationOutcome:
    """Async entrypoint wrapping `verify_analysis_result_sync` for worker & service callers."""
    return verify_analysis_result_sync(
        result_payload,
        expected_dataset_version=expected_dataset_version,
        input_snapshot=input_snapshot,
        catalog_crops=catalog_crops,
        sem04_tolerance=sem04_tolerance,
    )
