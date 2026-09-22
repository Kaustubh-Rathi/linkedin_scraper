"""Application search service orchestrator for dependency injection and dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from linkedin_scraper.models.search_queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
    SearchQuery,
)
from linkedin_scraper.models.search_results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
    SearchPage,
)
from linkedin_scraper.ports.browser import BrowserPort

from .export import ExportFormat
from .ports import (
    CompanySearchPort,
    EmployeeSearchPort,
    JobSearchPort,
    PersonSearchPort,
    PostSearchPort,
)

# Composer registry for browser-based facade construction (dependency inversion)
_BROWSER_COMPOSER = None

def register_browser_composer(composer):
    """Register a callable that builds a LinkedInSearchFacade from a BrowserPort.

    The composer must have signature (browser: BrowserPort, url_builder: Any = None) -> LinkedInSearchFacade.
    """
    global _BROWSER_COMPOSER
    _BROWSER_COMPOSER = composer

# NOTE: The application layer depends exclusively on SearchPort abstractions.
# Composition (wiring concrete LinkedIn adapters) is provided by
# `create_default_facade` in `linkedin_scraper.adapters.search`, the
# package-level equivalent of the former `from_browser` factory.
if TYPE_CHECKING:
    from .workflow import SearchWorkflowResult


class LinkedInSearchFacade:
    """
    Unified application-level search facade that orchestrates all five search capabilities.
    
    Demonstrates Dependency Inversion Principle (DIP) by depending exclusively on SearchPort
    abstractions rather than concrete scraper/Playwright implementations.
    """

    def __init__(
        self,
        person_port: PersonSearchPort | None = None,
        company_port: CompanySearchPort | None = None,
        job_port: JobSearchPort | None = None,
        post_port: PostSearchPort | None = None,
        employee_port: EmployeeSearchPort | None = None,
    ) -> None:
        self.person_port = person_port
        self.company_port = company_port
        self.job_port = job_port
        self.post_port = post_port
        self.employee_port = employee_port

    async def search_people(
        self, query: PersonSearchQuery
    ) -> SearchPage[PersonSearchResult]:
        """Execute person search via configured PersonSearchPort."""
        if self.person_port is None:
            raise NotImplementedError("PersonSearchPort is not configured.")
        return await self.person_port.search_people(query)

    async def search_companies(
        self, query: CompanySearchQuery
    ) -> SearchPage[CompanySearchResult]:
        """Execute company search via configured CompanySearchPort."""
        if self.company_port is None:
            raise NotImplementedError("CompanySearchPort is not configured.")
        return await self.company_port.search_companies(query)

    async def search_jobs(
        self, query: JobSearchQuery
    ) -> SearchPage[JobSearchResult]:
        """Execute job search via configured JobSearchPort."""
        if self.job_port is None:
            raise NotImplementedError("JobSearchPort is not configured.")
        return await self.job_port.search_jobs(query)

    async def search_posts(
        self, query: PostSearchQuery
    ) -> SearchPage[PostSearchResult]:
        """Execute post search via configured PostSearchPort."""
        if self.post_port is None:
            raise NotImplementedError("PostSearchPort is not configured.")
        return await self.post_port.search_posts(query)

    async def search_employees(
        self, query: EmployeeSearchQuery
    ) -> SearchPage[EmployeeSearchResult]:
        """Execute employee search via configured EmployeeSearchPort."""
        if self.employee_port is None:
            raise NotImplementedError("EmployeeSearchPort is not configured.")
        return await self.employee_port.search_employees(query)

    async def search(self, query: SearchQuery[Any]) -> SearchPage[Any]:
        """
        Dynamically dispatch any typed SearchQuery to its respective search method.
        """
        if isinstance(query, PersonSearchQuery):
            return await self.search_people(query)
        elif isinstance(query, CompanySearchQuery):
            return await self.search_companies(query)
        elif isinstance(query, JobSearchQuery):
            return await self.search_jobs(query)
        elif isinstance(query, PostSearchQuery):
            return await self.search_posts(query)
        elif isinstance(query, EmployeeSearchQuery):
            return await self.search_employees(query)
        else:
            raise TypeError(f"Unsupported query type: {type(query)}")

    async def consume(
        self,
        query: SearchQuery[Any],
        max_results: int | None = None,
        page_size: int | None = None,
    ) -> list[Any]:
        """
        Consume search results across paginated pages up to max_results.
        """
        from .workflow import consume_search

        return await consume_search(
            self.search, query, max_results=max_results, page_size=page_size
        )

    async def execute_workflow(
        self,
        query: SearchQuery[Any],
        max_results: int | None = None,
        page_size: int | None = None,
        export_format: str | ExportFormat | None = None,
        export_path: str | Path | None = None,
    ) -> SearchWorkflowResult[Any]:
        """
        Execute full search workflow with pagination, limit enforcement, and optional export.
        """
        from .workflow import execute_search_workflow

        return await execute_search_workflow(
            self.search,
            query,
            max_results=max_results,
            page_size=page_size,
            export_format=export_format,
            export_path=export_path,
        )

    @classmethod
    def from_browser(cls, browser: BrowserPort, url_builder: Any = None) -> LinkedInSearchFacade:
        """Create a facade with the standard LinkedIn search adapters.

        Uses the composer registered by the adapters layer (composition root).
        """
        if _BROWSER_COMPOSER is None:
            raise RuntimeError(
                "No browser composer registered. Import `linkedin_scraper.adapters.search` "
                "to register the default LinkedIn search adapters."
            )
        return cast(LinkedInSearchFacade, _BROWSER_COMPOSER(browser, url_builder))
