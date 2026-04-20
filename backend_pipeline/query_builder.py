"""
Elasticsearch query helpers for mail journey search.
Field names match journey_schema mappings (keyword vs text+keyword).
"""
from __future__ import annotations

from typing import Any


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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    must_clauses: list[dict[str, Any]] = []
    filter_clauses: list[dict[str, Any]] = []

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
        start_norm = normalize_hhmmss_millis(start_time or "", is_end=False) if start_time else ""
        end_norm = normalize_hhmmss_millis(end_time or "", is_end=True) if end_time else ""
        time_range: dict[str, str] = {}
        if start_norm:
            time_range["gte"] = f"{date} {start_norm}"
        if end_norm:
            time_range["lte"] = f"{date} {end_norm}"
        time_range["format"] = "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd HH:mm:ss.SSS"
        filter_clauses.append({"range": {"start_time": time_range}})

    return must_clauses, filter_clauses
