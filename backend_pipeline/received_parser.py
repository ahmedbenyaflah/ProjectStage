"""
Received-mail (MX) journey parser → Elasticsearch `mail-journeys-received-YYYY-MM-DD`.

Uses the same canonical audit shape as sent mail: `audit.fes_lines` (edge/MX trail) and
`audit.mapped_lines` (unused here). Documents are finalized with `journey_schema.finalize_journey_document`.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TS_FMT = "%Y-%m-%d %H:%M:%S.%f"

_RX_AUDIT_KEYWORDS = [
    "queue", "dequeuer", "header", "envelope",
    "extfilter", "kaspersky",
    "failed", "rejected", "rejecting",
    "discarded", "relayed", "delivered",
    "mailbox", "account", "smtpi",
    "got:250",
]


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


def process_line(
    line: str,
    qid: str,
    journeys: dict,
    target_date: str,
    server_name: str,
    details_id: str | None = None,
) -> None:
    if qid not in journeys:
        st = get_timestamp(line, target_date)
        journeys[qid] = {
            "qid": qid,
            "detailsid": None,
            "direction": "received",
            "sender": None,
            "recipients": [],
            "serverPath": [server_name],
            "relayIp": None,
            "status": "Success",
            "date": target_date,
            "start_time": st,
            "end_time": st,
            "@timestamp": parse_ts(st) if st else None,
            "duration_seconds": 0.0,
            "kaspersky_spam_status": "KAS_STATUS_NOT_SPAM",
            "kaspersky_virus_status": "CLEAN",
            "kaspersky_level": 0,
            "kas_method": None,
            "kav_status": None,
            "error_details": {
                "code": None,
                "message": None,
                "full_error_line": None,
            },
            "audit": {"fes_lines": [], "mapped_lines": []},
        }

    j = journeys[qid]
    line_lower = line.lower()
    ts = get_timestamp(line, target_date)
    if ts:
        j["end_time"] = ts
    if any(kw in line_lower for kw in _RX_AUDIT_KEYWORDS):
        j["audit"]["fes_lines"].append(f"[{server_name}] {line.strip()}")

    if details_id:
        j["detailsid"] = details_id

    if "header: From:" in line:
        m = re.search(r'From:\s+(?:.*<)?([^>\s\x1b"]+)(?:>)?', line)
        if m:
            j["sender"] = m.group(1).lower().strip()

    if "header: To:" in line or "header: CC:" in line:
        emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", line)
        for e in emails:
            e_clean = e.lower().strip()
            if e_clean not in j["recipients"]:
                j["recipients"].append(e_clean)

    if "envelope: R" in line:
        m = re.search(r"<\s*([^>\s]+)\s*>", line)
        if m:
            e_clean = m.group(1).lower().strip()
            if e_clean not in j["recipients"]:
                j["recipients"].append(e_clean)

    if "DEQUEUER" in line and "relayed" in line:
        m = re.search(r"SMTP\(.*?\)\s*([\w\.-]+@[\w\.-]+\.\w+)", line)
        if m:
            e_clean = m.group(1).lower().strip()
            if e_clean not in j["recipients"]:
                j["recipients"].append(e_clean)

    if "failed:" in line_lower and ("says:" in line_lower or "rejecting" in line_lower):
        code_match = re.search(r"says:\\n\s*(\d{3})", line)
        if code_match:
            j["error_details"]["code"] = code_match.group(1)
        msg_match = re.search(r"says:\\n\s*\d{3}\s+(.*?)(?:,\s*rejecting|$)", line)
        if msg_match:
            j["error_details"]["message"] = msg_match.group(1).strip()
        j["error_details"]["full_error_line"] = line.strip()

    if "EXTFILTER(kaspersky) inp" in line or "EXTFILTER(Kaspersky) inp" in line:
        id_match = re.search(r"inp\(\d+\):\s+(\d+)", line)
        if id_match:
            j["detailsid"] = id_match.group(1)
        spam_match = re.search(r"X-KAS-Status:\s+([A-Z_]+)", line)
        if spam_match:
            j["kaspersky_spam_status"] = spam_match.group(1).strip()
        method_match = re.search(r'X-KAS-Method:\s+([^"\\\x1b]+)', line)
        if method_match:
            j["kas_method"] = method_match.group(1).replace("\\e", "").strip()
        level_match = re.search(r"X-KAS-Level:\s+(\[[X\s]*\])", line)
        if level_match:
            raw_level = level_match.group(1).strip()
            xn = raw_level.count("X")
            j["kaspersky_level"] = max(int(j.get("kaspersky_level") or 0), xn)
        kav_stat_match = re.search(r"X-KAV-Status:\s+([A-Z]+)", line)
        if kav_stat_match:
            j["kav_status"] = kav_stat_match.group(1).strip()
        if "X-KAV-Status: DETECT" in line:
            v_ext = re.search(r'X-KAV-Extended:\s+([^"\\\x1b]+)', line)
            j["kaspersky_virus_status"] = v_ext.group(1).strip() if v_ext else "DETECTED"

    if "discarded" in line_lower or "discarded by rules" in line_lower:
        j["status"] = "Discarded"
    elif "failed" in line_lower or "rejecting" in line_lower or "rejection" in line_lower:
        j["status"] = "Failed"
        if not j["error_details"]["code"]:
            code_match = re.search(r"says:\\n\s*(\d{3})", line)
            if not code_match:
                error_part = line.split("failed:")[-1] if "failed:" in line else line
                code_match = re.search(r"\b([45]\d{2})\b", error_part)
            if code_match:
                j["error_details"]["code"] = code_match.group(1)
            if not j["error_details"]["message"]:
                msg = line.split("failed:")[-1].strip() if "failed:" in line else None
                if msg:
                    j["error_details"]["message"] = msg
            if not j["error_details"]["full_error_line"]:
                j["error_details"]["full_error_line"] = line.strip()


def process_reception_logs(target_date: str) -> None:
    start_bench = time.time()
    base_path = os.fsdecode(config.LOG_BASE_PATH)
    mx_folders = [os.path.join(base_path, f"MX0{i}") for i in range(1, 5)]

    journeys: dict[str, dict] = {}
    kaspersky_id_map: dict[str, str] = {}
    pending_kaspersky_lines: dict[str, list[str]] = {}

    es = get_elasticsearch()
    ensure_mail_journey_template(es)

    log.info("RECEIVED parser | date=%s | log_root=%s", target_date, base_path)

    for folder in mx_folders:
        if not os.path.exists(folder):
            continue
        server_name = os.path.basename(folder)
        files = sorted(glob.glob(os.path.join(folder, f"{target_date}*.log")))

        for f_path in files:
            with open(f_path, "r", errors="ignore") as f:
                for line in f:
                    if "SNMP" in line:
                        continue

                    if "EXTFILTER(kaspersky) out" in line:
                        link = re.search(r"out\(\d+\):\s+(\d+)\s+FILE\s+Queue/(\d+)\.msg", line)
                        if link:
                            det_id, mail_id = link.group(1), link.group(2)
                            kaspersky_id_map[det_id] = mail_id

                            process_line(line.strip(), mail_id, journeys, target_date, server_name, det_id)

                            if det_id in pending_kaspersky_lines:
                                for buffered_line in pending_kaspersky_lines[det_id]:
                                    process_line(buffered_line, mail_id, journeys, target_date, server_name, det_id)
                                del pending_kaspersky_lines[det_id]

                    qid_match = re.search(r"\[(\d+)\]", line)
                    qid = qid_match.group(1) if qid_match else None
                    current_det_id = None

                    if not qid and "EXTFILTER(kaspersky) inp" in line:
                        id_match = re.search(r"inp\(\d+\):\s+(\d+)", line)
                        if id_match:
                            d_id = id_match.group(1)
                            current_det_id = d_id
                            if d_id in kaspersky_id_map:
                                qid = kaspersky_id_map[d_id]
                            else:
                                pending_kaspersky_lines.setdefault(d_id, []).append(line.strip())
                                continue

                    if qid:
                        process_line(line.strip(), qid, journeys, target_date, server_name, current_det_id)

    actions: list[dict] = []
    for qid, j in journeys.items():
        if j["start_time"] and j["end_time"]:
            try:
                t_start = datetime.strptime(j["start_time"], TS_FMT)
                t_end = datetime.strptime(j["end_time"], TS_FMT)
                j["duration_seconds"] = round(abs((t_end - t_start).total_seconds()), 3)
            except Exception:
                j["duration_seconds"] = 0.0

        if len(j["audit"]["fes_lines"]) <= 1 and not j["sender"]:
            continue

        finalized = finalize_journey_document(
            j,
            max_edge_lines=config.MAX_AUDIT_EDGE_LINES,
            max_downstream_lines=config.MAX_AUDIT_DOWNSTREAM_LINES,
        )
        doc_id = f"{j['serverPath'][0]}-{qid}"
        actions.append(
            {"_index": f"mail-journeys-received-{target_date}", "_id": doc_id, "_source": finalized}
        )

    if actions:
        helpers.bulk(es, actions, chunk_size=200, refresh=True)
        log.info(
            "RECEIVED %s | indexed=%d | %.2fs",
            target_date,
            len(actions),
            time.time() - start_bench,
        )
    else:
        log.warning("RECEIVED %s | no documents to index.", target_date)


def _discover_received_dates(base_path: str) -> list[str]:
    files = glob.glob(os.path.join(base_path, "MX0*", "*.log"))
    return sorted({os.path.basename(f)[:10] for f in files})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index received-mail journeys into Elasticsearch.")
    parser.add_argument(
        "dates",
        nargs="*",
        help="YYYY-MM-DD dates to process (default: all dates found under MX0*).",
    )
    args = parser.parse_args()
    root = os.fsdecode(config.LOG_BASE_PATH)
    dates = args.dates if args.dates else _discover_received_dates(root)
    if not dates:
        log.error("No log files under %s/MX0*.", config.LOG_BASE_PATH)
        raise SystemExit(1)
    for d in dates:
        process_reception_logs(d)
