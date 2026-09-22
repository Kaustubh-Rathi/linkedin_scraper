"""Targeted branch coverage tests for core/auth.py."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from linkedin_scraper.core.auth import (
    AuthenticationError,
    is_logged_in,
    login_with_cookie,
    login_with_credentials,
    warm_up_browser,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_warm_up_browser_handles_site_failure():
    page = MagicMock()
    page.goto = AsyncMock(side_effect=[Exception("DNS error"), None, None])
    await warm_up_browser(page)
    assert page.goto.await_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_wait_for_username_failure():
    page = MagicMock()
    page.url = "https://www.linkedin.com/login"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=RuntimeError("Selector timeout"))

    with pytest.raises(AuthenticationError) as exc_info:
        await login_with_credentials(page, email="user@example.com", password="pwd", warm_up=False)
    assert "Login form not found" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_nav_failure_on_login_page():
    page = MagicMock()
    page.url = "https://www.linkedin.com/login"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_url = AsyncMock(side_effect=TimeoutError("wait_for_url timeout"))

    with pytest.raises(AuthenticationError) as exc_info:
        await login_with_credentials(page, email="user@example.com", password="pwd", warm_up=False)
    assert "Login failed" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_unexpected_exception():
    page = MagicMock()
    page.goto = AsyncMock(side_effect=OSError("Network down"))

    with pytest.raises(AuthenticationError) as exc_info:
        await login_with_credentials(page, email="user@example.com", password="pwd", warm_up=False)
    assert "Unexpected error during login" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_proceeds_if_not_verified():
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_url = AsyncMock()

    t_val = [0.0]
    def mock_time():
        t_val[0] += 3.0
        return t_val[0]

    with patch("linkedin_scraper.core.auth.is_logged_in", new_callable=AsyncMock) as mock_is_logged:
        mock_is_logged.return_value = False
        with patch("time.time", side_effect=mock_time):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await login_with_credentials(page, email="user@example.com", password="pwd", warm_up=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_cookie_via_context():
    context = MagicMock()
    context.add_cookies = AsyncMock()
    page = MagicMock()
    page.context = context
    del page.add_cookies  # Ensure context branch is taken
    page.url = "https://www.linkedin.com/feed/"
    page.goto = AsyncMock()

    with patch("linkedin_scraper.core.auth.is_logged_in", new_callable=AsyncMock) as mock_is_logged:
        mock_is_logged.return_value = True
        await login_with_cookie(page, "my-cookie-val")
        context.add_cookies.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_cookie_timeout_unverified():
    page = MagicMock()
    page.add_cookies = AsyncMock()
    page.url = "https://www.linkedin.com/feed/"
    page.goto = AsyncMock()

    t_val = [0.0]
    def mock_time():
        t_val[0] += 3.0
        return t_val[0]

    with patch("linkedin_scraper.core.auth.is_logged_in", new_callable=AsyncMock) as mock_is_logged:
        mock_is_logged.return_value = False
        with patch("time.time", side_effect=mock_time):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await login_with_cookie(page, "my-cookie-val")



@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_cookie_unexpected_exception():
    page = MagicMock()
    page.add_cookies = AsyncMock(side_effect=RuntimeError("Cookie error"))

    with pytest.raises(AuthenticationError) as exc_info:
        await login_with_cookie(page, "val")
    assert "Cookie authentication error" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_locator_branch():
    page = MagicMock(spec=["url", "locator"])
    page.url = "https://www.linkedin.com/in/someone/"
    loc = MagicMock()
    loc.count = AsyncMock(return_value=2)
    page.locator.return_value = loc

    assert await is_logged_in(page) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_exception_returns_false():
    page = MagicMock()
    page.url = "https://www.linkedin.com/in/someone/"
    page.query_selector_all = AsyncMock(side_effect=RuntimeError("Crash"))

    assert await is_logged_in(page) is False
