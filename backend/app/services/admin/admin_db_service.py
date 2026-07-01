"""
admin_db_service.py — SQL CRUD operations for the Admin Project Members.

All queries use parameterised statements to prevent SQL injection.
"""

from __future__ import annotations
from typing import Optional
from models.handle_logging import get_logging_conf
from core.database import get_connection

logging = get_logging_conf()
logger = logging.getLogger(__name__)


# ===========================================================================
# Helpers
# ===========================================================================

def _rows_to_dicts(cursor) -> list[dict]:
    """Convert cursor results to a list of dicts using column names."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _paginate(items: list, page: int, page_size: int) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total_count": total,
        "count": len(items[start:end]),
        "items": items[start:end],
    }


# ===========================================================================
# Project Members
# ===========================================================================

def list_project_members(project_id: Optional[int] = None, page: int = 1, page_size: int = 20) -> dict:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM admin_project_members"
        params: list = []
        if project_id:
            query += " WHERE project_id = ?"
            params.append(project_id)
        query += " ORDER BY id"
        cursor.execute(query, params)
        rows = _rows_to_dicts(cursor)
        return {"success": True, **_paginate(rows, page, page_size)}
    except Exception as exc:
        logger.error("[AdminDB] list_project_members failed: %s", exc)
        return {"success": False, "message": str(exc), "items": [], "total_count": 0, "count": 0}


def create_project_member(data: dict) -> dict:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO admin_project_members
                (project_id, user_id, azure_user_id, display_name, unique_name, role)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                data.get("project_id"), data.get("user_id"), data.get("azure_user_id"),
                data.get("display_name"), data.get("unique_name"), data.get("role"),
            ],
        )
        conn.commit()
        return {"success": True, "message": "Member added successfully."}
    except Exception as exc:
        logger.error("[AdminDB] create_project_member failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(exc)}


def update_project_member(member_id: int, data: dict) -> dict:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        fields = {k: v for k, v in data.items() if v is not None and k != "id"}
        if not fields:
            return {"success": False, "message": "No fields to update."}
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [member_id]
        cursor.execute(f"UPDATE admin_project_members SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return {"success": True, "message": "Member updated successfully."}
    except Exception as exc:
        logger.error("[AdminDB] update_project_member failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(exc)}


def delete_project_member(member_id: int) -> dict:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_project_members WHERE id = ?", [member_id])
        conn.commit()
        return {"success": True, "message": "Member removed successfully."}
    except Exception as exc:
        logger.error("[AdminDB] delete_project_member failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(exc)}
