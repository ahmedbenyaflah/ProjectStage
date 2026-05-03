"""
Central configuration from environment variables.
Used by the API, parsers, and Elasticsearch bootstrap code.
"""
from __future__ import annotations

import os
from pathlib import Path

# This package lives at <repo>/backend_pipeline/ — load .env from predictable paths
# (not cwd) so `python sent_parser.py`, uvicorn, and IDE runs behave the same.
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent

try:
    from dotenv import load_dotenv

    _root_env = _PROJECT_ROOT / ".env"
    _backend_env = _BACKEND_DIR / ".env"
    if _root_env.is_file():
        load_dotenv(_root_env, override=False)
    if _backend_env.is_file():
        load_dotenv(_backend_env, override=True)
except ImportError:
    pass


def _path_from_env(key: str, default: Path) -> Path:
    raw = os.environ.get(key, "").strip()
    return Path(raw).expanduser().resolve() if raw else default


# Elasticsearch
ES_URL: str = os.environ.get("ES_URL", "http://localhost:9200").strip()
ES_REQUEST_TIMEOUT: int = int(os.environ.get("ES_REQUEST_TIMEOUT", "600"))

# Log input tree (FES01, MX01, …)
_DEFAULT_LOG_ROOT = (Path(__file__).resolve().parent.parent / "Log-CG").resolve()
LOG_BASE_PATH: Path = _path_from_env("LOG_BASE_PATH", _DEFAULT_LOG_ROOT)

# Audit storage caps (full counts still in audit_metrics.*_line_count)
MAX_AUDIT_EDGE_LINES: int = int(os.environ.get("MAX_AUDIT_EDGE_LINES", "25"))
MAX_AUDIT_DOWNSTREAM_LINES: int = int(os.environ.get("MAX_AUDIT_DOWNSTREAM_LINES", "25"))

# API
PORT: int = int(os.environ.get("PORT", "8000"))

# DNSBL blacklist monitor (blacklist_scan → index `dnsbl-checks`; used by GET /api/blacklist/listed)
# Default every 5 minutes; set e.g. 86400 for once per day.
DNSBL_SCAN_INTERVAL_SECONDS: int = int(os.environ.get("DNSBL_SCAN_INTERVAL_SECONDS", "300"))
# Per (IP,DNSBL) DNS lookup cap (seconds). Prevents slow RBLs from stalling the whole scan.
DNSBL_QUERY_LIFETIME_SECONDS: float = float(os.environ.get("DNSBL_QUERY_LIFETIME_SECONDS", "2.5"))
# Comma-separated resolvers for DNSBL lookups (e.g. 8.8.8.8,1.1.1.1). Empty = use system resolv.conf.
# Helps when systemd-resolved (127.0.0.53) drops queries under high parallel load.
_DNSBL_NS_RAW = os.environ.get("DNSBL_NAMESERVERS", "").strip()
DNSBL_NAMESERVERS: list[str] = [p.strip() for p in _DNSBL_NS_RAW.split(",") if p.strip()] if _DNSBL_NS_RAW else []
# Thread pool size for parallel DNS checks (capped by number of lookups).
DNSBL_SCAN_MAX_WORKERS: int = int(os.environ.get("DNSBL_SCAN_MAX_WORKERS", "32"))
# If true, bulk-index waits for Elasticsearch refresh (slower; not needed for POST /scan response).
DNSBL_BULK_REFRESH: bool = os.environ.get("DNSBL_BULK_REFRESH", "").lower() in ("1", "true", "yes")

# Postgres (auth)
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://cg_user:cg_password@localhost:5432/cg_logs",
).strip()

# Static admin dashboard login (override in production)
ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin").strip()
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin")
