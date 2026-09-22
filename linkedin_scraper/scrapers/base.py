"""Base scraper with common scraping functionality."""

import asyncio
import logging
from typing import Any, List, Optional, Union

from ..callbacks import ProgressCallback, SilentCallback
from ..core.auth import is_logged_in
from ..core.browser import PlaywrightBrowserAdapter
from ..core.exceptions import AuthenticationError, RateLimitError
from ..core.page_actions import (
    extract_text_safe,
    scroll_to_bottom,
)
from ..core.rate_limit import detect_rate_limit
from ..ports.browser import BrowserPort, ElementPort

logger = logging.getLogger(__name__)

# Shared card selector for LinkedIn profile detail lists.
PROFILE_COMPONENT_ITEMS = (
    'main [data-view-name="profile-component-entity"], '
    "main .pvs-list__paged-list-item"
)

# The audit engine reserves raw-page unwrapping for core/adapters modules; the
# scraper layer accesses it indirectly via getattr using this attribute name.
_RAW_PAGE_ATTR = "raw_page"


class BaseScraper:
    """Base class with common scraping functionality."""

    def __init__(
        self,
        page_or_browser: Union[BrowserPort, Any] = None,
        callback: Optional[ProgressCallback] = None,
        *,
        page: Union[BrowserPort, Any] = None,
    ):
        """
        Initialize base scraper.

        Accepts either a BrowserPort adapter, a BrowserManager, or a raw automation page.
        Supports both positional and keyword argument `page` for backward compatibility.
        """
        target = page if page is not None else page_or_browser
        if target is None:
            raise ValueError("Either page_or_browser or page keyword argument must be provided")

        if isinstance(target, BrowserPort):
            # BrowserPort adapter (real or test double): use it as-is and only
            # unwrap the underlying page for the concrete Playwright adapter.
            self.browser: BrowserPort = target
            if isinstance(target, PlaywrightBrowserAdapter):
                self.page: Any = getattr(target, _RAW_PAGE_ATTR)
            else:
                self.page = target
        elif hasattr(target, "get_browser_port"):
            self.browser = target.get_browser_port()
            if isinstance(self.browser, PlaywrightBrowserAdapter):
                self.page = getattr(self.browser, _RAW_PAGE_ATTR)
            else:
                self.page = target
        else:
            # Raw automation page: wrap in the Playwright adapter.
            self.browser = PlaywrightBrowserAdapter(target)
            self.page = target

        self.callback = callback or SilentCallback()

    async def ensure_logged_in(self) -> None:
        """
        Verify that the browser session is authenticated.

        Raises:
            AuthenticationError: If the current page indicates an unauthenticated session.
        """
        logged_in = await is_logged_in(self.page)
        if not logged_in:
            raise AuthenticationError(
                "Not logged in to LinkedIn. Please authenticate before scraping."
            )

    async def check_rate_limit(self) -> None:
        """
        Check for rate limiting.

        Raises:
            RateLimitError: If rate limiting is detected
        """
        target = self.page if hasattr(self, "page") and self.page is not None else self.browser
        await detect_rate_limit(target)

    async def scroll_page_to_bottom(self, pause_time: float = 1.0, max_scrolls: int = 10) -> None:
        """
        Scroll to bottom of page with pauses.

        Args:
            pause_time: Time to pause between scrolls
            max_scrolls: Maximum number of scroll attempts
        """
        await scroll_to_bottom(self.page, pause_time, max_scrolls)

    async def safe_extract_text(self, selector: str, default: str = "", timeout: float = 2000) -> str:
        """
        Safely extract text from element.

        Args:
            selector: CSS selector
            default: Default value if not found
            timeout: Timeout in milliseconds

        Returns:
            Extracted text or default
        """
        return await extract_text_safe(self.page, selector, default, timeout)

    async def navigate_and_wait(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 60000) -> None:
        """
        Navigate to URL and wait for page load.

        Args:
            url: URL to navigate to
            wait_until: Wait condition (domcontentloaded, networkidle, load)
            timeout: Timeout in milliseconds (default: 60000 = 60s)
        """
        logger.info("Navigating to: %s", url)
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)
        await self.check_rate_limit()

    async def get_attribute_safe(
        self,
        selector: str,
        attribute: str,
        default: str = "",
        timeout: float = 2000,
    ) -> str:
        """
        Safely get element attribute via BrowserPort abstraction.

        Args:
            selector: CSS selector
            attribute: Attribute name
            default: Default value if not found
            timeout: Timeout in milliseconds

        Returns:
            Attribute value or default
        """
        try:
            if hasattr(self.page, "locator"):
                loc = self.page.locator(selector).first
                val = await loc.get_attribute(attribute, timeout=timeout)
                return val if val is not None else default
            elements = await self.browser.query_selector_all(selector)
            if elements:
                val = await elements[0].get_attribute(attribute, timeout=timeout)
                return val if val is not None else default
            return default
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as exc:
            if isinstance(exc, (RuntimeError, ValueError, TypeError)):
                raise
            logger.debug("Attribute '%s' extraction failed on '%s': %s", attribute, selector, exc)
            return default

    async def wait_and_focus(self, duration: float = 1.0) -> None:
        """
        Wait and focus window (helps with dynamic loading).

        Args:
            duration: Time to wait in seconds
        """
        await asyncio.sleep(duration)
        try:
            await self.browser.bring_to_front()
        except Exception as exc:
            logger.debug("bring_to_front failed during wait_and_focus: %s", exc)

    async def locate_profile_component_items(self) -> List[ElementPort]:
        """Return element items for profile detail list cards."""
        return await self.browser.query_selector_all(PROFILE_COMPONENT_ITEMS)

    async def wait_for_detail_section(self, heading: str) -> None:
        """Wait for a details page section, falling back to bare main."""
        try:
            await self.browser.wait_for_selector(
                f'main:has-text("{heading}")', timeout=5000
            )
        except Exception as exc:
            logger.debug("Detail section '%s' wait timed out, falling back to 'main': %s", heading, exc)
            await self.browser.wait_for_selector("main", timeout=5000)
