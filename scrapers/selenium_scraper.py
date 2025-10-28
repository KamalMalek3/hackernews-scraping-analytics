from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base import RequestEvent, ScraperResult, ScraperStats, Timer
from .utils import build_record, parse_comments, parse_points

FRONT_PAGE_URL = "https://news.ycombinator.com/"
DISCUSSION_BASE = "https://news.ycombinator.com/"


def _resolve_driver_path(driver_path: Optional[str]) -> Optional[str]:
    if driver_path:
        return driver_path
    try:
        from webdriver_manager.chrome import ChromeDriverManager

        return ChromeDriverManager().install()
    except Exception:
        return None


class SeleniumScraper:
    """Headless browser scraper driven by Selenium."""

    def __init__(
        self,
        *,
        driver_path: Optional[str] = None,
        headless: bool = True,
        throttle_s: float = 0.5,
        wait_timeout: int = 10,
    ) -> None:
        self.driver_path = _resolve_driver_path(driver_path)
        self.headless = headless
        self.throttle_s = throttle_s
        self.wait_timeout = wait_timeout

    @contextmanager
    def _driver(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        service = (
            ChromeService(executable_path=self.driver_path)
            if self.driver_path
            else ChromeService()
        )
        driver = webdriver.Chrome(service=service, options=options)
        try:
            yield driver
        finally:
            driver.quit()

    def _collect_network_events(self, driver) -> List[RequestEvent]:
        logs = driver.get_log("performance")
        events: List[RequestEvent] = []
        start_times: Dict[str, float] = {}
        urls: Dict[str, str] = {}
        methods: Dict[str, str] = {}
        statuses: Dict[str, int] = {}
        for entry in logs:
            message = json.loads(entry["message"])
            method = message.get("message", {}).get("method")
            params = message.get("message", {}).get("params", {})
            request_id = params.get("requestId")
            if not request_id:
                continue
            if method == "Network.requestWillBeSent":
                start_times[request_id] = params.get("timestamp", time.time())
                request = params.get("request", {})
                urls[request_id] = request.get("url", "")
                methods[request_id] = request.get("method", "")
            elif method == "Network.responseReceived":
                response = params.get("response", {})
                statuses[request_id] = int(response.get("status", 0))
                if request_id not in urls:
                    urls[request_id] = response.get("url", "")
            elif method == "Network.loadingFinished":
                finish_ts = params.get("timestamp", time.time())
                encoded_len = int(params.get("encodedDataLength", 0))
                elapsed_ms = 0.0
                if request_id in start_times:
                    elapsed_ms = (finish_ts - start_times[request_id]) * 1000
                events.append(
                    RequestEvent(
                        url=urls.get(request_id, ""),
                        method=methods.get(request_id, "GET"),
                        status_code=statuses.get(request_id, 0),
                        elapsed_ms=elapsed_ms,
                        bytes_read=encoded_len,
                        timestamp=time.time(),
                    )
                )
        return events

    def run(self, limit: int = 30) -> ScraperResult:
        records: List[Dict[str, str]] = []
        events: List[RequestEvent] = []
        with Timer() as timer, self._driver() as driver:
            driver.get(FRONT_PAGE_URL)
            WebDriverWait(driver, self.wait_timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.athing"))
            )
            rows = driver.find_elements(By.CSS_SELECTOR, "tr.athing")
            for idx, row in enumerate(rows):
                if idx >= limit:
                    break
                post_id = int(row.get_attribute("id"))
                title_el = row.find_element(By.CSS_SELECTOR, "span.titleline a")
                title = title_el.text
                url = title_el.get_attribute("href")
                subtext_row = row.find_element(
                    By.XPATH, "following-sibling::tr[1]/td[@class='subtext']"
                )
                points_el = subtext_row.find_elements(By.CSS_SELECTOR, "span.score")
                author_el = subtext_row.find_elements(By.CSS_SELECTOR, "a.hnuser")
                links = subtext_row.find_elements(By.CSS_SELECTOR, "a")
                comments_link = links[-1] if links else None

                points = parse_points(points_el[0].text if points_el else "")
                comments_count = parse_comments(
                    comments_link.text if comments_link else ""
                )
                comment_url = (
                    comments_link.get_attribute("href") if comments_link else ""
                )
                if comment_url and comment_url.startswith("item?id="):
                    comment_url = DISCUSSION_BASE + comment_url

                top_comment_author = ""
                top_comment_text = ""
                if comments_count > 0 and comment_url:
                    driver.switch_to.new_window("tab")
                    driver.get(comment_url)
                    try:
                        WebDriverWait(driver, self.wait_timeout).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, ".comment-tree .comtr")
                            )
                        )
                        comments = driver.find_elements(
                            By.CSS_SELECTOR, ".comment-tree .comtr"
                        )
                        if comments:
                            first = comments[0]
                            try:
                                top_comment_text = first.find_element(
                                    By.CSS_SELECTOR, "span.commtext"
                                ).text
                            except NoSuchElementException:
                                top_comment_text = ""
                            try:
                                top_comment_author = first.find_element(
                                    By.CSS_SELECTOR, "a.hnuser"
                                ).text
                            except NoSuchElementException:
                                top_comment_author = ""
                    except TimeoutException:
                        top_comment_author = ""
                        top_comment_text = ""
                    finally:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        if self.throttle_s > 0:
                            time.sleep(self.throttle_s)

                records.append(
                    build_record(
                        post_id=post_id,
                        title=title,
                        url=url,
                        points=points,
                        comments_count=comments_count,
                        author=author_el[0].text if author_el else "",
                        top_comment_author=top_comment_author,
                        top_comment_text=top_comment_text,
                    )
                )

            events = self._collect_network_events(driver)
        total_bytes = sum(event.bytes_read for event in events)
        total_requests = len(events)
        avg_latency = (
            sum(event.elapsed_ms for event in events) / total_requests
            if total_requests
            else 0.0
        )
        stats = ScraperStats(
            method="selenium",
            total_time_s=timer.elapsed,
            total_requests=total_requests,
            total_bytes=total_bytes,
            avg_latency_ms=avg_latency,
        )
        return ScraperResult(records=records, stats=stats, raw_events=events)
