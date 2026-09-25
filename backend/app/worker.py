"""Worker: Redis consumer with DLQ and graceful in-process fallback.

When Redis is unavailable, the worker falls back to direct database dispatch.
All events are still written to the outbox table first (transactional safety).
"""
import os
import json
import logging
import threading
import time
from typing import Optional
from .db import Session, OutboxEvent, Audit

log = logging.getLogger("aipieisr.worker")

MAX_ATTEMPTS = 5
DLQ_EVENT_TYPE_PREFIX = "dlq."
STREAM_NAME = "aipieisr:events"
DLQ_STREAM_NAME = "aipieisr:events:dlq"
CONSUMER_GROUP = "aipieisr-workers"
CONSUMER_NAME = os.getenv("WORKER_NAME", "worker-1")
POLL_INTERVAL = float(os.getenv("WORKER_POLL_SECONDS", "2"))

_redis_client = None
_redis_available: Optional[bool] = None


def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL")
    if not url:
        _redis_available = False
        return None
    try:
        import redis
        _redis_client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        _redis_client.ping()
        _redis_available = True
        try:
            _redis_client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass
        try:
            _redis_client.xgroup_create(DLQ_STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass
        return _redis_client
    except Exception as e:
        log.warning("Redis unavailable; using in-process worker fallback: %s", e)
        _redis_available = False
        _redis_client = None
        return None


def redis_available() -> bool:
    _get_redis()
    return bool(_redis_available)


def publish_to_stream(event: OutboxEvent) -> bool:
    r = _get_redis()
    if not r:
        return False
    try:
        r.xadd(STREAM_NAME, {
            "event_id": event.id,
            "event_type": event.event_type,
            "entity_id": event.entity_id,
            "payload": event.payload or "{}",
            "attempts": str(event.attempts),
        })
        return True
    except Exception as e:
        log.warning("Failed to publish to Redis stream: %s", e)
        return False


def _move_to_dlq(r, stream_msg_id, fields):
    try:
        r.xadd(DLQ_STREAM_NAME, {
            **fields,
            "original_stream": STREAM_NAME,
            "original_message_id": stream_msg_id,
            "moved_at": str(int(time.time())),
        })
        r.xack(STREAM_NAME, CONSUMER_GROUP, stream_msg_id)
        log.error("Moved event %s to DLQ after max attempts", fields.get("event_id"))
    except Exception as e:
        log.error("Failed to move to DLQ: %s", e)


def _process_event_fields(fields) -> bool:
    event_id = fields.get("event_id")
    if not event_id:
        return True
    session = Session()
    try:
        event = session.get(OutboxEvent, event_id)
        if not event:
            return True
        if event.status == "DISPATCHED":
            return True
        event.attempts += 1
        _apply_bounded_ai_job(event)
        if event.attempts >= MAX_ATTEMPTS:
            event.status = "DEAD"
            session.add(Audit(action="OUTBOX_DLQ", entity=event.id, actor="worker"))
            session.commit()
            return True
        event.status = "DISPATCHED"
        session.add(Audit(action="OUTBOX_DISPATCHED", entity=event.id, actor="worker"))
        session.commit()
        return True
    except Exception as e:
        log.error("Error processing event %s: %s", event_id, e)
        session.rollback()
        return False
    finally:
        session.close()


AI_PREFIXES = ("SubmissionAI", "AI_", "DocumentAI", "EvidenceAI")


def _apply_bounded_ai_job(event: OutboxEvent) -> None:
    if not event.event_type or not any(event.event_type.startswith(p) for p in AI_PREFIXES):
        return
    try:
        from .providers import get_llm_provider, get_embedding_provider
    except Exception:
        return
    try:
        llm = get_llm_provider()
        emb = get_embedding_provider()
    except Exception:
        return
    actor = f"ai-worker/{getattr(llm,'name','mock')}"
    try:
        from .db import Audit as A
        session = Session()
        try:
            session.add(A(action=f"AIEVENT_{event.event_type}", entity=event.entity_id or event.id, actor=actor))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        pass


def consume_once() -> int:
    r = _get_redis()
    processed = 0
    if r:
        try:
            results = r.xreadgroup(CONSUMER_GROUP, CONSUMER_NAME, {STREAM_NAME: ">"}, count=20, block=100)
            for _, messages in results:
                for msg_id, fields in messages:
                    ok = _process_event_fields(fields)
                    attempts = int(fields.get("attempts", "0"))
                    if attempts + 1 >= MAX_ATTEMPTS and not ok:
                        _move_to_dlq(r, msg_id, fields)
                    elif ok:
                        r.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                    processed += 1
        except Exception as e:
            log.warning("Redis consume error, falling back to DB dispatch: %s", e)
    if not processed:
        processed = _db_dispatch_once()
    return processed


def _db_dispatch_once(limit: int = 50) -> int:
    session = Session()
    try:
        events = session.query(OutboxEvent).filter(OutboxEvent.status == "PENDING").limit(limit).all()
        for event in events:
            event.attempts += 1
            if event.attempts >= MAX_ATTEMPTS:
                event.status = "DEAD"
                session.add(Audit(action="OUTBOX_DLQ", entity=event.id, actor="worker"))
            else:
                event.status = "DISPATCHED"
                session.add(Audit(action="OUTBOX_DISPATCHED", entity=event.id, actor="worker"))
        session.commit()
        return len(events)
    except Exception as e:
        session.rollback()
        log.error("DB dispatch error: %s", e)
        return 0
    finally:
        session.close()


def publish_pending_outbox_to_stream() -> int:
    r = _get_redis()
    if not r:
        return 0
    session = Session()
    try:
        events = session.query(OutboxEvent).filter(OutboxEvent.status == "PENDING").limit(100).all()
        count = 0
        for event in events:
            if publish_to_stream(event):
                count += 1
        return count
    finally:
        session.close()


def dlq_size() -> int:
    r = _get_redis()
    if not r:
        session = Session()
        try:
            return session.query(OutboxEvent).filter(OutboxEvent.status == "DEAD").count()
        finally:
            session.close()
    try:
        info = r.xinfo_stream(DLQ_STREAM_NAME)
        return info.get("length", 0)
    except Exception:
        return 0


def worker_status() -> dict:
    r = _get_redis()
    session = Session()
    try:
        pending = session.query(OutboxEvent).filter(OutboxEvent.status == "PENDING").count()
        dispatched = session.query(OutboxEvent).filter(OutboxEvent.status == "DISPATCHED").count()
        dead = session.query(OutboxEvent).filter(OutboxEvent.status == "DEAD").count()
    finally:
        session.close()
    return {
        "transport": "redis" if r else "in-process-db",
        "redis_connected": bool(r),
        "pending": pending,
        "dispatched": dispatched,
        "dead": dead,
        "dlq": dlq_size(),
        "consumer_group": CONSUMER_GROUP if r else None,
        "consumer_name": CONSUMER_NAME if r else None,
    }


class WorkerLoop(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="aipieisr-worker")
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        log.info("Worker loop starting (%s transport)", "redis" if redis_available() else "in-process")
        while not self._stop.is_set():
            try:
                publish_pending_outbox_to_stream()
                consume_once()
            except Exception as e:
                log.error("Worker loop error: %s", e)
            self._stop.wait(POLL_INTERVAL)
        log.info("Worker loop stopped")


_worker_loop: Optional[WorkerLoop] = None
_disabled = os.getenv("WORKER_DISABLED", "").lower() in ("1", "true", "yes")


def start_worker() -> Optional[WorkerLoop]:
    global _worker_loop
    if _disabled:
        return None
    if _worker_loop and _worker_loop.is_alive():
        return _worker_loop
    _worker_loop = WorkerLoop()
    _worker_loop.start()
    return _worker_loop


def stop_worker():
    global _worker_loop
    if _worker_loop:
        _worker_loop.stop()
        _worker_loop.join(timeout=5)
        _worker_loop = None


def list_dead_events(limit: int = 100) -> list[dict]:
    session = Session()
    try:
        rows = session.query(OutboxEvent).filter(OutboxEvent.status == "DEAD").order_by(OutboxEvent.created_at.desc()).limit(limit).all()
        return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    finally:
        session.close()


def retry_dead_event(event_id: str) -> bool:
    session = Session()
    try:
        event = session.get(OutboxEvent, event_id)
        if not event or event.status != "DEAD":
            return False
        event.status = "PENDING"
        event.attempts = 0
        session.add(Audit(action="OUTBOX_RETRY", entity=event.id, actor="admin"))
        session.commit()
        publish_to_stream(event)
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def retry_all_dead() -> int:
    session = Session()
    try:
        rows = session.query(OutboxEvent).filter(OutboxEvent.status == "DEAD").all()
        count = 0
        for e in rows:
            e.status = "PENDING"
            e.attempts = 0
            session.add(Audit(action="OUTBOX_RETRY", entity=e.id, actor="admin"))
            count += 1
        session.commit()
        for e in rows:
            publish_to_stream(e)
        return count
    except Exception:
        session.rollback()
        return 0
    finally:
        session.close()


def get_event(event_id: str) -> dict | None:
    session = Session()
    try:
        e = session.get(OutboxEvent, event_id)
        if not e:
            return None
        return {c.name: getattr(e, c.name) for c in e.__table__.columns}
    finally:
        session.close()


def cancel_event(event_id: str) -> bool:
    session = Session()
    try:
        e = session.get(OutboxEvent, event_id)
        if not e or e.status == "DISPATCHED":
            return False
        e.status = "CANCELLED"
        session.add(Audit(action="OUTBOX_CANCELLED", entity=e.id, actor="admin"))
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()
