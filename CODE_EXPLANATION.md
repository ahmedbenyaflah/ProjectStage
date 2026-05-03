# CG Mail Journey — Code Explanation Guide

> A complete walkthrough of every important code component in the project.
> Use this to prepare for questions about how the system works.

---

## Table of Contents

1. [Project Architecture Overview](#1-project-architecture-overview)
2. [Infrastructure — Docker Compose](#2-infrastructure--docker-compose)
3. [Backend Configuration](#3-backend-configuration)
4. [Log Parsing — Sent Mail](#4-log-parsing--sent-mail)
5. [Log Parsing — Received Mail](#5-log-parsing--received-mail)
6. [Journey Schema & Elasticsearch Template](#6-journey-schema--elasticsearch-template)
7. [Elasticsearch Client & Bootstrap](#7-elasticsearch-client--bootstrap)
8. [FastAPI Application (main.py)](#8-fastapi-application--mainpy)
9. [Elasticsearch Query Builder](#9-elasticsearch-query-builder)
10. [Authentication System (JWT + bcrypt)](#10-authentication-system--jwt--bcrypt)
11. [Database Layer (PostgreSQL Connection Pool)](#11-database-layer--postgresql-connection-pool)
12. [DNSBL Blacklist Scanner](#12-dnsbl-blacklist-scanner)
13. [Email Alert System](#13-email-alert-system)
14. [Elasticsearch Ingest Pipeline (pipeline.json)](#14-elasticsearch-ingest-pipeline--pipelinejson)
15. [Frontend — React Application](#15-frontend--react-application)
16. [Frontend — Authentication Context](#16-frontend--authentication-context)
17. [Frontend — Protected Routes](#17-frontend--protected-routes)
18. [Frontend — Search Page & Data Normalization](#18-frontend--search-page--data-normalization)
19. [Frontend — Kibana Dashboard Integration](#19-frontend--kibana-dashboard-integration)
20. [Frontend — Blacklist Panel & Email Reports](#20-frontend--blacklist-panel--email-reports)

---

## 1. Project Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Docker Compose                             │
│  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Elasticsearch     │  │   Kibana      │  │  PostgreSQL           │ │
│  │ (port 9200)       │  │  (port 5601)  │  │  (port 5432)          │ │
│  │ Stores mail       │  │  Dashboards   │  │  Stores user accounts │ │
│  │ journeys + DNSBL  │  │  & KPIs       │  │  (email + password)   │ │
│  └──────────────────┘  └──────────────┘  └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
         ▲                        ▲                     ▲
         │                        │                     │
┌────────┴────────────────────────┴─────────────────────┴─────────────┐
│                      FastAPI Backend (port 8000)                     │
│  • /api/search        — query mail journeys                         │
│  • /api/login         — authenticate user (JWT)                     │
│  • /api/signup        — register new user                           │
│  • /api/blacklist/*   — DNSBL scan + email alerts                   │
│  • Background thread  — periodic DNSBL scanning                     │
└─────────────────────────────────────────────────────────────────────┘
         ▲                                          ▲
         │                                          │
┌────────┴──────────────┐              ┌────────────┴──────────────┐
│  Sent/Received Parsers │              │   React Frontend          │
│  (offline scripts)     │              │   (port 3000)             │
│  Read raw .log files   │              │   Search + Dashboard +    │
│  → build journeys      │              │   Blacklist panel         │
│  → bulk index to ES    │              │   Embeds Kibana iframe    │
└────────────────────────┘              └──────────────────────────┘
```

**Data flow in one sentence:** Raw SMTP log files are parsed into "mail journey" documents, bulk-indexed into Elasticsearch, then queried through a JWT-protected FastAPI backend that the React frontend consumes.

---

## 2. Infrastructure — Docker Compose

**File:** `docker-compose.yml`

This file defines the three services that make up the data stack.

```yaml
# docker-compose.yml (key parts)

services:
  es-logs:                                          # Elasticsearch 8.12
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    environment:
      - discovery.type=single-node                  # No cluster, single node
      - xpack.security.enabled=false                # No auth (dev mode)
      - ES_JAVA_OPTS=-Xms1g -Xmx3g                 # JVM heap: 1GB min, 3GB max
    ports:
      - "9200:9200"
    volumes:
      - esdata:/usr/share/elasticsearch/data        # Persistent data

  kibana:                                           # Kibana 8.12 for dashboards
    image: docker.elastic.co/kibana/kibana:8.12.0
    depends_on: [es-logs]
    environment:
      - ELASTICSEARCH_HOSTS=http://es-logs:9200     # Connects to ES via Docker network
    ports:
      - "5601:5601"

  postgres:                                         # PostgreSQL 16 for user auth
    image: postgres:16
    environment:
      POSTGRES_DB: cg_logs
      POSTGRES_USER: cg_user
      POSTGRES_PASSWORD: cg_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data             # Persistent data
```

**Key points to explain:**
- `discovery.type=single-node` — tells ES it doesn't need to discover other cluster nodes.
- `xpack.security.enabled=false` — disables authentication on ES/Kibana for development simplicity.
- Named volumes (`esdata`, `pgdata`) — data survives container restarts.
- Kibana connects to ES through Docker's internal DNS (`http://es-logs:9200`).

---

## 3. Backend Configuration

**File:** `backend_pipeline/config.py`

Centralizes all environment-driven settings. Every module imports from here instead of reading `os.environ` directly.

```python
# config.py — important variables

ES_URL = os.environ.get("ES_URL", "http://localhost:9200")       # Elasticsearch URL
ES_REQUEST_TIMEOUT = int(os.environ.get("ES_REQUEST_TIMEOUT", "600"))

LOG_BASE_PATH = Path("../Log-CG")      # Where raw SMTP logs live (FES01/, MX01/, etc.)

MAX_AUDIT_EDGE_LINES = 25              # Cap stored audit lines per journey
MAX_AUDIT_DOWNSTREAM_LINES = 25

PORT = 8000                             # FastAPI port
DNSBL_SCAN_INTERVAL_SECONDS = 86400     # Once per day by default

DATABASE_URL = "postgresql://cg_user:cg_password@localhost:5432/cg_logs"
```

**Why it matters:** Single source of truth for configuration. Changing an environment variable (e.g., in `.env`) changes the behavior of all modules — parsers, API, and blacklist scanner.

---

## 4. Log Parsing — Sent Mail

**File:** `backend_pipeline/sent_parser.py`

This is one of the most important files. It reads raw CommuniGate SMTP logs and constructs **one Elasticsearch document per mail journey** (one email's full lifecycle).

### How it works — 3 passes:

#### Pass 1: FES (Front-End Servers) — lines 84–201

Reads logs from `FES01/` and `FES02/` folders. For each log line:

```python
# Extract the Queue ID (unique mail identifier) from lines like: QUEUE([12345])
qid_match = re.search(r"\[(\d+)\]", line)
qid = qid_match.group(1)  # e.g., "12345"
```

Each QID becomes one journey document with fields like:
- `sender` — extracted from `from <user@domain.com>`
- `recipients` — extracted from DEQUEUER lines
- `status` — Success, Failed, Discarded, or Pending
- `relayIp` — the IP the mail was relayed to
- `start_time` / `end_time` — first and last timestamps seen

**Relay IP → Server mapping (lines 26-30):**
```python
NEXT_HOP_MAP = {
    "20": ["VIP01", "VIP02"],   # Last octet .20 → VIP servers
    "21": ["GP01", "GP02"],     # Last octet .21 → GP servers
    "22": ["ML01", "ML02"],     # Last octet .22 → ML servers
}
```
When a mail is relayed to IP `x.x.x.20`, we know it went to VIP servers. The `deliveryId` links the FES record to the downstream server logs.

**MX-originated mail filter (line 34):**
```python
_MX_SMTPI_RE = re.compile(r"SMTPI-\d+\(\[?197\.26\.11\.\d{1,3}\]?\).*received", re.IGNORECASE)
```
This regex detects inbound mail that arrived through MX servers (IP range `197.26.11.*`). These are **excluded** from the sent index because they are received mail, not sent mail.

#### Pass 2: Downstream servers (VIP, GP, ML) — lines 202–260

Reads logs from `VIP01/`, `GP01/`, `ML01/`, etc. Uses `delivery_lookup` dict to link downstream IDs back to the original QID:

```python
# delivery_lookup maps: downstream_id → original_qid
if id_match.group(1) in delivery_lookup:
    qid = delivery_lookup[id_match.group(1)]
```

This pass also extracts **Kaspersky anti-spam/virus** results:
```python
if "extfilter(kaspersky)" in line_lower:
    spam_m = re.search(r"X-KAS-Status: (KAS_STATUS_\w+)", line)   # Spam check
    virus_m = re.search(r"X-KAV-Status: (\w+)", line)              # Virus check
    level_m = re.search(r"X-KAS-Level:\s+(\[[X\s]*\])", line)      # Threat level (count of X)
```

#### Pass 3: Finalize & Bulk Index — lines 262–316

```python
finalized = finalize_journey_document(j, ...)  # Normalize fields, cap audit lines
actions.append({"_index": f"mail-journeys-sent-{target_date}", "_id": qid, "_source": finalized})

helpers.bulk(es, actions, chunk_size=200, refresh=True)  # Bulk upload to ES
```

**Key points to explain:**
- **Multi-pass parsing:** Pass 1 builds the base journey from FES, Pass 2 enriches it from downstream servers, Pass 3 uploads.
- **delivery_lookup dictionary:** Links the original Queue ID on FES to the new ID assigned on downstream servers.
- **Daily indices:** Each day creates `mail-journeys-sent-YYYY-MM-DD`, making it easy to manage and query by date.
- **`helpers.bulk()`:** Elasticsearch bulk API — sends hundreds of documents in one HTTP request instead of one-by-one.

---

## 5. Log Parsing — Received Mail

**File:** `backend_pipeline/received_parser.py`

Similar structure to the sent parser, but processes **MX (Mail Exchanger) server** logs for inbound mail.

### Key difference: Kaspersky ID mapping (lines 200–228)

MX logs have a challenge: Kaspersky filter lines don't contain the mail QID directly. Instead, they use an internal ID. The parser handles this with a two-step approach:

```python
# Step 1: When we see "EXTFILTER(kaspersky) out", we learn the mapping
#   det_id (Kaspersky internal ID) → mail_id (Queue ID)
kaspersky_id_map[det_id] = mail_id

# Step 2: Kaspersky "inp" lines arrive BEFORE the mapping is known
#   So we buffer them in pending_kaspersky_lines
pending_kaspersky_lines.setdefault(d_id, []).append(line.strip())

# Step 3: When the mapping arrives, replay buffered lines
if det_id in pending_kaspersky_lines:
    for buffered_line in pending_kaspersky_lines[det_id]:
        process_line(buffered_line, mail_id, ...)
```

### The `process_line` function (lines 52–173)

Processes each log line and updates the journey document. Extracts:
- **Sender** from `header: From:` lines
- **Recipients** from `header: To:`, `header: CC:`, and `envelope: R` lines
- **Kaspersky results** (spam status, virus status, threat level, detection method)
- **Error details** with SMTP error codes (e.g., 550, 421)

**Key points to explain:**
- **Buffering mechanism:** Kaspersky results arrive before we know which mail they belong to, so we buffer and replay.
- **Received index:** Creates `mail-journeys-received-YYYY-MM-DD` (separate from sent).
- **Document ID:** Uses `{server}-{qid}` instead of just `qid`, because the same QID can appear on different MX servers.

---

## 6. Journey Schema & Elasticsearch Template

**File:** `backend_pipeline/journey_schema.py`

Defines the **Elasticsearch index template** (the "schema") and the document normalization logic.

### Index Template (lines 24–85)

```python
def mail_journey_index_template_body():
    return {
        "index_patterns": ["mail-journeys-sent-*", "mail-journeys-received-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,      # Single shard (small dataset per day)
                "number_of_replicas": 0,     # No replicas (dev environment)
            },
            "mappings": {
                "properties": {
                    "qid":    {"type": "keyword"},              # Exact match (filter/aggregate)
                    "sender": {"type": "text", "fields": {      # Full-text search + exact match
                                 "keyword": {"type": "keyword"}}},
                    "status": {"type": "keyword"},
                    "start_time": {"type": "date", "format": "..."},  # Sortable date
                    "duration_seconds": {"type": "float"},
                    "audit": {"type": "object", "enabled": False},    # NOT indexed (saves space)
                }
            }
        }
    }
```

**Important mapping choices:**
- `keyword` — for exact match and aggregations (Kibana pie charts, bar charts).
- `text` with `.keyword` sub-field — enables both full-text search (wildcard) AND exact aggregations.
- `audit: enabled: False` — raw log lines are stored in `_source` (visible in UI) but NOT indexed (saves disk and CPU).

### Document Finalization (lines 147–216)

```python
def finalize_journey_document(doc, *, max_edge_lines, max_downstream_lines):
    out["sender_domain"] = _extract_domain(out.get("sender"))    # "user@orange.tn" → "orange.tn"
    out["recipient_domains"] = [...]                              # All unique recipient domains
    out["kaspersky_level"] = coerce_kaspersky_level_to_int(out)   # "[XXX]" → 3
    audit["fes_lines"] = edge[:max_edge_lines]                    # Cap at 25 lines
    out["audit_metrics"] = {                                       # Store full counts separately
        "edge_line_count": edge_full,
        "downstream_line_count": down_full,
    }
```

**Key points to explain:**
- **`finalize_journey_document`** is the last step before indexing — it normalizes timestamps, extracts domains, converts Kaspersky level from string `"[XXX]"` to integer `3`, and caps audit lines.
- **`audit_metrics`** — stores the *real* line counts even though audit arrays are capped, so Kibana can chart "how many log lines per journey" without scanning text.

---

## 7. Elasticsearch Client & Bootstrap

**File:** `backend_pipeline/es_infra.py`

Simple but important: creates a singleton ES client and installs the index template on startup.

```python
_es_client = None

def get_elasticsearch():
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(config.ES_URL, request_timeout=config.ES_REQUEST_TIMEOUT)
    return _es_client

def ensure_mail_journey_template(es):
    body = mail_journey_index_template_body()
    client.indices.put_index_template(
        name="cg-mail-journeys-v1",
        index_patterns=body["index_patterns"],
        template=body["template"],
        priority=500,
    )
```

**Key points:**
- **Singleton pattern** — only one ES connection is created, reused everywhere.
- **`put_index_template`** — installs the template so any new `mail-journeys-*` index automatically gets the correct mappings.
- Called on API startup and before each parser run.

---

## 8. FastAPI Application (main.py)

**File:** `backend_pipeline/main.py`

The central API server. Key components:

### CORS Middleware (lines 37–42)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Accept requests from any origin (React on port 3000)
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Necessary because the React frontend (port 3000) talks to the API (port 8000) — different origins.

### Startup: DNSBL Background Thread (lines 86–126)

```python
@app.on_event("startup")
def startup():
    ensure_mail_journey_template(es)   # Install ES template
    init_db()                          # Create users table in PostgreSQL

    # Start background DNSBL scan loop
    def _loop():
        while not _dnsbl_stop.is_set():
            summary = run_dnsbl_scan(es=es)
            # Sleep with 1-second resolution for clean shutdown
            for _ in range(interval):
                if _dnsbl_stop.is_set(): return
                time.sleep(1)

    _dnsbl_thread = threading.Thread(target=_loop, daemon=True)
    _dnsbl_thread.start()
```

**Why a daemon thread?** Runs DNSBL scans periodically (default: daily) without blocking the API. The `_dnsbl_stop` event allows clean shutdown.

### JWT Authentication Dependency (lines 131–137)

```python
async def get_current_user(credentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload
```
Used as `Depends(get_current_user)` on protected endpoints — FastAPI automatically extracts the Bearer token from the Authorization header, decodes it, and rejects invalid tokens.

### Search Endpoint (lines 155–237)

```python
@app.get("/api/search")
async def search_mail(
    date: str = Query(...),           # Required: YYYY-MM-DD
    sender: str | None = Query(None),
    direction: str | None = Query(None),  # 'sent', 'received', or both
    page: int = Query(1, ge=1),
    _user: dict = Depends(get_current_user),  # JWT required
):
    # 1. Determine which indices to query
    if dir_lower == "sent":
        indices_to_query = [f"mail-journeys-sent-{date}"]
    elif dir_lower == "received":
        indices_to_query = [f"mail-journeys-received-{date}"]
    else:
        indices_to_query = [sent_index, received_index]  # Both

    # 2. Build Elasticsearch query
    must_clauses, filter_clauses = build_journey_query_clauses(...)

    # 3. Execute search with pagination
    response = es.search(
        index=",".join(active_indices),
        body={"query": query, "from": start_from, "size": size, "sort": [{"start_time": "asc"}]},
    )

    # 4. Normalize results and return
    results = [_normalize_hit_source(hit["_source"]) for hit in response["hits"]["hits"]]
```

**Key points to explain:**
- **Multi-index search:** Can query both sent and received indices simultaneously using comma-separated index names.
- **Pagination:** `from` parameter = `(page - 1) * size` to skip previous pages.
- **`_normalize_hit_source`** — aligns legacy document shapes (e.g., renames `mx_lines` → `fes_lines`).

### Blacklist Endpoints (lines 239–335)

Three endpoints for DNSBL management:
- `POST /api/blacklist/scan` — trigger an on-demand scan, return LISTED results.
- `GET /api/blacklist/listed` — query ES for currently blacklisted IPs.
- `POST /api/blacklist/email` — send an HTML email report of blacklisted servers.

---

## 9. Elasticsearch Query Builder

**File:** `backend_pipeline/query_builder.py`

Translates user search filters into Elasticsearch Query DSL.

### Wildcard Search for Sender/Recipient (lines 61–85)

```python
if sender:
    must_clauses.append({
        "query_string": {
            "query": f"*{escape_query_string(s)}*",     # Wildcard: *ahmed*
            "fields": ["sender", "sender.keyword"],
            "analyze_wildcard": True,
        }
    })
```
Uses `query_string` with wildcards so searching "ahmed" matches "ahmed@orange.tn", "bigahmed@gmail.com", etc.

### Filter Clauses (lines 90–118)

```python
if status and status.lower() != "all":
    filter_clauses.append({"term": {"status": status.title()}})    # Exact match

if min_duration is not None or max_duration is not None:
    filter_clauses.append({"range": {"duration_seconds": {"gte": min_duration, "lte": max_duration}}})

if start_time or end_time:
    filter_clauses.append({"range": {"start_time": {"gte": f"{date} {start_norm}", ...}}})
```

**Key points:**
- **`must` vs `filter`:** `must` clauses affect relevance scoring, `filter` clauses don't (faster, cached by ES).
- **`term`** — exact keyword match (no analysis). Used for status, spam_status, etc.
- **`range`** — numeric or date range. Used for duration and time window filtering.
- **`escape_query_string`** — escapes special characters (`+`, `-`, `*`, `?`, etc.) so user input doesn't break the query.

---

## 10. Authentication System (JWT + bcrypt)

**File:** `backend_pipeline/auth.py`

### Password Hashing (lines 40–46)

```python
def hash_password(password: str) -> str:
    pwd_bytes = _truncate_password_for_bcrypt(password)  # bcrypt limit: 72 bytes
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("ascii")
```
- **bcrypt** — intentionally slow hashing algorithm that makes brute-force attacks impractical.
- **Salt** — random value mixed with the password so identical passwords produce different hashes.
- **72-byte limit** — bcrypt silently ignores bytes beyond 72, so we explicitly truncate.

### JWT Token Creation (lines 61–68)

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=1440)  # 24 hours
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
```
- **JWT (JSON Web Token)** — a self-contained token with user info (`sub`: user ID, `email`) and expiration.
- **HS256** — HMAC-SHA256 symmetric signing. The server signs and verifies with the same `SECRET_KEY`.
- Token contains: `{"sub": "1", "email": "user@test.com", "exp": 1713700000}`.

### Login Flow (lines 116–139)

```python
def login(email, password):
    # 1. Query PostgreSQL for user by email
    cur.execute("SELECT id, password_hash FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    # 2. Verify password against stored hash
    if not verify_password(password, row[1]):
        return False, "Invalid email or password"
    # 3. Create and return JWT token
    token = create_access_token({"sub": str(row[0]), "email": email})
    return True, token
```

---

## 11. Database Layer (PostgreSQL Connection Pool)

**File:** `backend_pipeline/database.py`

### Thread-Safe Connection Pool (lines 33–56)

```python
def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:                    # Thread lock prevents race conditions
        if _pool is not None:           # Double-checked locking
            return _pool
        _pool = psycopg2.pool.ThreadedConnectionPool(
            POOL_MIN_CONN,              # Min 2 connections
            POOL_MAX_CONN,              # Max 20 connections
            DATABASE_URL,
        )
```

**Why a connection pool?**
- Creating a new database connection for every request is expensive (~50ms).
- A pool keeps connections open and reuses them (~0ms).
- `ThreadedConnectionPool` is safe for FastAPI's multi-threaded environment.

### Pooled Connection Wrapper (lines 59–86)

```python
class _PooledConnectionWrapper:
    def close(self):
        self._pool.putconn(self._conn)  # Returns to pool instead of actually closing
```
When code calls `conn.close()`, the connection goes back to the pool — not destroyed.

### Table Creation (lines 100–119)

```python
def init_db():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
```
Called on API startup. `IF NOT EXISTS` makes it safe to run multiple times.

---

## 12. DNSBL Blacklist Scanner

**File:** `backend_pipeline/blacklist_scan.py`

Checks whether the company's mail server IPs are blacklisted on public DNS-based Blackhole Lists.

### How DNSBL Works (lines 60–80)

```python
def _check_one(ip: str, dnsbl: str, timestamp: datetime) -> dict:
    reverse_ip = ".".join(reversed(ip.split(".")))    # "196.203.232.133" → "133.232.203.196"
    query = f"{reverse_ip}.{dnsbl}"                    # "133.232.203.196.zen.spamhaus.org"

    try:
        dns.resolver.resolve(query, "A")               # If it resolves → IP is LISTED
        doc["dnsb_status"] = "LISTED"
    except dns.resolver.NXDOMAIN:                      # NXDOMAIN → IP is CLEAN
        pass
```

**The DNSBL protocol:**
1. Reverse the IP octets: `196.203.232.133` → `133.232.203.196`
2. Append the blacklist domain: `133.232.203.196.zen.spamhaus.org`
3. Do a DNS A record lookup:
   - **Resolves** (returns an IP) → the IP is **blacklisted**
   - **NXDOMAIN** (not found) → the IP is **clean**

### Parallel Scanning with Bulk Index (lines 83–122)

```python
def run_dnsbl_scan(*, es, hosts=DEFAULT_HOSTS, dnsbls=DEFAULT_DNSBLS):
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(_check_one, ip, dnsbl, timestamp)
            for ip in hosts_list          # 13 IPs
            for dnsbl in dnsbls_list      # 5 blacklists = 65 checks
        ]
        results = [f.result() for f in futures]

    actions = [{"_index": INDEX_NAME, "_source": doc} for doc in results]
    bulk(es, actions, raise_on_error=False)  # Single bulk request to ES
```

**Key points:**
- **ThreadPoolExecutor** — runs 65 DNS queries in parallel (20 threads) instead of sequentially.
- **Bulk index** — writes all 65 results to ES in one HTTP request.
- Scans 13 mail server IPs against 5 blacklist providers = 65 total checks.

---

## 13. Email Alert System

**File:** `backend_pipeline/email_alerts.py`

Sends an HTML email report of blacklisted servers via Gmail SMTP.

```python
def send_blacklist_digest_email(*, listed_rows):
    # Build HTML table with IP, blacklist name, timestamp
    rows_html = ""
    for r in listed_rows:
        rows_html += f"<tr><td>{r['ip']}</td><td>{r['blacklist']}</td>...</tr>"

    msg = EmailMessage()
    msg["Subject"] = f"[CG Logs] Blacklisted servers detected ({len(listed_rows)})"
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)
```

**Key points:**
- Uses **SMTP_SSL** (port 465) — encrypted connection to Gmail.
- **Gmail App Password** — not the regular password; a 16-character app-specific password.
- Called as a **FastAPI BackgroundTask** so the API response returns immediately without waiting for email delivery.

---

## 14. Elasticsearch Ingest Pipeline (pipeline.json)

**File:** `pipeline.json`

An alternative approach to parsing — this is an **Elasticsearch ingest pipeline** that processes raw log lines at index time using Grok patterns.

```json
{
  "cg-mail-logs-pipeline": {
    "processors": [
      {
        "grok": {                                    // Extract server name and date from file path
          "field": "file",
          "patterns": [".*/%{WORD:source_server}/%{YEAR}-%{MONTHNUM}-%{MONTHDAY}.*"]
        }
      },
      {
        "grok": {                                    // Extract QID, sender, time from log message
          "field": "message",
          "patterns": [
            "%{TIME:time}.*QUEUE\\(\\[%{NUMBER:qid}\\]\\)\\s+from\\s+<%{DATA:sender}>.*",
            "%{TIME:time}.*DEQUEUER\\s+\\[%{NUMBER:qid}\\].*"
          ]
        }
      },
      {
        "date": {                                    // Parse timestamp string into ES date field
          "field": "timestamp_str",
          "formats": ["yyyy-MM-dd HH:mm:ss.SSS"],
          "timezone": "Africa/Tunis"
        }
      }
    ]
  }
}
```

**Key points:**
- **Grok** — regex-based pattern matching built into Elasticsearch. `%{WORD:source_server}` captures a word into field `source_server`.
- **Script processor** — runs Painless code to combine fields: `ctx.log_date = ctx.log_year + "-" + ctx.log_month`.
- **Date processor** — converts string timestamps to proper ES date type for time-based queries.
- This pipeline is used for raw line-level indexing (Kibana Discover), while the Python parsers create journey-level documents.

---

## 15. Frontend — React Application

**File:** `logs_filter_frontend_elastic/src/App.js`

The app uses **React Router v7** for client-side navigation and wraps everything in an `AuthProvider` for JWT management.

```jsx
function App() {
  return (
    <AuthProvider>                                    {/* Global auth state */}
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/search" element={
            <ProtectedRoute><SearchPage /></ProtectedRoute>       {/* JWT required */}
          } />
          <Route path="/dashboard" element={
            <ProtectedRoute><DashboardPage /></ProtectedRoute>    {/* JWT required */}
          } />
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

**Key points:**
- `/login` and `/signup` are public routes.
- `/search` and `/dashboard` are wrapped in `<ProtectedRoute>` — redirects to login if no valid token.
- `"/"` and any unknown route (`"*"`) redirect to `/dashboard`.

---

## 16. Frontend — Authentication Context

**File:** `logs_filter_frontend_elastic/src/context/AuthContext.js`

Uses React's **Context API** to share authentication state across all components without prop drilling.

```jsx
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [email, setEmail] = useState(() => localStorage.getItem(EMAIL_KEY));

  const login = (t, e) => {
    localStorage.setItem(TOKEN_KEY, t);    // Persist token across page refreshes
    setToken(t);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  };

  const isAuthenticated = !!token;         // true if token exists

  return (
    <AuthContext.Provider value={{ token, email, login, logout, isAuthenticated, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

// Any component can access auth state:
export function useAuth() {
  return useContext(AuthContext);
}
```

**Key points:**
- **localStorage** — JWT persists even if the user closes the browser tab.
- **`useAuth()` hook** — any component can call `const { token, logout } = useAuth()` to access auth state.
- `isAuthenticated` is a derived boolean: `!!token` — truthy if token exists.

---

## 17. Frontend — Protected Routes

**File:** `logs_filter_frontend_elastic/src/components/ProtectedRoute.js`

A wrapper component that blocks access to pages if the user isn't authenticated.

```jsx
export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <LoadingSpinner />;

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;   // Render the actual page
}
```

**Key points:**
- Shows a loading spinner while auth state initializes (prevents flash of login page).
- Saves the attempted URL in `state.from` so the login page could redirect back after login.
- `replace` prevents the login redirect from appearing in browser history.

---

## 18. Frontend — Search Page & Data Normalization

**File:** `logs_filter_frontend_elastic/src/components/SearchPage.js`

### The `mapItem` function (lines 65–149)

The most important frontend function — normalizes raw ES documents from both parsers into a consistent shape:

```javascript
function mapItem(item, idx, currentPage, dateNorm) {
  // Status normalization: "Failed" → "Rejected" (UI label)
  let displayStatus = 'Pending';
  if (s === 'success') displayStatus = 'Success';
  else if (s === 'failed') displayStatus = 'Rejected';

  // Kaspersky level: handles both integer (from finalize) and legacy string "[XXX]"
  const kasperskyLevel = normalizeKasperskyLevelXCount(item);

  // Error details: handles both sent_parser and received_parser shapes
  const errorMessage = ed?.full_message || ed?.message || '';

  return {
    id: qidValue,
    sender: item.sender,
    recipients: item.recipients,
    direction: item.direction,    // "sent" or "received"
    status: displayStatus,
    auditFesLines: fesLines,      // Raw log lines for detail view
    kasperskySpam: item.kaspersky_spam_status,
    errorCode, errorMessage,
    rawDocument: item,            // Keep original for debugging
  };
}
```

**Why this matters:** The sent parser and received parser produce slightly different field names. `mapItem` normalizes them so `ResultsList` and `DetailsPanel` don't need to know which parser produced the document.

### Search Flow (lines 163–228)

```javascript
const runSearch = async (filters, pageOverride) => {
  const params = new URLSearchParams();
  params.append('date', dateNorm);
  if (filters.sender) params.append('sender', filters.sender);
  if (filters.direction !== 'both') params.append('direction', filters.direction);
  params.append('page', String(currentPage));

  const res = await fetch(`${API_BASE}/api/search?${params.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (res.status === 401) { logout(); navigate('/login'); return; }

  const data = await res.json();
  const mapped = data.results.map((item, idx) => mapItem(item, idx, currentPage, dateNorm));
  setResults(mapped);
};
```

**Key points:**
- Sends the JWT as a `Bearer` token in the `Authorization` header.
- If the server returns 401 (expired/invalid token), automatically logs out and redirects.
- Uses `URLSearchParams` to build the query string cleanly.

---

## 19. Frontend — Kibana Dashboard Integration

**File:** `logs_filter_frontend_elastic/src/components/KibanaDashboard.jsx`

Embeds a Kibana dashboard inside an iframe with dynamic time range control.

### Rison Encoding for Kibana (lines 17–29)

```jsx
import { encode as risonEncode } from 'rison-node';

function buildIframeSrc({ baseUrl, time, refreshInterval }) {
  // Kibana uses Rison encoding (a compact JSON format) for URL state
  const risonGlobal = risonEncode({ time, refreshInterval });
  // Example: (time:(from:'now-30d',to:'now'),refreshInterval:(pause:!f,value:1000))

  const params = new URLSearchParams(queryString);
  params.set('_g', risonGlobal);         // _g = Kibana "global state" parameter
  return `${beforeQuery}?${params.toString()}`;
}
```

**What is Rison?** A URL-safe encoding of JSON that Kibana uses in its URLs. Instead of `{"time":{"from":"now-30d"}}`, Rison encodes it as `(time:(from:'now-30d'))`.

### Time Range Controls (lines 38–71)

```jsx
const quickRanges = [
  { id: 'last7d', from: 'now-7d', to: 'now' },
  { id: 'last30d', from: 'now-30d', to: 'now' },
  { id: 'last90d', from: 'now-90d', to: 'now' },
];

// Custom range uses absolute ISO dates
if (timeMode === 'custom') {
  return { from: customFrom.toISOString(), to: customTo.toISOString() };
}
```

When the user picks a time range, the iframe URL is rebuilt with the new `_g` parameter, and Kibana automatically refreshes to show data for that period.

**Live Mode** — sets `refreshInterval.pause` to `false` with a 1-second interval, making Kibana auto-refresh continuously.

---

## 20. Frontend — Blacklist Panel & Email Reports

**File:** `logs_filter_frontend_elastic/src/components/Navbar.js`

The navigation bar includes a **blacklist panel** that:

### Load Blacklisted Servers (lines 42–59)

```javascript
const loadBlacklist = async () => {
  const res = await fetch(`${API_BASE}/api/blacklist/listed`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  const data = await res.json();
  setBlacklisted(data.listed);    // Array of {ip, blacklist, @timestamp}
  setBlacklistOpen(true);         // Open the panel
};
```

### Send Email Report (lines 62–83)

```javascript
const sendBlacklistEmail = async () => {
  const res = await fetch(`${API_BASE}/api/blacklist/email`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  const data = await res.json();
  if (data.sent) setEmailStatus(`Email sent (${data.count} entries)`);
};
```

Triggers the backend to send an HTML email with all currently blacklisted IPs. The email is sent asynchronously (FastAPI `BackgroundTasks`) so the API responds immediately.

---

## Quick Reference: File Map

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Infrastructure: ES + Kibana + PostgreSQL |
| `backend_pipeline/config.py` | Centralized environment configuration |
| `backend_pipeline/main.py` | FastAPI app: API endpoints + DNSBL background thread |
| `backend_pipeline/sent_parser.py` | Parse FES/VIP/GP/ML logs → sent journey documents |
| `backend_pipeline/received_parser.py` | Parse MX logs → received journey documents |
| `backend_pipeline/journey_schema.py` | ES index template + document normalization |
| `backend_pipeline/es_infra.py` | ES client singleton + template bootstrap |
| `backend_pipeline/query_builder.py` | Build ES Query DSL from search filters |
| `backend_pipeline/auth.py` | JWT creation/verification + bcrypt password hashing |
| `backend_pipeline/database.py` | PostgreSQL connection pool + users table |
| `backend_pipeline/blacklist_scan.py` | DNSBL scanning (DNS lookups) + ES bulk indexing |
| `backend_pipeline/email_alerts.py` | Send HTML email alerts via Gmail SMTP |
| `pipeline.json` | ES ingest pipeline (Grok patterns for raw logs) |
| `src/App.js` | React router setup + auth provider wrapper |
| `src/context/AuthContext.js` | React Context for JWT state management |
| `src/components/ProtectedRoute.js` | Route guard: redirect to login if unauthenticated |
| `src/components/SearchPage.js` | Search UI + `mapItem` data normalization |
| `src/components/KibanaDashboard.jsx` | Embedded Kibana iframe with Rison-encoded time range |
| `src/components/Navbar.js` | Navigation + blacklist panel + email report trigger |
