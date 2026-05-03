"""Helpers for log filenames that start with YYYY-MM-DD and cross-midnight journeys."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_TS_FMT = "%Y-%m-%d %H:%M:%S.%f"

_LOG_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, _TS_FMT)
    except (ValueError, TypeError):
        return None


def bump_journey_ts_window(j: dict, ts: str | None) -> None:
    """Track true min/max instants so journeys crossing midnight keep correct order."""
    if not ts:
        return
    dt = parse_ts(ts)
    if not dt:
        return
    cur_min = j.get("_ts_min_dt")
    cur_max = j.get("_ts_max_dt")
    if cur_min is None or dt < cur_min:
        j["_ts_min_dt"] = dt
    if cur_max is None or dt > cur_max:
        j["_ts_max_dt"] = dt


def commit_journey_ts_bounds(j: dict) -> None:
    mn = j.pop("_ts_min_dt", None)
    mx = j.pop("_ts_max_dt", None)
    if mn and mx:
        j["start_time"] = format_ts_for_journey(mn)
        j["end_time"] = format_ts_for_journey(mx)
        j["@timestamp"] = mn
        j["spans_calendar_days"] = mn.date() != mx.date()
        if j["spans_calendar_days"]:
            j["journey_end_calendar_date"] = mx.date().isoformat()
        else:
            j.pop("journey_end_calendar_date", None)
    else:
        j.pop("spans_calendar_days", None)
        j.pop("journey_end_calendar_date", None)


def calendar_date_from_log_basename(basename: str) -> str | None:
    """Return YYYY-MM-DD from `2026-01-27-foo.log` style names, or None."""
    m = _LOG_DATE_PREFIX.match(basename)
    if not m:
        return None
    cand = m.group(1)
    try:
        datetime.strptime(cand, "%Y-%m-%d")
    except ValueError:
        return None
    return cand


def add_calendar_days(date_str: str, days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d + timedelta(days=days)).isoformat()


def resolve_journey_index_date(
    target_date: str,
    start_time_str: str | None,
    end_time_str: str | None,
) -> str | None:
    """
    When the daily job processes calendar day ``target_date`` (D), choose which
    index suffix ``mail-journeys-*-YYYY-MM-DD`` the journey belongs in:

    - Starts on D → index ``D`` (same as before).
    - Starts on D-1 and ends on D → index ``D-1`` so a run on day D can complete
      journeys that began the previous day after day D-1's job already ran.
    """
    t_start = parse_ts(start_time_str)
    if not t_start:
        return None
    start_day = t_start.strftime("%Y-%m-%d")
    if start_day == target_date:
        return target_date
    prev = add_calendar_days(target_date, -1)
    if start_day != prev:
        return None
    t_end = parse_ts(end_time_str)
    if t_end and t_end.strftime("%Y-%m-%d") == target_date:
        return prev
    return None


def format_ts_for_journey(dt: datetime) -> str:
    """Match parsers' TS_FMT resolution (milliseconds)."""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
