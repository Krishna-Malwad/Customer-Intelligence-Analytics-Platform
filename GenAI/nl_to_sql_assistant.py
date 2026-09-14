"""
nl_to_sql_assistant.py
=======================
Converts a natural-language business question into a SQL query against
the customer_intelligence schema, executes it, and explains the result.

Pipeline:
    question -> Claude (schema-aware prompt) -> {sql, explanation_intent}
             -> execute SQL against MySQL -> Claude explains the actual
                result rows in plain English

Safety note: this assistant is READ-ONLY. We reject any generated SQL
that isn't a SELECT statement before it ever reaches the database â€”
an LLM should never be trusted to run DDL/DML unsupervised.

Run:
    python nl_to_sql_assistant.py "Show top 10 customers by revenue"
"""

import sys
import argparse
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
from database_connection import get_cursor  # noqa: E402
from genai_client import ask_claude_json, ask_claude  # noqa: E402

SCHEMA_DESCRIPTION = """
Tables (MySQL, database customer_intelligence):

customers(customer_id PK, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
sellers(seller_id PK, seller_zip_code_prefix, seller_city, seller_state)
product_category_translation(product_category_name PK, product_category_name_english)
products(product_id PK, product_category_name FK->product_category_translation, product_weight_g, product_length_cm, product_height_cm, product_width_cm, ...)
geolocation(geolocation_zip_code_prefix PK, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state)
orders(order_id PK, customer_id FK->customers, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
order_items(order_id, order_item_id, PK(order_id,order_item_id), product_id FK->products, seller_id FK->sellers, shipping_limit_date, price, freight_value)
order_payments(order_id, payment_sequential, PK(order_id,payment_sequential), payment_type, payment_installments, payment_value)
order_reviews(review_pk PK auto_increment, review_id, order_id FK->orders, review_score 1-5, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp)

Revenue per order = SUM(order_items.price) for that order_id (freight_value is shipping cost, usually excluded from "revenue").
A customer's real identity across repeat purchases is customer_unique_id, NOT customer_id.
"""

SQL_SYSTEM_PROMPT = f"""You are a senior data analyst who writes MySQL queries for the
customer_intelligence e-commerce database. Given a business question, generate a single,
correct, read-only SQL query (SELECT only, no writes) that answers it.

Schema:
{SCHEMA_DESCRIPTION}

Return a JSON object with exactly these keys:
  "sql": the SQL query as a single string
  "reasoning": one sentence on why you wrote it this way (joins used, aggregation, etc.)
"""

EXPLAIN_SYSTEM_PROMPT = """You are a business analyst explaining query results to a
non-technical stakeholder. Be concise (3-5 sentences), lead with the headline number or
finding, and avoid restating the raw table row by row. All monetary values in the database are in Brazilian Real (BRL). Always use the currency symbol R$ for monetary values, never $ or USD."""


def generate_sql(question: str) -> dict:
    return ask_claude_json(SQL_SYSTEM_PROMPT, f"Question: {question}")


def is_safe_select(sql: str) -> bool:
    stripped = sql.strip().lower()
    if not stripped.startswith("select"):
        return False
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "create", ";--"]
    return not any(word in stripped for word in forbidden)


def execute_sql(sql: str, cursor=None) -> pd.DataFrame:
    """Execute a read-only SQL query.

    If a DB cursor is supplied (for example by FastAPI), use that injected
    connection. Otherwise, preserve the standalone CLI behavior by opening
    the project's normal MySQL connection.
    """
    if cursor is not None:
        cursor.execute(sql)
        rows = cursor.fetchall()
        if rows and isinstance(rows[0], dict):
            return pd.DataFrame(rows)
        cols = [desc[0] for desc in cursor.description] if cursor.description else []
        return pd.DataFrame(rows, columns=cols)

    with get_cursor(commit_on_success=False) as (conn, cursor):
        cursor.execute(sql)
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=cols)


def explain_result(question: str, df: pd.DataFrame) -> str:
    preview = df.head(20).to_csv(index=False)
    prompt = f"Original question: {question}\n\nQuery result (CSV, up to 20 rows shown):\n{preview}"
    return ask_claude(EXPLAIN_SYSTEM_PROMPT, prompt)


def run(question: str) -> dict:
    gen = generate_sql(question)
    sql = gen["sql"]
    print(f"Generated SQL:\n{sql}\n")
    print(f"Reasoning: {gen.get('reasoning', '')}\n")

    if not is_safe_select(sql):
        raise ValueError("Generated SQL failed the read-only safety check â€” refusing to execute.")

    df = execute_sql(sql)
    print(f"Result ({len(df)} rows):\n{df.head(10)}\n")

    explanation = explain_result(question, df)
    print(f"Explanation:\n{explanation}")

    return {"sql": sql, "result": df, "explanation": explanation}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Business question in plain English")
    args = parser.parse_args()
    run(args.question)
