"""Education section fetching, parsing, and deduplication."""

from __future__ import annotations

import logging
from typing import List

from ...models import Education
from .links import attach_organization_urls, profile_detail_url
from .parser import (
    item_text_and_url,
    parse_education_lines,
    parse_educations_text,
)
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class EducationExtractor(SectionExtractor):
    """Extracts and normalizes the Education section of a profile."""

    async def get_educations(self, base_url: str) -> List[Education]:
        """Extract educations from the details/education page (complete list)."""
        try:
            return await self._fetch_educations_from_details(base_url)
        except Exception as e:
            logger.warning(
                f"Error getting educations: {e}. The education section may not be publicly visible or the page structure has changed."
            )
            return []

    async def _fetch_educations_from_details(self, base_url: str) -> List[Education]:
        """Scrape complete education cards, with text as a fallback."""
        edu_url = profile_detail_url(base_url, "details/education/")
        await self.navigate_and_wait(edu_url)
        await self.wait_for_detail_section("Education")
        await self.scroll_page_to_bottom(pause_time=0.3, max_scrolls=3)

        educations = await self._parse_education_cards()
        if educations:
            return self._dedupe_educations(educations)

        page_text = await self.page.locator("main").first.inner_text()
        educations = parse_educations_text(page_text)
        if educations:
            educations = await attach_organization_urls(
                self.page, educations, "/school/"
            )
            return self._dedupe_educations(educations)

        await self.navigate_and_wait(base_url)
        educations = await self._parse_education_cards()
        return self._dedupe_educations(educations)

    async def _parse_education_cards(self) -> List[Education]:
        """Parse visible education cards and preserve school links when present."""
        educations = []
        items = await self.locate_profile_component_items()
        for item in items:
            try:
                lines, institution_url = await item_text_and_url(item, "/school/")
                education = parse_education_lines(lines, institution_url)
                if education:
                    educations.append(education)
            except Exception as exc:
                logger.debug("Error parsing education card: %s", exc)
        return educations

    @staticmethod
    def _dedupe_educations(educations: List[Education]) -> List[Education]:
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
