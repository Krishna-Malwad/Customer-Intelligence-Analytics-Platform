"""
api/routes/health.py
======================
GET /api/health — never exposes secrets, only status booleans/strings.
"""

from fastapi import APIRouter, Depends
from mysql.connector import Error

from app.core.database import get_db
from app.core.model_manager import model_manager
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(db=Depends(get_db)):
    conn, cursor = db
    db_status = "unknown"
    try:
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db_status = "connected"
    except Error:
        db_status = "unreachable"

    return {
        "api_status": "running",
        "database_status": db_status,
        "ml_models": model_manager.load_status,
        "genai_configured": bool(settings.GEMINI_API_KEY),  # never returns the key itself
    }
