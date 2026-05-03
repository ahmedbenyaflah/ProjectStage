from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Iterable

import dns.resolver
from elasticsearch.helpers import bulk

import config

log = logging.getLogger(__name__)

_tls_resolver = threading.local()

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
    # --- Original List ---
    "bl.spamcop.net",
    "zen.spamhaus.org",
    "dnsbl.sorbs.net",
    "dnsbl-2.uceprotect.net",
    "access.redhawk.org",
    # --- Added from Report ---
    "combined.mail.abusix.zone",
    "b.barracudacentral.org",
    "bl.blocklist.de",
    "ips.backscatterer.org",
    "bl.mailspike.net",
    "z.mailspike.net",
    "dnsbl-1.uceprotect.net",
    "dnsbl-3.uceprotect.net",
    "dnsbl.spfbl.net",
    "psbl.surriel.com",
    "bl.score.senderscore.com",
    "backscatter.spameatingmonkey.net",
    "bl.spameatingmonkey.net",
    "noptr.spamrats.com",
    "dyna.spamrats.com",
    "spam.spamrats.com",
    "hostkarma.junkemailfilter.com",
    "dnsbl.dronebl.org",
    "bl.nordspam.com",
    "truncate.gbud.net",
    "rbl.interserver.net",
    "pbl.fabel.dk",
    "dnsbl.zapbl.net",
    "swinog.spam-rbl.ch",
    "bl.suomispam.net",
    "ix.dnsbl.manitu.net",
    "db.wpbl.info",
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


def _thread_dnsbl_resolver() -> dns.resolver.Resolver:
    r = getattr(_tls_resolver, "resolver", None)
    if r is None:
        r = dns.resolver.Resolver(configure=True)
        if config.DNSBL_NAMESERVERS:
            r.nameservers = list(config.DNSBL_NAMESERVERS)
        _tls_resolver.resolver = r
    return r


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
        res = _thread_dnsbl_resolver()
        lt = float(config.DNSBL_QUERY_LIFETIME_SECONDS)
        if lt > 0:
            res.resolve(query, "A", lifetime=lt)
        else:
            res.resolve(query, "A")
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
    max_workers: int | None = None,
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
    n_tasks = len(hosts_list) * len(dnsbls_list)
    mw_cfg = int(config.DNSBL_SCAN_MAX_WORKERS)
    workers = min(max(1, n_tasks), mw_cfg) if max_workers is None else max(1, min(max_workers, n_tasks))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_check_one, ip, dnsbl, timestamp)
            for ip in hosts_list
            for dnsbl in dnsbls_list
        ]
        results = [f.result() for f in futures]

    actions = [{"_index": INDEX_NAME, "_source": doc} for doc in results]
    _, bulk_errors = bulk(
        es,
        actions,
        raise_on_error=False,
        request_timeout=120,
        refresh=config.DNSBL_BULK_REFRESH,
    )
    if bulk_errors:
        log.warning("DNSBL bulk index failures (%d): %s", len(bulk_errors), bulk_errors[:5])

    listed = [r for r in results if r.get(DNSB_STATUS_FIELD) == "LISTED"]
    errored = [r for r in results if r.get(DNSB_STATUS_FIELD) == "ERROR"]
    if len(errored) == len(results) and results:
        log.error(
            "DNSBL: all %d lookups returned ERROR (DNS unreachable, policy block, or resolver overload). "
            "Set DNSBL_NAMESERVERS=8.8.8.8,1.1.1.1 or lower DNSBL_SCAN_MAX_WORKERS.",
            len(results),
        )
    elif errored and len(errored) >= max(10, len(results) // 4):
        log.warning("DNSBL: %d/%d lookups returned ERROR.", len(errored), len(results))

    pair_status = {
        (str(r.get("ip") or ""), str(r.get("blacklist") or "")): r.get(DNSB_STATUS_FIELD)
        for r in results
    }
    return {
        "timestamp": timestamp.isoformat() + "Z",
        "total_checks": len(results),
        "listed": len(listed),
        "errors": len(errored),
        # Full LISTED documents from this scan (for change-detection alerts).
        "listed_rows": listed,
        # Per (ip, dnsbl) status this scan — used to confirm delists (CLEAN vs ERROR).
        "pair_status": pair_status,
    }

