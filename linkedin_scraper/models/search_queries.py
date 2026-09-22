"""Typed search queries for LinkedIn entities.

Defined in the models layer so pure parsers and other lower layers (e.g.
search ports) can depend on these types without importing the search
workflows layer.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from linkedin_scraper.models.search_filters import (
    CompanySearchFilter,
    EmployeeSearchFilter,
    JobSearchFilter,
    PersonSearchFilter,
    PostSearchFilter,
    _clean_optional_string,
)

FilterT = TypeVar("FilterT")


class SearchQuery(BaseModel, Generic[FilterT]):
    """
    Base generic typed query abstraction.
    
    Represents search intent completely independent of browser mechanics.
    """
    model_config = {"frozen": True}

    keywords: str | None = None
    filters: FilterT
    limit: int = Field(default=25, ge=1, le=1000)
    continuation_token: str | None = None

    @field_validator("keywords", mode="before")
    @classmethod
    def _validate_keywords(cls, v: str | None) -> str | None:
        return _clean_optional_string(v)

    @field_validator("continuation_token", mode="before")
    @classmethod
    def _validate_token(cls, v: str | None) -> str | None:
        return _clean_optional_string(v)


class PersonSearchQuery(SearchQuery[PersonSearchFilter]):
    """Typed search query for Person entities."""
    filters: PersonSearchFilter = Field(default_factory=PersonSearchFilter)


class CompanySearchQuery(SearchQuery[CompanySearchFilter]):
    """Typed search query for Company entities."""
    filters: CompanySearchFilter = Field(default_factory=CompanySearchFilter)


class JobSearchQuery(SearchQuery[JobSearchFilter]):
    """Typed search query for Job entities."""
    filters: JobSearchFilter = Field(default_factory=JobSearchFilter)


class PostSearchQuery(SearchQuery[PostSearchFilter]):
    """Typed search query for Post content entities."""
    filters: PostSearchFilter = Field(default_factory=PostSearchFilter)


class EmployeeSearchQuery(SearchQuery[EmployeeSearchFilter]):
    """
    Typed search query for Employee discovery within a specific company context.
    """
    company_identifier: str = Field(..., description="Company domain, URN, or LinkedIn URL identifier")
    filters: EmployeeSearchFilter = Field(default_factory=EmployeeSearchFilter)

    @field_validator("company_identifier", mode="before")
    @classmethod
    def _validate_company_id(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("company_identifier must not be empty or blank")
        return str(v).strip()
