"""Pure deterministic parsers for LinkedIn data structures.

This package contains pure parsing functions for person profiles, companies,
posts, and job postings that are completely independent of Playwright and
browser infrastructure.
"""

from .company import parse_company_overview
from .job import parse_job_posting
from .person import (
    parse_accomplishment_item,
    parse_contact_dialog_heading_and_links,
    parse_education_lines,
    parse_experience_lines,
    parse_interest_item,
    parse_name_and_location,
)
from .posts import parse_company_posts

__all__ = [
    "parse_name_and_location",
    "parse_experience_lines",
    "parse_education_lines",
    "parse_accomplishment_item",
    "parse_interest_item",
    "parse_contact_dialog_heading_and_links",
    "parse_company_overview",
    "parse_company_posts",
    "parse_job_posting",
]
