import os, re, glob, time, sys
from datetime import datetime
from elasticsearch import Elasticsearch, helpers

# Initialize ES
es = Elasticsearch("http://localhost:9200", request_timeout=60)

# Mapping of the last octet of Relay IPs to downstream server folders
NEXT_HOP_MAP = {
    "20": ["VIP01", "VIP02"],
    "21": ["GP01", "GP02"],
    "22": ["ML01", "ML02"]
}

def get_timestamp(line, date_str):
    """Extracts HH:MM:SS.ms and combines with date."""
    match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3})', line)
    return f"{date_str} {match.group(1)}" if match else None

def get_mapped_folders(relay_ip):
    if not relay_ip: return []
    octet = relay_ip.split('.')[-1]
    return NEXT_HOP_MAP.get(octet, [])

def process_logs(target_date):
    start_bench = time.time()
    base_path = "../Log-CG"
    fes_folders = [os.path.join(base_path, "FES01"), os.path.join(base_path, "FES02")]
    journeys = {}
    delivery_lookup = {}
    kaspersky_map = {} # Maps Kaspersky Internal ID -> Journey QID
    stats = {"Success": 0, "Failed": 0, "Discarded": 0, "Pending": 0}

    print(f"\n🚀 STARTING SENT LOG ENGINE | Date: {target_date}")
    
    # --- PASS 1: FES (Front-End Servers) ---
    for folder in fes_folders:
        server_name = os.path.basename(folder)
        files = sorted(glob.glob(os.path.join(folder, f"{target_date}*.log")))
        for f_path in files:
            with open(f_path, 'r', errors='ignore') as f:
                for line in f:
                    qid_match = re.search(r'\[(\d+)\]', line)
                    if not qid_match: continue
                    qid = qid_match.group(1)
                    ts = get_timestamp(line, target_date)

                    if qid not in journeys:
                        journeys[qid] = {
                            "qid": qid, 
                            "direction": "sent",  # ADDED: Direction field
                            "sender": None, 
                            "recipients": [],
                            "serverPath": [server_name], 
                            "deliveryId": None,
                            "relayIp": None, 
                            "status": "Pending", 
                            "date": target_date,
                            "start_time": ts, 
                            "end_time": ts,
                            "duration_seconds": 0,
                            "kaspersky_spam_status": "UNKNOWN",
                            "kaspersky_virus_status": "UNKNOWN",
                            "kaspersky_level": "",
                            "audit": {"fes_lines": [], "mapped_lines": []},
                            "error_details": None
                        }

                    if ts: journeys[qid]["end_time"] = ts

                    if any(x in line for x in ["QUEUE", "DEQUEUER", "got:250", "relayed"]):
                        journeys[qid]["audit"]["fes_lines"].append(f"[{server_name}] {line.strip()}")

                    # --- FES STATUS & ERROR LOGIC ---
                    if any(x in line for x in ["delivered to mailbox", "Delivered to the user mailbox", "2.0.0 OK", "2.0.0 Ok"]):
                        journeys[qid]["status"] = "Success"
                    elif journeys[qid]["status"] != "Success":
                        if "discarded" in line.lower() or "delivered via Automatic Rules" in line:
                            journeys[qid]["status"] = "Discarded"
                        elif any(x in line for x in ["failed:", "rejected"]):
                            journeys[qid]["status"] = "Failed"
                            code_match = re.search(r'\b([45]\d{2})\b', line)
                            journeys[qid]["error_details"] = {
                                "code": code_match.group(1) if code_match else "N/A",
                                "full_message": line.split("failed:")[-1].strip() if "failed:" in line else line.strip()
                            }

                    if "QUEUE" in line:
                        s_match = re.search(r'from <([^>]*)>', line)
                        if s_match: 
                            sender_val = s_match.group(1).strip()
                            journeys[qid]["sender"] = sender_val if sender_val else "NULL"
                    
                    if "got:250" in line:
                        d_match = re.search(r'got:250 (\d+)', line)
                        if d_match: 
                            d_id = d_match.group(1)
                            journeys[qid]["deliveryId"] = d_id
                            delivery_lookup[d_id] = qid
                        
                        ip_match = re.search(r'-> \[?(\d+\.\d+\.\d+\.\d+)\]?:25', line)
                        if ip_match:
                            rip = ip_match.group(1)
                            journeys[qid]["relayIp"] = rip
                            octet = rip.split('.')[-1]
                            if octet in NEXT_HOP_MAP:
                                journeys[qid]["serverPath"] += get_mapped_folders(rip)
                                journeys[qid]["status"] = "Pending"
                            else:
                                journeys[qid]["status"] = "Success"

                    if "DEQUEUER" in line:
                        r_match = re.search(r'(?:SMTP|LOCAL|SYSTEM)\([^)]*\)([^ ]+)', line)
                        if r_match: 
                            journeys[qid]["recipients"].append(r_match.group(1).strip(':').strip('<>'))

    # --- PASS 2: MAPPED (Downstream Servers) ---
    mapped_dirs = ["VIP01", "VIP02", "GP01", "GP02", "ML01", "ML02"]
    for m_dir in mapped_dirs:
        m_files = sorted(glob.glob(os.path.join(base_path, m_dir, f"{target_date}*.log")))
        for f_path in m_files:
            with open(f_path, 'r', errors='ignore') as f:
                for line in f:
                    # 1. Capture the link between Kaspersky Internal ID and Mail QID
                    link_match = re.search(r'EXTFILTER\(kaspersky\).*?(\d+)\s+FILE\s+Queue/(\d+)\.msg', line)
                    if link_match:
                        k_id, m_id = link_match.group(1), link_match.group(2)
                        if m_id in delivery_lookup:
                            kaspersky_map[k_id] = delivery_lookup[m_id]

                    # 2. General ID match for status/audit
                    id_match = re.search(r'\[(\d+)\]', line)
                    if id_match and id_match.group(1) in delivery_lookup:
                        qid = delivery_lookup[id_match.group(1)]
                        ts = get_timestamp(line, target_date)
                        journeys[qid]["audit"]["mapped_lines"].append(f"[{m_dir}] {line.strip()}")
                        if ts: journeys[qid]["end_time"] = ts

                        # --- KASPERSKY DETECTION LOGIC ---
                        if "EXTFILTER(Kaspersky)" in line:
                            spam_m = re.search(r'X-KAS-Status: (KAS_STATUS_\w+)', line)
                            if spam_m:
                                journeys[qid]["kaspersky_spam_status"] = spam_m.group(1)
                            
                            level_m = re.search(r'X-KAS-Level: \[([^\]]*)\]', line)
                            if level_m:
                                journeys[qid]["kaspersky_level"] = level_m.group(1)
                            
                            # Simple Virus Detection check
                            virus_m = re.search(r'X-KAV-Status: (\w+)', line)
                            if virus_m:
                                journeys[qid]["kaspersky_virus_status"] = virus_m.group(1)

                        # --- STATUS LOGIC ---
                        if any(x in line for x in ["2.0.0 OK", "2.0.0 Ok", "delivered", "relayed via"]):
                            if "delivered via Automatic Rules" in line:
                                journeys[qid]["status"] = "Discarded"
                            else:
                                journeys[qid]["status"] = "Success"
                                journeys[qid]["error_details"] = None
                        elif "message discarded" in line.lower():
                            journeys[qid]["status"] = "Discarded"
                        elif any(x in line for x in ["failed:", "rejected"]):
                            journeys[qid]["status"] = "Failed"
                            code_match = re.search(r'\b([45]\d{2})\b', line)
                            journeys[qid]["error_details"] = {
                                "code": code_match.group(1) if code_match else "N/A",
                                "full_message": line.split("failed:")[-1].strip() if "failed:" in line else line.strip()
                            }

                    # 3. ADVANCED VIRUS IDENTIFICATION (Grep Kaspersky ID for virus type)
                    if "X-KAV-Status: DETECT" in line:
                        k_id_match = re.search(r'inp\(\d+\):\s+(\d+)', line)
                        if k_id_match:
                            k_id = k_id_match.group(1)
                            if k_id in kaspersky_map:
                                uid = kaspersky_map[k_id]
                                # Extract specific virus name from X-KAV-Extended
                                virus_type_match = re.search(r'X-KAV-Extended:\s+([^"\e\\]+)', line)
                                if virus_type_match:
                                    journeys[uid]["kaspersky_virus_status"] = virus_type_match.group(1).strip()

    # --- PASS 3: UPLOAD ---
    actions = []
    time_fmt = "%Y-%m-%d %H:%M:%S.%f"
    for qid, j in journeys.items():
        if j["audit"]["fes_lines"]:
            try:
                d1 = datetime.strptime(j["start_time"], time_fmt)
                d2 = datetime.strptime(j["end_time"], time_fmt)
                j["duration_seconds"] = round(abs((d2 - d1).total_seconds()), 3)
            except:
                j["duration_seconds"] = 0
            
            actions.append({"_index": f"mail-journeys-sent-{target_date}", "_id": qid, "_source": j})
    
    if actions:
        helpers.bulk(es, actions, refresh=True)
        for j in journeys.values(): 
            if j["audit"]["fes_lines"]: stats[j["status"]] += 1
        elapsed = round(time.time() - start_bench, 2)
        print(f"✅ {target_date} (SENT) | Success: {stats['Success']} | Failed: {stats['Failed']} | Discarded: {stats['Discarded']} | Time: {elapsed}s")

if __name__ == "__main__":
    log_path = "../Log-CG/FES01/*.log"
    all_log_files = glob.glob(log_path)
    available_dates = sorted(list(set([os.path.basename(f)[:10] for f in all_log_files])))

    try:
        existing_indices = es.indices.get_alias(index="mail-journeys-sent-*").keys()
    except Exception:
        existing_indices = []

    for date_str in available_dates:
        index_name = f"mail-journeys-sent-{date_str}"
        if index_name in existing_indices:
            print(f"⏩ Skipping {date_str} (Index already exists)")
        else:
            process_logs(date_str)