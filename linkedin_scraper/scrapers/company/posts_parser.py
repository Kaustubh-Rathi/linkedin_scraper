"""Pure parsing helpers for LinkedIn company posts.

Kept free of Playwright so URL building, time/count extraction, and
`Post` construction can be unit tested without a browser.
`CompanyPostsScraper` remains the orchestrator that drives the page and
feeds extracted JS data into these helpers.
"""

import re
from typing import Any, Dict, Optional

from ...models.post import Post

_TIME_RE = re.compile(
    r"(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)", re.IGNORECASE
)
_COUNT_RE = re.compile(r"[\d,]+")


def build_posts_url(company_url: str) -> str:
    """Build the `/posts/` feed URL for a company page."""
    company_url = company_url.rstrip("/")
    if "/posts" not in company_url:
        return "{}/posts/".format(company_url)
    return company_url


def extract_time_from_text(text: str) -> Optional[str]:
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


def parse_count(text: str) -> Optional[int]:
    """Parse a leading number (e.g. reactions/comments count) out of text."""
    if not text:
        return None
    try:
        numbers = _COUNT_RE.findall(text.replace(",", ""))
        if numbers:
            return int(numbers[0])
    except Exception:
        pass
    return None


def post_from_js_data(data: Dict[str, Any]) -> Post:
    """Build a `Post` model from one item of the page-evaluated JS extract."""
    activity_id = data["urn"].replace("urn:li:activity:", "")
    return Post(
        linkedin_url="https://www.linkedin.com/feed/update/urn:li:activity:{}/".format(
            activity_id
        ),
        urn=data["urn"],
        text=data["text"],
        posted_date=extract_time_from_text(data.get("timeText", "")),
        reactions_count=parse_count(data.get("reactions", "")),
        comments_count=parse_count(data.get("comments", "")),
        reposts_count=parse_count(data.get("reposts", "")),
        image_urls=data.get("images", []),
    )
