# 10-Minute Presentation Outline

## 1. Problem Framing (1 min)
- Goal: Compare Selenium, BeautifulSoup, and Hacker News API scrapers.
- Metrics captured: runtime, bandwidth, request volume, latency.

## 2. Implementation Overview (2 min)
- Selenium: headless Chromium with network logging.
- BeautifulSoup: requests + HTML parsing with rate limiting.
- API: Firebase endpoints for lean polling.
- Shared orchestrator saves CSV + JSON artifacts for reproducibility.

## 3. Networking Observations (2 min)
- Display charts from `notebooks/network_analysis.ipynb` (runtime vs bandwidth).
- Highlight tcpdump/ufw workflow and proxy configuration.

## 4. Data Insights (2 min)
- Walk through `notebooks/ml_analysis.ipynb`.
- Show classification performance and key headline keywords.

## 5. Recommendation Slide (2 min)
- Summarize optimal hybrid strategy (API + BS4 baseline, Selenium validation).
- Security posture: rate limiting, firewall drills, proxy rotation.

## 6. Q&A (1 min)
- Invite questions on scaling, deployment, or ML extension ideas.
