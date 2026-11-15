"""15-scenario Golden Suite harness (`Blueprint §1.1/4.5`, `# TODO(OQ-6)`)."""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.ml_client.base import validate_contract_def
from app.ml_client.mock_adapter import MockMLAdapter
from app.schemas.analysis import AnalysisSubmitRequest
from app.services.analysis_input import compute_analysis_hashes
from app.services.verification import verify_analysis_result

# TODO(OQ-6): Replace scaffold tolerances and threshold assertions once Agronomy Owner delivers
# the authoritative 15 agronomic truth scenarios and KPI-06 pass percentage gate.
GOLDEN_OQ6_PASS_THRESHOLD_PERCENT: int | None = None

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
_BASE_INPUT: dict[str, Any] = json.loads(
    (FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
)
_SETIF_INPUT: dict[str, Any] = json.loads(
    (FIXTURES_DIR / "fixture_9_2_input_setif.json").read_text(encoding="utf-8")
)

GOLDEN_SCENARIOS: tuple[dict[str, Any], ...] = (
    {"id": "G01_guelma_guest_baseline", "mode": "fixture_9_1", "lang": "en"},
    {"id": "G02_setif_highlands_registered", "mode": "fixture_9_2", "lang": "fr"},
    {
        "id": "G03_drought_stress_precip_minus_25",
        "mode": "clone",
        "lang": "en",
        "temp_delta": 0.5,
        "precip_delta": -25.0,
        "water_saving": 50,
        "soil_improvement": 20,
        "income": 15,
        "risk_reduction": 10,
        "forage_value": 5,
    },
    {
        "id": "G04_heatwave_scenario_plus_2c",
        "mode": "clone",
        "lang": "en",
        "temp_delta": 2.0,
        "precip_delta": -10.0,
        "water_saving": 35,
        "soil_improvement": 20,
        "income": 20,
        "risk_reduction": 20,
        "forage_value": 5,
    },
    {
        "id": "G05_legume_soil_restoration",
        "mode": "clone",
        "lang": "en",
        "target_crops": ["chickpea"],
        "water_saving": 15,
        "soil_improvement": 50,
        "income": 20,
        "risk_reduction": 10,
        "forage_value": 5,
    },
    {
        "id": "G06_forage_livestock_priority",
        "mode": "clone",
        "lang": "fr",
        "target_crops": ["vetch_forage", "barley"],
        "water_saving": 15,
        "soil_improvement": 20,
        "income": 15,
        "risk_reduction": 10,
        "forage_value": 40,
    },
    {
        "id": "G07_high_value_sunflower_income",
        "mode": "clone",
        "lang": "en",
        "market_preference": "export",
        "target_crops": ["sunflower"],
        "water_saving": 10,
        "soil_improvement": 15,
        "income": 55,
        "risk_reduction": 10,
        "forage_value": 10,
    },
    {
        "id": "G08_conservative_water_saver",
        "mode": "clone",
        "lang": "en",
        "water_saving": 55,
        "soil_improvement": 15,
        "income": 10,
        "risk_reduction": 15,
        "forage_value": 5,
    },
    {
        "id": "G09_consecutive_seasons_cycle",
        "mode": "clone",
        "lang": "en",
        "cycle_mode": "consecutive_seasons",
        "horizon_seasons": 4,
    },
    {
        "id": "G10_six_season_extended_horizon",
        "mode": "clone",
        "lang": "en",
        "horizon_seasons": 6,
        "allow_fallow": True,
    },
    {
        "id": "G11_arabic_localization_output",
        "mode": "clone",
        "lang": "ar",
    },
    {
        "id": "G12_french_localization_output",
        "mode": "clone",
        "lang": "fr",
    },
    {
        "id": "G13_equipment_fertilizer_constraints",
        "mode": "clone",
        "lang": "en",
        "equipment_constraints": ["drip_nozzles_4ha", "npk_granular_cap"],
    },
    {
        "id": "G14_excluded_crop_strict_filter",
        "mode": "clone",
        "lang": "en",
        "excluded_crops": ["sunflower"],
        "target_crops": ["durum_wheat"],
    },
    {
        "id": "G15_schema_5_1_tolerant_replay_candidate",
        "mode": "schema_5_1_tolerant",
        "lang": "en",
    },
)


def _build_scenario_input(spec: dict[str, Any]) -> dict[str, Any]:
    if spec["mode"] == "fixture_9_2":
        payload = copy.deepcopy(_SETIF_INPUT)
    else:
        payload = copy.deepcopy(_BASE_INPUT)

    payload["request_id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(spec["id"])))
    payload["language"] = spec["lang"]
    payload["planning"]["scenario_overrides"]["temp_delta_c"] = spec.get("temp_delta", 0.0)
    payload["planning"]["scenario_overrides"]["precip_pct_delta"] = spec.get("precip_delta", 0.0)
    if "cycle_mode" in spec:
        payload["planning"]["cycle_mode"] = spec["cycle_mode"]
    if "horizon_seasons" in spec:
        payload["planning"]["horizon_seasons"] = spec["horizon_seasons"]

    weights = payload["priorities"]["weights"]
    if all(
        k in spec
        for k in ("water_saving", "soil_improvement", "income", "risk_reduction", "forage_value")
    ):
        weights["water_saving"] = spec["water_saving"]
        weights["soil_improvement"] = spec["soil_improvement"]
        weights["income"] = spec["income"]
        weights["risk_reduction"] = spec["risk_reduction"]
        weights["forage_value"] = spec["forage_value"]

    if "market_preference" in spec:
        payload["priorities"]["market_preference"] = spec["market_preference"]
    if "target_crops" in spec:
        payload["priorities"]["target_crop_ids"] = spec["target_crops"]
    if "excluded_crops" in spec:
        payload["priorities"]["excluded_crop_ids"] = spec["excluded_crops"]
    if "equipment_constraints" in spec:
        payload["priorities"]["equipment_constraints"] = spec["equipment_constraints"]

    return payload


def test_golden_suite_defines_exactly_15_scenarios() -> None:
    # TODO(OQ-6): Assert concrete KPI-06 threshold once `GOLDEN_OQ6_PASS_THRESHOLD_PERCENT` is set.
    assert len(GOLDEN_SCENARIOS) == 15
    assert len({s["id"] for s in GOLDEN_SCENARIOS}) == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", GOLDEN_SCENARIOS, ids=[s["id"] for s in GOLDEN_SCENARIOS])
async def test_golden_scenario_executes_deterministic_valid_pipeline(
    scenario: dict[str, Any],
) -> None:
    payload = _build_scenario_input(scenario)
    assert validate_contract_def(payload, "FarmAnalysisInput") == []

    # Verify canonical INPUT-01 sum & AnalysisSubmitRequest contract cleanly.
    weights = payload["priorities"]["weights"]
    _submit_req = AnalysisSubmitRequest.model_validate(
        {
            "farm_id": "farm_1",
            "field_ids": [f["field_id"] for f in payload["fields"]],
            "language": payload["language"],
            "planning": payload["planning"],
            "priorities": payload["priorities"],
        }
    )
    assert sum(weights.values()) == 100

    input_hash, full_hash = compute_analysis_hashes(payload)
    assert len(input_hash) == 64
    assert len(full_hash) == 64

    adapter = MockMLAdapter()
    ml_result = await adapter.analyze(payload, idempotency_key=f"idem_{scenario['id']}")
    if scenario["mode"] == "schema_5_1_tolerant":
        ml_result["schema_version"] = "5.1"
        ml_result["future_agronomy_hint"] = {"oq6_tag": scenario["id"]}

    assert validate_contract_def(ml_result, "AnalysisResult") == []

    catalog_data = json.loads(
        (FIXTURES_DIR / "fixture_9_4_catalog.json").read_text(encoding="utf-8")
    )["crops"]
    catalog_crops = {str(c["crop_id"]): c for c in catalog_data}
    outcome = await verify_analysis_result(
        ml_result,
        expected_dataset_version=payload["dataset_version"],
        input_snapshot=payload,
        catalog_crops=catalog_crops,
        sem04_tolerance=0.001,
    )
    assert outcome.valid, (
        f"Golden scenario {scenario['id']} failed SEM gate: {outcome.validation_errors}"
    )
    assert any(
        any(bool(st.get("is_existing_rotation")) for st in fr.get("strategies", []))
        for fr in ml_result.get("field_plans", [])
    )
