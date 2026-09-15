"""
services/analytics_service.py

Production analytics service.

All analytics are calculated inside MySQL using SQL aggregations.
Only small aggregated result sets are transferred to the API.

A short in-memory TTL cache prevents repeated historical analytics
queries from hitting the remote MySQL database unnecessarily.
"""

import time
from functools import wraps


# ============================================================
# ANALYTICS CACHE
# ============================================================

CACHE_TTL_SECONDS = 60

_ANALYTICS_CACHE = {}


def cached_analytics(func):
    """
    Cache the result of an analytics function for a short period.

    The cursor is intentionally NOT part of the cache key because
    database cursors are created per request and are not reusable.
    """

    @wraps(func)
    def wrapper(cursor):
        cache_key = func.__name__
        now = time.monotonic()

        cached = _ANALYTICS_CACHE.get(cache_key)

        if cached is not None:
            cached_time, cached_value = cached

            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_value

        result = func(cursor)

        _ANALYTICS_CACHE[cache_key] = (
            now,
            result,
        )

        return result

    return wrapper


def clear_analytics_cache():
    """
    Clear cached analytics results.

    Useful if the database is updated or data is reloaded.
    """
    _ANALYTICS_CACHE.clear()


# ============================================================
# OVERVIEW
# ============================================================

@cached_analytics
def get_overview(cursor) -> dict:

    cursor.execute("""
        SELECT
            COUNT(DISTINCT o.order_id) AS delivered_orders,
            COALESCE(SUM(oi.price + oi.freight_value), 0) AS total_revenue,
            COUNT(DISTINCT c.customer_unique_id) AS unique_customers
        FROM orders o
        JOIN customers c
            ON o.customer_id = c.customer_id
        JOIN order_items oi
            ON oi.order_id = o.order_id
        WHERE o.order_status = 'delivered'
    """)

    row = cursor.fetchone()

    revenue = float(row["total_revenue"] or 0)
    orders = int(row["delivered_orders"] or 0)
    customers = int(row["unique_customers"] or 0)

    return {
        "total_revenue": round(revenue, 2),
        "delivered_orders": orders,
        "unique_customers": customers,
        "average_order_value": round(revenue / orders, 2)
        if orders else None,
    }


# ============================================================
# REVENUE TREND
# ============================================================

@cached_analytics
def get_revenue_trend(cursor) -> list:

    cursor.execute("""
        SELECT
            DATE_FORMAT(
                o.order_purchase_timestamp,
                '%Y-%m'
            ) AS month,

            ROUND(
                SUM(
                    oi.price + oi.freight_value
                ),
                2
            ) AS revenue

        FROM orders o

        JOIN order_items oi
            ON oi.order_id = o.order_id

        WHERE o.order_status = 'delivered'

        GROUP BY
            DATE_FORMAT(
                o.order_purchase_timestamp,
                '%Y-%m'
            )

        ORDER BY month
    """)

    return [
        {
            "month": row["month"],
            "revenue": round(
                float(row["revenue"] or 0),
                2,
            ),
        }
        for row in cursor.fetchall()
    ]


# ============================================================
# CUSTOMER ANALYTICS
# ============================================================

@cached_analytics
def get_customer_analytics(cursor) -> dict:

    cursor.execute("""
        SELECT COUNT(*) AS total_customers
        FROM customers
    """)

    total = int(
        cursor.fetchone()["total_customers"] or 0
    )

    cursor.execute("""
        SELECT COUNT(*) AS repeat_customers
        FROM (
            SELECT
                c.customer_unique_id

            FROM customers c

            JOIN orders o
                ON o.customer_id = c.customer_id

            WHERE o.order_status = 'delivered'

            GROUP BY
                c.customer_unique_id

            HAVING COUNT(
                DISTINCT o.order_id
            ) > 1

        ) AS repeat_customer_list
    """)

    repeat = int(
        cursor.fetchone()["repeat_customers"] or 0
    )

    cursor.execute("""
        SELECT
            customer_state,
            COUNT(
                DISTINCT customer_unique_id
            ) AS customers

        FROM customers

        GROUP BY customer_state

        ORDER BY customers DESC

        LIMIT 10
    """)

    by_state = [
        {
            "state": row["customer_state"],
            "customers": int(
                row["customers"] or 0
            ),
        }
        for row in cursor.fetchall()
    ]

    return {
        "total_customers": total,
        "repeat_customers": repeat,
        "repeat_rate_pct": round(
            repeat / total * 100,
            2,
        )
        if total
        else None,
        "top_states": by_state,
    }


# ============================================================
# PRODUCT ANALYTICS
# ============================================================

@cached_analytics
def get_product_analytics(cursor) -> dict:

    cursor.execute("""
        SELECT
            COALESCE(
                ct.product_category_name_english,
                p.product_category_name,
                'unknown'
            ) AS category,

            ROUND(
                SUM(oi.price),
                2
            ) AS revenue

        FROM order_items oi

        JOIN orders o
            ON oi.order_id = o.order_id

        JOIN products p
            ON oi.product_id = p.product_id

        LEFT JOIN product_category_translation ct
            ON p.product_category_name =
               ct.product_category_name

        WHERE o.order_status = 'delivered'

        GROUP BY
            COALESCE(
                ct.product_category_name_english,
                p.product_category_name,
                'unknown'
            )

        ORDER BY revenue DESC

        LIMIT 10
    """)

    top_categories = [
        {
            "category": row["category"],
            "revenue": round(
                float(row["revenue"] or 0),
                2,
            ),
        }
        for row in cursor.fetchall()
    ]

    cursor.execute("""
        SELECT COUNT(
            DISTINCT product_id
        ) AS total_products

        FROM products
    """)

    total_products = int(
        cursor.fetchone()["total_products"] or 0
    )

    return {
        "total_products": total_products,
        "top_categories_by_revenue": top_categories,
    }


# ============================================================
# DELIVERY ANALYTICS
# ============================================================

@cached_analytics
def get_delivery_analytics(cursor) -> dict:

    cursor.execute("""
        SELECT

            ROUND(
                AVG(
                    DATEDIFF(
                        order_delivered_customer_date,
                        order_purchase_timestamp
                    )
                ),
                2
            ) AS average_delivery_days,

            ROUND(
                100 * AVG(
                    CASE
                        WHEN
                            order_delivered_customer_date >
                            order_estimated_delivery_date
                        THEN 1
                        ELSE 0
                    END
                ),
                2
            ) AS late_delivery_rate_pct

        FROM orders

        WHERE order_status = 'delivered'

          AND order_delivered_customer_date
              IS NOT NULL
    """)

    row = cursor.fetchone()

    cursor.execute("""
        SELECT

            c.customer_state AS state,

            ROUND(
                100 * AVG(
                    CASE
                        WHEN
                            o.order_delivered_customer_date >
                            o.order_estimated_delivery_date
                        THEN 1
                        ELSE 0
                    END
                ),
                2
            ) AS late_rate_pct,

            COUNT(*) AS order_count

        FROM orders o

        JOIN customers c
            ON o.customer_id = c.customer_id

        WHERE o.order_status = 'delivered'

          AND o.order_delivered_customer_date
              IS NOT NULL

        GROUP BY c.customer_state

        HAVING COUNT(*) >= 50

        ORDER BY late_rate_pct DESC

        LIMIT 10
    """)

    by_state = [
        {
            "state": row["state"],
            "late_rate_pct": round(
                float(
                    row["late_rate_pct"] or 0
                ),
                2,
            ),
        }
        for row in cursor.fetchall()
    ]

    return {
        "average_delivery_days": (
            round(
                float(
                    row["average_delivery_days"]
                ),
                2,
            )
            if row["average_delivery_days"]
            is not None
            else None
        ),

        "late_delivery_rate_pct": (
            round(
                float(
                    row["late_delivery_rate_pct"]
                ),
                2,
            )
            if row["late_delivery_rate_pct"]
            is not None
            else None
        ),

        "worst_states_by_late_rate": by_state,
    }


# ============================================================
# SATISFACTION ANALYTICS
# ============================================================

@cached_analytics
def get_satisfaction_analytics(cursor) -> dict:

    cursor.execute("""
        SELECT
            review_score,
            COUNT(*) AS n

        FROM order_reviews

        GROUP BY review_score

        ORDER BY review_score
    """)

    distribution = {
        int(row["review_score"]): int(row["n"])
        for row in cursor.fetchall()
    }

    cursor.execute("""
        SELECT
            AVG(review_score) AS avg_score,
            COUNT(*) AS total

        FROM order_reviews
    """)

    row = cursor.fetchone()

    cursor.execute("""
        SELECT

            COALESCE(
                ct.product_category_name_english,
                p.product_category_name,
                'unknown'
            ) AS category,

            ROUND(
                AVG(rv.review_score),
                2
            ) AS avg_score,

            COUNT(*) AS n_reviews

        FROM order_reviews rv

        JOIN order_items oi
            ON rv.order_id = oi.order_id

        JOIN products p
            ON oi.product_id = p.product_id

        LEFT JOIN product_category_translation ct
            ON p.product_category_name =
               ct.product_category_name

        GROUP BY
            COALESCE(
                ct.product_category_name_english,
                p.product_category_name,
                'unknown'
            )

        HAVING COUNT(*) >= 30

        ORDER BY avg_score ASC

        LIMIT 5
    """)

    worst_categories = [
        {
            "category": row["category"],
            "avg_score": round(
                float(row["avg_score"] or 0),
                2,
            ),
            "n_reviews": int(
                row["n_reviews"] or 0
            ),
        }
        for row in cursor.fetchall()
    ]

    return {
        "average_review_score": (
            round(
                float(row["avg_score"]),
                3,
            )
            if row["avg_score"] is not None
            else None
        ),

        "total_reviews": int(
            row["total"] or 0
        ),

        "score_distribution": distribution,

        "lowest_rated_categories":
            worst_categories,
    }