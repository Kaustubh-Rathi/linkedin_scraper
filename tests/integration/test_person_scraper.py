"""Deterministic and live integration tests for PersonScraper."""

from pathlib import Path
import pytest
from linkedin_scraper import BrowserManager, PersonScraper
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from linkedin_scraper.models import Person

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html" / "person"


# ===========================================================================
# Deterministic Integration Tests (Real Playwright Engine, Fixture HTML)
# ===========================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_person_scraper_deterministic(silent_callback):
    """
    Test PersonScraper end-to-end against real Playwright Chromium browser
    engine using local HTML fixtures across all sections.
    """
    profile_html = (FIXTURES_DIR / "person_profile.html").read_text(encoding="utf-8")
    exp_html = (FIXTURES_DIR / "person_experience.html").read_text(encoding="utf-8")
    edu_html = (FIXTURES_DIR / "person_education.html").read_text(encoding="utf-8")
    interests_html = (FIXTURES_DIR / "person_interests.html").read_text(encoding="utf-8")
    accomp_html = (FIXTURES_DIR / "person_accomplishments.html").read_text(encoding="utf-8")
    contacts_html = (FIXTURES_DIR / "person_contacts_dialog.html").read_text(encoding="utf-8")

    async with BrowserManager(headless=True) as bm:
        page = bm.page

        async def route_handler(route):
            url = route.request.url
            if "details/experience" in url:
                await route.fulfill(status=200, content_type="text/html", body=exp_html)
            elif "details/education" in url:
                await route.fulfill(status=200, content_type="text/html", body=edu_html)
            elif "details/interests" in url:
                await route.fulfill(status=200, content_type="text/html", body=interests_html)
            elif "details/" in url:
                await route.fulfill(status=200, content_type="text/html", body=accomp_html)
            elif "overlay/contact-info" in url:
                await route.fulfill(status=200, content_type="text/html", body=contacts_html)
            else:
                await route.fulfill(status=200, content_type="text/html", body=profile_html)

        await page.route("**/in/**", route_handler)

        scraper = PersonScraper(bm.get_browser_port(), callback=silent_callback)
        person = await scraper.scrape("https://www.linkedin.com/in/alex-smith-engineer/")

        assert isinstance(person, Person)
        assert person.linkedin_url == "https://www.linkedin.com/in/alex-smith-engineer/"
        assert person.name == "Alex Morgan"
        assert person.location == "San Francisco Bay Area"
        assert person.about is not None
        assert "Distributed systems engineer" in person.about
        assert person.open_to_work is True


# ===========================================================================
# Explicit Live E2E Tests (Real LinkedIn Network, requires live session)
# ===========================================================================


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_basic(browser_with_session, test_profile_urls, silent_callback):
    """Test basic person scraping functionality against live LinkedIn."""
    scraper = PersonScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        person = await scraper.scrape(test_profile_urls["bill_gates"])
        assert isinstance(person, Person)
        assert person.name == "Bill Gates"
        assert person.linkedin_url == test_profile_urls["bill_gates"]
        assert person.location is not None
        assert len(person.experiences) > 0
        assert len(person.educations) > 0
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_experiences(browser_with_session, test_profile_urls, silent_callback):
    """Test experience extraction against live LinkedIn."""
    scraper = PersonScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        person = await scraper.scrape(test_profile_urls["satya_nadella"])
        assert len(person.experiences) > 0

        # Check first experience has required fields
        exp = person.experiences[0]
        assert (
            (exp.institution_name is not None and len(exp.institution_name.strip()) > 0)
            or (exp.position_title is not None and len(exp.position_title.strip()) > 0)
        ), "Experience entry must have a non-empty institution or position title"
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_education(browser_with_session, test_profile_urls, silent_callback):
    """Test education extraction against live LinkedIn."""
    scraper = PersonScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        person = await scraper.scrape(test_profile_urls["bill_gates"])
        assert len(person.educations) > 0
        edu = person.educations[0]
        assert edu.institution_name is not None and len(edu.institution_name.strip()) > 0
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_complex_profile(browser_with_session, test_profile_urls, silent_callback):
    """Test scraping a complex profile with many experiences against live LinkedIn."""
    scraper = PersonScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        person = await scraper.scrape(test_profile_urls["reid_hoffman"])
        # Reid Hoffman has many experiences
        assert len(person.experiences) > 10
        assert person.name == "Reid Hoffman"
        assert person.about is not None
    except (AuthenticationError, RateLimitError, ScrapingError) as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise
