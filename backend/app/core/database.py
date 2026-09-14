"""
database/connection.py
========================
Reuses the exact same MySQL connection pattern as your existing
Python/database_connection.py — same DB_CONFIG shape, same credentials
source (.env). This is the FastAPI-adapted version: a dependency you
inject into endpoints via `Depends(get_db)`, rather than a context
manager used in standalone scripts.
"""

import logging
import mysql.connector
from mysql.connector import Error

from app.core.config import settings

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": settings.DB_HOST,
    "port": settings.DB_PORT,
    "user": settings.DB_USER,
    "password": settings.DB_PASSWORD,
    "database": settings.DB_NAME,
    "autocommit": True,
    "ssl_disabled": False,
}


def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        logger.error("Failed to connect to MySQL: %s", e)
        raise


def get_db():
    """
    FastAPI dependency — yields a (connection, cursor) pair and always
    closes both, even if the request handler raises. Use like:

        @router.get("/example")
        def example(db=Depends(get_db)):
            conn, cursor = db
            cursor.execute("SELECT 1")
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)  # dictionary=True -> rows as {col: value}
    try:
        yield conn, cursor
    finally:
        cursor.close()
        conn.close()
