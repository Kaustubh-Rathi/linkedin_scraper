"""Common page interaction helpers (waiting, scrolling, text extraction)."""

import asyncio
import inspect
import logging
from typing import Any, Literal, Optional, Union

from ..ports.browser import BrowserPort
from .exceptions import ElementNotFoundError

logger = logging.getLogger(__name__)

WaitForState = Literal["attached", "detached", "hidden", "visible"]


async def _resolve_first_locator(page: Any, selector: str) -> Any:
    """Resolve ``page.locator(selector).first`` with sync/async compatibility."""
    locator_factory = page.locator
    locator = locator_factory(selector)
    if inspect.isawaitable(locator):
        locator = await locator
    first = locator.first
    if inspect.isawaitable(first):
        return await first
    return first


async def wait_for_element_smart(
    page: Union[BrowserPort, Any],
    selector: str,
    timeout: float = 5000,
    state: WaitForState = "visible",
    error_context: Optional[str] = None,
) -> None:
    """
    Wait for an element with actionable error messages.
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
    except Exception as exc:
        if isinstance(exc, ElementNotFoundError):
            raise
        context = f" when {error_context}" if error_context else ""
        suggestions = _get_selector_suggestions(selector)
        logger.debug("wait_for_element_smart failed for selector '%s'%s: %s", selector, context, exc)
        raise ElementNotFoundError(
            f"Could not find element with selector '{selector}'{context}. "
            f"This may indicate:\n"
            f"  • The page structure has changed\n"
            f"  • The profile has restricted visibility\n"
            f"  • The content doesn't exist on this page\n"
            f"  • Network slowness (try increasing timeout)\n"
            f"{suggestions}"
        ) from exc


def _get_selector_suggestions(selector: str) -> str:
    """Get helpful suggestions based on selector type."""
    if "#" in selector:
        return "Tip: ID selectors may be dynamic. Consider using data attributes or text content."
    elif "pv-" in selector or "artdeco" in selector:
        return "Tip: LinkedIn class names change frequently. This selector may need updating."
    return ""


async def extract_text_safe(
    page: Union[BrowserPort, Any],
    selector: str,
    default: str = "",
    timeout: float = 2000,
) -> str:
    """
    Safely extract text from an element, returning default if not found.
    """
    if hasattr(page, "extract_text_safe"):
        return await page.extract_text_safe(selector, default, timeout)
    try:
        if hasattr(page, "query_selector_all"):
            elements = await page.query_selector_all(selector)
            if elements:
                text = await elements[0].text_content(timeout=timeout)
                return text.strip() if text else default
        if hasattr(page, "locator"):
            element = await _resolve_first_locator(page, selector)
            if hasattr(element, "text_content"):
                text = await element.text_content(timeout=timeout)
                return text.strip() if text else default
        return default
    except Exception as exc:
        logger.debug("Element not found or timed out: %s (defaulting to '%s'): %s", selector, default, exc)
        return default


async def scroll_to_bottom(
    page: Union[BrowserPort, Any], pause_time: float = 1.0, max_scrolls: int = 10
) -> None:
    """
    Scroll to the bottom of the page smoothly with pauses.
    """
    for i in range(max_scrolls):
        try:
            previous_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(pause_time)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == previous_height:
                logger.debug("Reached bottom after %d scrolls", i + 1)
                break
        except Exception as exc:
            logger.debug("Scroll evaluation interrupted at step %d: %s", i + 1, exc)
            break


async def scroll_to_half(page: Union[BrowserPort, Any]) -> None:
    """Scroll to middle of page."""
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    except Exception as exc:
        logger.debug("Scroll to half interrupted: %s", exc)


async def click_see_more_buttons(
    page: Union[BrowserPort, Any], max_attempts: int = 10
) -> int:
    """
    Click all 'Show more' / 'See more' buttons on the page.
    """
    clicked = 0
    selector = 'button:has-text("See more"), button:has-text("Show more"), button:has-text("show all")'
    for attempt in range(max_attempts):
        try:
            if hasattr(page, "query_selector_all"):
                buttons = await page.query_selector_all(selector)
                if not buttons:
                    break
                btn = buttons[0]
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    clicked += 1
                else:
                    break
                continue
            if hasattr(page, "locator"):
                see_more = await _resolve_first_locator(page, selector)
                if hasattr(see_more, "is_visible") and await see_more.is_visible(timeout=1000):
                    await see_more.click()
                    await asyncio.sleep(0.5)
                    clicked += 1
                else:
                    break
                continue
            break
        except Exception as exc:
            logger.debug("See-more button click loop ended on attempt %d: %s", attempt + 1, exc)
            break

    if clicked > 0:
        logger.debug("Clicked %d 'see more' buttons", clicked)

    return clicked


async def handle_modal_close(page: Union[BrowserPort, Any]) -> bool:
    """
    Close any popup modals that might be blocking content.
    """
    selector = 'button[aria-label="Dismiss"], button[aria-label="Close"], button.artdeco-modal__dismiss'
    try:
        if hasattr(page, "query_selector_all"):
            buttons = await page.query_selector_all(selector)
            if buttons and await buttons[0].is_visible(timeout=1000):
                await buttons[0].click()
                await asyncio.sleep(0.5)
                logger.debug("Closed modal via ElementPort")
                return True
            return False
        if hasattr(page, "locator"):
            close_button = await _resolve_first_locator(page, selector)
            if hasattr(close_button, "is_visible") and await close_button.is_visible(timeout=1000):
                await close_button.click()
                await asyncio.sleep(0.5)
                logger.debug("Closed modal via locator")
                return True
    except Exception as exc:
        logger.debug("Non-fatal exception while checking/closing modal: %s", exc)

    return False


async def is_page_loaded(page: Union[BrowserPort, Any]) -> bool:
    """
    Check if page has finished loading.
    """
    try:
        state = await page.evaluate("document.readyState")
        return bool(state == "complete")
    except Exception as exc:
        logger.debug("Non-fatal exception checking document.readyState: %s", exc)
        return False
