"""Phase M unit tests: pilot governance contracts, anti-fabrication rules, and readiness checks.

All test cases construct synthetic structural fixtures strictly to validate Pydantic contracts
and safety rules in `src/pilot/models.py`; zero real farmer participants, lab records,
or completed pilot observations are represented or fabricated here.
"""

from __future__ import annotations

import csv
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.pilot import (
    ALLOWED_EXPERT_OUTCOMES,
    ExpertReviewRecord,
    FarmerPilotObservation,
    MeasuredFieldObservation,
    PilotExecutionSession,
    PilotSamplingTarget,
    compute_pilot_metrics,
    validate_sampling_plan,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_M_DOCS_DIR = REPO_ROOT / "docs" / "phaseM"


def _sample_polygon() -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [7.4200, 36.4600],
                [7.4230, 36.4600],
                [7.4230, 36.4630],
                [7.4200, 36.4630],
                [7.4200, 36.4600],
            ]
        ],
    }


def _valid_farmer_payload(**overrides) -> dict:
    payload = {
        "pilot_field_code": "SYNTH-TEST-001",
        "commune_name": "Guelma",
        "stratum": "CENTRAL_VALLEY",
        "water_regime": "rainfed",
        "field_size_band": "MEDIUM_5_TO_30HA",
        "boundary_geojson": _sample_polygon(),
        "crop_history": [{"season": "Winter", "year": 2025, "crop_name_raw": "Durum Wheat"}],
        "planting_seasons_reported": ["Winter"],
        "irrigation_availability": "unknown",
        "irrigation_method": "none",
        "previous_crop_management_notes": "Synthetic test fixture note.",
        "farmer_preferences_notes": None,
    }
    payload.update(overrides)
    return payload


def _valid_review_payload(**overrides) -> dict:
    payload = {
        "review_id": "REV-SYNTH-001",
        "pilot_field_code": "SYNTH-TEST-001",
        "analysis_id": "ANAL_0123456789abcdef",
        "expert_id": "EXP_SYNTH_01",
        "institution": "ITGC",
        "agronomic_assessment": "Synthetic structural assessment checking sequence suitability.",
        "sequence_compatibility_verdict": "ACCEPTABLE",
        "local_constraints_flagged": [],
        "review_outcome": "ACCEPTED",
        "decision_rationale": "Cereal-legume break aligns cleanly with semi-humid winter cereal rules.",
        "recommended_modifications": None,
        "disagreement_investigation_code": "NOT_APPLICABLE",
        "constraint_detection_rating": 4,
        "explanation_quality_rating": 4,
        "uncertainty_communication_clear": True,
        "agronomic_safety_pass": True,
        "approved_for_farmer_briefing": True,
        "reviewed_at_utc": "2026-11-15T10:00:00Z",
    }
    payload.update(overrides)
    return payload


class PhaseMPilotContractTests(unittest.TestCase):
    """Validate Phase M documentation integrity, contracts, safety gates, and metrics logic."""

    def test_all_required_phase_m_documentation_files_exist_and_are_substantive(self) -> None:
        required_files = [
            "pilot_protocol.md",
            "field_sampling_strategy.md",
            "ground_truth_data_dictionary.csv",
            "expert_evaluation_form.md",
            "pilot_evaluation_metrics.md",
            "pilot_risk_register.md",
            "pilot_execution_checklist.md",
            "pilot_readiness_report.md",
        ]
        for filename in required_files:
            path = PHASE_M_DOCS_DIR / filename
            self.assertTrue(path.is_file(), f"Missing required Phase M deliverable: {path}")
            content = path.read_text(encoding="utf-8")
            self.assertGreater(len(content.strip()), 200, f"Deliverable {filename} is unexpectedly brief.")

        checklist_text = (PHASE_M_DOCS_DIR / "pilot_execution_checklist.md").read_text(encoding="utf-8")
        readiness_text = (PHASE_M_DOCS_DIR / "pilot_readiness_report.md").read_text(encoding="utf-8")
        self.assertIn("PLANNED", checklist_text)
        self.assertIn("CONDITIONAL", readiness_text)

    def test_ground_truth_data_dictionary_matches_pilot_models_and_sections(self) -> None:
        csv_path = PHASE_M_DOCS_DIR / "ground_truth_data_dictionary.csv"
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertGreaterEqual(len(rows), 40)
        by_section = {}
        for row in rows:
            section = row["section"]
            by_section.setdefault(section, set()).add(row["variable_name"])
            self.assertTrue(row["missing_value_policy"].strip())

        self.assertIn("pilot_field_code", by_section.get("A_FARMER_PROVIDED", set()))
        self.assertEqual(
            by_section.get("A_FARMER_PROVIDED", set()),
            set(FarmerPilotObservation.model_fields.keys()),
        )
        self.assertEqual(
            by_section.get("B_EXPERT_ASSESSMENT", set()) | {"pilot_field_code"},
            set(ExpertReviewRecord.model_fields.keys()),
        )
        self.assertEqual(
            by_section.get("C_MEASURED_FIELD_DATA", set()) | {"pilot_field_code"},
            set(MeasuredFieldObservation.model_fields.keys()),
        )

    def test_farmer_observation_rejects_technical_soil_climate_keys_and_non_polygons(self) -> None:
        obs_null_history = FarmerPilotObservation(**_valid_farmer_payload(crop_history=None))
        obs_empty_history = FarmerPilotObservation(**_valid_farmer_payload(crop_history=[]))
        self.assertIsNone(obs_null_history.crop_history)
        self.assertEqual(obs_empty_history.crop_history, [])

        for forbidden_key, val in (("soil_ph", 7.4), ("ndvi", 0.55), ("rainfall_mm", 520.0)):
            with self.assertRaises(ValidationError) as ctx:
                FarmerPilotObservation(**_valid_farmer_payload(**{forbidden_key: val}))
            self.assertIn("cannot collect system/lab technical keys", str(ctx.exception))

        multi = {
            "type": "MultiPolygon",
            "coordinates": [_sample_polygon()["coordinates"]],
        }
        with self.assertRaises(ValidationError):
            FarmerPilotObservation(**_valid_farmer_payload(boundary_geojson=multi))

        with self.assertRaises(ValidationError):
            FarmerPilotObservation(**_valid_farmer_payload(undeclared_field="nope"))

    def test_expert_review_enforces_human_in_the_loop_safety_gates(self) -> None:
        outcomes_valid = {
            "ACCEPTED": _valid_review_payload(
                review_outcome="ACCEPTED",
                disagreement_investigation_code="NOT_APPLICABLE",
                approved_for_farmer_briefing=True,
            ),
            "ACCEPTED_WITH_MODIFICATIONS": _valid_review_payload(
                review_outcome="ACCEPTED_WITH_MODIFICATIONS",
                recommended_modifications="Delay sowing until November rainfall onset.",
                disagreement_investigation_code="MICROCLIMATE_OR_RAINFALL_BIAS",
                approved_for_farmer_briefing=True,
            ),
            "REJECTED": _valid_review_payload(
                review_outcome="REJECTED",
                sequence_compatibility_verdict="UNACCEPTABLE",
                disagreement_investigation_code="MISSING_SALINITY_ECE_ECW",
                agronomic_safety_pass=False,
                approved_for_farmer_briefing=False,
            ),
            "REQUIRES_ADDITIONAL_INFO": _valid_review_payload(
                review_outcome="REQUIRES_ADDITIONAL_INFO",
                sequence_compatibility_verdict="UNCERTAIN",
                disagreement_investigation_code="MISSING_DEM_DRAINAGE_CONTEXT",
                approved_for_farmer_briefing=False,
            ),
        }
        self.assertEqual(set(outcomes_valid.keys()), set(ALLOWED_EXPERT_OUTCOMES))
        for label, payload in outcomes_valid.items():
            record = ExpertReviewRecord(**payload)
            self.assertEqual(record.review_outcome, label)

        # Gate 1: Rejected or REQUIRES_ADDITIONAL_INFO cannot be approved for briefing
        with self.assertRaises(ValidationError):
            ExpertReviewRecord(
                **_valid_review_payload(
                    review_outcome="REJECTED",
                    disagreement_investigation_code="MISSING_SALINITY_ECE_ECW",
                    approved_for_farmer_briefing=True,
                )
            )
        with self.assertRaises(ValidationError):
            ExpertReviewRecord(
                **_valid_review_payload(
                    review_outcome="REQUIRES_ADDITIONAL_INFO",
                    disagreement_investigation_code="INPUT_MISUNDERSTANDING_OR_BOUNDARY_ERROR",
                    approved_for_farmer_briefing=True,
                )
            )

        # Gate 2: agronomic_safety_pass=False cannot approve farmer briefing
        with self.assertRaises(ValidationError):
            ExpertReviewRecord(
                **_valid_review_payload(
                    review_outcome="ACCEPTED",
                    agronomic_safety_pass=False,
                    approved_for_farmer_briefing=True,
                )
            )

        # Gate 3: ACCEPTED_WITH_MODIFICATIONS requires explicit recommended_modifications
        with self.assertRaises(ValidationError):
            ExpertReviewRecord(
                **_valid_review_payload(
                    review_outcome="ACCEPTED_WITH_MODIFICATIONS",
                    recommended_modifications="   ",
                    disagreement_investigation_code="KNOWLEDGE_BASE_RULE_REFINEMENT_NEEDED",
                )
            )

        # Gate 4: Modified/Rejected requires explicit non-NOT_APPLICABLE investigation code
        with self.assertRaises(ValidationError):
            ExpertReviewRecord(
                **_valid_review_payload(
                    review_outcome="ACCEPTED_WITH_MODIFICATIONS",
                    recommended_modifications="Swap spring chickpea to lentil.",
                    disagreement_investigation_code="NOT_APPLICABLE",
                )
            )

    def test_measured_field_observation_anti_fabrication_and_texture_conservation(self) -> None:
        unmeasured = MeasuredFieldObservation(
            observation_id="OBS-SYNTH-01",
            pilot_field_code="SYNTH-TEST-001",
            measurement_status="NOT_MEASURED",
        )
        self.assertIsNone(unmeasured.soil_lab_ec_ds_m)
        self.assertIsNone(unmeasured.crop_yield_t_ha)

        with self.assertRaises(ValidationError):
            MeasuredFieldObservation(
                observation_id="OBS-SYNTH-02",
                pilot_field_code="SYNTH-TEST-001",
                measurement_status="NOT_MEASURED",
                soil_lab_ec_ds_m=0.0,
            )

        with self.assertRaises(ValidationError):
            MeasuredFieldObservation(
                observation_id="OBS-SYNTH-03",
                pilot_field_code="SYNTH-TEST-001",
                measurement_status="MEASURED",
            )

        valid_lab = MeasuredFieldObservation(
            observation_id="OBS-SYNTH-04",
            pilot_field_code="SYNTH-TEST-001",
            measurement_status="MEASURED",
            sample_collection_date="2026-10-15",
            soil_lab_ph=7.6,
            soil_lab_clay_pct=42.0,
            soil_lab_sand_pct=20.0,
            soil_lab_silt_pct=38.0,
            crop_yield_t_ha=3.4,
            crop_measured_name="Durum Wheat",
        )
        self.assertEqual(valid_lab.crop_measured_name, "Durum Wheat")
        self.assertIsNone(valid_lab.soil_lab_olsen_p_ppm)

        with self.assertRaises(ValidationError):
            MeasuredFieldObservation(
                observation_id="OBS-SYNTH-05",
                pilot_field_code="SYNTH-TEST-001",
                measurement_status="MEASURED",
                soil_lab_clay_pct=30.0,
                soil_lab_sand_pct=30.0,
                soil_lab_silt_pct=25.0,
            )

        with self.assertRaises(ValidationError):
            MeasuredFieldObservation(
                observation_id="OBS-SYNTH-06",
                pilot_field_code="SYNTH-TEST-001",
                measurement_status="PARTIALLY_MEASURED",
                crop_yield_t_ha=2.8,
                crop_measured_name=None,
            )

    def test_sampling_plan_validation_enforces_36_parcel_guelma_stratification(self) -> None:
        proposed_plan = [
            PilotSamplingTarget(stratum="NORTHERN_HUMID", rainfed_target=6, irrigated_target=6),
            PilotSamplingTarget(stratum="CENTRAL_VALLEY", rainfed_target=7, irrigated_target=5),
            PilotSamplingTarget(stratum="SOUTHERN_SEMI_ARID", rainfed_target=9, irrigated_target=3),
        ]
        summary = validate_sampling_plan(proposed_plan)
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["total_proposed_fields"], 36)
        self.assertEqual(summary["rainfed_fields"], 22)
        self.assertEqual(summary["irrigated_fields"], 14)

        with self.assertRaises(ValueError):
            validate_sampling_plan(proposed_plan[:2])

        with self.assertRaises(ValueError):
            validate_sampling_plan(
                [
                    PilotSamplingTarget(stratum="NORTHERN_HUMID", rainfed_target=5, irrigated_target=2),
                    PilotSamplingTarget(stratum="CENTRAL_VALLEY", rainfed_target=5, irrigated_target=2),
                    PilotSamplingTarget(stratum="SOUTHERN_SEMI_ARID", rainfed_target=5, irrigated_target=2),
                ]
            )

        with self.assertRaises(ValueError):
            validate_sampling_plan(
                [
                    PilotSamplingTarget(stratum="NORTHERN_HUMID", rainfed_target=12, irrigated_target=0),
                    PilotSamplingTarget(stratum="CENTRAL_VALLEY", rainfed_target=12, irrigated_target=0),
                    PilotSamplingTarget(stratum="SOUTHERN_SEMI_ARID", rainfed_target=12, irrigated_target=0),
                ]
            )

    def test_compute_pilot_metrics_separates_dimensions_and_blocks_premature_yield_claims(self) -> None:
        sessions = [
            PilotExecutionSession(
                session_id="S-1",
                pilot_field_code="SYNTH-TEST-001",
                intake_completed_unassisted_or_minor_help=True,
                intake_duration_seconds=310.0,
                polygon_validation_passed=True,
                field_profile_completeness_score=0.88,
                eligible_strategies_count=5,
                execution_latency_ms=420.0,
            ),
            PilotExecutionSession(
                session_id="S-2",
                pilot_field_code="SYNTH-TEST-002",
                intake_completed_unassisted_or_minor_help=False,
                intake_duration_seconds=610.0,
                polygon_validation_passed=True,
                field_profile_completeness_score=0.72,
                eligible_strategies_count=3,
                execution_latency_ms=680.0,
            ),
        ]
        reviews = [
            ExpertReviewRecord(**_valid_review_payload(review_id="REV-1")),
            ExpertReviewRecord(
                **_valid_review_payload(
                    review_id="REV-2",
                    pilot_field_code="SYNTH-TEST-002",
                    review_outcome="ACCEPTED_WITH_MODIFICATIONS",
                    recommended_modifications="Add salinity soil ECe sampling before sowing tomato.",
                    disagreement_investigation_code="MISSING_SALINITY_ECE_ECW",
                    constraint_detection_rating=3,
                    explanation_quality_rating=5,
                )
            ),
        ]
        measurements = [
            MeasuredFieldObservation(
                observation_id="OBS-1",
                pilot_field_code="SYNTH-TEST-001",
                measurement_status="NOT_MEASURED",
            )
        ]
        metrics = compute_pilot_metrics(sessions, reviews, measurements)
        self.assertEqual(metrics["session_count"], 2)
        self.assertEqual(metrics["expert_review_count"], 2)
        self.assertEqual(metrics["input_usability_completion_rate"], 0.5)
        self.assertEqual(metrics["polygon_validation_reliability_rate"], 1.0)
        self.assertEqual(metrics["mean_field_profile_completeness_score"], 0.8)
        self.assertEqual(metrics["recommendation_feasibility_rate"], 1.0)
        self.assertEqual(metrics["expert_strict_acceptance_rate"], 0.5)
        self.assertEqual(metrics["expert_usable_or_modified_rate"], 1.0)
        self.assertEqual(metrics["expert_agronomic_safety_pass_rate"], 1.0)
        self.assertEqual(metrics["mean_constraint_detection_rating_1_to_5"], 3.5)
        self.assertEqual(metrics["mean_explanation_quality_rating_1_to_5"], 4.5)
        self.assertEqual(
            metrics["predictive_yield_validation_status"],
            "NOT_VALIDATABLE_INSUFFICIENT_YIELD_LABELS",
        )
        self.assertFalse(metrics["predictive_yield_accuracy_claimable"])

        fifteen_yields = [
            MeasuredFieldObservation(
                observation_id=f"OBS-Y-{idx}",
                pilot_field_code=f"SYNTH-Y-{idx}",
                measurement_status="MEASURED",
                crop_yield_t_ha=3.1,
                crop_measured_name="Durum Wheat",
            )
            for idx in range(15)
        ]
        eligible_metrics = compute_pilot_metrics(sessions, reviews, fifteen_yields)
        self.assertEqual(eligible_metrics["measured_yield_observation_count"], 15)
        self.assertEqual(
            eligible_metrics["predictive_yield_validation_status"],
            "ELIGIBLE_FOR_EXTERNAL_YIELD_BENCHMARK",
        )
        self.assertTrue(eligible_metrics["predictive_yield_accuracy_claimable"])


if __name__ == "__main__":
    unittest.main()
