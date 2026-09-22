"""Pure deterministic parsers for LinkedIn data structures.

This package contains pure parsing functions for person profiles, companies,
posts, and job postings that are completely independent of Playwright and
browser infrastructure.
"""

from .company import parse_company_overview
from .job import parse_job_posting
from .person import (
    parse_accomplishments,
    parse_contacts,
    parse_educations,
    parse_experiences,
    parse_interests,
    parse_person_profile,
)
from .posts import parse_company_posts

__all__ = [
    "parse_person_profile",
    "parse_experiences",
    "parse_educations",
    "parse_accomplishments",
    "parse_interests",
    "parse_contacts",
    "parse_company_overview",
    "parse_company_posts",
    "parse_job_posting",
]
