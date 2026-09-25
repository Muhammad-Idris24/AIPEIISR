"""Transactional outbox adapter.

Events are first written to the database (transactional), then fanned out to
the Redis stream when available. The worker loop (worker.py) consumes from
either Redis or directly from the outbox table with retry + DLQ semantics.
"""
from .db import Session, OutboxEvent, Audit
from . import worker


def emit(session, event_type: str, entity_id: str, payload: str = "{}"):
    event = OutboxEvent(event_type=event_type, entity_id=entity_id, payload=payload)
    session.add(event)
    session.flush()
    try:
        worker.publish_to_stream(event)
    except Exception:
        pass


def dispatch_pending(limit: int = 50) -> int:
    """Admin-triggered dispatch. Also publishes pending events to Redis first."""
    worker.publish_pending_outbox_to_stream()
    return worker.consume_once() or worker._db_dispatch_once(limit)
