"""Pure, browser-independent parsing logic for LinkedIn feed/search post cards.

Contains the heuristics for the two post surfaces verified live in 2026-09:

* **Content search** (``/search/results/content/``) — cards have no permalink
  anchor and no ``data-urn``; they are located by the accessibility heading
  text ``"Feed post"`` and their author link.
* **Company feed** (``/company/<slug>/posts/``) — cards are
  ``.feed-shared-update-v2`` containers carrying ``data-urn`` and an
  accessibility heading ``"Feed post number N"``.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from ..models.post import Post
from ..models.search_results import PostSearchResult

_TIME_RE = re.compile(
    r"(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago|edited)", re.IGNORECASE
)
_COUNT_RE = re.compile(r"[\d,]+")
_FOLLOWERS_RE = re.compile(r"^[\d,.]+\s*(?:k|m)?\s*followers?$", re.IGNORECASE)
_REPOST_RE = re.compile(r"reposted this", re.IGNORECASE)
_ACTIVITY_RE = re.compile(r"urn:li:activity:(\d+)")
_NUMBERED_HEADING_RE = re.compile(r"^feed post number\s*\d+$", re.IGNORECASE)


def is_feed_post_heading(text: str | None) -> bool:
    """Return True when a card's heading marks it as a LinkedIn feed post."""
    if not text:
        return False
    lowered = text.strip().lower()
    return lowered == "feed post" or bool(_NUMBERED_HEADING_RE.match(lowered))


def activity_id_from_urn(urn: str | None) -> str | None:
    """Extract the numeric activity id from an ``urn:li:activity:`` URN."""
    if not urn:
        return None
    match = _ACTIVITY_RE.search(urn)
    return match.group(1) if match else None


def post_url_from_urn(urn: str | None) -> str | None:
    """Build the canonical feed permalink for an activity URN."""
    activity_id = activity_id_from_urn(urn)
    if not activity_id:
        return None
    return f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"


def extract_posted_time(lines: Sequence[str]) -> str | None:
    """Return the first relative-time line (``18h``, ``4d``, ``3 hours ago``)."""
    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) > 40:
            continue
        if _TIME_RE.search(stripped):
            return stripped
    return None


def extract_post_text(lines: Sequence[str]) -> str | None:
    """Return the post body: everything after the ``Follow`` action row.

    LinkedIn renders ``<heading> | <actor> | <followers?> | <time> | Follow |
    <author headline> | <post body...>``; the body is what follows the last
    action label, so anchoring on it avoids returning actor metadata as text.
    """
    cleaned = [line.strip() for line in lines if line and line.strip()]
    if not cleaned:
        return None

    start = 0
    for index, line in enumerate(cleaned):
        if line.lower() == "follow":
            start = index + 1
    body = cleaned[start:]

    # Drop actor metadata when no Follow anchor exists in the card text
    if start == 0:
        body = [
            line
            for line in cleaned
            if not is_feed_post_heading(line)
            and not _FOLLOWERS_RE.match(line)
            and not _TIME_RE.fullmatch(line)
            and line.lower() != "follow"
        ]

    if not body:
        return None
    text = "\n".join(body).strip()
    return text or None

def build_post_search_result(
    *,
    lines: Sequence[str],
    author_href: str | None = None,
    urn: str | None = None,
    permalink: str | None = None,
    reactions: int | None = None,
) -> PostSearchResult | None:
    """Build a :class:`PostSearchResult` from a post card's raw text.

    ``linkedin_url`` is ``None`` when LinkedIn exposes no permalink (verified
    content-search behaviour); it is derived from the activity URN when one is
    available.
    """
    author_name, author_headline = extract_author_from_lines(lines)
    if not author_name:
        return None

    url = permalink or post_url_from_urn(urn) or author_href
    return PostSearchResult(
        linkedin_url=url,
        author_name=author_name,
        author_headline=author_headline,
        text_snippet=extract_post_text(lines),
        posted_date=extract_posted_time(lines),
        reactions_count=reactions,
    )


def build_post_from_card(
    *,
    urn: str | None,
    lines: Sequence[str],
    image_urls: Sequence[str] = (),
    reactions: int | None = None,
    comments: int | None = None,
) -> Post | None:
    """Build a :class:`Post` model from a company-feed card's raw text."""
    activity_id = activity_id_from_urn(urn)
    if not activity_id:
        return None
    text = extract_post_text(lines)
    if not text:
        return None
    return Post(
        linkedin_url=post_url_from_urn(urn),
        urn=urn,
        text=text,
        posted_date=extract_posted_time(lines),
        reactions_count=reactions,
        comments_count=comments,
        image_urls=list(image_urls),
    )


def parse_count(value: Any) -> int | None:
    """Parse a leading number (e.g. ``1,234``) out of arbitrary text."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    numbers = _COUNT_RE.findall(str(value).replace(",", ""))
    if numbers and numbers[0].isdigit():
        return int(numbers[0])
    return None


def extract_author_from_lines(
    lines: Sequence[str],
) -> tuple[str | None, str | None]:
    """Derive ``(author_name, author_headline)`` from a post card's text lines."""
    cleaned = [line.strip() for line in lines if line and line.strip()]
    actor_lines: list[str] = []
    for line in cleaned:
        if is_feed_post_heading(line):
            actor_lines.clear()
            continue
        if line.lower() == "follow" or _FOLLOWERS_RE.match(line) or _TIME_RE.fullmatch(line):
            break
        if _REPOST_RE.search(line):
            actor_lines.clear()
            continue
        actor_lines.append(line)

    if not actor_lines:
        return None, None
    name = actor_lines[0]
    headline = actor_lines[1] if len(actor_lines) > 1 else None
    return name, headline
