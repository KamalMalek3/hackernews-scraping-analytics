from __future__ import annotations

import re
from typing import Dict, Optional

from bs4 import BeautifulSoup


POINTS_RE = re.compile(r"(\d+)\s+points?")
COMMENTS_RE = re.compile(r"(\d+)\s+comments?")


def extract_front_page_items(html: str) -> BeautifulSoup:
    """Parse HN front page HTML and return soup object."""
    return BeautifulSoup(html, "html.parser")


def parse_points(text: Optional[str]) -> int:
    if not text:
        return 0
    match = POINTS_RE.search(text)
    return int(match.group(1)) if match else 0


def parse_comments(text: Optional[str]) -> int:
    if not text:
        return 0
    if "discuss" in text.lower():
        return 0
    match = COMMENTS_RE.search(text)
    return int(match.group(1)) if match else 0


def build_record(
    *,
    post_id: int,
    title: str,
    url: str,
    points: int,
    comments_count: int,
    author: Optional[str],
    top_comment_author: Optional[str],
    top_comment_text: Optional[str],
) -> Dict[str, Optional[str]]:
    return {
        "post_id": str(post_id),
        "title": title,
        "url": url,
        "points": points,
        "comments_count": comments_count,
        "author": author or "",
        "top_comment_author": top_comment_author or "",
        "top_comment_text": (top_comment_text or "").strip(),
    }
