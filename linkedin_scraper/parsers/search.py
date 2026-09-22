"""
Pure, browser-independent search card parsers for LinkedIn search result cards.

Translates raw dict/JSON input or lightweight structured maps into Agent 3's DTO models.
Strictly decoupled from Playwright, BrowserPort, Page, or any networking logic.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from linkedin_scraper.models.search_results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
)


def _clean_str(val: Any) -> str | None:
    """Clean string values, stripping whitespace and returning None for empty strings."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _clean_first_line(val: Any) -> str | None:
    """Clean string values and take only the first non-empty line (prevents card bundling in name fields)."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    lines = [line.strip() for line in s.split("\n") if line.strip()]
    return lines[0] if lines else None


def _parse_int(val: Any) -> int | None:
    """Parse numeric values safely, supporting string numbers like '1,234' or '123'."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    s = str(val).strip().replace(",", "")
    # Support '1k', '1.5k' optional parsing if present in text
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kKmM]?)", s)
    if not match:
        return None
    num_str, multiplier = match.groups()
    try:
        num = float(num_str)
        if multiplier.lower() == "k":
            num *= 1000
        elif multiplier.lower() == "m":
            num *= 1000000
        return int(num)
    except ValueError:
        return None


def parse_person_search_card(data: Mapping[str, Any]) -> PersonSearchResult:
    """
    Parse lightweight person search card raw data dictionary into PersonSearchResult DTO.

    Expected keys (optional/required handled gracefully):
      - name: str (required, fails or defaults if missing)
      - linkedin_url: str (required, must be a valid person profile URL)
      - headline: str
      - location: str
      - current_company: str
    """
    name = _clean_first_line(data.get("name"))
    url = _clean_str(data.get("linkedin_url") or data.get("url"))

    if not name:
        raise ValueError("Person search card missing required field 'name'")
    if not url or "/in/" not in url:
        raise ValueError("Person search card missing required field 'linkedin_url'")

    return PersonSearchResult(
        name=name,
        linkedin_url=url,
        headline=_clean_str(data.get("headline")),
        location=_clean_str(data.get("location")),
        current_company=_clean_str(data.get("current_company") or data.get("company")),
    )


def parse_company_search_card(data: Mapping[str, Any]) -> CompanySearchResult:
    """
    Parse lightweight company search card raw data dictionary into CompanySearchResult DTO.

    Expected keys:
      - name: str (required)
      - linkedin_url: str (required)
      - industry: str
      - location: str
      - followers_count: int / str
    """
    name = _clean_first_line(data.get("name"))
    url = _clean_str(data.get("linkedin_url") or data.get("url"))

    if not name:
        raise ValueError("Company search card missing required field 'name'")
    if not url or "/company/" not in url:
        raise ValueError("Company search card missing required field 'linkedin_url'")

    followers = _parse_int(data.get("followers_count") or data.get("followers"))

    return CompanySearchResult(
        name=name,
        linkedin_url=url,
        industry=_clean_str(data.get("industry")),
        location=_clean_str(data.get("location")),
        followers_count=followers,
    )


def parse_job_search_card(data: Mapping[str, Any]) -> JobSearchResult:
    """
    Parse lightweight job search card raw data dictionary into JobSearchResult DTO.

    Expected keys:
      - job_title: str (required)
      - linkedin_url: str (required) — if relative (starts with "/"), it will be
        absolutized to https://www.linkedin.com<url>
      - company_name: str
      - location: str
      - posted_date: str
      - easy_apply: bool
    """
    title = _clean_first_line(data.get("job_title") or data.get("title"))
    url = _clean_str(data.get("linkedin_url") or data.get("url"))
    # Normalize relative LinkedIn URLs to absolute form so hrefs such as
    # "/jobs/view/12345/" work from both JS card extraction and legacy paths.
    if url and not url.startswith(("http://", "https://")):
        url = f"https://www.linkedin.com{url}"


    if not title:
        raise ValueError("Job search card missing required field 'job_title'")
    if not url or "/jobs/" not in url:
        raise ValueError("Job search card missing required field 'linkedin_url'")

    easy_apply = bool(data.get("easy_apply", False))

    return JobSearchResult(
        job_title=title,
        linkedin_url=url,
        company_name=_clean_str(data.get("company_name") or data.get("company")),
        location=_clean_str(data.get("location")),
        posted_date=_clean_str(data.get("posted_date") or data.get("posted_at")),
        easy_apply=easy_apply,
    )


def parse_post_search_card(data: Mapping[str, Any]) -> PostSearchResult:
    """
    Parse lightweight post search card raw data dictionary into PostSearchResult DTO.

    Expected keys:
      - linkedin_url: str
      - author_name: str
      - author_headline: str
      - text_snippet: str
      - posted_date: str
      - reactions_count: int / str
    """
    reactions = _parse_int(data.get("reactions_count") or data.get("reactions"))

    return PostSearchResult(
        linkedin_url=_clean_str(data.get("linkedin_url") or data.get("url")),
        author_name=_clean_first_line(data.get("author_name") or data.get("author")),
        author_headline=_clean_str(data.get("author_headline") or data.get("headline")),
        text_snippet=_clean_str(data.get("text_snippet") or data.get("text") or data.get("snippet")),
        posted_date=_clean_str(data.get("posted_date") or data.get("posted_at")),
        reactions_count=reactions,
    )


def parse_employee_search_card(data: Mapping[str, Any]) -> EmployeeSearchResult:
    """
    Parse lightweight employee search card raw data dictionary into EmployeeSearchResult DTO.

    Expected keys:
      - name: str (required)
      - linkedin_url: str
      - designation: str
      - company_name: str
    """
    name = _clean_first_line(data.get("name"))

    if not name:
        raise ValueError("Employee search card missing required field 'name'")

    url = _clean_str(data.get("linkedin_url") or data.get("url"))
    if url and "/in/" not in url:
        url = None

    return EmployeeSearchResult(
        name=name,
        linkedin_url=url,
        designation=_clean_str(data.get("designation") or data.get("title") or data.get("headline")),
        company_name=_clean_str(data.get("company_name") or data.get("company")),
    )
