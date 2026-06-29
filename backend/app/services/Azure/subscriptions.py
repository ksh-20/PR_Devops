from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests

from services.Azure.azure_auth import get_azure_token
from core.config import azure_management_base_url

logger = logging.getLogger(__name__)


def _fetch_subscriptions_live(project_name: str = None):
    logger.info("[Subscriptions] Fetching live subscriptions for project: %s", project_name)
    if not azure_management_base_url:
        logger.error("[Subscriptions] Azure Management Base URL is not configured in config.json")
        raise ValueError("Azure Management Base URL is not configured")
    token = get_azure_token(project_name)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    url = f"{azure_management_base_url}?api-version=2020-01-01"

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()
    raw_subs = data.get("value", [])
    subscriptions = []
    for sub in raw_subs:
        if not isinstance(sub, dict):
            continue
        subscriptions.append({
            "subscriptionId": sub.get("subscriptionId"),
            "displayName": sub.get("displayName"),
            "state": sub.get("state")
        })
    logger.info("[Subscriptions] Fetched %d subscriptions for project '%s'", len(subscriptions), project_name)
    return {
        "success": True,
        "subscriptions": subscriptions
    }


def fetch_subscriptions(project_name: str = None):
    logger.info("[Subscriptions] Requesting subscriptions for project: %s", project_name)
    from core.azure_cache import get_cached_azure_data, get_cache_key
    key = get_cache_key("subscriptions", project_name or "default")
    try:
        return get_cached_azure_data(
            key=key,
            fetch_fn=lambda: _fetch_subscriptions_live(project_name),
            ttl=7200
        )
    except Exception as e:
        logger.error("[Subscriptions] Failed to fetch subscriptions for project '%s': %s", project_name, e, exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "subscriptions": []
        }