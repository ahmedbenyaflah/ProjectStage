import dns.resolver
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from elasticsearch import Elasticsearch
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load variables from your .env file
load_dotenv()

app = FastAPI()

# --- CONFIGURATION ---
ES_HOST = "http://localhost:9200"
INDEX_NAME = "dnsbl-checks"
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "ahmedbenyaflah42@gmail.com")
RECEIVER_EMAIL = "ahmedbenyaflah71@gmail.com"
# Clean the App Password of spaces if they exist
APP_PASSWORD = os.getenv("EMAIL_PASSWORD", "tqjf mvys ybrq hkjk").replace(" ", "")

HOSTS = [
    "196.203.232.133", "197.26.11.132", "197.26.11.133", "197.26.11.134",
    "196.224.96.4", "196.224.96.5", "196.224.96.6", "193.95.123.25",
    "193.95.123.26", "193.95.123.27", "193.95.123.24", "196.203.232.5", "196.203.232.6"
]

DNSBLS = [
    "bl.spamcop.net", "zen.spamhaus.org", "dnsbl.sorbs.net", 
    "dnsbl-2.uceprotect.net", "access.redhawk.org"
]

es = Elasticsearch(ES_HOST)
scheduler = BackgroundScheduler()

# --- DATABASE INITIALIZATION ---
async def init_es():
    if not es.indices.exists(index=INDEX_NAME):
        mapping = {
            "mappings": {
                "properties": {
                    "ip": {"type": "ip"},
                    "blacklist": {"type": "keyword"},
                    "dnsb_status": {"type": "keyword"},
                    "@timestamp": {"type": "date"},
                }
            }
        }
        es.indices.create(index=INDEX_NAME, body=mapping)
        print(f"✅ Elasticsearch Index '{INDEX_NAME}' initialized.")

# --- CORE LOGIC ---
def check_ip_on_bl(ip, bl, timestamp):
    reverse_ip = ".".join(reversed(ip.split(".")))
    query = f"{reverse_ip}.{bl}"
    
    doc = {
        "ip": ip,
        "blacklist": bl,
        "dnsb_status": "CLEAN",
        "@timestamp": timestamp,
    }

    try:
        dns.resolver.resolve(query, 'A')
        doc["dnsb_status"] = "LISTED"
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        pass
    except Exception:
        doc["dnsb_status"] = "ERROR"

    es.index(index=INDEX_NAME, document=doc)
    return doc

def send_alert(listed_results):
    msg = EmailMessage()
    msg['Subject'] = f"🚨 ALERT: {len(listed_results)} IPs Blacklisted"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    table_rows = ""
    for item in listed_results:
        table_rows += f"""
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6;">{item['ip']}</td>
            <td style="padding: 12px; border: 1px solid #dee2e6; color: #dc3545; font-weight: bold;">{item['blacklist']}</td>
        </tr>
        """

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 8px; border-top: 5px solid #dc3545; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">Infrastructure Reputation Alert</h2>
            <p style="color: #666;">Our automated monitor detected blacklisted IPs. See details below:</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 12px; border: 1px solid #dee2e6; text-align: left;">Server IP</th>
                        <th style="padding: 12px; border: 1px solid #dee2e6; text-align: left;">Blacklist Provider</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
            </table>
            <p style="font-size: 11px; color: #999; margin-top: 20px;">Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        print("✅ HTML Alert sent successfully.")
    except Exception as e:
        print(f"❌ SMTP Error: {e}")

def run_full_scan():
    timestamp = datetime.utcnow()
    print(f"🕒 [{timestamp.strftime('%H:%M:%S')}] Auto-scan started...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(check_ip_on_bl, ip, bl, timestamp) for ip in HOSTS for bl in DNSBLS]
        results = [f.result() for f in futures]

    listed = [r for r in results if r["dnsb_status"] == "LISTED"]
    if listed:
        send_alert(listed)
    print(f"🏁 Scan complete. {len(listed)} issues found.")

# --- LIFECYCLE EVENTS ---
@app.on_event("startup")
async def startup_event():
    await init_es()
    # Add automated task: every 5 minutes
    scheduler.add_job(run_full_scan, 'interval', minutes=1)
    scheduler.start()
    print("⏰ Background Scheduler started: Scanning every 5 minutes.")

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head>
            <title>Monitor Dashboard</title>
            <style>
                body { font-family: sans-serif; background: #f0f2f5; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); text-align: center; }
                button { background: #1877f2; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; }
                #status { margin-top: 20px; color: #555; font-size: 0.9rem; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Reputation Monitor</h1>
                <p>Status: Automation Active (Every 5 mins)</p>
                <button onclick="runScan()">Force Manual Scan</button>
                <div id="status"></div>
            </div>
            <script>
                async function runScan() {
                    document.getElementById('status').innerText = "⏳ Scan triggered...";
                    await fetch('/scan', { method: 'POST' });
                    setTimeout(() => { document.getElementById('status').innerText = "✅ Background scan running."; }, 2000);
                }
            </script>
        </body>
    </html>
    """

@app.post("/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_full_scan)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)