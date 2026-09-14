"""
tests/test_api.py
===================
Covers all 13 required test scenarios. Run with:
    pytest tests/ -v
"""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database_status"] == "connected"
    assert "ml_models" in body
    assert "genai_configured" in body


def test_customer_360_found(client, sqlite_db_path):
    import sqlite3
    conn = sqlite3.connect(sqlite_db_path)
    cur = conn.cursor()
    cur.execute("SELECT customer_unique_id FROM customers LIMIT 1")
    real_id = cur.fetchone()[0]
    conn.close()

    r = client.get(f"/api/customers/{real_id}")
    assert r.status_code == 200
    body = r.json()
    assert "customer_unique_id" in body
    assert "rfm" in body
    assert "segment" in body
    assert "retention_prediction" in body
    assert "recommendations" in body


def test_customer_not_found(client):
    r = client.get("/api/customers/definitely_not_a_real_customer_id_999")
    assert r.status_code == 404


def test_ml_models_loaded(client):
    r = client.get("/api/health")
    status = r.json()["ml_models"]
    # All 4 should show "loaded" since we trained+saved them in this session
    for key in ["segmentation", "clv_pipeline", "retention_pipeline", "co_occurrence"]:
        assert status.get(key) == "loaded", f"{key} not loaded: {status.get(key)}"


def test_segmentation_prediction(client):
    r = client.post("/api/ml/segment-customer", json={"recency_days": 100, "frequency": 2, "monetary": 500})
    assert r.status_code == 200
    assert "segment_cluster" in r.json()


def test_retention_prediction(client):
    r = client.post("/api/ml/predict-retention", json={
        "order_total": 150.0, "n_items": 1, "payment_installments": 2,
        "review_score": 5.0, "product_category_name": "beleza_saude",
        "primary_payment_type": "credit_card", "customer_state": "SP",
    })
    assert r.status_code == 200
    proba = r.json()["repeat_purchase_probability"]
    assert 0.0 <= proba <= 1.0


def test_order_value_prediction(client):
    r = client.post("/api/ml/predict-order-value", json={
        "payment_installments": 3, "n_payment_methods": 1, "review_score": 5.0,
        "n_items": 1, "product_category_name": "beleza_saude",
        "primary_payment_type": "credit_card", "customer_state": "SP",
    })
    assert r.status_code == 200
    assert r.json()["predicted_order_value"] > 0


def test_recommendations_lookup(client):
    r = client.get("/api/ml/recommendations/0a0a92112bd4c708ca5fde585afaa872")
    assert r.status_code == 200
    assert "recommendations" in r.json()


def test_analytics_overview(client):
    r = client.get("/api/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_revenue"] > 0
    assert body["delivered_orders"] > 0


def test_analytics_all_endpoints_return_200(client):
    for endpoint in ["/api/analytics/revenue-trend", "/api/analytics/customers",
                      "/api/analytics/products", "/api/analytics/delivery",
                      "/api/analytics/satisfaction"]:
        r = client.get(endpoint)
        assert r.status_code == 200, f"{endpoint} failed: {r.text}"


def test_data_quality(client):
    r = client.get("/api/data-quality")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert len(body["checks"]) >= 5


def test_nl_to_sql_rejects_destructive_query():
    """Unit test of the safety guard itself — the critical security boundary.
    This does NOT call Gemini (no API key in this test environment);
    it tests the guard function directly, which is what actually matters."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "GenAI"))
    from nl_to_sql_assistant import is_safe_select

    assert is_safe_select("SELECT * FROM orders") is True
    for destructive in ["DROP TABLE orders", "DELETE FROM orders", "UPDATE orders SET x=1",
                         "INSERT INTO orders VALUES (1)", "ALTER TABLE orders ADD x INT",
                         "TRUNCATE TABLE orders", "CREATE TABLE evil (id INT)",
                         "GRANT ALL ON *.* TO x", "SELECT * FROM orders; DROP TABLE orders;"]:
        assert is_safe_select(destructive) is False, f"Failed to reject: {destructive}"


def test_nl_to_sql_execution_path_with_injected_cursor(monkeypatch, client):
    """Verify FastAPI uses the request-scoped DB cursor for generated SELECTs."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "GenAI"))
    import nl_to_sql_assistant as n2s

    monkeypatch.setattr(n2s, "generate_sql", lambda question: {
        "sql": "SELECT 1 AS answer",
        "reasoning": "Simple read-only smoke test",
    })
    monkeypatch.setattr(n2s, "explain_result", lambda question, df: "The query returned one row.")

    r = client.post("/api/genai/nl-to-sql", json={"question": "Return one row"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated_sql"] == "SELECT 1 AS answer"
    assert body["row_count"] == 1
    assert body["results"][0]["answer"] == 1
