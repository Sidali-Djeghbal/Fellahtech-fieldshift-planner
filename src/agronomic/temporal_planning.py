"""Centralized Temporal Planning Validation & Agricultural Calendar (Phase N).

Separates live current-season planning (`CURRENT_PLANNING`, default) from explicit
backtests (`HISTORICAL_SIMULATION`), supports an injectable clock / reference date,
validates planting windows cleanly, and constructs a unified multi-season timeline
consumed identically across Field Profile, Constraint Engine, Candidate Generator,
and Final Recommendation Assembly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

PLANNING_MODE_CURRENT = "CURRENT_PLANNING"
PLANNING_MODE_HISTORICAL = "HISTORICAL_SIMULATION"
VALID_PLANNING_MODES = (PLANNING_MODE_CURRENT, PLANNING_MODE_HISTORICAL)

SEASON_ORDER = ("Winter", "Spring", "Summer", "Autumn")
SEASON_RANK: Dict[str, int] = {s: idx for idx, s in enumerate(SEASON_ORDER)}
ClockProvider = Callable[[], date]


def season_sort_key(year: int, season: str) -> Tuple[int, int]:
    """Return canonical chronological sort key `(year, season_index)` matching SEASON_ORDER."""
    if season not in SEASON_RANK:
        raise ValueError(f"Unsupported agricultural season '{season}'. Expected one of {SEASON_ORDER}.")
    return (int(year), SEASON_RANK[season])


def season_ordinal(year: int, season: str) -> int:
    """Return monotonic integer season ordinal (`year * 4 + season_index`)."""
    yr, s_idx = season_sort_key(year, season)
    return yr * len(SEASON_ORDER) + s_idx


def assess_crop_history_completeness(
    crop_history: Optional[List[Dict[str, Any]]],
    start_season: str,
    start_year: int,
    *,
    min_entries_for_complete: int = 2,
) -> Dict[str, Any]:
    """Classify crop_history and extract chronological predecessors strictly preceding planning start."""
    if crop_history is None:
        return {
            "completeness_flag": "NOT_PROVIDED",
            "ordered_entries": [],
            "prior_entries": [],
            "recent_resolved_entries": [],
            "predecessor_record": None,
            "predecessor_2_record": None,
            "most_recent_predecessor": None,
            "predecessor_2": None,
            "sufficient_for_existing_baseline": False,
        }
    if len(crop_history) == 0:
        return {
            "completeness_flag": "EXPLICITLY_CONFIRMED_EMPTY",
            "ordered_entries": [],
            "prior_entries": [],
            "recent_resolved_entries": [],
            "predecessor_record": None,
            "predecessor_2_record": None,
            "most_recent_predecessor": None,
            "predecessor_2": None,
            "sufficient_for_existing_baseline": False,
        }

    start_ord = season_ordinal(start_year, start_season)
    ordered = sorted(crop_history, key=lambda h: season_sort_key(int(h["year"]), str(h["season"])))
    prior = [h for h in ordered if season_ordinal(int(h["year"]), str(h["season"])) < start_ord]
    any_non_prior = len(prior) < len(ordered)
    any_unresolved = any(h.get("crop_id_resolved") is None for h in prior)

    latest_prior = prior[-1] if prior else None
    predecessor_record: Optional[Dict[str, Any]] = None
    if latest_prior is not None:
        gap = start_ord - season_ordinal(int(latest_prior["year"]), str(latest_prior["season"]))
        if 1 <= gap <= 4 and latest_prior.get("crop_id_resolved") is not None:
            predecessor_record = latest_prior

    predecessor_2_record: Optional[Dict[str, Any]] = None
    if predecessor_record is not None and len(prior) >= 2:
        prev2 = prior[-2]
        prev2_gap = start_ord - season_ordinal(int(prev2["year"]), str(prev2["season"]))
        if 1 <= prev2_gap <= 16 and prev2.get("crop_id_resolved") is not None:
            predecessor_2_record = prev2

    recent_resolved = [
        h for h in prior
        if h.get("crop_id_resolved") is not None
        and 1 <= (start_ord - season_ordinal(int(h["year"]), str(h["season"]))) <= 16
    ]
    distinct_recent_slots = {(int(h["year"]), str(h["season"])) for h in recent_resolved}

    complete = (
        (not any_non_prior)
        and (not any_unresolved)
        and (predecessor_record is not None)
        and (len(distinct_recent_slots) >= min_entries_for_complete)
    )
    return {
        "completeness_flag": "PROVIDED_COMPLETE" if complete else "PROVIDED_PARTIAL",
        "ordered_entries": ordered,
        "prior_entries": prior,
        "recent_resolved_entries": recent_resolved,
        "predecessor_record": predecessor_record,
        "predecessor_2_record": predecessor_2_record,
        "most_recent_predecessor": predecessor_record.get("crop_id_resolved") if predecessor_record else None,
        "predecessor_2": predecessor_2_record.get("crop_id_resolved") if predecessor_2_record else None,
        "sufficient_for_existing_baseline": (
            predecessor_record is not None and len(distinct_recent_slots) >= min_entries_for_complete
        ),
    }


class TemporalPlanningError(ValueError):
    """Raised when planning timeframe violates temporal validity constraints."""

    def __init__(self, message: str, *, error_code: str = "PAST_PLANNING_SEASON", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


@dataclass(frozen=True)
class SeasonWindow:
    """Inclusive agricultural planning/sowing cutoff for a season in Guelma."""

    season: str
    default_planting_month: int
    window_label: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int


@dataclass(frozen=True)
class AgriculturalCalendarConfig:
    """Configurable Guelma seasonal sowing windows and calendar progression rules."""

    windows: Dict[str, SeasonWindow]
    subsequent_main_season: str = "Autumn"

    @classmethod
    def default_guelma(cls) -> "AgriculturalCalendarConfig":
        return cls(
            windows={
                "Winter": SeasonWindow("Winter", 1, "Dec (prev yr) - Mid Mar", 1, 1, 3, 15),
                "Spring": SeasonWindow("Spring", 3, "Mar - May", 3, 1, 5, 31),
                "Summer": SeasonWindow("Summer", 6, "Jun - Aug", 6, 1, 8, 31),
                "Autumn": SeasonWindow("Autumn", 11, "Sep - Dec", 9, 1, 12, 31),
            },
            subsequent_main_season="Autumn",
        )


DEFAULT_CALENDAR_CONFIG = AgriculturalCalendarConfig.default_guelma()


def resolve_reference_date(
    reference_date: Optional[Union[date, datetime, str]] = None,
    clock: Optional[ClockProvider] = None,
) -> date:
    """Resolve current planning reference date using explicit override or injectable clock."""
    if reference_date is not None:
        if isinstance(reference_date, datetime):
            return reference_date.date()
        if isinstance(reference_date, date):
            return reference_date
        if isinstance(reference_date, str):
            text = reference_date.strip()
            if "T" in text:
                text = text.split("T", 1)[0]
            return date.fromisoformat(text)
    if clock is not None:
        resolved = clock()
        return resolved.date() if isinstance(resolved, datetime) else resolved
    return date.today()


def season_window_bounds(
    season: str,
    year: int,
    config: AgriculturalCalendarConfig = DEFAULT_CALENDAR_CONFIG,
) -> Tuple[date, date]:
    """Return inclusive `(window_start, window_end)` dates for `(season, year)`."""
    if season not in config.windows:
        raise ValueError(f"Unsupported agricultural season '{season}'. Expected one of {SEASON_ORDER}.")
    win = config.windows[season]
    if season == "Winter":
        # Agricultural Winter Y covers late Dec Y-1 sowing through Mid-March Y.
        start_dt = date(year - 1, 12, 1)
    else:
        start_dt = date(year, win.start_month, win.start_day)
    end_dt = date(year, win.end_month, win.end_day)
    return start_dt, end_dt


def _agricultural_campaign_label(season: str, year: int) -> str:
    """Return Mediterranean rainfed agricultural year tag (e.g. Autumn 2026 -> 2026/2027)."""
    if season == "Autumn":
        return f"{year}/{year + 1}"
    if season == "Winter":
        return f"{year - 1}/{year}"
    return f"{year - 1}/{year}"


def recommend_next_valid_season(
    ref_date: date,
    config: AgriculturalCalendarConfig = DEFAULT_CALENDAR_CONFIG,
) -> Tuple[str, int]:
    """Return earliest non-expired planning `(season, year)` as of `ref_date`."""
    candidates: List[Tuple[date, date, str, int]] = []
    for yr in (ref_date.year, ref_date.year + 1):
        for season in SEASON_ORDER:
            start_dt, end_dt = season_window_bounds(season, yr, config=config)
            if end_dt >= ref_date:
                candidates.append((start_dt, end_dt, season, yr))
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, best_season, best_year = candidates[0]
    return best_season, best_year


def validate_and_build_planning_timeline(
    planning: Dict[str, Any],
    *,
    crop_history: Optional[List[Dict[str, Any]]] = None,
    reference_date: Optional[Union[date, datetime, str]] = None,
    clock: Optional[ClockProvider] = None,
    config: AgriculturalCalendarConfig = DEFAULT_CALENDAR_CONFIG,
) -> Dict[str, Any]:
    """Validate planning timeframe against planning mode and build unified slot timeline.

    In `CURRENT_PLANNING` mode (default), rejects any start season whose regional sowing
    window has already closed prior to `ref_date`, as well as an explicit `planting_month`
    earlier than the current month within the start year.
    """
    ref_date = resolve_reference_date(reference_date=reference_date, clock=clock)
    raw_mode = planning.get("planning_mode")
    planning_mode = str(raw_mode).strip() if raw_mode is not None else PLANNING_MODE_CURRENT
    if planning_mode not in VALID_PLANNING_MODES:
        raise TemporalPlanningError(
            f"Invalid planning_mode '{planning_mode}'. Must be one of {VALID_PLANNING_MODES}.",
            error_code="INVALID_PLANNING_MODE",
            details={"planning_mode": planning_mode, "allowed": list(VALID_PLANNING_MODES)},
        )

    start_season = str(planning.get("start_season") or "")
    start_year = int(planning.get("start_year"))
    horizon = int(planning.get("horizon_seasons"))
    planting_month = planning.get("planting_month")

    start_dt, end_dt = season_window_bounds(start_season, start_year, config=config)
    recommended_season, recommended_year = recommend_next_valid_season(ref_date, config=config)

    temporal_status = "VALID_HISTORICAL_SIMULATION"
    warnings: List[str] = []

    if planning_mode == PLANNING_MODE_CURRENT:
        if ref_date > end_dt:
            raise TemporalPlanningError(
                f"Cannot generate CURRENT_PLANNING rotation for past season '{start_season} {start_year}' "
                f"(sowing window ended {end_dt.isoformat()} before reference date {ref_date.isoformat()}). "
                f"Select '{recommended_season} {recommended_year}' or later, or set planning_mode='HISTORICAL_SIMULATION'.",
                error_code="PAST_PLANNING_SEASON",
                details={
                    "planning_mode": planning_mode,
                    "start_season": start_season,
                    "start_year": start_year,
                    "window_end_date": end_dt.isoformat(),
                    "reference_date": ref_date.isoformat(),
                    "recommended_start_season": recommended_season,
                    "recommended_start_year": recommended_year,
                },
            )
        if planting_month is not None:
            pm = int(planting_month)
            if start_year < ref_date.year or (start_year == ref_date.year and pm < ref_date.month):
                raise TemporalPlanningError(
                    f"Specified planting_month={pm:02d}/{start_year} is in the past relative to reference date "
                    f"{ref_date.isoformat()} under CURRENT_PLANNING mode. Choose a current/future month or set "
                    "planning_mode='HISTORICAL_SIMULATION'.",
                    error_code="PAST_PLANTING_MONTH",
                    details={
                        "planning_mode": planning_mode,
                        "start_season": start_season,
                        "start_year": start_year,
                        "planting_month": pm,
                        "reference_date": ref_date.isoformat(),
                    },
                )
        if ref_date >= start_dt:
            temporal_status = "VALID_CURRENT_WINDOW"
        else:
            temporal_status = "VALID_FUTURE_WINDOW"
    else:
        if ref_date > end_dt:
            temporal_status = "HISTORICAL_SIMULATION_PAST_HORIZON"
            warnings.append(
                f"HISTORICAL_SIMULATION active: start window {start_season} {start_year} (ended {end_dt.isoformat()}) "
                f"is prior to reference date {ref_date.isoformat()}; output must not be used as a live forward operational plan."
            )
        else:
            temporal_status = "HISTORICAL_SIMULATION_CURRENT_OR_FUTURE"
            warnings.append(
                f"Explicit HISTORICAL_SIMULATION mode requested for {start_season} {start_year}."
            )

    # Check crop_history vs planning start consistency (strictly prior chronological order)
    if isinstance(crop_history, list):
        start_ord = season_ordinal(start_year, start_season)
        for idx, rec in enumerate(crop_history):
            if not isinstance(rec, dict):
                continue
            hy = rec.get("year")
            hs = rec.get("season")
            if isinstance(hy, int) and hs in config.windows:
                h_ord = season_ordinal(hy, str(hs))
                if h_ord >= start_ord:
                    rel = "concurrent with" if h_ord == start_ord else "chronologically after"
                    msg = (
                        f"Crop history record #{idx + 1} ({hs} {hy}) is {rel} planned start "
                        f"({start_season} {start_year}); sequence carryover requires history strictly before slot 1."
                    )
                    raise TemporalPlanningError(
                        msg,
                        error_code="CROP_HISTORY_AFTER_PLANNING_START",
                        details={
                            "history_record_index": idx,
                            "history_season": hs,
                            "history_year": hy,
                            "start_season": start_season,
                            "start_year": start_year,
                            "relation": rel,
                        },
                    )

    # Build unified chronological multi-season slot timeline
    slots: List[Dict[str, Any]] = []
    for idx in range(horizon):
        if idx == 0:
            slot_season = start_season
            slot_year = start_year
            slot_month = int(planting_month) if planting_month is not None else config.windows[start_season].default_planting_month
        else:
            slot_season = config.subsequent_main_season
            if start_season in ("Winter", "Spring") and config.subsequent_main_season == "Autumn":
                # Winter/Spring 2027 finishes before Autumn 2027 main campaign (same calendar year for idx=1)
                slot_year = start_year + (idx - 1)
            else:
                slot_year = start_year + idx
            slot_month = config.windows[slot_season].default_planting_month

        w_start, w_end = season_window_bounds(slot_season, slot_year, config=config)
        slots.append(
            {
                "slot_index": idx,
                "order": idx + 1,
                "season": slot_season,
                "year": slot_year,
                "planting_month": slot_month,
                "agricultural_campaign": _agricultural_campaign_label(slot_season, slot_year),
                "window_start": w_start.isoformat(),
                "window_end": w_end.isoformat(),
                "window_label": config.windows[slot_season].window_label,
                "is_historical_relative_to_reference": bool(ref_date > w_end),
            }
        )

    return {
        "planning_mode": planning_mode,
        "temporal_status": temporal_status,
        "is_historical_simulation": planning_mode == PLANNING_MODE_HISTORICAL,
        "reference_date": ref_date.isoformat(),
        "start_season": start_season,
        "start_year": start_year,
        "horizon_seasons": horizon,
        "recommended_next_valid_start": {
            "start_season": recommended_season,
            "start_year": recommended_year,
        },
        "warnings": warnings,
        "slots": slots,
    }
