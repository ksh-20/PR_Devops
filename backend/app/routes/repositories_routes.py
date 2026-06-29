from fastapi import APIRouter

from core.data_cache import cache
from core.azure_throttle import _TtlCache
from services.Azure_Devops.repositories_service import (
    fetch_branches,
    fetch_commits,
    fetch_files,
    fetch_pull_requests,
    fetch_pushes,
    fetch_repositories,
    fetch_tags,
)

router = APIRouter(tags=["Repositories"])

_COLD_CACHE_RESPONSE = {
    "success": False,
    "count": 0,
    "repositories": [],
    "message": "Data is warming up. The background sync is in progress — please retry in a few seconds.",
}

# 5-minute cache for DevOps metrics
devops_cache = _TtlCache(ttl=300)


@router.get("/repos")
async def get_all_repositories():
    return cache.get("repos", _COLD_CACHE_RESPONSE)


@router.get("/projects/{project_name}/repos")
async def get_repositories(
    project_name: str,
    page: int = 1,
    page_size: int = 10,
    owner: str = "All"
):
    cached_repos = cache.get("repos")
    if isinstance(cached_repos, dict) and cached_repos.get("success"):
        proj_repos = [
            repo for repo in cached_repos.get("repositories", [])
            if isinstance(repo, dict) and repo.get("project", "").lower() == project_name.lower()
        ]
    else:
        res = fetch_repositories(project_name)
        if isinstance(res, dict) and res.get("success"):
            proj_repos = res.get("repositories", [])
        else:
            return res

    # Extract all unique owners working on the specified project BEFORE filtering by owner
    owners = sorted(list(set(
        repo.get("owner") for repo in proj_repos
        if isinstance(repo, dict) and repo.get("owner")
    )))

    # Filter by owner if specified
    if owner and owner.lower() != "all":
        proj_repos = [
            repo for repo in proj_repos
            if isinstance(repo, dict) and repo.get("owner") and repo.get("owner").lower() == owner.lower()
        ]

    total_count = len(proj_repos)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = proj_repos[start:end]

    return {
        "success": True,
        "total_count": total_count,
        "count": len(sliced),
        "repositories": sliced,
        "owners": owners
    }


@router.get("/projects/{project_name}/repos/{repo_name}/files")
async def get_files(project_name: str, repo_name: str):
    return fetch_files(project_name, repo_name)


@router.get("/projects/{project_name}/repos/{repo_name}/commits")
async def get_commits(project_name: str, repo_name: str):
    cache_key = f"commits:{project_name}:{repo_name}"
    cached = devops_cache.get(cache_key)
    if cached is not None:
        return cached
    result = fetch_commits(project_name, repo_name)
    if isinstance(result, dict) and result.get("success"):
        devops_cache.set(cache_key, result)
    return result


@router.get("/projects/{project_name}/repos/{repo_name}/pushes")
async def get_pushes(project_name: str, repo_name: str):
    cache_key = f"pushes:{project_name}:{repo_name}"
    cached = devops_cache.get(cache_key)
    if cached is not None:
        return cached
    result = fetch_pushes(project_name, repo_name)
    if isinstance(result, dict) and result.get("success"):
        devops_cache.set(cache_key, result)
    return result


@router.get("/projects/{project_name}/repos/{repo_name}/branches")
async def get_branches(project_name: str, repo_name: str):
    cache_key = f"branches:{project_name}:{repo_name}"
    cached = devops_cache.get(cache_key)
    if cached is not None:
        return cached
    result = fetch_branches(project_name, repo_name)
    if isinstance(result, dict) and result.get("success"):
        devops_cache.set(cache_key, result)
    return result


@router.get("/projects/{project_name}/repos/{repo_name}/tags")
async def get_tags(project_name: str, repo_name: str):
    return fetch_tags(project_name, repo_name)


@router.get("/projects/{project_name}/repos/{repo_name}/pullrequests")
async def get_pull_requests(project_name: str, repo_name: str):
    cache_key = f"pullrequests:{project_name}:{repo_name}"
    cached = devops_cache.get(cache_key)
    if cached is not None:
        return cached
    result = fetch_pull_requests(project_name, repo_name)
    if isinstance(result, dict) and result.get("success"):
        devops_cache.set(cache_key, result)
    return result