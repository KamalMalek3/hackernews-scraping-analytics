from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

METRICS_PATH = Path("data/raw/scraper_metrics.csv")
DATASET_PATH = Path("data/processed/combined_dataset.csv")
REPORT_PATH = Path("reports/optimization_report.pdf")


def load_data():
    metrics = pd.read_csv(METRICS_PATH)
    dataset = pd.read_csv(DATASET_PATH)
    return metrics, dataset


def compute_keyword_signals(df: pd.DataFrame, top_n: int = 10):
    threshold = df["points"].quantile(0.75)
    df = df.copy()
    df["label"] = (df["points"] >= threshold).astype(int)
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)
    X = vectorizer.fit_transform(df["title"])
    clf = LogisticRegression(max_iter=200, class_weight="balanced")
    clf.fit(X, df["label"])
    feature_names = np.array(vectorizer.get_feature_names_out())
    coefs = clf.coef_[0]
    top_idx = np.argsort(coefs)[-top_n:][::-1]
    bottom_idx = np.argsort(coefs)[:top_n]
    top_tokens = list(zip(feature_names[top_idx], coefs[top_idx]))
    low_tokens = list(zip(feature_names[bottom_idx], coefs[bottom_idx]))
    return top_tokens, low_tokens


def render_cover(pdf: PdfPages, metrics: pd.DataFrame):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    fig.suptitle("Website Data Collection Optimization Report", fontsize=20, y=0.94)

    total_requests = int(metrics["total_requests"].sum())
    total_bytes = metrics["total_bytes"].sum() / 1024
    best_method = (
        metrics.sort_values("total_time_s", ascending=True).iloc[0]["method"]
    )

    text = dedent(
        f"""
        Target Site: https://news.ycombinator.com
        Data Collected: Titles, points, comment counts, authors, first comment

        Key Highlights
        • Total requests issued: {total_requests}
        • Aggregate bandwidth consumed: {total_bytes:.1f} KB
        • Fastest method: {best_method.title()}
        • Selenium captured full rendered context (comment text) at the cost of higher latency.
        """
    )
    fig.text(0.1, 0.6, text, fontsize=12, va="top")

    fig.text(
        0.1,
        0.35,
        "Objective:\nCompare scraping efficiency, observe network behaviour, "
        "and recommend the most resilient workflow.",
        fontsize=12,
    )
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def render_metrics_table(pdf: PdfPages, metrics: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.set_title("Performance & Network Summary", fontsize=16, pad=20)

    display_df = metrics.copy()
    display_df["total_time_s"] = display_df["total_time_s"].map(lambda x: f"{x:.2f}")
    display_df["total_bytes"] = display_df["total_bytes"].map(
        lambda x: f"{x/1024:.1f} KB"
    )
    display_df["avg_latency_ms"] = display_df["avg_latency_ms"].map(
        lambda x: f"{x:.1f}"
    )

    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.4)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def render_method_comparison(pdf: PdfPages, metrics: pd.DataFrame, dataset: pd.DataFrame):
    agg = (
        dataset.groupby("method")
        .agg(mean_points=("points", "mean"), mean_comments=("comments_count", "mean"))
        .reset_index()
    )

    fig, axes = plt.subplots(1, 2, figsize=(11, 6))
    sns = __import__("seaborn")
    sns.barplot(data=agg, x="method", y="mean_points", ax=axes[0], palette="viridis")
    axes[0].set_title("Average Points by Method")
    axes[0].set_ylabel("Points")
    axes[0].set_xlabel("Method")

    sns.barplot(
        data=agg, x="method", y="mean_comments", ax=axes[1], palette="magma"
    )
    axes[1].set_title("Average Comments by Method")
    axes[1].set_ylabel("Comments")
    axes[1].set_xlabel("Method")

    plt.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def render_keyword_page(pdf: PdfPages, top_tokens, low_tokens):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.set_title("Headline Keyword Signals", fontsize=16, pad=20)

    def format_tokens(tokens):
        return "\n".join(f"{word:<20} ({weight:.2f})" for word, weight in tokens)

    text = (
        "Positive Indicators (more likely to rank high):\n"
        + format_tokens(top_tokens)
        + "\n\nNegative Indicators (less likely to rank high):\n"
        + format_tokens(low_tokens)
    )
    ax.text(0.05, 0.9, text, fontsize=12, va="top", family="monospace")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def render_recommendations(pdf: PdfPages, metrics: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.set_title("Recommended Strategy & Hardening Checklist", fontsize=16, pad=20)

    fastest_method = metrics.sort_values("total_time_s").iloc[0]["method"]
    lightest_method = metrics.sort_values("total_bytes").iloc[0]["method"]

    recommendations = dedent(
        f"""
        Optimal Workflow
        • Use the API collector for frequent polling (fastest: {fastest_method.title()}).
        • Augment with the BeautifulSoup scraper to capture rendered comment context.
        • Schedule Selenium runs hourly to validate UI changes and keep parsing selectors fresh.

        Hardening Steps
        • Enforce rate limiting via the configurable `throttle_s` arguments.
        • Restrict outbound ports with `ufw` during tests to ensure graceful degradation.
        • Capture traffic with `tcpdump` and archive `.pcap` files in `network/` for audits.
        • Route high-volume runs through a proxy or VPN and refresh credentials securely.
        """
    )
    ax.text(0.05, 0.95, recommendations, fontsize=12, va="top")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def build_report():
    metrics, dataset = load_data()
    top_tokens, low_tokens = compute_keyword_signals(dataset)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(REPORT_PATH) as pdf:
        render_cover(pdf, metrics)
        render_metrics_table(pdf, metrics)
        render_method_comparison(pdf, metrics, dataset)
        render_keyword_page(pdf, top_tokens, low_tokens)
        render_recommendations(pdf, metrics)
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    build_report()
