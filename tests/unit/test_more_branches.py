"""Targeted branch coverage tests for rate limiting, interests, and search adapters."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from linkedin_scraper.core.exceptions import RateLimitError
from linkedin_scraper.core.rate_limit import detect_rate_limit
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.scrapers.person.interests import InterestsExtractor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_callable_url_exception():
    page = MagicMock()
    page.url = MagicMock(side_effect=RuntimeError("URL getter crashed"))
    page.query_selector_all = AsyncMock(return_value=[])
    page.extract_text_safe = AsyncMock(return_value="")

    # Should not raise RateLimitError
    await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_query_selector_captcha():
    page = MagicMock(spec=["query_selector_all", "extract_text_safe"])
    captcha_el = MagicMock(spec=ElementPort)
    captcha_el.get_attribute = AsyncMock(side_effect=lambda attr: "https://captcha.linkedin.com/challenge" if attr == "src" else "Security Challenge")
    page.query_selector_all = AsyncMock(return_value=[captcha_el])
    page.extract_text_safe = AsyncMock(return_value="")

    with pytest.raises(RateLimitError):
        await detect_rate_limit(page)


class DummyPage:
    def __init__(self, loc):
        self._loc = loc

    def locator(self, sel):
        if "captcha" in sel:
            empty = MagicMock(spec=["count"])
            empty.count = AsyncMock(return_value=0)
            return empty
        return self._loc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_loc_text_content():
    loc = MagicMock(spec=["count", "text_content"])
    loc.count = AsyncMock(return_value=1)
    loc.text_content = AsyncMock(return_value="Please try again later. Rate limit reached.")
    raw_page = DummyPage(loc)

    with pytest.raises(RateLimitError, match="Rate limit message detected"):
        await detect_rate_limit(raw_page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_loc_text_without_container_does_not_raise():
    """A phrase-bearing locator that matches no container (count=0) must not raise."""
    loc = MagicMock(spec=["count", "text_content"])
    loc.count = AsyncMock(return_value=0)
    loc.text_content = AsyncMock(return_value="Please try again later. Rate limit reached.")
    raw_page = DummyPage(loc)

    await detect_rate_limit(raw_page)  # Should not raise



@pytest.mark.unit
@pytest.mark.asyncio
async def test_interests_extractor_main_page_tabs():
    browser = MagicMock(spec=BrowserPort)

    tab = MagicMock(spec=ElementPort)
    tab.text_content = AsyncMock(return_value="Companies")
    tab.click = AsyncMock()

    tabpanel = MagicMock(spec=ElementPort)
    item = MagicMock(spec=ElementPort)
    link = MagicMock(spec=ElementPort)
    link.get_attribute = AsyncMock(return_value="https://www.linkedin.com/company/microsoft/")
    span = MagicMock(spec=ElementPort)
    span.text_content = AsyncMock(return_value="Microsoft")

    item.query_selector_all = AsyncMock(side_effect=[[link], [span]])
    tabpanel.query_selector_all = AsyncMock(return_value=[item])

    browser.query_selector_all = AsyncMock(side_effect=[
        [tab],          # main profile tabs
        [tabpanel],     # main profile tabpanels
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        extractor = InterestsExtractor(browser)
        interests = await extractor.get_interests("https://www.linkedin.com/in/user/")

    assert len(interests) == 1
    assert interests[0].name == "Microsoft"
    assert interests[0].category == "company"
