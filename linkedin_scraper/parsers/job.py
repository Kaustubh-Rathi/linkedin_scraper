"""Pure, browser-independent parsing logic for LinkedIn job postings."""

from __future__ import annotations

from ..models.job import Job

POSTED_DATE_MARKERS = ("ago", "day", "week", "hour")
APPLICANT_COUNT_MARKERS = ("applicant", "people clicked", "applied")
LOCATION_MARKERS = (",", "Remote", "United States")


def clean_job_url(href: str) -> str:
    """Strip query params and ensure the URL is an absolute linkedin.com URL."""
    if not href:
        return ""
    href = href.strip()
    if "?" in href:
        href = href.split("?")[0].strip()
    if "#" in href:
        href = href.split("#")[0].strip()
    if not href:
        return ""
    if not href.startswith("http"):
        if not href.startswith("/"):
            href = f"/{href}"
        href = f"https://www.linkedin.com{href}"
    return href


def parse_top_card_parts(
    text: str,
) -> tuple[str | None, str | None, str | None]:
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


def looks_like_location(text: str, job_title: str | None = None) -> bool:
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


def parse_job_posting(
    linkedin_url: str,
    job_title: str | None,
    company: str | None,
    company_linkedin_url: str | None,
    top_card_text: str | None = None,
    location_fallback: str | None = None,
    posted_date_fallback: str | None = None,
    applicant_count_fallback: str | None = None,
    job_description: str | None = None,
) -> Job:
    """Parse raw job section components into a Job model."""
    location, posted_date, applicant_count = parse_top_card_parts(top_card_text or "")
    if location is None:
        location = location_fallback
    if posted_date is None:
        posted_date = posted_date_fallback
    if applicant_count is None:
        applicant_count = applicant_count_fallback

    clean_company_url = clean_job_url(company_linkedin_url) if company_linkedin_url else None

    return Job(
        linkedin_url=linkedin_url,
        job_title=job_title,
        company=company,
        company_linkedin_url=clean_company_url,
        location=location,
        posted_date=posted_date,
        applicant_count=applicant_count,
        job_description=job_description,
    )
