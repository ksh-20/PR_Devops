from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
from contextvars import ContextVar
import json
import os
import re
from collections import defaultdict

from core.azure_throttle import token_cache

logger = logging.getLogger(__name__)

azure_project_var = ContextVar("azure_project", default=None)


def _load_project_credentials():
    try:
        _config_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "config.json"))
        with open(_config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        logger.error("JSON file not found at %s: %s", _config_path, e)
        config = {}

    projects = defaultdict(dict)

    for key, value in config.items():
        parts = key.split("_")

        if len(parts) < 3:
            continue

        prefix = "_".join(parts[:-2])
        credential = "_".join(parts[-2:])

        projects[prefix][credential] = value

    return dict(projects)


def get_azure_token(project_name: str = None):
    projects = _load_project_credentials()

    if not projects:
        raise ValueError("No Azure configuration found")

    if not project_name:
        project_name = azure_project_var.get()

    creds = None

    if project_name:
        normalized = str(project_name).replace(" ", "").replace("_", "").lower()
        if normalized == "aidocflo":
            normalized = "docflow"

        for prefix, values in projects.items():
            prefix_normalized = prefix.replace("_", "").lower()

            if normalized == prefix_normalized:
                creds = values
                break

    if creds is None:
        # Find the first project with complete tenant/client credentials to avoid matching storage config
        for prefix, values in projects.items():
            if all(k in values for k in ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"]):
                creds = values
                break

    t_id = creds.get("TENANT_ID")
    c_id = creds.get("CLIENT_ID")
    c_secret = creds.get("CLIENT_SECRET")

    if not all([t_id, c_id, c_secret]):
        logger.error("[AzureAuth] Azure configuration is incomplete for project '%s'",project_name,)
        raise ValueError("Azure configuration is incomplete or missing in config.json")

    cached_token = token_cache.get(t_id, c_id)
    if cached_token:
        logger.debug("[AzureAuth] Token cache hit for project '%s' (tenant=%s)",project_name,t_id,)
        return cached_token

    url = f"https://login.microsoftonline.com/{t_id}/oauth2/v2.0/token"

    payload = {
        "client_id": c_id,
        "client_secret": c_secret,
        "scope": "https://management.azure.com/.default",
        "grant_type": "client_credentials",
    }

    response = requests.post(url, data=payload, timeout=10)
    response.raise_for_status()

    token = response.json()["access_token"]

    token_cache.set(t_id, c_id, token)

    logger.info("[AzureAuth] Acquired and cached new Azure AD token for project '%s' (tenant=%s)",project_name,t_id,)

    return token