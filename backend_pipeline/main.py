"""
FastAPI application: auth, Elasticsearch search, blacklist helpers.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable
import threading
import time
from datetime import datetime, timedelta

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import config
from admin_users import create_user, delete_user, list_users, update_user
from auth import admin_login, decode_token, login as auth_login, signup as auth_signup
from database import get_n3_subscriber_emails, init_db
from email_alerts import blacklist_email_configured, send_blacklist_delist_email, send_blacklist_digest_email
from es_infra import ensure_mail_journey_template, get_elasticsearch
from journey_schema import coerce_kaspersky_level_to_int
from query_builder import build_journey_query_clauses
from blacklist_scan import DNSB_STATUS_FIELD, ensure_dnsbl_index, run_dnsbl_scan
from dnsbl_journeys import (
    ensure_dnsbl_journeys_index,
    get_latest_interval_seconds,
    get_schedule_from_latest_journey,
    save_interval_config_journey,
    save_journey,
)

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
# (ip, dnsbl) keys from the last completed scan — used to detect new listings.
_dnsbl_prev_listed_keys: frozenset[tuple[str, str]] | None = None
_dnsbl_listing_state_lock = threading.Lock()

# Mutable DNSBL auto-scan interval (seconds). Initialized from env / latest ES journey; PATCH updates.
_dnsbl_scan_interval_seconds: int = max(10, int(config.DNSBL_SCAN_INTERVAL_SECONDS))
_dnsbl_interval_lock = threading.Lock()
_DNSBL_INTERVAL_MAX = 86400 * 7  # 7 days
_dnsbl_wakeup = threading.Event()
_dnsbl_scan_lock = threading.Lock()


def _get_dnsbl_scan_interval_seconds() -> int:
    with _dnsbl_interval_lock:
        return _dnsbl_scan_interval_seconds


def _set_dnsbl_scan_interval_seconds(value: int) -> int:
    """Clamp to [10, 7d]. Written to each new journey on scan; background loop reads latest from ES."""
    global _dnsbl_scan_interval_seconds
    v = max(10, min(int(value), _DNSBL_INTERVAL_MAX))
    with _dnsbl_interval_lock:
        _dnsbl_scan_interval_seconds = v
    return v


def _dnsbl_run_scan_persist_notify(trigger: str) -> dict | None:
    """Run DNSBL scan, index checks, save journey (interval + listed_rows), notify. Returns summary or None if stopped."""
    with _dnsbl_scan_lock:
        if _dnsbl_stop.is_set():
            return None
        summary = run_dnsbl_scan(es=es)
        interval = _get_dnsbl_scan_interval_seconds()
        save_journey(es, summary=summary, interval_seconds=interval, trigger=trigger)
        log.info(
            "DNSBL scan (%s): checks=%s listed=%s errors=%s interval=%s",
            trigger,
            summary.get("total_checks"),
            summary.get("listed"),
            summary.get("errors"),
            interval,
        )
        try:
            _notify_dnsbl_changes(
                summary.get("listed_rows") or [],
                summary.get("pair_status"),
            )
        except Exception as notify_err:
            log.warning("DNSBL change notification step failed: %s", notify_err)
        return summary


def _dnsbl_background_loop() -> None:
    """
    Wall-clock scheduling from the latest journey in ``dnsbl-scan-journeys``:
    next run when now >= last @timestamp + interval_seconds. Wakes early on interval PATCH.
    """
    while not _dnsbl_stop.is_set():
        try:
            sched = get_schedule_from_latest_journey(es)
            if sched is not None:
                last_ts, interval_sec = sched
                _set_dnsbl_scan_interval_seconds(interval_sec)
                next_wall = last_ts + timedelta(seconds=interval_sec)
                now_wall = datetime.utcnow()
                if now_wall < next_wall:
                    deadline_mono = time.monotonic() + (next_wall - now_wall).total_seconds()
                    while not _dnsbl_stop.is_set():
                        if time.monotonic() >= deadline_mono:
                            break
                        remaining = deadline_mono - time.monotonic()
                        if _dnsbl_wakeup.wait(timeout=min(1.0, max(0.05, remaining))):
                            _dnsbl_wakeup.clear()
                            break
                    if _dnsbl_stop.is_set():
                        return
                    if time.monotonic() < deadline_mono:
                        continue

            if _dnsbl_stop.is_set():
                return
            if _dnsbl_run_scan_persist_notify("scheduled") is None:
                return
        except Exception as e:
            log.warning("DNSBL background loop error: %s", e)
            for _ in range(30):
                if _dnsbl_stop.is_set():
                    return
                time.sleep(1)


def _dnsbl_row_key(row: dict) -> tuple[str, str]:
    ip, bl = row.get("ip"), row.get("blacklist")
    return (str(ip) if ip is not None else "", str(bl) if bl is not None else "")


def _notify_dnsbl_changes(
    listed_rows: list[dict],
    pair_status: dict[tuple[str, str], str] | None = None,
) -> None:
    """
    After a DNSBL scan, email when (IP, DNSBL) pairs newly become LISTED or are removed
    (prior scan listed, current scan CLEAN). The first scan after process start only
    establishes a baseline (no email). ERROR on a pair does not count as a delist.
    """
    global _dnsbl_prev_listed_keys
    current = frozenset(_dnsbl_row_key(r) for r in listed_rows)
    ps = pair_status or {}

    with _dnsbl_listing_state_lock:
        prev = _dnsbl_prev_listed_keys
        if prev is None:
            _dnsbl_prev_listed_keys = current
            return

        new_keys = current - prev
        delist_keys = frozenset(
            k for k in prev if k not in current and ps.get(k) == "CLEAN"
        )
        _dnsbl_prev_listed_keys = current

    ts = datetime.utcnow()
    new_rows = [r for r in listed_rows if _dnsbl_row_key(r) in new_keys]
    removed_rows = [{"ip": k[0], "blacklist": k[1], "@timestamp": ts} for k in sorted(delist_keys)]

    n3_emails = get_n3_subscriber_emails()
    if new_rows:
        if not blacklist_email_configured():
            log.warning("New DNSBL listings (email not configured): %s", sorted(new_keys))
        elif not n3_emails:
            log.warning("New DNSBL listings (no N3 subscriber emails in DB): %s", sorted(new_keys))
        else:
            try:
                send_blacklist_digest_email(
                    listed_rows=new_rows,
                    recipient_emails=n3_emails,
                    new_since_previous_scan=True,
                )
            except Exception as e:
                log.warning("New blacklist alert email failed: %s", e)

    if removed_rows:
        if not blacklist_email_configured():
            log.warning("DNSBL delists (email not configured): %s", sorted(delist_keys))
        elif not n3_emails:
            log.warning("DNSBL delists (no N3 subscriber emails in DB): %s", sorted(delist_keys))
        else:
            try:
                send_blacklist_delist_email(removed_rows=removed_rows, recipient_emails=n3_emails)
            except Exception as e:
                log.warning("Blacklist delist email failed: %s", e)


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
    try:
        ensure_dnsbl_journeys_index(es)
        j = get_latest_interval_seconds(es, fallback=_get_dnsbl_scan_interval_seconds())
        _set_dnsbl_scan_interval_seconds(j)
    except Exception as e:
        log.warning("dnsbl-scan-journeys init failed: %s", e)

    global _dnsbl_thread
    if _dnsbl_thread is None or not _dnsbl_thread.is_alive():
        _dnsbl_stop.clear()
        _dnsbl_wakeup.clear()
        _dnsbl_thread = threading.Thread(target=_dnsbl_background_loop, name="dnsbl-scan", daemon=True)
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
    if payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Use a user account token for this resource")
    return payload


async def require_user_dnsbl_n3(user: dict = Depends(get_current_user)) -> dict:
    """DNSBL UI/API is restricted to N3 (JWT must include role from login)."""
    role = str(user.get("role") or "N1").strip().upper()
    if role != "N3":
        raise HTTPException(status_code=403, detail="DNSBL is only available for N3 users.")
    return user


async def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload or not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


class SignupBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class AdminLoginBody(BaseModel):
    username: str
    password: str


class AdminUserCreateBody(BaseModel):
    email: str
    password: str
    role: str = "N1"


class AdminUserUpdateBody(BaseModel):
    email: str | None = None
    password: str | None = None
    role: str | None = None


class BlacklistIntervalBody(BaseModel):
    """Seconds between automatic DNSBL scans (background thread in main.py)."""

    interval_seconds: int


@app.post("/api/signup")
def api_signup(body: SignupBody):
    ok, msg = auth_signup(body.email, body.password)
    if not ok:
        return {"ok": False, "error": msg}
    ok2, token = auth_login(body.email, body.password)
    if not ok2 or not token:
        return {"ok": False, "error": "Account created but login failed."}
    email_out = body.email.strip().lower()
    pl = decode_token(token) or {}
    return {"ok": True, "token": token, "email": email_out, "role": pl.get("role", "N1")}


@app.post("/api/login")
def api_login(body: LoginBody):
    ok, result = auth_login(body.email, body.password)
    if not ok:
        return {"ok": False, "error": result}
    email_out = body.email.strip().lower()
    pl = decode_token(result) or {}
    return {"ok": True, "token": result, "email": email_out, "role": pl.get("role", "N1")}


@app.post("/api/admin/login")
def api_admin_login(body: AdminLoginBody):
    ok, result = admin_login(body.username, body.password)
    if not ok:
        return {"ok": False, "error": result}
    return {"ok": True, "token": result}


@app.get("/api/admin/users")
async def api_admin_list_users(_admin: dict = Depends(get_current_admin)):
    return {"users": list_users()}


@app.post("/api/admin/users")
async def api_admin_create_user(body: AdminUserCreateBody, _admin: dict = Depends(get_current_admin)):
    ok, msg, user = create_user(email=body.email, password=body.password, role=body.role.strip().upper())
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "user": user}


@app.patch("/api/admin/users/{user_id}")
async def api_admin_update_user(
    user_id: int,
    body: AdminUserUpdateBody,
    _admin: dict = Depends(get_current_admin),
):
    pwd = body.password
    if pwd is not None and not str(pwd).strip():
        pwd = None
    ok, msg, user = update_user(
        user_id,
        email=body.email,
        password=pwd,
        role=body.role.strip().upper() if body.role is not None else None,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "user": user}


@app.delete("/api/admin/users/{user_id}")
async def api_admin_delete_user(user_id: int, _admin: dict = Depends(get_current_admin)):
    ok, msg = delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True}


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
    must_clauses, filter_clauses, index_suffixes = build_journey_query_clauses(
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

    candidate_indices: list[str] = []
    seen_idx: set[str] = set()
    for suf in index_suffixes:
        if dir_lower in ("sent", "both"):
            n = f"mail-journeys-sent-{suf}"
            if n not in seen_idx:
                seen_idx.add(n)
                candidate_indices.append(n)
        if dir_lower in ("received", "both"):
            n = f"mail-journeys-received-{suf}"
            if n not in seen_idx:
                seen_idx.add(n)
                candidate_indices.append(n)

    active_indices = [idx for idx in candidate_indices if es.indices.exists(index=idx)]

    if not active_indices:
        return {
            "total": 0,
            "results": [],
            "page": page,
            "size": size,
            "message": f"No data found for indices {', '.join(candidate_indices)} (direction: {dir_lower}).",
        }

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


@app.get("/api/blacklist/interval")
async def get_blacklist_scan_interval(_user: dict = Depends(require_user_dnsbl_n3)):
    """Interval from the latest ``dnsbl-scan-journeys`` document, else in-memory default (env on cold start)."""
    fb = _get_dnsbl_scan_interval_seconds()
    try:
        sec = get_latest_interval_seconds(es, fallback=fb)
    except Exception:
        sec = fb
    return {"interval_seconds": sec}


@app.patch("/api/blacklist/interval")
async def set_blacklist_scan_interval(
    body: BlacklistIntervalBody,
    _user: dict = Depends(require_user_dnsbl_n3),
):
    """
    Set interval and append a lightweight ``dnsbl-scan-journeys`` row (no DNS scan — fast).
    Wakes the background loop so it recomputes ``last journey @timestamp + interval`` from ES.
    """
    v = _set_dnsbl_scan_interval_seconds(body.interval_seconds)
    log.info("DNSBL auto-scan interval updated to %s seconds (interval-only journey)", v)
    try:
        save_interval_config_journey(es, interval_seconds=v)
    except Exception as e:
        log.warning("DNSBL interval journey save failed: %s", e)
    _dnsbl_wakeup.set()
    return {"ok": True, "interval_seconds": v}


def _dedupe_normalize_listed_rows(rows: Iterable[dict]) -> list[dict]:
    """Deduplicate by (ip, blacklist) and align legacy ``status`` with ``dnsb_status`` for API clients."""
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
    return out


@app.post("/api/blacklist/scan")
async def blacklist_scan_now(_user: dict = Depends(require_user_dnsbl_n3)):
    """
    Run a full DNSBL scan, bulk-index into `dnsbl-checks`, append a ``dnsbl-scan-journeys`` document,
    and return the LISTED rows from this scan (not a follow-up ES search, so the UI updates
    immediately even before ``dnsbl-checks`` is refreshed for search).
    """
    try:
        summary = _dnsbl_run_scan_persist_notify("on_demand")
        if not summary:
            raise HTTPException(status_code=503, detail="DNSBL scan unavailable (shutting down).")
    except HTTPException:
        raise
    except Exception as e:
        log.error("DNSBL on-demand scan failed: %s", e)
        raise HTTPException(status_code=500, detail="DNSBL scan failed.")
    listed = _dedupe_normalize_listed_rows(summary.get("listed_rows") or [])
    summary_out = {k: v for k, v in summary.items() if k not in ("listed_rows", "pair_status")}
    return {
        "ok": True,
        "summary": summary_out,
        "listed": listed,
        "count": len(listed),
    }


@app.get("/api/blacklist/listed")
async def get_blacklisted_servers(_user: dict = Depends(require_user_dnsbl_n3)):
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
        out = _dedupe_normalize_listed_rows(rows)
        return {"listed": out, "count": len(out)}
    except Exception as e:
        log.error("ES blacklist query error: %s", e)
        raise HTTPException(status_code=500, detail="Blacklist query failed.")


@app.post("/api/blacklist/email")
async def email_blacklisted_servers(background: BackgroundTasks, _user: dict = Depends(require_user_dnsbl_n3)):
    data = await get_blacklisted_servers(_user=_user)
    listed = data.get("listed", [])
    if not listed:
        return {"ok": True, "sent": False, "message": "No blacklisted servers right now."}

    if not blacklist_email_configured():
        raise HTTPException(
            status_code=400,
            detail="Email is not configured. Set SENDER_EMAIL, EMAIL_PASSWORD.",
        )

    n3_emails = get_n3_subscriber_emails()
    if not n3_emails:
        return {
            "ok": True,
            "sent": False,
            "count": len(listed),
            "message": "No users with role N3 to notify.",
        }

    try:
        background.add_task(
            send_blacklist_digest_email,
            listed_rows=listed,
            recipient_emails=n3_emails,
            new_since_previous_scan=False,
        )
        return {"ok": True, "sent": True, "count": len(listed), "recipients": len(n3_emails)}
    except Exception as e:
        log.error("Blacklist email scheduling failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
