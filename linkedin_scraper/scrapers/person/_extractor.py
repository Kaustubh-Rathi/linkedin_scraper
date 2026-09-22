"""Shared base for composed person-section extractors."""

from __future__ import annotations

import logging
from typing import Any

from ...ports.browser import BrowserPort

logger = logging.getLogger(__name__)


class SectionExtractor:
    """Explicit dependency holder for person section extractors."""

    def __init__(self, browser_or_host: BrowserPort | Any) -> None:
        if hasattr(browser_or_host, "browser"):
            self.browser: BrowserPort = browser_or_host.browser
        else:
            self.browser = browser_or_host

    async def _wait_for_detail_section(self, heading: str) -> None:
        """Wait for a details page section, falling back to bare main."""
        try:
            await self.browser.wait_for_selector(
                f'main:has-text("{heading}")', timeout=5000
            )
        except Exception as exc:
            logger.debug("Detail section '%s' wait timed out: %s", heading, exc)
            await self.browser.wait_for_selector("main", timeout=5000)
