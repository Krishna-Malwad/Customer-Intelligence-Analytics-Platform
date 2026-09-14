"""
services/customer_service.py
==============================
All the real logic behind the Customer 360 / Intelligence endpoints.
Every number here is either a direct DB query result or a prediction
from a loaded model — nothing is invented.

IMPORTANT DESIGN NOTE — "customer_id" vs "customer_unique_id":
------------------------------------------------------------------
Throughout this whole project we established that Olist generates a
NEW customer_id for every order, even for the same real person —
customer_unique_id is the actual persistent identity. This API
therefore treats the {customer_id} path parameter as a
customer_unique_id. This is documented in the API docstrings so it's
not a silent surprise.

IMPORTANT DESIGN NOTE — "as-of" date for recency:
------------------------------------------------------------------
The dataset runs Sept 2016 - Aug 2018. All 4 ML models were trained
treating "now" as just after the last order in the dataset (2018-08-30).
Computing recency against today's real-world date would put every
customer's recency wildly outside the distribution the models were
trained on, making retention/segment predictions meaningless. So this
service uses the dataset's own "as-of" date, not datetime.now(). This
is a deliberate, documented choice — not a bug.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.model_manager import model_manager

logger = logging.getLogger(__name__)

AS_OF_DATE = datetime(2018, 8, 30)  # see docstring above


def _fetch_customer_orders(cursor, customer_unique_id: str) -> pd.DataFrame:
    """All orders for this customer, with computed order_total per order."""
    query = """
        SELECT o.order_id, o.order_status, o.order_purchase_timestamp,
               o.order_delivered_customer_date, o.order_estimated_delivery_date,
               COALESCE(SUM(oi.price), 0) AS item_revenue,
               COALESCE(SUM(oi.freight_value), 0) AS freight_total,
               COUNT(oi.order_item_id) AS n_items
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        LEFT JOIN order_items oi ON oi.order_id = o.order_id
        WHERE c.customer_unique_id = %s
        GROUP BY o.order_id, o.order_status, o.order_purchase_timestamp,
                 o.order_delivered_customer_date, o.order_estimated_delivery_date
        ORDER BY o.order_purchase_timestamp
    """
    cursor.execute(query, (customer_unique_id,))
    rows = cursor.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])
    df["order_total"] = df["item_revenue"] + df["freight_total"]
    return df


def _fetch_customer_profile(cursor, customer_unique_id: str) -> dict | None:
    query = """
        SELECT customer_unique_id, customer_state, customer_city
        FROM customers
        WHERE customer_unique_id = %s
        LIMIT 1
    """
    cursor.execute(query, (customer_unique_id,))
    row = cursor.fetchone()
    return row  # dict (cursor is dictionary=True) or None


def _fetch_order_features(cursor, order_id: str) -> dict:
    """Payment + category + review features for one order, used by ML models."""
    cursor.execute("""
        SELECT payment_installments, payment_type
        FROM order_payments WHERE order_id = %s
    """, (order_id,))
    payments = cursor.fetchall()

    cursor.execute("""
        SELECT p.product_category_name
        FROM order_items oi JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = %s
    """, (order_id,))
    cats = [r["product_category_name"] for r in cursor.fetchall() if r["product_category_name"]]

    cursor.execute("""
        SELECT review_score FROM order_reviews WHERE order_id = %s
    """, (order_id,))
    reviews = [r["review_score"] for r in cursor.fetchall()]

    return {
        "payment_installments": max((p["payment_installments"] for p in payments), default=1),
        "n_payment_methods": len(set(p["payment_type"] for p in payments)) or 1,
        "primary_payment_type": (max(set(p["payment_type"] for p in payments),
                                      key=[p["payment_type"] for p in payments].count)
                                  if payments else "unknown"),
        "product_category_name": (max(set(cats), key=cats.count) if cats else "unknown"),
        "review_score": (sum(reviews) / len(reviews)) if reviews else 4.0,  # dataset-wide median-ish fallback
    }


def compute_rfm(orders_df: pd.DataFrame) -> dict:
    delivered = orders_df[orders_df["order_status"] == "delivered"]
    if delivered.empty:
        return {"recency_days": None, "frequency": 0, "monetary": 0.0}
    recency_days = (AS_OF_DATE - delivered["order_purchase_timestamp"].max()).days
    return {
        "recency_days": int(recency_days),
        "frequency": int(delivered["order_id"].nunique()),
        "monetary": round(float(delivered["order_total"].sum()), 2),
    }


def predict_segment(rfm: dict) -> dict:
    if model_manager.segmentation is None:
        return {"segment": None, "status": model_manager.load_status.get("segmentation", "unavailable")}
    if rfm["frequency"] == 0:
        return {"segment": None, "status": "no delivered orders to segment on"}

    kmeans = model_manager.segmentation["kmeans"]
    scaler = model_manager.segmentation["scaler"]
    monetary_log = np.log1p(rfm["monetary"])
    frequency_log = np.log1p(rfm["frequency"])
    X = pd.DataFrame([{
        "recency_days": rfm["recency_days"],
        "frequency_log": frequency_log,
        "monetary_log": monetary_log,
    }])
    X_scaled = scaler.transform(X)
    cluster = int(kmeans.predict(X_scaled)[0])
    return {"segment_cluster": cluster, "status": "predicted"}


def predict_retention(rfm: dict, order_features: dict, customer_state: str) -> dict:
    if model_manager.retention_pipeline is None:
        return {"probability": None, "status": model_manager.load_status.get("retention_pipeline", "unavailable")}
    if rfm["frequency"] == 0:
        return {"probability": None, "status": "no delivered orders to predict from"}

    X = pd.DataFrame([{
        "order_total": rfm["monetary"] / rfm["frequency"],
        "n_items": order_features.get("n_items", 1),
        "payment_installments": order_features["payment_installments"],
        "review_score": order_features["review_score"],
        "product_category_name": order_features["product_category_name"],
        "primary_payment_type": order_features["primary_payment_type"],
        "customer_state": customer_state,
    }])
    proba = float(model_manager.retention_pipeline.predict_proba(X)[0][1])
    return {"probability": round(proba, 4), "status": "predicted"}


def predict_order_value(order_features: dict, customer_state: str, n_items: int) -> dict:
    if model_manager.clv_pipeline is None:
        return {"predicted_value": None, "status": model_manager.load_status.get("clv_pipeline", "unavailable")}

    X = pd.DataFrame([{
        "payment_installments": order_features["payment_installments"],
        "n_payment_methods": order_features["n_payment_methods"],
        "review_score": order_features["review_score"],
        "n_items": n_items,
        "product_category_name": order_features["product_category_name"],
        "primary_payment_type": order_features["primary_payment_type"],
        "customer_state": customer_state,
    }])
    pred = float(model_manager.clv_pipeline.predict(X)[0])
    return {"predicted_value": round(pred, 2), "status": "predicted"}


def get_recommendations(cursor, customer_unique_id: str, top_n: int = 5) -> dict:
    if model_manager.co_occurrence is None:
        return {"recommendations": [], "status": model_manager.load_status.get("co_occurrence", "unavailable")}

    cursor.execute("""
        SELECT DISTINCT oi.product_id
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.customer_unique_id = %s
    """, (customer_unique_id,))
    purchased = [r["product_id"] for r in cursor.fetchall()]
    if not purchased:
        return {"recommendations": [], "status": "no purchase history"}

    from collections import Counter
    scores = Counter()
    for pid in purchased:
        for (a, b), count in model_manager.co_occurrence.items():
            if a == pid:
                scores[b] += count
            elif b == pid:
                scores[a] += count
    recs = [{"product_id": pid, "score": score} for pid, score in scores.most_common(top_n * 2)
            if pid not in purchased][:top_n]
    return {"recommendations": recs, "status": "computed" if recs else "no co-purchase signal found"}


def build_insights(rfm: dict, segment: dict, retention: dict) -> list:
    insights = []
    if rfm["frequency"] > 1:
        insights.append(f"Repeat customer with {rfm['frequency']} delivered orders — above the dataset's 3.12% repeat rate baseline.")
    else:
        insights.append("One-time buyer so far — matches the dataset's dominant customer pattern (~97% of customers).")
    if retention.get("probability") is not None:
        if retention["probability"] > 0.5:
            insights.append(f"Above-average predicted likelihood of returning ({retention['probability']*100:.1f}%).")
        else:
            insights.append(f"Below-average predicted likelihood of returning ({retention['probability']*100:.1f}%).")
    if rfm["recency_days"] is not None and rfm["recency_days"] > 365:
        insights.append(f"Last order was {rfm['recency_days']} days before the dataset's end — likely dormant.")
    return insights


def get_customer_360(cursor, customer_unique_id: str) -> dict | None:
    profile = _fetch_customer_profile(cursor, customer_unique_id)
    if profile is None:
        return None

    orders_df = _fetch_customer_orders(cursor, customer_unique_id)
    rfm = compute_rfm(orders_df)

    if not orders_df.empty:
        latest_order_id = orders_df.iloc[-1]["order_id"]
        latest_n_items = int(orders_df.iloc[-1]["n_items"]) or 1
        order_features = _fetch_order_features(cursor, latest_order_id)
        first_purchase = orders_df["order_purchase_timestamp"].min().isoformat()
        last_purchase = orders_df["order_purchase_timestamp"].max().isoformat()
    else:
        order_features = {"payment_installments": 1, "n_payment_methods": 1,
                           "primary_payment_type": "unknown", "product_category_name": "unknown",
                           "review_score": 4.0}
        latest_n_items = 1
        first_purchase = last_purchase = None

    segment = predict_segment(rfm)
    retention = predict_retention(rfm, order_features, profile["customer_state"])
    order_value_pred = predict_order_value(order_features, profile["customer_state"], latest_n_items)
    recs = get_recommendations(cursor, customer_unique_id)
    insights = build_insights(rfm, segment, retention)

    return {
        "customer_unique_id": profile["customer_unique_id"],
        "state": profile["customer_state"],
        "city": profile["customer_city"],
        "order_count": rfm["frequency"],
        "total_revenue": rfm["monetary"],
        "average_order_value": round(rfm["monetary"] / rfm["frequency"], 2) if rfm["frequency"] else None,
        "first_purchase_date": first_purchase,
        "last_purchase_date": last_purchase,
        "rfm": rfm,
        "segment": segment,
        "retention_prediction": retention,
        "predicted_next_order_value": order_value_pred,
        "recommendations": recs,
        "insights": insights,
    }
