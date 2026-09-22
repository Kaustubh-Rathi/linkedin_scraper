"""Pure, browser-independent parsing logic for LinkedIn company posts."""

from __future__ import annotations

import re
from typing import Any, Sequence

from ..models.post import Post

_TIME_RE = re.compile(
    r"(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)", re.IGNORECASE
)
_COUNT_RE = re.compile(r"[\d,]+")


def build_posts_url(company_url: str) -> str:
    """Build the `/posts/` feed URL for a company page."""
    company_url = company_url.rstrip("/")
    if "/posts" not in company_url:
        return f"{company_url}/posts/"
    return company_url


def extract_time_from_text(text: str) -> str | None:
    """Extract a relative time (e.g. "3d", "2 weeks ago") from actor text."""
    if not text:
        return None
    match = _TIME_RE.search(text)
    if match:
        return match.group(1).strip()
    parts = text.split("\u2022")
    if parts:
        return parts[0].strip()
    return None


def parse_count(text: str) -> int | None:
    """Parse a leading number (e.g. reactions/comments count) out of text."""
    if not text or not isinstance(text, str):
        return None
    numbers = _COUNT_RE.findall(text.replace(",", ""))
    if numbers and numbers[0].isdigit():
        return int(numbers[0])
    return None


def post_from_js_data(data: dict[str, Any]) -> Post:
    """Build a `Post` model from one item of the page-evaluated JS extract."""
    activity_id = data["urn"].replace("urn:li:activity:", "")
    return Post(
        linkedin_url=f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
        urn=data["urn"],
        text=data["text"],
        posted_date=extract_time_from_text(data.get("timeText", "")),
        reactions_count=parse_count(data.get("reactions", "")),
        comments_count=parse_count(data.get("comments", "")),
        reposts_count=parse_count(data.get("reposts", "")),
        image_urls=data.get("images", []),
    )


def parse_company_posts(posts_data: Sequence[dict[str, Any]]) -> list[Post]:
    """Parse raw JS post dictionaries into Post models."""
    posts: list[Post] = []
    for data in posts_data:
        if "urn" in data and "text" in data:
            posts.append(post_from_js_data(data))
    return posts
