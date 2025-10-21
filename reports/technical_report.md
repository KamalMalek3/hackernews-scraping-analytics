# Technical Report: Hacker News Scraping Efficiency & Network Study

## Introduction
This project investigates how different web scraping strategies perform when collecting identical content from [Hacker News](https://news.ycombinator.com/). We implemented Selenium, BeautifulSoup, and API-based scrapers, captured network telemetry for each run, applied machine learning analysis to the merged dataset, and produced an optimization report that compares efficiency, stability, and data richness.

## Project Overview
- **Objective:** Identify the most effective scraping workflow by comparing runtime, bandwidth usage, request volume, and latency while ensuring secure, responsible collection practices.
- **Target Data:** Front-page post titles, points, comment counts, submitting user, and first comment content.
- **Outputs:** Normalized CSV datasets, per-method network traces (`*.json`), exploratory & ML notebooks, a PDF optimization report, and operational scripts for firewall/proxy testing.

## Repository Structure
```
.
├── collect_data.py              # Orchestrates scraping runs and saves outputs
├── data/
│   ├── raw/                     # Per-method records + network telemetry
│   └── processed/               # Combined dataset for analysis
├── notebooks/
│   ├── ml_analysis.ipynb        # EDA & ML models (classification + regression)
│   └── network_analysis.ipynb   # Network metrics visualizations & tooling guide
├── network/
│   ├── firewall_demo.sh         # UFW-based failure drill
│   └── observations.md          # Template for live instrumentation notes
├── reports/
│   ├── optimization_report.pdf  # Generated performance + recommendation report
│   ├── presentation_outline.md  # 10-minute talk track
│   └── technical_report.md      # (this document)
└── scrapers/
    ├── api_scraper.py           # Multithreaded HN API collector
    ├── bs4_scraper.py           # Requests + BeautifulSoup scraper
    ├── selenium_scraper.py      # Headless Chromium scraper with network logs
    └── utils.py                 # Shared parsing helpers
```

## Key Implementation Highlights

### Unified Scraper Orchestration
`collect_data.py` normalizes all outputs, ensuring every scraper writes records and metrics in the same format:

```python
# collect_data.py:24-36
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
```

### BeautifulSoup Scraper with Comment Retrieval
The HTML scraper downloads the front page, follows discussion links when comments exist, and records per-request telemetry:

```python
# scrapers/bs4_scraper.py:35-102
def _tracked_get(self, url: str, *, timeout: int = 15) -> requests.Response:
    start = time.perf_counter()
    response = self.session.get(url, timeout=timeout)
    elapsed_ms = (time.perf_counter() - start) * 1000
    bytes_read = len(response.content)
    event = RequestEvent(url=url, method="GET", status_code=response.status_code,
                         elapsed_ms=elapsed_ms, bytes_read=bytes_read, timestamp=time.time())
    self._events.append(event)
    if self.throttle_s > 0:
        time.sleep(self.throttle_s)
    response.raise_for_status()
    return response

def run(self, limit: int = 30) -> ScraperResult:
    front_page = self._tracked_get(FRONT_PAGE_URL)
    soup = extract_front_page_items(front_page.text)
    ...
    if comments_count > 0:
        discussion_soup = self._parse_discussion(post_id)
        comment = self._first_comment(discussion_soup)
```

### Multithreaded API Collector
The API scraper parallelizes story retrieval via `ThreadPoolExecutor` while safely recording network events:

```python
# scrapers/api_scraper.py:20-90
class HackerNewsAPIScraper:
    def __init__(..., max_workers: int = 5) -> None:
        self._events: List[RequestEvent] = []
        self._lock = threading.Lock()
        self._max_workers = max_workers

    def _tracked_get(...):
        ...
        with self._lock:
            self._events.append(event)
        ...

    def run(self, limit: int = 30) -> ScraperResult:
        top_ids = self._tracked_get("topstories.json")[:limit]
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            for record in executor.map(self._process_post, top_ids):
                records.append(record)
```

### Selenium Network Logging
The Selenium implementation runs headless Chromium, waits for rendered elements, and captures Chrome DevTools performance logs:

```python
# scrapers/selenium_scraper.py:72-112
def _collect_network_events(self, driver) -> List[RequestEvent]:
    logs = driver.get_log("performance")
    for entry in logs:
        message = json.loads(entry["message"])
        method = message.get("message", {}).get("method")
        ...
        if method == "Network.loadingFinished":
            events.append(RequestEvent(
                url=urls.get(request_id, ""),
                method=methods.get(request_id, "GET"),
                status_code=statuses.get(request_id, 0),
                elapsed_ms=elapsed_ms,
                bytes_read=encoded_len,
                timestamp=time.time(),
            ))
```

### Report Generation Pipeline
`generate_report.py` loads the consolidated metrics, computes keyword signals with logistic regression, and renders an A4 PDF report:

```python
# generate_report.py:152-176
def render_recommendations(pdf: PdfPages, metrics: pd.DataFrame):
    fastest_method = metrics.sort_values("total_time_s").iloc[0]["method"]
    recommendations = dedent(
        f"""
        Optimal Workflow
        • Use the API collector for frequent polling (fastest: {fastest_method.title()}).
        • Augment with the BeautifulSoup scraper to capture rendered comment context.
        • Schedule Selenium runs hourly to validate UI changes and keep parsing selectors fresh.
        """
    )
    ax.text(0.05, 0.95, recommendations, fontsize=12, va="top")
```

## Results & Analysis

### Performance & Network Metrics
| Method        | Runtime (s) | Requests | Downloaded KB | Avg Latency (ms) |
|---------------|-------------|----------|----------------|------------------|
| BeautifulSoup | 32.60       | 21       | 4,833.1        | 668.5            |
| API           | **5.12**    | 41       | **32.5**       | 295.2            |
| Selenium      | 49.31       | **128**  | 718.6          | **112.9**        |

- **API** scraping is the fastest and leanest by bandwidth, but it cannot capture rendered comment text.
- **BeautifulSoup** strikes a balance: it collects rendered comments while using a fraction of Selenium’s requests.
- **Selenium** provides the richest context (full DOM, dynamic content) but requires the most requests and runtime due to browser automation overhead and resource downloads.

### Engagement Dataset Insights
- 60 records were collected (20 per method) and merged into `data/processed/combined_dataset.csv`.
- Mean points per method were nearly identical (≈277 points), confirming that all collectors captured the same stories.
- Comment counts show the expected HTML vs. API contrast: API data only knows the count via metadata (mean 31.6) while HTML-based scrapes retrieve full threads (≈162 comments in top stories).
- The top-quartile threshold for “high engagement” posts landed at 402 points. Each method captured 5 such posts, demonstrating feature parity.

### Machine Learning Findings
- The classification pipeline in `notebooks/ml_analysis.ipynb` trains a balanced logistic regression model over TF-IDF headline features, yielding ROC-AUC ≈0.74 in initial runs. Terms such as “Ask HN”, “Show HN”, “AWS”, and “outage” surfaced as strong positive signals, while generic phrases like “Showcase” or “launch” trended negative.
- A Gradient Boosting Regressor achieved a mean absolute error around 52 points when predicting raw score from combined textual and structural features. Title length, presence of question marks, and n-gram TF-IDF features contributed most heavily.

### Network Observation & Security Controls
- `notebooks/network_analysis.ipynb` visualizes runtime vs. bandwidth consumption and offers an ECDF view of per-request latency derived from the JSON telemetry.
- `network/firewall_demo.sh` demonstrates how to block outbound HTTPS with UFW, run a scraper to validate error handling, and restore connectivity. The accompanying `network/observations.md` template guides documentation of `ss`, `iftop`, `tcpdump`, and Wireshark captures.
- Proxy usage is supported by environment variables (`HTTP_PROXY`, `HTTPS_PROXY`) and optional Selenium flags, enabling controlled routing through Squid/Tor for larger collection campaigns.

## Conclusion
Combining the three scrapers provides a resilient, auditable data collection pipeline for Hacker News. The API collector should serve as the high-frequency backbone because it minimizes bandwidth and runtime. BeautifulSoup complements it by retrieving rendered comment content with moderate overhead, while Selenium is best reserved for scheduled validation runs that guard against DOM changes and capture dynamic elements. Network instrumentation scripts, firewall exercises, and proxy support ensure the approach remains responsible and adaptable as site behavior evolves.

### References
- Hacker News Firebase API: https://github.com/HackerNews/API
- Selenium WebDriver Documentation: https://www.selenium.dev/documentation/
- BeautifulSoup Documentation: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- UFW Manual: https://help.ubuntu.com/community/UFW

### Requirements
- Python 3.12+
- Virtual environment with the packages listed in `requirements.txt`, including:
  - `requests`, `beautifulsoup4`, `selenium`, `pandas`, `scikit-learn`, `seaborn`, `matplotlib`, `tqdm`, `webdriver-manager`, `nbformat`
- Chromium/Chrome available on the system for Selenium runs
- Optional: `ufw`, `tcpdump`, `iftop`, `nload`, and Wireshark for network experiments
