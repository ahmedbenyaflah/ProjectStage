"""
Mail journey document shape, Elasticsearch index template, and ingest normalization.

Design goals:
- Explicit mappings: date fields for time range + sort; keywords for aggregations (Kibana).
- Small inverted index: `audit` is not indexed (still in _source for UI / Discover).
- Top-level `audit_metrics` for charts without scanning log lines.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

MAIL_JOURNEY_TEMPLATE_NAME = "cg-mail-journeys-v1"
MAIL_JOURNEY_TEMPLATE_PRIORITY = 500

# Bump when document contract changes; helps future migrations.
SCHEMA_VERSION = 2

_DATE_FORMATS = "strict_date_optional_time||yyyy-MM-dd HH:mm:ss.SSS||yyyy-MM-dd HH:mm:ss||epoch_millis"


def mail_journey_index_template_body() -> dict[str, Any]:
    """Composable index template for daily mail-journeys-sent-* / mail-journeys-received-* indices."""
    return {
        "index_patterns": ["mail-journeys-sent-*", "mail-journeys-received-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "5s",
            },
            "mappings": {
                "dynamic": "true",
                "properties": {
                    "schema_version": {"type": "short"},
                    "qid": {"type": "keyword", "ignore_above": 64},
                    "detailsid": {"type": "keyword", "ignore_above": 64},
                    "deliveryId": {"type": "keyword", "ignore_above": 64},
                    "direction": {"type": "keyword", "ignore_above": 16},
                    "date": {"type": "keyword", "ignore_above": 16},
                    "status": {"type": "keyword", "ignore_above": 32},
                    "sender": {
                        "type": "text",
                        "norms": False,
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
                    },
                    "sender_domain": {"type": "keyword", "ignore_above": 256},
                    "recipients": {"type": "keyword", "ignore_above": 512},
                    "recipient_domains": {"type": "keyword", "ignore_above": 256},
                    "successful_recipients": {"type": "keyword", "ignore_above": 512},
                    "serverPath": {"type": "keyword", "ignore_above": 64},
                    "relayIp": {"type": "keyword", "ignore_above": 45},
                    "start_time": {"type": "date", "format": _DATE_FORMATS},
                    "end_time": {"type": "date", "format": _DATE_FORMATS},
                    "@timestamp": {"type": "date", "format": _DATE_FORMATS},
                    "duration_seconds": {"type": "float"},
                    "kaspersky_spam_status": {"type": "keyword", "ignore_above": 64},
                    "kaspersky_virus_status": {"type": "keyword", "ignore_above": 128},
                    "kaspersky_level": {"type": "short"},
                    "kas_method": {"type": "keyword", "ignore_above": 256},
                    "kav_status": {"type": "keyword", "ignore_above": 64},
                    "audit_metrics": {
                        "properties": {
                            "edge_line_count": {"type": "integer"},
                            "downstream_line_count": {"type": "integer"},
                            "edge_lines_stored": {"type": "integer"},
                            "downstream_lines_stored": {"type": "integer"},
                        }
                    },
                    "error_details": {
                        "properties": {
                            "code": {"type": "keyword", "ignore_above": 16},
                            "message": {"type": "text", "norms": False},
                            "full_message": {"type": "text", "norms": False},
                            "full_error_line": {"type": "text", "norms": False},
                        }
                    },
                    # Raw lines: kept in _source, not indexed (saves disk + CPU on large audits).
                    "audit": {"type": "object", "enabled": False},
                },
            },
        },
    }


def _parse_journey_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        # ISO from older pipelines
        return datetime.fromisoformat(s.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def _format_es_local_ts(dt: datetime) -> str:
    """Format as yyyy-MM-dd HH:mm:ss.SSS for template date formats."""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def coerce_kaspersky_level_to_int(doc: dict[str, Any]) -> int:
    """
    Single integer: count of 'X' marks in KAS level (legacy string or kas_level_score).
    """
    klv = doc.get("kaspersky_level")
    if isinstance(klv, bool):
        klv = None
    if isinstance(klv, int):
        return max(0, min(32767, klv))
    if isinstance(klv, float) and not isinstance(klv, bool):
        return max(0, min(32767, int(klv)))
    ks = doc.get("kas_level_score")
    if isinstance(ks, bool):
        ks = None
    if isinstance(ks, (int, float)):
        return max(0, min(32767, int(ks)))
    if isinstance(klv, str) and klv.strip():
        return klv.count("X")
    kas = doc.get("kas_level")
    if isinstance(kas, str) and kas.strip():
        return kas.count("X")
    return 0


def _extract_domain(email: Any) -> str | None:
    """Return the lowercase domain part of an email address, or None."""
    if not isinstance(email, str):
        return None
    parts = email.strip().rsplit("@", 1)
    return parts[1].lower() if len(parts) == 2 and parts[1] else None


def finalize_journey_document(
    doc: dict[str, Any],
    *,
    max_edge_lines: int,
    max_downstream_lines: int,
) -> dict[str, Any]:
    """
    Normalize field names, cap audit arrays, attach metrics, coerce timestamps for ES date fields.
    """
    out = deepcopy(doc)
    out["schema_version"] = SCHEMA_VERSION

    out["sender_domain"] = _extract_domain(out.get("sender"))
    out["recipient_domains"] = sorted(
        {d for r in (out.get("recipients") or []) if (d := _extract_domain(r))}
    )

    out["kaspersky_level"] = coerce_kaspersky_level_to_int(out)
    out.pop("kas_level", None)
    out.pop("kas_level_score", None)

    if out.get("kaspersky_spam_status") == "UNKNOWN":
        out["kaspersky_spam_status"] = "KAS_STATUS_NOT_SPAM"

    if out.get("kaspersky_virus_status") == "UNKNOWN":
        out["kaspersky_virus_status"] = "CLEAN"

    audit = dict(out.get("audit") or {})
    edge = list(audit.get("fes_lines") or [])
    downstream = list(audit.get("mapped_lines") or [])
    legacy_mx = list(audit.get("mx_lines") or [])
    if legacy_mx and not edge:
        edge = legacy_mx

    edge_full = len(edge)
    down_full = len(downstream)
    audit["fes_lines"] = edge[:max_edge_lines]
    audit["mapped_lines"] = downstream[:max_downstream_lines]
    audit.pop("mx_lines", None)
    out["audit"] = audit

    out["audit_metrics"] = {
        "edge_line_count": edge_full,
        "downstream_line_count": down_full,
        "edge_lines_stored": len(audit["fes_lines"]),
        "downstream_lines_stored": len(audit["mapped_lines"]),
    }

    st = _parse_journey_datetime(out.get("start_time"))
    et = _parse_journey_datetime(out.get("end_time"))
    if st:
        out["start_time"] = _format_es_local_ts(st)
    if et:
        out["end_time"] = _format_es_local_ts(et)

    ts = out.get("@timestamp")
    if isinstance(ts, datetime):
        ts_dt = ts
    else:
        ts_dt = _parse_journey_datetime(ts)
    if ts_dt is None and st is not None:
        ts_dt = st
    if isinstance(ts_dt, datetime):
        out["@timestamp"] = _format_es_local_ts(ts_dt)

    # Recompute duration from normalized timestamps when possible
    if st and et:
        out["duration_seconds"] = round(abs((et - st).total_seconds()), 3)

    return out
