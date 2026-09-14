"""
services/ml_service.py
========================
Thin wrappers around the loaded models (app.core.model_manager) for the
direct /api/ml/* endpoints. These accept raw feature inputs (validated
by Pydantic schemas in the route layer) rather than looking a customer
up in the database — that's what customer_service.get_customer_360
already does. This separation matches the spec's distinction between
"Customer 360" (DB + ML combined) and "ML API" (model-only, given
arbitrary feature input).
"""

import numpy as np
import pandas as pd

from app.core.model_manager import model_manager


class ModelUnavailableError(Exception):
    pass


def segment_customer(recency_days: float, frequency: int, monetary: float) -> dict:
    if model_manager.segmentation is None:
        raise ModelUnavailableError(model_manager.load_status.get("segmentation", "unavailable"))
    kmeans = model_manager.segmentation["kmeans"]
    scaler = model_manager.segmentation["scaler"]
    X = pd.DataFrame([{
        "recency_days": recency_days,
        "frequency_log": np.log1p(frequency),
        "monetary_log": np.log1p(monetary),
    }])
    cluster = int(kmeans.predict(scaler.transform(X))[0])
    return {"segment_cluster": cluster}


def predict_retention(order_total: float, n_items: int, payment_installments: int,
                       review_score: float, product_category_name: str,
                       primary_payment_type: str, customer_state: str) -> dict:
    if model_manager.retention_pipeline is None:
        raise ModelUnavailableError(model_manager.load_status.get("retention_pipeline", "unavailable"))
    X = pd.DataFrame([{
        "order_total": order_total, "n_items": n_items,
        "payment_installments": payment_installments, "review_score": review_score,
        "product_category_name": product_category_name,
        "primary_payment_type": primary_payment_type, "customer_state": customer_state,
    }])
    proba = float(model_manager.retention_pipeline.predict_proba(X)[0][1])
    return {"repeat_purchase_probability": round(proba, 4)}


def predict_order_value(payment_installments: int, n_payment_methods: int, review_score: float,
                         n_items: int, product_category_name: str, primary_payment_type: str,
                         customer_state: str) -> dict:
    if model_manager.clv_pipeline is None:
        raise ModelUnavailableError(model_manager.load_status.get("clv_pipeline", "unavailable"))
    X = pd.DataFrame([{
        "payment_installments": payment_installments, "n_payment_methods": n_payment_methods,
        "review_score": review_score, "n_items": n_items,
        "product_category_name": product_category_name,
        "primary_payment_type": primary_payment_type, "customer_state": customer_state,
    }])
    pred = float(model_manager.clv_pipeline.predict(X)[0])
    return {"predicted_order_value": round(pred, 2)}


def get_recommendations_for_customer(cursor, customer_unique_id: str, top_n: int = 5) -> dict:
    if model_manager.co_occurrence is None:
        raise ModelUnavailableError(model_manager.load_status.get("co_occurrence", "unavailable"))

    cursor.execute("""
        SELECT DISTINCT oi.product_id
        FROM order_items oi JOIN orders o ON oi.order_id = o.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.customer_unique_id = %s
    """, (customer_unique_id,))
    purchased = {r["product_id"] for r in cursor.fetchall()}
    if not purchased:
        return {"recommendations": [], "note": "no purchase history for this customer"}

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
    return {"recommendations": recs}
