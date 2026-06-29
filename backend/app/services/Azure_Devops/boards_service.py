from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
from requests.auth import HTTPBasicAuth
import urllib3
from datetime import datetime, timezone, timedelta
import re

from core.config import base_url, collection, pat
from services.Azure_Devops.projects_service import fetch_projects
from exceptions.handler import handle_error_response
from core.auth import auth
from core.constants import API_VERSION, RESOURCE_WORKITEM

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def fetch_work_item_ids(project_name):
    if not base_url or not collection or not pat:
        return []
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/wit/wiql?api-version={API_VERSION}"

        query = {
            "query": f"""
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = '{project_name}'
              AND [System.WorkItemType] <> ''
            ORDER BY [System.ChangedDate] DESC
            """
        }

        response = requests.post(url=url, json=query, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        return [item["id"] for item in data.get("workItems", []) if isinstance(item, dict) and "id" in item]
    except Exception:
        return []


def fetch_sprints(project_name):
    if not base_url or not collection or not pat:
        return []
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/work/teamsettings/iterations?api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        return [
            it.get("name", "")
            for it in data.get("value", [])
            if isinstance(it, dict) and it.get("name")
        ]
    except Exception:
        return []


def get_sprint_sort_key(sprint_name, project_name):
    s_name_lower = sprint_name.lower() if sprint_name else ""
    p_name_lower = project_name.lower() if project_name else ""
    
    if "priority" in s_name_lower:
        return (0, 0, sprint_name)
        
    digits = re.findall(r'\d+', sprint_name)
    if digits:
        num = int(digits[0])
        return (1, -num, sprint_name)
        
    if p_name_lower in s_name_lower:
        return (2, 0, sprint_name)
        
    return (3, 0, sprint_name)


def fetch_work_items(project_name):
    logger.info("[BoardsService] Fetching work items for project: %s", project_name)
    if not base_url or not collection or not pat:
        logger.warning("[BoardsService] Azure DevOps not configured — skipping work items fetch for '%s'", project_name)
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "count": 0,
            "value": [],
            "sprints": []
        }
    try:
        ids = fetch_work_item_ids(project_name)

        if not ids:
            return {
                "success": False,
                "message": "No work items found",
                "count": 0,
                "value": [],
                "sprints": []
            }

        ids_string = ",".join(map(str, ids[:200]))

        fields_param = (
            "System.Id,System.WorkItemType,System.Title,System.State,"
            "System.BoardColumn,System.AssignedTo,"
            "Microsoft.VSTS.Common.Priority,"
            "Microsoft.VSTS.Common.Severity,"
            "Microsoft.VSTS.Common.StateChangeDate,"
            "Microsoft.VSTS.Scheduling.StartDate,"
            "Microsoft.VSTS.Scheduling.TargetDate,"
            "Microsoft.VSTS.Scheduling.OriginalEstimate,"
            "Microsoft.VSTS.Scheduling.CompletedWork,"
            "Microsoft.VSTS.Scheduling.RemainingWork,"
            "System.IterationPath"
        )

        url = f"{base_url}/{collection}/_apis/wit/workitems?ids={ids_string}&fields={fields_param}&api-version={API_VERSION}"

        auth_basic = HTTPBasicAuth("", pat)

        response = requests.get(url, auth=auth_basic, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"{RESOURCE_WORKITEM} in project '{project_name}'")

        raw_items = []
        sprint_set = set()
        data = response.json()

        for item in data.get("value", []):
            if not isinstance(item, dict):
                continue
            fields = item.get("fields", {})
            if not isinstance(fields, dict):
                fields = {}

            # Extract sprint from iteration path for grouping
            iteration_path = fields.get("System.IterationPath", "")
            sprint = iteration_path.split("\\")[-1] if iteration_path else "No Sprint"
            if sprint:
                sprint_set.add(sprint)

            assigned_to_raw = fields.get("System.AssignedTo")
            assigned_to = (
                {
                    "displayName": assigned_to_raw.get("displayName"),
                    "uniqueName": assigned_to_raw.get("uniqueName")
                }
                if isinstance(assigned_to_raw, dict)
                else None
            )

            out_fields = {
                "System.Id": fields.get("System.Id"),
                "System.WorkItemType": fields.get("System.WorkItemType"),
                "System.Title": fields.get("System.Title"),
                "System.State": fields.get("System.State"),
                "System.BoardColumn": fields.get("System.BoardColumn"),
                "System.AssignedTo": assigned_to,
                "Microsoft.VSTS.Common.Priority": fields.get("Microsoft.VSTS.Common.Priority"),
                "Microsoft.VSTS.Common.StateChangeDate": fields.get("Microsoft.VSTS.Common.StateChangeDate"),
                "_sprint": sprint,
            }

            for opt_key in (
                "Microsoft.VSTS.Common.Severity",
                "Microsoft.VSTS.Scheduling.StartDate",
                "Microsoft.VSTS.Scheduling.TargetDate",
                "Microsoft.VSTS.Scheduling.OriginalEstimate",
                "Microsoft.VSTS.Scheduling.CompletedWork",
                "Microsoft.VSTS.Scheduling.RemainingWork",
            ):
                val = fields.get(opt_key)
                if val is not None:
                    out_fields[opt_key] = val

            raw_items.append({
                "id":  item.get("id"),
                "rev": item.get("rev"),
                "fields": out_fields,
            })

        # Sort raw items using the custom sprint sort key to group them in the correct order for the frontend
        raw_items.sort(key=lambda x: get_sprint_sort_key(x["fields"]["_sprint"], project_name))

        sprints = sorted(list(sprint_set), key=lambda s: get_sprint_sort_key(s, project_name))
        logger.info("[BoardsService] Work items fetched: %d items, %d sprints for project '%s'", len(raw_items), len(sprints), project_name)

        return {
            "success": True,
            "count":   len(raw_items),
            "value":   raw_items,
            "sprints": sprints,
        }
    except Exception as e:
        logger.error("[BoardsService] Failed to fetch work items for '%s': %s", project_name, e, exc_info=True)
        return {
            "success": False,
            "message": f"Failed to fetch work items: {str(e)}",
            "count": 0,
            "value": [],
            "sprints": []
        }


def fetch_recent_state_changes(project_name: str, days: int = 30, limit: int = 25):
    logger.info("[BoardsService] Fetching recent state changes for project '%s' (days=%d, limit=%d)", project_name, days, limit)
    if not base_url or not collection or not pat:
        logger.warning("[BoardsService] Azure DevOps not configured — skipping recent state changes for '%s'", project_name)
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "count": 0,
            "changes": []
        }

    try:
        since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        wiql_url = f"{base_url}/{collection}/{project_name}/_apis/wit/wiql?api-version={API_VERSION}"

        query = {
            "query": f"""
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = '{project_name}'
              AND [Microsoft.VSTS.Common.StateChangeDate] >= '{since_date}'
            ORDER BY [Microsoft.VSTS.Common.StateChangeDate] DESC
            """
        }
        wiql_resp = requests.post(url=wiql_url, json=query, auth=auth, verify=False, timeout=10)
        if wiql_resp.status_code != 200:
            return {
                "success": False,
                "message": f"WIQL query failed ({wiql_resp.status_code}): {wiql_resp.text[:200]}",
                "count": 0,
                "changes": []
            }

        ids = [
            item["id"]
            for item in wiql_resp.json().get("workItems", [])
            if isinstance(item, dict) and "id" in item
        ][:limit]

        if not ids:
            return {"success": True, "count": 0, "changes": []}

        ids_str = ",".join(map(str, ids))
        fields_param = (
            "System.Id,System.Title,System.WorkItemType,System.State,"
            "System.AssignedTo,Microsoft.VSTS.Common.StateChangeDate"
        )

        bulk_url = f"{base_url}/{collection}/_apis/wit/workitems?ids={ids_str}&fields={fields_param}&api-version={API_VERSION}"

        bulk_resp = requests.get(bulk_url, auth=HTTPBasicAuth("", pat), verify=False, timeout=10)
        if bulk_resp.status_code != 200:
            return {
                "success": False,
                "message": f"Bulk field fetch failed ({bulk_resp.status_code})",
                "count": 0,
                "changes": []
            }

        items_by_id = {}
        for item in bulk_resp.json().get("value", []):
            if not isinstance(item, dict):
                continue
            fields = item.get("fields", {})
            assigned_raw = fields.get("System.AssignedTo")
            items_by_id[item["id"]] = {
                "id": item["id"],
                "title": fields.get("System.Title", ""),
                "type": fields.get("System.WorkItemType", ""),
                "new_state": fields.get("System.State", ""),
                "prev_state": None,
                "changed_at": fields.get("Microsoft.VSTS.Common.StateChangeDate"),
                "assigned_to": (
                    assigned_raw.get("displayName")
                    if isinstance(assigned_raw, dict)
                    else None
                ),
            }

        for wid in ids:
            try:
                upd_url = f"{base_url}/{collection}/_apis/wit/workitems/{wid}/updates?api-version={API_VERSION}"

                upd_resp = requests.get(upd_url, auth=HTTPBasicAuth("", pat), verify=False, timeout=8)
                if upd_resp.status_code != 200:
                    continue

                updates = upd_resp.json().get("value", [])
                for upd in reversed(updates):
                    fields_changed = upd.get("fields", {})
                    state_change = fields_changed.get("System.State")
                    if state_change and "oldValue" in state_change:
                        items_by_id[wid]["prev_state"] = state_change["oldValue"]
                        break
            except Exception:
                pass

        changes = sorted(
            items_by_id.values(),
            key=lambda x: x["changed_at"] or "",
            reverse=True,
        )

        logger.info("[BoardsService] Recent state changes fetched: %d items for project '%s'", len(changes), project_name)
        return {"success": True, "count": len(changes), "changes": changes}

    except Exception as exc:
        logger.error("[BoardsService] Failed to fetch recent state changes for '%s': %s", project_name, exc, exc_info=True)
        return {
            "success": False,
            "message": f"Failed to fetch recent state changes: {str(exc)}",
            "count": 0,
            "changes": []
        }