"""
tests/conftest.py
===================
Test configuration. Overrides the real MySQL dependency (app.core.database.get_db)
with a SQLite-backed equivalent pointing at a mirror of the real cleaned
dataset, so the ACTUAL FastAPI app, routes, and Pydantic validation can
be tested end-to-end without a live MySQL server.

IMPORTANT — what this does and doesn't prove:
  - DOES prove: routing, request validation, service logic, SQL query
    correctness (portable syntax), error handling, and response shapes
    all work correctly against real data.
  - DOES NOT prove: your actual MySQL server will behave identically —
    two queries (revenue-trend, delivery) use MySQL-specific functions
    (DATE_FORMAT, DATEDIFF) that are stubbed here with SQLite
    equivalents for testing only. See test_analytics.py for details.
"""

import sys
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "Python"))

from app.main import app
from app.core.database import get_db
from app.core.model_manager import model_manager


class DictCursorShim:
    """Mimics mysql.connector's dictionary=True cursor using SQLite."""
    def __init__(self, conn):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._cur = self._conn.cursor()

    def execute(self, query, params=None):
        query = query.replace("%s", "?")
        self._cur.execute(query, params or ())

    def fetchall(self):
        return [dict(row) for row in self._cur.fetchall()]

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None


@pytest.fixture(scope="session", autouse=True)
def load_models():
    model_manager.load_all()
    yield


@pytest.fixture(scope="session")
def sqlite_db_path():
    """
    Builds a SQLite mirror of the real cleaned Dataset/ CSVs, once per
    test session, using the SAME etl_pipeline.transform() logic the
    real project uses. This makes the test suite self-contained and
    runnable on any machine with the Dataset/ folder present — no live
    MySQL required to run tests, though your MySQL should still be
    tested separately for full confidence.
    """
    import etl_pipeline

    data_dir = Path(__file__).resolve().parent.parent.parent / "Dataset"
    if not data_dir.exists():
        pytest.skip(f"Dataset folder not found at {data_dir} — cannot build test DB")

    raw = etl_pipeline.extract(data_dir)
    clean = etl_pipeline.transform(raw)

    tmp_path = Path(tempfile.gettempdir()) / "ci_test_mirror.db"
    conn = sqlite3.connect(tmp_path)
    for table in ["customers", "orders", "order_items", "order_payments",
                  "order_reviews", "products", "category_translation"]:
        clean[table].to_sql(table, conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    return tmp_path


def _make_override(db_path):
    def _override_get_db():
        conn = sqlite3.connect(db_path)
        cursor = DictCursorShim(conn)
        try:
            yield (conn, cursor)
        finally:
            conn.close()
    return _override_get_db


@pytest.fixture
def client(sqlite_db_path):
    app.dependency_overrides[get_db] = _make_override(sqlite_db_path)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
