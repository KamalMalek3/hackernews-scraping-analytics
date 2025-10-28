from __future__ import annotations

import threading
import html
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import requests

from .base import RequestEvent, ScraperResult, ScraperStats, Timer
from .utils import build_record

API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsAPIScraper:
    """Scraper using the official Hacker News Firebase API."""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        throttle_s: float = 0.2,
        max_workers: int = 5,
    ) -> None:
        self.session = session or requests.Session()
        self.throttle_s = throttle_s
        self._events: List[RequestEvent] = []
        self._lock = threading.Lock()
        self._max_workers = max_workers

    def _tracked_get(self, endpoint: str, *, timeout: int = 15) -> dict:
        url = f"{API_BASE}/{endpoint}"
        start = time.perf_counter()
        response = self.session.get(url, timeout=timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000
        bytes_read = len(response.content)
        event = RequestEvent(
            url=url,
            method="GET",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            bytes_read=bytes_read,
            timestamp=time.time(),
        )
        with self._lock:
            self._events.append(event)
        if self.throttle_s > 0:
            time.sleep(self.throttle_s)
        response.raise_for_status()
        return response.json()

    def _process_post(self, post_id: int) -> dict:
        data = self._tracked_get(f"item/{post_id}.json")
        title = data.get("title", "")
        url = data.get("url", f"https://news.ycombinator.com/item?id={post_id}")
        points = data.get("score", 0)
        comments_ids = data.get("kids", []) or []
        comments_count = len(comments_ids)
        author = data.get("by")

        top_comment_author = ""
        top_comment_text = ""
        if comments_ids:
            comment_data = self._tracked_get(f"item/{comments_ids[0]}.json")
            top_comment_author = comment_data.get("by", "") or ""
            comment_text = comment_data.get("text", "") or ""
            top_comment_text = html.unescape(
                comment_text.replace("<p>", "\n").replace("</p>", "")
            )

        return build_record(
            post_id=post_id,
            title=title,
            url=url,
            points=points,
            comments_count=comments_count,
            author=author,
            top_comment_author=top_comment_author,
            top_comment_text=top_comment_text,
        )

    def run(self, limit: int = 30) -> ScraperResult:
        records = []
        with Timer() as timer:
            top_ids = self._tracked_get("topstories.json")[:limit]
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                for record in executor.map(self._process_post, top_ids):
                    records.append(record)

        total_bytes = sum(event.bytes_read for event in self._events)
        total_requests = len(self._events)
        avg_latency = (
            sum(event.elapsed_ms for event in self._events) / total_requests
            if total_requests
            else 0.0
        )
        stats = ScraperStats(
            method="api",
            total_time_s=timer.elapsed,
            total_requests=total_requests,
            total_bytes=total_bytes,
            avg_latency_ms=avg_latency,
        )
        return ScraperResult(
            records=records,
            stats=stats,
            raw_events=self._events.copy(),
        )
