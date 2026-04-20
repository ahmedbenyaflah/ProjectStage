"""
Central configuration from environment variables.
Used by the API, parsers, and Elasticsearch bootstrap code.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
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
# Default once per day; override for faster dev polling (e.g. 300).
DNSBL_SCAN_INTERVAL_SECONDS: int = int(os.environ.get("DNSBL_SCAN_INTERVAL_SECONDS", "86400"))

# Postgres (auth)
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://cg_user:cg_password@localhost:5432/cg_logs",
).strip()
