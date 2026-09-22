"""Tests for linkedin_scraper.core.rate_limit.detect_rate_limit."""
import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from linkedin_scraper.core.exceptions import RateLimitError
from linkedin_scraper.core.rate_limit import detect_rate_limit


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_checkpoint_url(fake_page_cls):
    page = fake_page_cls(url="https://www.linkedin.com/checkpoint/challenge/")

    with pytest.raises(RateLimitError) as exc_info:
        await detect_rate_limit(page)

    assert exc_info.value.suggested_wait_time == 3600


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_authwall_url(fake_page_cls):
    page = fake_page_cls(url="https://www.linkedin.com/authwall?trk=x")

    with pytest.raises(RateLimitError):
        await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_captcha(fake_page_cls, fake_locator_cls):
    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(count=1)
        return fake_locator_cls(text="")

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    with pytest.raises(RateLimitError) as exc_info:
        await detect_rate_limit(page)

    assert exc_info.value.suggested_wait_time == 3600


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_raises_on_too_many_requests_text(fake_page_cls, fake_locator_cls):
    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(count=0)
        if "rate-limit" in selector or "rateLimit" in selector:
            return fake_locator_cls(
                count=1, text="Whoa there! Too many requests, please slow down."
            )
        return fake_locator_cls(count=0)

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    with pytest.raises(RateLimitError) as exc_info:
        await detect_rate_limit(page)

    assert exc_info.value.suggested_wait_time == 1800


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phrase",
    ["rate limit exceeded", "please slow down", "try again later"],
)
async def test_detect_rate_limit_matches_all_known_phrases(phrase, fake_page_cls, fake_locator_cls):
    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(count=0)
        if "rate-limit" in selector or "rateLimit" in selector:
            return fake_locator_cls(count=1, text=f"Some banner text: {phrase}")
        return fake_locator_cls(count=0)

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    with pytest.raises(RateLimitError):
        await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_ignores_phrase_in_unrelated_page_text(fake_page_cls, fake_locator_cls):
    """Rate-limit phrases outside the dedicated containers must not raise.

    LinkedIn embeds rate-limit-like text in normal pages; only matches inside
    the known rate-limit containers count as an actual rate limit. This guards
    against the false positives that motivated container-scoped detection.
    """

    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(count=0)
        if (
            "rate-limit" in selector
            or "rateLimit" in selector
            or "artdeco" in selector
            or "has-text" in selector
        ):
            # Dedicated containers and the fallback probe match nothing.
            return fake_locator_cls(count=0)
        # Unrelated parts of the page still carry the phrase.
        return fake_locator_cls(count=1, text="Please try again later. Rate limit exceeded.")

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    await detect_rate_limit(page)  # Should not raise


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_clean_page_does_not_raise(fake_page_cls, fake_locator_cls):
    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(count=0)
        return fake_locator_cls(text="Welcome back! Everything looks normal here.")

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    await detect_rate_limit(page)  # Should not raise


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_swallows_captcha_locator_errors(fake_page_cls, fake_locator_cls):
    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(raise_on_count=RuntimeError("boom"))
        return fake_locator_cls(text="all good")

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    await detect_rate_limit(page)  # Should not raise, captcha errors are swallowed


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_swallows_body_text_timeout(fake_page_cls, fake_locator_cls):
    def locator_factory(selector: str):
        if "captcha" in selector:
            return fake_locator_cls(count=0)
        return fake_locator_cls(raise_on_text=PlaywrightTimeoutError("timed out"))

    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=locator_factory,
    )

    await detect_rate_limit(page)  # Timeout on body text is swallowed
