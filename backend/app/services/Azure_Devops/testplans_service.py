from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
from requests.auth import HTTPBasicAuth
import urllib3

from core.config import base_url, collection, pat
from services.Azure_Devops.projects_service import fetch_projects
from exceptions.handler import handle_error_response
from core.auth import auth
from core.constants import API_VERSION, RESOURCE_TESTPLAN

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def fetch_test_plans(project_name):
    logger.info("[TestPlansService] Fetching test plans for project: %s", project_name)
    if not base_url or not collection or not pat:
        logger.warning("[TestPlansService] Azure DevOps not configured — skipping test plans fetch for '%s'", project_name)
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "test_plans": []
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/testplan/plans?api-version={API_VERSION}-preview.1"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"{RESOURCE_TESTPLAN} in project '{project_name}'")
        
        tps = []
        data = response.json()
        for tp in data.get("value", []):
            if not isinstance(tp, dict):
                continue
            owner_info = tp.get("owner")
            owner_name = owner_info.get("displayName", "Unassigned") if isinstance(owner_info, dict) else "Unassigned"

            tps.append({
                "id": tp.get("id"),
                "name": tp.get("name"),
                "owner": owner_name,
                "state": tp.get("state"),
                "areaPath": tp.get("areaPath"),
                "iteration": tp.get("iteration"),
                "startDate" : tp.get("startDate"),
                "endDate" : tp.get("endDate")
            })

        result = {
            "success" : True,
            "count" : len(tps),
            "test_plans" : tps
        }
        logger.info("[TestPlansService] Test plans fetched: %d plans for project '%s'", len(tps), project_name)
        return result
    except Exception as e:
        logger.error("[TestPlansService] Failed to fetch test plans for '%s': %s", project_name, e, exc_info=True)
        return {
            "success": False,
            "message": f"Failed to fetch test plans: {str(e)}",
            "test_plans": []
        }