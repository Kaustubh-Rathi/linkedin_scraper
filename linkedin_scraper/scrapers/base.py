"""Base scraper with common scraping functionality."""

import asyncio
import logging
from typing import Optional
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..core.auth import is_logged_in
from ..core.rate_limit import detect_rate_limit
from ..core.page_actions import (
    scroll_to_bottom,
    extract_text_safe,
)
from ..core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# Shared card selector for LinkedIn profile detail lists.
PROFILE_COMPONENT_ITEMS = (
    'main [data-view-name="profile-component-entity"], '
    "main .pvs-list__paged-list-item"
)


class BaseScraper:
    """Base class with common scraping functionality."""

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize base scraper.

        Args:
            page: Playwright page object
            callback: Progress callback (defaults to SilentCallback)
        """
        self.page = page
        self.callback = callback or SilentCallback()

    async def ensure_logged_in(self) -> None:
        """
        Verify user is authenticated.

        Raises:
            AuthenticationError: If not logged in
        """
        if not await is_logged_in(self.page):
            raise AuthenticationError(
                "Not logged in. Please authenticate before scraping."
            )

    async def check_rate_limit(self) -> None:
        """
        Check for rate limiting.

        Raises:
            RateLimitError: If rate limiting is detected
        """
        await detect_rate_limit(self.page)

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
        logger.info(f"Navigating to: {url}")
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)  # type: ignore
        await self.check_rate_limit()

    async def get_attribute_safe(
        self,
        selector: str,
        attribute: str,
        default: str = "",
        timeout: float = 2000,
    ) -> str:
        """
        Safely get element attribute.

        Args:
            selector: CSS selector
            attribute: Attribute name
            default: Default value if not found
            timeout: Timeout in milliseconds

        Returns:
            Attribute value or default
        """
        try:
            element = self.page.locator(selector).first
            value = await element.get_attribute(attribute, timeout=timeout)
            return value if value else default
        except Exception:
            return default

    async def wait_and_focus(self, duration: float = 1.0) -> None:
        """
        Wait and focus window (helps with dynamic loading).

        Args:
            duration: Time to wait in seconds
        """
        await asyncio.sleep(duration)
        try:
            await self.page.bring_to_front()
        except Exception:
            pass

    async def locate_profile_component_items(self):
        """Return locators for profile detail list cards."""
        return await self.page.locator(PROFILE_COMPONENT_ITEMS).all()

    async def wait_for_detail_section(self, heading: str) -> None:
        """Wait for a details page section, falling back to bare main."""
        try:
            await self.page.wait_for_selector(
                f'main:has-text("{heading}")', timeout=5000
            )
        except Exception:
            await self.page.wait_for_selector("main", timeout=5000)
