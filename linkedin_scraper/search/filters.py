"""Enums and search filter models for LinkedIn search domain.

The definitions live in :mod:`linkedin_scraper.models.search_filters` so that
lower layers (pure parsers, ports) can depend on them without importing the
search workflows layer. This module re-exports them for backward compatibility.
"""

from __future__ import annotations

from linkedin_scraper.models.search_filters import (  # noqa: F401
    BaseSearchFilter,
    CompanySearchFilter,
    CompanySize,
    ConnectionDegree,
    DatePosted,
    EmployeeSearchFilter,
    EmploymentType,
    ExperienceLevel,
    JobSearchFilter,
    PersonSearchFilter,
    PostSearchFilter,
    SortBy,
    WorkplaceType,
)

__all__ = [
    "BaseSearchFilter",
    "CompanySearchFilter",
    "CompanySize",
    "ConnectionDegree",
    "DatePosted",
    "EmployeeSearchFilter",
    "EmploymentType",
    "ExperienceLevel",
    "JobSearchFilter",
    "PersonSearchFilter",
    "PostSearchFilter",
    "SortBy",
    "WorkplaceType",
]
