"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job URLs.
"""
from __future__ import annotations

import logging
from typing import Any

from ...adapters.search.job_adapter import LinkedInJobSearchAdapter
from ...callbacks import ProgressCallback
from ...core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from ...ports.browser import BrowserPort
from ...search.filters import JobSearchFilter
from ...search.queries import JobSearchQuery
from ..base import BaseScraper

logger = logging.getLogger(__name__)


class JobSearchScraper(BaseScraper):
    """
    Scraper for LinkedIn job search results.
    
    Example:
        async with BrowserManager() as browser:
            scraper = JobSearchScraper(browser.browser_port)
            job_urls = await scraper.search(
                keywords="software engineer",
                location="San Francisco",
                limit=10
            )
    """

    def __init__(
        self,
        page_or_browser: BrowserPort | Any = None,
        callback: ProgressCallback | None = None,
        *,
        page: BrowserPort | Any = None,
    throttler: Any | None = None,
    ):
        """
        Initialize job search scraper.
        
        Args:
            page_or_browser: BrowserPort instance or legacy page object
            callback: Optional progress callback
            page: Keyword argument alias for page_or_browser (backward compatibility)
        """
        super().__init__(page_or_browser, callback, page=page, throttler=throttler)
        self._adapter = LinkedInJobSearchAdapter(
            browser=self.browser, throttler=self._throttler
        )

    async def search(
        self,
        keywords: str | None = None,
        location: str | None = None,
        limit: int = 25
    ) -> list[str]:
        """
        Search for jobs on LinkedIn.
        
        Args:
            keywords: Job search keywords (e.g., "software engineer")
            location: Job location (e.g., "San Francisco, CA")
            limit: Maximum number of job URLs to return
            
        Returns:
            List of job posting URLs
        """
        logger.info("Starting job search: keywords='%s', location='%s'", keywords, location)

        search_url = self._build_search_url(keywords, location)
        await self.callback.on_start("JobSearch", search_url)
        await self.callback.on_progress("Navigated to search results", 20)

        loc_list = [location] if location else []
        query = JobSearchQuery(
            keywords=keywords,
            filters=JobSearchFilter(location=loc_list),
            limit=limit,
        )

        try:
            search_page = await self._adapter.search_jobs(query)
            job_urls = [item.linkedin_url for item in search_page.items]

            await self.callback.on_progress("Loaded job listings", 50)
            await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 90)
            await self.callback.on_progress("Search complete", 100)
            await self.callback.on_complete("JobSearch", job_urls)

            logger.info("Job search complete: found %d jobs", len(job_urls))
            return job_urls
        except (AuthenticationError, RateLimitError) as auth_or_rate_err:
            logger.error("Authentication or rate limit error during job search: %s", auth_or_rate_err)
            await self.callback.on_error(auth_or_rate_err)
            raise
        except Exception as e:
            logger.exception("Unexpected error during job search: %s", e)
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to execute job search: {e}") from e

    def _build_search_url(
        self,
        keywords: str | None = None,
        location: str | None = None
    ) -> str:
        """Build LinkedIn job search URL with parameters."""
        query = JobSearchQuery(
            keywords=keywords,
            filters=JobSearchFilter(location=[location] if location else []),
        )
        return self._adapter._url_builder.build_job_url(query)
