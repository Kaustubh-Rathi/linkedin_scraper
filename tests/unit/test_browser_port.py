"""Unit tests for BrowserPort abstraction and PlaywrightBrowserAdapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from linkedin_scraper.ports import BrowserPort, ElementPort
from linkedin_scraper.core.browser import PlaywrightBrowserAdapter, PlaywrightElementAdapter, BrowserManager
from linkedin_scraper.scrapers.base import BaseScraper
from playwright.async_api import Page


@pytest.mark.asyncio
async def test_browser_port_protocol_compliance():
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/in/test"
    adapter = PlaywrightBrowserAdapter(mock_page)

    assert isinstance(adapter, BrowserPort)
    assert adapter.url == "https://www.linkedin.com/in/test"

    await adapter.goto("https://www.linkedin.com")
    mock_page.goto.assert_called_once_with("https://www.linkedin.com", wait_until="domcontentloaded", timeout=60000)

    await adapter.wait_for_selector(".test-class", timeout=1000, state="attached")
    mock_page.wait_for_selector.assert_called_once_with(".test-class", timeout=1000, state="attached")

    await adapter.wait_for_load_state("networkidle", timeout=5000)
    mock_page.wait_for_load_state.assert_called_once_with("networkidle", timeout=5000)

    await adapter.wait_for_url("https://www.linkedin.com/feed/", timeout=5000)
    mock_page.wait_for_url.assert_called_once_with("https://www.linkedin.com/feed/", timeout=5000)

    await adapter.wait_for_timeout(500)
    mock_page.wait_for_timeout.assert_called_once_with(500)

    await adapter.evaluate("window.scrollTo(0, 100)")
    mock_page.evaluate.assert_called_once_with("window.scrollTo(0, 100)")

    await adapter.fill("#input", "hello")
    mock_page.fill.assert_called_once_with("#input", "hello")

    await adapter.click("#button")
    mock_page.click.assert_called_once_with("#button")

    await adapter.bring_to_front()
    mock_page.bring_to_front.assert_called_once()

    await adapter.keyboard_press("Enter")
    mock_page.keyboard.press.assert_called_once_with("Enter")


@pytest.mark.asyncio
async def test_element_adapter():
    mock_elem = AsyncMock()
    mock_elem.text_content.return_value = "Sample Text"
    mock_elem.inner_text.return_value = "Rendered Sample Text"
    mock_elem.get_attribute.return_value = "sample_value"
    mock_elem.is_visible.return_value = True
    child_mock = AsyncMock()
    mock_elem.query_selector_all.return_value = [child_mock]

    adapter = PlaywrightElementAdapter(mock_elem)
    assert isinstance(adapter, ElementPort)

    text = await adapter.text_content()
    assert text == "Sample Text"

    inner = await adapter.inner_text()
    assert inner == "Rendered Sample Text"

    attr = await adapter.get_attribute("href")
    assert attr == "sample_value"

    visible = await adapter.is_visible()
    assert visible is True

    children = await adapter.query_selector_all(".child")
    assert len(children) == 1
    assert isinstance(children[0], ElementPort)

    await adapter.click()
    mock_elem.click.assert_called_once()


@pytest.mark.asyncio
async def test_query_selector_all_adaptation():
    mock_page = AsyncMock()
    mock_elem1 = AsyncMock()
    mock_elem2 = AsyncMock()
    mock_page.query_selector_all.return_value = [mock_elem1, mock_elem2]

    adapter = PlaywrightBrowserAdapter(mock_page)
    results = await adapter.query_selector_all(".item")

    assert len(results) == 2
    assert all(isinstance(res, ElementPort) for res in results)


@pytest.mark.asyncio
async def test_base_scraper_with_browser_port():
    mock_browser = MagicMock(spec=BrowserPort)
    mock_browser.url = "https://www.linkedin.com"
    mock_browser.goto = AsyncMock()

    scraper = BaseScraper(mock_browser)
    assert scraper.browser is mock_browser

    await scraper.navigate_and_wait("https://www.linkedin.com/in/test")
    mock_browser.goto.assert_called_once_with("https://www.linkedin.com/in/test", wait_until="domcontentloaded", timeout=60000)


@pytest.mark.asyncio
async def test_base_scraper_backward_compatibility_with_page():
    mock_page = MagicMock(spec=Page)
    mock_page.url = "https://www.linkedin.com"

    scraper = BaseScraper(mock_page)
    assert hasattr(scraper, "browser")
    assert isinstance(scraper.browser, BrowserPort)
    assert scraper.page is mock_page


def test_browser_manager_port_access():
    manager = BrowserManager()
    with pytest.raises(RuntimeError, match="Browser not started"):
        _ = manager.browser_port
