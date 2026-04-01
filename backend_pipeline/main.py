import logging
import os
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from elasticsearch import Elasticsearch
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import init_db
from auth import signup as auth_signup, login as auth_login, decode_token

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch("http://localhost:9200")
security = HTTPBearer(auto_error=False)

# --- HELPER FUNCTIONS ---

def _escape_es_query_string(value: str) -> str:
    """Escapes reserved characters for Elasticsearch query_string."""
    reserved = set(list(r'+-=!(){}[]^"~*?:\/') + ["<", ">", "|", "&"])
    out = []
    for ch in value:
        if ch in reserved:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)

def _normalize_hhmmss_millis(value: str, *, is_end: bool) -> str:
    """Normalizes time input to HH:MM:SS.mmm format."""
    s = (value or "").strip()
    if not s:
        return ""
    if " " in s:
        s = s.split(" ", 1)[1].strip()

    ms_default = "999" if is_end else "000"

    if "." in s:
        time_part, ms_part = s.split(".", 1)
        ms = "".join(ch for ch in ms_part if ch.isdigit())[:3].ljust(3, "0") or ms_default
    else:
        time_part, ms = s, ms_default

    parts = [p for p in time_part.split(":") if p != ""]
    h = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    sec = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0

    h = max(0, min(23, h))
    m = max(0, min(59, m))
    sec = max(0, min(59, sec))
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms}"

def _build_query_clauses(
    sender, recipient, qid, status,
    spam_status, virus_status,
    min_duration, max_duration,
    start_time, end_time,
    date,
):
    """Builds must/filter clause lists shared across both index types."""
    must_clauses = []
    filter_clauses = []

    if sender:
        s = sender.strip()
        if s:
            must_clauses.append({
                "query_string": {
                    "query": f"*{_escape_es_query_string(s)}*",
                    "fields": ["sender", "sender.keyword"],
                    "analyze_wildcard": True,
                }
            })

    if recipient:
        r = recipient.strip()
        if r:
            must_clauses.append({
                "query_string": {
                    "query": f"*{_escape_es_query_string(r)}*",
                    "fields": ["recipients", "recipients.keyword"],
                    "analyze_wildcard": True,
                }
            })

    if qid:
        must_clauses.append({"term": {"qid": qid}})

    if status and status.lower() != "all":
        filter_clauses.append({"match": {"status": status.capitalize()}})

    if spam_status:
        filter_clauses.append({"term": {"kaspersky_spam_status.keyword": spam_status}})

    if virus_status:
        filter_clauses.append({"term": {"kaspersky_virus_status.keyword": virus_status}})

    if min_duration is not None or max_duration is not None:
        range_query = {}
        if min_duration is not None:
            range_query["gte"] = min_duration
        if max_duration is not None:
            range_query["lte"] = max_duration
        filter_clauses.append({"range": {"duration_seconds": range_query}})

    if start_time or end_time:
        start_norm = _normalize_hhmmss_millis(start_time or "", is_end=False) if start_time else ""
        end_norm = _normalize_hhmmss_millis(end_time or "", is_end=True) if end_time else ""
        time_range = {}
        if start_norm:
            time_range["gte"] = f"{date} {start_norm}"
        if end_norm:
            time_range["lte"] = f"{date} {end_norm}"
        time_range["format"] = "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd HH:mm:ss.SSS"
        filter_clauses.append({"range": {"start_time": time_range}})

    return must_clauses, filter_clauses

# --- AUTH DEPENDENCIES ---

@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        log.warning("Database init failed (auth may be unavailable): %s", e)

async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

# --- SCHEMAS ---

class SignupBody(BaseModel):
    email: str
    password: str

class LoginBody(BaseModel):
    email: str
    password: str

# --- AUTH ROUTES ---

@app.post("/api/signup")
def api_signup(body: SignupBody):
    ok, msg = auth_signup(body.email, body.password)
    if not ok:
        return {"ok": False, "error": msg}
    ok2, token = auth_login(body.email, body.password)
    if not ok2 or not token:
        return {"ok": False, "error": "Account created but login failed."}
    return {"ok": True, "token": token, "email": body.email.strip().lower()}

@app.post("/api/login")
def api_login(body: LoginBody):
    ok, result = auth_login(body.email, body.password)
    if not ok:
        return {"ok": False, "error": result}
    return {"ok": True, "token": result, "email": body.email.strip().lower()}

# --- MAIN SEARCH ENDPOINT ---

@app.get("/api/search")
async def search_mail(
    date: str = Query(..., description="Format: YYYY-MM-DD"),
    sender: str | None = Query(None),
    recipient: str | None = Query(None),
    qid: str | None = Query(None),
    status: str | None = Query(None),
    direction: str | None = Query(None, description="'sent', 'received', or None/'both' for all"),
    # Kaspersky specific filters
    spam_status: str | None = Query(None, description="e.g., KAS_STATUS_SPAM"),
    virus_status: str | None = Query(None, description="e.g., CLEAN"),
    min_duration: float | None = Query(None, ge=0),
    max_duration: float | None = Query(None, ge=0),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, le=1000),
    _user: dict = Depends(get_current_user),
):
    # Determine which indices to query
    dir_lower = (direction or "both").strip().lower()

    sent_index = f"mail-journeys-sent-{date}"
    received_index = f"mail-journeys-received-{date}"

    if dir_lower == "sent":
        indices_to_query = [sent_index]
    elif dir_lower == "received":
        indices_to_query = [received_index]
    else:
        indices_to_query = [sent_index, received_index]

    # Filter to only indices that actually exist
    active_indices = [idx for idx in indices_to_query if es.indices.exists(index=idx)]

    if not active_indices:
        return {
            "total": 0,
            "results": [],
            "page": page,
            "size": size,
            "message": f"No data found for {date} (direction: {dir_lower}).",
        }

    must_clauses, filter_clauses = _build_query_clauses(
        sender, recipient, qid, status,
        spam_status, virus_status,
        min_duration, max_duration,
        start_time, end_time,
        date,
    )

    query = (
        {"bool": {"must": must_clauses, "filter": filter_clauses}}
        if (must_clauses or filter_clauses)
        else {"match_all": {}}
    )

    start_from = (page - 1) * size

    try:
        response = es.search(
            index=",".join(active_indices),
            body={
                "query": query,
                "from": start_from,
                "size": size,
                "sort": [{"start_time": "asc"}],
            },
        )

        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            # Normalise the audit structure so both parser formats look the same to the frontend.
            # sent_parser  → audit.fes_lines / audit.mapped_lines
            # reception_parser → audit.mx_lines (stored under fes_lines for FE compatibility)
            audit = source.get("audit", {})
            if "mx_lines" in audit and "fes_lines" not in audit:
                audit["fes_lines"] = audit.pop("mx_lines")
            source["audit"] = audit

            # Normalise kaspersky_level field name
            # sent_parser uses "kaspersky_level", reception_parser uses "kas_level"
            if "kaspersky_level" not in source and "kas_level" in source:
                source["kaspersky_level"] = source["kas_level"]

            # Expose reception-specific fields that the FE may want
            # kas_method / kav_status are reception-only; keep them as-is
            results.append(source)

        return {
            "total": response["hits"]["total"]["value"],
            "results": results,
            "page": page,
            "size": size,
        }

    except Exception as e:
        log.error(f"ES Search Error: {e}")
        raise HTTPException(status_code=500, detail="Search engine error occurred.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)