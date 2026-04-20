# MASTER_PROJECT_INFO — CG Mail Journey & Log Intelligence Platform

Technical reference for the PFE report: end-to-end problem statement, architecture, mail-journey correlation logic, DNSBL security monitoring, stack versions, and performance characteristics. This document is aligned with the implementation under `backend_pipeline/` and `docker-compose.yml`.

---

## 1. The Problem

### Operational context

Corporate SMTP traffic is distributed across a **large, heterogeneous fleet** of edge and internal servers. In this project the log corpus is organized by role and host under a common root (`LOG_BASE_PATH`, defaulting to `Log-CG/`):

| Role | Typical folders (examples) |
|------|----------------------------|
| Front-end / submission (FES) | `FES01`, `FES02` |
| VIP routing | `VIP01`, `VIP02` |
| General population / GP | `GP01`, `GP02` |
| Mail layer | `ML01`, `ML02` |
| Inbound (MX) | `MX01` … `MX04` (`received_parser.py` scans `MX01`–`MX04`) |

Each host produces **plain-text daily (and sometimes time-sliced) `.log` files**. A single logical email does not live in one file: it leaves traces on **FES** (queue, relay, Kaspersky hand-off), may appear on **VIP / GP / ML** with **different numeric identifiers** after relay, and inbound paths are captured on **MX** with yet another line grammar.

### Why manual investigation fails

1. **Volume and fragmentation** — Operators must open many files across **20+ server directories**, search for queue IDs, delivery IDs, or timestamps, and mentally stitch timelines. Error rates and partial deliveries multiply the number of lines to reconcile per incident.

2. **Identifier churn** — On the sent path, Postfix-style **`[qid]`** brackets identify the message on FES, but after a successful `got:250` relay the downstream system may log a **separate numeric delivery ID**. Without automated linkage, support cannot answer “what happened to this message end-to-end?” from FES alone.

3. **No unified KPI layer** — Counting failures by SMTP code, spam vs clean, average latency, or top problematic flows requires repeated `grep`/`awk` or ad-hoc scripts, not a shared, authenticated UI.

4. **Infrastructure blind spots** — Outbound IP reputation (DNS blocklists) affects deliverability but is **orthogonal** to SMTP log text; checking dozens of IPs against multiple DNSBLs manually does not scale.

The platform addresses this by **normalizing journeys into Elasticsearch documents**, exposing **search and aggregations via FastAPI**, and optionally **surfacing the same indices in Kibana** while a **React** app (see `backend_pipeline/readme.md`: `logs_filter_frontend_elastic`) provides a tailored operator workflow.

---

## 2. Architecture

### High-level data flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Raw logs (per-server .log trees: FES*, VIP*, GP*, ML*, MX*)            │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Python batch parsers                                                    │
│  • sent_parser.py      → mail-journeys-sent-YYYY-MM-DD                   │
│  • received_parser.py  → mail-journeys-received-YYYY-MM-DD               │
│  (stream files, regex extract, merge per journey, finalize schema)       │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │  elasticsearch.helpers.bulk(...)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Elasticsearch 8.12.0                                                    │
│  • Composable index template `cg-mail-journeys-v1` (journey_schema.py)   │
│  • Daily indices; keyword/date mappings for filters, sorts, aggs        │
│  • Parallel index `dnsbl-checks` for blacklist probe results               │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│  FastAPI (main)  │    │  Kibana 8.12.0       │    │  React SPA           │
│  JWT + Postgres  │    │  Lens / Discover     │    │  (separate package;  │
│  /api/search,    │    │  on mail-journeys-*  │    │   polls API — see   │
│  /api/blacklist/*│    │                      │    │   Performance)      │
└──────────────────┘    └──────────────────────┘    └──────────────────────┘
```

### Component responsibilities

| Layer | Implementation | Responsibility |
|-------|----------------|----------------|
| **Ingestion** | `sent_parser.py`, `received_parser.py` | Walk configured directories, parse lines, build one JSON document per journey (sent) or per MX journey key (received), cap audit arrays, call `finalize_journey_document()`. |
| **Schema / template** | `journey_schema.py`, `es_infra.py` | Single composable template for `mail-journeys-sent-*` and `mail-journeys-received-*`; `audit` stored but not indexed; `audit_metrics` for chart-friendly counts. |
| **API** | `main.py`, `query_builder.py` | Authenticated search (`/api/search`), DNSBL scan/listing (`/api/blacklist/*`), optional email digest. KPI-style charts live in Kibana on the same indices. |
| **Auth** | Postgres + JWT (`database.py`, `auth.py`) | Sign-up/login; bearer token for API routes. |
| **Infra (containers)** | `docker-compose.yml` | Elasticsearch and Kibana **8.12.0**, Postgres **16** for local/dev stack. |

### Concurrency note (accurate to code)

- **Journey parsers** run as **single-threaded** Python processes that sequentially read log files. Parallelism in production is typically achieved by **running multiple processes** (e.g. per date or per host) or by Elasticsearch’s internal handling of bulk requests—not by `threading` inside `sent_parser` / `received_parser`.
- **DNSBL scanning** (`blacklist_scan.py`) uses **`concurrent.futures.ThreadPoolExecutor` with `max_workers=20`** to run many DNS lookups in parallel across the `(IP × DNSBL)` matrix.

---

## 3. Mail Journey Logic

### 3.1 Queue ID (`qid`) on the sent path

On **FES**, almost every relevant line contains a Postfix-style queue id in **square brackets**, e.g. `[123456]`. The parser uses:

```python
qid_match = re.search(r"\[(\d+)\]", line)
```

All state for that message on FES is aggregated under `journeys[qid]`: sender, recipients, timestamps, relay IP, audit lines, provisional status, etc.

### 3.2 `deliveryId` and cross-server correlation (`NEXT_HOP_MAP`)

When FES logs a successful SMTP handoff to a **mapped next hop**, the line may include:

- Relay **IPv4** (last octet encodes which downstream family is used).
- **`got:250 <deliveryId>`** — a **long numeric delivery identifier** used on VIP/GP/ML logs.

The code maps **last octet of the relay IP** to candidate downstream host names:

```26:30:backend_pipeline/sent_parser.py
NEXT_HOP_MAP = {
    "20": ["VIP01", "VIP02"],
    "21": ["GP01", "GP02"],
    "22": ["ML01", "ML02"],
}
```

When the relay IP’s last octet is in `NEXT_HOP_MAP`, the parser:

1. Sets journey `status` to **`Pending`** (handed off; outcome not yet known on FES).
2. Extracts **`deliveryId`** and fills **`delivery_lookup[deliveryId] = qid`**.

Second pass: for **VIP01, VIP02, GP01, GP02, ML01, ML02** log files, any line whose `[...]` id matches a key in **`delivery_lookup`** is attributed to the **original FES `qid`**, merging **Kaspersky** fields, **serverPath**, outcomes, and **mapped_lines** audit entries into the same journey document.

Thus **one Elasticsearch document** (id = `qid` for sent) represents the **correlated path** FES → VIP/GP/ML, even though downstream logs use a **different numeric id**.

### 3.3 Received (MX) path: `qid` and Kaspersky `detailsid`

Inbound parsing (`received_parser.py`) keys journeys primarily by **`[qid]`** on MX lines. Kaspersky **EXTFILTER** lines may arrive with an internal **`inp(...): <detailsid>`** before the queue id is known; the parser maintains:

- **`kaspersky_id_map`**: links `detailsid` → `mail_id` (queue id) when `EXTFILTER(kaspersky) out` lines appear.
- **`pending_kaspersky_lines`**: buffers `inp` lines until the link exists, then **replays** them into the correct journey.

Documents are indexed with **`_id = f"{serverPath[0]}-{qid}"`** to avoid collisions when the same numeric id appears on different MX hosts.

### 3.4 Status model (sent parser)

| Status | Meaning (sent path) |
|--------|----------------------|
| **Pending** | Still in flight: relayed to mapped hop (`NEXT_HOP_MAP`) without final downstream outcome, or recipients known but none marked successful yet. |
| **Success** | All known recipients have a successful terminal signal (per recipient accounting). |
| **Partial Success** | Some recipients succeeded, some not (`0 < num_success < num_total`). |
| **Failed** | Explicit failure/rejection on FES or mapped server; **`error_details`** may include SMTP-style **4xx/5xx** code and message. |
| **Discarded** | Policy discard / automatic rules / “discarded” in log text. |

**FES** sets Failed/Discarded from phrases like `failed:`, `rejected`, `discarded`, `delivered via automatic rules`. **Mapped servers** can clear `error_details` on success signals (`2.0.0 ok`, `delivered`, `relayed via`, `batch relayed`) or set Failed/Discarded similarly.

**Final normalization** after scanning all logs: if status is still **`Pending` or `Success`**, recipient counts are used to upgrade **`Pending` → Success / Partial Success / Pending`** as appropriate.

### 3.5 Status model (received parser)

Received journeys default to **`Success`** and move to **`Discarded`** or **`Failed`** when matching failure/rejection/discard patterns appear in MX lines. **`error_details`** captures SMTP code and message fragments when present.

### 3.6 Duration and timestamps

- Timestamps are parsed from **`HH:MM:SS.mmm`** on each line, combined with the **batch date** (`YYYY-MM-DD`).
- **`duration_seconds`** is the difference between first and last parsed time for that journey (rounded to milliseconds).

### 3.7 Document finalization

`finalize_journey_document()` applies **schema_version**, normalizes Kaspersky fields, **caps** `audit.fes_lines` and `audit.mapped_lines` (defaults **25** lines each, configurable via env), fills **`audit_metrics`** with full vs stored line counts, and normalizes **date** fields for Elasticsearch.

---

## 4. Infrastructure Security: DNSBL Integration & Alerts

### 4.1 What is checked

`blacklist_scan.py` probes a configurable list of **outbound / infrastructure IPs** against multiple **DNS blocklists** (defaults include Spamhaus ZEN, SpamCop, Sorbs, UCEPROTECT, Redhawk, etc.). For each IP, the IPv4 address is **reversed** and queried as `*.dnsbl` (standard DNSBL DNS technique).

### 4.2 Result encoding

Each check is indexed into Elasticsearch index **`dnsbl-checks`** with:

- **`ip`** (mapped as ES `ip`)
- **`blacklist`** (keyword)
- **`dnsb_status`** — `LISTED`, `CLEAN`, or `ERROR` (field name avoids clashing with mail-journey **`status`**)
- **`@timestamp`**

### 4.3 Concurrency

`run_dnsbl_scan()` submits **all (IP × DNSBL) pairs** to a **`ThreadPoolExecutor(max_workers=20)`**, so DNS latency is overlapped across many queries.

### 4.4 API integration (`main.py`)

On application **startup**:

1. **`ensure_dnsbl_index(es)`** creates the index if missing.
2. A **daemon thread** runs **`run_dnsbl_scan(es)`** immediately, then sleeps until **`DNSBL_SCAN_INTERVAL_SECONDS`** (default **300** seconds / 5 minutes). Sleep is implemented as **one-second `time.sleep` slices** so shutdown can stop within ~1s.

### 4.5 Alerting support

- **`GET /api/blacklist/listed`** returns distinct **LISTED** rows for the React/Kibana operator UI.
- **`POST /api/blacklist/email`** (authenticated) schedules **`send_blacklist_digest_email()`** via FastAPI **BackgroundTasks**: HTML table of IP, blacklist, timestamp, sent through **Gmail SMTP over SSL** (`smtp.gmail.com:465`) using **`SENDER_EMAIL`**, **`RECEIVER_EMAIL`**, **`EMAIL_PASSWORD`** (app password). If env vars are missing, the endpoint returns **400** with a clear configuration error.

This gives **support** both **live visibility** in the app and **push notification** to a mailbox when operators trigger or automate digest sends.

---

## 5. Technical Stack (versions & rationale)

| Component | Version / constraint | Notes |
|-----------|----------------------|--------|
| **Elasticsearch** | **8.12.0** (`docker-compose.yml`) | Single-node dev profile; security disabled for local simplicity (`xpack.security.enabled=false`). |
| **Kibana** | **8.12.0** | Same stack line as ES; `ELASTICSEARCH_HOSTS=http://es-logs:9200`. |
| **Postgres** | **16** | Database `cg_logs`; user auth storage. |
| **Python client** | `elasticsearch>=8.12.0,<9.0.0` | Async-compatible cluster client used synchronously in API and parsers. |
| **FastAPI** | `>=0.109.0,<1.0.0` | OpenAPI, dependency-injected auth, `BackgroundTasks`. |
| **Uvicorn** | `>=0.27.0` | ASGI server. |
| **dnspython** | `>=2.6.1` | DNSBL queries. |

### Why FastAPI + React beyond “only Kibana”?

1. **Product workflow** — Support needs **guided filters** (date, direction, sender, recipient, `qid`, status, spam/virus, duration, time-of-day) and **pagination** exposed as a **stable JSON contract** (`/api/search`, `/api/blacklist/*`) without writing KQL/Lucene for every ticket; **Kibana** covers ad-hoc KPIs on the same indices.

2. **Security boundary** — **JWT + Postgres** application users are **not** the same as Elasticsearch/Kibana’s (disabled) local stack security model; a dedicated API allows **fine-grained access** and future hardening (rate limits, audit logs, row-level rules) independent of Kibana spaces.

3. **Operational actions** — **Blacklist digest email** and **custom KPIs** (e.g. `avg_duration_by_status`, `top_error_codes`) are first-class API features, not one-off saved objects.

4. **Kibana remains valuable** — **Lens**, **Discover**, and ad-hoc exploration on `mail-journeys-*` complement the app; the **index template** (`journey_schema.py`) is explicitly **Kibana-friendly** (keyword subfields, `audit_metrics`, date fields).

---

## 6. Performance

### 6.1 Bulk indexing (`helpers.bulk`)

Both parsers flush documents with:

```python
helpers.bulk(es, actions, chunk_size=200, refresh=True)
```

- **`chunk_size=200`**: batches **200 operations** per HTTP request to balance request size and memory.
- **`refresh=True`**: after each bulk call, affected shards **refresh** so documents are **immediately searchable** (important right after batch jobs; trades some extra cluster load for operator visibility).

### 6.2 Index refresh interval (template)

The composable template sets **`refresh_interval`: `"5s"`** for steady-state indexing/search tradeoff on daily indices. Bulk `refresh=True` overrides behavior for those bulk responses.

### 6.3 Near–real-time UI: 1-second refresh

For **live monitoring** (blacklist widgets or search results), the intended React client pattern is to **poll** `GET /api/blacklist/listed` (and trigger `POST /api/blacklist/scan` when the operator refreshes DNSBL) on an interval tuned per environment. **Kibana** is used for KPI-style dashboards on `mail-journeys-*`.

Separately, the **DNSBL background loop** in `main.py` uses **1-second sleep steps** between scans so the process can exit promptly on shutdown while honoring **`DNSBL_SCAN_INTERVAL_SECONDS`** (default 5 minutes) between full scans.

### 6.4 API timeouts

`ES_REQUEST_TIMEOUT` defaults to **600** seconds in `config.py` for heavy searches/aggregations over large daily indices.

### 6.5 Audit caps

`MAX_AUDIT_EDGE_LINES` and `MAX_AUDIT_DOWNSTREAM_LINES` (default **25**) limit stored raw lines per document while preserving **full counts** in **`audit_metrics`**, reducing **index size** and **serialization cost** to the UI.

---

## 7. Configuration quick reference

| Variable | Purpose |
|----------|---------|
| `ES_URL` | Elasticsearch HTTP endpoint (default `http://localhost:9200`) |
| `LOG_BASE_PATH` | Root of `FES01`, `MX01`, … trees |
| `DATABASE_URL` | Postgres for JWT users |
| `DNSBL_SCAN_INTERVAL_SECONDS` | Seconds between full DNSBL scans (default 300) |
| `SENDER_EMAIL`, `RECEIVER_EMAIL`, `EMAIL_PASSWORD` | Gmail SMTP for blacklist digest |
| `MAX_AUDIT_*` | Truncation limits for `audit` arrays |

---

## 8. Key source files

| File | Role |
|------|------|
| `backend_pipeline/main.py` | FastAPI app, startup template + DNSBL thread, routes |
| `backend_pipeline/sent_parser.py` | FES + VIP/GP/ML correlation, `NEXT_HOP_MAP`, statuses |
| `backend_pipeline/received_parser.py` | MX ingestion, Kaspersky id bridging |
| `backend_pipeline/journey_schema.py` | Index template + `finalize_journey_document` |
| `backend_pipeline/blacklist_scan.py` | DNSBL parallel scan + `dnsbl-checks` index |
| `backend_pipeline/email_alerts.py` | HTML digest email |
| `backend_pipeline/query_builder.py` | Search + overview query DSL |
| `docker-compose.yml` | ES 8.12.0, Kibana 8.12.0, Postgres 16 |

---

*This file is generated from the repository implementation as of the documented versions; adjust if production deploys differ (security, replication, parser scheduling).*
