"""Pure/heuristic parsing helpers for LinkedIn company overview data.

Kept free of Playwright so the classification logic can be unit tested
without a browser. `CompanyScraper` remains the orchestrator that walks
the DOM and feeds text into these helpers.
"""

from typing import Optional, Tuple

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


def classify_info_item(text: str) -> Optional[Tuple[str, str]]:
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


def apply_dt_dd_label(label: str, value: str, overview: dict) -> None:
    """
    Apply a legacy dt/dd label-value pair to an overview dict in place.

    Mirrors LinkedIn's old dt/dd company page structure, used as a
    fallback when the newer info-item list yields nothing.
    """
    label = label.strip().lower()

    if "website" in label:
        overview["website"] = value
    elif "phone" in label:
        overview["phone"] = value
    elif "headquarters" in label or "location" in label:
        overview["headquarters"] = value
    elif "founded" in label:
        overview["founded"] = value
    elif "industry" in label or "industries" in label:
        overview["industry"] = value
    elif "company type" in label or "type" in label:
        overview["company_type"] = value
    elif "company size" in label or "size" in label:
        overview["company_size"] = value
    elif "specialt" in label:
        overview["specialties"] = value
