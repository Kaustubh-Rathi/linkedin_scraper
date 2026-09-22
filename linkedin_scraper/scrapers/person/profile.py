"""Name, location, and about-section extraction for a person profile."""

from __future__ import annotations

import logging

from ...parsers.person import (
    location_from_header_lines as _pure_location_from_header_lines,
)
from ...parsers.person import (
    parse_about_section,
    parse_name_and_location,
    parse_open_to_work,
)
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class ProfileExtractor(SectionExtractor):
    """Profile identity (name/location/about)."""

    async def get_name_and_location(self) -> tuple[str | None, str | None]:
        """Extract name and location from profile DOM elements and pure parsing."""
        h1_text = await self.browser.extract_text_safe("h1", default="")
        h2_texts = []
        if not h1_text:
            for h2 in await self.browser.query_selector_all("h2"):
                txt = (await h2.text_content() or "").strip()
                if txt:
                    h2_texts.append(txt)

        main_text = None
        main_elements = await self.browser.query_selector_all("main")
        if main_elements:
            main_text = await main_elements[0].inner_text()

        return parse_name_and_location(h1_text, h2_texts, main_text)

    @staticmethod
    def location_from_header_lines(text: str, name: str) -> str | None:
        """Location sits after name/(pronouns)/headline and before Contact info."""
        return _pure_location_from_header_lines(text, name)

    async def check_open_to_work(self) -> bool:
        """Check if profile has open to work badge."""
        elements = await self.browser.query_selector_all(".pv-top-card-profile-picture img")
        img_title = ""
        if elements:
            img_title = (await elements[0].get_attribute("title")) or ""
        return parse_open_to_work(img_title)

    async def get_about(self) -> str | None:
        """Extract about section from profile sections."""
        sections = await self.browser.query_selector_all("section")
        section_texts = []
        for section in sections:
            txt = await section.inner_text()
            if txt:
                section_texts.append(txt)
        return parse_about_section(section_texts)
