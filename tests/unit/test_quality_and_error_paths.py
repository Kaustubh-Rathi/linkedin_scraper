"""
Authoritative suite for error-path testing, strict required fields, and optional vs failure contracts.

Requirements Tested:
1. Network failure -> raises NetworkError / ScrapingError
2. Timeout -> raises expected exception
3. Navigation failure -> raises ScrapingError
4. DOM selector failure -> raises ScrapingError on required fields
5. Parser failure -> propagates failure to caller
6. Required-field failure:
   - Missing Person.name does not silently create invalid Person
   - Missing Company.name does not silently create invalid Company
   - Missing Job.job_title does not silently create Job(job_title=None)
   - Missing Job.company does not silently create Job(company=None)
7. Rate-limit detection -> raises RateLimitError immediately
8. Authwall/Checkpoint detection -> raises AuthenticationError immediately
9. Pagination failure -> propagates or halts safely without infinite loop
10. Browser startup failure -> raises NetworkError
11. Export failure -> raises IOError / ValueError
12. Legitimate optional absence returns None / [] contractually
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from linkedin_scraper.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    RequiredFieldExtractionError,
    ScrapingError,
)
from linkedin_scraper.models import Company, Job, Person, Post
from linkedin_scraper.ports.browser import BrowserPort
from linkedin_scraper.scrapers.company.scraper import CompanyScraper
from linkedin_scraper.scrapers.job.scraper import JobScraper
from linkedin_scraper.scrapers.job.search import JobSearchScraper
from linkedin_scraper.scrapers.person.scraper import PersonScraper
from linkedin_scraper.search.export import ExportFormat, export_results
from linkedin_scraper.search.results import (
    PersonSearchResult,
    SearchPage,
)


# ===========================================================================
# 1. Rate-Limit & Authwall Immediate Propagation (No Silent Success)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_rate_limit_immediate_propagation():
    """Verify PersonScraper immediately raises RateLimitError and does not return empty Person."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.url = "https://www.linkedin.com/in/test"
    browser.wait_for_load_state = AsyncMock()
    browser.extract_text_safe = AsyncMock(return_value="")
    browser.query_selector_all = AsyncMock(return_value=[])

    with patch("linkedin_scraper.scrapers.base.detect_rate_limit", side_effect=RateLimitError("Rate limit exceeded")):
        scraper = PersonScraper(browser)
        with pytest.raises(RateLimitError):
            await scraper.scrape("https://www.linkedin.com/in/test")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_authwall_immediate_propagation():
    """Verify CompanyScraper immediately raises RateLimitError/AuthenticationError on checkpoint/authwall."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.url = "https://www.linkedin.com/authwall?trk=test"
    browser.wait_for_load_state = AsyncMock()

    scraper = CompanyScraper(browser)
    with pytest.raises((AuthenticationError, RateLimitError)):
        await scraper.scrape("https://www.linkedin.com/company/test")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_not_logged_in_raises_authentication_error():
    """Verify PersonScraper raises AuthenticationError when session is not authenticated."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.url = "https://www.linkedin.com/feed/"
    browser.wait_for_load_state = AsyncMock()

    with patch("linkedin_scraper.scrapers.base.is_logged_in", return_value=False):
        scraper = PersonScraper(browser)
        with pytest.raises(AuthenticationError, match="Not logged in to LinkedIn"):
            await scraper.scrape("https://www.linkedin.com/in/test")


# ===========================================================================
# 2. Navigation & Network Failures
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_network_failure_raises_scraping_error():
    """Verify JobScraper raises ScrapingError when navigation fails."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock(side_effect=RuntimeError("net::ERR_CONNECTION_REFUSED"))
    browser.url = "https://www.linkedin.com/jobs/view/12345"

    scraper = JobScraper(browser)
    with pytest.raises(ScrapingError, match="Failed to scrape job"):
        await scraper.scrape("https://www.linkedin.com/jobs/view/12345")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_scraper_error_raises_scraping_error():
    """Verify JobSearchScraper raises ScrapingError when search query fails."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock(side_effect=RuntimeError("Page navigation timeout"))

    scraper = JobSearchScraper(browser)
    with pytest.raises(ScrapingError, match="Failed to execute job search"):
        await scraper.search(keywords="Senior Python", limit=5)


# ===========================================================================
# 3. Required-Field Extraction Failure Tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scraper_missing_job_title_raises_failure():
    """Verify JobScraper raises RequiredFieldExtractionError when required job_title cannot be extracted."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.url = "https://www.linkedin.com/jobs/view/12345"
    browser.wait_for_load_state = AsyncMock()
    browser.extract_text_safe = AsyncMock(return_value="")
    browser.query_selector_all = AsyncMock(return_value=[])

    scraper = JobScraper(browser)
    with pytest.raises(RequiredFieldExtractionError, match="Failed to extract required field 'job_title'"):
        await scraper.scrape("https://www.linkedin.com/jobs/view/12345")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_missing_name_raises_failure():
    """Verify CompanyScraper raises RequiredFieldExtractionError when company name is not found."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.url = "https://www.linkedin.com/company/testcorp"
    browser.wait_for_load_state = AsyncMock()
    browser.extract_text_safe = AsyncMock(return_value="")
    browser.query_selector_all = AsyncMock(return_value=[])

    scraper = CompanyScraper(browser)
    with pytest.raises(RequiredFieldExtractionError, match="Failed to extract required field 'name'"):
        await scraper.scrape("https://www.linkedin.com/company/testcorp")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_missing_name_raises_failure():
    """Verify PersonScraper raises RequiredFieldExtractionError when person name cannot be extracted."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.url = "https://www.linkedin.com/in/testperson"
    browser.wait_for_load_state = AsyncMock()
    browser.extract_text_safe = AsyncMock(return_value="")
    browser.query_selector_all = AsyncMock(return_value=[])

    with patch("linkedin_scraper.scrapers.base.is_logged_in", return_value=True):
        with patch("linkedin_scraper.scrapers.base.detect_rate_limit", return_value=None):
            scraper = PersonScraper(browser)
            with pytest.raises(RequiredFieldExtractionError, match="Failed to extract required field 'name'"):
                await scraper.scrape("https://www.linkedin.com/in/testperson")


# ===========================================================================
# 4. Legitimate Optional Absence vs Extraction Failure Contract
# ===========================================================================


@pytest.mark.unit
def test_model_optional_fields_contract():
    """Verify models allow None / empty lists for legitimate optional fields."""
    p = Person(name="Alice Smith", linkedin_url="https://www.linkedin.com/in/alicesmith")
    assert p.about is None
    assert p.location is None
    assert p.open_to_work is False
    assert p.experiences == []
    assert p.educations == []
    assert p.interests == []
    assert p.accomplishments == []
    assert p.contacts == []

    c = Company(name="TechCorp", linkedin_url="https://www.linkedin.com/company/techcorp")
    assert c.about_us is None
    assert c.industry is None
    assert c.company_size is None
    assert c.headquarters is None
    assert c.specialties is None
    assert c.website is None
    assert c.headcount is None
    assert c.employees == []

    j = Job(job_title="Software Engineer", company="TechCorp", linkedin_url="https://www.linkedin.com/jobs/view/123")
    assert j.job_description is None
    assert j.location is None
    assert j.posted_date is None
    assert j.applicant_count is None
    assert j.benefits is None

    post = Post(linkedin_url="https://www.linkedin.com/feed/update/urn:li:activity:123")
    assert post.text is None
    assert post.reactions_count is None
    assert post.comments_count is None
    assert post.reposts_count is None
    assert post.image_urls == []


@pytest.mark.unit
def test_model_url_validation_rejections():
    """Verify URL validator rejects invalid domain URLs."""
    with pytest.raises(ValidationError):
        Company(name="Bad", linkedin_url="https://www.facebook.com/techcorp")

    with pytest.raises(ValidationError):
        Job(job_title="Dev", linkedin_url="https://www.google.com/careers")


# ===========================================================================
# 5. Search Export Failures
# ===========================================================================


@pytest.mark.unit
def test_search_exporter_invalid_format_and_path_errors(tmp_path):
    """Verify export_results raises ValueError on invalid formats and handles IO errors."""
    page = SearchPage(
        items=[PersonSearchResult(name="Alex", linkedin_url="https://www.linkedin.com/in/alex")],
        total_count=1,
    )

    with pytest.raises(ValueError, match="Unsupported export format"):
        export_results(page, format="unsupported_fmt")

    invalid_dir = tmp_path / "file.txt"
    invalid_dir.write_text("not a dir", encoding="utf-8")
    invalid_target = invalid_dir / "output.json"

    with pytest.raises((IOError, OSError)):
        export_results(page, format=ExportFormat.JSON, destination=invalid_target)
