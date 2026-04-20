"""
FastAPI application: auth, Elasticsearch search, blacklist helpers.
"""
from __future__ import annotations

import logging
import os
import threading
import time

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import config
from auth import decode_token, login as auth_login, signup as auth_signup
from database import init_db
from email_alerts import send_blacklist_digest_email
from es_infra import ensure_mail_journey_template, get_elasticsearch
from journey_schema import coerce_kaspersky_level_to_int
from query_builder import build_journey_query_clauses
from blacklist_scan import DNSB_STATUS_FIELD, ensure_dnsbl_index, run_dnsbl_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = FastAPI(title="CG Mail Journey API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

es = get_elasticsearch()
security = HTTPBearer(auto_error=False)

_dnsbl_thread: threading.Thread | None = None
_dnsbl_stop = threading.Event()


def _latest_index_date(prefix: str) -> str | None:
    try:
        indices = list(es.indices.get_alias(index=f"{prefix}-*").keys())
    except Exception:
        return None
    dates: list[str] = []
    for idx in indices:
        parts = idx.split("-")
        if len(parts) >= 4:
            d = "-".join(parts[-3:])
            if len(d) == 10:
                dates.append(d)
    return max(dates) if dates else None


def _normalize_hit_source(source: dict) -> dict:
    """Align legacy documents with the unified API contract."""
    out = dict(source)
    audit = dict(out.get("audit") or {})
    if "mx_lines" in audit and "fes_lines" not in audit:
        audit["fes_lines"] = audit.pop("mx_lines")
    out["audit"] = audit

    out["kaspersky_level"] = coerce_kaspersky_level_to_int(out)
    out.pop("kas_level", None)
    out.pop("kas_level_score", None)

    if out.get("kaspersky_spam_status") == "UNKNOWN":
        out["kaspersky_spam_status"] = "KAS_STATUS_NOT_SPAM"

    if out.get("kaspersky_virus_status") == "UNKNOWN":
        out["kaspersky_virus_status"] = "CLEAN"
    return out


@app.on_event("startup")
def startup() -> None:
    ensure_mail_journey_template(es)
    try:
        init_db()
    except Exception as e:
        log.warning("Database init failed (auth may be unavailable): %s", e)

    # Start DNSBL monitoring loop (writes to `dnsbl-checks`) so the frontend can
    # display current blacklisted entries via GET /api/blacklist/listed.
    try:
        ensure_dnsbl_index(es)
    except Exception as e:
        log.warning("dnsbl-checks init failed: %s", e)

    global _dnsbl_thread
    if _dnsbl_thread is None or not _dnsbl_thread.is_alive():
        _dnsbl_stop.clear()

        def _loop() -> None:
            # Run immediately on boot, then on DNSBL_SCAN_INTERVAL_SECONDS (default: daily).
            while not _dnsbl_stop.is_set():
                try:
                    summary = run_dnsbl_scan(es=es)
                    log.info(
                        "DNSBL scan: checks=%s listed=%s errors=%s",
                        summary.get("total_checks"),
                        summary.get("listed"),
                        summary.get("errors"),
                    )
                except Exception as e:
                    log.warning("DNSBL scan failed: %s", e)

                # Sleep until next scan, but allow fast shutdown (1s resolution).
                interval = max(10, int(config.DNSBL_SCAN_INTERVAL_SECONDS))
                for _ in range(interval):
                    if _dnsbl_stop.is_set():
                        return
                    time.sleep(1)

        _dnsbl_thread = threading.Thread(target=_loop, name="dnsbl-scan", daemon=True)
        _dnsbl_thread.start()


@app.on_event("shutdown")
def shutdown() -> None:
    _dnsbl_stop.set()
    if _dnsbl_thread and _dnsbl_thread.is_alive():
        _dnsbl_thread.join(timeout=5)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


class SignupBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


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


@app.get("/api/search")
async def search_mail(
    date: str = Query(..., description="Format: YYYY-MM-DD"),
    sender: str | None = Query(None),
    recipient: str | None = Query(None),
    qid: str | None = Query(None),
    status: str | None = Query(None),
    direction: str | None = Query(None, description="'sent', 'received', or omit for both"),
    spam_status: str | None = Query(None, description="e.g. KAS_STATUS_SPAM"),
    virus_status: str | None = Query(None, description="e.g. CLEAN"),
    min_duration: float | None = Query(None, ge=0),
    max_duration: float | None = Query(None, ge=0),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, le=10000),
    _user: dict = Depends(get_current_user),
):
    dir_lower = (direction or "both").strip().lower()
    sent_index = f"mail-journeys-sent-{date}"
    received_index = f"mail-journeys-received-{date}"

    if dir_lower == "sent":
        indices_to_query = [sent_index]
    elif dir_lower == "received":
        indices_to_query = [received_index]
    else:
        indices_to_query = [sent_index, received_index]

    active_indices = [idx for idx in indices_to_query if es.indices.exists(index=idx)]

    if not active_indices:
        return {
            "total": 0,
            "results": [],
            "page": page,
            "size": size,
            "message": f"No data found for {date} (direction: {dir_lower}).",
        }

    must_clauses, filter_clauses = build_journey_query_clauses(
        sender=sender,
        recipient=recipient,
        qid=qid,
        status=status,
        spam_status=spam_status,
        virus_status=virus_status,
        min_duration=min_duration,
        max_duration=max_duration,
        start_time=start_time,
        end_time=end_time,
        date=date,
    )

    query: dict = (
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
                "sort": [{"start_time": "asc"}, {"qid": "asc"}],
            },
        )

        results = [_normalize_hit_source(hit["_source"]) for hit in response["hits"]["hits"]]

        return {
            "total": response["hits"]["total"]["value"],
            "results": results,
            "page": page,
            "size": size,
        }

    except Exception as e:
        log.error("ES Search Error: %s", e)
        raise HTTPException(status_code=500, detail="Search engine error occurred.")


@app.post("/api/blacklist/scan")
async def blacklist_scan_now(_user: dict = Depends(get_current_user)):
    """
    Run a full DNSBL scan, bulk-index results into `dnsbl-checks`, and return the LISTED rows.
    Use from the UI when the operator opens blacklists (on-demand save + list).
    """
    try:
        summary = run_dnsbl_scan(es=es)
        log.info(
            "DNSBL scan (on-demand): checks=%s listed=%s errors=%s",
            summary.get("total_checks"),
            summary.get("listed"),
            summary.get("errors"),
        )
    except Exception as e:
        log.error("DNSBL on-demand scan failed: %s", e)
        raise HTTPException(status_code=500, detail="DNSBL scan failed.")
    data = await get_blacklisted_servers(_user=_user)
    return {
        "ok": True,
        "summary": summary,
        "listed": data.get("listed", []),
        "count": data.get("count", len(data.get("listed", []))),
    }


@app.get("/api/blacklist/listed")
async def get_blacklisted_servers(_user: dict = Depends(get_current_user)):
    if not es.indices.exists(index="dnsbl-checks"):
        return {"listed": [], "message": "dnsbl-checks index not found."}
    try:
        # `dnsb_status` is the DNSBL field (avoids clashing with mail journey `status`).
        # Still match legacy `status` for older indexed documents.
        resp = es.search(
            index="dnsbl-checks",
            body={
                "size": 1000,
                "query": {
                    "bool": {
                        "should": [
                            {"term": {DNSB_STATUS_FIELD: "LISTED"}},
                            {"term": {f"{DNSB_STATUS_FIELD}.keyword": "LISTED"}},
                            {"term": {"status": "LISTED"}},
                            {"term": {"status.keyword": "LISTED"}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "sort": [{"@timestamp": "desc"}],
            },
        )
        rows = [h.get("_source", {}) for h in resp.get("hits", {}).get("hits", [])]
        seen: set[tuple] = set()
        out: list[dict] = []
        for r in rows:
            k = (r.get("ip"), r.get("blacklist"))
            if k in seen:
                continue
            seen.add(k)
            row = dict(r)
            if DNSB_STATUS_FIELD not in row and row.get("status") == "LISTED":
                row[DNSB_STATUS_FIELD] = "LISTED"
            out.append(row)
        return {"listed": out, "count": len(out)}
    except Exception as e:
        log.error("ES blacklist query error: %s", e)
        raise HTTPException(status_code=500, detail="Blacklist query failed.")


@app.post("/api/blacklist/email")
async def email_blacklisted_servers(background: BackgroundTasks, _user: dict = Depends(get_current_user)):
    data = await get_blacklisted_servers(_user=_user)
    listed = data.get("listed", [])
    if not listed:
        return {"ok": True, "sent": False, "message": "No blacklisted servers right now."}

    if not all(
        [
            os.getenv("SENDER_EMAIL", "").strip(),
            os.getenv("RECEIVER_EMAIL", "").strip(),
            os.getenv("EMAIL_PASSWORD", "").strip(),
        ]
    ):
        raise HTTPException(
            status_code=400,
            detail="Email is not configured. Set SENDER_EMAIL, RECEIVER_EMAIL, EMAIL_PASSWORD.",
        )

    try:
        background.add_task(send_blacklist_digest_email, listed_rows=listed)
        return {"ok": True, "sent": True, "count": len(listed)}
    except Exception as e:
        log.error("Blacklist email scheduling failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
