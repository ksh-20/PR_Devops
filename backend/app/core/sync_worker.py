from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import threading
import time
from datetime import datetime, timezone
import json
import os

_config_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.json"))

from core.data_cache import cache
from services.Azure.azure_auth import azure_project_var
from services.Azure_Devops.projects_service import fetch_projects
from services.Azure_Devops.repositories_service import fetch_all_repositories
from services.Azure.subscriptions import fetch_subscriptions
from services.Azure.costs import (
    fetch_total_cost,
    fetch_resource_group_costs,
    fetch_service_costs,
    fetch_top_resources,
    fetch_budgets,
    fetch_yearly_costs,
    fetch_aggregated_monthly_costs,
    fetch_monthly_costs
)

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS: int = 7_200   # 2 hours

def _sync_projects() -> None:
    try:
        result = fetch_projects()
        if isinstance(result, dict) and result.get("success", True):
            cache.set("projects", result)
            logger.info("[SyncWorker] projects cached (%d entries)", len(result.get("projects", [])))
    except Exception as exc:
        logger.warning("[SyncWorker] projects sync failed: %s", exc)

def _sync_repos() -> None:
    try:
        result = fetch_all_repositories()
        if isinstance(result, dict) and result.get("success", True):
            cache.set("repos", result)
            logger.info("[SyncWorker] repos cached (%d entries)", len(result.get("repositories", [])))
    except Exception as exc:
        logger.warning("[SyncWorker] repos sync failed: %s", exc)


def _sync_subscriptions() -> list:
    try:
        with open(_config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        logger.error("JSON file not found at %s: %s", _config_path, e)
        config = {}

    projects = []

    for key in config.keys():
        if key.endswith("_TENANT_ID"):
            prefix = key[:-10]

            if (f"{prefix}_CLIENT_ID" in config and f"{prefix}_CLIENT_SECRET" in config):
                if prefix == "DOC_FLOW":
                    name = "AiDocFlo"
                else:
                    words = prefix.lower().split("_")
                    name = "".join(word.capitalize() for word in words)

                projects.append(name)

    if not projects:
        projects = [None]

    all_sub_ids = []
    all_subscriptions = []
    sub_project_map = {}

    for proj in projects:
        try:
            result = fetch_subscriptions(proj)

            if isinstance(result, dict) and not result.get("error"):
                cache.set(f"subscriptions:{proj}", result)

                subs = result.get("subscriptions", [])
                all_subscriptions.extend(subs)

                for s in subs:
                    sub_id = s.get("subscriptionId")

                    if sub_id:
                        all_sub_ids.append((sub_id, proj))
                        sub_project_map[sub_id] = proj

        except Exception as exc:
            logger.warning("[SyncWorker] subscriptions sync failed for project %s: %s",proj,exc,)

    if all_subscriptions:
        cache.set(
            "subscriptions",
            {
                "success": True,
                "subscriptions": all_subscriptions,
            },
        )

        logger.info("[SyncWorker] all subscriptions cached (%d entries)",len(all_subscriptions),)

    if sub_project_map:
        cache.set("sub_project_map", sub_project_map)
        logger.info("[SyncWorker] sub_project_map cached (%d entries)",len(sub_project_map),)

    return all_sub_ids

def _sync_cost_trend() -> None:
    try:
        with open(_config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        logger.error("JSON file not found at %s: %s", _config_path, e)
        config = {}

    projects = []

    for key in config.keys():
        if key.endswith("_TENANT_ID"):
            prefix = key[:-10]

            if (f"{prefix}_CLIENT_ID" in config and f"{prefix}_CLIENT_SECRET" in config):
                if prefix == "DOC_FLOW":
                    name = "AiDocFlo"
                else:
                    words = prefix.lower().split("_")
                    name = "".join(word.capitalize() for word in words)

                projects.append(name)

    if not projects:
        projects = [None]

    for proj in projects:
        try:
            azure_project_var.set(proj)
            result = fetch_aggregated_monthly_costs(proj)

            if isinstance(result, dict) and result.get("success"):
                cache.set(f"costs:trend:{proj}", result)

                if proj == projects[0]:
                    cache.set("costs:trend", result)

                logger.info("[SyncWorker] cost trend analytics timeline cached successfully for project %s",proj,)

        except Exception as exc:
            logger.warning("[SyncWorker] cost trend sync failed for project %s: %s",proj,exc,)

def _sync_costs_for_subscription(sub_id: str, from_date: str = None, to_date: str = None) -> None:
    try:
        result = fetch_total_cost(sub_id)
        if isinstance(result, dict) and result.get("success"):
            cache.set(f"costs:{sub_id}", result)
            cache.set(f"total:{sub_id}", result)
            logger.info("[SyncWorker] costs+total cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] costs sync failed for sub=%s: %s", sub_id, exc)

    try:
        result = fetch_resource_group_costs(sub_id)
        if isinstance(result, dict) and result.get("success"):
            cache.set(f"resourcegroups:{sub_id}", result)
            logger.info("[SyncWorker] resourcegroups cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] resourcegroups sync failed for sub=%s: %s", sub_id, exc)

    try:
        result = fetch_service_costs(sub_id, from_date, to_date)
        if isinstance(result, dict) and result.get("success"):
            cache.set(f"services:{sub_id}", result)
            logger.info("[SyncWorker] services cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] services sync failed for sub=%s: %s", sub_id, exc)

    try:
        result = fetch_top_resources(sub_id, from_date, to_date)
        # Verify the payload structure is successful and contains valid items before committing to memory
        if isinstance(result, dict) and result.get("success") and result.get("top_resources"):
            cache.set(f"topresources:{sub_id}", result)
            logger.info("[SyncWorker] topresources successfully validated and cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] topresources sync failed for sub=%s: %s", sub_id, exc)

    try:
        result = fetch_budgets(sub_id)
        if isinstance(result, dict) and result.get("success"):
            cache.set(f"budgets:{sub_id}", result)
            logger.info("[SyncWorker] budgets cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] budgets sync failed for sub=%s: %s", sub_id, exc)

    try:
        result = fetch_yearly_costs(sub_id)
        if isinstance(result, dict) and result.get("success") and result.get("yearly_cost", 0) > 0:
            cache.set(f"yearly:{sub_id}", result)
            logger.info("[SyncWorker] yearly costs cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] yearly sync failed for sub=%s: %s", sub_id, exc)

    try:
        result = fetch_monthly_costs(sub_id)
        if isinstance(result, dict) and result.get("success") and result.get("rows"):
            cache.set(f"monthly:{sub_id}", result)
            logger.info("[SyncWorker] historical monthly intervals cached for sub=%s", sub_id)
    except Exception as exc:
        logger.warning("[SyncWorker] historical trend lines sync failed for sub=%s: %s", sub_id, exc)

    time.sleep(3.0)

def run_sync() -> None:
    logger.info("[SyncWorker] Starting sync sweep")
    cache.set("worker_status", "running")

    try:
        _sync_projects()
        _sync_repos()
        sub_ids = _sync_subscriptions()

        if sub_ids:
            for sub_id, proj in sub_ids:
                azure_project_var.set(proj)
                _sync_costs_for_subscription(sub_id)
            _sync_cost_trend()
        else:
            logger.info("[SyncWorker] No active subscriptions found — skipping cost matrix sync")

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cache.set("last_sync_time", now_utc)
        cache.set("worker_status", "idle")
        logger.info("[SyncWorker] ── Sync completed successfully at %s ──", now_utc)

    except Exception as exc:
        cache.set("worker_status", f"error:{exc}")
        logger.error("[SyncWorker] Unexpected sweep failure: %s", exc)


class SyncWorker(threading.Thread):
    def __init__(self):
        super().__init__(name="AzureSyncWorker", daemon=True)
        self._stop_event = threading.Event()

    def run(self) -> None:
        logger.info("[SyncWorker] Daemon thread active. Waiting 15s before initial sync sweep...")
        for _ in range(15):
            if self._stop_event.is_set():
                logger.info("[SyncWorker] Stop event set during initial delay. Exiting.")
                return
            time.sleep(1)

        run_sync()

        elapsed = 0
        while not self._stop_event.is_set():
            time.sleep(1)
            elapsed += 1
            if elapsed >= SYNC_INTERVAL_SECONDS:
                elapsed = 0
                run_sync()
        logger.info("[SyncWorker] Daemon thread stopping gracefully.")

    def stop(self) -> None:
        self._stop_event.set()