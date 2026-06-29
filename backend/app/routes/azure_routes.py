from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import os
from fastapi import APIRouter, Query
from core.data_cache import cache
from core.azure_throttle import range_cache
from services.Azure.azure_auth import azure_project_var
from services.Azure.subscriptions import fetch_subscriptions
import json
from services.Azure.costs import (
    fetch_total_cost,
    fetch_daily_costs,
    fetch_daily_costs_by_range,
    fetch_monthly_costs,
    fetch_yearly_costs,
    fetch_resource_group_costs,
    fetch_service_costs,
    fetch_resource_costs,
    fetch_top_resources,
    fetch_budgets,
    fetch_aggregated_monthly_costs,
    normalize_utc_date,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/azure", tags=["Azure"])


def resolve_project_for_subscription(subscription_id: str) -> str | None:
    if not subscription_id:
        return None

    sub_map = cache.get("sub_project_map")
    if not isinstance(sub_map, dict) or not sub_map:
        return None

    if subscription_id in sub_map:
        return sub_map[subscription_id]

    sub_lower = subscription_id.lower()
    for sub_id, proj in sub_map.items():
        if isinstance(sub_id, str) and sub_id.lower() == sub_lower:
            return proj

    return None


def _set_project_context(subscription_id: str, project: str | None) -> str | None:
    if not project:
        project = resolve_project_for_subscription(subscription_id)
    azure_project_var.set(project)
    return project


def _cache_query(cache_key: str, fetch_fn, cold_default: dict):
    if cache.has(cache_key):
        return cache.get(cache_key)

    # Cache miss: fetch live from Azure
    live_result = fetch_fn()
    if isinstance(live_result, dict) and live_result.get("success"):
        # Only cache successes so we never persist stale empty results
        cache.set(cache_key, live_result)
        return live_result
    if isinstance(live_result, dict) and live_result:
        # Return the real error payload so the frontend shows it
        return live_result
    return cold_default


@router.get("/projects")
async def get_azure_projects():
    try:
        # Resolve config path
        _config_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
        with open(_config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        logger.error("[AzureRoutes] Failed to load config.json at %s: %s", _config_path, str(e))
        config = {}

    projects = []
    for key in config.keys():
        if key.endswith("_TENANT_ID"):
            prefix = key[:-10]
            if f"{prefix}_CLIENT_ID" in config and f"{prefix}_CLIENT_SECRET" in config:
                if prefix == "DOC_FLOW":
                    name = "AiDocFlo"
                else:
                    words = prefix.lower().split("_")
                    name = "".join(word.capitalize() for word in words)
                projects.append(name)
    return {"success": True, "projects": projects}


_COLD_TREND_FALLBACK = {
    "success": True,
    "trend": [
        {"month": "January", "cost": 0}, {"month": "February", "cost": 0},
        {"month": "March", "cost": 0}, {"month": "April", "cost": 0},
        {"month": "May", "cost": 0}, {"month": "June", "cost": 0}
    ]
}
_COLD_COST_RESPONSE = {"success": True, "total_cost": 0.0, "amount": 0.0}
_COLD_SUBSCRIPTIONS = {
    "success": False,
    "subscriptions": [],
    "message": "Data is warming up. The background sync is in progress — please retry in a few seconds.",
}


@router.get("/costs/trend")
async def get_cost_trend(project: str = Query(None)):
    try:
        azure_project_var.set(project)
        cache_key = f"costs:trend:{project}" if project else "costs:trend"
        return _cache_query(
            cache_key,
            lambda: fetch_aggregated_monthly_costs(project),
            _COLD_TREND_FALLBACK,
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_cost_trend: %s", str(e))
        return _COLD_TREND_FALLBACK


@router.get("/subscriptions")
async def get_subscriptions(project: str = Query(None)):
    try:
        azure_project_var.set(project)
        cache_key = f"subscriptions:{project}" if project else "subscriptions"
        return _cache_query(
            cache_key,
            lambda: fetch_subscriptions(project),
            _COLD_SUBSCRIPTIONS,
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_subscriptions: %s", str(e))
        return _COLD_SUBSCRIPTIONS


@router.get("/costs/combined-yearly")
async def get_combined_yearly_costs():
    try:
        try:
            _config_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
            with open(_config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error("[AzureRoutes] Failed to load config.json at %s: %s", _config_path, str(e))
            config = {}

        projects = []
        for key in config.keys():
            if key.endswith("_TENANT_ID"):
                prefix = key[:-10]
                if f"{prefix}_CLIENT_ID" in config and f"{prefix}_CLIENT_SECRET" in config:
                    if prefix == "DOC_FLOW":
                        name = "AiDocFlo"
                    else:
                        words = prefix.lower().split("_")
                        name = "".join(word.capitalize() for word in words)
                    projects.append(name)

        total_combined = 0.0
        for proj in projects:
            try:
                subs_res = fetch_subscriptions(proj)
                subs = []
                if isinstance(subs_res, dict) and "subscriptions" in subs_res:
                    subs = subs_res["subscriptions"]
                elif isinstance(subs_res, list):
                    subs = subs_res
                    
                for sub in subs:
                    sub_id = sub.get("subscriptionId")
                    if not sub_id:
                        continue
                    azure_project_var.set(proj)
                    yearly_res = _cache_query(
                        f"yearly:{sub_id}",
                        lambda s=sub_id: fetch_yearly_costs(s),
                        {"success": True, "yearly_cost": 0.0}
                    )
                    if isinstance(yearly_res, dict):
                        total_combined += yearly_res.get("yearly_cost", 0.0)
            except Exception as e:
                logger.error("[AzureRoutes] Failed to fetch yearly costs for project %s: %s", proj, str(e))

        return {"success": True, "yearly_cost": total_combined}
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_combined_yearly_costs: %s", str(e))
        return {"success": False, "yearly_cost": 0.0}


@router.get("/costs/global-overview")
async def get_global_overview():
    try:
        # Get active projects
        projects_res = get_azure_projects()
        projects = projects_res.get("projects", [])
        
        overview = []
        for proj in projects:
            proj_data = {
                "project": proj,
                "devTest": 0.0,
                "production": 0.0
            }
            # Fetch subscriptions for this project
            subs_res = fetch_subscriptions(proj)
            subs = subs_res.get("subscriptions", []) if isinstance(subs_res, dict) else []
            for sub in subs:
                sub_id = sub.get("subscriptionId")
                display_name = sub.get("displayName", "").lower()
                
                # Check environment environment
                is_prod = "prod" in display_name
                is_dev_test = "dev" in display_name or "test" in display_name
                
                # Fallback matching
                if not is_prod and not is_dev_test:
                    is_dev_test = True
                
                # Fetch total cost (month-to-date)
                cost_res = fetch_total_cost(sub_id)
                cost = cost_res.get("total_cost", 0.0) if isinstance(cost_res, dict) else 0.0
                
                if is_prod:
                    proj_data["production"] += cost
                else:
                    proj_data["devTest"] += cost
            overview.append(proj_data)
            
        return {"success": True, "overview": overview}
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_global_overview: %s", str(e))
        return {"success": False, "error": str(e), "overview": []}


@router.get("/costs/{subscription_id}")
async def get_costs(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"costs:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_total_cost(subscription_id),
            _COLD_COST_RESPONSE,
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_costs: %s", str(e))
        return _COLD_COST_RESPONSE


@router.get("/costs/{subscription_id}/total")
async def get_total_cost(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"total:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_total_cost(subscription_id),
            _COLD_COST_RESPONSE,
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_total_cost: %s", str(e))
        return _COLD_COST_RESPONSE


@router.get("/costs/{subscription_id}/resourcegroups")
async def get_resource_group_costs(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"resourcegroups:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_resource_group_costs(subscription_id),
            {"success": True, "resource_groups": [], "rows": []},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_resource_group_costs: %s", str(e))
        return {"success": True, "resource_groups": [], "rows": []}


@router.get("/costs/{subscription_id}/services")
async def get_service_costs(
    subscription_id: str,
    from_date: str = Query(None),
    to_date: str = Query(None),
    project: str = Query(None),
):
    try:
        _set_project_context(subscription_id, project)

        utc_from = normalize_utc_date(from_date) if from_date else None
        utc_to = normalize_utc_date(to_date) if to_date else None

        if utc_from and utc_to:
            # Check 5-minute TTL cache first — avoids redundant Azure quota hits
            ttl_key = f"svc:{subscription_id}:{utc_from}:{utc_to}"
            cached = range_cache.get(ttl_key)
            if cached is not None:
                return cached

            result = fetch_service_costs(subscription_id, utc_from, utc_to)
            if isinstance(result, dict) and result.get("success"):
                range_cache.set(ttl_key, result)
            if isinstance(result, dict) and result:
                return result
            return {"success": False, "services": [], "rows": [], "error": "No service cost data for this date range."}

        # No date range: serve from persistent cache (MTD fallback)
        cache_key = f"services:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_service_costs(subscription_id, None, None),
            {"success": True, "services": [], "rows": []},
            )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_service_costs: %s", str(e))
        return {"success": True, "services": [], "rows": []}


@router.get("/costs/{subscription_id}/top-resources")
async def get_top_resources(
    subscription_id: str,
    from_date: str = Query(None),
    to_date: str = Query(None),
    project: str = Query(None),
):
    try:
        _set_project_context(subscription_id, project)

        utc_from = normalize_utc_date(from_date) if from_date else None
        utc_to = normalize_utc_date(to_date) if to_date else None

        if utc_from and utc_to:
            # Check 5-minute TTL cache first — avoids redundant Azure quota hits
            ttl_key = f"topres:{subscription_id}:{utc_from}:{utc_to}"
            cached = range_cache.get(ttl_key)
            if cached is not None:
                return cached

            result = fetch_top_resources(subscription_id, utc_from, utc_to)
            if isinstance(result, dict) and result.get("success"):
                range_cache.set(ttl_key, result)
            if isinstance(result, dict) and result:
                return result
            return {"success": False, "top_resources": [], "rows": [], "error": "No resource data for this date range."}

        # No date range: serve from persistent cache (MTD fallback)
        cache_key = f"topresources:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_top_resources(subscription_id, None, None),
            {"success": True, "top_resources": [], "rows": []},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_top_resources: %s", str(e))
        return {"success": True, "top_resources": [], "rows": []}


@router.get("/costs/{subscription_id}/budgets")
async def get_budgets(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"budgets:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_budgets(subscription_id),
            {"success": True, "budgets": []},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_budgets: %s", str(e))
        return {"success": True, "budgets": []}


@router.get("/costs/{subscription_id}/yearly")
async def get_yearly_costs(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"yearly:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_yearly_costs(subscription_id),
            {"success": True, "yearly_costs": [], "rows": [], "yearly_cost": 0.0},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_yearly_costs: %s", str(e))
        return {"success": True, "yearly_costs": [], "rows": [], "yearly_cost": 0.0}


@router.get("/costs/{subscription_id}/daily")
async def get_daily_costs(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"daily:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_daily_costs(subscription_id),
            {"success": True, "daily_costs": [], "rows": []},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_daily_costs: %s", str(e))
        return {"success": True, "daily_costs": [], "rows": []}


@router.get("/costs/{subscription_id}/daily-range")
async def get_daily_costs_by_range(
    subscription_id: str,
    from_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    to_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    project: str = Query(None),
):
    try:
        _set_project_context(subscription_id, project)

        utc_from = normalize_utc_date(from_date)
        utc_to = normalize_utc_date(to_date)

        ttl_key = f"dailyrange:{subscription_id}:{utc_from}:{utc_to}"
        cached = range_cache.get(ttl_key)
        if cached is not None:
            return cached

        result = fetch_daily_costs_by_range(subscription_id, utc_from, utc_to)
        if isinstance(result, dict) and result.get("success"):
            range_cache.set(ttl_key, result)
        if isinstance(result, dict) and result:
            return result
        return {"success": False, "points": [], "count": 0, "error": "No data returned from Azure for this date range."}
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_daily_costs_by_range: %s", str(e))
        return {"success": False, "points": [], "count": 0}


@router.get("/costs/{subscription_id}/monthly")
async def get_monthly_costs(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"monthly:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_monthly_costs(subscription_id),
            {"success": True, "monthly_costs": [], "rows": []},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_monthly_costs: %s", str(e))
        return {"success": True, "monthly_costs": [], "rows": []}


@router.get("/costs/{subscription_id}/resources")
async def get_resource_costs(subscription_id: str, project: str = Query(None)):
    try:
        _set_project_context(subscription_id, project)
        cache_key = f"resources:{subscription_id}"
        return _cache_query(
            cache_key,
            lambda: fetch_resource_costs(subscription_id),
            {"success": True, "resources": [], "rows": []},
        )
    except Exception as e:
        logger.error("[AzureRoutes] Failed executing get_resource_costs: %s", str(e))
        return {"success": True, "resources": [], "rows": []}
