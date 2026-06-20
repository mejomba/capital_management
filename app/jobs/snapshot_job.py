"""Simple daily snapshot scheduler (no external dependency).

A background daemon thread sleeps until the next configured UTC run time and
builds today's snapshot for every user. Enabled only when settings.ENABLE_SCHEDULER
is true; the snapshot logic itself is fully testable without this thread.
"""

import logging
import threading
from datetime import datetime, time, timedelta, timezone

from app.core.config import settings
from app.core.db import SessionLocal
from app.services import snapshots

logger = logging.getLogger(__name__)


def _seconds_until_next_run(now: datetime) -> float:
    target = datetime.combine(
        now.date(),
        time(settings.SNAPSHOT_HOUR_UTC, settings.SNAPSHOT_MINUTE_UTC),
        tzinfo=timezone.utc,
    )
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        delay = _seconds_until_next_run(datetime.now(timezone.utc))
        if stop_event.wait(delay):
            break
        try:
            built = snapshots.run_daily_snapshots(SessionLocal)
            logger.info("Daily snapshots built for %d users", built)
        except Exception:  # pragma: no cover - defensive, keep the loop alive
            logger.exception("Daily snapshot run failed")


def start_scheduler() -> threading.Event:
    """Start the daemon thread and return its stop event."""
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_loop, args=(stop_event,), name="snapshot-scheduler", daemon=True
    )
    thread.start()
    logger.info("Snapshot scheduler started")
    return stop_event
