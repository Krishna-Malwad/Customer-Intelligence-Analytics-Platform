"""
api/routes/analytics.py
=========================

Real database-backed analytics endpoints.

Individual endpoints are preserved for page-specific use.
A combined overview endpoint reduces frontend HTTP requests
during the initial dashboard load.

Overview analytics are executed in parallel using independent
MySQL connections to reduce total response time.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db, get_connection
from app.services import analytics_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
)


# ============================================================
# ERROR HANDLING
# ============================================================

def _safe(fn, *args):
    """
    Execute an analytics function safely.

    Used by the individual page-specific endpoints.
    """
    try:
        return fn(*args)

    except Exception:
        logger.exception(
            "Analytics query failed: %s",
            fn.__name__,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Analytics query failed: {fn.__name__}",
        )


# ============================================================
# PARALLEL ANALYTICS HELPER
# ============================================================

def _run_analytics(fn):
    """
    Run one analytics function using its own MySQL connection.

    Each parallel worker gets an independent connection so that
    MySQL cursors/connections are never shared between threads.
    """

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        return fn(cursor)

    finally:
        cursor.close()
        connection.close()


# ============================================================
# COMBINED OVERVIEW
# ============================================================

@router.get("/overview-full")
def overview_full():
    """
    Return all analytics required by the Overview page
    through a single HTTP request.

    The six analytics queries run concurrently using separate
    MySQL connections.

    Individual analytics functions retain their own
    60-second TTL cache.
    """

    analytics_tasks = {
        "overview": analytics_service.get_overview,
        "revenue_trend": analytics_service.get_revenue_trend,
        "customers": analytics_service.get_customer_analytics,
        "products": analytics_service.get_product_analytics,
        "delivery": analytics_service.get_delivery_analytics,
        "satisfaction": analytics_service.get_satisfaction_analytics,
    }

    results = {}

    try:
        with ThreadPoolExecutor(max_workers=6) as executor:

            future_to_name = {
                executor.submit(_run_analytics, fn): name
                for name, fn in analytics_tasks.items()
            }

            for future in as_completed(future_to_name):

                name = future_to_name[future]

                try:
                    results[name] = future.result()

                except Exception:
                    logger.exception(
                        "Parallel analytics query failed: %s",
                        name,
                    )

                    raise HTTPException(
                        status_code=500,
                        detail=f"Analytics query failed: {name}",
                    )

        return {
            "overview": results["overview"],
            "revenue_trend": results["revenue_trend"],
            "customers": results["customers"],
            "products": results["products"],
            "delivery": results["delivery"],
            "satisfaction": results["satisfaction"],
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Combined overview analytics failed")

        raise HTTPException(
            status_code=500,
            detail="Combined overview analytics failed",
        )


# ============================================================
# INDIVIDUAL ENDPOINTS
# ============================================================

@router.get("/overview")
def overview(db=Depends(get_db)):
    return _safe(
        analytics_service.get_overview,
        db[1],
    )


@router.get("/revenue-trend")
def revenue_trend(db=Depends(get_db)):
    return {
        "trend": _safe(
            analytics_service.get_revenue_trend,
            db[1],
        )
    }


@router.get("/customers")
def customers(db=Depends(get_db)):
    return _safe(
        analytics_service.get_customer_analytics,
        db[1],
    )


@router.get("/products")
def products(db=Depends(get_db)):
    return _safe(
        analytics_service.get_product_analytics,
        db[1],
    )


@router.get("/delivery")
def delivery(db=Depends(get_db)):
    return _safe(
        analytics_service.get_delivery_analytics,
        db[1],
    )


@router.get("/satisfaction")
def satisfaction(db=Depends(get_db)):
    return _safe(
        analytics_service.get_satisfaction_analytics,
        db[1],
    )