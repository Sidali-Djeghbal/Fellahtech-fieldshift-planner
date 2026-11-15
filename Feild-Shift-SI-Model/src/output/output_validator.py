"""JSON Schema Draft 2020-12 and Semantic Consistency Validator (Phase J)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agronomic.data_adequacy import BLOCKING_ADEQUACY_STATUSES

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "final_recommendation_output.schema.json"

INFEASIBLE_STATUSES = {"UNVERIFIED_HARD_UNKNOWN", "INFEASIBLE_HARD_CONSTRAINT", "INFEASIBLE_CONSTRAINT"}
ELIGIBLE_STATUSES = {"FEASIBLE_PASS", "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS"}


class OutputValidationError(ValueError):
    """Raised when a Phase J final recommendation payload fails schema or semantic validation."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__(f"Final recommendation output validation failed with {len(errors)} error(s): " + "; ".join(errors[:5]))


def load_output_schema(schema_path: Optional[Path] = None) -> Dict[str, Any]:
    path = Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def _matches_json_type(val: Any, expected: str) -> bool:
    if expected == "null":
        return val is None
    if expected == "boolean":
        return isinstance(val, bool)
    if expected == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if expected == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool) and not math.isnan(val) and not math.isinf(val)
    if expected == "string":
        return isinstance(val, str)
    if expected == "array":
        return isinstance(val, list)
    if expected == "object":
        return isinstance(val, dict)
    return False


def _resolve_ref(ref: str, root_schema: Dict[str, Any]) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported external schema $ref: {ref}")
    cur: Any = root_schema
    for part in ref[2:].split("/"):
        cur = cur[part]
    return cur


def _validate_schema_node(
    instance: Any,
    schema: Dict[str, Any],
    root_schema: Dict[str, Any],
    path: str,
    errors: List[str],
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root_schema)

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = [expected_type] if isinstance(expected_type, str) else list(expected_type)
        if not any(_matches_json_type(instance, t) for t in allowed_types):
            errors.append(f"{path}: expected type {allowed_types}, got {type(instance).__name__} ({instance!r}).")
            return

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must equal const {schema['const']!r}, got {instance!r}.")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in allowed enum {schema['enum']}.")

    if isinstance(instance, str) and "minLength" in schema and len(instance) < schema["minLength"]:
        errors.append(f"{path}: string length {len(instance)} < minLength {schema['minLength']}.")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: value {instance} < minimum {schema['minimum']}.")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: value {instance} > maximum {schema['maximum']}.")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: array length {len(instance)} < minItems {schema['minItems']}.")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: array length {len(instance)} > maxItems {schema['maxItems']}.")
        if "items" in schema:
            for idx, item in enumerate(instance):
                _validate_schema_node(item, schema["items"], root_schema, f"{path}[{idx}]", errors)

    if isinstance(instance, dict):
        for req_key in schema.get("required", []):
            if req_key not in instance:
                errors.append(f"{path}: missing required key '{req_key}'.")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(instance.keys()) - set(props.keys())
            if extra:
                errors.append(f"{path}: unsupported additionalProperties {sorted(extra)}.")
        for key, prop_schema in props.items():
            if key in instance:
                _validate_schema_node(instance[key], prop_schema, root_schema, f"{path}.{key}", errors)


def _validate_semantics(payload: Dict[str, Any], errors: List[str]) -> None:
    """Enforce Phase J cross-field scientific, feasibility, Pareto, rank, and provenance invariants."""
    field_plans = payload.get("field_plans", [])
    if len(field_plans) != 1:
        errors.append(f"field_plans must contain exactly 1 field entry (one-field-per-request), got {len(field_plans)}.")
        return

    fp = field_plans[0]
    strats = fp.get("strategies", [])
    by_sid = {s["strategy_id"]: s for s in strats}
    if len(by_sid) != len(strats):
        errors.append("Duplicate strategy_id detected in field_plans[0].strategies.")

    sugg_id = fp.get("suggested_strategy_id")
    rec_status = fp.get("recommendation_status")

    # 1. Suggested strategy & feasibility consistency
    if sugg_id is not None:
        if sugg_id not in by_sid:
            errors.append(f"suggested_strategy_id '{sugg_id}' does not reference any strategy in field_plans[0].strategies.")
        else:
            sugg = by_sid[sugg_id]
            if sugg["feasibility_status"] in INFEASIBLE_STATUSES:
                errors.append(f"Infeasible strategy '{sugg_id}' ({sugg['feasibility_status']}) cannot be recommended.")
            if sugg.get("rank") != 1:
                errors.append(f"suggested_strategy_id '{sugg_id}' must carry rank=1, got rank={sugg.get('rank')}.")

    # 2. Rank & Pareto consistency
    ranked_strats = [s for s in strats if s.get("rank") is not None]
    ranked_strats.sort(key=lambda s: s["rank"])
    expected_ranks = list(range(1, len(ranked_strats) + 1))
    actual_ranks = [s["rank"] for s in ranked_strats]
    if actual_ranks != expected_ranks:
        errors.append(f"Strategy ranks must be contiguous starting at 1; got {actual_ranks}.")

    prev_ws: Optional[float] = None
    for s in ranked_strats:
        if s["feasibility_status"] not in ELIGIBLE_STATUSES:
            errors.append(f"Ranked strategy '{s['strategy_id']}' carries non-eligible feasibility '{s['feasibility_status']}'.")
        if s["pareto_status"] == "EXCLUDED_INFEASIBLE":
            errors.append(f"Ranked strategy '{s['strategy_id']}' cannot carry pareto_status='EXCLUDED_INFEASIBLE'.")
        ws = s.get("weighted_score")
        if ws is None:
            errors.append(f"Ranked strategy '{s['strategy_id']}' is missing weighted_score.")
        elif prev_ws is not None and ws > prev_ws + 1e-9:
            errors.append(f"Rank order inconsistency: rank {s['rank']} score {ws} exceeds prior score {prev_ws}.")
        prev_ws = ws

    for s in strats:
        if s["feasibility_status"] in INFEASIBLE_STATUSES:
            if s.get("rank") is not None or s.get("weighted_score") is not None:
                errors.append(f"Infeasible strategy '{s['strategy_id']}' must have rank=None and weighted_score=None.")
            if s["pareto_status"] != "EXCLUDED_INFEASIBLE":
                errors.append(f"Infeasible strategy '{s['strategy_id']}' must have pareto_status='EXCLUDED_INFEASIBLE'.")

        # 3. Score / status / weight consistency (no null -> 0.0 coercion)
        for obj_id, obj_eval in s.get("scores", {}).items():
            st = obj_eval.get("status")
            val = obj_eval.get("score")
            nw = obj_eval.get("normalized_weight")
            if st in ("UNKNOWN", "NOT_APPLICABLE"):
                if val is not None:
                    errors.append(f"{s['strategy_id']}.scores.{obj_id}: status '{st}' must have score=null, got {val}.")
                if nw != 0.0:
                    errors.append(f"{s['strategy_id']}.scores.{obj_id}: inactive status '{st}' must have normalized_weight=0.0, got {nw}.")
            elif st in ("SCORED", "PARTIAL") and val is None:
                errors.append(f"{s['strategy_id']}.scores.{obj_id}: status '{st}' requires numeric score in [0, 1].")

        # 4. Evidence non-empty on strategies
        if not s.get("explanation", {}).get("evidence"):
            errors.append(f"{s['strategy_id']}: explanation.evidence must not be empty.")

    # 5. Conditional recommendation & Phase N decision gate consistency
    eligible_strats = [s for s in strats if s["feasibility_status"] in ELIGIBLE_STATUSES]
    if not eligible_strats and sugg_id is not None:
        errors.append("Zero eligible strategies exist; suggested_strategy_id must be null.")
    if rec_status == "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION":
        if any(s["feasibility_status"] == "FEASIBLE_PASS" for s in eligible_strats):
            errors.append("rec_status indicates all conditional, yet a FEASIBLE_PASS strategy exists.")

    d_gate = fp.get("decision_gate")
    if isinstance(d_gate, dict):
        d_status = d_gate.get("decision_status")
        endorsed = d_gate.get("endorsed_recommendation_id")
        allowed_decisions = {
            "FEASIBLE_PASS",
            "CONDITIONALLY_FEASIBLE",
            "REQUIRES_LOCAL_VERIFICATION",
            "EXPLORATORY_ONLY",
            "INFEASIBLE",
            "NO_RECOMMENDATION",
        }
        if d_status not in allowed_decisions:
            errors.append(f"decision_gate.decision_status '{d_status}' must be one of {sorted(allowed_decisions)}.")
        if d_status in {"EXPLORATORY_ONLY", "INFEASIBLE", "NO_RECOMMENDATION"} and endorsed is not None:
            errors.append(f"decision_gate '{d_status}' cannot carry a non-null endorsed_recommendation_id ('{endorsed}').")
        if d_status == "EXPLORATORY_ONLY" and not d_gate.get("provisional_only"):
            errors.append("decision_gate 'EXPLORATORY_ONLY' must set provisional_only=true.")
        dq_status = ((fp.get("data_quality") or {}).get("critical_data_adequacy") or {}).get("adequacy_status")
        if dq_status in BLOCKING_ADEQUACY_STATUSES:
            if endorsed is not None:
                errors.append(
                    f"critical_data_adequacy '{dq_status}' forbids non-null endorsed_recommendation_id ('{endorsed}')."
                )
            if d_status not in {"EXPLORATORY_ONLY", "INFEASIBLE", "NO_RECOMMENDATION"}:
                errors.append(
                    f"critical_data_adequacy '{dq_status}' must gate decision_status to EXPLORATORY_ONLY/INFEASIBLE/NO_RECOMMENDATION; got '{d_status}'."
                )

    # 6. Pareto references must point only to eligible strategy IDs
    ps = fp.get("pareto_summary", {})
    for sid_ref in ps.get("front_strategy_ids", []) + ps.get("dominated_strategy_ids", []):
        if sid_ref not in by_sid or by_sid[sid_ref]["feasibility_status"] in INFEASIBLE_STATUSES:
            errors.append(f"pareto_summary references missing or infeasible strategy '{sid_ref}'.")

    # 7. Active weight normalization consistency
    rm = fp.get("ranking_methodology", {})
    if ranked_strats:
        w_sum = rm.get("normalized_active_weight_sum", 0.0)
        if abs(float(w_sum) - 1.0) > 1e-4:
            errors.append(f"normalized_active_weight_sum must equal 1.0 when ranked strategies exist; got {w_sum}.")


def validate_final_recommendation(
    payload: Dict[str, Any],
    schema_path: Optional[Path] = None,
    *,
    raise_on_error: bool = True,
) -> Dict[str, Any]:
    """Validate final recommendation output for strict RFC-8259 JSON, Draft 2020-12 schema, and semantics."""
    errors: List[str] = []

    # 1. Strict JSON serializability check (forbids NaN / Infinity / non-JSON types)
    try:
        serialized = json.dumps(payload, allow_nan=False)
        parsed = json.loads(serialized)
    except (TypeError, ValueError) as exc:
        errors.append(f"Payload is not valid strict RFC-8259 JSON: {exc}")
        if raise_on_error:
            raise OutputValidationError(errors)
        return {"valid": False, "errors": errors, "schema_draft": "2020-12"}

    # 2. Structural Draft 2020-12 validation
    schema = load_output_schema(schema_path)
    _validate_schema_node(parsed, schema, schema, "$", errors)

    # Optional cross-check with external jsonschema library if available in environment
    try:
        from jsonschema import Draft202012Validator  # type: ignore

        validator = Draft202012Validator(schema)
        for err in validator.iter_errors(parsed):
            errors.append(f"jsonschema: {err.message}")
    except ImportError:
        pass

    # 3. Cross-field semantic checks
    if isinstance(parsed, dict):
        _validate_semantics(parsed, errors)

    if errors and raise_on_error:
        raise OutputValidationError(errors)

    return {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "schema_draft": "2020-12",
    }
