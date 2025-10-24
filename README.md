# Web Scraping Efficiency & Network Behavior Study

This repository compares three techniques for collecting identical Hacker News
front-page data (Selenium, BeautifulSoup, and the official API). Each run
records performance, networking characteristics, and produces a cleaned dataset
for downstream machine learning tasks.

## Structure

- `scrapers/`: individual scraper implementations plus shared utilities.
- `data/raw/`: raw CSV exports from each scraping technique.
- `data/processed/`: cleaned dataset used for ML modelling.
- `notebooks/`: Jupyter notebooks for networking analysis and ML exploration.
- `network/`: helper scripts, captured traces, and firewall/proxy configs.
- `reports/`: generated report PDFs and supporting assets.

## Quick Start

1. Install dependencies: `python -m venv env && source env/bin/activate && pip install -r requirements.txt`.
2. Run the orchestrator to scrape and capture metrics: `python collect_data.py --limit 30`.
3. Execute notebooks for analysis, then render the final report with
   `python generate_report.py`.

## Network Monitoring Lab

- Script: `network/network_lab.sh` (referenced from `Lab2-net.pdf`).
- Captures a timed `tcpdump` trace, streams live `nload`, samples interface
  counters, and renders a PNG bandwidth chart.

Example (60 s on default interface):

```bash
./network/network_lab.sh monitor --duration 60
```

Artifacts are written to `network/logs/`. Run `./network/network_lab.sh firewall`
to configure `ufw` so only HTTP/HTTPS inbound traffic is allowed (remains
disabled if ufw is inactive).

## KMeans Upvote Clustering

- Script: `notebooks/kmeans_lab.py` (uses one-hot encoding and unsupervised
  KMeans).
- Trains on 90% of the combined dataset, labels clusters by mean upvotes, and
  compares predictions on the remaining 10%.

Example:

```bash
env/bin/python notebooks/kmeans_lab.py --clusters 4 --test-size 0.1
```

Results (including holdout comparisons) are saved to
`reports/kmeans_holdout_comparison.csv`.
