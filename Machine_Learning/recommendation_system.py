"""
recommendation_system.py
=========================
Product recommendation using item-based co-occurrence ("customers who
bought this also bought...") with a category-popularity fallback.

Why not classic collaborative filtering (user-item matrix factorization)?
---------------------------------------------------------------------------
Collaborative filtering needs users with MULTIPLE interactions to learn
taste patterns. In this dataset ~97% of customers buy exactly once, so
a user-item matrix would be almost entirely one interaction per row —
there's no repeat-purchase signal to factorize. Item-based co-occurrence
sidesteps this: it only needs orders with 2+ different products, which
exist independent of whether the CUSTOMER ever returns.

Two recommenders are built:
  1. get_similar_products(product_id): "customers who bought X also
     bought Y", ranked by co-occurrence count.
  2. get_popular_in_category(category): fallback for products with no
     co-purchase history (cold start), ranked by revenue.

NEW: this version also saves a full recommendations TABLE to CSV
(top N most-purchased products x their top 3 recommendations each),
suitable for importing into Power BI as a browsable table visual —
unlike the single-product terminal demo, this gives you a chart-ready
dataset covering many products at once.

Run:
    python recommendation_system.py --data-dir /path/to/csvs --product-id <id>
    python recommendation_system.py --data-dir /path/to/csvs --top-n-products 20 --out-dir ./ml_output
"""

import argparse
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import joblib
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
import etl_pipeline # noqa: E402


def build_co_occurrence(order_items: pd.DataFrame) -> Counter:
    co_occurrence = Counter()
    for _, group in order_items.groupby("order_id")["product_id"]:
        products = group.unique()
        if len(products) < 2:
            continue
        for a, b in combinations(sorted(products), 2):
            co_occurrence[(a, b)] += 1
    return co_occurrence


def get_similar_products(product_id: str, co_occurrence: Counter, top_n: int = 5) -> list:
    scores = Counter()
    for (a, b), count in co_occurrence.items():
        if a == product_id:
            scores[b] += count
        elif b == product_id:
            scores[a] += count
    return scores.most_common(top_n)


def get_popular_in_category(category: str, clean: dict, top_n: int = 5) -> pd.DataFrame:
    items = clean["order_items"].merge(
        clean["products"][["product_id", "product_category_name"]], on="product_id"
    )
    cat_items = items[items["product_category_name"] == category]
    popularity = cat_items.groupby("product_id").agg(
        total_revenue=("price", "sum"), times_purchased=("order_id", "nunique")
    ).sort_values("total_revenue", ascending=False)
    return popularity.head(top_n)


def recommend(product_id: str, co_occurrence: Counter, clean: dict, top_n: int = 5) -> dict:
    similar = get_similar_products(product_id, co_occurrence, top_n)
    result = {"product_id": product_id, "method": "co_occurrence", "recommendations": similar}

    if not similar:
        prod_row = clean["products"][clean["products"]["product_id"] == product_id]
        if not prod_row.empty and pd.notna(prod_row.iloc[0]["product_category_name"]):
            category = prod_row.iloc[0]["product_category_name"]
            fallback = get_popular_in_category(category, clean, top_n)
            result = {
                "product_id": product_id,
                "method": "category_popularity_fallback",
                "category": category,
                "recommendations": list(fallback.itertuples(index=True, name=None)),
            }
    return result


def build_recommendations_table(co_occurrence: Counter, clean: dict, top_n_products: int = 20,
                                 recs_per_product: int = 3) -> pd.DataFrame:
    """
    Builds a flat table: for each of the top_n_products most-purchased
    products, list its top recs_per_product recommended products.
    This is the shape Power BI wants — one row per (source, recommendation)
    pair, so it can be filtered/browsed as a table visual.
    """
    items = clean["order_items"]
    products = clean["products"][["product_id", "product_category_name"]]

    top_products = (
        items.groupby("product_id")["order_id"].nunique()
        .sort_values(ascending=False)
        .head(top_n_products)
        .index.tolist()
    )

    rows = []
    for pid in top_products:
        result = recommend(pid, co_occurrence, clean, top_n=recs_per_product)
        source_cat = products.loc[products["product_id"] == pid, "product_category_name"]
        source_cat = source_cat.iloc[0] if not source_cat.empty else "unknown"

        for rec in result["recommendations"]:
            rec_id, score = rec[0], rec[-1]  # works for both co-occurrence tuples and fallback rows
            rec_cat = products.loc[products["product_id"] == rec_id, "product_category_name"]
            rec_cat = rec_cat.iloc[0] if not rec_cat.empty else "unknown"
            rows.append({
                "source_product_id": pid,
                "source_category": source_cat,
                "recommended_product_id": rec_id,
                "recommended_category": rec_cat,
                "method": result["method"],
                "score": score,
            })

    return pd.DataFrame(rows)


def run(data_dir: str, product_id: str = None, out_dir: str = None,
        top_n_products: int = 20) -> dict:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)

    co_occurrence = build_co_occurrence(clean["order_items"])
    print(f"Built co-occurrence table: {len(co_occurrence)} product pairs "
          f"from {clean['order_items']['order_id'].nunique()} orders")

    if product_id is None:
        pair_counts = Counter()
        for (a, b), c in co_occurrence.items():
            pair_counts[a] += c
            pair_counts[b] += c
        product_id = pair_counts.most_common(1)[0][0]
        print(f"No --product-id given, demoing with most co-purchased product: {product_id}")

    result = recommend(product_id, co_occurrence, clean)
    print(f"\nMethod: {result['method']}")
    print(f"Recommendations for {product_id}:")
    for rec in result["recommendations"]:
        print(" ", rec)

    if out_dir:
        table = build_recommendations_table(co_occurrence, clean, top_n_products=top_n_products)
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        table.to_csv(out_path / "recommendations_table.csv", index=False)
        print(f"\nSaved full recommendations table ({len(table)} rows, "
              f"top {top_n_products} products) to {out_path / 'recommendations_table.csv'}")

        # --- Model persistence (additive; does not affect CSV output above) ---
        model_dir = out_path / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(co_occurrence, model_dir / "co_occurrence.joblib")
        print(f"Saved co-occurrence table to {model_dir / 'co_occurrence.joblib'}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--product-id", default=None)
    parser.add_argument("--out-dir", default=None,
                         help="If set, saves recommendations_table.csv here for Power BI import")
    parser.add_argument("--top-n-products", type=int, default=20,
                         help="How many top-selling products to build a rec table for")
    args = parser.parse_args()
    run(args.data_dir, args.product_id, args.out_dir, args.top_n_products)