"""Pydantic v2 contracts and safety/anti-fabrication validators for Phase M Pilot."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

ALLOWED_STRATA = ("NORTHERN_HUMID", "CENTRAL_VALLEY", "SOUTHERN_SEMI_ARID")
ALLOWED_FIELD_SIZE_BANDS = ("SMALL_LT_5HA", "MEDIUM_5_TO_30HA", "LARGE_GT_30HA")
ALLOWED_EXPERT_INSTITUTIONS = (
    "DSA_GUELMA",
    "ITGC",
    "ONID",
    "INRA",
    "CHAMBER_OF_AGRICULTURE",
    "UNIVERSITY_AGRONOMY",
    "OTHER_EXTENSION",
)
ALLOWED_EXPERT_OUTCOMES = (
    "ACCEPTED",
    "ACCEPTED_WITH_MODIFICATIONS",
    "REJECTED",
    "REQUIRES_ADDITIONAL_INFO",
)
DISAGREEMENT_CAUSE_CODES = (
    "LOCAL_DISEASE_PRESSURE_UNOBSERVED",
    "MISSING_DEM_DRAINAGE_CONTEXT",
    "MISSING_SALINITY_ECE_ECW",
    "MICROCLIMATE_OR_RAINFALL_BIAS",
    "SOCIOECONOMIC_MARKET_LABOR_BARRIER",
    "KNOWLEDGE_BASE_RULE_REFINEMENT_NEEDED",
    "INPUT_MISUNDERSTANDING_OR_BOUNDARY_ERROR",
    "NOT_APPLICABLE",
)
FORBIDDEN_FARMER_MEASUREMENT_KEYS = frozenset(
    {
        "soil_ph",
        "clay_pct",
        "sand_pct",
        "silt_pct",
        "soc",
        "cec",
        "ndvi",
        "evi",
        "rainfall_mm",
        "temperature_c",
        "elevation_m",
        "slope_deg",
    }
)


class PilotSafetyViolationError(ValueError):
    """Raised when pilot governance or anti-fabrication safety rules are violated."""


class StrictPilotModel(BaseModel):
    """Base contract prohibiting undeclared or fabricated fields."""

    model_config = ConfigDict(extra="forbid")


class FarmerPilotObservation(StrictPilotModel):
    """Section A: Farmer-provided operational & geographic pilot intake only."""

    pilot_field_code: str = Field(..., min_length=3, max_length=64)
    commune_name: str = Field(..., min_length=2, max_length=80)
    stratum: Literal["NORTHERN_HUMID", "CENTRAL_VALLEY", "SOUTHERN_SEMI_ARID"]
    water_regime: Literal["rainfed", "irrigated", "supplemental", "unknown"]
    field_size_band: Literal["SMALL_LT_5HA", "MEDIUM_5_TO_30HA", "LARGE_GT_30HA"]
    boundary_geojson: Dict[str, Any]
    crop_history: Optional[List[Dict[str, Any]]] = None
    planting_seasons_reported: Optional[List[Literal["Winter", "Spring", "Summer", "Autumn"]]] = None
    irrigation_availability: Literal["limited", "moderate", "abundant", "unknown"]
    irrigation_method: Literal["drip", "sprinkler", "surface", "none", "unknown"]
    previous_crop_management_notes: Optional[str] = Field(default=None, max_length=1000)
    farmer_preferences_notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="before")
    @classmethod
    def _reject_technical_measurements(cls, raw: Any) -> Any:
        if isinstance(raw, dict):
            bad = sorted(k for k in raw if str(k).lower() in FORBIDDEN_FARMER_MEASUREMENT_KEYS)
            if bad:
                raise PilotSafetyViolationError(
                    f"Section A farmer observation cannot collect system/lab technical keys: {bad}"
                )
        return raw

    @model_validator(mode="after")
    def _check_polygon_type(self) -> "FarmerPilotObservation":
        if self.boundary_geojson.get("type") != "Polygon":
            raise PilotSafetyViolationError("Pilot field boundary_geojson must be a GeoJSON Polygon.")
        return self


class ExpertReviewRecord(StrictPilotModel):
    """Section B: Standardized ITGC/DSA/ONID agronomic review form per Field Shift analysis."""

    review_id: str = Field(..., min_length=3, max_length=64)
    pilot_field_code: str = Field(..., min_length=3, max_length=64)
    analysis_id: str = Field(..., min_length=5, max_length=80)
    expert_id: str = Field(..., min_length=2, max_length=64)
    institution: Literal[
        "DSA_GUELMA",
        "ITGC",
        "ONID",
        "INRA",
        "CHAMBER_OF_AGRICULTURE",
        "UNIVERSITY_AGRONOMY",
        "OTHER_EXTENSION",
    ]
    agronomic_assessment: str = Field(..., min_length=10, max_length=2000)
    sequence_compatibility_verdict: Literal["ACCEPTABLE", "ACCEPTABLE_WITH_CAVEATS", "UNACCEPTABLE", "UNCERTAIN"]
    local_constraints_flagged: Optional[List[str]] = None
    review_outcome: Literal[
        "ACCEPTED",
        "ACCEPTED_WITH_MODIFICATIONS",
        "REJECTED",
        "REQUIRES_ADDITIONAL_INFO",
    ]
    decision_rationale: str = Field(..., min_length=10, max_length=2000)
    recommended_modifications: Optional[str] = Field(default=None, max_length=1500)
    disagreement_investigation_code: Literal[
        "LOCAL_DISEASE_PRESSURE_UNOBSERVED",
        "MISSING_DEM_DRAINAGE_CONTEXT",
        "MISSING_SALINITY_ECE_ECW",
        "MICROCLIMATE_OR_RAINFALL_BIAS",
        "SOCIOECONOMIC_MARKET_LABOR_BARRIER",
        "KNOWLEDGE_BASE_RULE_REFINEMENT_NEEDED",
        "INPUT_MISUNDERSTANDING_OR_BOUNDARY_ERROR",
        "NOT_APPLICABLE",
    ]
    constraint_detection_rating: int = Field(..., ge=1, le=5)
    explanation_quality_rating: int = Field(..., ge=1, le=5)
    uncertainty_communication_clear: bool
    agronomic_safety_pass: bool
    approved_for_farmer_briefing: bool
    reviewed_at_utc: str = Field(..., min_length=10)

    @model_validator(mode="after")
    def _enforce_pilot_safety_gates(self) -> "ExpertReviewRecord":
        if self.review_outcome in ("REJECTED", "REQUIRES_ADDITIONAL_INFO") and self.approved_for_farmer_briefing:
            raise PilotSafetyViolationError(
                f"Outcome '{self.review_outcome}' cannot set approved_for_farmer_briefing=True."
            )
        if not self.agronomic_safety_pass and self.approved_for_farmer_briefing:
            raise PilotSafetyViolationError(
                "Unsafe recommendations (agronomic_safety_pass=False) cannot be approved for farmer briefing."
            )
        if self.review_outcome == "ACCEPTED_WITH_MODIFICATIONS" and not (
            self.recommended_modifications and self.recommended_modifications.strip()
        ):
            raise PilotSafetyViolationError(
                "ACCEPTED_WITH_MODIFICATIONS requires non-empty recommended_modifications."
            )
        if self.review_outcome in ("ACCEPTED_WITH_MODIFICATIONS", "REJECTED") and (
            self.disagreement_investigation_code == "NOT_APPLICABLE"
        ):
            raise PilotSafetyViolationError(
                "Modified or rejected recommendations require an explicit disagreement_investigation_code."
            )
        return self


class MeasuredFieldObservation(StrictPilotModel):
    """Section C: Optional empirical laboratory soil/water & observed harvest records.

    All fields default to None ('UNKNOWN') and must NEVER be silently imputed to zero.
    """

    observation_id: str = Field(..., min_length=3, max_length=64)
    pilot_field_code: str = Field(..., min_length=3, max_length=64)
    measurement_status: Literal["MEASURED", "PARTIALLY_MEASURED", "NOT_MEASURED"]
    sample_collection_date: Optional[str] = None
    soil_lab_ec_ds_m: Optional[float] = Field(default=None, ge=0.0, le=50.0)
    soil_lab_ph: Optional[float] = Field(default=None, ge=3.0, le=10.5)
    soil_lab_clay_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    soil_lab_sand_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    soil_lab_silt_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    soil_lab_som_pct: Optional[float] = Field(default=None, ge=0.0, le=30.0)
    soil_lab_caco3_pct: Optional[float] = Field(default=None, ge=0.0, le=90.0)
    soil_lab_olsen_p_ppm: Optional[float] = Field(default=None, ge=0.0, le=500.0)
    crop_yield_t_ha: Optional[float] = Field(default=None, ge=0.0, le=200.0)
    crop_measured_name: Optional[str] = Field(default=None, max_length=120)
    irrigation_water_ec_ds_m: Optional[float] = Field(default=None, ge=0.0, le=30.0)
    actual_water_consumption_m3_ha: Optional[float] = Field(default=None, ge=0.0, le=25000.0)
    lab_or_method_reference: Optional[str] = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def _validate_texture_and_status(self) -> "MeasuredFieldObservation":
        measured_vals = [
            self.soil_lab_ec_ds_m,
            self.soil_lab_ph,
            self.soil_lab_clay_pct,
            self.soil_lab_sand_pct,
            self.soil_lab_silt_pct,
            self.soil_lab_som_pct,
            self.soil_lab_caco3_pct,
            self.soil_lab_olsen_p_ppm,
            self.crop_yield_t_ha,
            self.irrigation_water_ec_ds_m,
            self.actual_water_consumption_m3_ha,
        ]
        if self.measurement_status == "NOT_MEASURED" and any(v is not None for v in measured_vals):
            raise PilotSafetyViolationError("measurement_status='NOT_MEASURED' cannot carry numeric lab/yield values.")
        if self.measurement_status in ("MEASURED", "PARTIALLY_MEASURED") and all(v is None for v in measured_vals):
            raise PilotSafetyViolationError(
                f"measurement_status='{self.measurement_status}' requires at least one real measurement (or set NOT_MEASURED)."
            )
        tex = (self.soil_lab_clay_pct, self.soil_lab_sand_pct, self.soil_lab_silt_pct)
        if all(x is not None for x in tex):
            tot = sum(float(x) for x in tex if x is not None)
            if not (98.0 <= tot <= 102.0):
                raise PilotSafetyViolationError(
                    f"Soil lab clay+sand+silt fractions must sum cleanly to ~100% (got {tot:.2f}%)."
                )
        if self.crop_yield_t_ha is not None and not (self.crop_measured_name and self.crop_measured_name.strip()):
            raise PilotSafetyViolationError("Measured crop_yield_t_ha must specify crop_measured_name.")
        return self


class PilotExecutionSession(StrictPilotModel):
    """Operational telemetry recorded during a supervised pilot run."""

    session_id: str = Field(..., min_length=3, max_length=64)
    pilot_field_code: str = Field(..., min_length=3, max_length=64)
    intake_completed_unassisted_or_minor_help: bool
    intake_duration_seconds: float = Field(..., ge=1.0, le=7200.0)
    polygon_validation_passed: bool
    field_profile_completeness_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    eligible_strategies_count: int = Field(..., ge=0)
    execution_latency_ms: float = Field(..., ge=0.0)


class PilotSamplingTarget(StrictPilotModel):
    """Stratified quota cell definition for pilot field selection."""

    stratum: Literal["NORTHERN_HUMID", "CENTRAL_VALLEY", "SOUTHERN_SEMI_ARID"]
    rainfed_target: int = Field(..., ge=1)
    irrigated_target: int = Field(..., ge=0)

    @property
    def total(self) -> int:
        return self.rainfed_target + self.irrigated_target


def validate_sampling_plan(
    targets: Sequence[PilotSamplingTarget],
    min_total_fields: int = 30,
) -> Dict[str, Any]:
    """Validate that proposed pilot sampling plan covers all 3 climate strata and both water regimes."""
    strata_present = {t.stratum for t in targets}
    if strata_present != set(ALLOWED_STRATA):
        missing = sorted(set(ALLOWED_STRATA) - strata_present)
        raise PilotSafetyViolationError(f"Sampling plan must cover all 3 Guelma strata; missing {missing}.")
    total_fields = sum(t.total for t in targets)
    total_rainfed = sum(t.rainfed_target for t in targets)
    total_irrigated = sum(t.irrigated_target for t in targets)
    if total_fields < min_total_fields:
        raise PilotSafetyViolationError(
            f"Proposed sample size {total_fields} is below minimum Phase E Pillar 5 floor ({min_total_fields})."
        )
    if total_rainfed == 0 or total_irrigated == 0:
        raise PilotSafetyViolationError("Sampling plan must include both rainfed and irrigated parcels.")
    return {
        "valid": True,
        "total_proposed_fields": total_fields,
        "rainfed_fields": total_rainfed,
        "irrigated_fields": total_irrigated,
        "strata_covered": sorted(strata_present),
    }


def compute_pilot_metrics(
    sessions: Sequence[PilotExecutionSession],
    reviews: Sequence[ExpertReviewRecord],
    measurements: Sequence[MeasuredFieldObservation],
    *,
    min_yield_pairs_for_accuracy: int = 15,
) -> Dict[str, Any]:
    """Compute separated usability, geospatial, expert, and execution metrics.

    Strictly refuses to compute predictive yield accuracy without >= min_yield_pairs_for_accuracy
    real measured crop_yield_t_ha observations.
    """
    n_sess = len(sessions)
    n_rev = len(reviews)
    yield_obs = [m for m in measurements if m.crop_yield_t_ha is not None]
    soil_lab_obs = [m for m in measurements if m.soil_lab_ec_ds_m is not None or m.soil_lab_ph is not None]

    if n_sess > 0:
        usability_rate = round(
            sum(1 for s in sessions if s.intake_completed_unassisted_or_minor_help) / n_sess, 4
        )
        poly_pass_rate = round(sum(1 for s in sessions if s.polygon_validation_passed) / n_sess, 4)
        comp_vals = [s.field_profile_completeness_score for s in sessions if s.field_profile_completeness_score is not None]
        mean_comp = round(sum(comp_vals) / len(comp_vals), 4) if comp_vals else None
        feas_rate = round(sum(1 for s in sessions if s.eligible_strategies_count > 0) / n_sess, 4)
        latencies = sorted(s.execution_latency_ms for s in sessions)
        p50_ms = latencies[len(latencies) // 2]
        p95_ms = latencies[min(len(latencies) - 1, math.floor(0.95 * len(latencies)))]
    else:
        usability_rate = poly_pass_rate = mean_comp = feas_rate = p50_ms = p95_ms = None

    if n_rev > 0:
        counts = {
            k: sum(1 for r in reviews if r.review_outcome == k)
            for k in ALLOWED_EXPERT_OUTCOMES
        }
        strict_accept_rate = round(counts["ACCEPTED"] / n_rev, 4)
        usable_with_mod_rate = round((counts["ACCEPTED"] + counts["ACCEPTED_WITH_MODIFICATIONS"]) / n_rev, 4)
        reject_rate = round(counts["REJECTED"] / n_rev, 4)
        safety_pass_rate = round(sum(1 for r in reviews if r.agronomic_safety_pass) / n_rev, 4)
        mean_constraint_rating = round(sum(r.constraint_detection_rating for r in reviews) / n_rev, 3)
        mean_expl_rating = round(sum(r.explanation_quality_rating for r in reviews) / n_rev, 3)
        unc_clear_rate = round(sum(1 for r in reviews if r.uncertainty_communication_clear) / n_rev, 4)
    else:
        counts = {k: 0 for k in ALLOWED_EXPERT_OUTCOMES}
        strict_accept_rate = usable_with_mod_rate = reject_rate = safety_pass_rate = None
        mean_constraint_rating = mean_expl_rating = unc_clear_rate = None

    if len(yield_obs) < min_yield_pairs_for_accuracy:
        yield_validation_status = "NOT_VALIDATABLE_INSUFFICIENT_YIELD_LABELS"
        predictive_yield_accuracy_claimable = False
    else:
        yield_validation_status = "ELIGIBLE_FOR_EXTERNAL_YIELD_BENCHMARK"
        predictive_yield_accuracy_claimable = True

    return {
        "session_count": n_sess,
        "expert_review_count": n_rev,
        "measured_soil_lab_count": len(soil_lab_obs),
        "measured_yield_observation_count": len(yield_obs),
        "input_usability_completion_rate": usability_rate,
        "polygon_validation_reliability_rate": poly_pass_rate,
        "mean_field_profile_completeness_score": mean_comp,
        "recommendation_feasibility_rate": feas_rate,
        "execution_latency_p50_ms": p50_ms,
        "execution_latency_p95_ms": p95_ms,
        "expert_outcome_counts": counts,
        "expert_strict_acceptance_rate": strict_accept_rate,
        "expert_usable_or_modified_rate": usable_with_mod_rate,
        "expert_rejection_rate": reject_rate,
        "expert_agronomic_safety_pass_rate": safety_pass_rate,
        "mean_constraint_detection_rating_1_to_5": mean_constraint_rating,
        "mean_explanation_quality_rating_1_to_5": mean_expl_rating,
        "uncertainty_clarity_rate": unc_clear_rate,
        "predictive_yield_validation_status": yield_validation_status,
        "predictive_yield_accuracy_claimable": predictive_yield_accuracy_claimable,
    }
