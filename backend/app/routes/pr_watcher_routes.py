"""
pr_watcher_routes.py
--------------------
REST endpoints to inspect and control the PR Auto-Review Daemon.

Routes
------
GET  /api/pr_watcher/status      → current daemon status + last reviews
POST /api/pr_watcher/enable      → un-pause the daemon
POST /api/pr_watcher/disable     → pause polling (does not stop the thread)
POST /api/pr_watcher/trigger     → force an immediate poll tick (async)
POST /api/pr_watcher/reset       → wipe persisted reviewed-PR state
"""

import threading
from fastapi import APIRouter
from services.reviewer.auto_review_daemon import (
    get_daemon_status,
    clear_reviewed_state,
    run_poll_tick,
)
from core.pr_watcher import set_watcher_enabled, is_watcher_enabled

router = APIRouter(tags=["PR Auto-Review Watcher"])


@router.get("/pr_watcher/status")
async def watcher_status():
    """Return the live status of the PR auto-review daemon."""
    status = get_daemon_status()
    status["enabled"] = is_watcher_enabled()
    return {"success": True, "data": status}


@router.post("/pr_watcher/enable")
async def enable_watcher():
    """Re-enable the auto-review daemon after it was paused."""
    set_watcher_enabled(True)
    return {"success": True, "message": "PR Auto-Review Daemon enabled."}


@router.post("/pr_watcher/disable")
async def disable_watcher():
    """Pause the auto-review daemon (thread keeps running, polls are skipped)."""
    set_watcher_enabled(False)
    return {"success": True, "message": "PR Auto-Review Daemon paused."}


@router.post("/pr_watcher/trigger")
async def trigger_poll():
    """
    Immediately fire a poll tick in a background thread.
    Returns instantly — check /status to see results.
    """
    def _run():
        run_poll_tick()

    t = threading.Thread(target=_run, daemon=True, name="PRWatcher-ManualTick")
    t.start()
    return {
        "success": True,
        "message": "Manual poll tick triggered. Check /api/pr_watcher/status for results.",
    }


@router.post("/pr_watcher/reset")
async def reset_reviewed_state():
    """
    Clear the persisted set of already-reviewed PRs.
    The daemon will re-review all currently-active PRs on the next poll.
    """
    result = clear_reviewed_state()
    return result
