"""Deterministic and live tests for CompanyScraper."""

from pathlib import Path
import pytest
from linkedin_scraper import BrowserManager, CompanyScraper
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from linkedin_scraper.models import Company

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html"


# ===========================================================================
# Deterministic Integration Tests (Real Playwright Engine, Fixture HTML)
# ===========================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_company_scraper_deterministic(silent_callback):
    """
    Test CompanyScraper end-to-end against real Playwright Chromium browser
    engine using local HTML company overview fixture.
    """
    fixture_content = (FIXTURES_DIR / "company_overview.html").read_text(encoding="utf-8")

    async with BrowserManager(headless=True) as bm:
        page = bm.page
        await page.route("**/company/**", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body=fixture_content,
        ))

        scraper = CompanyScraper(bm.get_browser_port(), callback=silent_callback)
        company = await scraper.scrape("https://www.linkedin.com/company/microsoft/")

        assert isinstance(company, Company)
        assert company.name == "Example Corp"
        assert company.linkedin_url == "https://www.linkedin.com/company/microsoft/"
        assert company.website == "https://example.com"
        assert company.industry == "Software Development"
        assert company.company_size == "1,001-5,000 employees"
        assert company.headquarters == "San Francisco, California"
        assert company.about_us is not None
        assert "We build example products" in company.about_us


# ===========================================================================
# Explicit Live E2E Tests (Real LinkedIn Network, requires live session)
# ===========================================================================


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_company_scraper_basic(browser_with_session, test_company_urls, silent_callback):
    """Test basic company scraping functionality against live LinkedIn."""
    scraper = CompanyScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        company = await scraper.scrape(test_company_urls["microsoft"])
        assert isinstance(company, Company)
        assert company.name == "Microsoft"
        assert company.linkedin_url == test_company_urls["microsoft"]
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_company_scraper_about(browser_with_session, test_company_urls, silent_callback):
    """Test about section extraction against live LinkedIn."""
    scraper = CompanyScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        company = await scraper.scrape(test_company_urls["microsoft"])
        assert company.name == "Microsoft"
        assert company.about_us is not None and len(company.about_us.strip()) > 0
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_company_scraper_overview(browser_with_session, test_company_urls, silent_callback):
    """Test company overview extraction against live LinkedIn."""
    scraper = CompanyScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        company = await scraper.scrape(test_company_urls["google"])
        assert company.name == "Google"
        assert company.linkedin_url == test_company_urls["google"]
        assert (
            company.industry is not None
            or company.company_size is not None
            or company.headquarters is not None
            or company.website is not None
        ), "Company overview metadata must be populated"
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise
