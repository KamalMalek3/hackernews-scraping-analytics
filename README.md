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
