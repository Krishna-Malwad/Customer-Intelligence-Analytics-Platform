"""
api/routes/data_quality.py
============================
GET /api/data-quality — runs real checks against the live database.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.services import data_quality_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["data-quality"])


@router.get("/data-quality")
def data_quality(db=Depends(get_db)):
    conn, cursor = db
    try:
        return data_quality_service.run_all_checks(cursor)
    except Exception:
        logger.exception("Data quality check failed")
        raise HTTPException(status_code=500, detail="Data quality checks failed to run")
