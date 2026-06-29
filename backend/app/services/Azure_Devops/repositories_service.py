from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import requests
from requests.auth import HTTPBasicAuth
import urllib3
from urllib.parse import quote
from fastapi.responses import JSONResponse
from datetime import datetime

from core.config import base_url, collection, pat
from services.Azure_Devops.projects_service import fetch_projects
from exceptions.handler import handle_error_response
from core.auth import auth
from core.constants import API_VERSION, RESOURCE_REPOSITORY

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def fetch_repositories(project_name):
    logger.info("[ReposService] Fetching repositories for project: %s", project_name)
    if not base_url or not collection or not pat:
        logger.warning("[ReposService] Azure DevOps not configured — skipping repos fetch for '%s'", project_name)
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "repositories": []
        }

    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories?api-version={API_VERSION}"
        response = requests.get(url=url,auth=auth,verify=False,timeout=10)

        if response.status_code != 200:
            return handle_error_response(response,RESOURCE_REPOSITORY)

        from concurrent.futures import ThreadPoolExecutor

        def process_repo(repo):
            if not isinstance(repo, dict):
                return None

            repo_name = repo.get("name")
            default_branch = repo.get("defaultBranch")

            owner = None
            created_date = None

            if default_branch:
                try:
                    branch_name = default_branch.replace("refs/heads/","")
                    commits_url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/commits?searchCriteria.itemVersion.version={branch_name}&api-version={API_VERSION}"
                    commits_response = requests.get(url=commits_url,auth=auth,verify=False,timeout=10)

                    if commits_response.status_code == 200:
                        commits = commits_response.json().get("value", [])

                        if commits:
                            oldest_commit = commits[-1]
                            owner = oldest_commit.get("author", {}).get("name")
                            raw_date = oldest_commit.get("author", {}).get("date")
                            if raw_date:
                                created_date = _fmt_date(raw_date)
                except Exception as e:
                    logger.warning("[ReposService] Failed to process default branch commits for repo %s: %s", repo_name, e)

            proj_info = repo.get("project")
            proj_name = (
                proj_info.get("name")
                if isinstance(proj_info, dict)
                else "Unknown"
            )

            return {
                "id": repo.get("id"),
                "name": repo_name,
                "project": proj_name,
                "owner": owner,
                "createdDate": created_date,
                "defaultBranch": (
                    default_branch.replace("refs/heads/","")
                    if default_branch
                    else None
                ),
                "remoteUrl": repo.get("remoteUrl")
            }

        repo_list = response.json().get("value", [])
        with ThreadPoolExecutor(max_workers=min(len(repo_list) or 1, 15)) as executor:
            results = executor.map(process_repo, repo_list)

        repos = [r for r in results if r is not None]

        result = {
            "success": True,
            "count": len(repos),
            "repositories": repos
        }
        logger.info("[ReposService] Repositories fetched: %d repos for project '%s'", len(repos), project_name)
        return result

    except Exception as e:
        logger.error("[ReposService] Failed to fetch repositories for '%s': %s", project_name, e, exc_info=True)
        return {
            "success": False,
            "message": f"Failed to fetch repositories: {str(e)}",
            "repositories": []
        }


def fetch_all_repositories():
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "repositories": []
        }
    try:
        projects = fetch_projects()

        if isinstance(projects, JSONResponse):
            return projects

        all_repos = []

        for project in projects.get("projects", []):
            if not isinstance(project, dict):
                continue
            project_name = project.get("name")
            if not project_name:
                continue
            repos = fetch_repositories(project_name)

            if isinstance(repos, JSONResponse) or not isinstance(repos, dict) or not repos.get("success"):
                continue

            all_repos.extend(repos.get("repositories", []))

        return {
            "success": True,
            "count": len(all_repos),
            "repositories": all_repos
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch all repositories: {str(e)}",
            "repositories": []
        }


def fetch_files(project_name, repo_name):
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json."
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/items?scopePath=/&recursionLevel=Full&api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"Repository '{repo_name}'")
        
        return response.json()
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch files: {str(e)}"
        }


def fetch_commits(project_name, repo_name):
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "commits": []
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/commits?api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"Repository '{repo_name}'")
        
        commits = []
        data = response.json()
        for commit in data.get("value", []):
            if not isinstance(commit, dict):
                continue
            author_info = commit.get("author")
            author_name = author_info.get("name", "Unknown") if isinstance(author_info, dict) else "Unknown"
            author_email = author_info.get("email", "Unknown") if isinstance(author_info, dict) else "Unknown"
            author_date = author_info.get("date") if isinstance(author_info, dict) else None

            commits.append({
                "commitId": commit.get("commitId"),
                "author": author_name,
                "email": author_email,
                "date": author_date,
                "comment": commit.get("comment")
            })

        return {
            "success" : True,
            "count" : len(commits),
            "commits" : commits
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch commits: {str(e)}",
            "commits": []
        }


def fetch_pushes(project_name, repo_name):
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "pushes": []
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/pushes?api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"Repository '{repo_name}'")
        
        pushes = []
        data = response.json()
        for push in data.get("value", []):
            if not isinstance(push, dict):
                continue
            pushed_by_info = push.get("pushedBy")
            pushed_by_name = pushed_by_info.get("displayName", "Unknown") if isinstance(pushed_by_info, dict) else "Unknown"

            pushes.append({
                "pushId": push.get("pushId"),
                "date": push.get("date"),
                "pushedBy": pushed_by_name
            })

        return {
            "success" : True,
            "count" : len(pushes),
            "pushes" : pushes
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch pushes: {str(e)}",
            "pushes": []
        }


def _fmt_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.split("T")[0])
        return dt.strftime("%-d %b %Y")  # Linux/Mac
    except Exception:
        try:
            dt = datetime.strptime(iso_str.split("T")[0], "%Y-%m-%d")
            return f"{dt.day} {dt.strftime('%b')} {dt.year}"
        except Exception:
            return iso_str.split("T")[0]


def fetch_branches(project_name, repo_name):
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "branches": []
        }

    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/refs?filter=heads/&api-version={API_VERSION}"

        response = requests.get(url=url,auth=auth,verify=False,timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"Repository '{repo_name}'")

        from concurrent.futures import ThreadPoolExecutor

        def process_branch(branch):
            if not isinstance(branch, dict):
                return None

            full_branch_name = branch.get("name", "")
            branch_name = full_branch_name.replace("refs/heads/", "")
            encoded_branch = quote(branch_name)

            owner = None
            created_date = None
            last_modified_by = None
            last_modified_date = None

            # Fetch latest commit info
            try:
                latest_commit_url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/commits?searchCriteria.itemVersion.version={encoded_branch}&$top=1&api-version={API_VERSION}"
                latest_response = requests.get(url=latest_commit_url,auth=auth,verify=False,timeout=10)

                if latest_response.status_code == 200:
                    commits = latest_response.json().get("value",[])
                    if commits:
                        latest_commit = commits[-1]
                        last_modified_by = latest_commit.get("author", {}).get("name")
                        raw_date = latest_commit.get("author", {}).get("date")
                        if raw_date:
                            last_modified_date = _fmt_date(raw_date)
            except Exception as e:
                logger.warning("[ReposService] Failed to fetch branch %s latest commit: %s", branch_name, e)

            # Fetch first push info
            try:
                pushes_url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/pushes?searchCriteria.refName=refs/heads/{encoded_branch}&searchCriteria.order=asc&$top=1&api-version={API_VERSION}"
                pushes_response = requests.get(url=pushes_url,auth=auth,verify=False,timeout=10)

                if pushes_response.status_code == 200:
                    pushes = pushes_response.json().get("value",[])
                    if pushes:
                        first_push = pushes[0]
                        owner = first_push.get("pushedBy", {}).get("displayName")
                        raw_date = first_push.get("date")
                        if raw_date:
                            created_date = _fmt_date(raw_date)
            except Exception as e:
                logger.warning("[ReposService] Failed to fetch branch %s pushes: %s", branch_name, e)

            return {
                "name": branch_name,
                "owner": last_modified_by,
                "createdDate": last_modified_date,
                "lastModifiedBy": owner,
                "lastModifiedDate": created_date
            }

        branch_list = response.json().get("value", [])
        with ThreadPoolExecutor(max_workers=min(len(branch_list) or 1, 15)) as executor:
            results = executor.map(process_branch, branch_list)

        branches = [r for r in results if r is not None]

        return {
            "success": True,
            "count": len(branches),
            "branches": branches
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch branches: {str(e)}",
            "branches": []
        }

def fetch_tags(project_name, repo_name):
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "tags": []
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/refs?filter=tags/&api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"Repository '{repo_name}'")

        tags = []
        data = response.json()
        for tag in data.get("value", []):
            if not isinstance(tag, dict):
                continue
            tags.append({
                "name": tag.get("name"),
                "objectId": tag.get("objectId")
            })

        return {
            "success": True,
            "count": len(tags),
            "tags": tags
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch tags: {str(e)}",
            "tags": []
        }


def fetch_pull_requests(project_name, repo_name):
    if not base_url or not collection or not pat:
        return {
            "success": False,
            "message": "Azure DevOps is not configured. Please check config.json.",
            "pullRequests": []
        }
    try:
        url = f"{base_url}/{collection}/{project_name}/_apis/git/repositories/{repo_name}/pullrequests?searchCriteria.status=all&api-version={API_VERSION}"
        response = requests.get(url=url, auth=auth, verify=False, timeout=10)

        if response.status_code != 200:
            return handle_error_response(response, f"Repository '{repo_name}'")

        prs = []
        data = response.json()
        for pr in data.get("value", []):
            if not isinstance(pr, dict):
                continue
            created_by_info = pr.get("createdBy")
            created_by_name = created_by_info.get("displayName", "Unknown") if isinstance(created_by_info, dict) else "Unknown"

            prs.append({
                "pullRequestId": pr.get("pullRequestId"),
                "title": pr.get("title"),
                "status": pr.get("status"),
                "description" : pr.get("description"),
                "createdBy": created_by_name,
                "creationDate": pr.get("creationDate"),
                "closedDate" : pr.get("closedDate"),
                "sourceBranch": pr.get("sourceRefName"),
                "targetBranch": pr.get("targetRefName"),
                "mergeStatus" : pr.get("mergeStatus")
            })

        return {
            "success": True,
            "count": len(prs),
            "pullRequests": prs
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch pull requests: {str(e)}",
            "pullRequests": []
        }