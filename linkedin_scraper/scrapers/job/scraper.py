"""

Job scraper for LinkedIn.



Extracts job posting information from LinkedIn job pages.

"""

from __future__ import annotations

import logging
from typing import Any

from ...callbacks import ProgressCallback
from ...core.exceptions import (
    AuthenticationError,
    RateLimitError,
    RequiredFieldExtractionError,
    ScrapingError,
)
from ...models.job import Job
from ...parsers.job import (
    clean_job_url,
    looks_like_applicant_count,
    looks_like_location,
    looks_like_posted_date,
    parse_job_posting,
    parse_top_card_parts,
)
from ...ports.browser import BrowserPort
from ..base import BaseScraper

logger = logging.getLogger(__name__)





class JobScraper(BaseScraper):

    """

    Scraper for LinkedIn job postings.



    Example:

        async with BrowserManager() as browser:

            scraper = JobScraper(browser.browser_port)

            job = await scraper.scrape("https://www.linkedin.com/jobs/view/123456/")

            print(job.to_json())

    """



    def __init__(

        self,

        page_or_browser: BrowserPort | Any = None,

        callback: ProgressCallback | None = None,

        *,

        page: BrowserPort | Any = None,

    ):

        """

        Initialize job scraper.



        Args:

            page_or_browser: BrowserPort instance or legacy page object

            callback: Optional progress callback

            page: Keyword argument alias for page_or_browser (for backward compatibility)

        """

        super().__init__(page_or_browser, callback, page=page)



    async def scrape(self, linkedin_url: str) -> Job:

        """

        Scrape a LinkedIn job posting.



        Args:

            linkedin_url: URL of the LinkedIn job posting



        Returns:

            Job object with scraped data

        """

        if not linkedin_url:

            raise RequiredFieldExtractionError(field_name="linkedin_url", entity_url=linkedin_url)



        logger.info(f"Starting job scraping: {linkedin_url}")

        await self.callback.on_start("Job", linkedin_url)



        try:

            await self.navigate_and_wait(linkedin_url)

            await self.callback.on_progress("Navigated to job page", 10)



            job_title = await self._get_job_title()

            if not job_title:

                logger.error("Failed to extract required field 'job_title' for job: %s", linkedin_url)

                raise RequiredFieldExtractionError(field_name="job_title", entity_url=linkedin_url)

            await self.callback.on_progress(f"Got job title: {job_title}", 20)



            company = await self._get_company()

            await self.callback.on_progress("Got company name", 30)



            location, posted_date, applicant_count = await self._read_top_card()

            if location is None:

                logger.debug("Location not found in top card; attempting fallback scan")

                location = await self._get_location_fallback()

            await self.callback.on_progress("Got location", 40)



            if posted_date is None:

                logger.debug("Posted date not found in top card; attempting fallback scan")

                posted_date = await self._get_posted_date_fallback()

            await self.callback.on_progress("Got posted date", 50)



            if applicant_count is None:

                logger.debug("Applicant count not found in top card; attempting fallback scan")

                applicant_count = await self._get_applicant_count_fallback()

            await self.callback.on_progress("Got applicant count", 60)



            job_description = await self._get_description()

            await self.callback.on_progress("Got job description", 80)



            company_url = await self._get_company_url()

            await self.callback.on_progress("Got company URL", 90)



            job = parse_job_posting(

                linkedin_url=linkedin_url,

                job_title=job_title,

                company=company,

                company_linkedin_url=company_url,

                location_fallback=location,

                posted_date_fallback=posted_date,

                applicant_count_fallback=applicant_count,

                job_description=job_description,

            )



            await self.callback.on_progress("Scraping complete", 100)

            await self.callback.on_complete("Job", job)



            logger.info("Successfully scraped job: %s", job_title)

            return job

        except (AuthenticationError, RateLimitError, RequiredFieldExtractionError) as direct_err:

            logger.error("Error while scraping job %s: %s", linkedin_url, direct_err)

            await self.callback.on_error(direct_err)

            raise

        except Exception as e:

            logger.exception("Unexpected error while scraping job %s: %s", linkedin_url, e)

            await self.callback.on_error(e)

            raise ScrapingError(f"Failed to scrape job: {e}") from e



    async def _read_top_card(self) -> tuple[str | None, str | None, str | None]:

        """Parse location, posted date, and applicant count from the job top card."""

        # 1. Try legacy/modern CSS class selectors first

        SELECTORS = [

            ".job-details-jobs-unified-top-card__primary-description-container",

            ".job-details-jobs-unified-top-card__primary-description",

            ".jobs-unified-top-card__subtitle-primary-grouping",

            ".jobs-unified-top-card__metadata-container",

        ]

        for sel in SELECTORS:

            text = await self.browser.extract_text_safe(sel, default="")

            if text and text.strip():

                result = parse_top_card_parts(text)

                if any(r is not None for r in result):

                    return result



        # 2. JS top-card scanning across leaf elements

        try:

            card_info = await self.browser.evaluate("""() => {

                const title = (document.title || '').split(' | ')[0].trim();

                const SKIP = new Set(['·', '•', '-', '|', 'apply', 'save', 'easy apply', 'promoted by hirer', '']);

                const POSTED_MARKERS = ['ago', 'day', 'week', 'hour', 'month', 'year'];

                const APPLICANT_MARKERS = ['applicant', 'people clicked', 'applied'];

                const LOC_MARKERS = [',', 'remote', 'united states', 'hybrid', 'on-site'];



                let loc = null;

                let date = null;

                let apps = null;



                const all = document.querySelectorAll('div, p, span, li');

                for (const el of all) {

                    if (el.children.length > 0) continue;

                    const t = (el.innerText || el.textContent || '').trim();

                    if (!t || t.length > 80 || SKIP.has(t.toLowerCase())) continue;

                    if (title && t.toLowerCase() === title.toLowerCase()) continue;



                    const lo = t.toLowerCase();

                    if (!apps && APPLICANT_MARKERS.some(m => lo.includes(m))) {

                        apps = t;

                    } else if (!date && POSTED_MARKERS.some(m => lo.includes(m))) {

                        date = t;

                    } else if (!loc && LOC_MARKERS.some(m => lo.includes(m)) && !lo.startsWith('$') && t.length > 3) {

                        loc = t;

                    }

                }

                return [loc, date, apps];

            }""")

            if isinstance(card_info, list) and len(card_info) == 3:

                return (

                    card_info[0] or None,

                    card_info[1] or None,

                    card_info[2] or None,

                )

        except Exception as exc:

            logger.debug("JS top-card leaf extraction failed: %s", exc)



        return None, None, None



    async def _get_job_title(self) -> str | None:

        """Extract job title from h1 heading, document title, or top card."""

        title = await self.browser.extract_text_safe("h1", default="")

        title = title.strip()

        if title:

            return title



        # Fallback to document.title extraction

        try:

            doc_title = await self.browser.evaluate("() => document.title")

            title_text = doc_title.strip() if isinstance(doc_title, str) else ""

            if title_text and title_text.lower() not in ("complete", "interactive", "loading"):

                # Titles look like "<Job Title> | LinkedIn"; skip placeholders

                # that carry no job title information.

                first_part = title_text.split(" | ")[0].strip()

                if first_part and first_part.lower() not in ("linkedin", "sign in", "jobs"):

                    return first_part

        except Exception as exc:

            logger.debug("JS title extraction failed: %s", exc)



        return None



    async def _get_company(self) -> str | None:

        """Extract company name from company link."""

        company_links = await self.browser.query_selector_all('a[href*="/company/"]')

        for link in company_links:

            text = (await link.inner_text()).strip()

            if text and len(text) > 1 and not text.startswith("logo"):

                return text

        return None



    async def _get_company_url(self) -> str | None:

        """Extract company LinkedIn URL."""

        company_links = await self.browser.query_selector_all('a[href*="/company/"]')

        if company_links:

            href = await company_links[0].get_attribute("href")

            if href:

                return clean_job_url(href)

        return None



    async def _get_location_fallback(self) -> str | None:

        """Fallback location scan when top-card parse misses."""

        title = await self._get_job_title()

        elements = await self.browser.query_selector_all("main span, main div")

        if not elements:

            elements = await self.browser.query_selector_all("span, div")

        for elem in elements:

            text = (await elem.inner_text()).strip()

            if looks_like_location(text, title):

                return text

        return None



    async def _get_posted_date_fallback(self) -> str | None:

        """Fallback posted-date scan when top-card parse misses."""

        elements = await self.browser.query_selector_all("main span, main div")

        if not elements:

            elements = await self.browser.query_selector_all("span, div")

        for elem in elements:

            text = (await elem.inner_text()).strip()

            if looks_like_posted_date(text):

                return text

        return None



    async def _get_applicant_count_fallback(self) -> str | None:

        """Fallback applicant-count scan when top-card parse misses."""

        elements = await self.browser.query_selector_all("main span, main div")

        if not elements:

            elements = await self.browser.query_selector_all("span, div")

        for elem in elements:

            text = (await elem.inner_text()).strip()

            if looks_like_applicant_count(text):

                return text

        return None



    async def _get_description(self) -> str | None:

        """Extract job description from article, about the job section, or content div."""

        # 1. Modern SDUI 'About the job' heading extraction via JS

        try:

            desc = await self.browser.evaluate("""() => {

                for (const h of document.querySelectorAll('h2, h3, h4')) {

                    const txt = (h.innerText || h.textContent || '').trim().toLowerCase();

                    if (txt.includes('about the job') || txt === 'job description' || txt === 'about this job') {

                        let sib = h.nextElementSibling;

                        if (!sib && h.parentElement) {

                            sib = h.parentElement.nextElementSibling;

                        }

                                                if (sib) {

                            const heading = (h.innerText || h.textContent || '').trim();

                            const content = (sib.innerText || sib.textContent || '').trim();

                            const combined = heading + '

' + content;

                            if (combined.length > 30) {

                                return combined;

                            }

                        }

                    }

                }

                return null;

            }""")

            description_text = str(desc).strip() if desc is not None else ""

            if description_text:

                return description_text

        except Exception as exc:

            logger.debug("JS evaluation for job description failed: %s", exc)



        # 2. Legacy article fallback

        articles = await self.browser.query_selector_all("article")

        if articles:

            for art in articles:

                text = (await art.inner_text()).strip()

                if text:

                    return text



        # 3. Class selector fallback

        desc = await self.browser.extract_text_safe(

            ".jobs-description__content, .jobs-box__html-content, #job-details",

            default="",

        )

        desc = desc.strip()

        return desc if desc else None

