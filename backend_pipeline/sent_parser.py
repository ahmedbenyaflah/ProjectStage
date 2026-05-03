"""
Sent-mail journey parser: FES + mapped server logs → Elasticsearch `mail-journeys-sent-YYYY-MM-DD`.

Run after Elasticsearch is up and the index template is installed (automatic on API startup,
or call `es_infra.ensure_mail_journey_template` once).

For each ``target_date`` (D), reads D-1 and D log files only (no D+1). Journeys starting on D go to
``mail-journeys-sent-D``; journeys that started on D-1 and ended on D are written to
``mail-journeys-sent-(D-1)`` so the day-D job can complete overnight mail after day D-1's run.
"""
from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import time
from datetime import datetime

from elasticsearch import helpers

import config
from es_infra import ensure_mail_journey_template, get_elasticsearch
from journey_schema import finalize_journey_document
from log_calendar import (
    add_calendar_days,
    bump_journey_ts_window,
    calendar_date_from_log_basename,
    commit_journey_ts_bounds,
    resolve_journey_index_date,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

NEXT_HOP_MAP = {
    "20": ["VIP01", "VIP02"],
    "21": ["GP01", "GP02"],
    "22": ["ML01", "ML02"],
}

# MX servers relay external inbound mail through FES with an SMTPI line from this IP range.
# Any message matching this pattern is NOT a POP-client send and must be excluded.
_MX_SMTPI_RE = re.compile(r"SMTPI-\d+\(\[?197\.26\.11\.\d{1,3}\]?\).*received", re.IGNORECASE)

TS_FMT = "%Y-%m-%d %H:%M:%S.%f"


def get_timestamp(line: str, date_str: str) -> str | None:
    match = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})", line)
    return f"{date_str} {match.group(1)}" if match else None


def parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, TS_FMT)
    except (ValueError, TypeError):
        return None


def extract_recipient(line: str) -> str | None:
    r_match = re.search(r"(?:SMTP|LOCAL|SYSTEM)\([^)]*\)([^ ]+)", line)
    if r_match:
        return r_match.group(1).strip(":").strip("<>").split(")")[-1]
    return None


def _mapped_outcome_line(line_lower: str) -> bool:
    """True when this line is a terminal success/failure signal on a mapped server (for serverPath)."""
    if any(x in line_lower for x in ["2.0.0 ok", "delivered", "relayed via", "batch relayed"]):
        return True
    if "discarded" in line_lower:
        return True
    if any(x in line_lower for x in ["failed:", "rejected"]):
        return True
    return False


def process_logs(target_date: str) -> None:
    start_bench = time.time()
    base_path = os.fsdecode(config.LOG_BASE_PATH)
    fes_folders = [os.path.join(base_path, "FES01"), os.path.join(base_path, "FES02")]
    journeys: dict[str, dict] = {}
    delivery_lookup: dict[str, str] = {}
    stats = {"Success": 0, "Partial Success": 0, "Failed": 0, "Discarded": 0, "Pending": 0}

    es = get_elasticsearch()
    ensure_mail_journey_template(es)

    log.info("SENT parser | date=%s | log_root=%s", target_date, base_path)
    prev_date = add_calendar_days(target_date, -1)

    for folder in fes_folders:
        server_name = os.path.basename(folder)
        files = sorted(
            glob.glob(os.path.join(folder, f"{prev_date}*.log"))
            + glob.glob(os.path.join(folder, f"{target_date}*.log"))
        )
        for f_path in files:
            file_date = calendar_date_from_log_basename(os.path.basename(f_path)) or target_date
            with open(f_path, "r", errors="ignore") as f:
                for line in f:
                    line_lower = line.lower()

                    if any(x in line_lower for x in ["enqueued", "deleted", "snmp", "return-path rejected"]):
                        continue

                    qid_match = re.search(r"\[(\d+)\]", line)
                    if not qid_match:
                        continue
                    qid = qid_match.group(1)
                    ts = get_timestamp(line, file_date)

                    if qid not in journeys:
                        journeys[qid] = {
                            "qid": qid,
                            "direction": "sent",
                            "sender": None,
                            "recipients": [],
                            "successful_recipients": [],
                            "serverPath": [server_name],
                            "deliveryId": None,
                            "relayIp": None,
                            "status": "Pending",
                            "date": target_date,
                            "start_time": None,
                            "end_time": None,
                            "@timestamp": None,
                            "duration_seconds": 0.0,
                            "kaspersky_spam_status": "KAS_STATUS_NOT_SPAM",
                            "kaspersky_virus_status": "CLEAN",
                            "kaspersky_level": 0,
                            "audit": {"fes_lines": [], "mapped_lines": []},
                            "error_details": None,
                            "_mx_originated": False,
                        }

                    j = journeys[qid]

                    if _MX_SMTPI_RE.search(line):
                        j["_mx_originated"] = True

                    bump_journey_ts_window(j, ts)

                    fes_keywords = [
                        "queue",
                        "dequeuer",
                        "got:250",
                        "relayed",
                        "failed",
                        "rejected",
                        "discarded",
                        "delivered",
                        "mailbox",
                        "account",
                        "smtpi",
                        "extfilter",
                    ]
                    if any(x in line_lower for x in fes_keywords):
                        j["audit"]["fes_lines"].append(f"[{server_name}] {line.strip()}")

                    current_recipient = extract_recipient(line)
                    if "dequeuer" in line_lower and current_recipient:
                        if current_recipient not in j["recipients"]:
                            j["recipients"].append(current_recipient)

                    if j["status"] not in ["Success", "Pending"]:
                        pass
                    elif "discarded" in line_lower or "delivered via automatic rules" in line_lower:
                        j["status"] = "Discarded"
                    elif any(x in line_lower for x in ["failed:", "rejected"]):
                        j["status"] = "Failed"
                        code_match = re.search(r"says:\\n\s*(\d{3})", line)
                        if not code_match:
                            error_part = line.split("failed:")[-1] if "failed:" in line else line
                            code_match = re.search(r"\b([45]\d{2})\b", error_part)
                        j["error_details"] = {
                            "code": code_match.group(1) if code_match else "N/A",
                            "full_message": line.split("failed:")[-1].strip()
                            if "failed:" in line
                            else line.strip(),
                        }

                    if any(x in line_lower for x in ["delivered to mailbox", "delivered to the user mailbox"]):
                        if current_recipient and current_recipient not in j["successful_recipients"]:
                            j["successful_recipients"].append(current_recipient)

                    elif "relayed: relayed via" in line_lower:
                        ip_match = re.search(r"relayed via \[?(\d+\.\d+\.\d+\.\d+)\]?", line)
                        if ip_match:
                            if ip_match.group(1).split(".")[-1] not in NEXT_HOP_MAP:
                                if current_recipient and current_recipient not in j["successful_recipients"]:
                                    j["successful_recipients"].append(current_recipient)

                    if "queue" in line_lower:
                        s_match = re.search(r"from <([^>]*)>", line)
                        if s_match:
                            j["sender"] = s_match.group(1).strip() or "NULL"

                    if "sent " in line_lower and "->" in line_lower and "got:250" in line_lower:
                        ip_match = re.search(r"-> \[?(\d+\.\d+\.\d+\.\d+)\]?:\d+", line)
                        if ip_match:
                            rip = ip_match.group(1)
                            j["relayIp"] = rip

                            if rip.split(".")[-1] in NEXT_HOP_MAP:
                                j["status"] = "Pending"
                                d_match = re.search(r"got:250 (\d{5,})", line)
                                if d_match:
                                    d_id = d_match.group(1)
                                    j["deliveryId"] = d_id
                                    delivery_lookup[d_id] = qid

    mapped_dirs = ["VIP01", "VIP02", "GP01", "GP02", "ML01", "ML02"]
    for m_dir in mapped_dirs:
        m_files = sorted(
            glob.glob(os.path.join(base_path, m_dir, f"{prev_date}*.log"))
            + glob.glob(os.path.join(base_path, m_dir, f"{target_date}*.log"))
        )
        for f_path in m_files:
            file_date = calendar_date_from_log_basename(os.path.basename(f_path)) or target_date
            with open(f_path, "r", errors="ignore") as f:
                for line in f:
                    line_lower = line.lower()
                    if "enqueued" in line_lower or "deleted" in line_lower:
                        continue

                    id_match = re.search(r"\[(\d+)\]", line)
                    if id_match and id_match.group(1) in delivery_lookup:
                        qid = delivery_lookup[id_match.group(1)]
                        j = journeys[qid]

                        mapped_keywords = [
                            "queue",
                            "dequeuer",
                            "kaspersky",
                            "extfilter",
                            "delivered",
                            "relayed",
                            "failed",
                            "rejected",
                            "discarded",
                            "got:250",
                        ]
                        if any(x in line_lower for x in mapped_keywords):
                            j["audit"]["mapped_lines"].append(f"[{m_dir}] {line.strip()}")

                        if _mapped_outcome_line(line_lower) and m_dir not in j["serverPath"]:
                            j["serverPath"].append(m_dir)

                        ts = get_timestamp(line, file_date)
                        bump_journey_ts_window(j, ts)

                        if "extfilter(kaspersky)" in line_lower:
                            spam_m = re.search(r"X-KAS-Status: (KAS_STATUS_\w+)", line)
                            if spam_m:
                                j["kaspersky_spam_status"] = spam_m.group(1)
                            virus_m = re.search(r"X-KAV-Status: (\w+)", line)
                            if virus_m:
                                j["kaspersky_virus_status"] = virus_m.group(1)
                            level_m = re.search(r"X-KAS-Level:\s+(\[[X\s]*\])", line)
                            if level_m:
                                xn = level_m.group(1).strip().count("X")
                                j["kaspersky_level"] = max(int(j.get("kaspersky_level") or 0), xn)

                        current_recipient = extract_recipient(line)

                        if any(x in line_lower for x in ["2.0.0 ok", "delivered", "relayed via", "batch relayed"]):
                            j["error_details"] = None
                            if current_recipient and current_recipient not in j["successful_recipients"]:
                                j["successful_recipients"].append(current_recipient)
                        elif "discarded" in line_lower:
                            j["status"] = "Discarded"
                        elif any(x in line_lower for x in ["failed:", "rejected"]):
                            j["status"] = "Failed"

    actions: list[dict] = []
    mx_filtered = 0
    carry_count = 0
    for qid, j in journeys.items():
        commit_journey_ts_bounds(j)
        index_date = resolve_journey_index_date(
            target_date, j.get("start_time"), j.get("end_time")
        )
        if not index_date:
            continue

        if not j["audit"]["fes_lines"]:
            continue

        if j.pop("_mx_originated", False):
            mx_filtered += 1
            continue

        j["date"] = index_date

        if j["status"] in ["Pending", "Success"]:
            num_total = len(j["recipients"])
            num_success = len(j["successful_recipients"])

            if num_total > 0:
                if num_success >= num_total:
                    j["status"] = "Success"
                elif 0 < num_success < num_total:
                    j["status"] = "Partial Success"
                elif num_success == 0:
                    j["status"] = "Pending"

        t_start = parse_ts(j["start_time"])
        t_end = parse_ts(j["end_time"])
        j["duration_seconds"] = (
            round((t_end - t_start).total_seconds(), 3) if t_start and t_end else 0.0
        )

        finalized = finalize_journey_document(
            j,
            max_edge_lines=config.MAX_AUDIT_EDGE_LINES,
            max_downstream_lines=config.MAX_AUDIT_DOWNSTREAM_LINES,
        )
        actions.append(
            {"_index": f"mail-journeys-sent-{index_date}", "_id": qid, "_source": finalized}
        )
        if index_date != target_date:
            carry_count += 1

    if actions:
        helpers.bulk(es, actions, chunk_size=200, refresh=True)
        for act in actions:
            stats[act["_source"]["status"]] += 1
        log.info(
            "SENT %s | indexed=%d (carry_prev_day=%d) mx_filtered=%d | Success=%s Partial=%s Failed=%s Pending=%s Discarded=%s | %.2fs",
            target_date,
            len(actions),
            carry_count,
            mx_filtered,
            stats["Success"],
            stats["Partial Success"],
            stats["Failed"],
            stats["Pending"],
            stats["Discarded"],
            time.time() - start_bench,
        )
    else:
        log.warning("SENT %s | no documents to index.", target_date)


def _discover_sent_dates(base_path: str) -> list[str]:
    pattern = os.path.join(base_path, "FES01", "*.log")
    files = glob.glob(pattern)
    return sorted({os.path.basename(f)[:10] for f in files})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index sent-mail journeys into Elasticsearch.")
    parser.add_argument(
        "dates",
        nargs="*",
        help="YYYY-MM-DD dates to process (default: all dates found under FES01).",
    )
    args = parser.parse_args()
    dates = args.dates if args.dates else _discover_sent_dates(os.fsdecode(config.LOG_BASE_PATH))
    if not dates:
        log.error("No log files under %s/FES01.", config.LOG_BASE_PATH)
        raise SystemExit(1)
    for d in dates:
        process_logs(d)
