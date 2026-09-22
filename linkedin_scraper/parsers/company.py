"""Pure, browser-independent parsing logic for LinkedIn company data."""

from __future__ import annotations

import urllib.parse
from typing import Sequence

from ..models.company import Company

LOCATION_HINTS = (
    "Washington",
    "California",
    "New York",
    "Texas",
    "United States",
    "United Kingdom",
)
INDUSTRY_HINTS = (
    "software",
    "technology",
    "financial",
    "healthcare",
    "retail",
    "manufacturing",
    "consulting",
    "education",
)


def empty_overview() -> dict:
    """Return the default (all-None) company overview dict."""
    return {
        "website": None,
        "phone": None,
        "headquarters": None,
        "founded": None,
        "industry": None,
        "company_type": None,
        "company_size": None,
        "specialties": None,
    }


def classify_info_item(text: str) -> tuple[str, str] | None:
    """
    Classify a single `.org-top-card-summary-info-list__info-item` text.

    Returns a `(field_name, value)` tuple for company_size, headquarters,
    or industry, or `None` when the text doesn't match a known pattern
    (e.g. follower counts, or anything unrecognized).
    """
    text = text.strip()
    text_lower = text.lower()

    if "employee" in text_lower or "k+" in text_lower:
        return "company_size", text
    if "," in text and any(loc in text for loc in LOCATION_HINTS):
        return "headquarters", text
    if any(ind in text_lower for ind in INDUSTRY_HINTS):
        return "industry", text
    return None



def clean_company_website_url(url: str | None) -> str | None:
    """Clean and unquote website URL, stripping LinkedIn safety redirects if present."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if "linkedin.com/safety/go" in url and "url=" in url:
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            if "url" in params and params["url"]:
                target_url = urllib.parse.unquote(params["url"][0])
                return target_url.strip()
        except Exception:
            pass
    return url


def apply_dt_dd_label(label: str, value: str, overview: dict) -> None:
    """
    Apply a dt/dd or SDUI label-value pair to an overview dict in place.

    Mirrors LinkedIn's dt/dd and modern SDUI overview structure.
    """
    label = label.strip().lower()
    val = value.strip()
    if not val:
        return

    if "website" in label:
        overview["website"] = clean_company_website_url(val)
    elif "phone" in label:
        overview["phone"] = val
    elif "headquarters" in label or "location" in label:
        overview["headquarters"] = val
    elif "founded" in label:
        overview["founded"] = val
    elif "industry" in label or "industries" in label:
        overview["industry"] = val
    elif "company type" in label or label == "type":
        overview["company_type"] = val
    elif "company size" in label or label == "size":
        overview["company_size"] = val
    elif "specialt" in label:
        overview["specialties"] = val


def parse_company_name(raw_name: str | None) -> str | None:
    """Parse and normalize company name, returning None if missing or whitespace."""
    if raw_name:
        cleaned = raw_name.strip()
        if cleaned:
            return cleaned
    return None



def parse_about_section(sections_data: Sequence[tuple[str, Sequence[str]]]) -> str | None:
    """
    Extract about/description text from raw section tuples: (section_text, [paragraph_texts]).
    Only sections whose heading explicitly mentions "about us" are considered.
    """
    for section_text, paragraphs in sections_data:
        sec_lower = section_text[:80].lower()
        if "about us" in sec_lower:
            for p in paragraphs:
                cleaned = p.strip()
                if cleaned and not any(k in cleaned.lower() for k in ["website", "industry", "company size", "headquarters", "specialties"]):
                    return cleaned
    return None


def parse_company_overview(
    info_item_texts: Sequence[str],
    links: Sequence[tuple[str, str]],
    dt_dd_pairs: Sequence[tuple[str, str]] = (),
) -> dict[str, str | None]:
    """Parse raw overview text items, website links, and fallback dt/dd pairs into an overview dictionary."""
    overview = empty_overview()

    for text in info_item_texts:
        classified = classify_info_item(text)
        if classified:
            field, value = classified
            overview[field] = value

    for href, link_text in links:
        cleaned_href = clean_company_website_url(href)
        if cleaned_href and "linkedin.com" not in cleaned_href and ("http" in cleaned_href or "www." in cleaned_href):
            if link_text and any(word in link_text.lower() for word in ["learn more", "website", "visit", "http", ".com", ".org", ".net"]):
                overview["website"] = cleaned_href
                break

    if dt_dd_pairs:
        for label, value in dt_dd_pairs:
            if value:
                apply_dt_dd_label(label, value.strip(), overview)

    return overview


def parse_company_profile(
    linkedin_url: str,
    name: str,
    about_us: str | None,
    info_item_texts: Sequence[str],
    links: Sequence[tuple[str, str]],
    dt_dd_pairs: Sequence[tuple[str, str]] = (),
) -> Company:
    """Construct a Company model from extracted fields and raw overview data."""
    overview = parse_company_overview(info_item_texts, links, dt_dd_pairs)
    return Company(
        linkedin_url=linkedin_url,
        name=name,
        about_us=about_us,
        website=overview.get("website"),
        phone=overview.get("phone"),
        headquarters=overview.get("headquarters"),
        founded=overview.get("founded"),
        industry=overview.get("industry"),
        company_type=overview.get("company_type"),
        company_size=overview.get("company_size"),
        specialties=overview.get("specialties"),
    )

