import os, re, glob, time
from datetime import datetime
from elasticsearch import Elasticsearch, helpers

# Initialize ES
es = Elasticsearch("http://localhost:9200", request_timeout=60)

def get_timestamp(line, date_str):
    """Extracts HH:MM:SS.ms and combines with date."""
    match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3})', line)
    return f"{date_str} {match.group(1)}" if match else None

def process_reception_logs(target_date):
    start_bench = time.time()
    base_path = "../Log-CG"
    # Reception servers MX01-MX04
    mx_folders = [os.path.join(base_path, f"MX0{i}") for i in range(1, 5)]
    
    journeys = {}
    kaspersky_id_map = {} 
    # Buffer to hold KAS lines that appear BEFORE the QID mapping is known
    pending_kaspersky_lines = {} 

    print(f"\n📥 STARTING FULL RECEPTION ENGINE | Date: {target_date}")

    for folder in mx_folders:
        if not os.path.exists(folder): continue
        server_name = os.path.basename(folder)
        files = sorted(glob.glob(os.path.join(folder, f"{target_date}*.log")))
        
        for f_path in files:
            with open(f_path, 'r', errors='ignore') as f:
                for line in f:
                    # --- 1. IGNORE SNMP NOISE ---
                    if "SNMP" in line: continue

                    # --- 2. CAPTURE MAPPINGS (QID <-> DetailsID) ---
                    if "EXTFILTER(kaspersky) out" in line:
                        link = re.search(r'out\(\d+\):\s+(\d+)\s+FILE\s+Queue/(\d+)\.msg', line)
                        if link:
                            det_id, mail_id = link.group(1), link.group(2)
                            kaspersky_id_map[det_id] = mail_id
                            
                            if det_id in pending_kaspersky_lines:
                                for buffered_line in pending_kaspersky_lines[det_id]:
                                    process_line(buffered_line, mail_id, journeys, target_date, server_name, det_id)
                                del pending_kaspersky_lines[det_id]

                    # --- 3. IDENTIFY QID OR DETAILSID ---
                    qid_match = re.search(r'\[(\d+)\]', line)
                    qid = qid_match.group(1) if qid_match else None
                    current_det_id = None

                    if not qid and "EXTFILTER(kaspersky) inp" in line:
                        id_match = re.search(r'inp\(\d+\):\s+(\d+)', line)
                        if id_match:
                            d_id = id_match.group(1)
                            current_det_id = d_id
                            if d_id in kaspersky_id_map:
                                qid = kaspersky_id_map[d_id]
                            else:
                                if d_id not in pending_kaspersky_lines:
                                    pending_kaspersky_lines[d_id] = []
                                pending_kaspersky_lines[d_id].append(line.strip())
                                continue

                    if qid:
                        process_line(line.strip(), qid, journeys, target_date, server_name, current_det_id)

    # --- UPLOAD TO ELASTICSEARCH ---
    actions = []
    for qid, j in journeys.items():
        # --- DURATION CALCULATION ---
        if j["start_time"] and j["end_time"]:
            try:
                fmt = "%Y-%m-%d %H:%M:%S.%f"
                t_start = datetime.strptime(j["start_time"], fmt)
                t_end = datetime.strptime(j["end_time"], fmt)
                j["duration_seconds"] = abs((t_end - t_start).total_seconds())
            except Exception:
                j["duration_seconds"] = 0

        if len(j["audit"]["mx_lines"]) > 1 or j["sender"]:
            actions.append({
                "_index": f"mail-journeys-received-{target_date}",
                "_id": f"{j['serverPath'][0]}-{qid}",
                "_source": j
            })
    
    if actions:
        helpers.bulk(es, actions, refresh=True)
        print(f"✅ {target_date} | Indexed {len(actions)} Journeys.")

def process_line(line, qid, journeys, target_date, server_name, details_id=None):
    """Core logic to update a journey based on a single line."""
    if qid not in journeys:
        journeys[qid] = {
            "qid": qid,
            "detailsid": None,
            "direction": "received",
            "sender": None,
            "recipients": [],
            "serverPath": [server_name],
            "status": "Success",
            "date": target_date,
            "start_time": get_timestamp(line, target_date),
            "end_time": get_timestamp(line, target_date),
            "duration_seconds": 0,
            "kaspersky_spam_status": "KAS_STATUS_NOT_SPAM",
            "kaspersky_virus_status": "CLEAN",
            "kas_method": None,
            "kav_status": None,
            "kas_level": None,
            "kas_level_score": 0,
            "error_details": {
                "code": None,
                "message": None,
                "full_error_line": None
            },
            "audit": {"mx_lines": []}
        }
    
    j = journeys[qid]
    line_lower = line.lower()
    ts = get_timestamp(line, target_date)
    if ts: j["end_time"] = ts
    j["audit"]["mx_lines"].append(line)

    if details_id:
        j["detailsid"] = details_id

    # --- SENDER EXTRACTION ---
    if "header: From:" in line:
        m = re.search(r'From:\s+(?:.*<)?([^>\s\x1b"]+)(?:>)?', line)
        if m: j["sender"] = m.group(1).lower().strip()
    
    # --- RECIPIENT EXTRACTION (IMPROVED) ---
    # 1. From standard headers (To and CC) - finds all emails in line
    if "header: To:" in line or "header: CC:" in line:
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', line)
        for e in emails:
            e_clean = e.lower().strip()
            if e_clean not in j["recipients"]:
                j["recipients"].append(e_clean)

    # 2. From Envelope lines (R W lines) - the most accurate delivery targets
    if "envelope: R" in line:
        m = re.search(r'<\s*([^>\s]+)\s*>', line)
        if m:
            e_clean = m.group(1).lower().strip()
            if e_clean not in j["recipients"]:
                j["recipients"].append(e_clean)

    # 3. From Dequeuer lines (Final relay confirmation)
    if "DEQUEUER" in line and "relayed" in line:
        m = re.search(r'SMTP\(.*?\)\s*([\w\.-]+@[\w\.-]+\.\w+)', line)
        if m:
            e_clean = m.group(1).lower().strip()
            if e_clean not in j["recipients"]:
                j["recipients"].append(e_clean)

    # --- ERROR EXTRACTION ---
    if "failed:" in line_lower and ("says:" in line_lower or "rejecting" in line_lower):
        code_match = re.search(r'says:\\n\s*(\d{3})', line)
        if code_match: j["error_details"]["code"] = code_match.group(1)
        msg_match = re.search(r'says:\\n\s*\d{3}\s+(.*?)(?:,\s*rejecting|$)', line)
        if msg_match: j["error_details"]["message"] = msg_match.group(1).strip()
        j["error_details"]["full_error_line"] = line.strip()

    # --- SECURITY HEADERS (KASPERSKY) ---
    if "EXTFILTER(kaspersky) inp" in line or "EXTFILTER(Kaspersky) inp" in line:
        id_match = re.search(r'inp\(\d+\):\s+(\d+)', line)
        if id_match: j["detailsid"] = id_match.group(1)
        spam_match = re.search(r'X-KAS-Status:\s+([A-Z_]+)', line)
        if spam_match: j["kaspersky_spam_status"] = spam_match.group(1).strip()
        method_match = re.search(r'X-KAS-Method:\s+([^"\\\x1b]+)', line)
        if method_match: j["kas_method"] = method_match.group(1).replace('\\e', '').strip()
        level_match = re.search(r'X-KAS-Level:\s+(\[[X\s]*\])', line)
        if level_match:
            raw_level = level_match.group(1).strip()
            j["kas_level"] = raw_level
            j["kas_level_score"] = raw_level.count('X')
        kav_stat_match = re.search(r'X-KAV-Status:\s+([A-Z]+)', line)
        if kav_stat_match: j["kav_status"] = kav_stat_match.group(1).strip()
        if "X-KAV-Status: DETECT" in line:
            v_ext = re.search(r'X-KAV-Extended:\s+([^"\\\x1b]+)', line)
            j["kaspersky_virus_status"] = v_ext.group(1).strip() if v_ext else "DETECTED"

    # --- STATUS LOGIC ---
    # Since we initialize as "Success", we only need to look for terminal failures.
    
    if "discarded" in line_lower or "discarded by rules" in line_lower:
        j["status"] = "Discarded"
    elif "failed" in line_lower or "rejecting" in line_lower or "rejection" in line_lower:
        j["status"] = "Failed"
    # No need for a Success 'elif' if the default is already Success, 
    # but keeping it doesn't hurt.

if __name__ == "__main__":
    log_path = "../Log-CG/MX0*/*.log"
    available_dates = sorted(list(set([os.path.basename(f)[:10] for f in glob.glob(log_path)])))
    for d in available_dates:
        process_reception_logs(d)