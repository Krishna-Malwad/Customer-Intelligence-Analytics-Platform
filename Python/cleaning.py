"""
cleaning.py
===========
Pure pandas cleaning functions — one per table. Each function takes the
raw DataFrame (as read straight from CSV) and returns a cleaned
DataFrame ready to load into the production MySQL tables.

These mirror the exact same cleaning decisions made in SQL/validation.sql,
so the SQL-only path and the Python-automation path produce the same
result. That consistency is the point: ETL logic should not depend on
which tool executes it.

Design pattern used throughout:
  1. Drop rows missing a required (non-nullable) field.
  2. Deduplicate on the table's primary key.
  3. Cast to correct dtypes.
  4. Return the cleaned frame — never mutate the input in place.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _log_drop(name: str, before: int, after: int) -> None:
    dropped = before - after
    if dropped:
        logger.info("%s: dropped %d rows (%d -> %d)", name, dropped, before, after)


def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["customer_id", "customer_zip_code_prefix"])
    df = df.drop_duplicates(subset=["customer_id"], keep="first")
    df["customer_zip_code_prefix"] = pd.to_numeric(
        df["customer_zip_code_prefix"], errors="coerce"
    )
    df = df.dropna(subset=["customer_zip_code_prefix"])
    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(int)
    df["customer_city"] = df["customer_city"].str.strip()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    _log_drop("customers", before, len(df))
    return df.reset_index(drop=True)


def clean_sellers(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["seller_id", "seller_zip_code_prefix"])
    df = df.drop_duplicates(subset=["seller_id"], keep="first")
    df["seller_zip_code_prefix"] = pd.to_numeric(
        df["seller_zip_code_prefix"], errors="coerce"
    )
    df = df.dropna(subset=["seller_zip_code_prefix"])
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(int)
    df["seller_city"] = df["seller_city"].str.strip()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    _log_drop("sellers", before, len(df))
    return df.reset_index(drop=True)


def clean_category_translation(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["product_category_name", "product_category_name_english"])
    df = df.drop_duplicates(subset=["product_category_name"], keep="first")
    _log_drop("product_category_translation", before, len(df))
    return df.reset_index(drop=True)


def clean_products(df: pd.DataFrame, valid_categories: set) -> pd.DataFrame:
    """
    valid_categories: the set of category names that exist in the
    (already-cleaned) product_category_translation table. Categories
    not in this set are set to NULL rather than dropping the product —
    we still want the product row, just without a category label.
    """
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["product_id"])
    df = df.drop_duplicates(subset=["product_id"], keep="first")

    df["product_category_name"] = df["product_category_name"].where(
        df["product_category_name"].isin(valid_categories), np.nan
    )

    numeric_cols = [
        "product_name_lenght", "product_description_lenght", "product_photos_qty",
        "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    _log_drop("products", before, len(df))
    return df.reset_index(drop=True)


def clean_geolocation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Raw geolocation has ~26% fully duplicate rows and no natural key.
    Strategy: aggregate to ONE row per zip prefix — average lat/lng,
    and the most frequent (city, state) pair for that zip.
    """
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"])
    df["geolocation_zip_code_prefix"] = pd.to_numeric(
        df["geolocation_zip_code_prefix"], errors="coerce"
    )
    df = df.dropna(subset=["geolocation_zip_code_prefix"])
    df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].astype(int)

    avg_coords = df.groupby("geolocation_zip_code_prefix")[
        ["geolocation_lat", "geolocation_lng"]
    ].mean()

    mode_city_state = (
        df.groupby("geolocation_zip_code_prefix")[["geolocation_city", "geolocation_state"]]
        .agg(lambda s: s.value_counts().idxmax())
    )

    result = avg_coords.join(mode_city_state).reset_index()
    _log_drop("geolocation (raw rows -> unique zip prefixes)", before, len(result))
    return result


def clean_orders(df: pd.DataFrame, valid_customer_ids: set) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["order_id", "customer_id", "order_purchase_timestamp",
                            "order_estimated_delivery_date"])
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    df = df[df["customer_id"].isin(valid_customer_ids)]

    date_cols = [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Business rule: a delivered date can never be before the purchase date.
    impossible = df["order_delivered_customer_date"] < df["order_purchase_timestamp"]
    if impossible.any():
        logger.warning("orders: %d rows have delivery date before purchase date — nulling delivery date",
                        impossible.sum())
        df.loc[impossible, "order_delivered_customer_date"] = pd.NaT

    _log_drop("orders", before, len(df))
    return df.reset_index(drop=True)


def clean_order_items(df: pd.DataFrame, valid_order_ids: set,
                       valid_product_ids: set, valid_seller_ids: set) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["order_id", "order_item_id", "product_id", "seller_id"])
    df = df.drop_duplicates(subset=["order_id", "order_item_id"], keep="first")

    df = df[
        df["order_id"].isin(valid_order_ids)
        & df["product_id"].isin(valid_product_ids)
        & df["seller_id"].isin(valid_seller_ids)
    ]

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")
    df = df[(df["price"] >= 0) & (df["freight_value"] >= 0)]
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")

    _log_drop("order_items", before, len(df))
    return df.reset_index(drop=True)


def clean_order_payments(df: pd.DataFrame, valid_order_ids: set) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["order_id", "payment_sequential", "payment_type"])
    df = df.drop_duplicates(subset=["order_id", "payment_sequential"], keep="first")
    df = df[df["order_id"].isin(valid_order_ids)]

    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce")
    df = df[df["payment_value"] >= 0]
    df["payment_installments"] = pd.to_numeric(
        df["payment_installments"], errors="coerce"
    ).fillna(0).astype(int)

    _log_drop("order_payments", before, len(df))
    return df.reset_index(drop=True)


def clean_order_reviews(df: pd.DataFrame, valid_order_ids: set) -> pd.DataFrame:
    before = len(df)
    df = df.copy()
    df = df.dropna(subset=["review_id", "order_id", "review_score"])
    # Fully duplicate rows collapse; near-duplicates are kept (surrogate PK
    # in the DB schema handles that — see schema.sql design note #3).
    df = df.drop_duplicates(keep="first")
    df = df[df["order_id"].isin(valid_order_ids)]

    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    df = df[df["review_score"].between(1, 5)]
    df["review_score"] = df["review_score"].astype(int)

    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    df = df.dropna(subset=["review_creation_date", "review_answer_timestamp"])

    df["review_comment_title"] = df["review_comment_title"].replace("", np.nan)
    df["review_comment_message"] = df["review_comment_message"].replace("", np.nan)

    _log_drop("order_reviews", before, len(df))
    return df.reset_index(drop=True)
