"""Unit tests for linkedin_scraper.core.browser.BrowserManager.

These tests avoid launching a real browser: they exercise the guard-rail
logic (RuntimeError before start(), file-existence checks, property
getters/setters) that doesn't require Playwright to actually be running.
Real browser launch/session round-tripping is already covered by
``tests/test_browser.py``.
"""
import pytest

from linkedin_scraper.core.browser import BrowserManager


@pytest.mark.unit
def test_page_property_raises_before_start():
    manager = BrowserManager(headless=True)
    with pytest.raises(RuntimeError, match="Browser not started"):
        _ = manager.page


@pytest.mark.unit
def test_context_property_raises_before_start():
    manager = BrowserManager(headless=True)
    with pytest.raises(RuntimeError, match="Browser context not initialized"):
        _ = manager.context


@pytest.mark.unit
def test_browser_property_raises_before_start():
    manager = BrowserManager(headless=True)
    with pytest.raises(RuntimeError, match="Browser not started"):
        _ = manager.browser


@pytest.mark.unit
def test_is_authenticated_defaults_to_false():
    manager = BrowserManager(headless=True)
    assert manager.is_authenticated is False


@pytest.mark.unit
def test_is_authenticated_setter_updates_value():
    manager = BrowserManager(headless=True)
    manager.is_authenticated = True
    assert manager.is_authenticated is True


@pytest.mark.unit
def test_constructor_defaults():
    manager = BrowserManager()
    assert manager.headless is True
    assert manager.slow_mo == 0
    assert manager.viewport == {"width": 1280, "height": 720}
    assert manager.user_agent is None


@pytest.mark.unit
def test_constructor_custom_options():
    manager = BrowserManager(
        headless=False,
        slow_mo=50,
        viewport={"width": 800, "height": 600},
        user_agent="custom-agent",
    )
    assert manager.headless is False
    assert manager.slow_mo == 50
    assert manager.viewport == {"width": 800, "height": 600}
    assert manager.user_agent == "custom-agent"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_page_raises_before_start():
    manager = BrowserManager(headless=True)
    with pytest.raises(RuntimeError, match="Browser context not initialized"):
        await manager.new_page()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_cookie_raises_before_start():
    manager = BrowserManager(headless=True)
    with pytest.raises(RuntimeError, match="No browser context"):
        await manager.set_cookie("li_at", "value")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_session_raises_before_start(tmp_path):
    manager = BrowserManager(headless=True)
    with pytest.raises(RuntimeError, match="No browser context to save"):
        await manager.save_session(str(tmp_path / "session.json"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_load_session_raises_file_not_found(tmp_path):
    manager = BrowserManager(headless=True)
    missing_file = tmp_path / "does-not-exist.json"
    with pytest.raises(FileNotFoundError):
        await manager.load_session(str(missing_file))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_without_start_does_not_raise():
    manager = BrowserManager(headless=True)
    await manager.close()  # Should be a safe no-op
