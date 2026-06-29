from fastapi import APIRouter

from services.Azure_Devops.pipelines_service import fetch_pipelines, fetch_active_pipelines_count

router = APIRouter(tags=["Pipelines"])

@router.get("/projects/{project_name}/pipelines")
async def get_pipelines(project_name: str, page: int = 1, page_size: int = 10, search: str | None = None):
    result = fetch_pipelines(project_name)
    if not isinstance(result, dict) or not result.get("success"):
        return result
    pipelines = result.get("pipelines", [])
    if search:
        s_lower = search.lower()
        pipelines = [
            p for p in pipelines
            if s_lower in (p.get("name") or "").lower() or s_lower in (p.get("folder") or "").lower()
        ]
    total_count = len(pipelines)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = pipelines[start:end]
    return {
        "success": True,
        "total_count": total_count,
        "count": len(sliced),
        "pipelines": sliced
    }

@router.get("/pipelines/active-count")
async def get_active_pipelines_count():
    return fetch_active_pipelines_count()