"""
api/routes/analytics.py
=========================
Real database-backed analytics endpoints — every response reflects
the current state of the database, nothing is cached or hardcoded.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.services import analytics_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        logger.exception("Analytics query failed: %s", fn.__name__)
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {fn.__name__}")


@router.get("/overview")
def overview(db=Depends(get_db)):
    return _safe(analytics_service.get_overview, db[1])


@router.get("/revenue-trend")
def revenue_trend(db=Depends(get_db)):
    return {"trend": _safe(analytics_service.get_revenue_trend, db[1])}


@router.get("/customers")
def customers(db=Depends(get_db)):
    return _safe(analytics_service.get_customer_analytics, db[1])


@router.get("/products")
def products(db=Depends(get_db)):
    return _safe(analytics_service.get_product_analytics, db[1])


@router.get("/delivery")
def delivery(db=Depends(get_db)):
    return _safe(analytics_service.get_delivery_analytics, db[1])


@router.get("/satisfaction")
def satisfaction(db=Depends(get_db)):
    return _safe(analytics_service.get_satisfaction_analytics, db[1])
