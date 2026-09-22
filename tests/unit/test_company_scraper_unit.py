"""Unit tests for CompanyScraper and CompanyPostsScraper."""

import pytest

from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from linkedin_scraper.models.company import Company
from linkedin_scraper.models.post import Post
from linkedin_scraper.scrapers.company.posts import CompanyPostsScraper
from linkedin_scraper.scrapers.company.scraper import CompanyScraper


class MockBrowserForCompany:
    def __init__(self, url="https://www.linkedin.com/company/acme-corp/", extract_map=None, eval_results=None):
        self.url = url
        self._extract_map = extract_map or {}
        self._eval_results = list(eval_results or [])
        self.goto_calls = []

    async def goto(self, url, **kw):
        self.goto_calls.append(url)

    async def wait_for_load_state(self, *a, **kw):
        pass

    async def wait_for_selector(self, *a, **kw):
        pass

    async def wait_for_timeout(self, *a, **kw):
        pass

    async def query_selector_all(self, selector):
        return []

    async def extract_text_safe(self, selector, default="", timeout=2000):
        return self._extract_map.get(selector, default)

    async def evaluate(self, script, arg=None):
        if self._eval_results:
            return self._eval_results.pop(0)
        return True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_scrape_success():
    browser = MockBrowserForCompany(extract_map={"h1": "Acme Corp"})
    scraper = CompanyScraper(browser)
    company = await scraper.scrape("https://www.linkedin.com/company/acme-corp/")

    assert isinstance(company, Company)
    assert company.name == "Acme Corp"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_propagates_auth_error():
    browser = MockBrowserForCompany()

    async def raise_auth(url, **kw):
        raise AuthenticationError("Logged out")

    browser.goto = raise_auth
    scraper = CompanyScraper(browser)
    with pytest.raises(AuthenticationError):
        await scraper.scrape("https://www.linkedin.com/company/acme-corp/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_wraps_unexpected_error():
    browser = MockBrowserForCompany()

    async def raise_crash(url, **kw):
        raise RuntimeError("Browser crashed")

    browser.goto = raise_crash
    scraper = CompanyScraper(browser)
    with pytest.raises(ScrapingError, match="Failed to scrape company profile"):
        await scraper.scrape("https://www.linkedin.com/company/acme-corp/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_posts_scraper_success():
    browser = MockBrowserForCompany(
        eval_results=[
            None,  # trigger lazy load 1
            None,  # trigger lazy load 2 (window.scrollTo)
            True,  # has_posts check (includes urn:li:activity:)
            [{"urn": "urn:li:activity:123", "author_name": "Acme Corp", "text": "Post text", "time_str": "1d", "reactions_count": 10}],
        ]
    )

    scraper = CompanyPostsScraper(browser)
    posts = await scraper.scrape("https://www.linkedin.com/company/acme-corp/", limit=1)

    assert isinstance(posts, list)
    assert len(posts) == 1
    assert isinstance(posts[0], Post)
    assert posts[0].urn == "urn:li:activity:123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_posts_scraper_propagates_rate_limit():
    browser = MockBrowserForCompany()

    async def raise_rate(url, **kw):
        raise RateLimitError("Rate limited")

    browser.goto = raise_rate
    scraper = CompanyPostsScraper(browser)
    with pytest.raises(RateLimitError):
        await scraper.scrape("https://www.linkedin.com/company/acme-corp/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_posts_scraper_wraps_unexpected_error():
    browser = MockBrowserForCompany()

    async def raise_crash(url, **kw):
        raise RuntimeError("Browser disconnected")

    browser.goto = raise_crash
    scraper = CompanyPostsScraper(browser)
    with pytest.raises(ScrapingError, match="Failed to scrape company posts"):
        await scraper.scrape("https://www.linkedin.com/company/acme-corp/")
