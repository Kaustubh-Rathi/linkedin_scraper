"""Interests section (Companies/Groups/Schools/Newsletters/Influencers) extraction."""

from __future__ import annotations

import logging
from typing import List, Optional, Set

from ...models import Interest
from .links import profile_detail_url
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class InterestsExtractor(SectionExtractor):
    """Extracts the tabbed Interests section of a profile."""

    async def get_interests(self, base_url: str) -> List[Interest]:
        """Extract interests from the main profile page Interests section with tablist."""
        interests: List[Interest] = []

        try:
            interests_heading = self.page.locator('h2:has-text("Interests")').first

            if await interests_heading.count() > 0:
                interests_section = interests_heading.locator(
                    'xpath=ancestor::*[.//tablist or .//*[@role="tablist"]][1]'
                )
                if await interests_section.count() == 0:
                    interests_section = interests_heading.locator("xpath=ancestor::*[4]")

                tabs = (
                    await interests_section.locator('[role="tab"], tab').all()
                    if await interests_section.count() > 0
                    else []
                )

                if tabs:
                    for tab in tabs:
                        try:
                            tab_name = await tab.text_content()
                            if not tab_name:
                                continue
                            tab_name = tab_name.strip()
                            category = self._map_interest_tab_to_category(tab_name)

                            await tab.click()
                            await self.wait_and_focus(0.5)

                            tabpanel = interests_section.locator('[role="tabpanel"]').first
                            if await tabpanel.count() > 0:
                                list_items = await tabpanel.locator("li, listitem").all()

                                for item in list_items:
                                    try:
                                        interest = await self._parse_interest_item(item, category)
                                        if interest:
                                            interests.append(interest)
                                    except Exception as e:
                                        logger.debug(f"Error parsing interest item: {e}")
                                        continue
                        except Exception as e:
                            logger.debug(f"Error processing interest tab: {e}")
                            continue

            if not interests:
                interests_url = profile_detail_url(base_url, "details/interests/")
                await self.navigate_and_wait(interests_url)
                await self.page.wait_for_selector("main", timeout=10000)
                await self.wait_and_focus(1.5)

                tabs = await self.page.locator('[role="tab"], tab').all()

                if not tabs:
                    logger.debug("No interests tabs found on profile")
                    return interests

                for tab in tabs:
                    try:
                        tab_name = await tab.text_content()
                        if not tab_name:
                            continue
                        tab_name = tab_name.strip()
                        category = self._map_interest_tab_to_category(tab_name)

                        await tab.click()
                        await self.wait_and_focus(0.8)

                        tabpanel = self.page.locator('[role="tabpanel"], tabpanel').first
                        list_items = await tabpanel.locator(
                            "listitem, li, .pvs-list__paged-list-item"
                        ).all()

                        for item in list_items:
                            try:
                                interest = await self._parse_interest_item(item, category)
                                if interest:
                                    interests.append(interest)
                            except Exception as e:
                                logger.debug(f"Error parsing interest item: {e}")
                                continue

                    except Exception as e:
                        logger.debug(f"Error processing interest tab: {e}")
                        continue

        except Exception as e:
            logger.warning(f"Error getting interests: {e}")

        return interests

    async def _parse_interest_item(self, item, category: str) -> Optional[Interest]:
        """Parse a single interest item from profile or details page."""
        try:
            link = item.locator("a, link").first
            if await link.count() == 0:
                return None
            href = await link.get_attribute("href")

            unique_texts = await self._extract_unique_texts_from_element(item)
            name = unique_texts[0] if unique_texts else None

            if name and href:
                return Interest(
                    name=name,
                    category=category,
                    linkedin_url=href,
                )
            return None
        except Exception as e:
            logger.debug(f"Error parsing interest: {e}")
            return None

    async def _extract_unique_texts_from_element(self, element) -> List[str]:
        """Extract unique text content from nested elements, avoiding duplicates from parent/child overlap."""
        text_elements = await element.locator(
            'span[aria-hidden="true"], div > span'
        ).all()

        if not text_elements:
            text_elements = await element.locator("span, div").all()

        seen_texts: Set[str] = set()
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

    def _map_interest_tab_to_category(self, tab_name: str) -> str:
        tab_lower = tab_name.lower()
        if "compan" in tab_lower:
            return "company"
        elif "group" in tab_lower:
            return "group"
        elif "school" in tab_lower:
            return "school"
        elif "newsletter" in tab_lower:
            return "newsletter"
        elif "voice" in tab_lower or "influencer" in tab_lower:
            return "influencer"
        else:
            return tab_lower
