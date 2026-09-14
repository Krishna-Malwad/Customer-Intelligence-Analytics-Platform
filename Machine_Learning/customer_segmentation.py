"""
customer_segmentation.py
=========================
Customer segmentation via RFM (Recency, Frequency, Monetary) features
+ KMeans clustering.

Why RFM?
--------
Recency, Frequency, and Monetary value are the three variables that
correlate most strongly with future purchase behavior in retail/e-comm.
It's a 40-year-old technique from direct-mail marketing that still
outperforms much fancier approaches for a first-pass segmentation,
precisely because it's built from ground-truth transaction data rather
than assumptions.

Note on this dataset: Olist's repeat-purchase rate is only ~3%, so most
customers will have Frequency=1. That's expected and still informative —
segmentation here mostly separates high-value one-time buyers from
low-value ones, plus isolates the small repeat-customer segment.

Run:
    python customer_segmentation.py --data-dir /path/to/csvs --k 4
"""

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "EDA"))
import etl_pipeline  # noqa: E402
import eda_analysis  # noqa: E402


def build_rfm(order_value: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    delivered = order_value[order_value["order_status"] == "delivered"].copy()
    delivered = delivered.merge(
        customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left"
    )

    snapshot_date = delivered["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

    rfm = delivered.groupby("customer_unique_id").agg(
        recency_days=("order_purchase_timestamp", lambda s: (snapshot_date - s.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("order_total", "sum"),
    ).reset_index()

    return rfm


def fit_kmeans(rfm: pd.DataFrame, k: int = 4, random_state: int = 42):
    """
    Feature engineering note: RFM features live on very different scales
    (days vs. counts vs. currency) and Monetary is heavily right-skewed
    (a few big spenders dominate). We log-transform Monetary and Frequency
    to compress that skew, then StandardScale all three so KMeans
    (which is distance-based) doesn't let currency dominate the distance
    metric purely because it has the largest raw numbers.
    """
    features = rfm.copy()
    features["monetary_log"] = np.log1p(features["monetary"])
    features["frequency_log"] = np.log1p(features["frequency"])

    X = features[["recency_days", "frequency_log", "monetary_log"]]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    features["cluster"] = model.fit_predict(X_scaled)

    sil = silhouette_score(X_scaled, features["cluster"])
    return features, model, scaler, sil


def profile_clusters(features: pd.DataFrame) -> pd.DataFrame:
    profile = features.groupby("cluster").agg(
        n_customers=("customer_unique_id", "count"),
        avg_recency_days=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
        total_monetary=("monetary", "sum"),
    ).round(2).sort_values("avg_monetary", ascending=False)

    # Simple, defensible business labels based on relative rank within
    # THIS dataset's clusters (not fixed external thresholds).
    labels = []
    for _, row in profile.iterrows():
        if row["avg_monetary"] == profile["avg_monetary"].max():
            labels.append("High-Value")
        elif row["avg_recency_days"] == profile["avg_recency_days"].max():
            labels.append("At-Risk / Dormant")
        elif row["avg_frequency"] == profile["avg_frequency"].max():
            labels.append("Loyal / Repeat")
        else:
            labels.append("Standard")
    profile["segment_label"] = labels
    return profile


def run(data_dir: str, k: int, out_dir: str) -> dict:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)
    order_value = eda_analysis.build_order_value_table(clean)

    rfm = build_rfm(order_value, clean["customers"])
    features, model, scaler, sil = fit_kmeans(rfm, k=k)
    profile = profile_clusters(features)

    print(f"\nSilhouette score (k={k}): {sil:.4f}  (closer to 1 = better-separated clusters)")
    print("\nCluster profile:\n", profile)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    features.to_csv(out_path / "customer_segments.csv", index=False)
    profile.to_csv(out_path / "segment_profile.csv")

    # --- Model persistence (additive; does not affect CSV outputs/metrics above) ---
    model_dir = out_path / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"kmeans": model, "scaler": scaler}, model_dir / "segmentation_model.joblib")
    print(f"Saved segmentation model to {model_dir / 'segmentation_model.joblib'}")

    return {"features": features, "profile": profile, "silhouette": sil}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--out-dir", default="./ml_output")
    args = parser.parse_args()
    run(args.data_dir, args.k, args.out_dir)
