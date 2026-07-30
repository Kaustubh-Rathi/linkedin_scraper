"""Tests for linkedin_scraper.core.page_actions."""
import asyncio

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from linkedin_scraper.core import page_actions
from linkedin_scraper.core.page_actions import (
    _get_selector_suggestions,
    extract_text_safe,
    is_page_loaded,
    scroll_to_bottom,
)


@pytest.mark.unit
def test_get_selector_suggestions_for_id_selector():
    suggestion = _get_selector_suggestions("#main-content")
    assert "ID selectors" in suggestion


@pytest.mark.unit
def test_get_selector_suggestions_for_pv_prefixed_selector():
    suggestion = _get_selector_suggestions(".pv-top-card")
    assert "LinkedIn class names change frequently" in suggestion


@pytest.mark.unit
def test_get_selector_suggestions_for_artdeco_selector():
    suggestion = _get_selector_suggestions(".artdeco-modal__dismiss")
    assert "LinkedIn class names change frequently" in suggestion


@pytest.mark.unit
def test_get_selector_suggestions_for_unknown_selector():
    assert _get_selector_suggestions(".some-random-class") == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_returns_default_on_timeout(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(
            raise_on_text=PlaywrightTimeoutError("timed out")
        )
    )

    result = await extract_text_safe(page, ".missing", default="fallback")

    assert result == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_returns_default_on_generic_error(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(raise_on_text=RuntimeError("boom"))
    )

    result = await extract_text_safe(page, ".missing", default="fallback")

    assert result == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_returns_stripped_text(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(text="  Hello World  ")
    )

    result = await extract_text_safe(page, "h1")

    assert result == "Hello World"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_returns_default_when_text_is_none(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(locator_factory=lambda selector: fake_locator_cls(text=None))

    result = await extract_text_safe(page, "h1", default="none-found")

    assert result == "none-found"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_page_loaded_returns_true_when_complete(fake_page_cls):
    page = fake_page_cls(evaluate_results=["complete"])

    assert await is_page_loaded(page) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_page_loaded_returns_false_when_not_complete(fake_page_cls):
    page = fake_page_cls(evaluate_results=["loading"])

    assert await is_page_loaded(page) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_page_loaded_returns_false_on_exception(fake_page_cls, monkeypatch):
    page = fake_page_cls()

    async def raise_error(script):
        raise RuntimeError("evaluate failed")

    monkeypatch.setattr(page, "evaluate", raise_error)

    assert await is_page_loaded(page) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scroll_to_bottom_stops_when_height_stable(fake_page_cls, monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(page_actions.asyncio, "sleep", fake_sleep)

    # Iteration 1: previous=1000, scrollTo (unused), new=1000 -> stable, stop.
    page = fake_page_cls(evaluate_results=[1000, None, 1000])

    await scroll_to_bottom(page, pause_time=0.01, max_scrolls=10)

    assert len(sleep_calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scroll_to_bottom_continues_until_stable(fake_page_cls, monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(page_actions.asyncio, "sleep", fake_sleep)

    # Iteration 1: 1000 -> 2000 (grew, keep going)
    # Iteration 2: 2000 -> 2000 (stable, stop)
    page = fake_page_cls(evaluate_results=[1000, None, 2000, 2000, None, 2000])

    await scroll_to_bottom(page, pause_time=0.01, max_scrolls=10)

    assert len(sleep_calls) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scroll_to_bottom_respects_max_scrolls(fake_page_cls, monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(page_actions.asyncio, "sleep", fake_sleep)

    # Height always grows within each iteration, so it never stabilizes:
    # bounded by max_scrolls instead. 3 iterations * 3 evaluate calls each.
    page = fake_page_cls(
        evaluate_results=[0, None, 100, 100, None, 200, 200, None, 300]
    )

    await scroll_to_bottom(page, pause_time=0.01, max_scrolls=3)

    assert len(sleep_calls) == 3
