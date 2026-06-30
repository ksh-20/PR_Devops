import os
import threading
from datetime import datetime, timezone
from typing import Optional
from requests.auth import HTTPBasicAuth
import requests
import urllib3
import difflib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from models.handle_logging import get_logging_conf
logging = get_logging_conf()
logger = logging.getLogger(__name__)

from core.config import AZURE_BASE_URL, AZURE_COLLECTION, AZURE_PAT, AZURE_PROJECT

from services.reviewer.repos_service import fetch_repos
from services.reviewer.LLM_review_service import review_pr
from services.reviewer.secrets_filter_service import sanitize_files


daemon_status: dict = {
    "running": False,
    "last_poll_at": None,
    "total_reviews_posted": 0,
    "errors": [],
    "review_log": [],
}


_review_cache: dict[str, str] = {}


_auth = HTTPBasicAuth("", AZURE_PAT)


def _get_projects() -> list[str]:
    try:
        url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/_apis/projects?api-version=7.1"
        resp = requests.get(url, auth=_auth, verify=False, timeout=20)
        if resp.status_code == 200:
            names = [p["name"] for p in resp.json().get("value", []) if p.get("name")]
            return names if names else [AZURE_PROJECT]
    except Exception as exc:
        logger.warning("[AutoReviewDaemon] Failed to list projects: %s", exc)
    return [AZURE_PROJECT]


def _get_repos_for_project(project: str) -> list[dict]:
    try:
        result = fetch_repos(project=project)
        if isinstance(result, dict):
            data = result.get("data", {})
            if isinstance(data, dict):
                return data.get("value", [])
    except Exception as exc:
        logger.warning("[AutoReviewDaemon] Failed to list repos for %s: %s", project, exc)
    return []


def _get_active_prs(project: str, repo_id: str) -> list[dict]:
    try:
        url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/pullrequests?searchCriteria.status=active&api-version=7.1"
        resp = requests.get(url, auth=_auth, verify=False, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("value", [])
    except Exception as exc:
        logger.warning("[AutoReviewDaemon] Failed to list PRs for repo=%s project=%s: %s",repo_id, project, exc)
    return []


def _fetch_pr_details(project: str, repo_id: str, pr_id: int) -> dict:
    url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}?api-version=7.1"
    resp = requests.get(url, auth=_auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _fetch_iterations(project: str, repo_id: str, pr_id: int) -> list:
    url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/iterations?api-version=7.1"
    resp = requests.get(url, auth=_auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json().get("value", [])


def _fetch_iteration_changes(project: str, repo_id: str, pr_id: int, iteration_id: int) -> list:
    url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/iterations/{iteration_id}/changes?api-version=7.1"
    resp = requests.get(url, auth=_auth, verify=False, timeout=20)
    resp.raise_for_status()
    return resp.json().get("changeEntries", [])


def _fetch_file_content(project: str, repo_id: str, path: str, commit_id: str) -> Optional[str]:
    url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/items"
    params = {
        "path": path,
        "versionDescriptor.version": commit_id,
        "versionDescriptor.versionType": "commit",
        "includeContent": "true",
        "api-version": "7.1",
    }
    try:
        resp = requests.get(url, params=params, auth=_auth, verify=False, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _generate_diff(old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile="old", tofile="new", lineterm=""
    )
    return "\n".join(diff)


def _post_review_comment(project: str, repo_id: str, pr_id: int, review_text: str) -> dict:
    url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads?api-version=7.1"

    formatted = (
        "```markdown\n"
        "# AI Pull Request Review\n"
        "---\n"
        f"{review_text}\n"
        "---\n"
        "Generated automatically by the PR Auto-Review Daemon.\n"
        "```"
    )
    payload = {
        "comments": [{"parentCommentId": 0, "content": formatted, "commentType": 1}],
        "status": 1,
    }
    resp = requests.post(url, json=payload, auth=_auth, verify=False, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _review_pr_full(project: str, repo_id: str, pr_id: int) -> dict:
    try:
        details = _fetch_pr_details(project, repo_id, pr_id)
        source_commit = (details.get("lastMergeSourceCommit") or {}).get("commitId")
        target_commit = (details.get("lastMergeTargetCommit") or {}).get("commitId")

        if not source_commit or not target_commit:
            iterations = _fetch_iterations(project, repo_id, pr_id)
            if not iterations:
                return {"success": False, "review": None, "error": "No iterations found"}
            latest = max(iterations, key=lambda x: x["id"])
            iteration_id = latest["id"]
            source_commit = (latest.get("sourceRefCommit") or {}).get("commitId")
            target_commit = (latest.get("targetRefCommit") or {}).get("commitId")
        else:
            iterations = _fetch_iterations(project, repo_id, pr_id)
            iteration_id = max(iterations, key=lambda x: x["id"])["id"] if iterations else 1

        if not source_commit or not target_commit:
            return {"success": False, "review": None, "error": "Cannot resolve commit SHAs"}

        changes = _fetch_iteration_changes(project, repo_id, pr_id, iteration_id)
        if not changes:
            return {"success": False, "review": None, "error": "No changed files in PR"}

        file_diffs = []
        for change in changes:
            item = change.get("item", {})
            path = item.get("path")
            if not path:
                continue
            old_content = _fetch_file_content(project, repo_id, path, target_commit) or ""
            new_content = _fetch_file_content(project, repo_id, path, source_commit) or ""
            diff = _generate_diff(old_content, new_content)
            file_diffs.append({
                "path": path,
                "change_type": change.get("changeType"),
                "diff": diff,
            })

        if not file_diffs:
            return {"success": False, "review": None, "error": "Could not fetch any file diffs"}

        sanitized = sanitize_files(file_diffs)
        result = review_pr(sanitized)

        return result

    except Exception as exc:
        return {"success": False, "review": None, "error": str(exc)}



def run_poll_tick() -> None:
    global daemon_status

    projects = _get_projects()
    logger.info("[AutoReviewDaemon] Polling %d project(s): %s", len(projects), projects)

    newly_reviewed = []
    errors = []

    for project in projects:
        repos = _get_repos_for_project(project)
        logger.info("[AutoReviewDaemon] Project='%s' has %d repo(s)", project, len(repos))

        for repo in repos:
            repo_id = repo.get("id")
            repo_name = repo.get("name", repo_id)
            if not repo_id:
                continue

            prs = _get_active_prs(project, repo_id)
            for pr in prs:
                pr_id = pr.get("pullRequestId")
                if not pr_id:
                    continue

                pr_title = pr.get("title", f"PR #{pr_id}")
                logger.info(
                    "[AutoReviewDaemon] Reviewing PR → project='%s' repo='%s' pr=%d ('%s')",
                    project, repo_name, pr_id, pr_title,
                )

                review_result = _review_pr_full(project, repo_id, pr_id)
                timestamp = datetime.now(timezone.utc).isoformat()

                if review_result.get("success"):
                    review_text = review_result.get("review", "")
                    try:
                        _post_review_comment(project, repo_id, pr_id, review_text)
                        logger.info("[AutoReviewDaemon] Review posted → project='%s' repo='%s' pr=%d",project, repo_name, pr_id)
                        cache_key = f"{project}::{repo_id}::{pr_id}"
                        _review_cache[cache_key] = review_text
                        newly_reviewed.append({
                            "project": project,
                            "repo_id": repo_id,
                            "repo_name": repo_name,
                            "pr_id": pr_id,
                            "pr_title": pr_title,
                            "reviewed_at": timestamp,
                            "verdict": _extract_verdict(review_text),
                            "review_snippet": review_text[:300],
                        })
                        daemon_status["total_reviews_posted"] += 1

                    except Exception as post_exc:
                        err_msg = f"Post failed for PR #{pr_id} in {repo_name}: {post_exc}"
                        logger.error("[AutoReviewDaemon] %s", err_msg)
                        errors.append({"timestamp": timestamp, "error": err_msg})

                else:
                    err_msg = review_result.get("error") or review_result.get("message", "Unknown error")
                    logger.warning("[AutoReviewDaemon] Review failed for PR #%d in '%s': %s",pr_id, repo_name, err_msg)
                    errors.append({
                        "timestamp": timestamp,
                        "error": f"PR #{pr_id} in {repo_name} ({project}): {err_msg}",
                    })

    daemon_status["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    daemon_status["errors"] = (daemon_status["errors"] + errors)[-50:]
    daemon_status["review_log"] = (daemon_status["review_log"] + newly_reviewed)[-100:]

    logger.info("[AutoReviewDaemon] Poll tick done. %d review(s) posted this cycle.",len(newly_reviewed))


def _extract_verdict(review_text: str) -> str:
    for line in review_text.splitlines():
        if "VERDICT:" in line.upper():
            return line.strip()
    return "UNKNOWN"


def get_daemon_status() -> dict:
    return {**daemon_status}


def get_cached_review(project: str, repo_id: str, pr_id: int) -> Optional[str]:
    return _review_cache.get(f"{project}::{repo_id}::{pr_id}")


def is_pr_reviewed(project: str, repo_id: str, pr_id: int) -> bool:
    return f"{project}::{repo_id}::{pr_id}" in _review_cache


def clear_reviewed_state() -> dict:
    global _review_cache
    _review_cache = {}
    daemon_status["review_log"] = []
    daemon_status["total_reviews_posted"] = 0
    return {"success": True, "message": "In-memory review log and cache cleared."}