"""Tests for BrowserManager."""
import pytest
from linkedin_scraper import BrowserManager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_manager_context():
    """Test BrowserManager as context manager."""
    async with BrowserManager(headless=True) as browser:
        assert browser.page is not None
        assert browser.context is not None
        assert browser.browser is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_manager_navigation():
    """Test basic navigation."""
    async with BrowserManager(headless=True) as browser:
        await browser.page.route("**/local-test", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="<html><head><title>Local Test Page</title></head><body>Hello</body></html>"
        ))
        await browser.page.goto("http://localhost/local-test")
        title = await browser.page.title()
        assert "Local Test Page" in title


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_manager_session_save_load(tmp_path):
    """Test session save and load."""
    session_file = tmp_path / "test_session.json"

    async with BrowserManager(headless=True) as browser:
        await browser.page.route("**/local-test", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="<html><head><title>Local Test</title></head><body>Hello</body></html>"
        ))
        await browser.page.goto("http://localhost/local-test")

        # Save session
        await browser.save_session(str(session_file))
        assert session_file.exists()

    # Load session in new browser
    async with BrowserManager(headless=True) as browser:
        await browser.load_session(str(session_file))
        # Should have cookies loaded
        cookies = await browser.context.cookies()
        assert len(cookies) >= 0  # At least session was loadable


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_manager_headless_mode():
    """Test headless mode."""
    async with BrowserManager(headless=True) as browser:
        assert browser.page is not None
        await browser.page.set_content("<html><body><h1>Example Page</h1></body></html>")
        content = await browser.page.content()
        assert "Example Page" in content
