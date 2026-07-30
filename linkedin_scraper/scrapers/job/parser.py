"""Pure/heuristic parsing helpers for LinkedIn job postings.

Kept free of Playwright so the URL cleanup and text-classification logic
can be unit tested without a browser. `JobScraper` (and `JobSearchScraper`)
remain the orchestrators that walk the DOM and feed text into these
helpers.
"""

from typing import Optional, Tuple

POSTED_DATE_MARKERS = ("ago", "day", "week", "hour")
APPLICANT_COUNT_MARKERS = ("applicant", "people clicked", "applied")
LOCATION_MARKERS = (",", "Remote", "United States")


def clean_job_url(href: str) -> str:
    """Strip query params and ensure the URL is an absolute linkedin.com URL."""
    if "?" in href:
        href = href.split("?")[0]
    if not href.startswith("http"):
        href = "https://www.linkedin.com{}".format(href)
    return href


def parse_top_card_parts(
    text: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Split the job top-card description text by `·` into
    (location, posted_date, applicant_count).

    Each part is trimmed to its first line, since LinkedIn sometimes
    embeds extra lines within a single `·`-separated segment.
    """
    if not text:
        return None, None, None

    parts = text.split("\u00b7")

    def _first_line(part: str) -> str:
        return part.strip().split("\n")[0].strip()

    location = _first_line(parts[0]) if len(parts) > 0 else None
    posted_date = _first_line(parts[1]) if len(parts) > 1 else None
    applicant_count = _first_line(parts[2]) if len(parts) > 2 else None

    return location or None, posted_date or None, applicant_count or None


def looks_like_location(text: str, job_title: Optional[str] = None) -> bool:
    """Heuristic match for a job location string found while scanning the page."""
    if not text:
        return False
    text = text.strip()
    if job_title and text == job_title:
        return False
    if not any(marker in text for marker in LOCATION_MARKERS):
        return False
    if not (3 < len(text) < 100):
        return False
    if text.startswith("$"):
        return False
    return True


def looks_like_posted_date(text: str) -> bool:
    """Heuristic match for a "posted X ago" style string."""
    if not text:
        return False
    stripped = text.strip()
    lower = stripped.lower()
    if not any(marker in lower for marker in POSTED_DATE_MARKERS):
        return False
    if len(stripped) >= 50:
        return False
    return True


def looks_like_applicant_count(text: str) -> bool:
    """Heuristic match for an applicant-count string."""
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) >= 50:
        return False
    lower = stripped.lower()
    return any(marker in lower for marker in APPLICANT_COUNT_MARKERS)
