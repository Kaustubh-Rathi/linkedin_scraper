"""Tests for authentication functions."""

import pytest
from linkedin_scraper import BrowserManager
from linkedin_scraper.core.auth import is_logged_in
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_is_logged_in_deterministic_unauthenticated():
    """Test is_logged_in returns False on unauthenticated / login page DOM."""
    async with BrowserManager(headless=True) as browser:
        await browser.page.set_content(
            "<html><head><title>LinkedIn: Log In or Sign Up</title></head>"
            "<body><form class='login__form'><input id='username'/></form></body></html>"
        )
        logged_in = await is_logged_in(browser.get_browser_port())
        assert logged_in is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_is_logged_in_deterministic_authenticated():
    """Test is_logged_in returns True when authenticated navigation DOM elements are present."""
    async with BrowserManager(headless=True) as browser:
        await browser.page.set_content(
            "<html><head><title>Feed | LinkedIn</title></head>"
            "<body><nav><a class='global-nav__primary-link' href='/feed/'>Feed</a></nav></body></html>"
        )
        logged_in = await is_logged_in(browser.get_browser_port())
        assert logged_in is True


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_is_logged_in_with_live_session(browser_with_session):
    """Test is_logged_in returns True with valid live LinkedIn session."""
    try:
        await browser_with_session.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        logged_in = await is_logged_in(browser_with_session.get_browser_port())
        assert logged_in is True
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
