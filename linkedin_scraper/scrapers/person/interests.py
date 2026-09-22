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
from ...selectors import PersonProfile as PersonSelectors
from ._extractor import SectionExtractor
from .links import profile_detail_url

logger = logging.getLogger(__name__)


class InterestsExtractor(SectionExtractor):
    """Extracts the tabbed Interests section of a profile."""

    async def get_interests(self, base_url: str) -> list[Interest]:
        """Extract interests from the profile Interests tabs, falling back to the details page."""
        interests: list[Interest] = []

        try:
            interests = await self._collect_from_tabs()

            if not interests:
                interests_url = profile_detail_url(base_url, "details/interests/")
                await self._goto(interests_url)
                try:
                    await self.browser.wait_for_selector(
                        PersonSelectors.MAIN, timeout=10000
                    )
                except Exception as exc:
                    logger.debug("Interests main wait timed out: %s", exc)
                await asyncio.sleep(1.5)

                interests = await self._collect_from_tabs()
                if not interests:
                    logger.debug("No interests tabs found on profile")

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning("Error getting interests: %s", e)

        return interests

    async def _collect_from_tabs(self) -> list[Interest]:
        """Iterate every interest tab once and collect items from its panel."""
        interests: list[Interest] = []
        tabs = await self.browser.query_selector_all(PersonSelectors.TABS)
        for tab in tabs:
            try:
                tab_name = await tab.text_content()
                if not tab_name:
                    continue
                category = map_interest_tab_to_category(tab_name.strip())

                await tab.click()
                await asyncio.sleep(0.5)

                tabpanels = await self.browser.query_selector_all(
                    PersonSelectors.TAB_PANELS
                )
                if not tabpanels:
                    continue
                list_items = await tabpanels[0].query_selector_all(
                    PersonSelectors.INTEREST_ITEMS
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
            PersonSelectors.INTEREST_TEXT_SPANS
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
