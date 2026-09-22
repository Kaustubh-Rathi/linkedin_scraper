"""Education section fetching, parsing, and deduplication."""

from __future__ import annotations

import logging

from ...core.exceptions import AuthenticationError, RateLimitError
from ...core.page_actions import scroll_to_bottom
from ...models import Education
from ...parsers.person import (
    parse_education_lines,
    parse_educations_text,
)
from ..base import PROFILE_COMPONENT_ITEMS
from ._extractor import SectionExtractor
from .links import attach_organization_urls, extract_item_text_and_url, profile_detail_url

logger = logging.getLogger(__name__)


class EducationExtractor(SectionExtractor):
    """Extracts and normalizes the Education section of a profile."""

    async def get_educations(self, base_url: str) -> list[Education]:
        """Extract educations from the details/education page (complete list)."""
        try:
            return await self._fetch_educations_from_details(base_url)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning(
                "Error getting educations: %s. The education section may not be publicly visible or the page structure has changed.",
                e,
            )
            return []

    async def _fetch_educations_from_details(self, base_url: str) -> list[Education]:
        """Scrape complete education cards, with text as a fallback."""
        edu_url = profile_detail_url(base_url, "details/education/")
        await self._goto(edu_url)
        await self._wait_for_detail_section("Education")
        await scroll_to_bottom(self.browser, pause_time=0.3, max_scrolls=3)

        educations = await self._parse_education_cards()
        if educations:
            return self._dedupe_educations(educations)

        main_elements = await self.browser.query_selector_all("main")
        if main_elements:
            page_text = await main_elements[0].inner_text()
            educations = parse_educations_text(page_text)
            if educations:
                educations = await attach_organization_urls(
                    self.browser, educations, "/school/"
                )
                return self._dedupe_educations(educations)

        await self._goto(base_url)
        educations = await self._parse_education_cards()
        return self._dedupe_educations(educations)

    async def _parse_education_cards(self) -> list[Education]:
        """Parse visible education cards and preserve school links when present."""
        educations = []
        items = await self.browser.query_selector_all(PROFILE_COMPONENT_ITEMS)
        for item in items:
            try:
                lines, institution_url = await extract_item_text_and_url(item, "/school/")
                education = parse_education_lines(lines, institution_url)
                if education:
                    educations.append(education)
            except Exception as exc:
                logger.debug("Error parsing education card: %s", exc)
        return educations

    @staticmethod
    def _dedupe_educations(educations: list[Education]) -> list[Education]:
        """Remove duplicate cards emitted by overlapping selectors."""
        by_key = {}
        for education in educations:
            key = (
                education.institution_name,
                education.degree,
                education.from_date,
                education.to_date,
            )
            by_key[key] = education
        return list(by_key.values())
