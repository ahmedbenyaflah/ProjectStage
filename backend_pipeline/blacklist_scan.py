from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Iterable

import dns.resolver
from elasticsearch.helpers import bulk

log = logging.getLogger(__name__)

INDEX_NAME = "dnsbl-checks"
# DNSBL listing state — not named `status` to avoid clashing with mail-journey `status`.
DNSB_STATUS_FIELD = "dnsb_status"

# Keep defaults aligned with the existing BlacklistCkeck.py script.
DEFAULT_HOSTS: list[str] = [
    "196.203.232.133",
    "197.26.11.132",
    "197.26.11.133",
    "197.26.11.134",
    "196.224.96.4",
    "196.224.96.5",
    "196.224.96.6",
    "193.95.123.25",
    "193.95.123.26",
    "193.95.123.27",
    "193.95.123.24",
    "196.203.232.5",
    "196.203.232.6",
]

DEFAULT_DNSBLS: list[str] = [
    "bl.spamcop.net",
    "zen.spamhaus.org",
    "dnsbl.sorbs.net",
    "dnsbl-2.uceprotect.net",
    "access.redhawk.org",
]


def ensure_dnsbl_index(es) -> None:
    """Create the dnsbl-checks index with a minimal mapping if missing."""
    if es.indices.exists(index=INDEX_NAME):
        return
    mapping = {
        "mappings": {
            "properties": {
                "ip": {"type": "ip"},
                "blacklist": {"type": "keyword"},
                DNSB_STATUS_FIELD: {"type": "keyword"},
                "@timestamp": {"type": "date"},
            }
        }
    }
    es.indices.create(index=INDEX_NAME, body=mapping)


def _check_one(ip: str, dnsbl: str, timestamp: datetime) -> dict:
    """DNS lookup only; indexing is batched via :func:`bulk` to avoid ES 429 backpressure."""
    reverse_ip = ".".join(reversed(ip.split(".")))
    query = f"{reverse_ip}.{dnsbl}"

    doc = {
        "ip": ip,
        "blacklist": dnsbl,
        DNSB_STATUS_FIELD: "CLEAN",
        "@timestamp": timestamp,
    }

    try:
        dns.resolver.resolve(query, "A")
        doc[DNSB_STATUS_FIELD] = "LISTED"
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        pass
    except Exception:
        doc[DNSB_STATUS_FIELD] = "ERROR"

    return doc


def run_dnsbl_scan(
    *,
    es,
    hosts: Iterable[str] = DEFAULT_HOSTS,
    dnsbls: Iterable[str] = DEFAULT_DNSBLS,
    max_workers: int = 20,
) -> dict:
    """
    Scan all (ip,dnsbl) pairs and index results into Elasticsearch.

    DNS checks run in parallel; documents are written with a single bulk request
    so the cluster is not flooded with concurrent single-document index calls (HTTP 429).

    Returns a small summary suitable for logs.
    """
    timestamp = datetime.utcnow()
    hosts_list = list(hosts)
    dnsbls_list = list(dnsbls)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_check_one, ip, dnsbl, timestamp)
            for ip in hosts_list
            for dnsbl in dnsbls_list
        ]
        results = [f.result() for f in futures]

    actions = [{"_index": INDEX_NAME, "_source": doc} for doc in results]
    _, bulk_errors = bulk(es, actions, raise_on_error=False, request_timeout=120)
    if bulk_errors:
        log.warning("DNSBL bulk index failures (%d): %s", len(bulk_errors), bulk_errors[:5])

    listed = [r for r in results if r.get(DNSB_STATUS_FIELD) == "LISTED"]
    errored = [r for r in results if r.get(DNSB_STATUS_FIELD) == "ERROR"]
    return {
        "timestamp": timestamp.isoformat() + "Z",
        "total_checks": len(results),
        "listed": len(listed),
        "errors": len(errored),
    }

