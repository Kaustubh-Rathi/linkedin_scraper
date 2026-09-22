from unittest.mock import AsyncMock, MagicMock
import pytest

from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError

from linkedin_scraper.scrapers.base import BaseScraper


class MockBrowserForBase:
    def __init__(self, url="https://www.linkedin.com/feed/", elements=None, extract_val=""):
        self.url = url
        self._elements = elements or []
        self._extract_val = extract_val
        self.goto_calls = []
        self.focus_called = False
        self.wait_selector_calls = []

    async def goto(self, url, **kw):
        self.goto_calls.append(url)

    async def wait_for_load_state(self, *a, **kw):
        pass

    async def wait_for_selector(self, selector, **kw):
        self.wait_selector_calls.append(selector)

    async def wait_for_timeout(self, *a, **kw):
        pass

    async def evaluate(self, script, arg=None):
        return self.url != "https://www.linkedin.com/login"

    async def query_selector_all(self, selector):
        return self._elements

    async def extract_text_safe(self, selector, default="", timeout=2000):
        return self._extract_val or default

    async def bring_to_front(self):
        pass

    async def focus(self, selector):
        self.focus_called = True


class MockElementForBase:
    def __init__(self, attr_val=None):
        self._attr_val = attr_val

    async def get_attribute(self, name, timeout=2000):
        return self._attr_val


class ConcreteScraper(BaseScraper):
    async def scrape(self, linkedin_url: str):
        return {"scraped": linkedin_url}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_ensure_logged_in_success():
    browser = MockBrowserForBase(url="https://www.linkedin.com/feed/")
    scraper = ConcreteScraper(browser)
    await scraper.ensure_logged_in()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_ensure_logged_in_raises_when_logged_out():
    browser = MockBrowserForBase(url="https://www.linkedin.com/login")
    scraper = ConcreteScraper(browser)
    with pytest.raises(AuthenticationError, match="Not logged in to LinkedIn"):
        await scraper.ensure_logged_in()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_check_rate_limit():
    browser = MockBrowserForBase(url="https://www.linkedin.com/feed")
    scraper = ConcreteScraper(browser)
    await scraper.check_rate_limit()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_safe_extract_text():
    browser = MockBrowserForBase(extract_val="Heading 1")
    scraper = ConcreteScraper(browser)
    text = await scraper.safe_extract_text("h1", default="default")
    assert text == "Heading 1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_get_attribute_safe():
    el = MockElementForBase(attr_val="https://example.com")
    browser = MockBrowserForBase(elements=[el])
    scraper = ConcreteScraper(browser)
    attr = await scraper.get_attribute_safe("a", "href")
    assert attr == "https://example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_get_attribute_safe_empty():
    browser = MockBrowserForBase(elements=[])
    scraper = ConcreteScraper(browser)
    attr = await scraper.get_attribute_safe(".missing", "href")
    assert attr == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_wait_and_focus():
    browser = MockBrowserForBase()
    scraper = ConcreteScraper(browser)
    await scraper.wait_and_focus(0.01)


@pytest.mark.unit
def test_base_scraper_init_validation():
    with pytest.raises(ValueError, match="Either page_or_browser or page"):
        BaseScraper()


@pytest.mark.unit
def test_base_scraper_init_with_browser_manager():
    mock_mgr = MagicMock(spec=["get_browser_port"])
    mock_port = MagicMock()
    mock_mgr.get_browser_port.return_value = mock_port
    scraper = BaseScraper(mock_mgr)
    assert scraper.browser == mock_port



@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_get_attribute_safe_browser_branch():
    el = MockElementForBase(attr_val="val123")
    browser = MockBrowserForBase(elements=[el])
    scraper = ConcreteScraper(browser)
    val = await scraper.get_attribute_safe(".item", "data-id")
    assert val == "val123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_get_attribute_safe_propagates_rate_limit():
    browser = MagicMock(spec=["locator"])
    loc = MagicMock()
    loc.first.get_attribute = AsyncMock(side_effect=RateLimitError("Rate limit!"))
    browser.locator.return_value = loc
    scraper = ConcreteScraper(browser)
    with pytest.raises(RateLimitError):
        await scraper.get_attribute_safe(".item", "href")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_wait_and_focus_exception():
    browser = MagicMock()
    browser.bring_to_front = AsyncMock(side_effect=RuntimeError("Cannot focus"))
    scraper = ConcreteScraper(browser)
    # Should not raise
    await scraper.wait_and_focus(0.01)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_scraper_wait_for_detail_section_fallback():
    browser = MockBrowserForBase()
    scraper = ConcreteScraper(browser)
    await scraper.wait_for_detail_section("Experience")
    assert len(browser.wait_selector_calls) >= 1

