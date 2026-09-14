"""
api/routes/ml.py
==================
Direct model-serving endpoints. Uses models already loaded at startup
(app.core.model_manager) — no retraining happens on any request here.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.schemas.ml import SegmentRequest, RetentionRequest, OrderValueRequest
from app.services import ml_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.post("/segment-customer")
def segment_customer(payload: SegmentRequest):
    try:
        return ml_service.segment_customer(payload.recency_days, payload.frequency, payload.monetary)
    except ml_service.ModelUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Segmentation model unavailable: {e}")
    except Exception:
        logger.exception("Segmentation prediction failed")
        raise HTTPException(status_code=500, detail="Prediction failed")


@router.post("/predict-retention")
def predict_retention(payload: RetentionRequest):
    try:
        return ml_service.predict_retention(**payload.model_dump())
    except ml_service.ModelUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Retention model unavailable: {e}")
    except Exception:
        logger.exception("Retention prediction failed")
        raise HTTPException(status_code=500, detail="Prediction failed")


@router.post("/predict-order-value")
def predict_order_value(payload: OrderValueRequest):
    try:
        return ml_service.predict_order_value(**payload.model_dump())
    except ml_service.ModelUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"CLV model unavailable: {e}")
    except Exception:
        logger.exception("Order value prediction failed")
        raise HTTPException(status_code=500, detail="Prediction failed")


@router.get("/recommendations/{customer_id}")
def get_recommendations(customer_id: str, db=Depends(get_db)):
    conn, cursor = db
    try:
        return ml_service.get_recommendations_for_customer(cursor, customer_id)
    except ml_service.ModelUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Recommendation model unavailable: {e}")
    except Exception:
        logger.exception("Recommendation lookup failed")
        raise HTTPException(status_code=500, detail="Recommendation lookup failed")
