"""
api/routes/customers.py
=========================
GET /api/customers/{customer_id} — Customer 360 profile.

NOTE: {customer_id} means customer_unique_id — see
app/services/customer_service.py docstring for why.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.services import customer_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/{customer_id}")
def get_customer(customer_id: str, db=Depends(get_db)):
    conn, cursor = db
    try:
        result = customer_service.get_customer_360(cursor, customer_id)
    except Exception as e:
        logger.exception("Error building customer 360 for %s", customer_id)
        raise HTTPException(status_code=500, detail="Internal error computing customer profile")

    if result is None:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    return result
