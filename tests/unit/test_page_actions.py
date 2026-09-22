"""Tests for linkedin_scraper.core.page_actions."""
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from linkedin_scraper.core import page_actions
from linkedin_scraper.core.exceptions import ElementNotFoundError
from linkedin_scraper.core.page_actions import (
    _get_selector_suggestions,
    click_see_more_buttons,
    extract_text_safe,
    handle_modal_close,
    is_page_loaded,
    scroll_to_bottom,
    scroll_to_half,
    wait_for_element_smart,
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
async def test_wait_for_element_smart_success():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock()
    await wait_for_element_smart(page, "#username", timeout=3000)
    page.wait_for_selector.assert_awaited_once_with("#username", timeout=3000, state="visible")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_element_smart_raises_element_not_found():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
    with pytest.raises(ElementNotFoundError) as exc_info:
        await wait_for_element_smart(page, "#username", error_context="logging in")
    assert "Could not find element with selector '#username' when logging in." in str(exc_info.value)
    assert "ID selectors" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_element_smart_re_raises_element_not_found():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=ElementNotFoundError("already typed error"))
    with pytest.raises(ElementNotFoundError, match="already typed error"):
        await wait_for_element_smart(page, "#username")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_with_native_method():
    page = AsyncMock()
    page.extract_text_safe = AsyncMock(return_value="Native safe text")
    res = await extract_text_safe(page, "h1", default="default", timeout=2000)
    assert res == "Native safe text"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_with_query_selector_all():
    el = AsyncMock()
    el.text_content = AsyncMock(return_value="  Extracted element text  ")
    page = AsyncMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(return_value=[el])

    res = await extract_text_safe(page, "h1")
    assert res == "Extracted element text"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_with_query_selector_all_empty():
    page = AsyncMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(return_value=[])

    res = await extract_text_safe(page, "h1", default="none")
    assert res == "none"


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
async def test_scroll_to_half():
    page = AsyncMock()
    page.evaluate = AsyncMock()
    await scroll_to_half(page)
    page.evaluate.assert_awaited_once_with("window.scrollTo(0, document.body.scrollHeight / 2)")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scroll_to_half_exception_handled():
    page = AsyncMock()
    page.evaluate = AsyncMock(side_effect=RuntimeError("eval error"))
    # Should not raise
    await scroll_to_half(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_click_see_more_buttons_query_selector_all():
    btn1 = AsyncMock()
    btn1.is_visible = AsyncMock(return_value=True)
    btn1.click = AsyncMock()

    page = AsyncMock(spec=["query_selector_all"])
    # First attempt returns [btn1], second attempt returns []
    page.query_selector_all = AsyncMock(side_effect=[[btn1], []])

    clicked = await click_see_more_buttons(page, max_attempts=5)
    assert clicked == 1
    btn1.click.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_click_see_more_buttons_locator(fake_page_cls, fake_locator_cls):
    clicked_count = 0

    class MockLocator(fake_locator_cls):
        async def is_visible(self, timeout=1000):
            nonlocal clicked_count
            return clicked_count == 0

        async def click(self):
            nonlocal clicked_count
            clicked_count += 1

    page = fake_page_cls(locator_factory=lambda s: MockLocator())
    clicked = await click_see_more_buttons(page, max_attempts=5)
    assert clicked == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_modal_close_query_selector_all():
    btn = AsyncMock()
    btn.is_visible = AsyncMock(return_value=True)
    btn.click = AsyncMock()

    page = AsyncMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(return_value=[btn])

    closed = await handle_modal_close(page)
    assert closed is True
    btn.click.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_modal_close_not_found():
    page = AsyncMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(return_value=[])

    closed = await handle_modal_close(page)
    assert closed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_modal_close_locator(fake_page_cls, fake_locator_cls):
    class MockModalLocator(fake_locator_cls):
        async def is_visible(self, timeout=1000):
            return True

        async def click(self):
            pass

    page = fake_page_cls(locator_factory=lambda s: MockModalLocator())
    closed = await handle_modal_close(page)
    assert closed is True


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

    page = fake_page_cls(
        evaluate_results=[0, None, 100, 100, None, 200, 200, None, 300]
    )
    await scroll_to_bottom(page, pause_time=0.01, max_scrolls=3)
    assert len(sleep_calls) == 3
