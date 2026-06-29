from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
from requests.auth import HTTPBasicAuth
import urllib3

from core.config import base_url, collection, pat
from services.Azure_Devops.projects_service import fetch_projects
from exceptions.handler import handle_error_response
from core.auth import auth
from core.constants import API_VERSION, RESOURCE_PIPELINE

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def fetch_pipelines(project_name):
    logger.info("[PipelinesService] Fetching pipelines for project: %s", project_name)
    if not base_url or not collection or not pat:
        logger.warning("[PipelinesService] Azure DevOps not configured — skipping pipelines fetch for '%s'", project_name)
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "pipelines": []
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/pipelines?api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"{RESOURCE_PIPELINE} in project '{project_name}'")
        
        pipelines = []
        data = response.json()
        for pipeline in data.get("value", []):
            if not isinstance(pipeline, dict):
                continue
            pipeline_id = pipeline.get("id")
            pipelines.append({
                "id"     : pipeline_id,
                "name"   : pipeline.get("name"),
                "folder" : pipeline.get("folder"),
                "url"    : f"{base_url}/{collection}/{project_name}/_build?definitionId={pipeline_id}" if pipeline_id else pipeline.get("url")
            })

        result = {
            "success" : True,
            "count" : len(pipelines),
            "pipelines" : pipelines
        }
        logger.info("[PipelinesService] Pipelines fetched: %d pipelines for project '%s'", len(pipelines), project_name)
        return result
    except Exception as e:
        logger.error("[PipelinesService] Failed to fetch pipelines for '%s': %s", project_name, e, exc_info=True)
        return {
            "success": False,
            "message": f"Failed to fetch pipelines: {str(e)}",
            "pipelines": []
        }


def fetch_active_pipelines_count():
    projects_data = fetch_projects()
    if not isinstance(projects_data, dict) or not projects_data.get("success") or "projects" not in projects_data:
        return {"success": False, "count": 0}
    
    total_count = 0
    for project in projects_data["projects"]:
        if not isinstance(project, dict):
            continue
        proj_name = project.get("name")
        if not proj_name:
            continue
        try:
            pipelines_data = fetch_pipelines(proj_name)
            if isinstance(pipelines_data, dict) and pipelines_data.get("success") and "count" in pipelines_data:
                total_count += pipelines_data["count"]
        except Exception:
            pass
            
    return {
        "success": True,
        "count": total_count
    }