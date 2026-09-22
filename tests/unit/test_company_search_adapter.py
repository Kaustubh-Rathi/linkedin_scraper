"""Unit tests for LinkedInCompanySearchAdapter."""

from typing import Any, Dict, List, Optional

import pytest

from linkedin_scraper.adapters.search.company_adapter import (
    LinkedInCompanySearchAdapter,
)
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.search.filters import CompanySearchFilter, CompanySize
from linkedin_scraper.search.queries import CompanySearchQuery
from linkedin_scraper.search.results import SearchPage


class FakeElementPort(ElementPort):
    def __init__(
        self,
        href: Optional[str] = None,
        text: Optional[str] = None,
        raise_attr_err: bool = False,
        raise_rate_limit: bool = False,
    ):
        self._href = href
        self._text = text
        self._raise_attr_err = raise_attr_err
        self._raise_rate_limit = raise_rate_limit

    async def text_content(self, timeout: float = 2000) -> Optional[str]:
        return self._text

    async def get_attribute(self, name: str, timeout: float = 2000) -> Optional[str]:
        if self._raise_rate_limit:
            raise RateLimitError("Rate limit during card attribute fetch")
        if self._raise_attr_err:
            raise Exception("DOM attribute access error")
        if name == "href":
            return self._href
        return None

    async def is_visible(self, timeout: float = 1000) -> bool:
        return True

    async def click(self) -> None:
        pass


class FakeLocator:
    """Minimal locator stand-in used for rate-limit container detection."""

    def __init__(self, count: int = 0, text: str = ""):
        self._count = count
        self._text = text

    async def count(self) -> int:
        return self._count

    async def text_content(self, timeout: float = 1000) -> str:
        return self._text

    async def inner_text(self, timeout: float = 1000) -> str:
        return self._text


class FakeBrowserPort(BrowserPort):
    def __init__(
        self,
        current_url: str = "https://www.linkedin.com/search/results/companies/",
        elements: Optional[List[ElementPort]] = None,
        should_fail_selector: bool = False,
        rate_limit_on_detect: bool = False,
        rate_limit_body_text_only: bool = False,
    ):
        self._url = current_url
        self.goto_calls: List[Dict[str, Any]] = []
        self.wait_for_selector_calls: List[str] = []
        self.evaluate_calls: List[str] = []
        self._elements = elements or []
        self._should_fail_selector = should_fail_selector
        self._rate_limit_on_detect = rate_limit_on_detect
        self._rate_limit_body_text_only = rate_limit_body_text_only

    @property
    def url(self) -> str:
        return self._url

    async def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: float = 60000,
    ) -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        if "login" in self._url or "authwall" in self._url or "checkpoint" in self._url:
            pass
        else:
            self._url = url

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 5000,
        state: str = "visible",
    ) -> None:
        self.wait_for_selector_calls.append(selector)
        if self._should_fail_selector:
            raise Exception("Selector timeout")

    async def wait_for_load_state(
        self, state: str = "domcontentloaded", timeout: float = 30000
    ) -> None:
        pass

    async def wait_for_url(
        self, predicate_or_url: Any, timeout: float = 30000
    ) -> None:
        pass

    async def wait_for_timeout(self, timeout: float) -> None:
        pass

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        self.evaluate_calls.append(expression)
        return None

    async def extract_text_safe(
        self, selector: str, default: str = "", timeout: float = 2000
    ) -> str:
        if (self._rate_limit_on_detect or self._rate_limit_body_text_only) and "body" in selector:
            return "Please slow down. Rate limit exceeded. Try again later."
        return default

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def click(self, selector: str) -> None:
        pass

    def locator(self, selector: str) -> Any:
        # The detector only inspects dedicated rate-limit containers, never the
        # whole page body, so only those selectors can produce a match.
        if self._rate_limit_on_detect and (
            "rate-limit" in selector or "rateLimit" in selector
        ):
            return FakeLocator(
                count=1, text="Too many requests. Please try again later."
            )
        return FakeLocator()


    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        return self._elements

    async def bring_to_front(self) -> None:
        pass

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        pass

    async def keyboard_press(self, key: str) -> None:
        pass


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_basic():
    elements = [
        FakeElementPort(
            href="https://www.linkedin.com/company/google/?mini=1",
            text="Google",
        ),
        FakeElementPort(
            href="https://www.linkedin.com/company/microsoft/",
            text="Microsoft",
        ),
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Technology", limit=10)
    page = await adapter.search_companies(query)

    assert isinstance(page, SearchPage)
    assert len(page.items) == 2
    assert page.items[0].name == "Google"
    assert page.items[0].linkedin_url == "https://www.linkedin.com/company/google/"
    assert page.items[1].name == "Microsoft"
    assert page.items[1].linkedin_url == "https://www.linkedin.com/company/microsoft/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_keywords():
    browser = FakeBrowserPort(elements=[])
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Artificial Intelligence")
    await adapter.search_companies(query)

    nav_url = browser.goto_calls[0]["url"]
    assert "keywords=Artificial+Intelligence" in nav_url or "keywords=Artificial%20Intelligence" in nav_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_filters():
    browser = FakeBrowserPort(elements=[])
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(
        keywords="Software",
        filters=CompanySearchFilter(
            location=["103644278"],
            industry=["96"],
            company_size=[CompanySize.SIZE_11_50, CompanySize.SIZE_51_200],
        ),
        limit=5,
    )
    await adapter.search_companies(query)

    nav_url = browser.goto_calls[0]["url"]
    assert "geoUrn" in nav_url
    assert "industry" in nav_url
    assert "companySize" in nav_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_pagination():
    elements = [
        FakeElementPort(
            href=f"https://www.linkedin.com/company/corp-{i}/",
            text=f"Company {i}",
        )
        for i in range(10)
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    # limit=10 matches element count so has_more=True (more may exist on LinkedIn)
    query = CompanySearchQuery(keywords="Tech", continuation_token="10", limit=10)
    page = await adapter.search_companies(query)

    assert "page=10" in browser.goto_calls[0]["url"] or "start=10" in browser.goto_calls[0]["url"]
    assert page.has_more is True
    assert page.continuation_token == "20"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_limit():
    elements = [
        FakeElementPort(
            href=f"https://www.linkedin.com/company/corp-{i}/",
            text=f"Company {i}",
        )
        for i in range(10)
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Tech", limit=4)
    page = await adapter.search_companies(query)

    assert len(page.items) == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_empty_results():
    browser = FakeBrowserPort(should_fail_selector=True)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="nonexistent_company_9999")
    page = await adapter.search_companies(query)

    assert isinstance(page, SearchPage)
    assert len(page.items) == 0
    assert page.total_count == 0
    assert page.has_more is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_duplicate():
    elements = [
        FakeElementPort(href="https://www.linkedin.com/company/google/?trk=1", text="Google"),
        FakeElementPort(href="https://www.linkedin.com/company/google/?trk=2", text="Google Dup"),
        FakeElementPort(href="https://www.linkedin.com/company/apple/", text="Apple"),
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Tech")
    page = await adapter.search_companies(query)

    assert len(page.items) == 2
    assert page.items[0].linkedin_url == "https://www.linkedin.com/company/google/"
    assert page.items[1].linkedin_url == "https://www.linkedin.com/company/apple/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_malformed_card():
    elements = [
        FakeElementPort(raise_attr_err=True),
        FakeElementPort(href="/school/stanford/", text="Not company"),
        FakeElementPort(href="https://www.linkedin.com/company/valid-co/", text="Valid Co"),
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Tech")
    page = await adapter.search_companies(query)

    assert len(page.items) == 1
    assert page.items[0].name == "Valid Co"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_auth():
    browser = FakeBrowserPort(current_url="https://www.linkedin.com/login")
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Tech")
    with pytest.raises(AuthenticationError):
        await adapter.search_companies(query)



@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_rate_limit():
    browser = FakeBrowserPort(rate_limit_on_detect=True)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Tech")
    with pytest.raises(RateLimitError):
        await adapter.search_companies(query)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_companies_rate_limit_body_text_only_does_not_raise():
    """Rate-limit phrases in unrelated page text must not abort the search."""
    elements = [
        FakeElementPort(href="https://www.linkedin.com/company/google/", text="Google"),
    ]
    browser = FakeBrowserPort(elements=elements, rate_limit_body_text_only=True)
    adapter = LinkedInCompanySearchAdapter(browser=browser)

    query = CompanySearchQuery(keywords="Tech")
    page = await adapter.search_companies(query)

    assert len(page.items) == 1
    assert page.items[0].name == "Google"
