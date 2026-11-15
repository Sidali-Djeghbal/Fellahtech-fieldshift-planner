"""Unit tests for M9 Stage 1 (Draft 2020-12 + ADR-6) and Stage 2 (`SEM-01..07`) validation."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from app.core.errors import ErrorCode
from app.core.metrics import ML_UNKNOWN_FIELDS_OBSERVED_TOTAL
from app.services.verification import (
    CatalogCropMeta,
    verify_analysis_result,
    verify_analysis_result_sync,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return dict(json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8")))


def _catalog_meta_from_fixture() -> dict[str, tuple[str, tuple[str, ...], str]]:
    catalog = _load_fixture("fixture_9_4_catalog.json")
    return {
        str(c["crop_id"]): (
            str(c["category"]),
            tuple(str(r) for r in c["roles"]),
            str(c["family"]),
        )
        for c in catalog["crops"]
    }


def _setif_aligned_output() -> tuple[dict[str, Any], dict[str, Any]]:
    input_data = _load_fixture("fixture_9_2_input_setif.json")
    output = _load_fixture("fixture_9_3_output.json")
    output["request_id"] = input_data["request_id"]
    output["language"] = input_data["language"]
    fp = output["field_plans"][0]
    for strat in fp["strategies"]:
        # Align season schedule to Setif start_season='autumn' 2027 and farmer water='limited'.
        strat["seasons"][0].update({"season": "autumn", "year": 2027, "planting_month": 11})
        strat["seasons"][1].update({"season": "spring", "year": 2028, "planting_month": 3})
        strat["seasons"][2].update({"season": "autumn", "year": 2028, "planting_month": 11})
        strat["seasons"][3].update({"season": "spring", "year": 2029, "planting_month": 3})
        for ev in strat["explanation"]["evidence"]:
            if (
                ev.get("data_source") == "farmer_input"
                and ev.get("parameter") == "water_availability"
            ):
                ev["observed_value"] = "limited"
    rec_sids = [
        str(s["strategy_id"])
        for s in fp["strategies"]
        if not s.get("is_existing_rotation", False)
    ]
    fp["requested_crop_results"] = [
        {
            "requested_crop_id": "durum_wheat",
            "outcome": "included",
            "included_in_strategy_ids": rec_sids,
            "replaced_by_crop_id": None,
            "explanation": "Integrated durum wheat rotation.",
            "comparison": [],
            "evidence": [],
        }
    ]
    return input_data, output


def _sample_value(metric: Any) -> float:
    return float(metric._value.get())


def test_stage1_and_sem01_07_pass_on_golden_fixtures() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    base_output = _load_fixture("fixture_9_3_output.json")
    catalog_meta = _catalog_meta_from_fixture()

    outcome = verify_analysis_result_sync(
        base_output,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert outcome.valid is True
    assert outcome.result_status == "ok"
    assert outcome.error_code is None
    assert outcome.validation_errors == []


def test_stage1_tolerant_reader_5_1_unknown_fields_and_params_exemption(
    caplog: pytest.LogCaptureFixture,
) -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    payload = _load_fixture("fixture_9_3_output.json")
    catalog_meta = _catalog_meta_from_fixture()

    payload["schema_version"] = "5.1"
    payload["future_top_level_meta"] = {"version": 2}
    payload["field_plans"][0]["strategies"][0]["future_confidence_band"] = [0.7, 0.9]
    # Freeform dicts explicitly omitted from property walking (`ReasonItem.params` & `comparison`).
    payload["field_plans"][0]["strategies"][0]["explanation"]["reasons"][0]["params"][
        "custom_extra_key"
    ] = 99
    if payload["field_plans"][0]["requested_crop_results"]:
        payload["field_plans"][0]["requested_crop_results"][0]["comparison"] = [
            {"arbitrary_comparison_metric": 12.5}
        ]

    before = _sample_value(ML_UNKNOWN_FIELDS_OBSERVED_TOTAL)
    with caplog.at_level(logging.WARNING):
        outcome = verify_analysis_result_sync(
            payload,
            expected_dataset_version=str(base_input["dataset_version"]),
            input_snapshot=base_input,
            catalog_crops=catalog_meta,
        )
    after = _sample_value(ML_UNKNOWN_FIELDS_OBSERVED_TOTAL)

    assert outcome.valid is True
    assert outcome.result_status == "ok"
    assert after - before == 2.0


def test_stage1_rejects_schema_6_0_and_non_mapping_and_wrong_root_keys() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    bad_type = verify_analysis_result_sync(
        ["not", "an", "object"],  # type: ignore[arg-type]
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert bad_type.valid is False
    assert bad_type.error_code == ErrorCode.ML_INVALID_RESPONSE

    v6 = _load_fixture("fixture_9_3_output.json")
    v6["schema_version"] = "6.0"
    v6["dataset_version_used"] = "wrong-ds"
    out_v6 = verify_analysis_result_sync(
        v6,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    # IMPL-007: Stage 1 failure prioritizes ML_INVALID_RESPONSE even if dataset also differs.
    assert out_v6.valid is False
    assert out_v6.error_code == ErrorCode.ML_INVALID_RESPONSE

    wrong_root = _load_fixture("fixture_9_3_output.json")
    wrong_root["fields"] = []
    out_root = verify_analysis_result_sync(
        wrong_root,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert out_root.valid is False
    assert out_root.error_code == ErrorCode.ML_INVALID_RESPONSE


def test_sem01_field_coverage_rejects_missing_extra_and_duplicate_fields() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    extra_id = _load_fixture("fixture_9_3_output.json")
    extra_id["field_plans"][0]["field_id"] = "F_UNKNOWN"
    res_extra = verify_analysis_result_sync(
        extra_id,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_extra.valid is False
    assert res_extra.error_code == ErrorCode.ML_INVALID_RESPONSE
    assert any(e["rule"] == "SEM-01" for e in res_extra.validation_errors)

    dup_id = _load_fixture("fixture_9_3_output.json")
    dup_id["field_plans"].append(copy.deepcopy(dup_id["field_plans"][0]))
    res_dup = verify_analysis_result_sync(
        dup_id,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_dup.valid is False
    assert any(
        e["rule"] == "SEM-01" and "Duplicate" in e["message"] for e in res_dup.validation_errors
    )

    two_fields = copy.deepcopy(base_input)
    second_field = copy.deepcopy(two_fields["fields"][0])
    second_field["field_id"] = "F2"
    two_fields["fields"].append(second_field)
    missing_f2 = _load_fixture("fixture_9_3_output.json")
    res_missing = verify_analysis_result_sync(
        missing_f2,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=two_fields,
        catalog_crops=catalog_meta,
    )
    assert res_missing.valid is False
    assert any(
        e["rule"] == "SEM-01" and "F2" in e["message"] for e in res_missing.validation_errors
    )


def test_sem02_partial_valid_and_failures_for_baseline_chronology_horizon_and_ids() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    # Valid partial result preserves result_status='partial'.
    partial_ok = _load_fixture("fixture_9_3_output.json")
    partial_ok["status"] = "partial"
    partial_ok["field_plans"][0]["status"] = "partial"
    partial_ok["field_plans"][0]["partial_reason"] = "Limited drought resistance crop options."
    partial_ok["field_plans"][0]["strategies"] = partial_ok["field_plans"][0]["strategies"][:2]
    partial_ok["field_plans"][0]["requested_crop_results"][0]["included_in_strategy_ids"] = [
        "S2_water_resilient"
    ]
    res_partial = verify_analysis_result_sync(
        partial_ok,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_partial.valid is True
    assert res_partial.result_status == "partial"

    # Multiple baselines fail Stage 1 / SEM-02.
    two_baselines = _load_fixture("fixture_9_3_output.json")
    two_baselines["field_plans"][0]["strategies"][1]["is_existing_rotation"] = True
    res_base = verify_analysis_result_sync(
        two_baselines,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_base.valid is False

    # Non-existent suggested_strategy_id fails SEM-02.
    bad_suggested = _load_fixture("fixture_9_3_output.json")
    bad_suggested["field_plans"][0]["suggested_strategy_id"] = "S99_invented"
    res_sug = verify_analysis_result_sync(
        bad_suggested,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_sug.valid is False
    assert any(
        e["rule"] == "SEM-02" and "suggested_strategy_id" in e["path"]
        for e in res_sug.validation_errors
    )

    # Non-chronological season sequence fails SEM-02.
    bad_chrono = _load_fixture("fixture_9_3_output.json")
    bad_chrono["field_plans"][0]["strategies"][0]["seasons"][1]["year"] = 2026
    res_chrono = verify_analysis_result_sync(
        bad_chrono,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_chrono.valid is False
    assert any(e["rule"] == "SEM-02" for e in res_chrono.validation_errors)

    # Wrong season count vs horizon_seasons fails SEM-02.
    bad_horizon = _load_fixture("fixture_9_3_output.json")
    bad_horizon["field_plans"][0]["strategies"][0]["seasons"].pop()
    res_horizon = verify_analysis_result_sync(
        bad_horizon,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_horizon.valid is False
    assert any(
        e["rule"] == "SEM-02" and "Expected 4 season slots" in e["message"]
        for e in res_horizon.validation_errors
    )

    # Duplicate strategy_id fails SEM-02.
    dup_sid = _load_fixture("fixture_9_3_output.json")
    dup_sid["field_plans"][0]["strategies"][2]["strategy_id"] = dup_sid["field_plans"][0][
        "strategies"
    ][1]["strategy_id"]
    res_dup_sid = verify_analysis_result_sync(
        dup_sid,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_dup_sid.valid is False
    assert any(
        e["rule"] == "SEM-02" and "Duplicate strategy_id" in e["message"]
        for e in res_dup_sid.validation_errors
    )


def test_sem03_catalog_grounding_roles_categories_and_excluded_crops() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    unknown_crop = _load_fixture("fixture_9_3_output.json")
    unknown_crop["field_plans"][0]["strategies"][0]["seasons"][0]["crop_id"] = "quinoa_invented"
    res_unknown = verify_analysis_result_sync(
        unknown_crop,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_unknown.valid is False
    assert any(
        e["rule"] == "SEM-03" and "quinoa_invented" in e["message"]
        for e in res_unknown.validation_errors
    )

    wrong_cat = _load_fixture("fixture_9_3_output.json")
    wrong_cat["field_plans"][0]["strategies"][0]["seasons"][0]["category"] = "vegetables"
    res_cat = verify_analysis_result_sync(
        wrong_cat,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_cat.valid is False
    assert any(
        e["rule"] == "SEM-03" and "category" in e["message"] for e in res_cat.validation_errors
    )

    wrong_role = _load_fixture("fixture_9_3_output.json")
    wrong_role["field_plans"][0]["strategies"][0]["seasons"][0]["role"] = "forage"
    res_role = verify_analysis_result_sync(
        wrong_role,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_role.valid is False
    assert any(e["rule"] == "SEM-03" and "role" in e["message"] for e in res_role.validation_errors)

    excl_input = copy.deepcopy(base_input)
    excl_input["priorities"]["excluded_crop_ids"] = ["vetch_forage"]
    excl_output = _load_fixture("fixture_9_3_output.json")
    res_excl = verify_analysis_result_sync(
        excl_output,
        expected_dataset_version=str(excl_input["dataset_version"]),
        input_snapshot=excl_input,
        catalog_crops=catalog_meta,
    )
    assert res_excl.valid is False
    assert any(
        e["rule"] == "SEM-03" and "Excluded crop_id 'vetch_forage'" in e["message"]
        for e in res_excl.validation_errors
    )


def test_sem04_tolerance_fabricated_farmer_inputs_and_dataset_provenance() -> None:
    setif_in, setif_out = _setif_aligned_output()
    catalog_meta = _catalog_meta_from_fixture()
    ev_list = setif_out["field_plans"][0]["strategies"][0]["explanation"]["evidence"]

    # Within SEM04_NUMERIC_TOLERANCE (input soil_ph=7.6 vs observed=7.6005).
    ev_list.append(
        {
            "parameter": "soil_ph",
            "observed_value": 7.6005,
            "unit": None,
            "period": "2026",
            "data_source": "farmer_input",
            "derived": False,
            "interpretation": "Alkaline soil pH supplied by farmer lab analysis.",
        }
    )
    res_within = verify_analysis_result_sync(
        setif_out,
        expected_dataset_version=str(setif_in["dataset_version"]),
        input_snapshot=setif_in,
        catalog_crops=catalog_meta,
        sem04_tolerance=0.001,
    )
    assert res_within.valid is True

    # Exceeding tolerance fails SEM-04.
    ev_list[-1]["observed_value"] = 7.65
    res_diverge = verify_analysis_result_sync(
        setif_out,
        expected_dataset_version=str(setif_in["dataset_version"]),
        input_snapshot=setif_in,
        catalog_crops=catalog_meta,
        sem04_tolerance=0.001,
    )
    assert res_diverge.valid is False
    assert any(
        e["rule"] == "SEM-04" and "tolerance" in e["message"]
        for e in res_diverge.validation_errors
    )

    # Null soil_ph in Guelma fixture cannot be fabricated under farmer_input (KPI-03).
    guelma_in = _load_fixture("fixture_9_1_input.json")
    guelma_fab = _load_fixture("fixture_9_3_output.json")
    guelma_fab["field_plans"][0]["strategies"][0]["explanation"]["evidence"].append(
        {
            "parameter": "soil_ph",
            "observed_value": 6.9,
            "unit": None,
            "period": "2026",
            "data_source": "farmer_input",
            "derived": False,
            "interpretation": "Assumed neutral soil pH.",
        }
    )
    res_fab = verify_analysis_result_sync(
        guelma_fab,
        expected_dataset_version=str(guelma_in["dataset_version"]),
        input_snapshot=guelma_in,
        catalog_crops=catalog_meta,
    )
    assert res_fab.valid is False
    assert any(
        e["rule"] == "SEM-04" and "Fabricated" in e["message"] for e in res_fab.validation_errors
    )

    # Climate/dataset parameter under farmer_input rejected.
    guelma_clim = _load_fixture("fixture_9_3_output.json")
    guelma_clim["field_plans"][0]["strategies"][0]["explanation"]["evidence"].append(
        {
            "parameter": "precipitation",
            "observed_value": 420.0,
            "unit": "mm",
            "period": "2025",
            "data_source": "farmer_input",
            "derived": False,
            "interpretation": "Rainfall from weather archive.",
        }
    )
    res_clim = verify_analysis_result_sync(
        guelma_clim,
        expected_dataset_version=str(guelma_in["dataset_version"]),
        input_snapshot=guelma_in,
        catalog_crops=catalog_meta,
    )
    assert res_clim.valid is False
    assert any(
        e["rule"] == "SEM-04" and "climate/dataset parameter" in e["message"]
        for e in res_clim.validation_errors
    )

    # dataset evidence missing period / derived=false rejected (OQ-D5).
    guelma_ds = _load_fixture("fixture_9_3_output.json")
    guelma_ds["field_plans"][0]["strategies"][0]["explanation"]["evidence"].append(
        {
            "parameter": "ndvi",
            "observed_value": 0.42,
            "unit": "index",
            "period": "   ",
            "data_source": "dataset",
            "derived": False,
            "interpretation": "Mean greenness index.",
        }
    )
    res_ds = verify_analysis_result_sync(
        guelma_ds,
        expected_dataset_version=str(guelma_in["dataset_version"]),
        input_snapshot=guelma_in,
        catalog_crops=catalog_meta,
    )
    assert res_ds.valid is False
    assert sum(1 for e in res_ds.validation_errors if e["rule"] == "SEM-04") >= 2

    # Unsupported data_source='model_estimate' fails Stage 1 DataSource enum.
    guelma_est = _load_fixture("fixture_9_3_output.json")
    guelma_est["field_plans"][0]["strategies"][0]["explanation"]["evidence"].append(
        {
            "parameter": "precipitation",
            "observed_value": 15,
            "unit": "% vs historical mean",
            "period": "2027",
            "data_source": "model_estimate",
            "derived": False,
            "interpretation": "Estimated precipitation deviation.",
        }
    )
    res_est = verify_analysis_result_sync(
        guelma_est,
        expected_dataset_version=str(guelma_in["dataset_version"]),
        input_snapshot=guelma_in,
        catalog_crops=catalog_meta,
    )
    assert res_est.valid is False
    assert res_est.error_code == ErrorCode.ML_INVALID_RESPONSE

    # Valid farmer_input crop_history check + invalid non-numeric, unknown & dataset-feature checks.
    setif_in2, setif_out2 = _setif_aligned_output()
    ev2 = setif_out2["field_plans"][0]["strategies"][0]["explanation"]["evidence"]
    ev2.append(
        {
            "parameter": "crop_history",
            "observed_value": "Ble dur local",
            "unit": None,
            "period": "2025",
            "data_source": "farmer_input",
            "derived": False,
            "interpretation": "Matches farmer crop history.",
        }
    )
    assert (
        verify_analysis_result_sync(
            setif_out2,
            expected_dataset_version=str(setif_in2["dataset_version"]),
            input_snapshot=setif_in2,
            catalog_crops=catalog_meta,
        ).valid
        is True
    )

    ev2.extend(
        [
            {
                "parameter": "crop_history",
                "observed_value": "invented_crop",
                "unit": None,
                "period": "2025",
                "data_source": "farmer_input",
                "derived": False,
                "interpretation": "Wrong prior crop.",
            },
            {
                "parameter": "soil_ph",
                "observed_value": "alkaline",
                "unit": None,
                "period": "2026",
                "data_source": "farmer_input",
                "derived": False,
                "interpretation": "Non-numeric pH.",
            },
            {
                "parameter": "dataset_feature",
                "observed_value": 1.2,
                "unit": "index",
                "period": "2026",
                "data_source": "farmer_input",
                "derived": False,
                "interpretation": "Improper dataset_feature tagged farmer_input.",
            },
        ]
    )
    res_extra_sem04 = verify_analysis_result_sync(
        setif_out2,
        expected_dataset_version=str(setif_in2["dataset_version"]),
        input_snapshot=setif_in2,
        catalog_crops=catalog_meta,
    )
    assert res_extra_sem04.valid is False
    assert sum(1 for e in res_extra_sem04.validation_errors if e["rule"] == "SEM-04") >= 3


def test_sem05_explanation_consistency_and_template_params() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    bad_tmpl = _load_fixture("fixture_9_3_output.json")
    bad_tmpl["field_plans"][0]["strategies"][0]["explanation"]["reasons"][0]["text"] = (
        "Needs {missing_placeholder} rotation."
    )
    res_tmpl = verify_analysis_result_sync(
        bad_tmpl,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_tmpl.valid is False
    assert any(
        e["rule"] == "SEM-05" and "missing_placeholder" in e["message"]
        for e in res_tmpl.validation_errors
    )

    bad_ev = _load_fixture("fixture_9_3_output.json")
    bad_ev["field_plans"][0]["strategies"][0]["explanation"]["evidence"] = []
    res_ev = verify_analysis_result_sync(
        bad_ev,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_ev.valid is False
    assert any(
        e["rule"] == "SEM-05" and "evidence" in e["message"] for e in res_ev.validation_errors
    )


def test_sem06_requested_crop_results_coverage_and_outcome_truth() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    # Missing target crop evaluation.
    missing_req = _load_fixture("fixture_9_3_output.json")
    missing_req["field_plans"][0]["requested_crop_results"] = []
    res_miss = verify_analysis_result_sync(
        missing_req,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_miss.valid is False
    assert any(
        e["rule"] == "SEM-06" and "chickpea" in e["message"] for e in res_miss.validation_errors
    )

    # Dishonest included_in_strategy_ids fails SEM-06.
    bad_inc = _load_fixture("fixture_9_3_output.json")
    bad_inc["field_plans"][0]["requested_crop_results"][0]["included_in_strategy_ids"] = [
        "NONEXISTENT_STRATEGY"
    ]
    res_inc = verify_analysis_result_sync(
        bad_inc,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_inc.valid is False
    assert any(
        e["rule"] == "SEM-06" and "mismatches" in e["message"] for e in res_inc.validation_errors
    )

    # Replaced target citing a catalog crop absent from recommended strategies fails SEM-06.
    bad_rep = _load_fixture("fixture_9_3_output.json")
    for strat in bad_rep["field_plans"][0]["strategies"]:
        for slot in strat["seasons"]:
            if slot["crop_id"] in {"chickpea", "vetch_forage"}:
                slot["crop_id"] = "barley"
                slot["category"] = "cereals"
                slot["role"] = "cash_crop"
    bad_rep["field_plans"][0]["requested_crop_results"][0] = {
        "requested_crop_id": "chickpea",
        "outcome": "replaced",
        "included_in_strategy_ids": [],
        "replaced_by_crop_id": "vetch_forage",
        "explanation": "Chickpea swapped.",
        "comparison": [],
        "evidence": [],
    }
    res_rep = verify_analysis_result_sync(
        bad_rep,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_rep.valid is False
    assert any(
        e["rule"] == "SEM-06" and "absent from recommended" in e["message"]
        for e in res_rep.validation_errors
    )


def test_sem07_dataset_mismatch_returns_dataset_version_unavailable() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    base_output = _load_fixture("fixture_9_3_output.json")
    catalog_meta = _catalog_meta_from_fixture()

    base_output["dataset_version_used"] = "2025.01-stale-v1"
    outcome = verify_analysis_result_sync(
        base_output,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert outcome.valid is False
    assert outcome.result_status == "invalid"
    assert outcome.error_code == ErrorCode.DATASET_VERSION_UNAVAILABLE
    assert any(e["rule"] == "SEM-07" for e in outcome.validation_errors)


@pytest.mark.asyncio
async def test_verification_edge_cases_coercion_sem05_duplicates_and_sem06_excluded() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog = _load_fixture("fixture_9_4_catalog.json")

    meta_objs = {
        str(c["crop_id"]): CatalogCropMeta(
            crop_id=str(c["crop_id"]),
            category=str(c["category"]),
            roles=tuple(str(r) for r in c["roles"]),
            family=str(c["family"]),
        )
        for c in catalog["crops"]
    }
    meta_dicts = {
        str(c["crop_id"]): {"category": c["category"], "roles": c["roles"], "family": c["family"]}
        for c in catalog["crops"]
    }
    out_ok = _load_fixture("fixture_9_3_output.json")
    for cat_arg in (meta_objs, meta_dicts, None):
        res = await verify_analysis_result(
            out_ok,
            expected_dataset_version=str(base_input["dataset_version"]),
            input_snapshot=base_input,
            catalog_crops=cat_arg,
        )
        assert res.valid is True

    # SEM-05 duplicate benefit_id, risk_id, reason code & blank strings + SEM-06 evidence checks.
    bad_expl = _load_fixture("fixture_9_3_output.json")
    bad_expl["overall_summary"] = "   "
    s0 = bad_expl["field_plans"][0]["strategies"][0]
    s0["name"] = "  "
    s0["description"] = " "
    s0["explanation"]["benefits"].append(copy.deepcopy(s0["explanation"]["benefits"][0]))
    s0["explanation"]["risks"].append(copy.deepcopy(s0["explanation"]["risks"][0]))
    s0["explanation"]["reasons"].append(copy.deepcopy(s0["explanation"]["reasons"][0]))
    s0["explanation"]["reasons"][0]["code"] = "  "
    s0["explanation"]["risks"][0]["mitigation"] = "  "
    res_expl = verify_analysis_result_sync(
        bad_expl,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=meta_objs,
    )
    assert res_expl.valid is False
    assert sum(1 for e in res_expl.validation_errors if e["rule"] == "SEM-05") >= 5

    # SEM-06 excluded target + invalid fallback & fabricated evidence inside requested_crop_results.
    excl_in = copy.deepcopy(base_input)
    excl_in["priorities"]["excluded_crop_ids"] = ["chickpea"]
    bad_excl = _load_fixture("fixture_9_3_output.json")
    for strat in bad_excl["field_plans"][0]["strategies"]:
        if not strat["is_existing_rotation"]:
            for slot in strat["seasons"]:
                if slot["crop_id"] == "chickpea":
                    slot["crop_id"] = "barley"
                    slot["category"] = "cereals"
                    slot["role"] = "cash_crop"
    bad_excl["field_plans"][0]["requested_crop_results"][0] = {
        "requested_crop_id": "chickpea",
        "outcome": "excluded",
        "included_in_strategy_ids": [],
        "replaced_by_crop_id": "chickpea",
        "explanation": "  ",
        "comparison": [],
        "evidence": [
            {
                "data_source": "farmer_input",
                "parameter": "elevation_m",
                "observed_value": 100,
                "unit": "m",
                "period": "2026",
                "derived": False,
                "interpretation": "Fabricated elevation when null.",
            }
        ],
    }
    res_excl = verify_analysis_result_sync(
        bad_excl,
        expected_dataset_version=str(excl_in["dataset_version"]),
        input_snapshot=excl_in,
        catalog_crops=meta_objs,
    )
    assert res_excl.valid is False
    assert any(e["rule"] == "SEM-06" for e in res_excl.validation_errors)
    assert any(e["rule"] == "SEM-04" for e in res_excl.validation_errors)


def test_verification_sem02_sem05_sem06_remaining_branches() -> None:
    base_input = _load_fixture("fixture_9_1_input.json")
    catalog_meta = _catalog_meta_from_fixture()

    # SEM-02: bad season orders, start before planning window, bad partial suggested_strategy_id.
    p_bad = _load_fixture("fixture_9_3_output.json")
    p_bad["status"] = "partial"
    p_bad["field_plans"][0]["status"] = "partial"
    p_bad["field_plans"][0]["partial_reason"] = "Limited options."
    p_bad["field_plans"][0]["suggested_strategy_id"] = "UNKNOWN_SUGGESTION"
    p_bad["field_plans"][0]["strategies"][0]["seasons"][0]["order"] = 2
    p_bad["field_plans"][0]["strategies"][0]["seasons"][0]["year"] = 2026
    res_p = verify_analysis_result_sync(
        p_bad,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_p.valid is False
    assert sum(1 for e in res_p.validation_errors if e["rule"] == "SEM-02") >= 3

    # SEM-04 blank interpretation + SEM-05 empty arrays & blank benefit/reason text.
    s5_bad = _load_fixture("fixture_9_3_output.json")
    e0 = s5_bad["field_plans"][0]["strategies"][0]["explanation"]
    e0["evidence"][0]["interpretation"] = "   "
    e0["benefits"][0]["title"] = "   "
    e0["reasons"][0]["text"] = "  "
    e0["risks"] = []
    res_s5 = verify_analysis_result_sync(
        s5_bad,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_s5.valid is False
    assert any(
        e["rule"] == "SEM-04" and "interpretation" in e["path"] for e in res_s5.validation_errors
    )
    assert sum(1 for e in res_s5.validation_errors if e["rule"] == "SEM-05") >= 3

    # SEM-06: replaced with self / excluded / unknown / None + included with non-null replaced_by.
    in_two = copy.deepcopy(base_input)
    in_two["priorities"]["target_crop_ids"] = ["chickpea", "barley"]
    in_two["priorities"]["excluded_crop_ids"] = ["sunflower"]
    out_s6 = _load_fixture("fixture_9_3_output.json")
    for strat in out_s6["field_plans"][0]["strategies"]:
        if not strat["is_existing_rotation"]:
            for slot in strat["seasons"]:
                if slot["crop_id"] == "sunflower":
                    slot["crop_id"] = "vetch_forage"
                    slot["category"] = "forage"
                    slot["role"] = "forage"
    out_s6["field_plans"][0]["requested_crop_results"] = [
        {
            "requested_crop_id": "chickpea",
            "outcome": "included",
            "included_in_strategy_ids": ["S2_water_resilient", "S3_income_diversified"],
            "replaced_by_crop_id": "barley",
            "explanation": "Included with bogus replaced_by.",
            "comparison": [],
            "evidence": [],
        },
        {
            "requested_crop_id": "barley",
            "outcome": "replaced",
            "included_in_strategy_ids": [],
            "replaced_by_crop_id": "sunflower",
            "explanation": "Bogus replacement with excluded sunflower.",
            "comparison": [],
            "evidence": [],
        },
    ]
    res_s6 = verify_analysis_result_sync(
        out_s6,
        expected_dataset_version=str(in_two["dataset_version"]),
        input_snapshot=in_two,
        catalog_crops=catalog_meta,
    )
    assert res_s6.valid is False
    assert sum(1 for e in res_s6.validation_errors if e["rule"] == "SEM-06") >= 3

    # SEM-06 replaced pointing to unknown crop & null replaced_by.
    out_s6_b = copy.deepcopy(out_s6)
    out_s6_b["field_plans"][0]["requested_crop_results"][0]["replaced_by_crop_id"] = None
    out_s6_b["field_plans"][0]["requested_crop_results"][1]["replaced_by_crop_id"] = "unknown_crop"
    res_s6_b = verify_analysis_result_sync(
        out_s6_b,
        expected_dataset_version=str(in_two["dataset_version"]),
        input_snapshot=in_two,
        catalog_crops=catalog_meta,
    )
    assert res_s6_b.valid is False
    assert any("missing from catalog" in e["message"] for e in res_s6_b.validation_errors)

    # Extra coverage for SEM-05 empty benefits/reasons & SEM-02 partial blank reason.
    s2_partial_blank = _load_fixture("fixture_9_3_output.json")
    s2_partial_blank["status"] = "partial"
    s2_partial_blank["field_plans"][0]["status"] = "partial"
    s2_partial_blank["field_plans"][0]["partial_reason"] = "   "
    e1 = s2_partial_blank["field_plans"][0]["strategies"][0]["explanation"]
    e1["benefits"] = []
    e1["reasons"] = []
    res_s2b = verify_analysis_result_sync(
        s2_partial_blank,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_s2b.valid is False
    assert any(
        e["rule"] == "SEM-02" and "partial_reason" in e["path"]
        for e in res_s2b.validation_errors
    )
    assert sum(1 for e in res_s2b.validation_errors if e["rule"] == "SEM-05") >= 2

    # SEM-06 outcome='replaced' with null replaced_by & excluded crop in included_ids.
    out_s6_c = copy.deepcopy(out_s6)
    out_s6_c["field_plans"][0]["requested_crop_results"][1]["replaced_by_crop_id"] = None
    in_two_c = copy.deepcopy(in_two)
    in_two_c["priorities"]["excluded_crop_ids"] = ["chickpea", "sunflower"]
    res_s6_c = verify_analysis_result_sync(
        out_s6_c,
        expected_dataset_version=str(in_two_c["dataset_version"]),
        input_snapshot=in_two_c,
        catalog_crops=catalog_meta,
    )
    assert res_s6_c.valid is False
    assert any(
        "cannot have outcome='included'" in e["message"] for e in res_s6_c.validation_errors
    )
    assert any(
        "requires non-empty replaced_by_crop_id" in e["message"]
        for e in res_s6_c.validation_errors
    )

    # Extra branch checks pushing SEM-04/05/06 coverage > 90%.
    dup_code = _load_fixture("fixture_9_3_output.json")
    reasons = dup_code["field_plans"][0]["strategies"][0]["explanation"]["reasons"]
    reasons.append(copy.deepcopy(reasons[0]))
    dup_code["field_plans"][0]["strategies"][0]["explanation"]["evidence"][0][
        "observed_value"
    ] = "abundant"
    res_dup_code = verify_analysis_result_sync(
        dup_code,
        expected_dataset_version=str(base_input["dataset_version"]),
        input_snapshot=base_input,
        catalog_crops=catalog_meta,
    )
    assert res_dup_code.valid is False
    assert any("Duplicate reason code" in e["message"] for e in res_dup_code.validation_errors)
    assert any("does not match input" in e["message"] for e in res_dup_code.validation_errors)

    # SEM-06 excluded fallback to catalog-missing crop & integer count on crop_history.
    setif_in3, setif_out3 = _setif_aligned_output()
    setif_out3["field_plans"][0]["strategies"][0]["explanation"]["evidence"].append(
        {
            "parameter": "crop_history",
            "observed_value": 1,
            "unit": None,
            "period": "2025",
            "data_source": "farmer_input",
            "derived": False,
            "interpretation": "One season recorded in farmer history.",
        }
    )
    assert (
        verify_analysis_result_sync(
            setif_out3,
            expected_dataset_version=str(setif_in3["dataset_version"]),
            input_snapshot=setif_in3,
            catalog_crops=catalog_meta,
        ).valid
        is True
    )

    in_excl_fb = copy.deepcopy(base_input)
    in_excl_fb["priorities"]["excluded_crop_ids"] = ["chickpea"]
    out_excl_fb = _load_fixture("fixture_9_3_output.json")
    for strat in out_excl_fb["field_plans"][0]["strategies"]:
        if not strat["is_existing_rotation"]:
            for slot in strat["seasons"]:
                if slot["crop_id"] == "chickpea":
                    slot["crop_id"] = "barley"
                    slot["category"] = "cereals"
                    slot["role"] = "cash_crop"
    out_excl_fb["field_plans"][0]["requested_crop_results"][0] = {
        "requested_crop_id": "chickpea",
        "outcome": "excluded",
        "included_in_strategy_ids": ["S2_water_resilient"],
        "replaced_by_crop_id": "nonexistent_crop",
        "explanation": "Excluded with bad fallback and non-empty included_ids.",
        "comparison": [],
        "evidence": [],
    }
    res_excl_fb = verify_analysis_result_sync(
        out_excl_fb,
        expected_dataset_version=str(in_excl_fb["dataset_version"]),
        input_snapshot=in_excl_fb,
        catalog_crops=catalog_meta,
    )
    assert res_excl_fb.valid is False
    assert any("missing from catalog" in e["message"] for e in res_excl_fb.validation_errors)
    assert any(
        "requires included_in_strategy_ids=[]" in e["message"]
        for e in res_excl_fb.validation_errors
    )


