from __future__ import annotations

import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import RequestEvent, ScraperResult, ScraperStats, Timer
from .utils import build_record, extract_front_page_items, parse_comments, parse_points

FRONT_PAGE_URL = "https://news.ycombinator.com/"
DISCUSSION_URL = "https://news.ycombinator.com/item?id={post_id}"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0 Safari/537.36"
}


class BeautifulSoupScraper:
    """HTML scraping using requests + BeautifulSoup."""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        throttle_s: float = 0.5,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.throttle_s = throttle_s
        self._events: List[RequestEvent] = []

    def _tracked_get(self, url: str, *, timeout: int = 15) -> requests.Response:
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
        self._events.append(event)
        if self.throttle_s > 0:
            time.sleep(self.throttle_s)
        response.raise_for_status()
        return response

    def _parse_discussion(
        self, post_id: int
    ) -> BeautifulSoup:
        response = self._tracked_get(DISCUSSION_URL.format(post_id=post_id))
        return BeautifulSoup(response.text, "html.parser")

    def _first_comment(self, soup: BeautifulSoup) -> Optional[dict]:
        comment = soup.select_one(".comment-tree .comtr .comment")
        if not comment:
            return None
        author_tag = comment.find_previous("a", class_="hnuser")
        return {
            "author": author_tag.get_text(strip=True) if author_tag else None,
            "text": comment.get_text(strip=True),
        }

    def run(self, limit: int = 30) -> ScraperResult:
        records = []
        with Timer() as timer:
            front_page = self._tracked_get(FRONT_PAGE_URL)
            soup = extract_front_page_items(front_page.text)
            items = soup.select("tr.athing")
            for idx, item in enumerate(items):
                if idx >= limit:
                    break
                post_id = int(item.get("id"))
                title = item.select_one("span.titleline a").get_text(strip=True)
                url = item.select_one("span.titleline a")["href"]
                meta_row = item.find_next_sibling("tr")
                points_tag = meta_row.select_one("span.score")
                subtext = meta_row.select_one("td.subtext")
                author_tag = subtext.select_one("a.hnuser") if subtext else None
                comments_link = subtext.find_all("a")[-1] if subtext else None

                points = parse_points(points_tag.get_text() if points_tag else "")
                comments_count = parse_comments(
                    comments_link.get_text() if comments_link else ""
                )

                top_comment_author = ""
                top_comment_text = ""
                if comments_count > 0:
                    discussion_soup = self._parse_discussion(post_id)
                    comment = self._first_comment(discussion_soup)
                    if comment:
                        top_comment_author = comment.get("author") or ""
                        top_comment_text = comment.get("text") or ""

                records.append(
                    build_record(
                        post_id=post_id,
                        title=title,
                        url=url,
                        points=points,
                        comments_count=comments_count,
                        author=author_tag.get_text(strip=True) if author_tag else "",
                        top_comment_author=top_comment_author,
                        top_comment_text=top_comment_text,
                    )
                )

        total_bytes = sum(event.bytes_read for event in self._events)
        total_requests = len(self._events)
        avg_latency = (
            sum(event.elapsed_ms for event in self._events) / total_requests
            if total_requests
            else 0.0
        )
        stats = ScraperStats(
            method="beautifulsoup",
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
