from fastapi import APIRouter

from core.data_cache import cache

router = APIRouter(prefix="/projects", tags=["Projects"])

_COLD_CACHE_RESPONSE = {
    "success": False,
    "count": 0,
    "projects": [],
    "message": "Data is warming up. The background sync is in progress — please retry in a few seconds.",
}


@router.get("")
async def get_projects(page: int = 1, page_size: int = 10, search: str | None = None):
    res = cache.get("projects", _COLD_CACHE_RESPONSE)
    if not res.get("success"):
        return res
    projects = res.get("projects", [])
    if search:
        s_lower = search.lower()
        projects = [
            p for p in projects
            if isinstance(p, dict) and s_lower in (p.get("name") or "").lower()
        ]
    total_count = len(projects)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = projects[start:end]
    return {
        "success": True,
        "total_count": total_count,
        "count": len(sliced),
        "projects": sliced
    }