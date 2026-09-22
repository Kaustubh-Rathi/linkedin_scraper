"""Interests section (Companies/Groups/Schools/Newsletters/Influencers) extraction."""

from __future__ import annotations

import asyncio
import logging

from ...core.exceptions import AuthenticationError, RateLimitError
from ...models import Interest
from ...parsers.person import (
    map_interest_tab_to_category,
    parse_interest_item,
)
from ...ports.browser import ElementPort
from ._extractor import SectionExtractor
from .links import profile_detail_url

logger = logging.getLogger(__name__)


class InterestsExtractor(SectionExtractor):
    """Extracts the tabbed Interests section of a profile."""

    async def get_interests(self, base_url: str) -> list[Interest]:
        """Extract interests from the main profile page Interests section with tablist."""
        interests: list[Interest] = []

        try:
            tabs = await self.browser.query_selector_all('[role="tab"], tab')

            if tabs:
                for tab in tabs:
                    try:
                        tab_name = await tab.text_content()
                        if not tab_name:
                            continue
                        tab_name = tab_name.strip()
                        category = map_interest_tab_to_category(tab_name)

                        await tab.click()
                        await asyncio.sleep(0.5)

                        tabpanels = await self.browser.query_selector_all('[role="tabpanel"], tabpanel')
                        if tabpanels:
                            list_items = await tabpanels[0].query_selector_all(
                                "li, listitem, .pvs-list__paged-list-item"
                            )
                            for item in list_items:
                                try:
                                    interest = await self._parse_interest_item(item, category)
                                    if interest:
                                        interests.append(interest)
                                except Exception as e:
                                    logger.debug("Error parsing interest item: %s", e)
                                    continue
                    except Exception as e:
                        logger.debug("Error processing interest tab: %s", e)
                        continue

            if not interests:
                interests_url = profile_detail_url(base_url, "details/interests/")
                await self.browser.goto(interests_url, wait_until="domcontentloaded")
                try:
                    await self.browser.wait_for_selector("main", timeout=10000)
                except Exception as exc:
                    logger.debug("Interests main wait timed out: %s", exc)
                await asyncio.sleep(1.5)

                tabs = await self.browser.query_selector_all('[role="tab"], tab')
                if not tabs:
                    logger.debug("No interests tabs found on profile")
                    return interests

                for tab in tabs:
                    try:
                        tab_name = await tab.text_content()
                        if not tab_name:
                            continue
                        tab_name = tab_name.strip()
                        category = map_interest_tab_to_category(tab_name)

                        await tab.click()
                        await asyncio.sleep(0.8)

                        tabpanels = await self.browser.query_selector_all('[role="tabpanel"], tabpanel')
                        if tabpanels:
                            list_items = await tabpanels[0].query_selector_all(
                                "listitem, li, .pvs-list__paged-list-item"
                            )
                            for item in list_items:
                                try:
                                    interest = await self._parse_interest_item(item, category)
                                    if interest:
                                        interests.append(interest)
                                except Exception as e:
                                    logger.debug("Error parsing interest item: %s", e)
                                    continue

                    except Exception as e:
                        logger.debug("Error processing interest tab: %s", e)
                        continue

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning("Error getting interests: %s", e)

        return interests

    async def _parse_interest_item(self, item: ElementPort, category: str) -> Interest | None:
        """Extract raw attributes/text from item and delegate to pure parser."""
        try:
            links = await item.query_selector_all("a, link")
            if not links:
                return None
            href = await links[0].get_attribute("href")

            unique_texts = await self._extract_unique_texts_from_element(item)
            return parse_interest_item(unique_texts, href, category)
        except Exception as e:
            logger.debug("Error parsing interest: %s", e)
            return None

    async def _extract_unique_texts_from_element(self, element: ElementPort) -> list[str]:
        """Extract unique text content from nested elements, avoiding duplicates from parent/child overlap."""
        text_elements = await element.query_selector_all(
            'span[aria-hidden="true"], div > span'
        )

        if not text_elements:
            text_elements = await element.query_selector_all("span, div")

        seen_texts: set[str] = set()
        unique_texts = []

        for el in text_elements:
            text = await el.text_content()
            if text and text.strip():
                text = text.strip()
                if (
                    text not in seen_texts
                    and len(text) < 200
                    and not any(
                        text in t or t in text for t in seen_texts if len(t) > 3
                    )
                ):
                    seen_texts.add(text)
                    unique_texts.append(text)

        return unique_texts

    @staticmethod
    def _map_interest_tab_to_category(tab_name: str) -> str:
        """Map interest tab heading to normalized category via pure parser."""
        return map_interest_tab_to_category(tab_name)
