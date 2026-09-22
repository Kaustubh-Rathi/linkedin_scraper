"""Unit tests for JobScraper and JobSearchScraper."""

from unittest.mock import AsyncMock
import pytest

from linkedin_scraper.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    RequiredFieldExtractionError,
    ScrapingError,
)
from linkedin_scraper.models.job import Job
from linkedin_scraper.scrapers.job.scraper import JobScraper
from linkedin_scraper.scrapers.job.search import JobSearchScraper
from linkedin_scraper.search.results import JobSearchResult, SearchPage


class MockElementForJob:
    def __init__(self, href=None, text=""):
        self._href = href
        self._text = text

    async def get_attribute(self, name, timeout=2000):
        if name == "href":
            return self._href
        return None

    async def text_content(self, timeout=2000):
        return self._text

    async def inner_text(self):
        return self._text


class MockBrowserForJob:
    def __init__(self, url="https://www.linkedin.com/jobs/view/99999/", extract_map=None, elements_map=None):
        self.url = url
        self._extract_map = extract_map or {}
        self._elements_map = elements_map or {}
        self.goto_calls = []

    async def goto(self, url, **kw):
        self.goto_calls.append(url)

    async def wait_for_load_state(self, *a, **kw):
        pass

    async def wait_for_selector(self, *a, **kw):
        pass

    async def wait_for_timeout(self, *a, **kw):
        pass

    async def evaluate(self, script, arg=None):
        return "complete"

    async def query_selector_all(self, selector):
        for k, v in self._elements_map.items():
            if k in selector or selector in k:
                return v
        return []

    async def extract_text_safe(self, selector, default="", timeout=2000):
        return self._extract_map.get(selector, default)


# ---------------------------------------------------------------------------
# JobSearchScraper Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_scraper_search_success():
    browser = MockBrowserForJob()
    scraper = JobSearchScraper(browser)

    mock_page = SearchPage[JobSearchResult](
        items=[
            JobSearchResult(
                job_title="Software Engineer",
                company_name="Acme",
                location="San Francisco, CA",
                linkedin_url="https://www.linkedin.com/jobs/view/12345/",
            )
        ],
        total_count=1,
        continuation_token=None,
        has_more=False,
    )

    scraper._adapter.search_jobs = AsyncMock(return_value=mock_page)

    job_urls = await scraper.search(keywords="Python", location="SF", limit=1)
    assert job_urls == ["https://www.linkedin.com/jobs/view/12345/"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_scraper_propagates_auth_error():
    browser = MockBrowserForJob()
    scraper = JobSearchScraper(browser)
    scraper._adapter.search_jobs = AsyncMock(side_effect=AuthenticationError("Logged out"))

    with pytest.raises(AuthenticationError):
        await scraper.search(keywords="Python")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_scraper_propagates_rate_limit_error():
    browser = MockBrowserForJob()
    scraper = JobSearchScraper(browser)
    scraper._adapter.search_jobs = AsyncMock(side_effect=RateLimitError("Rate limited"))

    with pytest.raises(RateLimitError):
        await scraper.search(keywords="Python")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_scraper_wraps_unexpected_error():
    browser = MockBrowserForJob()
    scraper = JobSearchScraper(browser)
    scraper._adapter.search_jobs = AsyncMock(side_effect=RuntimeError("Browser crashed"))

    with pytest.raises(ScrapingError, match="Failed to execute job search"):
        await scraper.search(keywords="Python")


# ---------------------------------------------------------------------------
# JobScraper Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_scrape_success():
    company_link = MockElementForJob(href="https://www.linkedin.com/company/dataflow/", text="DataFlow Inc")
    browser = MockBrowserForJob(
        extract_map={
            "h1": "Staff Data Engineer",
            "a[href*='/company/']": "DataFlow Inc",
            ".jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__primary-description-container": "Austin, TX · 1 week ago · 45 applicants",
            ".jobs-description__container, .jobs-box__html": "Job description text content.",
        },
        elements_map={
            "/company/": [company_link],
        },
    )

    scraper = JobScraper(browser)
    job = await scraper.scrape("https://www.linkedin.com/jobs/view/99999/")

    assert isinstance(job, Job)
    assert job.job_title == "Staff Data Engineer"
    assert job.company == "DataFlow Inc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_propagates_rate_limit():
    browser = MockBrowserForJob()

    async def raise_rate(url, **kw):
        raise RateLimitError("Rate limit hit")

    browser.goto = raise_rate

    scraper = JobScraper(browser)
    with pytest.raises(RateLimitError):
        await scraper.scrape("https://www.linkedin.com/jobs/view/99999/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_wraps_unexpected_error():
    browser = MockBrowserForJob()

    async def raise_crash(url, **kw):
        raise RuntimeError("Connection reset")

    browser.goto = raise_crash

    scraper = JobScraper(browser)
    with pytest.raises(ScrapingError, match="Failed to scrape job"):
        await scraper.scrape("https://www.linkedin.com/jobs/view/99999/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_missing_required_job_title():
    browser = MockBrowserForJob(
        extract_map={"h1": ""},
    )
    scraper = JobScraper(browser)
    with pytest.raises(RequiredFieldExtractionError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/jobs/view/99999/")
    assert exc_info.value.field_name == "job_title"
    assert exc_info.value.entity_url == "https://www.linkedin.com/jobs/view/99999/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_missing_linkedin_url():
    browser = MockBrowserForJob()
    scraper = JobScraper(browser)
    with pytest.raises(RequiredFieldExtractionError) as exc_info:
        await scraper.scrape("")
    assert exc_info.value.field_name == "linkedin_url"
