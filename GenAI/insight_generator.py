"""
insight_generator.py
=====================
Automatically scans sales, customers, products, delivery, and reviews
for notable patterns, then asks Claude to turn each flagged pattern
into a plain-English insight + recommendation.

Design principle — detection is rule-based, narrative is LLM-based:
----------------------------------------------------------------------
"Automatic insight generation" from an LLM alone tends to hallucinate
trends. Instead, this script uses simple, transparent statistical rules
(month-over-month % change, top/bottom-N, threshold checks) to DETECT
candidate insights deterministically in pandas, then hands each
detected fact to Claude only to phrase it and suggest a recommendation.

Run:
    python insight_generator.py --data-dir /path/to/csvs
"""

import sys
import argparse
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "EDA"))
import etl_pipeline  # noqa: E402
import eda_analysis  # noqa: E402
from genai_client import ask_claude  # noqa: E402

SYSTEM_PROMPT = """You are a business intelligence analyst. You will be given ONE
detected data pattern (already computed — treat the numbers as ground truth).
Write: (1) a one-sentence plain-English insight, (2) 1-2 plausible business reasons,
(3) one concrete recommendation. Maximum 60 words total."""


def detect_patterns(clean: dict, order_value: pd.DataFrame) -> list:
    """Returns a list of {area, fact} dicts — deterministic, no LLM involved."""
    facts = []

    # Sales: biggest month-over-month revenue drop
    delivered = order_value[order_value["order_status"] == "delivered"].copy()
    delivered["month"] = delivered["order_purchase_timestamp"].dt.to_period("M")
    monthly = delivered.groupby("month")["order_total"].sum()
    monthly = monthly[monthly.index >= monthly.index[2]]  # skip noisy launch months
    pct_change = monthly.pct_change() * 100
    if len(pct_change.dropna()) > 0:
        worst_month = pct_change.idxmin()
        facts.append({
            "area": "sales",
            "fact": f"Revenue in {worst_month} was {pct_change[worst_month]:.1f}% vs the prior month "
                    f"(R${monthly[worst_month]:,.2f} vs R${monthly.shift(1)[worst_month]:,.2f})."
        })

    # Products: category with lowest average review score (min 30 reviews)
    items_cat = clean["order_items"].merge(
        clean["products"][["product_id", "product_category_name"]], on="product_id"
    )
    reviews = clean["order_reviews"][["order_id", "review_score"]]
    cat_reviews = items_cat.merge(reviews, on="order_id").dropna(subset=["product_category_name"])
    cat_stats = cat_reviews.groupby("product_category_name")["review_score"].agg(["mean", "count"])
    cat_stats = cat_stats[cat_stats["count"] >= 30]
    if not cat_stats.empty:
        worst_cat = cat_stats["mean"].idxmin()
        facts.append({
            "area": "product_satisfaction",
            "fact": f"Category '{worst_cat}' has the lowest average review score among categories "
                    f"with 30+ reviews: {cat_stats.loc[worst_cat, 'mean']:.2f}/5 "
                    f"across {int(cat_stats.loc[worst_cat, 'count'])} reviews."
        })

    # Delivery: state with highest late-delivery rate (min 100 delivered orders)
    orders = clean["orders"].merge(clean["customers"][["customer_id", "customer_state"]], on="customer_id")
    delivered_orders = orders[orders["order_status"] == "delivered"].dropna(subset=["order_delivered_customer_date"])
    delivered_orders = delivered_orders.copy()
    delivered_orders["late"] = (
        delivered_orders["order_delivered_customer_date"] > delivered_orders["order_estimated_delivery_date"]
    )
    state_stats = delivered_orders.groupby("customer_state").agg(
        late_rate=("late", "mean"), n=("order_id", "count")
    )
    state_stats = state_stats[state_stats["n"] >= 100]
    if not state_stats.empty:
        worst_state = state_stats["late_rate"].idxmax()
        facts.append({
            "area": "delivery",
            "fact": f"State '{worst_state}' has the highest late-delivery rate among states with "
                    f"100+ delivered orders: {state_stats.loc[worst_state, 'late_rate']*100:.1f}% "
                    f"(n={int(state_stats.loc[worst_state, 'n'])})."
        })

    # Payments: installment count most correlated with higher order value
    pay = clean["order_payments"]
    installment_value = pay.groupby("payment_installments")["payment_value"].mean()
    installment_value = installment_value[pay["payment_installments"].value_counts().reindex(
        installment_value.index).fillna(0) >= 50]
    if not installment_value.empty:
        top_installment = installment_value.idxmax()
        facts.append({
            "area": "payments",
            "fact": f"Orders paid in {top_installment} installments have the highest average payment "
                    f"value among installment counts used 50+ times: R${installment_value[top_installment]:,.2f}."
        })

    return facts


def generate_insights(data_dir: str) -> list:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)
    order_value = eda_analysis.build_order_value_table(clean)

    facts = detect_patterns(clean, order_value)
    insights = []
    for f in facts:
        narrative = ask_claude(SYSTEM_PROMPT, f"Area: {f['area']}\nDetected fact: {f['fact']}", max_tokens=200)
        insights.append({**f, "narrative": narrative})
    return insights


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    for ins in generate_insights(args.data_dir):
        print(f"\n[{ins['area'].upper()}]")
        print(f"Fact: {ins['fact']}")
        print(f"Insight: {ins['narrative']}")
