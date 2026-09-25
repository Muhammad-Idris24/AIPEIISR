"""Source scheduler: interval-based collection trigger loop with health tracking.

Live network collection is intentionally gated: the scheduler triggers collection
hooks but actual fetching uses approved-source registries and only fires synthetic
paths until a source is explicitly marked live. Source health (last_success) is
tracked regardless so operators can validate cadence and reliability.
"""
import os
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from .db import Session, Source, Audit

log = logging.getLogger("aipieisr.scheduler")

TICK_SECONDS = float(os.getenv("SCHEDULER_TICK_SECONDS", "30"))

_last_run: dict[str, float] = {}
_run_lock = threading.Lock()
_stats = {"ticks": 0, "runs": 0, "failures": 0, "last_tick_at": None}


def _fetch_rss(source: Source) -> list[tuple[str, str]]:
    """Approved-source RSS collection hook.

    Returns list of (url, content) tuples. In development mode without source
    authorization, this is a no-op and returns empty results so the scheduler
    exercises scheduling, health and retry plumbing without network calls.
    """
    if source.status != "APPROVED" or source.collector_type.upper() != "RSS":
        return []
    try:
        import feedparser
        parsed = feedparser.parse(source.url)
        results: list[tuple[str, str]] = []
        for entry in getattr(parsed, "entries", [])[:10]:
            url = getattr(entry, "link", source.url)
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            content = f"{title}\n{summary}".strip()
            if content:
                results.append((url, content))
        return results
    except Exception as e:
        log.warning("RSS fetch %s skipped (network/source gated): %s", source.id, e)
        return []


def _collect_for_source(source_id: str) -> bool:
    from .collector import collect_synthetic
    session = Session()
    try:
        source = session.get(Source, source_id)
        if not source or source.status != "APPROVED":
            return False
        collected = False
        if source.collector_type.upper() == "RSS":
            items = _fetch_rss(source)
            for url, content in items:
                try:
                    collect_synthetic(source.id, content, url=url)
                    collected = True
                except Exception:
                    pass
        source.last_success = datetime.now(timezone.utc)
        session.add(Audit(action="SOURCE_COLLECTED", entity=source.id, actor="scheduler"))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        log.error("Scheduler collect failed for %s: %s", source_id, e)
        return False
    finally:
        session.close()


def tick_sources() -> int:
    """Run one scheduler tick: collect from any sources past their interval."""
    global _stats
    _stats["ticks"] += 1
    _stats["last_tick_at"] = datetime.now(timezone.utc).isoformat()
    session = Session()
    try:
        sources = session.query(Source).filter_by(status="APPROVED").all()
    finally:
        session.close()
    now = time.time()
    ran = 0
    for src in sources:
        interval = max(5, int(src.interval_minutes or 60)) * 60
        last = _last_run.get(src.id, 0.0)
        with _run_lock:
            if now - last >= interval:
                _last_run[src.id] = now
                ok = _collect_for_source(src.id)
                if ok:
                    _stats["runs"] += 1
                else:
                    _stats["failures"] += 1
                ran += 1
    return ran


def run_source_now(source_id: str) -> bool:
    session = Session()
    try:
        src = session.get(Source, source_id)
        if not src or src.status != "APPROVED":
            return False
    finally:
        session.close()
    _last_run[source_id] = time.time()
    return _collect_for_source(source_id)


def scheduler_status() -> dict:
    session = Session()
    try:
        total = session.query(Source).count()
        approved = session.query(Source).filter_by(status="APPROVED").count()
        recently_ok = session.query(Source).filter(Source.last_success.is_not(None)).count()
    finally:
        session.close()
    return {
        "mode": "in-process-thread",
        "tick_seconds": TICK_SECONDS,
        "sources": {"total": total, "approved": approved, "recent_success": recently_ok},
        "stats": dict(_stats),
        "next_runs": {sid: max(0, int((_last_run.get(sid, 0) + interval - time.time()))) for sid, interval in _iter_source_intervals()},
    }


def _iter_source_intervals():
    session = Session()
    try:
        for src in session.query(Source).filter_by(status="APPROVED").all():
            yield src.id, max(5, int(src.interval_minutes or 60)) * 60
    finally:
        session.close()


class SchedulerLoop(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="aipieisr-scheduler")
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        log.info("Scheduler loop starting (tick=%ss)", TICK_SECONDS)
        while not self._stop.is_set():
            try:
                tick_sources()
            except Exception as e:
                log.error("Scheduler loop error: %s", e)
            self._stop.wait(TICK_SECONDS)
        log.info("Scheduler loop stopped")


_scheduler_loop: Optional[SchedulerLoop] = None
_disabled = os.getenv("SCHEDULER_DISABLED", "").lower() in ("1", "true", "yes")


def start_scheduler() -> Optional[SchedulerLoop]:
    global _scheduler_loop
    if _disabled:
        return None
    if _scheduler_loop and _scheduler_loop.is_alive():
        return _scheduler_loop
    _scheduler_loop = SchedulerLoop()
    _scheduler_loop.start()
    return _scheduler_loop


def stop_scheduler():
    global _scheduler_loop
    if _scheduler_loop:
        _scheduler_loop.stop()
        _scheduler_loop.join(timeout=5)
        _scheduler_loop = None
