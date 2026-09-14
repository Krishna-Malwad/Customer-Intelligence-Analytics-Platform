"""
eda_analysis.py
================
Exploratory Data Analysis on the CLEANED tables (reuses etl_pipeline's
extract+transform so the numbers here match exactly what gets loaded
into MySQL). Produces the metrics requested in Phase 4:

    Customer Intelligence | Sales | Orders | Payments | Reviews

Run:
    python eda_analysis.py --data-dir /path/to/csvs --out-dir ./eda_output
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
import etl_pipeline  # noqa: E402


def build_order_value_table(clean: dict) -> pd.DataFrame:
    """One row per order_id with total item value + freight (the 'order total')."""
    items = clean["order_items"]
    order_totals = items.groupby("order_id").agg(
        item_revenue=("price", "sum"),
        freight_total=("freight_value", "sum"),
        n_items=("order_item_id", "count"),
    ).reset_index()
    order_totals["order_total"] = order_totals["item_revenue"] + order_totals["freight_total"]
    orders = clean["orders"][["order_id", "customer_id", "order_status",
                               "order_purchase_timestamp", "order_delivered_customer_date",
                               "order_estimated_delivery_date"]]
    return orders.merge(order_totals, on="order_id", how="left")


def customer_intelligence(clean: dict, order_value: pd.DataFrame) -> dict:
    customers = clean["customers"]
    out = {}
    out["total_customers"] = customers["customer_unique_id"].nunique()
    out["total_customer_rows"] = len(customers)

    out["customers_by_state"] = (
        customers.groupby("customer_state")["customer_unique_id"]
        .nunique().sort_values(ascending=False)
    )

    ov = order_value.merge(
        customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left"
    )
    orders_per_customer = ov.groupby("customer_unique_id")["order_id"].nunique()
    out["repeat_customers"] = int((orders_per_customer > 1).sum())
    out["one_time_customers"] = int((orders_per_customer == 1).sum())
    out["repeat_customer_rate_pct"] = round(
        100 * out["repeat_customers"] / out["total_customers"], 2
    )
    out["avg_orders_per_customer"] = round(orders_per_customer.mean(), 3)
    return out


def sales_analysis(order_value: pd.DataFrame, clean: dict) -> dict:
    delivered = order_value[order_value["order_status"] == "delivered"].copy()
    out = {}
    out["total_revenue"] = round(delivered["order_total"].sum(), 2)
    out["total_orders_delivered"] = delivered["order_id"].nunique()
    out["average_order_value"] = round(delivered["order_total"].mean(), 2)

    delivered["month"] = delivered["order_purchase_timestamp"].dt.to_period("M")
    out["monthly_revenue"] = delivered.groupby("month")["order_total"].sum().round(2)

    items = clean["order_items"].merge(clean["orders"][["order_id", "order_status"]], on="order_id")
    items = items[items["order_status"] == "delivered"]
    prod_rev = items.groupby("product_id")["price"].sum().sort_values(ascending=False)
    out["top_10_products_by_revenue"] = prod_rev.head(10)

    prod_cat = items.merge(clean["products"][["product_id", "product_category_name"]], on="product_id")
    cat_rev = prod_cat.groupby("product_category_name")["price"].sum().sort_values(ascending=False)
    out["top_10_categories_by_revenue"] = cat_rev.head(10)
    return out


def order_analysis(clean: dict) -> dict:
    orders = clean["orders"]
    out = {}
    out["status_breakdown"] = orders["order_status"].value_counts()

    delivered = orders[orders["order_status"] == "delivered"].dropna(
        subset=["order_delivered_customer_date"]
    ).copy()
    delivered["delivery_days"] = (
        delivered["order_delivered_customer_date"] - delivered["order_purchase_timestamp"]
    ).dt.days
    out["avg_delivery_days"] = round(delivered["delivery_days"].mean(), 2)
    out["median_delivery_days"] = round(delivered["delivery_days"].median(), 2)

    late = delivered[
        delivered["order_delivered_customer_date"] > delivered["order_estimated_delivery_date"]
    ]
    out["late_deliveries_count"] = len(late)
    out["late_delivery_rate_pct"] = round(100 * len(late) / len(delivered), 2)
    return out


def payment_analysis(clean: dict) -> dict:
    pay = clean["order_payments"]
    out = {}
    out["payment_type_counts"] = pay["payment_type"].value_counts()
    out["revenue_by_payment_type"] = (
        pay.groupby("payment_type")["payment_value"].sum().sort_values(ascending=False).round(2)
    )
    out["installment_distribution"] = pay["payment_installments"].value_counts().sort_index()
    out["avg_installments"] = round(pay["payment_installments"].mean(), 2)
    return out


def review_analysis(clean: dict) -> dict:
    rev = clean["order_reviews"]
    out = {}
    out["avg_review_score"] = round(rev["review_score"].mean(), 3)
    out["score_distribution"] = rev["review_score"].value_counts().sort_index()
    out["pct_5_star"] = round(100 * (rev["review_score"] == 5).mean(), 2)
    out["pct_1_2_star"] = round(100 * (rev["review_score"] <= 2).mean(), 2)
    return out


def print_section(title: str, d: dict) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    for k, v in d.items():
        print(f"\n--- {k} ---")
        print(v)


def run(data_dir: str, out_dir: str) -> dict:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)
    order_value = build_order_value_table(clean)

    results = {
        "customer_intelligence": customer_intelligence(clean, order_value),
        "sales_analysis": sales_analysis(order_value, clean),
        "order_analysis": order_analysis(clean),
        "payment_analysis": payment_analysis(clean),
        "review_analysis": review_analysis(clean),
    }

    for title, d in results.items():
        print_section(title.replace("_", " ").upper(), d)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    order_value.to_csv(out_path / "order_value_table.csv", index=False)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Olist EDA")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", default="./eda_output")
    args = parser.parse_args()
    run(args.data_dir, args.out_dir)
