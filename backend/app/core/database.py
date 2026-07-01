"""
database.py — Admin SQL database connection layer.

Uses pyodbc to connect to an on-prem SQL Server instance.
Connection string is read from config.json (DB_CONNECTION_STRING).
"""

import pyodbc
from models.handle_logging import get_logging_conf

logging = get_logging_conf()
logger = logging.getLogger(__name__)

_connection: pyodbc.Connection | None = None


def _load_connection_string() -> str:
    from core.config import db_connection_string
    return db_connection_string


def get_connection() -> pyodbc.Connection:
    """
    Return a live pyodbc connection.
    Re-establishes the connection if it has been closed or dropped.
    """
    global _connection
    try:
        if _connection is not None:
            # Quick ping to verify the connection is still alive
            _connection.cursor().execute("SELECT 1")
            return _connection
    except Exception:
        logger.warning("[DB] Existing connection is stale — reconnecting.")
        _connection = None

    conn_str = _load_connection_string()
    if not conn_str:
        raise RuntimeError(
            "[DB] DB_CONNECTION_STRING is not configured in config.json. "
            "Please add it before using Admin features."
        )

    try:
        _connection = pyodbc.connect(conn_str, autocommit=False)
        logger.info("[DB] Connected to SQL database successfully.")
        return _connection
    except Exception as exc:
        logger.error("[DB] Failed to connect to SQL database: %s", exc)
        raise


def close_connection() -> None:
    """Gracefully close the database connection."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
            logger.info("[DB] SQL database connection closed.")
        except Exception as exc:
            logger.warning("[DB] Error closing connection: %s", exc)
        finally:
            _connection = None
