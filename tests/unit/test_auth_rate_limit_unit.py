"""Unit tests for auth.py and rate_limit.py functions and error branches."""

import pytest

from linkedin_scraper.core.auth import (
    is_logged_in,
    login_with_cookie,
    login_with_credentials,
    warm_up_browser,
)
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError
from linkedin_scraper.core.rate_limit import detect_rate_limit


# ---------------------------------------------------------------------------
# Rate Limit Detector Tests
# ---------------------------------------------------------------------------


class MockElementForRateLimit:
    def __init__(self, src="", title="", text=None):
        self._src = src
        self._title = title
        self._text = text

    async def get_attribute(self, attr, timeout=2000):
        if attr == "src":
            return self._src
        if attr == "title":
            return self._title
        return None

    async def text_content(self, timeout=1000):
        return self._text


class MockBrowserForRateLimit:
    def __init__(self, url="https://www.linkedin.com/feed/", elements=None, body_text="", rate_limit_elements=None):
        self.url = url
        self._elements = elements or []
        self._body_text = body_text
        self._rate_limit_elements = rate_limit_elements or []

    async def query_selector_all(self, selector):
        if "captcha" in selector:
            return self._elements
        if "rate-limit" in selector or "rateLimit" in selector or "artdeco" in selector:
            return self._rate_limit_elements
        return []

    async def extract_text_safe(self, selector, default="", timeout=1000):
        if selector == "body":
            return self._body_text
        return default


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_clean():
    browser = MockBrowserForRateLimit(url="https://www.linkedin.com/feed/", body_text="Normal feed")
    # Should not raise
    await detect_rate_limit(browser)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_checkpoint_url():
    browser = MockBrowserForRateLimit(url="https://www.linkedin.com/checkpoint/challenge/")
    with pytest.raises(RateLimitError, match="LinkedIn security checkpoint detected"):
        await detect_rate_limit(browser)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_captcha_iframe():
    captcha_el = MockElementForRateLimit(src="https://captcha.com")
    browser = MockBrowserForRateLimit(
        url="https://www.linkedin.com/feed/",
        elements=[captcha_el],
    )

    with pytest.raises(RateLimitError, match="CAPTCHA challenge detected"):
        await detect_rate_limit(browser)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_rate_limit_phrase():
    banner = MockElementForRateLimit(
        text="Please try again later. You have reached the rate limit."
    )
    browser = MockBrowserForRateLimit(
        url="https://www.linkedin.com/feed/",
        rate_limit_elements=[banner],
    )

    with pytest.raises(RateLimitError, match="Rate limit message detected"):
        await detect_rate_limit(browser)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_body_text_only_does_not_raise():
    """Rate-limit phrases in unrelated body text must not trigger a false positive."""
    browser = MockBrowserForRateLimit(
        url="https://www.linkedin.com/feed/",
        body_text="Please try again later. You have reached the rate limit.",
    )

    await detect_rate_limit(browser)  # Should not raise


# ---------------------------------------------------------------------------
# Auth Functions Tests
# ---------------------------------------------------------------------------


class MockBrowserForAuth:
    def __init__(self, url="https://www.linkedin.com/feed/", is_logged_in_val=True, elements=None):
        self.url = url
        self._is_logged_in_val = is_logged_in_val
        self._elements = elements or []
        self.add_cookies_called = False
        self.goto_calls = []

    async def add_cookies(self, cookies):
        self.add_cookies_called = True

    async def goto(self, url, **kw):
        self.goto_calls.append(url)

    async def wait_for_load_state(self, *a, **kw):
        pass

    async def wait_for_selector(self, *a, **kw):
        pass

    async def wait_for_timeout(self, *a, **kw):
        pass

    async def query_selector_all(self, selector):
        return self._elements

    async def evaluate(self, expr):
        return self._is_logged_in_val

    async def fill(self, *a, **kw):
        pass

    async def click(self, *a, **kw):
        if "login" in self.url:
            self.url = "https://www.linkedin.com/checkpoint/challenge/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_login_url():
    browser = MockBrowserForAuth(url="https://www.linkedin.com/login", is_logged_in_val=False)
    assert await is_logged_in(browser) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_feed_url():
    browser = MockBrowserForAuth(url="https://www.linkedin.com/feed/", is_logged_in_val=True)
    assert await is_logged_in(browser) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_cookie_success():
    browser = MockBrowserForAuth(url="https://www.linkedin.com/feed/", is_logged_in_val=True)
    await login_with_cookie(browser, "valid-li-at-cookie")
    assert browser.add_cookies_called is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_cookie_fails():
    browser = MockBrowserForAuth(url="https://www.linkedin.com/login", is_logged_in_val=False)
    with pytest.raises(AuthenticationError, match="Cookie authentication failed"):
        await login_with_cookie(browser, "invalid-cookie")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_fails():
    browser = MockBrowserForAuth(url="https://www.linkedin.com/login", is_logged_in_val=False)
    with pytest.raises(AuthenticationError, match="(?i)security checkpoint"):
        await login_with_credentials(browser, "user@example.com", "secret")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_warm_up_browser():
    browser = MockBrowserForAuth()
    await warm_up_browser(browser)
    assert "https://www.google.com" in browser.goto_calls
