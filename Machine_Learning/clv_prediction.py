"""
clv_prediction.py
==================
Customer (order) value prediction using a regression model.

IMPORTANT HONEST FRAMING (teach this in interviews):
------------------------------------------------------
"True" CLV modeling (e.g. BG/NBD, Gamma-Gamma) requires enough repeat
transactions per customer to model purchase timing and drop-off
probabilistically. In this dataset, ~97% of customers buy exactly once,
so there isn't enough longitudinal signal per customer for a classic
probabilistic CLV model to be meaningfully better than a simple average.

Given that constraint, this script builds a more honest and still useful
model: predict a customer's MONETARY VALUE from features known at/near
their first purchase (product category, payment method, installments,
delivery region, review outcome).

NEW: this version also saves actual-vs-predicted values to CSV (for the
test set), suitable for a Power BI scatter chart comparing predicted vs
real order values — a standard way to visually communicate model quality
to a non-technical audience (points near the diagonal = accurate).

Run:
    python clv_prediction.py --data-dir /path/to/csvs --out-dir ./ml_output
"""

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "EDA"))
import etl_pipeline  # noqa: E402
import eda_analysis  # noqa: E402


def build_feature_table(clean: dict, order_value: pd.DataFrame) -> pd.DataFrame:
    delivered = order_value[order_value["order_status"] == "delivered"].dropna(subset=["order_total"])

    pay = clean["order_payments"].groupby("order_id").agg(
        payment_installments=("payment_installments", "max"),
        n_payment_methods=("payment_type", "nunique"),
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
    customers = clean["customers"][["customer_id", "customer_state"]]

    df = delivered.merge(pay, on="order_id", how="left")
    df = df.merge(top_category, on="order_id", how="left")
    df = df.merge(reviews, on="order_id", how="left")
    df = df.merge(customers, on="customer_id", how="left")

    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    df["review_score"] = df["review_score"].fillna(df["review_score"].median())
    df["payment_installments"] = df["payment_installments"].fillna(1)
    df["n_payment_methods"] = df["n_payment_methods"].fillna(1)
    df["primary_payment_type"] = df["primary_payment_type"].fillna("unknown")

    return df


def train_model(df: pd.DataFrame):
    feature_cols_num = ["payment_installments", "n_payment_methods", "review_score", "n_items"]
    feature_cols_cat = ["product_category_name", "primary_payment_type", "customer_state"]
    target_col = "order_total"

    X = df[feature_cols_num + feature_cols_cat]
    y = df[target_col]

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index, test_size=0.2, random_state=42
    )

    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), feature_cols_cat),
    ], remainder="passthrough")

    models = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
    }

    results = {}
    predictions = {}
    for name, estimator in models.items():
        pipe = Pipeline([("prep", preprocess), ("model", estimator)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        results[name] = {
            "pipeline": pipe,
            "mae": round(mean_absolute_error(y_test, preds), 2),
            "r2": round(r2_score(y_test, preds), 4),
        }
        predictions[name] = preds

    return results, (X_test, y_test, idx_test), predictions


def run(data_dir: str, out_dir: str) -> dict:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)
    order_value = eda_analysis.build_order_value_table(clean)

    df = build_feature_table(clean, order_value)
    results, (X_test, y_test, idx_test), predictions = train_model(df)

    print(f"\nTarget: order_total | mean={y_test.mean():.2f}, std={y_test.std():.2f}")
    for name, r in results.items():
        print(f"\n{name}: MAE=R${r['mae']}  R2={r['r2']}")

    best_name = max(results, key=lambda k: results[k]["r2"])
    print(f"\nBest model: {best_name} (highest R2)")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path / "clv_feature_table.csv", index=False)

    # Save actual vs predicted for the BEST model, for a Power BI scatter chart
    pred_df = pd.DataFrame({
        "order_id": df.loc[idx_test, "order_id"].values,
        "actual_order_value": y_test.values,
        "predicted_order_value": predictions[best_name],
        "product_category_name": df.loc[idx_test, "product_category_name"].values,
        "customer_state": df.loc[idx_test, "customer_state"].values,
    })
    pred_df["absolute_error"] = (pred_df["actual_order_value"] - pred_df["predicted_order_value"]).abs()
    pred_df.to_csv(out_path / "clv_predictions.csv", index=False)
    print(f"Saved {len(pred_df)} actual-vs-predicted rows (model: {best_name}) to "
          f"{out_path / 'clv_predictions.csv'}")

    # --- Model persistence (additive; does not affect CSV outputs/metrics above) ---
    model_dir = out_path / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(results[best_name]["pipeline"], model_dir / "clv_model.joblib")
    print(f"Saved CLV model ({best_name}) to {model_dir / 'clv_model.joblib'}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", default="./ml_output")
    args = parser.parse_args()
    run(args.data_dir, args.out_dir)