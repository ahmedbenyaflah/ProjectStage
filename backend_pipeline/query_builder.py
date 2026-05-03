"""
Elasticsearch query helpers for mail journey search.
Field names match journey_schema mappings (keyword vs text+keyword).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

_ES_TS_FORMATS = (
    "strict_date_optional_time||yyyy-MM-dd HH:mm:ss.SSS||yyyy-MM-dd HH:mm:ss||epoch_millis"
)


def _add_calendar_days(date_str: str, days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d + timedelta(days=days)).isoformat()


def _parse_window_datetime(s: str) -> datetime:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"invalid window timestamp: {s!r}")


def _seconds_from_midnight_hms(norm: str) -> int:
    """Seconds since midnight for a ``normalize_hhmmss_millis`` value (HH:MM:SS.xxx)."""
    base = norm.split(".")[0]
    parts = base.split(":")
    h = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    sec = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
    return h * 3600 + m * 60 + sec


def index_suffixes_touching_time_window(window_start: str, window_end: str) -> list[str]:
    """
    Daily index suffixes (YYYY-MM-DD) that may hold a document overlapping
    ``[window_start, window_end]``. Includes each day in the window plus the
    previous calendar day (parser stores ``start`` on D-1 ``end`` on D in
    ``mail-journeys-*-(D-1)``).
    """
    ws = _parse_window_datetime(window_start)
    we = _parse_window_datetime(window_end)
    out: set[str] = set()
    cur = ws.date()
    end_d = we.date()
    while cur <= end_d:
        out.add(cur.isoformat())
        out.add((cur - timedelta(days=1)).isoformat())
        cur += timedelta(days=1)
    return sorted(out)


def escape_query_string(value: str) -> str:
    reserved = set(list(r'+-=!(){}[]^"~*?:\/') + ["<", ">", "|", "&"])
    out: list[str] = []
    for ch in value:
        out.append("\\" + ch if ch in reserved else ch)
    return "".join(out)


def normalize_hhmmss_millis(value: str, *, is_end: bool) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if " " in s:
        s = s.split(" ", 1)[1].strip()

    ms_default = "999" if is_end else "000"

    if "." in s:
        time_part, ms_part = s.split(".", 1)
        ms = "".join(ch for ch in ms_part if ch.isdigit())[:3].ljust(3, "0") or ms_default
    else:
        time_part, ms = s, ms_default

    parts = [p for p in time_part.split(":") if p != ""]
    h = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    sec = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0

    h = max(0, min(23, h))
    m = max(0, min(59, m))
    sec = max(0, min(59, sec))
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms}"


def build_journey_query_clauses(
    *,
    sender: str | None,
    recipient: str | None,
    qid: str | None,
    status: str | None,
    spam_status: str | None,
    virus_status: str | None,
    min_duration: float | None,
    max_duration: float | None,
    start_time: str | None,
    end_time: str | None,
    date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Returns ``(must_clauses, filter_clauses, index_suffixes)`` for daily ``mail-journeys-*-{suffix}``."""
    must_clauses: list[dict[str, Any]] = []
    filter_clauses: list[dict[str, Any]] = []
    index_suffixes: list[str] = [date]

    if sender:
        s = sender.strip()
        if s:
            must_clauses.append(
                {
                    "query_string": {
                        "query": f"*{escape_query_string(s)}*",
                        "fields": ["sender", "sender.keyword"],
                        "analyze_wildcard": True,
                    }
                }
            )

    if recipient:
        r = recipient.strip()
        if r:
            must_clauses.append(
                {
                    "query_string": {
                        "query": f"*{escape_query_string(r)}*",
                        "fields": ["recipients"],
                        "analyze_wildcard": True,
                    }
                }
            )

    if qid:
        must_clauses.append({"term": {"qid": qid}})

    if status and status.lower() != "all":
        filter_clauses.append({"term": {"status": status.title()}})

    if spam_status:
        filter_clauses.append({"term": {"kaspersky_spam_status": spam_status}})

    if virus_status:
        filter_clauses.append({"term": {"kaspersky_virus_status": virus_status}})

    if min_duration is not None or max_duration is not None:
        range_query: dict[str, float] = {}
        if min_duration is not None:
            range_query["gte"] = min_duration
        if max_duration is not None:
            range_query["lte"] = max_duration
        filter_clauses.append({"range": {"duration_seconds": range_query}})

    if start_time or end_time:
        start_norm = (
            normalize_hhmmss_millis(start_time or "", is_end=False) if (start_time or "").strip() else ""
        )
        end_raw = (end_time or "").strip()
        if not start_norm:
            return must_clauses, filter_clauses, index_suffixes

        if not end_raw:
            window_start = f"{date} {start_norm}"
            window_end = f"{date} 23:59:59.999"
            filter_clauses.append(
                {
                    "range": {
                        "start_time": {
                            "gte": window_start,
                            "lte": window_end,
                            "format": _ES_TS_FORMATS,
                        }
                    }
                }
            )
        else:
            end_norm = normalize_hhmmss_millis(end_time or "", is_end=True)
            if end_norm.startswith("00:00:00."):
                window_start = f"{date} {start_norm}"
                window_end = f"{date} 23:59:59.999"
                filter_clauses.append(
                    {
                        "range": {
                            "start_time": {
                                "gte": window_start,
                                "lte": window_end,
                                "format": _ES_TS_FORMATS,
                            }
                        }
                    }
                )
            else:
                start_sec = _seconds_from_midnight_hms(start_norm)
                end_sec = _seconds_from_midnight_hms(end_norm)
                if end_sec < start_sec:
                    end_day = _add_calendar_days(date, 1)
                    window_start = f"{date} {start_norm}"
                    window_end = f"{end_day} {end_norm}"
                else:
                    window_start = f"{date} {start_norm}"
                    window_end = f"{date} {end_norm}"

                filter_clauses.append(
                    {
                        "bool": {
                            "must": [
                                {"range": {"start_time": {"lte": window_end, "format": _ES_TS_FORMATS}}},
                                {"range": {"end_time": {"gte": window_start, "format": _ES_TS_FORMATS}}},
                            ]
                        }
                    }
                )

        index_suffixes = index_suffixes_touching_time_window(window_start, window_end)

    return must_clauses, filter_clauses, index_suffixes
