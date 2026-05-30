"""
Elasticsearch client factory and index-template bootstrap.
"""
from __future__ import annotations

import logging

from elasticsearch import Elasticsearch

import config
from journey_schema import (
    MAIL_JOURNEY_TEMPLATE_NAME,
    MAIL_JOURNEY_TEMPLATE_PRIORITY,
    mail_journey_index_template_body,
)

log = logging.getLogger(__name__)

_es_client: Elasticsearch | None = None


def get_elasticsearch() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(
            config.ES_URL,
            request_timeout=config.ES_REQUEST_TIMEOUT,
        )
    return _es_client


def ensure_mail_journey_template(es: Elasticsearch | None = None) -> None:
    """Install or update the composable index template for mail journey indices."""
    client = es or get_elasticsearch()
    body = mail_journey_index_template_body()
    try:
        client.indices.put_index_template(
            name=MAIL_JOURNEY_TEMPLATE_NAME,
            index_patterns=body["index_patterns"],
            template=body["template"],
            priority=MAIL_JOURNEY_TEMPLATE_PRIORITY,
        )
        log.info("Elasticsearch index template %r ensured.", MAIL_JOURNEY_TEMPLATE_NAME)
    except Exception as e:
        log.warning("Could not install index template %s: %s", MAIL_JOURNEY_TEMPLATE_NAME, e)
