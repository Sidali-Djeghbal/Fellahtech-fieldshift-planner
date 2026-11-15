"""Analysis request, polling, selection, and farm history DTOs matching `openapi.yaml`."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.errors import ErrorCode
from app.schemas.common import (
    Language,
    PaginatedResponse,
    Season,
    WarningNotice,
    sanitize_free_text,
)

CleanText = Annotated[str, BeforeValidator(sanitize_free_text)]


def _reject_bool_int(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean is not valid for integer field.")
    return value


StrictJsonInt = Annotated[int, BeforeValidator(_reject_bool_int)]


class CycleMode(StrEnum):
    """Cropping cycle planning mode (`schema-v5.0.json#/$defs/CycleMode`)."""

    ANNUAL_ROTATION = "annual_rotation"
    CONSECUTIVE_SEASONS = "consecutive_seasons"


class MarketPreference(StrEnum):
    """Target market preference (`schema-v5.0.json#/$defs/MarketPreference`)."""

    LOCAL_MARKET = "local_market"
    EXPORT = "export"
    SUBSISTENCE = "subsistence"
    MIXED = "mixed"


class AnalysisRequestStatus(StrEnum):
    """Durable job lifecycle states stored in `public.analysis_requests.status`."""

    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisResultStatus(StrEnum):
    """Completed analysis status values surfaced in `AnalysisEnvelope.status`."""

    OK = "ok"
    PARTIAL = "partial"


class SelectionChoiceStatus(StrEnum):
    """Mutable farmer decision states accepted by `PATCH /analysis/{id}/selection`."""

    SELECTED = "selected"
    REJECTED = "rejected"


class ScenarioOverrides(BaseModel):
    """What-if climate scenario overrides (`schema-v5.0.json#/$defs/ScenarioOverrides`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    temp_delta_c: float = Field(default=0.0, ge=-5.0, le=10.0)
    precip_pct_delta: float = Field(default=0.0, ge=-80.0, le=100.0)


class Planning(BaseModel):
    """Planning horizon configuration (`schema-v5.0.json#/$defs/Planning`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    start_season: Season
    start_year: StrictJsonInt = Field(ge=2020, le=2100)
    horizon_seasons: StrictJsonInt = Field(ge=1, le=6)
    cycle_mode: CycleMode = CycleMode.ANNUAL_ROTATION
    planting_month: StrictJsonInt | None = Field(default=None, ge=1, le=12)
    scenario_overrides: ScenarioOverrides = Field(default_factory=ScenarioOverrides)

    @model_validator(mode="after")
    def _reject_null_non_nullable(self) -> Planning:
        if "cycle_mode" in self.model_fields_set and self.cycle_mode is None:
            raise ValueError("cycle_mode cannot be null.")
        if "scenario_overrides" in self.model_fields_set and self.scenario_overrides is None:
            raise ValueError("scenario_overrides cannot be null.")
        return self


class PriorityWeights(BaseModel):
    """Five farmer objective weights (`schema-v5.0.json#/$defs/PriorityWeights`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    water_saving: StrictJsonInt = Field(ge=0, le=100)
    soil_improvement: StrictJsonInt = Field(ge=0, le=100)
    income: StrictJsonInt = Field(ge=0, le=100)
    risk_reduction: StrictJsonInt = Field(ge=0, le=100)
    forage_value: StrictJsonInt = Field(ge=0, le=100)


class AnalysisPriorities(BaseModel):
    """Farmer optimization priorities and constraints (`AnalysisSubmitRequest.priorities`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    weights: PriorityWeights
    market_preference: MarketPreference
    target_crop_ids: list[Annotated[CleanText, Field(min_length=1, max_length=64)]] = Field(
        max_length=20
    )
    excluded_crop_ids: list[Annotated[CleanText, Field(min_length=1, max_length=64)]] = Field(
        max_length=20
    )
    equipment_constraints: (
        list[Annotated[CleanText, Field(min_length=1, max_length=160)]] | None
    ) = Field(default_factory=list, max_length=20)

    @field_validator("equipment_constraints", mode="after")
    @classmethod
    def _normalize_equipment_constraints(cls, value: list[str] | None) -> list[str]:
        # IMPL-022: omitted or null fertilizer/equipment constraints normalize to [].
        return [] if value is None else value


class AnalysisSubmitRequest(BaseModel):
    """Submission payload for `POST /api/v1/analysis` (`openapi.yaml`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    farm_id: str = Field(pattern=r"^farm_[0-9]+$")
    language: Language
    planning: Planning
    priorities: AnalysisPriorities
    field_ids: list[Annotated[CleanText, Field(min_length=1, max_length=64)]] = Field(
        min_length=1,
        max_length=10,
    )


class AnalysisQueuedResponse(BaseModel):
    """`202 Accepted` async job queued envelope (`openapi.yaml`)."""

    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    status: Literal["pending"] = "pending"
    poll_url: str
    poll_interval_ms: int = Field(ge=1)
    warnings: list[WarningNotice]


class DegradedModeMetadata(BaseModel):
    """Explicit stale replay banner (`openapi.yaml` `DegradedModeMetadata`, `IMPL-017`)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["last_good_replay"] = "last_good_replay"
    stale: Literal[True] = True
    source_analysis_id: str = Field(pattern=r"^analysis_[0-9a-f]{12}$")
    created_at: datetime
    dataset_version: str
    age_seconds: int = Field(ge=0)


class AnalysisEnvelope(BaseModel):
    """Completed analysis payload (`GET /analysis/{analysis_id}`, `POST /analysis?wait=true`)."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str = Field(pattern=r"^analysis_[0-9a-f]{12}$")
    request_id: uuid.UUID
    status: AnalysisResultStatus
    dataset_version: str
    warnings: list[WarningNotice]
    degraded_mode: DegradedModeMetadata | None = None
    result: dict[str, Any]


class PollErrorObject(BaseModel):
    """Structured terminal failure metadata returned inside `AnalysisPollEnvelope`."""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    http_equivalent: int
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisPollEnvelope(BaseModel):
    """Job polling payload (`GET /api/v1/analysis/requests/{request_id}`)."""

    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    status: AnalysisRequestStatus
    poll_interval_ms: int | None
    analysis_id: str | None = Field(default=None, pattern=r"^analysis_[0-9a-f]{12}$")
    warnings: list[WarningNotice]
    degraded_mode: DegradedModeMetadata | None = None
    error: PollErrorObject | None = None
    result: dict[str, Any] | None = None


class AnalysisCancelResponse(BaseModel):
    """Response for `POST /api/v1/analysis/requests/{request_id}/cancel`."""

    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    status: Literal["cancelled"] = "cancelled"


class SelectionUpdateRequest(BaseModel):
    """Body for `PATCH /api/v1/analysis/{analysis_id}/selection`."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    field_id: CleanText = Field(min_length=1, max_length=64)
    strategy_id: CleanText = Field(min_length=1, max_length=64)
    selection_status: SelectionChoiceStatus


class SelectionResponse(BaseModel):
    """Response for `PATCH /api/v1/analysis/{analysis_id}/selection`."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str = Field(pattern=r"^analysis_[0-9a-f]{12}$")
    field_id: str
    strategy_id: str
    selection_status: SelectionChoiceStatus


class FarmAnalysisSummary(BaseModel):
    """History summary entry (`GET /api/v1/farms/{farm_id}/analyses`)."""

    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    analysis_id: str | None
    status: AnalysisRequestStatus
    language: Language
    catalog_version: str
    dataset_version: str | None
    ml_engine_version: str | None
    warnings: list[WarningNotice]
    created_at: datetime
    duration_ms: int | None


class FarmAnalysesPage(PaginatedResponse[FarmAnalysisSummary]):
    """Cursor-paginated farm analysis history (`FarmAnalysesPage` in `openapi.yaml`)."""
