"""Unit tests for M7 INPUT-01..03, canonical hashing (IMPL-003), and zero-PII snapshots."""

from __future__ import annotations

import copy
import gzip
import json
import uuid
from decimal import Decimal
from typing import Any

import pytest

from app.core.errors import ErrorCode, FieldShiftError
from app.ml_client.base import validate_contract_def
from app.models.farm import Farm
from app.models.field import Field, FieldCropHistory
from app.schemas.analysis import AnalysisSubmitRequest
from app.schemas.common import Season
from app.services.analysis_input import (
    AssembledAnalysisField,
    FieldProjectionData,
    aggregate_field_warnings,
    build_farm_analysis_input,
    compress_analysis_snapshot,
    compute_analysis_hashes,
    validate_input_rules,
    validate_unique_field_ids,
)


def _sample_farm() -> Farm:
    return Farm(
        id=42,
        user_id=7,
        farm_name="Ferme Guelma Unit",
        country="Algeria",
        region="Guelma",
        commune="Bouchegouf",
    )


def _sample_field(
    *,
    ext_id: str = "F1",
    latitude: float = 36.4621,
    longitude: float = 7.4312,
    outside_mvp: bool = False,
    unverified: bool = True,
) -> AssembledAnalysisField:
    field_obj = Field(
        id=101 if ext_id == "F1" else 102,
        farm_id=42,
        external_field_id=ext_id,
        field_name=f"Parcel {ext_id}",
        is_unverified_demo_parcel=unverified,
        area_hectares=Decimal("12.5000"),
        elevation_m=Decimal("245.50"),
        soil_type="loamy",
        soil_source="farmer",
        soil_ph=Decimal("7.15"),
        organic_matter_percent=Decimal("1.85"),
        soil_test_date=None,
        water_availability="moderate",
        water_source="well",
        water_source_other=None,
        irrigation_system="drip",
    )
    proj = FieldProjectionData(
        field=field_obj,
        latitude=latitude,
        longitude=longitude,
        boundary=None,
        outside_mvp_coverage=outside_mvp,
    )
    ch1 = FieldCropHistory(
        id=1,
        field_id=int(field_obj.id),
        season="autumn",
        year=2025,
        planting_month=11,
        catalog_version="2026.11",
        crop_id="durum_wheat",
        crop_name_raw="Durum Wheat",
        yield_tons_per_hectare=Decimal("3.40"),
        notes="PRIVATE PII FARMER PHONE +213555999 DO NOT LEAK",
    )
    ch2 = FieldCropHistory(
        id=2,
        field_id=int(field_obj.id),
        season="autumn",
        year=2024,
        planting_month=11,
        catalog_version="2026.11",
        crop_id="barley",
        crop_name_raw="Barley",
        yield_tons_per_hectare=Decimal("2.90"),
        notes="SECRET INTERNAL NOTE",
    )
    return AssembledAnalysisField(projection=proj, crop_history=(ch1, ch2))


def _sample_submit_payload(**overrides: Any) -> AnalysisSubmitRequest:
    base: dict[str, Any] = {
        "farm_id": "farm_42",
        "language": "en",
        "planning": {
            "start_season": "spring",
            "start_year": 2027,
            "horizon_seasons": 4,
            "cycle_mode": "annual_rotation",
            "planting_month": 3,
            "scenario_overrides": {"temp_delta_c": 0.0, "precip_pct_delta": 0.0},
        },
        "priorities": {
            "weights": {
                "water_saving": 30,
                "soil_improvement": 25,
                "income": 25,
                "risk_reduction": 10,
                "forage_value": 10,
            },
            "market_preference": "mixed",
            "target_crop_ids": ["chickpea", "barley"],
            "excluded_crop_ids": ["tomato"],
            "equipment_constraints": ["Limited NPK fertilizer"],
        },
        "field_ids": ["F1"],
    }
    base.update(overrides)
    return AnalysisSubmitRequest.model_validate(base)


def test_input_01_weights_sum_must_equal_100() -> None:
    field = _sample_field()
    valid_payload = _sample_submit_payload()
    validate_input_rules(valid_payload, [field.projection])

    bad_payload = _sample_submit_payload(
        priorities={
            "weights": {
                "water_saving": 30,
                "soil_improvement": 25,
                "income": 25,
                "risk_reduction": 10,
                "forage_value": 9,
            },
            "market_preference": "mixed",
            "target_crop_ids": [],
            "excluded_crop_ids": [],
        }
    )
    with pytest.raises(FieldShiftError) as exc_info:
        validate_input_rules(bad_payload, [field.projection])
    assert exc_info.value.code == ErrorCode.INVALID_INPUT
    assert exc_info.value.details[0]["reason"] == "weights_sum_not_100"


def test_input_02_target_and_excluded_crops_must_be_disjoint() -> None:
    field = _sample_field()
    bad_payload = _sample_submit_payload(
        priorities={
            "weights": {
                "water_saving": 20,
                "soil_improvement": 20,
                "income": 20,
                "risk_reduction": 20,
                "forage_value": 20,
            },
            "market_preference": "local_market",
            "target_crop_ids": ["chickpea", "barley"],
            "excluded_crop_ids": ["barley"],
        }
    )
    with pytest.raises(FieldShiftError) as exc_info:
        validate_input_rules(bad_payload, [field.projection])
    assert exc_info.value.code == ErrorCode.INVALID_INPUT
    assert exc_info.value.details[0]["crops"] == ["barley"]


@pytest.mark.parametrize(
    ("latitude", "season", "month", "should_pass"),
    [
        (36.5, Season.WINTER, 12, True),
        (0.0, Season.WINTER, 1, True),
        (36.5, Season.SPRING, 5, True),
        (36.5, Season.SUMMER, 7, True),
        (36.5, Season.AUTUMN, 10, True),
        (36.5, Season.SPRING, 6, False),
        (36.5, Season.WINTER, 3, False),
        (-33.9, Season.WINTER, 7, True),
        (-33.9, Season.SPRING, 10, True),
        (-33.9, Season.SUMMER, 1, True),
        (-33.9, Season.AUTUMN, 4, True),
        (-33.9, Season.SPRING, 3, False),
        (36.5, Season.AUTUMN, None, True),
    ],
)
def test_input_03_hemisphere_season_planting_month_matrix(
    latitude: float,
    season: Season,
    month: int | None,
    should_pass: bool,
) -> None:
    field = _sample_field(latitude=latitude)
    payload = _sample_submit_payload(
        planning={
            "start_season": season.value,
            "start_year": 2027,
            "horizon_seasons": 4,
            "cycle_mode": "annual_rotation",
            "planting_month": month,
        }
    )
    if should_pass:
        validate_input_rules(payload, [field.projection])
    else:
        with pytest.raises(FieldShiftError) as exc_info:
            validate_input_rules(payload, [field.projection])
        assert exc_info.value.code == ErrorCode.INVALID_INPUT
        assert exc_info.value.details[0]["reason"] == "incompatible_season_planting_month"


def test_duplicate_field_ids_rejected() -> None:
    with pytest.raises(FieldShiftError) as exc_info:
        validate_unique_field_ids(["F1", "F2", "F1"])
    assert exc_info.value.code == ErrorCode.INVALID_INPUT
    assert exc_info.value.details[0]["reason"] == "duplicate_field_id"


def test_equipment_constraints_optional_nullable_and_canonical_equivalence_impl_022() -> None:
    farm = _sample_farm()
    field = _sample_field()

    payload_omitted = AnalysisSubmitRequest.model_validate(
        {
            "farm_id": "farm_42",
            "language": "en",
            "planning": {"start_season": "spring", "start_year": 2027, "horizon_seasons": 4},
            "priorities": {
                "weights": {
                    "water_saving": 30,
                    "soil_improvement": 25,
                    "income": 25,
                    "risk_reduction": 10,
                    "forage_value": 10,
                },
                "market_preference": "mixed",
                "target_crop_ids": ["chickpea"],
                "excluded_crop_ids": [],
            },
            "field_ids": ["F1"],
        }
    )
    payload_null = copy.deepcopy(payload_omitted.model_dump())
    payload_null["priorities"]["equipment_constraints"] = None
    dto_null = AnalysisSubmitRequest.model_validate(payload_null)

    assert payload_omitted.priorities.equipment_constraints == []
    assert dto_null.priorities.equipment_constraints == []

    inp1 = build_farm_analysis_input(
        request_id=uuid.uuid4(),
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        farm=farm,
        payload=payload_omitted,
        fields=[field],
    )
    inp2 = build_farm_analysis_input(
        request_id=uuid.uuid4(),
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        farm=farm,
        payload=dto_null,
        fields=[field],
    )
    assert compute_analysis_hashes(inp1) == compute_analysis_hashes(inp2)
    assert not validate_contract_def(inp1, "FarmAnalysisInput")


def test_canonical_hashing_what_if_vs_full_and_zero_pii_snapshot() -> None:
    farm = _sample_farm()
    f1 = _sample_field(ext_id="F1", latitude=36.4621001, longitude=7.4312002)
    f2 = _sample_field(ext_id="F2", latitude=36.49, longitude=7.48, unverified=False)

    p1 = _sample_submit_payload(field_ids=["F1", "F2"])
    p2_reordered = AnalysisSubmitRequest.model_validate(
        {
            "farm_id": "farm_42",
            "language": "en",
            "planning": {
                "start_season": "spring",
                "start_year": 2027,
                "horizon_seasons": 4,
                "cycle_mode": "annual_rotation",
                "planting_month": 3,
                "scenario_overrides": {"temp_delta_c": -0.0, "precip_pct_delta": 0},
            },
            "priorities": {
                "weights": {
                    "water_saving": 30,
                    "soil_improvement": 25,
                    "income": 25,
                    "risk_reduction": 10,
                    "forage_value": 10,
                },
                "market_preference": "mixed",
                "target_crop_ids": ["barley", "chickpea"],
                "excluded_crop_ids": ["tomato"],
                "equipment_constraints": ["Limited NPK fertilizer"],
            },
            "field_ids": ["F2", "F1"],
        }
    )

    f1_reversed = AssembledAnalysisField(
        projection=FieldProjectionData(
            field=f1.projection.field,
            latitude=36.4621004,  # within 6-decimal rounding (both round to 36.462100)
            longitude=7.4312001,
            boundary=None,
            outside_mvp_coverage=False,
        ),
        crop_history=(f1.crop_history[1], f1.crop_history[0]),
    )

    inp1 = build_farm_analysis_input(
        request_id=uuid.uuid4(),
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        farm=farm,
        payload=p1,
        fields=[f1, f2],
    )
    inp2 = build_farm_analysis_input(
        request_id=uuid.uuid4(),
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        farm=farm,
        payload=p2_reordered,
        fields=[f2, f1_reversed],
    )
    h1 = compute_analysis_hashes(inp1)
    h2 = compute_analysis_hashes(inp2)
    assert h1 == h2

    # What-If tweak (different weights & climate overrides): input_hash SAME, full_input_hash DIFF.
    p_what_if = _sample_submit_payload(
        field_ids=["F1", "F2"],
        planning={
            "start_season": "spring",
            "start_year": 2027,
            "horizon_seasons": 4,
            "cycle_mode": "annual_rotation",
            "planting_month": 3,
            "scenario_overrides": {"temp_delta_c": 2.5, "precip_pct_delta": -20.0},
        },
        priorities={
            "weights": {
                "water_saving": 60,
                "soil_improvement": 10,
                "income": 10,
                "risk_reduction": 10,
                "forage_value": 10,
            },
            "market_preference": "mixed",
            "target_crop_ids": ["chickpea", "barley"],
            "excluded_crop_ids": ["tomato"],
            "equipment_constraints": ["Limited NPK fertilizer"],
        },
    )
    inp_what_if = build_farm_analysis_input(
        request_id=uuid.uuid4(),
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        farm=farm,
        payload=p_what_if,
        fields=[f1, f2],
    )
    h_what_if = compute_analysis_hashes(inp_what_if)
    assert h_what_if[0] == h1[0]
    assert h_what_if[1] != h1[1]

    # Compress & check zero-PII stripping + schema conformance.
    gz = compress_analysis_snapshot(inp1)
    raw_text = gzip.decompress(gz).decode("utf-8")
    assert "PRIVATE PII" not in raw_text
    assert "notes" not in raw_text
    assert "user_id" not in raw_text
    parsed = json.loads(raw_text)
    assert not validate_contract_def(parsed, "FarmAnalysisInput")


def test_aggregate_field_warnings_combines_fields_per_code() -> None:
    f1 = _sample_field(ext_id="F1", outside_mvp=True, unverified=True).projection
    f2 = _sample_field(ext_id="F2", outside_mvp=False, unverified=True).projection
    f3 = _sample_field(ext_id="F3", outside_mvp=True, unverified=False).projection

    notices = aggregate_field_warnings([f1, f2, f3], include_outside_coverage=True)
    by_code = {n.code.value: n.fields for n in notices}
    assert by_code["MVP_OUTSIDE_COVERAGE"] == ["F1", "F3"]
    assert by_code["DEMO_PARCEL_UNVERIFIED"] == ["F1", "F2"]
