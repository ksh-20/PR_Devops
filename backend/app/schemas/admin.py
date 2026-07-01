"""
admin.py — Pydantic schemas for the Admin module.

Covers Projects, Repositories, Users, Project Members, and the Sync Summary.
Column names are flexible placeholders — adjust to match your DDL once provided.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    state: Optional[str] = None
    visibility: Optional[str] = None
    url: Optional[str] = None
    azure_id: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None
    visibility: Optional[str] = None
    url: Optional[str] = None


class ProjectOut(ProjectBase):
    id: int
    azure_id: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

class RepositoryBase(BaseModel):
    name: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    default_branch: Optional[str] = None
    remote_url: Optional[str] = None
    size: Optional[int] = None
    azure_id: Optional[str] = None


class RepositoryCreate(RepositoryBase):
    pass


class RepositoryUpdate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    default_branch: Optional[str] = None
    remote_url: Optional[str] = None
    size: Optional[int] = None


class RepositoryOut(RepositoryBase):
    id: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    display_name: str
    unique_name: Optional[str] = None
    email: Optional[str] = None
    azure_id: Optional[str] = None
    is_active: Optional[bool] = True


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    unique_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(UserBase):
    id: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Project Members
# ---------------------------------------------------------------------------

class ProjectMemberBase(BaseModel):
    project_id: int
    user_id: Optional[int] = None
    azure_user_id: Optional[str] = None
    display_name: Optional[str] = None
    unique_name: Optional[str] = None
    role: Optional[str] = None


class ProjectMemberCreate(ProjectMemberBase):
    pass


class ProjectMemberUpdate(BaseModel):
    project_id: Optional[int] = None
    user_id: Optional[int] = None
    azure_user_id: Optional[str] = None
    display_name: Optional[str] = None
    unique_name: Optional[str] = None
    role: Optional[str] = None


class ProjectMemberOut(ProjectMemberBase):
    id: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Sync Summary
# ---------------------------------------------------------------------------

class SyncSummary(BaseModel):
    projects_upserted: int = 0
    repositories_upserted: int = 0
    users_upserted: int = 0
    members_upserted: int = 0
    errors: list[str] = []
    success: bool = True
    message: str = "Synchronization completed."
