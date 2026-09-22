"""Name, headline, location, and about-section extraction for a person profile."""

from __future__ import annotations

import logging

from ...parsers.person import (
    parse_about_section,
    parse_headline,
    parse_name_and_location,
    parse_open_to_work,
)
from ...selectors import PersonProfile as PersonSelectors
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class ProfileExtractor(SectionExtractor):
    """Profile identity (name/headline/location/about)."""

    async def get_name_and_location(self) -> tuple[str | None, str | None]:
        """Extract name and location from profile DOM elements and pure parsing."""
        h1_text = await self.browser.extract_text_safe(PersonSelectors.H1, default="")
        h2_texts = []
        if not h1_text:
            for h2 in await self.browser.query_selector_all(PersonSelectors.H2):
                txt = (await h2.text_content() or "").strip()
                if txt:
                    h2_texts.append(txt)

        main_text = None
        main_elements = await self.browser.query_selector_all(PersonSelectors.MAIN)
        if main_elements:
            main_text = await main_elements[0].inner_text()

        return parse_name_and_location(h1_text, h2_texts, main_text)

    async def get_headline(self, name: str | None) -> str | None:
        """Extract the profile headline from the top-card header lines."""
        main_text = None
        main_elements = await self.browser.query_selector_all(PersonSelectors.MAIN)
        if main_elements:
            main_text = await main_elements[0].inner_text()
        return parse_headline(main_text, name)

    async def check_open_to_work(self) -> bool:
        """Check if profile has open to work badge."""
        elements = await self.browser.query_selector_all(
            PersonSelectors.OPEN_TO_WORK_IMAGE
        )
        img_title = ""
        if elements:
            img_title = (await elements[0].get_attribute("title")) or ""
        return parse_open_to_work(img_title)

    async def get_about(self) -> str | None:
        """Extract about section from profile sections."""
        sections = await self.browser.query_selector_all(PersonSelectors.SECTION)
        section_texts = []
        for section in sections:
            txt = await section.inner_text()
            if txt:
                section_texts.append(txt)
        return parse_about_section(section_texts)
