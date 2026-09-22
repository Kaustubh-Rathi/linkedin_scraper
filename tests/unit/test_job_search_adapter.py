"""Unit tests for LinkedInJobSearchAdapter."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.adapters.search.job_adapter import LinkedInJobSearchAdapter
from linkedin_scraper.core.exceptions import AuthenticationError
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.search.filters import (
    DatePosted,
    EmploymentType,
    ExperienceLevel,
    JobSearchFilter,
    WorkplaceType,
)
from linkedin_scraper.search.queries import JobSearchQuery
from linkedin_scraper.search.results import SearchPage


class FakeElementPort(ElementPort):
    def __init__(self, href: Optional[str] = None, text: Optional[str] = None):
        self._href = href
        self._text = text

    async def text_content(self, timeout: float = 2000) -> Optional[str]:
        return self._text

    async def get_attribute(self, name: str, timeout: float = 2000) -> Optional[str]:
        if name == "href":
            return self._href
        return None

    async def is_visible(self, timeout: float = 1000) -> bool:
        return True

    async def click(self) -> None:
        pass


class FakeBrowserPort(BrowserPort):
    def __init__(
        self,
        current_url: str = "https://www.linkedin.com/jobs/search/",
        elements: Optional[List[ElementPort]] = None,
        should_fail_selector: bool = False,
    ):
        self._url = current_url
        self.goto_calls: List[Dict[str, Any]] = []
        self.wait_for_selector_calls: List[str] = []
        self.evaluate_calls: List[str] = []
        self._elements = elements or []
        self._should_fail_selector = should_fail_selector

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
            pass  # keep existing auth error url if specified
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
        return default

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def click(self, selector: str) -> None:
        pass

    def locator(self, selector: str) -> Any:
        mock = AsyncMock()
        mock.count = AsyncMock(return_value=0)
        mock.text_content = AsyncMock(return_value="")
        return mock


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
async def test_search_jobs_basic_flow():
    elements = [
        FakeElementPort(
            href="https://www.linkedin.com/jobs/view/1001/?refId=123",
            text="Senior Python Engineer\nAcme Corp",
        ),
        FakeElementPort(
            href="https://www.linkedin.com/jobs/view/1002/",
            text="Backend Developer",
        ),
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="python", limit=10)
    result_page = await adapter.search_jobs(query)

    assert isinstance(result_page, SearchPage)
    assert len(result_page.items) == 2
    assert result_page.items[0].job_title == "Senior Python Engineer"
    assert result_page.items[0].linkedin_url == "https://www.linkedin.com/jobs/view/1001/"
    assert result_page.items[1].job_title == "Backend Developer"
    assert result_page.items[1].linkedin_url == "https://www.linkedin.com/jobs/view/1002/"
    assert browser.goto_calls[0]["url"] == "https://www.linkedin.com/jobs/search/?keywords=python"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_query_filters_to_url():
    browser = FakeBrowserPort(elements=[])
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(
        keywords="lead engineer",
        filters=JobSearchFilter(
            location=["San Francisco, CA"],
            date_posted=DatePosted.PAST_WEEK,
            experience_levels=[ExperienceLevel.MID_SENIOR],
            employment_types=[EmploymentType.FULL_TIME],
            workplace_types=[WorkplaceType.REMOTE],
            easy_apply_only=True,
        ),
        limit=5,
    )

    await adapter.search_jobs(query)

    nav_url = browser.goto_calls[0]["url"]
    assert "keywords=lead+engineer" in nav_url or "keywords=lead%20engineer" in nav_url or "keywords=lead" in nav_url
    assert "location=San+Francisco%2C+CA" in nav_url or "location=San+Francisco" in nav_url
    assert "f_TPR=r604800" in nav_url
    assert "f_E=4" in nav_url
    assert "f_JT=F" in nav_url
    assert "f_WT=2" in nav_url
    assert "f_AL=true" in nav_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_deduplication():
    elements = [
        FakeElementPort(href="https://www.linkedin.com/jobs/view/555/?refId=a", text="Job A"),
        FakeElementPort(href="https://www.linkedin.com/jobs/view/555/?refId=b", text="Job A Duplicate"),
        FakeElementPort(href="https://www.linkedin.com/jobs/view/777/", text="Job B"),
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="dev", limit=10)
    page = await adapter.search_jobs(query)

    assert len(page.items) == 2
    assert page.items[0].linkedin_url == "https://www.linkedin.com/jobs/view/555/"
    assert page.items[1].linkedin_url == "https://www.linkedin.com/jobs/view/777/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_limit_enforcement():
    elements = [
        FakeElementPort(href=f"https://www.linkedin.com/jobs/view/{i}/", text=f"Job {i}")
        for i in range(10)
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="dev", limit=3)
    page = await adapter.search_jobs(query)

    assert len(page.items) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_empty_results():
    browser = FakeBrowserPort(should_fail_selector=True)
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="nonexistent_job_12345", limit=10)
    page = await adapter.search_jobs(query)

    assert isinstance(page, SearchPage)
    assert len(page.items) == 0
    assert page.has_more is False
    assert page.total_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_auth_error():
    browser = FakeBrowserPort(current_url="https://www.linkedin.com/login")
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="dev")
    with pytest.raises(AuthenticationError):
        await adapter.search_jobs(query)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_pagination_continuation_token():
    elements = [
        FakeElementPort(href=f"https://www.linkedin.com/jobs/view/{i}/", text=f"Job {i}")
        for i in range(25)
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInJobSearchAdapter(browser=browser)

    # limit=25 matches the 25 elements returned, so has_more=True (may be more on LinkedIn)
    query = JobSearchQuery(keywords="dev", continuation_token="25", limit=25)
    page = await adapter.search_jobs(query)

    assert browser.goto_calls[0]["url"].endswith("start=25") or "start=25" in browser.goto_calls[0]["url"]
    assert page.has_more is True
    assert page.continuation_token == "50"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_scroll_failure_handling():
    elements = [
        FakeElementPort(href="https://www.linkedin.com/jobs/view/101/", text="Job 101"),
    ]
    browser = FakeBrowserPort(elements=elements)

    async def raise_eval_err(exp, arg=None):
        raise Exception("Scroll error")

    browser.evaluate = raise_eval_err
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="dev")
    page = await adapter.search_jobs(query)
    assert len(page.items) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_jobs_skips_invalid_element_attributes():
    class BrokenElement(FakeElementPort):
        async def get_attribute(self, name: str, timeout: float = 2000) -> Optional[str]:
            raise Exception("DOM error")

    elements = [
        BrokenElement(href="https://www.linkedin.com/jobs/view/101/", text="Broken"),
        FakeElementPort(href="https://www.linkedin.com/jobs/view/102/", text="Job 102"),
    ]
    browser = FakeBrowserPort(elements=elements)
    adapter = LinkedInJobSearchAdapter(browser=browser)

    query = JobSearchQuery(keywords="dev")
    page = await adapter.search_jobs(query)
    assert len(page.items) == 1
    assert page.items[0].linkedin_url == "https://www.linkedin.com/jobs/view/102/"

