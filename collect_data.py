from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from scrapers.api_scraper import HackerNewsAPIScraper
from scrapers.base import RequestEvent, ScraperResult, ScraperStats, write_stats_csv
from scrapers.bs4_scraper import BeautifulSoupScraper
from scrapers.selenium_scraper import SeleniumScraper

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


def serialize_events(events: List[RequestEvent]) -> List[Dict]:
    return [event.to_dict() for event in events] if events else []


def run_all(limit: int, include_selenium: bool = True) -> Dict[str, ScraperResult]:
    results: Dict[str, ScraperResult] = {}

    bs_scraper = BeautifulSoupScraper()
    results["beautifulsoup"] = bs_scraper.run(limit=limit)

    api_scraper = HackerNewsAPIScraper()
    results["api"] = api_scraper.run(limit=limit)

    if include_selenium:
        selenium_scraper = SeleniumScraper()
        results["selenium"] = selenium_scraper.run(limit=limit)

    return results


def save_results(results: Dict[str, ScraperResult]) -> None:
    stats: List[ScraperStats] = []
    combined_rows: List[Dict] = []

    for method, result in results.items():
        raw_path = RAW_DIR / f"{method}_records.csv"
        events_path = RAW_DIR / f"{method}_network.json"
        result.dump_csv(raw_path)
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("w", encoding="utf-8") as fh:
            json.dump(serialize_events(result.raw_events or []), fh, indent=2)

        stats.append(result.stats)
        for row in result.records:
            combined_rows.append({**row, "method": method})

    write_stats_csv(stats, RAW_DIR / "scraper_metrics.csv")
    df = pd.DataFrame(combined_rows)
    df.to_csv(PROCESSED_DIR / "combined_dataset.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect Hacker News data using multiple scraping strategies."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of posts to collect per scraper.",
    )
    parser.add_argument(
        "--skip-selenium",
        action="store_true",
        help="Skip the Selenium scraper (useful in headless or driver-less environments).",
    )
    args = parser.parse_args()

    if args.limit <= 0:
        raise ValueError("--limit must be positive.")

    results = run_all(limit=args.limit, include_selenium=not args.skip_selenium)
    save_results(results)
    print("Scraping complete. Metrics saved to data/raw/scraper_metrics.csv")


if __name__ == "__main__":
    main()
