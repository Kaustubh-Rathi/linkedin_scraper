"""Deterministic and Live E2E tests for JobScraper and JobSearchScraper."""

from pathlib import Path
import pytest
from linkedin_scraper import BrowserManager, JobScraper, JobSearchScraper
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError
from linkedin_scraper.models import Job

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html"


# ===========================================================================
# Deterministic Integration Tests (Real Playwright Engine, Fixture HTML)
# ===========================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_job_search_scraper_deterministic(silent_callback):
    """
    Test JobSearchScraper end-to-end against real Playwright Chromium browser
    engine using local HTML search fixture (zero network flakiness, hard skips removed).
    """
    fixture_content = (FIXTURES_DIR / "search_jobs_results.html").read_text(encoding="utf-8")

    async with BrowserManager(headless=True) as bm:
        page = bm.page
        # Serve fixture content via Playwright route interception
        await page.route("**/jobs/search/**", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body=fixture_content,
        ))

        scraper = JobSearchScraper(bm.get_browser_port(), callback=silent_callback)
        job_urls = await scraper.search(
            keywords="Senior Python Engineer",
            location="San Francisco, CA",
            limit=5,
        )

        assert isinstance(job_urls, list)
        assert len(job_urls) == 4
        for url in job_urls:
            assert url.startswith("https://www.linkedin.com/jobs/view/")
            assert "/?" not in url  # clean_job_url removes query parameters


@pytest.mark.integration
@pytest.mark.asyncio
async def test_job_scraper_deterministic(silent_callback):
    """
    Test JobScraper end-to-end against real Playwright Chromium browser
    engine using local HTML job details fixture.
    """
    fixture_content = (FIXTURES_DIR / "job_details.html").read_text(encoding="utf-8")

    async with BrowserManager(headless=True) as bm:
        page = bm.page
        await page.route("**/jobs/view/**", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body=fixture_content,
        ))

        scraper = JobScraper(bm.get_browser_port(), callback=silent_callback)
        job = await scraper.scrape("https://www.linkedin.com/jobs/view/3891234567/")

        assert isinstance(job, Job)
        assert job.linkedin_url == "https://www.linkedin.com/jobs/view/3891234567/"
        assert job.job_title == "Software Engineer"
        assert job.company == "Acme Inc"
        assert job.company_linkedin_url == "https://www.linkedin.com/company/acme/"
        assert job.location == "San Francisco, CA"
        assert job.posted_date == "2 days ago"
        assert job.applicant_count == "100 applicants"
        assert job.job_description is not None
        assert "About the job" in job.job_description
        assert "Build great software with our team." in job.job_description


# ===========================================================================
# Explicit Live E2E Tests (Real LinkedIn Network, requires live session)
# ===========================================================================


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_job_search(browser_with_session, test_job_search_params, silent_callback):
    """Test live LinkedIn job search against production LinkedIn."""
    scraper = JobSearchScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        job_urls = await scraper.search(
            keywords=test_job_search_params["keywords"],
            location=test_job_search_params["location"],
            limit=test_job_search_params["limit"],
        )
        assert isinstance(job_urls, list)
        assert len(job_urls) > 0, "Live job search must return at least 1 job URL"
        for url in job_urls:
            assert "linkedin.com/jobs/view/" in url
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_job_scraper(browser_with_session, test_job_search_params, silent_callback):
    """Test live LinkedIn job scraping against production LinkedIn."""
    search_scraper = JobSearchScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        job_urls = await search_scraper.search(
            keywords=test_job_search_params["keywords"],
            location=test_job_search_params["location"],
            limit=1,
        )
        if not job_urls:
            pytest.skip("No live job URLs returned from LinkedIn search")

        job_scraper = JobScraper(browser_with_session.get_browser_port(), callback=silent_callback)
        job = await job_scraper.scrape(job_urls[0])

        assert isinstance(job, Job)
        assert job.linkedin_url == job_urls[0]
        assert job.job_title is not None and len(job.job_title.strip()) > 0
        assert job.company is not None and len(job.company.strip()) > 0
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
