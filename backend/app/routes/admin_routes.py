"""
admin_routes.py — FastAPI router for the Admin module.

Endpoints:
  GET    /api/admin/project-members         — list (filter by project_id + paginate)
  POST   /api/admin/project-members         — create member
  PUT    /api/admin/project-members/{id}    — update member
  DELETE /api/admin/project-members/{id}    — delete member

All mutating endpoints require a valid admin JWT (Authorization: Bearer <token>).
GET endpoints are open so the frontend can show data after login.
"""

from __future__ import annotations
from fastapi import APIRouter, Header, Query, HTTPException
from typing import Optional

from models.handle_logging import get_logging_conf
from core.auth import get_current_user
from services.admin import admin_db_service
from schemas.admin import ProjectMemberCreate, ProjectMemberUpdate

logging = get_logging_conf()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _require_admin(authorization: Optional[str]) -> dict:
    """Verify the Bearer token and ensure it carries role=admin."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    payload = get_current_user(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


# ===========================================================================
# Project Members
# ===========================================================================

@router.get("/project-members")
async def list_project_members(
    project_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    authorization: Optional[str] = Header(default=None),
):
    _require_admin(authorization)
    return admin_db_service.list_project_members(project_id=project_id, page=page, page_size=page_size)


@router.post("/project-members")
async def create_project_member(
    body: ProjectMemberCreate, authorization: Optional[str] = Header(default=None)
):
    _require_admin(authorization)
    return admin_db_service.create_project_member(body.model_dump())


@router.put("/project-members/{member_id}")
async def update_project_member(
    member_id: int, body: ProjectMemberUpdate, authorization: Optional[str] = Header(default=None)
):
    _require_admin(authorization)
    return admin_db_service.update_project_member(member_id, body.model_dump(exclude_none=True))


@router.delete("/project-members/{member_id}")
async def delete_project_member(member_id: int, authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    return admin_db_service.delete_project_member(member_id)
