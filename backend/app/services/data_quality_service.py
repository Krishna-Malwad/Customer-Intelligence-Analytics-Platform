"""
services/data_quality_service.py
==================================
Lightweight, real data-quality checks against the live database.
Deliberately simple per the spec ("do not overengineer") — each check
is one SQL query, returning an actual count of affected rows.
"""


def _check(name, status, affected_rows, severity, message):
    return {"check": name, "status": status, "affected_rows": affected_rows,
            "severity": severity, "message": message}


def run_all_checks(cursor) -> dict:
    checks = []

    # 1. Null customer_id in orders (should never happen due to FK, but verify)
    cursor.execute("SELECT COUNT(*) AS n FROM orders WHERE customer_id IS NULL")
    n = cursor.fetchone()["n"]
    checks.append(_check("orders.customer_id not null", "pass" if n == 0 else "fail", n,
                          "high", "Every order must reference a customer."))

    # 2. Duplicate order_id (should be impossible — PK — but verify)
    cursor.execute("SELECT COUNT(*) - COUNT(DISTINCT order_id) AS n FROM orders")
    n = cursor.fetchone()["n"]
    checks.append(_check("orders.order_id uniqueness", "pass" if n == 0 else "fail", n,
                          "high", "order_id should be unique (primary key)."))

    # 3. Invalid dates: delivered before purchased
    cursor.execute("""
        SELECT COUNT(*) AS n FROM orders
        WHERE order_delivered_customer_date IS NOT NULL
          AND order_delivered_customer_date < order_purchase_timestamp
    """)
    n = cursor.fetchone()["n"]
    checks.append(_check("delivery date >= purchase date", "pass" if n == 0 else "fail", n,
                          "medium", "A delivery date earlier than the purchase date is logically impossible."))

    # 4. Invalid numeric values: negative price/freight
    cursor.execute("SELECT COUNT(*) AS n FROM order_items WHERE price < 0 OR freight_value < 0")
    n = cursor.fetchone()["n"]
    checks.append(_check("order_items non-negative price/freight", "pass" if n == 0 else "fail", n,
                          "high", "Prices and freight values must not be negative."))

    # 5. Invalid review scores (should be 1-5)
    cursor.execute("SELECT COUNT(*) AS n FROM order_reviews WHERE review_score NOT BETWEEN 1 AND 5")
    n = cursor.fetchone()["n"]
    checks.append(_check("review_score in range 1-5", "pass" if n == 0 else "fail", n,
                          "medium", "Review scores must be between 1 and 5."))

    # 6. Orphan order_items (order_id not present in orders)
    cursor.execute("""
        SELECT COUNT(*) AS n FROM order_items oi
        LEFT JOIN orders o ON oi.order_id = o.order_id
        WHERE o.order_id IS NULL
    """)
    n = cursor.fetchone()["n"]
    checks.append(_check("order_items -> orders referential integrity", "pass" if n == 0 else "fail", n,
                          "high", "Every order_item must belong to an existing order."))

    # 7. Orphan orders (customer_id not present in customers)
    cursor.execute("""
        SELECT COUNT(*) AS n FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """)
    n = cursor.fetchone()["n"]
    checks.append(_check("orders -> customers referential integrity", "pass" if n == 0 else "fail", n,
                          "high", "Every order must belong to an existing customer."))

    # 8. Unexpected row-count sanity (basic non-empty check, not a historical trend)
    cursor.execute("SELECT COUNT(*) AS n FROM orders")
    n = cursor.fetchone()["n"]
    checks.append(_check("orders table non-empty", "pass" if n > 0 else "fail", 0 if n > 0 else 1,
                          "high", f"orders table currently has {n} rows."))

    # 9. Invalid order_status values (should be one of a known set)
    valid_statuses = {"delivered", "shipped", "canceled", "unavailable", "invoiced",
                       "processing", "created", "approved"}
    cursor.execute("SELECT DISTINCT order_status FROM orders")
    found = {r["order_status"] for r in cursor.fetchall()}
    unexpected = found - valid_statuses
    checks.append(_check("order_status values within known set", "pass" if not unexpected else "warn",
                          len(unexpected), "low",
                          f"Unexpected status values found: {sorted(unexpected)}" if unexpected else "All statuses recognized."))

    overall = "healthy" if all(c["status"] == "pass" for c in checks) else \
              ("degraded" if any(c["status"] == "fail" and c["severity"] == "high" for c in checks) else "warning")

    return {"status": overall, "checks": checks}
