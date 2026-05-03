"""
DNSBL scan journeys in Elasticsearch: each completed scan (or interval change)
is stored with the interval that schedules the next run. The background loop
uses last @timestamp + interval_seconds to compute the next wall-clock scan.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

log = logging.getLogger(__name__)

JOURNEYS_INDEX = "dnsbl-scan-journeys"


def ensure_dnsbl_journeys_index(es) -> None:
    """Create the journeys index if missing."""
    if es.indices.exists(index=JOURNEYS_INDEX):
        return
    mapping = {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "interval_seconds": {"type": "integer"},
                "next_scan_at": {"type": "date"},
                "trigger": {"type": "keyword"},
                "scan": {
                    "properties": {
                        "total_checks": {"type": "integer"},
                        "listed": {"type": "integer"},
                        "errors": {"type": "integer"},
                    }
                },
                "listed_rows": {"type": "object", "enabled": True},
            }
        }
    }
    es.indices.create(index=JOURNEYS_INDEX, body=mapping)


def _parse_journey_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        log.warning("Could not parse journey @timestamp: %r", value)
        return None


def get_latest_journey(es) -> dict[str, Any] | None:
    """Return _source of the most recent journey document, or None."""
    if not es.indices.exists(index=JOURNEYS_INDEX):
        return None
    try:
        resp = es.search(
            index=JOURNEYS_INDEX,
            body={"size": 1, "sort": [{"@timestamp": "desc"}]},
        )
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return None
        return hits[0].get("_source") or {}
    except Exception as e:
        log.warning("get_latest_journey failed: %s", e)
        return None


def get_latest_interval_seconds(es, *, fallback: int) -> int:
    """Interval from the latest journey, or fallback if none."""
    src = get_latest_journey(es)
    if not src:
        return fallback
    try:
        v = int(src.get("interval_seconds", fallback))
        return max(10, v)
    except (TypeError, ValueError):
        return fallback


def get_schedule_from_latest_journey(es) -> tuple[datetime, int] | None:
    """
    (last_completed_at_utc_naive, interval_seconds) from the newest journey, or None.
    """
    src = get_latest_journey(es)
    if not src:
        return None
    last = _parse_journey_timestamp(src.get("@timestamp"))
    if last is None:
        return None
    try:
        interval_sec = int(src.get("interval_seconds", 300))
    except (TypeError, ValueError):
        interval_sec = 300
    interval_sec = max(10, interval_sec)
    return last, interval_sec


def save_journey(
    es,
    *,
    summary: dict[str, Any],
    interval_seconds: int,
    trigger: str,
) -> None:
    """
    Index one journey document. ``summary`` is the return value of run_dnsbl_scan
    (includes listed_rows; pair_status is not stored to keep documents smaller).
    """
    ts_raw = summary.get("timestamp")
    if isinstance(ts_raw, str) and ts_raw.endswith("Z"):
        ts_raw = ts_raw[:-1]
    completed_at = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else datetime.utcnow()
    interval_seconds = max(10, int(interval_seconds))
    next_scan_at = completed_at + timedelta(seconds=interval_seconds)

    doc: dict[str, Any] = {
        "@timestamp": summary.get("timestamp") or (completed_at.isoformat() + "Z"),
        "interval_seconds": interval_seconds,
        "next_scan_at": next_scan_at.isoformat() + "Z",
        "trigger": trigger,
        "scan": {
            "total_checks": summary.get("total_checks", 0),
            "listed": summary.get("listed", 0),
            "errors": summary.get("errors", 0),
        },
        "listed_rows": summary.get("listed_rows") or [],
    }
    # refresh=True so the background loop's next get_schedule_from_latest_journey sees this
    # anchor; refresh=False can leave the previous journey visible and trigger a second scan.
    try:
        es.index(index=JOURNEYS_INDEX, document=doc, refresh=True)
    except TypeError:
        es.index(index=JOURNEYS_INDEX, body=doc, refresh=True)
    log.info(
        "DNSBL journey saved trigger=%s interval=%s next_scan_at=%s",
        trigger,
        interval_seconds,
        doc["next_scan_at"],
    )


def save_interval_config_journey(es, *, interval_seconds: int) -> None:
    """
    Persist new interval + schedule anchor without running DNS (fast PATCH /api/blacklist/interval).
    Next background scan is scheduled from this document's @timestamp + interval_seconds.
    """
    now = datetime.utcnow()
    ts = now.isoformat() + "Z"
    interval_seconds = max(10, int(interval_seconds))
    next_scan_at = now + timedelta(seconds=interval_seconds)
    doc: dict[str, Any] = {
        "@timestamp": ts,
        "interval_seconds": interval_seconds,
        "next_scan_at": next_scan_at.isoformat() + "Z",
        "trigger": "interval_change",
        "interval_only": True,
        "scan": {"total_checks": 0, "listed": 0, "errors": 0},
        "listed_rows": [],
    }
    try:
        es.index(index=JOURNEYS_INDEX, document=doc, refresh=True)
    except TypeError:
        es.index(index=JOURNEYS_INDEX, body=doc, refresh=True)
    log.info(
        "DNSBL interval-only journey saved interval=%s next_scan_at=%s",
        interval_seconds,
        doc["next_scan_at"],
    )
