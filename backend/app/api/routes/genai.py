"""
api/routes/genai.py
=====================
Exposes the existing Gemini-based GenAI scripts as API endpoints.
Every failure mode returns a clean, structured error.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.schemas.ml import NLQueryRequest, BusinessQuestionRequest
from app.services import genai_service, analytics_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/genai", tags=["genai"])


def get_segmentation_context() -> str:
    """
    Load the verified customer segmentation profile produced by the ML pipeline.
    This keeps the Business Assistant grounded in the actual segmentation output.
    """

    project_root = Path(__file__).resolve().parents[4]
    segment_file = project_root / "Machine_Learning" / "ml_output" / "segment_profile.csv"

    if not segment_file.exists():
        logger.warning("Segmentation profile not found: %s", segment_file)
        return (
            "CUSTOMER SEGMENTATION\n"
            "---------------------\n"
            "Verified segmentation profile is not currently available.\n"
        )

    try:
        import pandas as pd

        df = pd.read_csv(segment_file)

        required_columns = {
            "cluster",
            "n_customers",
            "avg_recency_days",
            "avg_frequency",
            "avg_monetary",
            "total_monetary",
            "segment_label",
        }

        if not required_columns.issubset(df.columns):
            logger.warning(
                "Segmentation profile is missing required columns: %s",
                required_columns - set(df.columns),
            )
            return (
                "CUSTOMER SEGMENTATION\n"
                "---------------------\n"
                "Segmentation profile exists but does not contain the expected fields.\n"
            )

        lines = [
            "CUSTOMER SEGMENTATION — VERIFIED ML OUTPUT",
            "------------------------------------------",
            "These figures come directly from the customer segmentation model output.",
            "Do not invent, rename, or replace these segment figures.",
            "",
        ]

        for _, row in df.iterrows():
            lines.append(
                f"Cluster {int(row['cluster'])}: "
                f"{row['segment_label']} | "
                f"Customers: {int(row['n_customers']):,} | "
                f"Avg recency: {float(row['avg_recency_days']):.2f} days | "
                f"Avg frequency: {float(row['avg_frequency']):.2f} | "
                f"Avg monetary: R${float(row['avg_monetary']):,.2f} | "
                f"Total monetary: R${float(row['total_monetary']):,.2f}"
            )

        total_customers = int(df["n_customers"].sum())
        total_segment_revenue = float(df["total_monetary"].sum())

        lines.extend(
            [
                "",
                f"Total customers represented in segmentation: {total_customers:,}",
                f"Total monetary value represented by segments: R${total_segment_revenue:,.2f}",
            ]
        )

        return "\n".join(lines)

    except Exception:
        logger.exception("Failed to load customer segmentation profile")
        return (
            "CUSTOMER SEGMENTATION\n"
            "---------------------\n"
            "Segmentation profile could not be loaded.\n"
        )


@router.post("/ask")
def ask_business_question(payload: BusinessQuestionRequest, db=Depends(get_db)):
    conn, cursor = db

    try:
        overview = analytics_service.get_overview(cursor)
        customer = analytics_service.get_customer_analytics(cursor)
        product = analytics_service.get_product_analytics(cursor)
        delivery = analytics_service.get_delivery_analytics(cursor)
        satisfaction = analytics_service.get_satisfaction_analytics(cursor)
        segmentation_context = get_segmentation_context()

        context_text = f"""
REAL DATABASE-BACKED BUSINESS METRICS
======================================

IMPORTANT:
- These are verified metrics from the project's database and ML output.
- Never invent, estimate, or substitute numbers.
- If the requested information is not present below, explicitly say that it
  is not available in the provided metrics.
- All monetary values are Brazilian Real (BRL). Use R$.
- When discussing customer segments, use the verified segmentation output
  provided below.
- Do not create alternative segment names or customer counts.

OVERALL BUSINESS
----------------
Total delivered revenue: R${overview["total_revenue"]:,.2f}
Delivered orders: {overview["delivered_orders"]:,}
Unique customers: {overview["unique_customers"]:,}
Average order value: R${overview["average_order_value"]:,.2f}

CUSTOMER ANALYTICS
------------------
Total customers: {customer["total_customers"]:,}
Repeat customers: {customer["repeat_customers"]:,}
Repeat customer rate: {customer["repeat_rate_pct"]:.2f}%

Top customer states:
{customer["top_states"]}

{segmentation_context}

PRODUCT ANALYTICS
-----------------
Total products: {product["total_products"]:,}

Top product categories by revenue:
{product["top_categories_by_revenue"]}

DELIVERY ANALYTICS
------------------
Average delivery time: {delivery["average_delivery_days"]:.2f} days
Late delivery rate: {delivery["late_delivery_rate_pct"]:.2f}%

Worst states by late-delivery rate:
{delivery["worst_states_by_late_rate"]}

CUSTOMER SATISFACTION
---------------------
Average review score: {satisfaction["average_review_score"]:.3f}/5
Total reviews: {satisfaction["total_reviews"]:,}

Review score distribution:
{satisfaction["score_distribution"]}

Lowest-rated product categories:
{satisfaction["lowest_rated_categories"]}
"""

    except Exception:
        logger.exception("Failed to build GenAI business context")
        context_text = (
            "No verified business metrics are currently available. "
            "Do not invent numerical values."
        )

    try:
        return genai_service.ask_business_question(
            payload.question,
            context_text
        )
    except genai_service.GenAIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/nl-to-sql")
def nl_to_sql(payload: NLQueryRequest, db=Depends(get_db)):
    conn, cursor = db

    try:
        return genai_service.natural_language_to_sql(
            payload.question,
            cursor
        )
    except genai_service.GenAIError as e:
        raise HTTPException(status_code=422, detail=str(e))
