"""
retention_model.py
===================
Binary classification: will this customer place a SECOND order?
(i.e. become a repeat customer, based on signals available from/near
their first order).

Class imbalance warning (teach this explicitly):
-------------------------------------------------
Only ~3.1% of customers in this dataset are repeat buyers. A model that
always predicts "will NOT repeat" is already ~97% accurate — and
completely useless. This is why we use class_weight='balanced' and
report ROC-AUC/precision/recall instead of plain accuracy.

NEW: this version also saves each test-set customer's PREDICTED
PROBABILITY of repeat purchase to CSV, alongside their actual outcome
and key features (state, category, order value) — suitable for a
Power BI chart showing predicted retention likelihood by segment.

Run:
    python retention_model.py --data-dir /path/to/csvs --out-dir ./ml_output
"""

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, classification_report

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "EDA"))
import etl_pipeline  # noqa: E402
import eda_analysis  # noqa: E402


def build_retention_table(clean: dict, order_value: pd.DataFrame) -> pd.DataFrame:
    delivered = order_value[order_value["order_status"] == "delivered"].dropna(subset=["order_total"])
    delivered = delivered.merge(
        clean["customers"][["customer_id", "customer_unique_id", "customer_state"]],
        on="customer_id", how="left"
    )

    delivered = delivered.sort_values("order_purchase_timestamp")
    first_orders = delivered.drop_duplicates(subset=["customer_unique_id"], keep="first").copy()

    order_counts = delivered.groupby("customer_unique_id")["order_id"].nunique()
    first_orders["target_repeat"] = first_orders["customer_unique_id"].map(
        lambda cu: 1 if order_counts.get(cu, 0) > 1 else 0
    )

    pay = clean["order_payments"].groupby("order_id").agg(
        payment_installments=("payment_installments", "max"),
        primary_payment_type=("payment_type", lambda s: s.mode().iat[0]),
    ).reset_index()

    items_cat = clean["order_items"].merge(
        clean["products"][["product_id", "product_category_name"]], on="product_id"
    )
    top_category = (
        items_cat.groupby("order_id")["product_category_name"]
        .agg(lambda s: s.mode().iat[0] if not s.mode().empty else "unknown")
        .reset_index()
    )

    reviews = clean["order_reviews"].groupby("order_id")["review_score"].mean().reset_index()

    df = first_orders.merge(pay, on="order_id", how="left")
    df = df.merge(top_category, on="order_id", how="left")
    df = df.merge(reviews, on="order_id", how="left")

    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    df["primary_payment_type"] = df["primary_payment_type"].fillna("unknown")
    df["review_score"] = df["review_score"].fillna(df["review_score"].median())
    df["payment_installments"] = df["payment_installments"].fillna(1)

    return df


def train_model(df: pd.DataFrame):
    feature_cols_num = ["order_total", "n_items", "payment_installments", "review_score"]
    feature_cols_cat = ["product_category_name", "primary_payment_type", "customer_state"]

    X = df[feature_cols_num + feature_cols_cat]
    y = df["target_repeat"]

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index, test_size=0.2, random_state=42, stratify=y
    )

    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), feature_cols_cat),
        ("num", StandardScaler(), feature_cols_num),
    ])

    models = {
        "logistic_regression": LogisticRegression(max_iter=3000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=8, class_weight="balanced", random_state=42, n_jobs=-1
        ),
    }

    results = {}
    probas = {}
    for name, estimator in models.items():
        pipe = Pipeline([("prep", preprocess), ("model", estimator)])
        pipe.fit(X_train, y_train)
        proba = pipe.predict_proba(X_test)[:, 1]
        preds = pipe.predict(X_test)
        results[name] = {
            "pipeline": pipe,
            "auc": round(roc_auc_score(y_test, proba), 4),
            "report": classification_report(y_test, preds, zero_division=0),
        }
        probas[name] = proba

    return results, (X_test, y_test, idx_test), probas


def run(data_dir: str, out_dir: str) -> dict:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)
    order_value = eda_analysis.build_order_value_table(clean)

    df = build_retention_table(clean, order_value)
    print(f"\nBase rate (repeat customers): {df['target_repeat'].mean()*100:.2f}%  "
          f"({df['target_repeat'].sum()} / {len(df)})")

    results, (X_test, y_test, idx_test), probas = train_model(df)
    for name, r in results.items():
        print(f"\n{name}: ROC-AUC={r['auc']}")
        print(r["report"])

    best_name = max(results, key=lambda k: results[k]["auc"])
    print(f"\nBest model: {best_name} (highest ROC-AUC)")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path / "retention_feature_table.csv", index=False)

    # Save predicted repeat-probability per test customer, for Power BI
    pred_df = pd.DataFrame({
        "order_id": df.loc[idx_test, "order_id"].values,
        "customer_state": df.loc[idx_test, "customer_state"].values,
        "product_category_name": df.loc[idx_test, "product_category_name"].values,
        "order_total": df.loc[idx_test, "order_total"].values,
        "review_score": df.loc[idx_test, "review_score"].values,
        "actual_repeat": y_test.values,
        "predicted_repeat_probability": probas[best_name],
    })
    pred_df.to_csv(out_path / "retention_predictions.csv", index=False)
    print(f"Saved {len(pred_df)} prediction rows (model: {best_name}) to "
          f"{out_path / 'retention_predictions.csv'}")

    # --- Model persistence (additive; does not affect CSV outputs/metrics above) ---
    model_dir = out_path / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(results[best_name]["pipeline"], model_dir / "retention_model.joblib")
    print(f"Saved retention model ({best_name}) to {model_dir / 'retention_model.joblib'}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", default="./ml_output")
    args = parser.parse_args()
    run(args.data_dir, args.out_dir)