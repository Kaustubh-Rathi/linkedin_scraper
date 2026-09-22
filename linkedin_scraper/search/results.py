"""Lightweight search result DTOs and page containers for LinkedIn search domain.

The DTO definitions live in :mod:`linkedin_scraper.models.search_results` so that
pure parsers (layer 2) can depend on them without importing from the search
workflows layer. This module re-exports them for backward compatibility.
"""

from __future__ import annotations

from linkedin_scraper.models.search_results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
    SearchMetadata,
    SearchPage,
)

__all__ = [
    "CompanySearchResult",
    "EmployeeSearchResult",
    "JobSearchResult",
    "PersonSearchResult",
    "PostSearchResult",
    "SearchMetadata",
    "SearchPage",
]

