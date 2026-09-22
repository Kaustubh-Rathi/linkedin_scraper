"""
Tests for protocol and port definitions and default protocol methods.
"""

import pytest
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.search.ports import (
    CompanySearchPort,
    EmployeeSearchPort,
    JobSearchPort,
    PersonSearchPort,
    PostSearchPort,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_element_port_default_methods():
    """Verify ElementPort methods can be invoked when called directly on protocol class."""
    assert await ElementPort.text_content(None) is None
    assert await ElementPort.inner_text(None) is None
    assert await ElementPort.get_attribute(None, "href") is None
    assert await ElementPort.is_visible(None) is None
    assert await ElementPort.click(None) is None
    assert await ElementPort.query_selector_all(None, "div") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_port_default_methods():
    """Verify BrowserPort methods can be invoked when called directly on protocol class."""
    # Test default implementations in protocol class
    assert BrowserPort.url.fget(None) is None
    assert await BrowserPort.goto(None, "https://example.com") is None
    assert await BrowserPort.wait_for_selector(None, "div") is None
    assert await BrowserPort.wait_for_load_state(None) is None
    assert await BrowserPort.wait_for_url(None, "https://example.com") is None
    assert await BrowserPort.wait_for_timeout(None, 100) is None
    assert await BrowserPort.evaluate(None, "1+1") is None
    assert await BrowserPort.extract_text_safe(None, "div") is None
    assert await BrowserPort.fill(None, "input", "text") is None
    assert await BrowserPort.click(None, "button") is None
    assert await BrowserPort.locator(None, "div") is None
    assert await BrowserPort.query_selector_all(None, "div") is None
    assert await BrowserPort.bring_to_front(None) is None
    assert await BrowserPort.add_cookies(None, []) is None
    assert await BrowserPort.keyboard_press(None, "Enter") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_ports_default_methods():
    """Verify SearchPort protocol methods can be invoked when called directly."""
    assert await PersonSearchPort.search_people(None, None) is None
    assert await CompanySearchPort.search_companies(None, None) is None
    assert await EmployeeSearchPort.search_employees(None, None) is None
    assert await JobSearchPort.search_jobs(None, None) is None
    assert await PostSearchPort.search_posts(None, None) is None
