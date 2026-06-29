from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
import time
from datetime import datetime, timezone
import random

from services.Azure.azure_auth import get_azure_token
from core.config import azure_cost_base_url
from core.azure_cache import get_cached_azure_data, get_cache_key, determine_cost_query_ttl
from services.Azure.subscriptions import fetch_subscriptions
from core.data_cache import cache 
from core.azure_throttle import azure_semaphore

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_utc_date(date_str: str | None) -> str:
    if not date_str:
        return ""
    raw = str(date_str).strip()
    if not raw:
        return ""

    if "T" in raw:
        raw = raw.split("T")[0]

    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw

    if len(raw) == 8 and raw[4].isdigit() and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else raw


def utc_day_start_iso(date_str: str | None) -> str:
    day = normalize_utc_date(date_str)
    return f"{day}T00:00:00Z" if day else ""


def utc_day_end_iso(date_str: str | None) -> str:
    day = normalize_utc_date(date_str)
    return f"{day}T23:59:59Z" if day else ""


def build_dated_cache_key(prefix: str, subscription_id: str, from_date: str | None, to_date: str | None) -> str:
    if from_date and to_date:
        utc_from = normalize_utc_date(from_date)
        utc_to = normalize_utc_date(to_date)
        return f"{prefix}:{subscription_id}:{utc_from}:{utc_to}"
    return f"{prefix}:{subscription_id}"


def _stamp_utc_metadata(payload: dict, from_date: str | None = None, to_date: str | None = None) -> dict:
    if from_date:
        utc_from = normalize_utc_date(from_date)
        payload["fromDate"] = utc_from
        payload["fromDateUtc"] = utc_day_start_iso(utc_from)
    if to_date:
        utc_to = normalize_utc_date(to_date)
        payload["toDate"] = utc_to
        payload["toDateUtc"] = utc_day_end_iso(utc_to)
    payload["fetchedAtUtc"] = utc_now_iso()
    return payload


def _execute_azure_query_live(subscription_id: str, payload: dict):
    MAX_ATTEMPTS = 8
    BASE_DELAY   = 2.0   # seconds
    MAX_DELAY    = 60.0  # seconds cap per sleep

    with azure_semaphore:
        for attempt in range(MAX_ATTEMPTS):
            try:
                token = get_azure_token()
                url = f"{azure_cost_base_url}/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }

                response = requests.post(url, headers=headers, json=payload, timeout=60)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    logger.warning("[AzureQuery] 429 rate-limited sub=%s. Aborting retry loop to protect request timer.",subscription_id)
                    return {
                        "success": False,
                        "status_code": 429,
                        "error": "Azure Cost Management rate limit exceeded. Cached fallback data will be served if available.",
                    }

                if response.status_code >= 500 and attempt < MAX_ATTEMPTS - 1:
                    sleep_time = random.uniform(0, min(MAX_DELAY, BASE_DELAY * (2 ** attempt)))
                    logger.warning("[AzureQuery] HTTP %d sub=%s attempt=%d/%d sleeping=%.1fs",response.status_code, subscription_id, attempt + 1, MAX_ATTEMPTS, sleep_time,)
                    time.sleep(sleep_time)
                    continue

                return {
                    "success": False,
                    "status_code": response.status_code,
                    "rows": [],
                    "detail": f"Azure Cost query returned HTTP {response.status_code}.",
                }

            except requests.exceptions.Timeout:
                sleep_time = random.uniform(0, min(MAX_DELAY, BASE_DELAY * (2 ** attempt)))
                if attempt < MAX_ATTEMPTS - 1:
                    logger.warning("[AzureQuery] timeout sub=%s attempt=%d/%d sleeping=%.1fs",subscription_id, attempt + 1, MAX_ATTEMPTS, sleep_time,)
                    time.sleep(sleep_time)
                    continue
                return {
                    "success": False,
                    "error": "Azure Cost Management request timed out after all retries.",
                    "properties": {"rows": []},
                }

            except Exception as e:
                logger.exception("[AzureQuery] Unexpected query execution error for sub=%s", subscription_id)
                return {
                    "success": False,
                    "error": "Azure Integration is not configured or offline",
                    "message": str(e),
                    "properties": {"rows": []},
                }

        return {
            "success": False,
            "error": "Azure Cost Management did not respond after maximum retry attempts.",
            "properties": {"rows": []},
        }


def _execute_azure_query(subscription_id: str, payload: dict):
    try:
        key = get_cache_key("cost_query", subscription_id, payload)
        ttl = determine_cost_query_ttl(payload)
        return get_cached_azure_data(
            key=key,
            fetch_fn=lambda: _execute_azure_query_live(subscription_id, payload),
            ttl=ttl
        )
    except Exception as e:
        logger.error("[AzureCosts] Failed executing _execute_azure_query: %s", str(e))
        return {"success": False, "error": str(e), "properties": {"rows": []}}


def fetch_total_cost(subscription_id: str):
    try:
        payload = {
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                }
            }
        }
        result = _execute_azure_query(subscription_id, payload)

        if not isinstance(result, dict) or "properties" not in result:
            return _stamp_utc_metadata({
                "success": False,
                "total_cost": 0.0,
                "amount": 0.0,
                "error": result.get("error", "Failed to fetch total cost") if isinstance(result, dict) else "Failed to fetch total cost",
            })

        total_amount = 0.0
        rows = result["properties"].get("rows", [])
        if rows and len(rows) > 0 and len(rows[0]) > 0:
            total_amount = float(rows[0][0])

        return _stamp_utc_metadata({
            "success": True,
            "total_cost": total_amount,
            "amount": total_amount,
        })
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_total_cost: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "total_cost": 0.0,
            "amount": 0.0,
            "error": str(e),
        })


def fetch_service_costs(subscription_id: str, from_date: str = None, to_date: str = None):
    try:
        utc_from = normalize_utc_date(from_date) if from_date else None
        utc_to = normalize_utc_date(to_date) if to_date else None

        if utc_from and utc_to:
            payload = {
                "type": "ActualCost",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": utc_day_start_iso(utc_from),
                    "to": utc_day_end_iso(utc_to),
                },
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"}
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ServiceName"}
                    ]
                }
            }
        else:
            utc_from = None
            utc_to = None
            payload = {
                "type": "ActualCost",
                "timeframe": "MonthToDate",
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"}
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ServiceName"}
                    ]
                }
            }

        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result or result.get("error"):
            return _stamp_utc_metadata({
                "success": False,
                "error": result.get("error", "Failed to fetch service costs") if isinstance(result, dict) else "Failed to fetch service costs",
                "services": [],
                "rows": [],
            }, utc_from, utc_to)

        rows = result.get("properties", {}).get("rows", [])
        return _stamp_utc_metadata({
            "success": True,
            "services": rows,
            "rows": rows,
        }, utc_from, utc_to)
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_service_costs: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "error": str(e),
            "services": [],
            "rows": [],
        }, from_date, to_date)


def fetch_resource_group_costs(subscription_id: str):
    try:
        payload = {
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceGroupName"}
                ]
            }
        }
        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result or result.get("error"):
            return _stamp_utc_metadata({
                "success": False,
                "error": result.get("error", "Failed to fetch resource group costs") if isinstance(result, dict) else "Failed to fetch resource group costs",
                "resource_groups": [],
                "rows": [],
            })

        rows = result.get("properties", {}).get("rows", [])
        return _stamp_utc_metadata({
            "success": True,
            "resource_groups": rows,
            "rows": rows,
        })
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_resource_group_costs: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "error": str(e),
            "resource_groups": [],
            "rows": [],
        })


def fetch_daily_costs(subscription_id: str):
    try:
        payload = {
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                }
            }
        }
        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result:
            return _stamp_utc_metadata({
                "success": False,
                "daily_costs": [],
                "rows": [],
                "error": result.get("error", "Failed to fetch daily costs") if isinstance(result, dict) else "Failed to fetch daily costs",
            })

        rows = result.get("properties", {}).get("rows", [])
        return _stamp_utc_metadata({
            "success": True,
            "daily_costs": rows,
            "rows": rows,
        })
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_daily_costs: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "daily_costs": [],
            "rows": [],
            "error": str(e),
        })


def fetch_daily_costs_by_range(subscription_id: str, from_date: str, to_date: str):
    try:
        utc_from = normalize_utc_date(from_date)
        utc_to = normalize_utc_date(to_date)

        payload = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {
                "from": utc_day_start_iso(utc_from),
                "to": utc_day_end_iso(utc_to),
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                }
            }
        }
        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result or result.get("error"):
            return _stamp_utc_metadata({
                "success": False,
                "error": result.get("error", "Failed to fetch daily costs") if isinstance(result, dict) else "Failed to fetch daily costs",
                "points": [],
                "count": 0,
            }, utc_from, utc_to)

        raw_rows = result.get("properties", {}).get("rows", [])

        points = []
        for row in raw_rows:
            if len(row) >= 2:
                cost = float(row[0])
                raw_date = str(row[1])
                if len(raw_date) == 8 and raw_date.isdigit():
                    label = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                else:
                    label = normalize_utc_date(raw_date)
                points.append({
                    "date": label,
                    "dateUtc": utc_day_start_iso(label),
                    "cost": round(cost, 2),
                })

        points.sort(key=lambda p: p["date"])
        return _stamp_utc_metadata({
            "success": True,
            "points": points,
            "count": len(points),
        }, utc_from, utc_to)
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_daily_costs_by_range: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "error": str(e),
            "points": [],
            "count": 0,
        }, from_date, to_date)


def fetch_monthly_costs(subscription_id: str):
    try:
        payload = {
            "type": "ActualCost",
            "timeframe": "YearToDate",
            "dataset": {
                "granularity": "Monthly",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                }
            }
        }
        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result:
            return _stamp_utc_metadata({
                "success": False,
                "monthly_costs": [],
                "rows": [],
                "error": result.get("error", "Failed to fetch monthly costs") if isinstance(result, dict) else "Failed to fetch monthly costs",
            })

        rows = result.get("properties", {}).get("rows", [])
        return _stamp_utc_metadata({
            "success": True,
            "monthly_costs": rows,
            "rows": rows,
        })
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_monthly_costs: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "monthly_costs": [],
            "rows": [],
            "error": str(e),
        })


def fetch_yearly_costs(subscription_id: str):
    try:
        payload = {
            "type": "ActualCost",
            "timeframe": "YearToDate",
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                }
            }
        }
        result = _execute_azure_query(subscription_id, payload)

        rows = []
        if isinstance(result, dict) and "properties" in result:
            rows = result["properties"].get("rows", [])
        elif isinstance(result, dict):
            rows = result.get("rows", [])

        if not isinstance(result, dict) or "properties" not in result:
            return _stamp_utc_metadata({
                "success": False,
                "yearly_costs": [],
                "rows": [],
                "yearly_cost": 0.0,
                "amount": 0.0,
                "total_cost": 0.0,
                "error": result.get("error", "Failed to fetch yearly costs") if isinstance(result, dict) else "Failed to fetch yearly costs",
            })

        yearly_amount = 0.0
        if rows and len(rows) > 0 and len(rows[0]) > 0:
            yearly_amount = float(rows[0][0])

        return _stamp_utc_metadata({
            "success": True,
            "yearly_costs": rows,
            "rows": rows,
            "yearly_cost": yearly_amount,
            "amount": yearly_amount,
            "total_cost": yearly_amount,
        })
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_yearly_costs: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "yearly_costs": [],
            "rows": [],
            "yearly_cost": 0.0,
            "amount": 0.0,
            "total_cost": 0.0,
            "error": str(e),
        })


def fetch_resource_costs(subscription_id: str):
    try:
        payload = {
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"}
                ]
            }
        }
        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result:
            return _stamp_utc_metadata({
                "success": False,
                "resources": [],
                "rows": [],
                "error": result.get("error", "Failed to fetch resource costs") if isinstance(result, dict) else "Failed to fetch resource costs",
            })

        rows = result.get("properties", {}).get("rows", [])
        return _stamp_utc_metadata({
            "success": True,
            "resources": rows,
            "rows": rows,
        })
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_resource_costs: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "resources": [],
            "rows": [],
            "error": str(e),
        })


def _extract_resource_name(resource_id: str) -> str:
    if not resource_id or not isinstance(resource_id, str):
        return resource_id or "Unknown"
    parts = [p for p in resource_id.strip("/").split("/") if p]
    return parts[-1] if parts else resource_id


def fetch_top_resources(subscription_id: str, from_date: str = None, to_date: str = None):
    try:
        utc_from = normalize_utc_date(from_date) if from_date else None
        utc_to = normalize_utc_date(to_date) if to_date else None

        if utc_from and utc_to:
            payload = {
                "type": "ActualCost",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": utc_day_start_iso(utc_from),
                    "to": utc_day_end_iso(utc_to),
                },
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"}
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ResourceId"}
                    ]
                }
            }
        else:
            utc_from = None
            utc_to = None
            payload = {
                "type": "ActualCost",
                "timeframe": "MonthToDate",
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"}
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ResourceId"}
                    ]
                }
            }

        result = _execute_azure_query(subscription_id, payload)
        if not isinstance(result, dict) or "properties" not in result or result.get("error"):
            return _stamp_utc_metadata({
                "success": False,
                "error": result.get("error", "Failed to fetch top resources") if isinstance(result, dict) else "Failed to fetch top resources",
                "top_resources": [],
                "rows": [],
            }, utc_from, utc_to)

        rows = result.get("properties", {}).get("rows", [])
        sorted_rows = sorted(rows, key=lambda x: x[0], reverse=True) if rows else []

        cleaned_rows = []
        for row in sorted_rows[:10]:
            if len(row) >= 2:
                cleaned = list(row)
                cleaned[1] = _extract_resource_name(str(row[1]))
                cleaned_rows.append(cleaned)
            else:
                cleaned_rows.append(row)

        return _stamp_utc_metadata({
            "success": True,
            "top_resources": cleaned_rows,
            "rows": cleaned_rows,
        }, utc_from, utc_to)
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_top_resources: %s", str(e))
        return _stamp_utc_metadata({
            "success": False,
            "error": str(e),
            "top_resources": [],
            "rows": [],
        }, from_date, to_date)


def _fetch_budgets_live(subscription_id: str):
    token = get_azure_token()
    url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Consumption/budgets?api-version=2023-05-01"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    budgets = []
    for b in data.get("value", []):
        if not isinstance(b, dict):
            continue
        props = b.get("properties", {})
        budgets.append({
            "name": b.get("name"),
            "amount": props.get("amount"),
            "timeGrain": props.get("timeGrain")
        })
    return _stamp_utc_metadata({"success": True, "budgets": budgets})


def fetch_budgets(subscription_id: str):
    try:
        key = get_cache_key("budgets", subscription_id)
        return get_cached_azure_data(
            key=key,
            fetch_fn=lambda: _fetch_budgets_live(subscription_id),
            ttl=7200
        )
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_budgets: %s", str(e))
        return _stamp_utc_metadata({"success": True, "budgets": [], "error": str(e)})


def fetch_aggregated_monthly_costs(project_name: str = None):
    try:
        try:
            subs_data = fetch_subscriptions(project_name)
        except Exception:
            subs_data = []

        subs = []
        if isinstance(subs_data, dict) and "subscriptions" in subs_data:
            subs = subs_data["subscriptions"]
        elif isinstance(subs_data, list):
            subs = subs_data

        fallback_data = [
            {"month": "January", "cost": 0}, {"month": "February", "cost": 0},
            {"month": "March", "cost": 0}, {"month": "April", "cost": 0},
            {"month": "May", "cost": 0}, {"month": "June", "cost": 0}
        ]

        if not subs:
            return _stamp_utc_metadata({
                "success": False,
                "trend": fallback_data,
                "error": "No subscriptions found",
            })

        aggregated = {}
        has_real_data = False

        for sub in subs:
            sub_id = sub.get("subscriptionId")
            if not sub_id:
                continue
            try:
                res = cache.get(f"monthly:{sub_id}")

                if not res or not isinstance(res, dict) or not res.get("rows"):
                    res = fetch_monthly_costs(sub_id)

                if res and res.get("success") and res.get("rows"):
                    has_real_data = True
                    for row in res["rows"]:
                        if len(row) >= 2:
                            cost = float(row[0])
                            month_raw = str(row[1])
                            month_name = _parse_month_name(month_raw)
                            if month_name:
                                aggregated[month_name] = aggregated.get(month_name, 0.0) + cost
            except Exception:
                pass

        if not has_real_data:
            return _stamp_utc_metadata({
                "success": False,
                "trend": fallback_data,
                "error": "API rate-limited or cache warming up",
            })

        month_order = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        trend = []
        for m in month_order:
            if m in aggregated:
                trend.append({"month": m, "cost": round(aggregated[m], 2)})

        if not trend:
            return _stamp_utc_metadata({
                "success": False,
                "trend": fallback_data,
                "error": "Trend aggregation compiled empty",
            })

        return _stamp_utc_metadata({"success": True, "trend": trend})
    except Exception as e:
        logger.error("[AzureCosts] Failed executing fetch_aggregated_monthly_costs: %s", str(e))
        fallback_data = [
            {"month": "January", "cost": 0}, {"month": "February", "cost": 0},
            {"month": "March", "cost": 0}, {"month": "April", "cost": 0},
            {"month": "May", "cost": 0}, {"month": "June", "cost": 0}
        ]
        return _stamp_utc_metadata({
            "success": False,
            "trend": fallback_data,
            "error": str(e),
        })


def _parse_month_name(month_str: str) -> str:
    cleaned = month_str.replace("-", "").replace("/", "").strip()
    month_num = None
    if len(cleaned) >= 6 and cleaned[:4].isdigit() and cleaned[4:6].isdigit():
        month_num = int(cleaned[4:6])
    elif len(cleaned) >= 2 and cleaned.isdigit():
        month_num = int(cleaned)

    month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    if month_num and 1 <= month_num <= 12:
        return month_names[month_num - 1]

    for m in month_names:
        if m.lower() in month_str.lower():
            return m

    return ""