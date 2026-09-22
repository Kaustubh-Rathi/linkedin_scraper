"""Enums and search filter models for LinkedIn search domain.

Defined in the models layer so pure parsers and other lower layers can depend
on these types without importing the search workflows layer.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "ConnectionDegree",
    "CompanySize",
    "CompanySearchFilter",
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


class ConnectionDegree(str, Enum):
    """LinkedIn connection degree level."""
    FIRST = "1"
    SECOND = "2"
    THIRD = "3+"


class DatePosted(str, Enum):
    """Time frame for when job or post was published."""
    PAST_24H = "past_24h"
    PAST_WEEK = "past_week"
    PAST_MONTH = "past_month"
    ANY_TIME = "any_time"


class ExperienceLevel(str, Enum):
    """Job experience level classifications on LinkedIn."""
    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry_level"
    ASSOCIATE = "associate"
    MID_SENIOR = "mid_senior"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class EmploymentType(str, Enum):
    """Employment arrangement types."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    VOLUNTEER = "volunteer"
    INTERNSHIP = "internship"


class WorkplaceType(str, Enum):
    """Workplace location arrangements."""
    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"


class CompanySize(str, Enum):
    """Company headcount size ranges."""
    SELF_EMPLOYED = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_500 = "201-500"
    SIZE_501_1000 = "501-1000"
    SIZE_1001_5000 = "1001-5000"
    SIZE_5001_10000 = "5001-10000"
    SIZE_10000_PLUS = "10001+"


class SortBy(str, Enum):
    """Search result sorting criteria."""
    RELEVANCE = "relevance"
    DATE = "date"


def _clean_list(values: list[str] | None) -> list[str]:
    """Clean string lists by removing empty/blank values and deduplicating while preserving order."""
    if not values:
        return []
    cleaned: list[str] = []
    seen = set()
    for v in values:
        if v is None:
            continue
        stripped = str(v).strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            cleaned.append(stripped)
    return cleaned


def _clean_optional_string(value: str | None) -> str | None:
    """Normalize an optional string by stripping blanks and mapping empty to None."""
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


class BaseSearchFilter(BaseModel):
    """Base class for search filters with common validation helper functions."""

    model_config = {"frozen": True}

    @classmethod
    def _validate_string_lists(cls, v: list[str] | None) -> list[str]:
        return _clean_list(v)

    @classmethod
    def _validate_title(cls, v: str | None) -> str | None:
        return _clean_optional_string(v)


class PersonSearchFilter(BaseSearchFilter):
    """Filter parameters specific to Person search on LinkedIn."""
    title: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    school_name: str | None = None
    location: list[str] = Field(default_factory=list)
    current_company: list[str] = Field(default_factory=list)
    past_company: list[str] = Field(default_factory=list)
    industry: list[str] = Field(default_factory=list)
    school: list[str] = Field(default_factory=list)
    connection_degrees: list[ConnectionDegree] = Field(default_factory=list)
    profile_language: list[str] = Field(default_factory=list)
    service_category: list[str] = Field(default_factory=list)

    @field_validator(
        "location",
        "current_company",
        "past_company",
        "industry",
        "school",
        "profile_language",
        "service_category",
        mode="before",
    )
    @classmethod
    def _validate_string_lists(cls, v: list[str] | None) -> list[str]:
        return super()._validate_string_lists(v)

    @field_validator(
        "title", "first_name", "last_name", "company", "school_name", mode="before"
    )
    @classmethod
    def _validate_title(cls, v: str | None) -> str | None:
        return super()._validate_title(v)


class CompanySearchFilter(BaseSearchFilter):
    """Filter parameters specific to Company search on LinkedIn."""
    location: list[str] = Field(default_factory=list)
    industry: list[str] = Field(default_factory=list)
    company_size: list[CompanySize] = Field(default_factory=list)

    @field_validator("location", "industry", mode="before")
    @classmethod
    def _validate_string_lists(cls, v: list[str] | None) -> list[str]:
        return super()._validate_string_lists(v)


class JobSearchFilter(BaseSearchFilter):
    """Filter parameters specific to Job search on LinkedIn.

    ``job_functions`` and ``salary_buckets`` accept LinkedIn's own facet codes
    (``f_F`` and ``f_SB2`` respectively) so every value exposed in the LinkedIn
    UI can be expressed even when the code catalog changes.
    """
    location: list[str] = Field(default_factory=list)
    date_posted: DatePosted | None = None
    experience_levels: list[ExperienceLevel] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    workplace_types: list[WorkplaceType] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    easy_apply_only: bool = False
    under_ten_applicants: bool = False
    sort_by: SortBy | None = None
    distance: int | None = Field(default=None, ge=0)
    job_functions: list[str] = Field(default_factory=list)
    salary_buckets: list[str] = Field(default_factory=list)

    @field_validator("location", "companies", "industries", mode="before")
    @classmethod
    def _validate_string_lists(cls, v: list[str] | None) -> list[str]:
        return super()._validate_string_lists(v)


class PostSearchFilter(BaseSearchFilter):
    """Filter parameters specific to Post content search on LinkedIn."""
    date_posted: DatePosted | None = None
    author_company: list[str] = Field(default_factory=list)
    author_industry: list[str] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)
    sort_by: SortBy = SortBy.RELEVANCE

    @field_validator("author_company", "author_industry", "content_types", mode="before")
    @classmethod
    def _validate_string_lists(cls, v: list[str] | None) -> list[str]:
        return super()._validate_string_lists(v)


class EmployeeSearchFilter(BaseSearchFilter):
    """Filter parameters specific to Employee discovery within a company context."""
    title: str | None = None
    location: list[str] = Field(default_factory=list)
    department: list[str] = Field(default_factory=list)

    @field_validator("location", "department", mode="before")
    @classmethod
    def _validate_string_lists(cls, v: list[str] | None) -> list[str]:
        return super()._validate_string_lists(v)

    @field_validator("title", mode="before")
    @classmethod
    def _validate_title(cls, v: str | None) -> str | None:
        return super()._validate_title(v)

