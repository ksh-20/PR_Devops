"""
pr_watcher.py
-------------
Background daemon thread that runs the PR auto-review poll on a configurable
interval. Mirrors the pattern used by core/sync_worker.py.
"""

import threading
import time
from datetime import datetime, timezone

from models.handle_logging import get_logging_conf
logging = get_logging_conf()
logger = logging.getLogger(__name__)

from services.reviewer.auto_review_daemon import run_poll_tick, daemon_status

# How often to poll Azure DevOps for new PRs (default: 60 seconds)
PR_POLL_INTERVAL_SECONDS: int = 60

_watcher_enabled: bool = True
_watcher_lock = threading.Lock()


def set_watcher_enabled(enabled: bool) -> None:
    global _watcher_enabled
    with _watcher_lock:
        _watcher_enabled = enabled
    logger.info("[PRWatcher] Watcher enabled=%s", enabled)


def is_watcher_enabled() -> bool:
    with _watcher_lock:
        return _watcher_enabled


class PRWatcher(threading.Thread):
    """
    Daemon thread that periodically invokes `run_poll_tick()`.
    Starts with a short initial delay to let FastAPI finish booting.
    """

    def __init__(self, poll_interval: int = PR_POLL_INTERVAL_SECONDS):
        super().__init__(name="PRWatcherDaemon", daemon=True)
        self._stop_event = threading.Event()
        self._poll_interval = poll_interval

    def run(self) -> None:
        logger.info(
            "[PRWatcher] Daemon thread active. Waiting 10s before initial poll..."
        )
        # Brief warm-up delay
        for _ in range(10):
            if self._stop_event.is_set():
                return
            time.sleep(1)

        daemon_status["running"] = True
        logger.info("[PRWatcher] Starting first PR poll sweep...")
        self._do_poll()

        elapsed = 0
        while not self._stop_event.is_set():
            time.sleep(1)
            elapsed += 1
            if elapsed >= self._poll_interval:
                elapsed = 0
                self._do_poll()

        daemon_status["running"] = False
        logger.info("[PRWatcher] Daemon thread stopping gracefully.")

    def _do_poll(self) -> None:
        if not is_watcher_enabled():
            logger.info("[PRWatcher] Watcher is paused — skipping poll tick.")
            return
        try:
            run_poll_tick()
        except Exception as exc:
            logger.error("[PRWatcher] Unhandled error during poll tick: %s", exc)

    def stop(self) -> None:
        self._stop_event.set()
        daemon_status["running"] = False
