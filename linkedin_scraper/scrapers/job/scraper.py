"""
Job scraper for LinkedIn.

Extracts job posting information from LinkedIn job pages.
"""
import logging
from typing import Optional, Tuple
from playwright.async_api import Page

from ...models.job import Job
from ...callbacks import ProgressCallback
from ..base import BaseScraper
from .parser import (
    clean_job_url,
    looks_like_applicant_count,
    looks_like_location,
    looks_like_posted_date,
    parse_top_card_parts,
)

logger = logging.getLogger(__name__)


class JobScraper(BaseScraper):
    """
    Scraper for LinkedIn job postings.

    Example:
        async with BrowserManager() as browser:
            scraper = JobScraper(browser.page)
            job = await scraper.scrape("https://www.linkedin.com/jobs/view/123456/")
            print(job.to_json())
    """

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback)

    async def scrape(self, linkedin_url: str) -> Job:
        """
        Scrape a LinkedIn job posting.

        Args:
            linkedin_url: URL of the LinkedIn job posting

        Returns:
            Job object with scraped data
        """
        logger.info(f"Starting job scraping: {linkedin_url}")
        await self.callback.on_start("Job", linkedin_url)

        await self.navigate_and_wait(linkedin_url)
        await self.callback.on_progress("Navigated to job page", 10)

        job_title = await self._get_job_title()
        await self.callback.on_progress(f"Got job title: {job_title}", 20)

        company = await self._get_company()
        await self.callback.on_progress("Got company name", 30)

        location, posted_date, applicant_count = await self._read_top_card()
        if location is None:
            location = await self._get_location_fallback()
        await self.callback.on_progress("Got location", 40)

        if posted_date is None:
            posted_date = await self._get_posted_date_fallback()
        await self.callback.on_progress("Got posted date", 50)

        if applicant_count is None:
            applicant_count = await self._get_applicant_count_fallback()
        await self.callback.on_progress("Got applicant count", 60)

        job_description = await self._get_description()
        await self.callback.on_progress("Got job description", 80)

        company_url = await self._get_company_url()
        await self.callback.on_progress("Got company URL", 90)

        job = Job(
            linkedin_url=linkedin_url,
            job_title=job_title,
            company=company,
            company_linkedin_url=company_url,
            location=location,
            posted_date=posted_date,
            applicant_count=applicant_count,
            job_description=job_description,
        )

        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("Job", job)

        logger.info(f"Successfully scraped job: {job_title}")
        return job

    async def _read_top_card(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse location, posted date, and applicant count from the top card once."""
        try:
            container = self.page.locator(
                ".job-details-jobs-unified-top-card__primary-description-container"
            ).first
            if await container.count() > 0:
                text = await container.inner_text()
                return parse_top_card_parts(text)
        except Exception:
            pass
        return None, None, None

    async def _get_job_title(self) -> Optional[str]:
        """Extract job title from h1 heading."""
        try:
            title_elem = self.page.locator("h1").first
            await title_elem.wait_for(timeout=5000)
            title = await title_elem.inner_text()
            return title.strip()
        except Exception:
            return None

    async def _get_company(self) -> Optional[str]:
        """Extract company name from company link."""
        try:
            company_links = await self.page.locator('a[href*="/company/"]').all()
            for link in company_links:
                text = await link.inner_text()
                text = text.strip()
                if text and len(text) > 1 and not text.startswith("logo"):
                    return text
        except Exception:
            pass
        return None

    async def _get_company_url(self) -> Optional[str]:
        """Extract company LinkedIn URL."""
        try:
            company_link = self.page.locator('a[href*="/company/"]').first
            if await company_link.count() > 0:
                href = await company_link.get_attribute("href")
                if href:
                    return clean_job_url(href)
        except Exception:
            pass
        return None

    async def _get_location_fallback(self) -> Optional[str]:
        """Fallback location scan when top-card parse misses."""
        try:
            job_panel = self.page.locator("h1").first.locator("xpath=ancestor::*[5]")
            if await job_panel.count() > 0:
                text_elements = await job_panel.locator("span, div").all()
                title = await self._get_job_title()
                for elem in text_elements:
                    text = await elem.inner_text()
                    if looks_like_location(text, title):
                        return text.strip()
        except Exception:
            pass
        return None

    async def _get_posted_date_fallback(self) -> Optional[str]:
        """Fallback posted-date scan when top-card parse misses."""
        try:
            text_elements = await self.page.locator("span, div").all()
            for elem in text_elements:
                text = await elem.inner_text()
                if looks_like_posted_date(text):
                    return text.strip()
        except Exception:
            pass
        return None

    async def _get_applicant_count_fallback(self) -> Optional[str]:
        """Fallback applicant-count scan when top-card parse misses."""
        try:
            main_content = self.page.locator("main").first
            if await main_content.count() > 0:
                text_elements = await main_content.locator("span, div").all()
                for elem in text_elements:
                    text = await elem.inner_text()
                    if looks_like_applicant_count(text):
                        return text.strip()
        except Exception:
            pass
        return None

    async def _get_description(self) -> Optional[str]:
        """Extract job description from article or about section."""
        try:
            about_heading = self.page.locator('h2:has-text("About the job")').first
            if await about_heading.count() > 0:
                article = about_heading.locator("xpath=ancestor::article[1]")
                if await article.count() > 0:
                    description = await article.inner_text()
                    return description.strip()

            article = self.page.locator("article").first
            if await article.count() > 0:
                description = await article.inner_text()
                return description.strip()
        except Exception:
            pass
        return None
