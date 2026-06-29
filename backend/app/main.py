from contextlib import asynccontextmanager

from fastapi.responses import PlainTextResponse, StreamingResponse
from models.handle_logging import get_logging_conf
logging = get_logging_conf()
import os

from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional, Dict, Any
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
from services.reviewer.auto_review_daemon import _get_projects,_get_repos_for_project,_get_active_prs

from services.reviewer.webhooks_service import fetch_webhooks
from services.reviewer.repos_service import fetch_repos
from services.reviewer.project_service import fetch_projects
from services.reviewer.PR_service import AzurePRManager
from services.reviewer.auto_review_daemon import _review_pr_full,daemon_status

from routes.boards_routes import router as boards_router
from routes.pipelines_routes import router as pipelines_router
from routes.projects_routes import router as projects_router
from routes.repositories_routes import router as repositories_router
from routes.testplans_routes import router as testplans_router
from routes.auth_routes import router as auth_router
from routes.azure_routes import router as azure_router
from routes.status_routes import router as status_router

from core.sync_worker import SyncWorker
from core.pr_watcher import PRWatcher

from routes.pr_watcher_routes import router as pr_watcher_router

logger = logging.getLogger(__name__)
_sync_worker: SyncWorker | None = None
_pr_watcher: PRWatcher | None = None


PR_WATCHER_POLLING_ENABLED: bool = (os.getenv("PR_WATCHER_POLLING_ENABLED", "false").strip().lower() == "true")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_worker, _pr_watcher
    logger.info("[Lifespan] Application startup")
    logger.info("[Lifespan] Booting Azure background synchronization worker engine...")
    _sync_worker = SyncWorker()
    _sync_worker.start()
    logger.info("[Lifespan] Background worker spawned successfully (daemon=True).")

    if PR_WATCHER_POLLING_ENABLED:
        logger.info("[Lifespan] Booting PR Auto-Review Watcher daemon (polling mode)...")
        _pr_watcher = PRWatcher(poll_interval=60)
        _pr_watcher.start()
        logger.info("[Lifespan] PR Auto-Review Watcher daemon spawned successfully.")
    else:
        logger.info(
            "[Lifespan] PR polling daemon is DISABLED — webhook-driven mode active. "
            "Set PR_WATCHER_POLLING_ENABLED=true to re-enable polling."
        )

    logger.info("[Lifespan] Azure Analytics API is ready to accept requests.")

    yield

    logger.info("[Lifespan] Application shutdown")
    logger.info("[Lifespan] Shutdown intercepted — stopping daemon sync execution loops...")
    if _sync_worker is not None:
        _sync_worker.stop()
        logger.info("[Lifespan] Stop event signalled to SyncWorker daemon.")
    if _pr_watcher is not None:
        _pr_watcher.stop()
        logger.info("[Lifespan] Stop event signalled to PRWatcher daemon.")
    logger.info("[Lifespan] Background daemons reaped safely. Goodbye.")


app = FastAPI(
    title="Azure Analytics API",
    description="FastAPI backend with decoupled background data sync cache.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router, prefix="/api")
app.include_router(repositories_router, prefix="/api")
app.include_router(pipelines_router, prefix="/api")
app.include_router(boards_router, prefix="/api")
app.include_router(testplans_router, prefix="/api")
app.include_router(auth_router)
app.include_router(azure_router, prefix="/api")
app.include_router(status_router, prefix="/api")
app.include_router(pr_watcher_router, prefix="/api")

class EventPublisher:
    def __init__(self):
        self.queues = []

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self.queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.queues:
            self.queues.remove(q)

    async def broadcast(self, event_data: dict):
        for q in list(self.queues):
            await q.put(event_data)

event_publisher = EventPublisher()

@app.get("/api/ws/prs")
async def sse_endpoint():
    import time
    start_time = time.time()
    q = event_publisher.subscribe()
    try:
        while time.time() - start_time < 20.0:
            if not q.empty():
                return q.get_nowait()
            await asyncio.sleep(0.5)
        return {"event": "timeout"}
    finally:
        event_publisher.unsubscribe(q)

manager = AzurePRManager()

class ReviewRequest(BaseModel):
    repo_id: str
    pr_id: int
    review: str
    project: Optional[str] = None

logger.info("[Main] Registered routers: projects, repositories, pipelines, boards, testplans, auth, azure, status")


@app.get("/")
async def default():
    logger.debug("[Main] Root health-check endpoint hit.")
    return "Watcher API is running ..."


@app.get('/api/watcher/ghty34jkdzxdo0o/log', response_class=PlainTextResponse)
async def log(lines: int = Query(default=100, description="Number of log lines to retrieve")):
    try:
        log=""
        if lines is not None:
            lines = min(int(lines), 100000)
        with open("logs/app.log", "r") as f:
            log = f.readlines()
            if len(log)>lines:
                log = log[len(log)-lines:]
        log = "".join(log)
        return log
    except Exception as e:
        logging.error(str(e))
        return ""
    
@app.get("/api/webhooks")
async def get_webhooks():
    return fetch_webhooks()


@app.get("/api/projects")
async def get_projects():
    return fetch_projects()


@app.get("/api/repos")
async def get_repos():
    return fetch_repos()


@app.get("/api/pr/active-all")
async def get_all_active_prs():
    def _scan_all() -> list:
        import time
        start_time = time.time()
        results = []
        projects = _get_projects()
        for project in projects:
            if time.time() - start_time > 30.0:
                break
            repos = _get_repos_for_project(project)
            for repo in repos:
                if time.time() - start_time > 30.0:
                    break
                repo_id = repo.get("id")
                repo_name = repo.get("name", repo_id)
                if not repo_id:
                    continue
                prs = _get_active_prs(project, repo_id)
                for pr in prs:
                    results.append({
                        **pr,
                        "project_name": project,
                        "repo_id": repo_id,
                        "repo_name": repo_name,
                    })
        results.sort(key=lambda p: p.get("creationDate", ""), reverse=True)
        return results

    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        results = await loop.run_in_executor(executor, _scan_all)
        executor.shutdown(wait=False)
        for pr in results:
            proj = pr.get("project_name")
            repo = pr.get("repo_id")
            pr_id = pr.get("pullRequestId") or pr.get("id")
            if proj and repo and pr_id:
                import threading
                threading.Thread(
                    target=_check_and_review_pr,
                    args=(proj, repo, pr_id),
                    daemon=True
                ).start()
        return {"success": True, "pull_requests": results}
    except Exception as exc:
        executor.shutdown(wait=False)
        logger.error("[ActivePRs] Failed: %s", exc)
        return {"success": False, "message": str(exc), "pull_requests": []}



@app.get("/api/pr")
async def get_prs(repo: Optional[str] = Query(None), project: Optional[str] = Query(None)):
    if project:
        manager.project = project
    return manager.fetch_prs(repo_target=repo)


@app.get("/api/pr_iterations")
async def get_pr_iterations(repo_id: Optional[str] = Query(None), pr_id: Optional[int] = Query(None), project: Optional[str] = Query(None)):
    if repo_id and pr_id:
        manager.repo_id = repo_id
        manager.pr_id = pr_id
    if project:
        manager.project = project
    return manager.fetch_latest_iteration()


@app.get("/api/pr_changes")
async def get_pr_changes(repo_id: Optional[str] = Query(None), pr_id: Optional[int] = Query(None),iteration_id: Optional[int] = Query(None), project: Optional[str] = Query(None)):
    if repo_id and pr_id and iteration_id:
        manager.repo_id = repo_id
        manager.pr_id = pr_id
        manager.iteration_id = iteration_id
    if project:
        manager.project = project
    return manager.get_changed_files()


@app.get("/api/pr_deltas")
async def get_pr_deltas(repo_id: Optional[str] = Query(None),pr_id: Optional[int] = Query(None),iteration_id: Optional[int] = Query(None), project: Optional[str] = Query(None)):
    if repo_id:
        manager.repo_id = repo_id
    if pr_id:
        manager.pr_id = pr_id
    if iteration_id:
        manager.iteration_id = iteration_id
    if project:
        manager.project = project

    return manager.get_file_deltas()


@app.get("/api/pr_review")
async def review_pr(repo_id: Optional[str] = Query(None),pr_id: Optional[int] = Query(None),iteration_id: Optional[int] = Query(None), project: Optional[str] = Query(None)):
    if repo_id:
        manager.repo_id = repo_id
    if pr_id:
        manager.pr_id = pr_id
    if iteration_id:
        manager.iteration_id = iteration_id
    if project:
        manager.project = project

    return manager.review_current_pr()


@app.post("/api/post_review")
async def post_review(request: ReviewRequest):
    manager.repo_id = request.repo_id
    manager.pr_id = request.pr_id
    if request.project:
        manager.project = request.project

    return manager.post_review(request.review)




def _has_ai_review(project: str, repo_id: str, pr_id: int) -> bool:
    try:
        import requests
        from services.reviewer.auto_review_daemon import AZURE_BASE_URL, AZURE_COLLECTION, _auth
        url = f"{AZURE_BASE_URL}/{AZURE_COLLECTION}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads?api-version=7.1"
        resp = requests.get(url, auth=_auth, verify=False, timeout=15)
        if resp.status_code == 200:
            threads = resp.json().get("value", [])
            for thread in threads:
                for comment in thread.get("comments", []):
                    content = comment.get("content", "")
                    if "# AI Pull Request Review" in content or "Senior Engineer Evaluation Active" in content:
                        return True
    except Exception as exc:
        logger.warning("[AutoReview] Failed checking threads for pr %d: %s", pr_id, exc)
    return False

def _check_and_review_pr(project: str, repo_id: str, pr_id: int):
    try:
        already_reviewed = _has_ai_review(project, repo_id, pr_id)
        if already_reviewed:
            logger.info("[AutoReview] PR %d already reviewed", pr_id)
            return

        logger.info("[AutoReview] PR %d not reviewed — triggering review", pr_id)
        result = _review_pr_full(project, repo_id, pr_id)
        if result.get("success"):
            review_text = result.get("review", "")
            manager.repo_id = str(repo_id)
            manager.pr_id = int(pr_id)
            manager.project = project
            post_result = manager.post_review(review_text)
            if post_result.get("success"):
                logger.info("[AutoReview] Posted review comment for PR %d", pr_id)
            else:
                logger.error("[AutoReview] post_review failed for PR %d: %s", pr_id, post_result.get("message"))
        else:
            logger.error("[AutoReview] Failed to review PR %d: %s", pr_id, result.get("error"))
    except Exception as exc:
        logger.exception("[AutoReview] Error checking/reviewing PR %d: %s", pr_id, exc)

def _webhook_review_task(project: str, repo_id: str, pr_id: int) -> None:
    log_prefix = f"[Webhook] project='{project}' repo='{repo_id}' pr={pr_id}"
    logger.info("%s — starting review", log_prefix)
    try:
        result = _review_pr_full(project, repo_id, pr_id)
        if result.get("success"):
            review_text = result.get("review", "")
            manager.repo_id = str(repo_id)
            manager.pr_id = int(pr_id)
            manager.project = project
            post_result = manager.post_review(review_text)
            if post_result.get("success"):
                daemon_status["total_reviews_posted"] += 1
                logger.info("%s — review comment posted successfully", log_prefix)
            else:
                logger.error("%s — post_review failed: %s", log_prefix, post_result.get("message"))
        else:
            err = result.get("error") or result.get("message", "unknown")
            logger.error("%s — review failed: %s", log_prefix, err)
    except Exception as exc:
        logger.exception("%s — unhandled error: %s", log_prefix, exc)


@app.post("/api/pr-webhook", status_code=202)
@app.post("/", status_code=202)
async def pr_webhook(payload: Dict[str, Any]):
    try:
        event_type: str = payload.get("eventType", "")
        resource: dict = payload.get("resource", {})

        pr_id: int = resource.get("pullRequestId")
        repository: dict = resource.get("repository", {})
        repo_id: str = repository.get("id")

        proj_block: dict = (
            repository.get("project")
            or resource.get("project")
            or {}
        )
        project: str = proj_block.get("name") or proj_block.get("id", "")

        if not pr_id or not repo_id or not project:
            logger.warning("[Webhook] Payload missing required fields — pr_id=%s repo_id=%s project=%s",pr_id, repo_id, project)
            return {
                "status": "ignored",
                "reason": "Missing pr_id, repo_id or project in payload",
            }

        logger.info("[Webhook] Received '%s' — project='%s' repo='%s' pr=%d", event_type, project, repo_id, pr_id)

        pr_data = {
            "pullRequestId": pr_id,
            "id": pr_id,
            "title": resource.get("title", f"PR #{pr_id}"),
            "status": resource.get("status", "active"),
            "sourceRefName": resource.get("sourceRefName"),
            "targetRefName": resource.get("targetRefName"),
            "creationDate": resource.get("creationDate"),
            "createdBy": resource.get("createdBy"),
            "project_name": project,
            "repo_id": repo_id,
            "repo_name": repository.get("name", repo_id)
        }
        asyncio.create_task(event_publisher.broadcast({"event": "pr_updated", "pr": pr_data}))

        import threading
        threading.Thread(
            target=_webhook_review_task,
            args=(project, repo_id, pr_id),
            daemon=True
        ).start()

        return {
            "status": "accepted",
            "event": event_type,
            "project": project,
            "repo_id": repo_id,
            "pr_id": pr_id,
        }

    except Exception as exc:
        logger.exception("[Webhook] Unexpected error parsing payload: %s", exc)
        return {"status": "error", "message": str(exc)}


if __name__ == "__main__":
    port = int(os.environ.get("SERVER_PORT", 80))
    logger.info("[Main] Starting uvicorn on 0.0.0.0:%d", port)
    uvicorn.run("main:app",host="0.0.0.0",port=port,reload=False)