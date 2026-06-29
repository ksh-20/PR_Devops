from fastapi import APIRouter, Query

from services.Azure_Devops.boards_service import fetch_work_items, fetch_recent_state_changes

router = APIRouter(tags=["Boards"])

@router.get("/project/{project_name}/workitems")
async def get_work_items(project_name: str, page: int = 1, page_size: int = 10, sprint: str | None = None, type: str | None = None, state: str | None = None, assigned: str | None = None):
    return await get_paginated_work_items(project_name, page, page_size, sprint, type, state, assigned)

@router.get("/projects/{project_name}/workitems")
async def get_projects_work_items(project_name: str, page: int = 1, page_size: int = 10, sprint: str | None = None, type: str | None = None, state: str | None = None, assigned: str | None = None):
    return await get_paginated_work_items(project_name, page, page_size, sprint, type, state, assigned)

async def get_paginated_work_items(project_name: str, page: int, page_size: int, sprint: str | None = None, type: str | None = None, state: str | None = None, assigned: str | None = None):
    result = fetch_work_items(project_name)
    if not isinstance(result, dict) or not result.get("success"):
        return result
    value = result.get("value", [])
    
    # Extract unique categories before filtering
    sprints = result.get("sprints", [])
    types_set = set()
    states_set = set()
    assignees_set = set()
    for x in value:
        fields = x.get("fields", {})
        if fields.get("System.WorkItemType"):
            types_set.add(fields.get("System.WorkItemType"))
        if fields.get("System.State"):
            states_set.add(fields.get("System.State"))
        assigned_to = fields.get("System.AssignedTo")
        if isinstance(assigned_to, dict):
            assignees_set.add(assigned_to.get("displayName") or "Unassigned")
        else:
            assignees_set.add("Unassigned")
            
    types = sorted(list(types_set))
    states = sorted(list(states_set))
    assignees = sorted(list(assignees_set))

    # Apply filters
    filtered = []
    for x in value:
        fields = x.get("fields", {})
        
        # Sprint filter
        item_sprint = fields.get("_sprint") or "No Sprint"
        if sprint and item_sprint != sprint:
            continue
            
        # Type filter
        item_type = fields.get("System.WorkItemType")
        if type and item_type != type:
            continue
            
        # State filter
        item_state = fields.get("System.State")
        if state and item_state != state:
            continue
            
        # Assigned filter
        assigned_to = fields.get("System.AssignedTo")
        item_assigned = assigned_to.get("displayName") if isinstance(assigned_to, dict) else "Unassigned"
        if assigned and item_assigned != assigned:
            continue
            
        filtered.append(x)
        
    total_count = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = filtered[start:end]
    
    return {
        "success": True,
        "total_count": total_count,
        "count": len(sliced),
        "value": sliced,
        "sprints": sprints,
        "types": types,
        "states": states,
        "assignees": assignees
    }

@router.get("/boards/{project}/recent-changes")
async def get_recent_changes(
    project: str,
    days: int = Query(default=30, ge=1, le=180, description="Look-back window in days"),
    limit: int = Query(default=25, ge=1, le=100, description="Max items to return"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, description="Page size"),
):
    result = fetch_recent_state_changes(project, days=days, limit=limit)
    if not isinstance(result, dict) or not result.get("success"):
        return result
    changes = result.get("changes", [])
    total_count = len(changes)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = changes[start:end]
    return {
        "success": True,
        "total_count": total_count,
        "count": len(sliced),
        "changes": sliced
    }