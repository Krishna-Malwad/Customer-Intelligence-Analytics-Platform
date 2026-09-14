"""
etl_pipeline.py
================
Orchestrates the full Python ETL pipeline:

    CSV files -> pandas DataFrames -> cleaning.py -> validation.py
        -> mysql.connector (executemany) -> production MySQL tables

This is the automated equivalent of SQL/staging_tables.sql +
SQL/validation.sql, but driven from Python so it can be scheduled,
logged, unit-tested, and extended (e.g. add a new source, swap CSV for
an API pull) without touching SQL at all.

Run:
    python etl_pipeline.py --data-dir /path/to/csvs
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
import mysql.connector

import cleaning
import validation
from database_connection import get_cursor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("etl_pipeline")

FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def _find_file(data_dir: Path, suffix: str) -> Path:
    """
    The uploaded files are prefixed with a timestamp
    (e.g. '1786023047470_olist_customers_dataset.csv'), so we match by
    suffix rather than assuming an exact filename.
    """
    matches = list(data_dir.glob(f"*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"No file matching *{suffix} found in {data_dir}")
    return matches[0]


def extract(data_dir: Path) -> dict:
    """Read every CSV into a DataFrame. Returns {table_name: raw_df}."""
    logger.info("EXTRACT: reading CSVs from %s", data_dir)
    raw = {}
    for key, suffix in FILES.items():
        path = _find_file(data_dir, suffix)
        raw[key] = pd.read_csv(path)
        logger.info("  loaded %-22s %6d rows, %2d cols  (%s)",
                    key, *raw[key].shape, path.name)
    return raw


def transform(raw: dict) -> dict:
    """Apply cleaning.py functions in dependency order."""
    logger.info("TRANSFORM: cleaning each table")
    clean = {}

    clean["category_translation"] = cleaning.clean_category_translation(raw["category_translation"])
    clean["customers"] = cleaning.clean_customers(raw["customers"])
    clean["sellers"] = cleaning.clean_sellers(raw["sellers"])

    valid_categories = set(clean["category_translation"]["product_category_name"])
    clean["products"] = cleaning.clean_products(raw["products"], valid_categories)

    clean["geolocation"] = cleaning.clean_geolocation(raw["geolocation"])

    valid_customer_ids = set(clean["customers"]["customer_id"])
    clean["orders"] = cleaning.clean_orders(raw["orders"], valid_customer_ids)

    valid_order_ids = set(clean["orders"]["order_id"])
    valid_product_ids = set(clean["products"]["product_id"])
    valid_seller_ids = set(clean["sellers"]["seller_id"])
    clean["order_items"] = cleaning.clean_order_items(
        raw["order_items"], valid_order_ids, valid_product_ids, valid_seller_ids
    )
    clean["order_payments"] = cleaning.clean_order_payments(raw["order_payments"], valid_order_ids)
    clean["order_reviews"] = cleaning.clean_order_reviews(raw["order_reviews"], valid_order_ids)

    return clean


def validate(clean: dict) -> pd.DataFrame:
    """Run validation.py checks across all cleaned tables."""
    logger.info("VALIDATE: running data quality checks")
    checks = []
    checks.append(validation.check_unique_key(clean["customers"], ["customer_id"], "customers"))
    checks.append(validation.check_nulls(clean["customers"],
                                          ["customer_id", "customer_zip_code_prefix"], "customers"))

    checks.append(validation.check_unique_key(clean["orders"], ["order_id"], "orders"))
    checks.append(validation.check_referential_integrity(
        clean["orders"], "customer_id", set(clean["customers"]["customer_id"]), "orders"))

    checks.append(validation.check_unique_key(
        clean["order_items"], ["order_id", "order_item_id"], "order_items"))
    checks.append(validation.check_numeric_range(
        clean["order_items"], "price", min_val=0, table_name="order_items"))

    checks.append(validation.check_unique_key(
        clean["order_payments"], ["order_id", "payment_sequential"], "order_payments"))
    checks.append(validation.check_numeric_range(
        clean["order_payments"], "payment_value", min_val=0, table_name="order_payments"))

    checks.append(validation.check_numeric_range(
        clean["order_reviews"], "review_score", min_val=1, max_val=5, table_name="order_reviews"))
    checks.append(validation.check_date_order(
        clean["order_reviews"], "review_creation_date", "review_answer_timestamp", "order_reviews"))

    report = validation.run_report(checks)
    failed = report[~report["passed"]]
    if not failed.empty:
        logger.warning("VALIDATE: %d check(s) failed — review before loading:\n%s",
                        len(failed), failed.to_string(index=False))
    else:
        logger.info("VALIDATE: all checks passed")
    return report


def _executemany(cursor, sql: str, df: pd.DataFrame, cols: list, batch_size: int = 5000) -> int:
    records = [tuple(row) for row in df[cols].itertuples(index=False, name=None)]
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        cursor.executemany(sql, batch)
        total += len(batch)
    return total


def load(clean: dict) -> None:
    """Load cleaned DataFrames into MySQL production tables, in FK-safe order."""
    logger.info("LOAD: writing to MySQL")

    load_plan = [
        ("category_translation",
         "INSERT IGNORE INTO product_category_translation "
         "(product_category_name, product_category_name_english) VALUES (%s, %s)",
         ["product_category_name", "product_category_name_english"]),

        ("customers",
         "INSERT IGNORE INTO customers "
         "(customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state) "
         "VALUES (%s, %s, %s, %s, %s)",
         ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
          "customer_city", "customer_state"]),

        ("sellers",
         "INSERT IGNORE INTO sellers "
         "(seller_id, seller_zip_code_prefix, seller_city, seller_state) VALUES (%s, %s, %s, %s)",
         ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"]),

        ("products",
         "INSERT IGNORE INTO products "
         "(product_id, product_category_name, product_name_lenght, product_description_lenght, "
         "product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm) "
         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
         ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
          "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm",
          "product_width_cm"]),

        ("geolocation",
         "INSERT IGNORE INTO geolocation "
         "(geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state) "
         "VALUES (%s, %s, %s, %s, %s)",
         ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
          "geolocation_city", "geolocation_state"]),

        ("orders",
         "INSERT IGNORE INTO orders "
         "(order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, "
         "order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date) "
         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
         ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
          "order_delivered_carrier_date", "order_delivered_customer_date",
          "order_estimated_delivery_date"]),

        ("order_items",
         "INSERT IGNORE INTO order_items "
         "(order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value) "
         "VALUES (%s, %s, %s, %s, %s, %s, %s)",
         ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date",
          "price", "freight_value"]),

        ("order_payments",
         "INSERT IGNORE INTO order_payments "
         "(order_id, payment_sequential, payment_type, payment_installments, payment_value) "
         "VALUES (%s, %s, %s, %s, %s)",
         ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"]),

        ("order_reviews",
         "INSERT IGNORE INTO order_reviews "
         "(review_id, order_id, review_score, review_comment_title, review_comment_message, "
         "review_creation_date, review_answer_timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
         ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
          "review_creation_date", "review_answer_timestamp"]),
    ]

    try:
        with get_cursor() as (conn, cursor):
            for table_key, sql, cols in load_plan:
                df = clean[table_key].where(pd.notnull(clean[table_key]), None)
                n = _executemany(cursor, sql, df, cols)
                logger.info("  loaded %-22s %6d rows", table_key, n)
    except mysql.connector.Error as e:
        logger.error("LOAD failed, transaction rolled back: %s", e)
        raise


def run(data_dir: str, load_to_db: bool = True) -> dict:
    data_dir = Path(data_dir)
    raw = extract(data_dir)
    clean = transform(raw)
    report = validate(clean)
    if load_to_db:
        load(clean)
    else:
        logger.info("Skipping DB load (--no-load flag set)")
    return {"clean": clean, "validation_report": report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Olist Customer Intelligence ETL pipeline")
    parser.add_argument("--data-dir", required=True, help="Directory containing the Olist CSV files")
    parser.add_argument("--no-load", action="store_true", help="Run extract/transform/validate only, skip DB load")
    args = parser.parse_args()

    run(args.data_dir, load_to_db=not args.no_load)
