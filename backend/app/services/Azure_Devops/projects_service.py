from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
from requests.auth import HTTPBasicAuth
import urllib3

from core.config import base_url, collection, pat
from exceptions.handler import handle_error_response
from core.auth import auth
from core.constants import API_VERSION, RESOURCE_PROJECT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def fetch_projects():
    logger.info("[ProjectsService] Fetching projects from Azure DevOps")
    if not base_url or not collection or not pat:
        logger.warning("[ProjectsService] Azure DevOps not configured — skipping projects fetch")
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "projects": []
        }
    try:
        url = f"{base_url}/{collection}/_apis/projects?api-version={API_VERSION}"
        response = requests.get(url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"{RESOURCE_PROJECT}")

        projects = []
        data = response.json()
        for project in data.get("value", []):
            if not isinstance(project, dict):
                continue
            proj_name = project.get("name", "")
            projects.append({
                "id": project.get("id"),
                "name": proj_name,
                "description": project.get("description"),
                "state": project.get("state"),
                "visibility": project.get("visibility"),
                "url": f"{base_url}/{collection}/{proj_name}" if proj_name else project.get("url")
            })

        result = {
            "success": True,
            "count": len(projects),
            "projects": projects
        }
        logger.info("[ProjectsService] Projects fetched successfully: %d projects", len(projects))
        return result
    except Exception as e:
        logger.error("[ProjectsService] Failed to fetch projects: %s", e, exc_info=True)
        return {
            "success": False,
            "message": f"Failed to fetch projects: {str(e)}",
            "projects": []
        }
