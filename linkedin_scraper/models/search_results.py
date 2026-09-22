"""Lightweight search result DTOs shared by parsers, adapters, and search workflows.

These models are intentionally defined in the models layer (no dependencies on
search workflows, ports, or infrastructure) so that pure parsers can build them
without violating hexagonal layering.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

__all__ = [
    "CompanySearchResult",
    "EmployeeSearchResult",
    "JobSearchResult",
    "PersonSearchResult",
    "PostSearchResult",
    "SearchMetadata",
    "SearchPage",
]


class PersonSearchResult(BaseModel):
    """
    Lightweight DTO for a person search result card.

    Contains essential search summary fields without requiring full profile scraping.
    """
    model_config = {"frozen": True}

    name: str
    linkedin_url: str
    headline: str | None = None
    location: str | None = None
    current_company: str | None = None


class CompanySearchResult(BaseModel):
    """
    Lightweight DTO for a company search result card.
    """
    model_config = {"frozen": True}

    name: str
    linkedin_url: str
    industry: str | None = None
    location: str | None = None
    followers_count: int | None = None


class JobSearchResult(BaseModel):
    """
    Lightweight DTO for a job search result item.
    """
    model_config = {"frozen": True}

    job_title: str
    linkedin_url: str
    company_name: str | None = None
    location: str | None = None
    posted_date: str | None = None
    easy_apply: bool = False


class PostSearchResult(BaseModel):
    """
    Lightweight DTO for a post search result item.
    """
    model_config = {"frozen": True}

    linkedin_url: str | None = None
    author_name: str | None = None
    author_headline: str | None = None
    text_snippet: str | None = None
    posted_date: str | None = None
    reactions_count: int | None = None


class EmployeeSearchResult(BaseModel):
    """
    Lightweight DTO for an employee discovery result.
    """
    model_config = {"frozen": True}

    name: str
    linkedin_url: str | None = None
    designation: str | None = None
    company_name: str | None = None


class SearchMetadata(BaseModel):
    """Metadata about a search execution."""
    model_config = {"frozen": True}

    total_results: int | None = None
    query_string: str | None = None
    page: int | None = None


ItemT = TypeVar("ItemT")


class SearchPage(BaseModel, Generic[ItemT]):
    """
    Infrastructure-agnostic paginated result container.
    """
    model_config = {"frozen": True}

    items: list[ItemT] = Field(default_factory=list)
    total_count: int | None = None
    continuation_token: str | None = None
    has_more: bool = False
    metadata: SearchMetadata | None = None
