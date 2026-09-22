"""Typed search queries for LinkedIn entities.

The canonical definitions live in :mod:`linkedin_scraper.models.search_queries`
so that lower layers (search ports, pure parsers) can depend on them without
importing the search workflows layer. This module re-exports them for backward
compatibility.
"""

from __future__ import annotations

from linkedin_scraper.models.search_queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
    SearchQuery,
)

__all__ = [
    "SearchQuery",
    "PersonSearchQuery",
    "CompanySearchQuery",
    "JobSearchQuery",
    "PostSearchQuery",
    "EmployeeSearchQuery",
]
