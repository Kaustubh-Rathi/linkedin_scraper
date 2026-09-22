"""Unit tests for linkedin_scraper.scrapers.base.BaseScraper (mocked page)."""
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.core.exceptions import AuthenticationError
from linkedin_scraper.scrapers import base as base_module
from linkedin_scraper.scrapers.base import BaseScraper


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_logged_in_raises_when_not_logged_in(monkeypatch):
    monkeypatch.setattr(base_module, "is_logged_in", AsyncMock(return_value=False))
    scraper = BaseScraper(page=object())

    with pytest.raises(AuthenticationError, match="Not logged in"):
        await scraper.ensure_logged_in()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_logged_in_passes_when_logged_in(monkeypatch):
    monkeypatch.setattr(base_module, "is_logged_in", AsyncMock(return_value=True))
    scraper = BaseScraper(page=object())

    await scraper.ensure_logged_in()  # Should not raise


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_rate_limit_delegates_to_detect_rate_limit(monkeypatch):
    detect_mock = AsyncMock()
    monkeypatch.setattr(base_module, "detect_rate_limit", detect_mock)
    page = object()
    scraper = BaseScraper(page=page)

    await scraper.check_rate_limit()

    detect_mock.assert_awaited_once_with(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_and_wait_calls_goto_and_check_rate_limit(monkeypatch):
    detect_mock = AsyncMock()
    monkeypatch.setattr(base_module, "detect_rate_limit", detect_mock)

    page = AsyncMock()
    scraper = BaseScraper(page=page)

    await scraper.navigate_and_wait("https://example.com/page", wait_until="load", timeout=1234)

    page.goto.assert_awaited_once_with(
        "https://example.com/page", wait_until="load", timeout=1234
    )
    detect_mock.assert_awaited_once_with(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_attribute_safe_returns_value_on_success(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(attribute="https://example.com")
    )
    scraper = BaseScraper(page=page)

    result = await scraper.get_attribute_safe("a", "href")

    assert result == "https://example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_attribute_safe_returns_default_when_none(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(locator_factory=lambda selector: fake_locator_cls(attribute=None))
    scraper = BaseScraper(page=page)

    result = await scraper.get_attribute_safe("a", "href", default="fallback")

    assert result == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_attribute_safe_returns_default_on_timeout(fake_page_cls, fake_locator_cls):
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(
            raise_on_attribute=PlaywrightTimeoutError("timeout")
        )
    )
    scraper = BaseScraper(page=page)

    result = await scraper.get_attribute_safe("a", "href", default="fallback")
    assert result == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_attribute_safe_propagates_unexpected_exception(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(
            raise_on_attribute=RuntimeError("boom")
        )
    )
    scraper = BaseScraper(page=page)

    with pytest.raises(RuntimeError, match="boom"):
        await scraper.get_attribute_safe("a", "href", default="fallback")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_safe_extract_text_delegates_to_extract_text_safe(monkeypatch):
    extract_mock = AsyncMock(return_value="extracted text")
    monkeypatch.setattr(base_module, "extract_text_safe", extract_mock)
    page = object()
    scraper = BaseScraper(page=page)

    result = await scraper.safe_extract_text(".title", default="none", timeout=1500)

    assert result == "extracted text"
    extract_mock.assert_awaited_once_with(page, ".title", "none", 1500)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_locate_profile_component_items(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(locator_factory=lambda selector: fake_locator_cls(count=2))
    scraper = BaseScraper(page=page)
    items = await scraper.locate_profile_component_items()
    assert items == []

