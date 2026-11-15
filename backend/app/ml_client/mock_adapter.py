"""Deterministic fixture-backed MockMLAdapter with fault-injection switches (`IMPL-008`)."""

from __future__ import annotations

import copy
import json
from collections import deque
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ml_client.base import (
    MLAdapter,
    MLAuthError,
    MLCatalogVersionMismatchError,
    MLContractError,
    MLDatasetError,
    MLDatasetVersionUnavailableError,
    MLHealthResult,
    MLInsufficientDataError,
    MLInvalidPayloadError,
    MLPayloadTooLargeError,
    MLRateLimitError,
    MLTimeoutError,
    MLTransportError,
    MLUpstreamServerError,
    ProviderKind,
)
from app.schemas.catalog import MLCatalogPayload

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_SEASONS_ORDER: tuple[str, ...] = ("winter", "spring", "summer", "autumn")
_DEFAULT_SEASON_MONTH: dict[str, int] = {
    "spring": 3,
    "summer": 6,
    "autumn": 11,
    "winter": 1,
}


def _load_fixture_json(filename: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((_FIXTURES_DIR / filename).read_text(encoding="utf-8"))
    return data


def _build_season_slots(
    *,
    start_season: str,
    start_year: int,
    horizon_seasons: int,
    cycle_mode: str,
    planting_month: int | None,
) -> list[tuple[int, str, int, int]]:
    start_idx = _SEASONS_ORDER.index(start_season) if start_season in _SEASONS_ORDER else 0
    step = 2 if cycle_mode == "annual_rotation" else 1
    slots: list[tuple[int, str, int, int]] = []
    idx = start_idx
    year = start_year
    for order in range(1, horizon_seasons + 1):
        season = _SEASONS_ORDER[idx]
        month = (
            planting_month
            if order == 1 and planting_month is not None
            else _DEFAULT_SEASON_MONTH[season]
        )
        slots.append((order, season, year, month))
        next_raw = idx + step
        year += next_raw // len(_SEASONS_ORDER)
        idx = next_raw % len(_SEASONS_ORDER)
    return slots


class MockMLAdapter(MLAdapter):
    """Deterministic in-process ML provider backed by Fixtures 9.3 & 9.4 + fault switches."""

    SUPPORTED_FAULT_MODES: frozenset[str] = frozenset(
        {
            "none",
            "http_400",
            "http_401",
            "http_409_catalog",
            "http_409_dataset",
            "http_413",
            "http_422_dataset",
            "http_422_insufficient",
            "http_429",
            "http_500",
            "http_503",
            "ml_dataset_error",
            "timeout",
            "offline",
            "unavailable",
            "corrupt_json",
            "wrong_dataset_version",
            "extra_fields_5_1",
            "schema_6_0",
        }
    )

    def __init__(
        self,
        *,
        fault_mode: str = "none",
        retry_after_seconds: int | None = 2,
        ml_engine_version: str = "agro-ml-2.1.0",
        supported_dataset_versions: tuple[str, ...] = ("2026.11-guelma-v1",),
    ) -> None:
        self._output_template = _load_fixture_json("fixture_9_3_output.json")
        self._catalog_template = _load_fixture_json("fixture_9_4_catalog.json")
        self._ml_engine_version = ml_engine_version
        self._supported_dataset_versions = supported_dataset_versions
        self._fault_mode = "none"
        self._retry_after_seconds = retry_after_seconds
        self._fault_queue: deque[str] = deque()
        self.set_fault_mode(fault_mode, retry_after_seconds=retry_after_seconds)

    @property
    def provider_name(self) -> ProviderKind:
        return "mock_ml"

    @property
    def fault_mode(self) -> str:
        """Return currently armed steady-state fault injection mode."""
        return self._fault_mode

    def set_fault_mode(
        self,
        mode: str,
        *,
        retry_after_seconds: int | None = 2,
    ) -> None:
        """Configure steady-state fault injection behavior for tests."""
        if mode not in self.SUPPORTED_FAULT_MODES:
            raise ValueError(f"Unsupported mock ML fault mode: {mode!r}")
        self._fault_mode = mode
        self._retry_after_seconds = retry_after_seconds

    def set_fault_sequence(self, modes: Sequence[str]) -> None:
        """Queue per-call fault modes consumed FIFO before falling back to steady `fault_mode`."""
        for mode in modes:
            if mode not in self.SUPPORTED_FAULT_MODES:
                raise ValueError(f"Unsupported mock ML fault mode: {mode!r}")
        self._fault_queue = deque(modes)

    def _consume_active_mode(self) -> str:
        if self._fault_queue:
            return self._fault_queue.popleft()
        return self._fault_mode

    def _raise_if_transport_or_http_fault(self, mode: str) -> None:
        if mode == "http_400":
            raise MLContractError("Mock ML rejected payload contract (400 INVALID_INPUT).")
        if mode == "http_401":
            raise MLAuthError("Mock ML rejected authentication credentials (401 AUTH_FAILED).")
        if mode == "http_409_catalog":
            raise MLCatalogVersionMismatchError("Mock ML catalog version mismatch.")
        if mode in {"http_409_dataset", "http_422_dataset"}:
            status = 409 if mode == "http_409_dataset" else 422
            raise MLDatasetVersionUnavailableError(
                "Mock ML dataset_version unavailable.",
                status_code=status,
            )
        if mode == "http_413":
            raise MLPayloadTooLargeError("Mock ML simulated 413 PAYLOAD_TOO_LARGE.")
        if mode == "http_422_insufficient":
            raise MLInsufficientDataError("Mock ML simulated 422 INSUFFICIENT_DATA.")
        if mode == "http_429":
            raise MLRateLimitError(
                "Mock ML simulated 429 RATE_LIMITED.",
                retry_after_seconds=self._retry_after_seconds,
            )
        if mode == "http_500":
            raise MLUpstreamServerError(
                "Mock ML simulated 500 INTERNAL_ERROR.",
                status_code=500,
                ml_error_code="INTERNAL_ERROR",
            )
        if mode == "http_503":
            raise MLUpstreamServerError(
                "Mock ML simulated 503 OVERLOADED.",
                status_code=503,
                ml_error_code="OVERLOADED",
                retry_after_seconds=self._retry_after_seconds,
            )
        if mode == "ml_dataset_error":
            raise MLDatasetError("Mock ML simulated 502 ML_DATASET_ERROR querying Schema: dataset.")
        if mode == "timeout":
            raise MLTimeoutError("Mock ML simulated request timeout.")
        if mode in {"offline", "unavailable"}:
            raise MLTransportError("Mock ML simulated offline transport error.")
        if mode == "corrupt_json":
            raise MLInvalidPayloadError(
                "Mock ML simulated corrupt JSON body.",
                raw_body="{corrupt-json-payload",
                status_code=200,
            )

    def _build_dynamic_analysis(
        self,
        payload_dict: Mapping[str, Any],
        *,
        mode: str,
    ) -> dict[str, Any]:
        template = copy.deepcopy(self._output_template)
        base_field_plan = template["field_plans"][0]

        catalog_crops: dict[str, dict[str, Any]] = {
            str(item["crop_id"]): item for item in self._catalog_template["crops"]
        }

        request_id = str(payload_dict["request_id"])
        dataset_version = str(payload_dict["dataset_version"])
        if mode == "wrong_dataset_version":
            dataset_version = f"{dataset_version}-mismatched"

        language = str(payload_dict.get("language", "en"))
        planning = payload_dict.get("planning", {})
        priorities = payload_dict.get("priorities", {})
        fields_in = payload_dict.get("fields", [])

        start_season = str(planning.get("start_season", "spring"))
        start_year = int(planning.get("start_year", 2027))
        horizon = int(planning.get("horizon_seasons", 4))
        cycle_mode = str(planning.get("cycle_mode", "annual_rotation"))
        planting_month_raw = planning.get("planting_month")
        planting_month = int(planting_month_raw) if isinstance(planting_month_raw, int) else None

        target_crop_ids = [str(cid) for cid in priorities.get("target_crop_ids", [])]
        excluded_crop_ids = {str(cid) for cid in priorities.get("excluded_crop_ids", [])}

        slots = _build_season_slots(
            start_season=start_season,
            start_year=start_year,
            horizon_seasons=horizon,
            cycle_mode=cycle_mode,
            planting_month=planting_month,
        )

        # Build non-excluded candidate crop pool preserving valid categories & roles.
        eligible_crops = [
            crop
            for cid, crop in catalog_crops.items()
            if cid not in excluded_crop_ids and cid != "fallow"
        ]
        if not eligible_crops:
            eligible_crops = [catalog_crops["fallow"]]

        included_targets = [
            cid for cid in target_crop_ids if cid in catalog_crops and cid not in excluded_crop_ids
        ]

        field_plans: list[dict[str, Any]] = []
        for field_input in fields_in:
            fp = copy.deepcopy(base_field_plan)
            fp["field_id"] = str(field_input["field_id"])
            fp["field_name"] = str(field_input["field_name"])

            water_obj = field_input.get("water", {})
            water_avail = str(water_obj.get("availability", "moderate"))
            soil_obj = field_input.get("soil", {})

            strategies = fp["strategies"]
            for idx, strategy in enumerate(strategies):
                is_baseline = bool(strategy.get("is_existing_rotation"))
                base_seasons = list(strategy.get("seasons", []))
                new_seasons: list[dict[str, Any]] = []
                placed_crops: list[str] = []

                for slot_idx, (order, season, year, month) in enumerate(slots):
                    if is_baseline:
                        tmpl_season = (
                            copy.deepcopy(base_seasons[slot_idx])
                            if slot_idx < len(base_seasons)
                            else {
                                "selection_status": "suggested",
                                "notes": None,
                                "crop_id": "durum_wheat"
                                if season in {"autumn", "winter"}
                                else "fallow",
                            }
                        )
                        crop_id = str(tmpl_season["crop_id"])
                        if crop_id not in catalog_crops:
                            crop_id = "durum_wheat"
                        crop_meta = catalog_crops[crop_id]
                        role = str(
                            tmpl_season.get("role")
                            or crop_meta["roles"][0]
                        )
                        if role not in crop_meta["roles"]:
                            role = str(crop_meta["roles"][0])
                    else:
                        if slot_idx == 0 and included_targets:
                            chosen_id = included_targets[0]
                        elif idx == 1 and slot_idx < len(included_targets):
                            chosen_id = included_targets[slot_idx]
                        else:
                            chosen = eligible_crops[(slot_idx + idx) % len(eligible_crops)]
                            chosen_id = str(chosen["crop_id"])
                        crop_meta = catalog_crops[chosen_id]
                        crop_id = chosen_id
                        role = str(crop_meta["roles"][0])

                    placed_crops.append(crop_id)
                    new_seasons.append(
                        {
                            "order": order,
                            "season": season,
                            "year": year,
                            "planting_month": month,
                            "crop_id": crop_id,
                            "crop_name": str(
                                crop_meta["names"].get(language, crop_meta["names"]["en"])
                            ),
                            "category": str(crop_meta["category"]),
                            "role": role,
                            "selection_status": "suggested",
                            "notes": None,
                        }
                    )

                strategy["seasons"] = new_seasons
                strategy["_placed_crops"] = placed_crops

                # Align farmer_input evidence values for SEM-04 provenance checks.
                for ev in strategy.get("explanation", {}).get("evidence", []):
                    if ev.get("data_source") == "farmer_input":
                        param = ev.get("parameter")
                        if param == "water_availability":
                            ev["observed_value"] = water_avail
                        elif param == "soil_type" and soil_obj.get("soil_type") is not None:
                            ev["observed_value"] = str(soil_obj["soil_type"])
                        elif param == "soil_ph" and soil_obj.get("soil_ph") is not None:
                            ev["observed_value"] = soil_obj["soil_ph"]
                        elif (
                            param == "organic_matter_percent"
                            and soil_obj.get("organic_matter_percent") is not None
                        ):
                            ev["observed_value"] = soil_obj["organic_matter_percent"]

            # Clean internal helper attribute while computing requested_crop_results (SEM-06).
            req_crop_evals: list[dict[str, Any]] = []
            strategy_crops: dict[str, list[str]] = {}
            for strategy in strategies:
                sid = str(strategy["strategy_id"])
                strategy_crops[sid] = list(strategy.pop("_placed_crops", []))

            for target_id in target_crop_ids:
                matching_sids = [
                    sid
                    for sid, cids in strategy_crops.items()
                    if target_id in cids and sid != "S1_baseline_cereal"
                ]
                if matching_sids and target_id not in excluded_crop_ids:
                    req_crop_evals.append(
                        {
                            "requested_crop_id": target_id,
                            "outcome": "included",
                            "included_in_strategy_ids": matching_sids,
                            "replaced_by_crop_id": None,
                            "explanation": (
                                f"Target crop '{target_id}' integrated into field plan "
                                f"'{fp['field_id']}'."
                            ),
                            "comparison": [],
                            "evidence": [],
                        }
                    )
                else:
                    fallback_cid = str(eligible_crops[0]["crop_id"])
                    replaced_by = fallback_cid if fallback_cid != target_id else None
                    req_crop_evals.append(
                        {
                            "requested_crop_id": target_id,
                            "outcome": (
                                "excluded" if target_id in excluded_crop_ids else "replaced"
                            ),
                            "included_in_strategy_ids": [],
                            "replaced_by_crop_id": replaced_by,
                            "explanation": (
                                f"Target crop '{target_id}' was excluded or omitted for field "
                                f"'{fp['field_id']}'."
                            ),
                            "comparison": [],
                            "evidence": [],
                        }
                    )

            fp["requested_crop_results"] = req_crop_evals
            field_plans.append(fp)

        template["schema_version"] = "5.0"
        if mode == "extra_fields_5_1":
            template["schema_version"] = "5.1"
            template["extra_tolerant_reader_metadata"] = {"mock_minor_upgrade": True}
        elif mode == "schema_6_0":
            template["schema_version"] = "6.0"

        template["request_id"] = request_id
        template["dataset_version_used"] = dataset_version
        template["generated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        template["language"] = language
        template["ml_engine_version"] = self._ml_engine_version
        template["field_plans"] = field_plans
        return template

    async def analyze(
        self,
        payload: bytes | Mapping[str, Any],
        *,
        idempotency_key: str,
        compress: bool = False,
    ) -> dict[str, Any]:
        """Return deterministic dynamic `AnalysisResult` or execute armed fault mode."""
        _ = idempotency_key
        _ = compress
        mode = self._consume_active_mode()
        self._raise_if_transport_or_http_fault(mode)

        if isinstance(payload, bytes):
            raw_obj = json.loads(payload.decode("utf-8"))
        else:
            raw_obj = dict(payload)

        return self._build_dynamic_analysis(raw_obj, mode=mode)

    async def get_catalog(self) -> MLCatalogPayload:
        """Return validated Fixture 9.4 `CropCatalog` or execute armed fault mode."""
        mode = self._consume_active_mode()
        self._raise_if_transport_or_http_fault(mode)
        return MLCatalogPayload.model_validate(copy.deepcopy(self._catalog_template))

    async def get_health(self) -> MLHealthResult:
        """Return deterministic `MLHealthResult`, honoring offline/unhealthy fault modes."""
        mode = self._consume_active_mode()
        if mode in {"offline", "unavailable", "timeout", "http_500", "http_503", "http_401"}:
            return MLHealthResult(
                reachable=False,
                status="unavailable",
                ml_engine_version=None,
                dataset_versions_supported=(),
                provider="mock_ml",
                error=mode,
            )
        return MLHealthResult(
            reachable=True,
            status="ok",
            ml_engine_version=self._ml_engine_version,
            dataset_versions_supported=self._supported_dataset_versions,
            provider="mock_ml",
        )
