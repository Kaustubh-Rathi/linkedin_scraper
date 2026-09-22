"""Search port contracts defining focused interfaces for LinkedIn search capabilities."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from linkedin_scraper.models.search_queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
)
from linkedin_scraper.models.search_results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
    SearchPage,
)


@runtime_checkable
class PersonSearchPort(Protocol):
    """Port interface for searching Person entities."""

    async def search_people(
        self, query: PersonSearchQuery
    ) -> SearchPage[PersonSearchResult]:
        """Execute person search with typed query."""
        ...


@runtime_checkable
class CompanySearchPort(Protocol):
    """Port interface for searching Company entities."""

    async def search_companies(
        self, query: CompanySearchQuery
    ) -> SearchPage[CompanySearchResult]:
        """Execute company search with typed query."""
        ...


@runtime_checkable
class JobSearchPort(Protocol):
    """Port interface for searching Job entities."""

    async def search_jobs(
        self, query: JobSearchQuery
    ) -> SearchPage[JobSearchResult]:
        """Execute job search with typed query."""
        ...


@runtime_checkable
class PostSearchPort(Protocol):
    """Port interface for searching Post entities."""

    async def search_posts(
        self, query: PostSearchQuery
    ) -> SearchPage[PostSearchResult]:
        """Execute post search with typed query."""
        ...


@runtime_checkable
class EmployeeSearchPort(Protocol):
    """Port interface for discovering employees of a specified company."""

    async def search_employees(
        self, query: EmployeeSearchQuery
    ) -> SearchPage[EmployeeSearchResult]:
        """Execute employee search with typed query."""
        ...
