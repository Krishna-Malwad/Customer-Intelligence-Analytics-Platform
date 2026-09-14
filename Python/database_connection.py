"""
database_connection.py
=======================
Centralized MySQL connection handling for the ETL pipeline.

Why a separate module?
-----------------------
In a real project you NEVER hardcode credentials inside your ETL logic.
Keeping connection handling in one place means:
  - credentials are read from environment variables (or a .env file),
  - every script (etl_pipeline.py, validation.py, analysis scripts)
    reuses the exact same connection logic,
  - if you switch host/port/database later, you change it in ONE file.
"""

import os
import logging
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error, MySQLConnection

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.environ.get("CI_DB_HOST", "localhost"),
    "port": int(os.environ.get("CI_DB_PORT", 3306)),
    "user": os.environ.get("CI_DB_USER", "root"),
    "password": os.environ.get("CI_DB_PASSWORD", ""),
    "database": os.environ.get("CI_DB_NAME", "customer_intelligence"),
    "autocommit": False,
}


def get_connection() -> MySQLConnection:
    """
    Open a new MySQL connection using DB_CONFIG.

    Returns
    -------
    mysql.connector.connection.MySQLConnection

    Raises
    ------
    mysql.connector.Error if the connection fails (bad credentials,
    database not reachable, etc). We let this propagate — the caller
    (etl_pipeline.py) decides how to handle a failed connection, this
    module's only job is to open one.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        logger.info("Connected to MySQL database '%s' on %s:%s",
                    DB_CONFIG["database"], DB_CONFIG["host"], DB_CONFIG["port"])
        return conn
    except Error as e:
        logger.error("Failed to connect to MySQL: %s", e)
        raise


@contextmanager
def get_cursor(commit_on_success: bool = True):
    """
    Context manager that yields (connection, cursor) and guarantees:
      - commit() if the block succeeds and commit_on_success=True
      - rollback() if the block raises
      - cursor + connection are always closed

    Usage
    -----
    with get_cursor() as (conn, cursor):
        cursor.execute("SELECT 1")
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield conn, cursor
        if commit_on_success:
            conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Transaction rolled back due to an error.")
        raise
    finally:
        cursor.close()
        conn.close()


def test_connection() -> bool:
    """Quick health check used by the pipeline before doing real work."""
    try:
        with get_cursor(commit_on_success=False) as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Error:
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok = test_connection()
    print("Connection OK" if ok else "Connection FAILED — check CI_DB_* env vars")
