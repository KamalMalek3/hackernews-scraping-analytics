#!/usr/bin/env python3
"""
K-means clustering experiment to discover upvote-friendly content groupings.

Steps:
1. Load the combined Hacker News dataset.
2. Convert categorical columns to numeric via one-hot encoding.
3. Fit KMeans on a training split (unsupervised) and compute cluster stats.
4. Predict cluster membership for a small holdout slice and compare actual points
   with the cluster-level expectations.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATASET_PATH = Path("data/processed/combined_dataset.csv")
REPORTS_DIR = Path("reports")


@dataclass
class ClusterSummary:
    cluster: int
    mean_points: float
    median_points: float
    count: int
    category: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an unsupervised KMeans clustering experiment on HN data."
    )
    parser.add_argument(
        "--clusters",
        type=int,
        default=4,
        help="Number of clusters (K).",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.1,
        help="Fraction of records reserved for holdout evaluation.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORTS_DIR / "kmeans_holdout_comparison.csv",
        help="CSV path for holdout predictions vs actuals.",
    )
    return parser.parse_args()


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["title", "comments_count", "points", "method"])
    df["title_length"] = df["title"].str.len()
    df["top_comment_length"] = df["top_comment_text"].fillna("").str.len()
    df["author_encoded"] = df["author"].fillna("unknown")
    df["has_comment"] = (df["top_comment_text"].fillna("").str.len() > 0).astype(int)
    return df


def build_pipeline(n_clusters: int, random_state: int) -> Pipeline:
    numeric_features = [
        "comments_count",
        "title_length",
        "top_comment_length",
        "has_comment",
    ]
    categorical_features = ["method", "author_encoded"]

    preprocess = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_features,
            ),
        ]
    )

    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
    return Pipeline(
        steps=[
            ("preprocess", preprocess),
            ("cluster", model),
        ]
    )


def label_clusters(train_df: pd.DataFrame, labels: np.ndarray) -> List[ClusterSummary]:
    grouped = (
        train_df.assign(cluster=labels)
        .groupby("cluster")["points"]
        .agg(["mean", "median", "count"])
        .reset_index()
    )

    # Determine improvised categories based on mean scores.
    means = grouped["mean"]
    high_cut = means.quantile(0.66)
    low_cut = means.quantile(0.33)

    def categorize(mean_val: float) -> str:
        if mean_val >= high_cut:
            return "High-Upvote Cluster"
        if mean_val <= low_cut:
            return "Low-Upvote Cluster"
        return "Mid-Upvote Cluster"

    summaries = [
        ClusterSummary(
            cluster=int(row["cluster"]),
            mean_points=float(row["mean"]),
            median_points=float(row["median"]),
            count=int(row["count"]),
            category=categorize(row["mean"]),
        )
        for _, row in grouped.iterrows()
    ]
    return summaries


def summarize_holdout(
    holdout_df: pd.DataFrame,
    holdout_labels: np.ndarray,
    summaries: List[ClusterSummary],
) -> Tuple[pd.DataFrame, float]:
    summary_map = {s.cluster: s for s in summaries}

    holdout = holdout_df.copy()
    holdout["cluster"] = holdout_labels
    holdout["cluster_mean_points"] = holdout["cluster"].map(
        lambda c: summary_map[c].mean_points
    )
    holdout["cluster_category"] = holdout["cluster"].map(
        lambda c: summary_map[c].category
    )

    # Binary label: does this record beat the global median by points?
    global_median = holdout_df["points"].median()
    actual_high = holdout_df["points"] >= global_median
    predicted_high = holdout["cluster_category"] == "High-Upvote Cluster"
    # Convert booleans to int for compatibility with accuracy_score.
    accuracy = accuracy_score(actual_high.astype(int), predicted_high.astype(int))

    return holdout, accuracy


def main() -> None:
    args = parse_args()
    df = load_dataset(DATASET_PATH)

    features = [
        "comments_count",
        "title_length",
        "top_comment_length",
        "has_comment",
        "method",
        "author_encoded",
    ]

    train_df, holdout_df = train_test_split(
        df,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=df["method"],
    )

    pipeline = build_pipeline(args.clusters, args.random_state)
    pipeline.fit(train_df[features])

    cluster_labels = pipeline.named_steps["cluster"].labels_
    summaries = label_clusters(train_df.reset_index(drop=True), cluster_labels)

    holdout_labels = pipeline.predict(holdout_df[features])
    holdout_results, accuracy = summarize_holdout(
        holdout_df.reset_index(drop=True),
        holdout_labels,
        summaries,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    holdout_results[
        [
            "post_id",
            "title",
            "points",
            "comments_count",
            "method",
            "cluster",
            "cluster_category",
            "cluster_mean_points",
        ]
    ].to_csv(args.output, index=False)

    print("=== Cluster Profiles ===")
    for summary in sorted(summaries, key=lambda s: s.mean_points, reverse=True):
        print(
            f"Cluster {summary.cluster}: {summary.category} "
            f"(mean={summary.mean_points:.1f}, median={summary.median_points:.1f}, n={summary.count})"
        )

    print("\n=== Holdout Comparison ===")
    print(holdout_results[["title", "points", "cluster_category", "cluster_mean_points"]].head())
    print(f"\nHoldout high-upvote agreement accuracy: {accuracy:.2%}")
    print(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    main()

