"""Shared base for composed person-section extractors."""

from __future__ import annotations

import logging
from typing import Any

from ...core.page_actions import wait_for_section_or_main
from ...core.rate_limit import RequestThrottler, get_default_throttler
from ...ports.browser import BrowserPort

logger = logging.getLogger(__name__)


class SectionExtractor:
    """Explicit dependency holder for person section extractors.

    Provides a throttled ``_goto`` so every section navigation is paced
    (one request at a time) through the shared :class:`RequestThrottler`.
    """

    def __init__(
        self,
        browser_or_host: BrowserPort | Any,
        throttler: RequestThrottler | None = None,
    ) -> None:
        if hasattr(browser_or_host, "browser"):
            self.browser: BrowserPort = browser_or_host.browser
        else:
            self.browser = browser_or_host
        self._throttler = throttler or get_default_throttler()

    async def _goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate with request throttling applied."""
        async with self._throttler:
            await self.browser.goto(url, wait_until=wait_until)

    async def _wait_for_detail_section(self, heading: str) -> None:
        """Wait for a details page section, falling back to bare main."""
        await wait_for_section_or_main(self.browser, heading)
