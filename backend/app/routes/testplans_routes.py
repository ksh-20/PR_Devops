from fastapi import APIRouter

from services.Azure_Devops.testplans_service import fetch_test_plans

router = APIRouter(tags=["Test Plans"])

@router.get("/project/{project_name}/testplans")
async def get_test_plans(project_name: str, page: int = 1, page_size: int = 10, search: str | None = None):
    return await get_paginated_test_plans(project_name, page, page_size, search)

@router.get("/projects/{project_name}/testplans")
async def get_projects_test_plans(project_name: str, page: int = 1, page_size: int = 10, search: str | None = None):
    return await get_paginated_test_plans(project_name, page, page_size, search)

async def get_paginated_test_plans(project_name: str, page: int, page_size: int, search: str | None):
    result = fetch_test_plans(project_name)
    if not isinstance(result, dict) or not result.get("success"):
        return result
    plans = result.get("test_plans", [])
    if search:
        s_lower = search.lower()
        plans = [
            tp for tp in plans
            if s_lower in (tp.get("name") or "").lower() or s_lower in (tp.get("owner") or "").lower() or s_lower in (tp.get("state") or "").lower()
        ]
    total_count = len(plans)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = plans[start:end]
    return {
        "success": True,
        "total_count": total_count,
        "count": len(sliced),
        "test_plans": sliced
    }