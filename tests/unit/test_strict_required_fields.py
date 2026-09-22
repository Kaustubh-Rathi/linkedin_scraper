"""Deterministic fixture tests verifying strict required field contracts.

Covers:
1. Valid required name -> Success
2. Missing required name -> RequiredFieldExtractionError with field_name and entity_url
3. Browser failure -> ScrapingError with original cause preserved
4. Genuinely optional fields missing -> Valid absence
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from bs4 import BeautifulSoup

from linkedin_scraper import CompanyScraper, PersonScraper, JobScraper
from linkedin_scraper.core.exceptions import (
    RequiredFieldExtractionError,
    ScrapingError,
    AuthenticationError,
    RateLimitError,
)
from linkedin_scraper.models import Company, Person
from .test_person_characterization import PersonFixtureBrowser
from .test_company_characterization import CompanyFixtureBrowser


def _make_person_browser(profile_html: str, empty_subpages: bool = False) -> PersonFixtureBrowser:
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/satyanadella/")
    browser._fixtures["profile"] = profile_html
    if empty_subpages:
        empty_html = (
            "<html><body><header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>"
            "<main><div>Nothing to see here</div></main></body></html>"
        )
        browser._fixtures["experience"] = empty_html
        browser._fixtures["education"] = empty_html
        browser._fixtures["contacts"] = empty_html
        browser._fixtures["accomplishments"] = empty_html
        browser._fixtures["interests"] = empty_html
    browser._current_soup = BeautifulSoup(profile_html, "html.parser")
    return browser



# ===========================================================================
# 1. Person Strict Required Field Contract
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_valid_name_h1_success():
    """Valid h1 name extracts cleanly and produces a Person instance."""
    html = """
    <html><body>
      <header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>
      <main>
        <h1>Satya Nadella</h1>
        <div>Chairman and CEO at Microsoft</div>
      </main>
    </body></html>
    """
    browser = _make_person_browser(html)
    scraper = PersonScraper(browser)

    person = await scraper.scrape("https://www.linkedin.com/in/satyanadella/")
    assert isinstance(person, Person)
    assert person.name == "Satya Nadella"
    assert person.linkedin_url == "https://www.linkedin.com/in/satyanadella/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_valid_name_h2_fallback_success():
    """When h1 is empty, fallback h2 candidate extracts valid name."""
    html = """
    <html><body>
      <header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>
      <main>
        <h1></h1>
        <h2>Satya Nadella</h2>
      </main>
    </body></html>
    """
    browser = _make_person_browser(html)
    scraper = PersonScraper(browser)

    person = await scraper.scrape("https://www.linkedin.com/in/satyanadella/")
    assert isinstance(person, Person)
    assert person.name == "Satya Nadella"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_missing_required_name_raises_typed_error():
    """When no name can be extracted, raises RequiredFieldExtractionError."""
    html = """
    <html><body>
      <header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>
      <main>
        <div>No headings or name here</div>
      </main>
    </body></html>
    """
    browser = _make_person_browser(html)
    scraper = PersonScraper(browser)

    with pytest.raises(RequiredFieldExtractionError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/in/satyanadella/")

    err = exc_info.value
    assert err.field_name == "name"
    assert err.entity_url == "https://www.linkedin.com/in/satyanadella/"
    assert "name" in str(err)
    assert "https://www.linkedin.com/in/satyanadella/" in str(err)
    assert isinstance(err, ScrapingError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_browser_failure_preserves_cause():
    """When a browser error occurs, raises ScrapingError preserving original cause."""
    browser = PersonFixtureBrowser()
    original_err = RuntimeError("Browser connection crashed")
    browser.goto = AsyncMock(side_effect=original_err)

    scraper = PersonScraper(browser)

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/in/satyanadella/")

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "Browser connection crashed" in str(exc_info.value.__cause__)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_optional_fields_missing_valid_absence():
    """Genuinely optional fields (about, location, open_to_work, experiences) default cleanly."""
    html = """
    <html><body>
      <header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>
      <main>
        <h1>Satya Nadella</h1>
      </main>
    </body></html>
    """
    browser = _make_person_browser(html, empty_subpages=True)
    scraper = PersonScraper(browser)

    person = await scraper.scrape("https://www.linkedin.com/in/satyanadella/")
    assert person.name == "Satya Nadella"
    assert person.about is None
    assert person.location is None
    assert person.open_to_work is False
    assert person.experiences == []
    assert person.educations == []
    assert person.interests == []
    assert person.accomplishments == []
    assert person.contacts == []


# ===========================================================================
# 2. Company Strict Required Field Contract
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_valid_name_h1_success():
    """Valid company h1 name extracts cleanly."""
    html = """
    <html><body>
      <main>
        <h1>Microsoft</h1>
      </main>
    </body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/microsoft/")
    assert isinstance(company, Company)
    assert company.name == "Microsoft"
    assert company.linkedin_url == "https://www.linkedin.com/company/microsoft/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_missing_required_name_raises_typed_error():
    """When company h1 is missing or whitespace, raises RequiredFieldExtractionError."""
    html = """
    <html><body>
      <main>
        <p>No h1 company heading</p>
      </main>
    </body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    with pytest.raises(RequiredFieldExtractionError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/company/microsoft/")

    err = exc_info.value
    assert err.field_name == "name"
    assert err.entity_url == "https://www.linkedin.com/company/microsoft/"
    assert "name" in str(err)
    assert isinstance(err, ScrapingError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_browser_failure_preserves_cause():
    """When a browser error occurs during company scraping, preserves cause."""
    browser = CompanyFixtureBrowser("<html><body><main><h1>Microsoft</h1></main></body></html>")
    original_err = ConnectionResetError("Remote host closed connection")
    browser.goto = AsyncMock(side_effect=original_err)

    scraper = CompanyScraper(browser)

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/company/microsoft/")

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, ConnectionResetError)
    assert "Remote host closed connection" in str(exc_info.value.__cause__)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_optional_fields_missing_valid_absence():
    """Optional fields (about_us, website, phone, headquarters, etc.) remain None."""
    html = """
    <html><body>
      <main>
        <h1>Microsoft</h1>
      </main>
    </body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/microsoft/")
    assert company.name == "Microsoft"
    assert company.about_us is None
    assert company.website is None
    assert company.phone is None
    assert company.headquarters is None
    assert company.founded is None
    assert company.industry is None
    assert company.company_type is None
    assert company.company_size is None
    assert company.specialties is None
    assert company.employees == []
    assert company.showcase_pages == []
    assert company.affiliated_companies == []


# ===========================================================================
# 3. Direct RateLimit and Auth Pass-Through Verification
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_rate_limit_and_auth_passthrough():
    """AuthenticationError and RateLimitError are re-raised typed without masking."""
    browser = PersonFixtureBrowser()
    browser.goto = AsyncMock(side_effect=RateLimitError("Rate limit hit", suggested_wait_time=300))

    scraper = PersonScraper(browser)
    with pytest.raises(RateLimitError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/in/satyanadella/")
    assert exc_info.value.suggested_wait_time == 300

    browser.goto = AsyncMock(side_effect=AuthenticationError("Session expired"))
    with pytest.raises(AuthenticationError):
        await scraper.scrape("https://www.linkedin.com/in/satyanadella/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_rate_limit_and_auth_passthrough():
    """AuthenticationError and RateLimitError are re-raised typed without masking."""
    browser = CompanyFixtureBrowser("<html><body><main><h1>Microsoft</h1></main></body></html>")
    browser.goto = AsyncMock(side_effect=RateLimitError("Rate limit hit", suggested_wait_time=600))

    scraper = CompanyScraper(browser)
    with pytest.raises(RateLimitError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/company/microsoft/")
    assert exc_info.value.suggested_wait_time == 600

    browser.goto = AsyncMock(side_effect=AuthenticationError("Auth challenge"))
    with pytest.raises(AuthenticationError):
        await scraper.scrape("https://www.linkedin.com/company/microsoft/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_rate_limit_and_auth_passthrough():
    """AuthenticationError and RateLimitError are re-raised typed without masking in JobScraper."""
    class SimpleJobBrowser:
        url = "https://www.linkedin.com/jobs/view/12345/"

        async def goto(self, url, **kw):
            pass

        async def extract_text_safe(self, sel, default="", timeout=2000, **kw):
            return "Software Engineer" if sel == "h1" else ""

        async def query_selector_all(self, sel):
            return []

    browser = SimpleJobBrowser()
    browser.goto = AsyncMock(side_effect=RateLimitError("Job rate limit", suggested_wait_time=900))

    scraper = JobScraper(browser)
    with pytest.raises(RateLimitError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/jobs/view/12345/")
    assert exc_info.value.suggested_wait_time == 900

    browser.goto = AsyncMock(side_effect=AuthenticationError("Job authwall"))
    with pytest.raises(AuthenticationError):
        await scraper.scrape("https://www.linkedin.com/jobs/view/12345/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_missing_required_title_raises_typed_error():
    """Missing job title produces explicit RequiredFieldExtractionError with field_name and entity_url."""
    class EmptyTitleJobBrowser:
        url = "https://www.linkedin.com/jobs/view/12345/"

        async def goto(self, url, **kw):
            pass

        async def extract_text_safe(self, sel, default="", timeout=2000, **kw):
            return ""

        async def query_selector_all(self, sel):
            return []

    browser = EmptyTitleJobBrowser()
    scraper = JobScraper(browser)

    with pytest.raises(RequiredFieldExtractionError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/jobs/view/12345/")

    err = exc_info.value
    assert err.field_name == "job_title"
    assert err.entity_url == "https://www.linkedin.com/jobs/view/12345/"
    assert isinstance(err, ScrapingError)
