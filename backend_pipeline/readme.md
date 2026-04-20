# CG Mail Journey backend

Production-oriented pipeline: parsers build **one document per mail journey** for Elasticsearch/Kibana; the FastAPI service serves search, KPIs, and auth.

## Architecture

| Module | Role |
|--------|------|
| `config.py` | Environment-driven settings (`ES_URL`, `LOG_BASE_PATH`, audit caps, `DATABASE_URL`). |
| `journey_schema.py` | Composable **index template** (strict field types), `finalize_journey_document()` for a stable JSON shape. |
| `es_infra.py` | Shared Elasticsearch client + `ensure_mail_journey_template()`. |
| `query_builder.py` | Search query DSL aligned with the template. |
| `email_alerts.py` | Blacklist digest email (SMTP). |
| `main.py` | FastAPI app (installs template on startup, exposes `/api/*`). |
| `sent_parser.py` | FES + mapped servers → `mail-journeys-sent-YYYY-MM-DD`. |
| `received_parser.py` | MX servers → `mail-journeys-received-YYYY-MM-DD`. |

### Document design (Kibana-friendly, smaller index)

- **Indexed for analytics:** `status`, `direction`, `date`, `kaspersky_*`, `duration_seconds`, `serverPath`, `error_details.code`, `sender` (+ `.keyword` for aggregations), `recipients`, `relayIp`, `audit_metrics.*`, proper **`date`** types for `start_time`, `end_time`, `@timestamp`.
- **Stored but not indexed:** `audit` (`fes_lines`, `mapped_lines`) — still visible in Discover and in the UI via `_source`, without paying inverted-index cost on long log lines.
- **Caps:** Raw audit arrays are truncated before bulk index; full line counts live in `audit_metrics` for charts.

`schema_version` is set on each document for future migrations.

---

## Run locally with Docker (Elasticsearch, Kibana, Postgres)

### 1. Start infrastructure

From the **repository root** (where `docker-compose.yml` lives):

```bash
docker compose up -d
```

Wait until Elasticsearch answers:

```bash
until curl -s http://localhost:9200 >/dev/null; do sleep 2; done
echo "Elasticsearch is up."
```

Services:

- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`
- Postgres: `localhost:5432` (db `cg_logs`, user `cg_user`, password `cg_password`)

### 2. Python environment

```bash
cd backend_pipeline
python3 -m venv .venv
cd backend_pipeline
cd backend_pipeline

source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration (environment variables)

| Variable | Purpose | Default |
|----------|---------|---------|
| `ES_URL` | Elasticsearch HTTP URL | `http://localhost:9200` |
| `LOG_BASE_PATH` | Directory containing `FES01`, `MX01`, … | `<repo>/Log-CG` |
| `DATABASE_URL` | Postgres for JWT auth users | `postgresql://cg_user:cg_password@localhost:5432/cg_logs` |
| `JWT_SECRET_KEY` | Signing key for tokens | dev default in `auth.py` (change in prod) |
| `MAX_AUDIT_EDGE_LINES` | Max stored edge (FES/MX) audit lines | `25` |
| `MAX_AUDIT_DOWNSTREAM_LINES` | Max stored mapped-server lines | `25` |
| `SENDER_EMAIL`, `RECEIVER_EMAIL`, `EMAIL_PASSWORD` | Optional Gmail SMTP for blacklist alerts | unset |
| `DNSBL_SCAN_INTERVAL_SECONDS` | Background DNSBL scan period | `86400` (1 day) |

Example for a typical dev shell:

```bash
export DATABASE_URL="postgresql://cg_user:cg_password@localhost:5432/cg_logs"
export ES_URL="http://localhost:9200"
export LOG_BASE_PATH="/absolute/path/to/ProjectStage/Log-CG"
```

If logs live only on the host, keep `LOG_BASE_PATH` pointing at that host path when you run parsers on the host (default already targets `../Log-CG` relative to the repo).

### 4. Install the index template and run parsers

The API installs the composable template on startup. You can also rely on parsers, which call `ensure_mail_journey_template()` before bulk indexing.

```bash
# Optional: start API first so the template is registered
python main.py
# or: uvicorn main:app --host 0.0.0.0 --port 8000
```

In another terminal (same venv + env vars):

```bash
python received_parser.py          # all dates discovered under MX0*
python received_parser.py 2026-01-27
python sent_parser.py              # all dates under FES01
python sent_parser.py 2026-01-27
```

### 5. Frontend

```bash
cd logs_filter_frontend_elastic
npm install
# optional: echo 'REACT_APP_API_URL=http://localhost:8000' > .env.local
cd logs_filter_frontend_elastic

npm start
```

Use the same origin or set `REACT_APP_API_URL` to your API base URL.

---

## Reindexing after mapping changes

Index templates apply to **new** indices only. After changing mappings:

```bash
curl -X DELETE "http://localhost:9200/mail-journeys-sent-*"
curl -X DELETE "http://localhost:9200/mail-journeys-received-*"
```

http://localhost:9200/mail-journeys-sent-2026-01-27/_search?size=50&pretty
http://localhost:9200/mail-journeys-received-2026-01-27/_search?size=50&pretty

Then rerun `sent_parser.py` / `received_parser.py`.

---

## Kibana quick tips

- Create a **Data view** on `mail-journeys-sent-*` or `mail-journeys-*`.
- Use **Lens** with terms on `status`, `kaspersky_spam_status`, `serverPath`, `error_details.code`, `sender.keyword`.
- Time field: `@timestamp` or `start_time`.
- Histograms: `duration_seconds`, `audit_metrics.edge_line_count`.

---

## API summary

- `POST /api/signup`, `POST /api/login`
- `GET /api/search` — paginated journey search (Bearer token)
- `POST /api/blacklist/scan` — run DNSBL check now, write to `dnsbl-checks`, return LISTED rows (e.g. blacklist button)
- `GET /api/blacklist/listed` — read current LISTED rows from Elasticsearch
- `POST /api/blacklist/email` — digest email for current LISTED rows

---

## Troubleshooting

- **401 on API:** Sign up / log in; send `Authorization: Bearer <token>`.
- **Empty search:** Check index exists: `curl http://localhost:9200/_cat/indices?v | grep mail-journeys`.
- **Fielddata / sort errors on old indices:** Delete old `mail-journeys-*` indices and reindex so the new template applies.
