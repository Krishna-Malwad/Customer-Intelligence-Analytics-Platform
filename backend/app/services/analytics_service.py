"""
services/analytics_service.py
===============================
Real database-backed analytics, mirroring the metrics from EDA/eda_analysis.py
but exposed as live queries instead of a one-off script. Every number
comes from a SQL aggregation against the actual tables — nothing here
is a cached/precomputed constant.
"""


def get_overview(cursor) -> dict:
    cursor.execute("""
        SELECT COUNT(DISTINCT o.order_id) AS delivered_orders,
               COALESCE(SUM(oi.price + oi.freight_value), 0) AS total_revenue,
               COUNT(DISTINCT c.customer_unique_id) AS unique_customers
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.order_status = 'delivered'
    """)
    row = cursor.fetchone()
    revenue = float(row["total_revenue"] or 0)
    orders = int(row["delivered_orders"] or 0)
    return {
        "total_revenue": round(revenue, 2),
        "delivered_orders": orders,
        "unique_customers": int(row["unique_customers"] or 0),
        "average_order_value": round(revenue / orders, 2) if orders else None,
    }


def get_revenue_trend(cursor) -> list:
    import pandas as pd
    cursor.execute("""
        SELECT o.order_purchase_timestamp, oi.price, oi.freight_value
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.order_status = 'delivered'
    """)
    rows = cursor.fetchall()
    if not rows:
        return []
    df = pd.DataFrame(rows)
    df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])
    df["revenue"] = df["price"] + df["freight_value"]
    df["month"] = df["order_purchase_timestamp"].dt.strftime("%Y-%m")
    monthly = df.groupby("month")["revenue"].sum().reset_index().sort_values("month")
    return [{"month": r["month"], "revenue": round(float(r["revenue"]), 2)} for _, r in monthly.iterrows()]


def get_customer_analytics(cursor) -> dict:
    cursor.execute("""
        SELECT COUNT(DISTINCT customer_unique_id) AS total_customers
        FROM customers
    """)
    total = cursor.fetchone()["total_customers"]

    cursor.execute("""
        SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_count
        FROM customers c JOIN orders o ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered'
        GROUP BY c.customer_unique_id
    """)
    counts = [r["order_count"] for r in cursor.fetchall()]
    repeat = sum(1 for c in counts if c > 1)

    cursor.execute("""
        SELECT customer_state, COUNT(DISTINCT customer_unique_id) AS n
        FROM customers GROUP BY customer_state ORDER BY n DESC LIMIT 10
    """)
    by_state = [{"state": r["customer_state"], "customers": r["n"]} for r in cursor.fetchall()]

    return {
        "total_customers": int(total),
        "repeat_customers": repeat,
        "repeat_rate_pct": round(repeat / total * 100, 2) if total else None,
        "top_states": by_state,
    }


def get_product_analytics(cursor) -> dict:
    cursor.execute("""
        SELECT ct.product_category_name_english AS category,
               SUM(oi.price) AS revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN product_category_translation ct ON p.product_category_name = ct.product_category_name
        WHERE o.order_status = 'delivered'
        GROUP BY category
        ORDER BY revenue DESC
        LIMIT 10
    """)
    top_categories = [{"category": r["category"] or "unknown", "revenue": round(float(r["revenue"]), 2)}
                       for r in cursor.fetchall()]
    cursor.execute("SELECT COUNT(DISTINCT product_id) AS n FROM products")
    total_products = cursor.fetchone()["n"]
    return {"total_products": int(total_products), "top_categories_by_revenue": top_categories}


def get_delivery_analytics(cursor) -> dict:
    import pandas as pd
    cursor.execute("""
        SELECT order_purchase_timestamp, order_delivered_customer_date, order_estimated_delivery_date
        FROM orders
        WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
    """)
    rows = cursor.fetchall()
    if not rows:
        return {"average_delivery_days": None, "late_delivery_rate_pct": None, "worst_states_by_late_rate": []}
    df = pd.DataFrame(rows)
    for col in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        df[col] = pd.to_datetime(df[col])
    df["delivery_days"] = (df["order_delivered_customer_date"] - df["order_purchase_timestamp"]).dt.days
    df["late"] = df["order_delivered_customer_date"] > df["order_estimated_delivery_date"]
    total = len(df)
    late = int(df["late"].sum())

    cursor.execute("""
        SELECT c.customer_state, o.order_purchase_timestamp, o.order_delivered_customer_date, o.order_estimated_delivery_date
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
    """)
    state_rows = pd.DataFrame(cursor.fetchall())
    state_rows["order_delivered_customer_date"] = pd.to_datetime(state_rows["order_delivered_customer_date"])
    state_rows["order_estimated_delivery_date"] = pd.to_datetime(state_rows["order_estimated_delivery_date"])
    state_rows["late"] = state_rows["order_delivered_customer_date"] > state_rows["order_estimated_delivery_date"]
    state_stats = state_rows.groupby("customer_state")["late"].agg(["mean", "count"])
    state_stats = state_stats[state_stats["count"] >= 50].sort_values("mean", ascending=False).head(10)
    by_state = [{"state": idx, "late_rate_pct": round(row["mean"] * 100, 2)} for idx, row in state_stats.iterrows()]

    return {
        "average_delivery_days": round(float(df["delivery_days"].mean()), 2),
        "late_delivery_rate_pct": round(late / total * 100, 2) if total else None,
        "worst_states_by_late_rate": by_state,
    }


def get_satisfaction_analytics(cursor) -> dict:
    cursor.execute("""
        SELECT review_score, COUNT(*) AS n FROM order_reviews GROUP BY review_score ORDER BY review_score
    """)
    distribution = {int(r["review_score"]): int(r["n"]) for r in cursor.fetchall()}

    cursor.execute("SELECT AVG(review_score) AS avg_score, COUNT(*) AS total FROM order_reviews")
    row = cursor.fetchone()

    cursor.execute("""
        SELECT ct.product_category_name_english AS category, AVG(rv.review_score) AS avg_score, COUNT(*) AS n
        FROM order_reviews rv
        JOIN order_items oi ON rv.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN product_category_translation ct ON p.product_category_name = ct.product_category_name
        GROUP BY category HAVING n >= 30
        ORDER BY avg_score ASC LIMIT 5
    """)
    worst_categories = [{"category": r["category"] or "unknown", "avg_score": round(float(r["avg_score"]), 2), "n_reviews": int(r["n"])}
                         for r in cursor.fetchall()]

    return {
        "average_review_score": round(float(row["avg_score"]), 3) if row["avg_score"] else None,
        "total_reviews": int(row["total"] or 0),
        "score_distribution": distribution,
        "lowest_rated_categories": worst_categories,
    }
