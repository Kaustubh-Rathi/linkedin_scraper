"""Name, location, and about-section extraction for a person profile."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)

# Profile section headings that appear as <h2> but are not the person's name
SECTION_HEADINGS = {
    "About",
    "Featured",
    "Activity",
    "Experience",
    "Education",
    "Skills",
    "Interests",
    "Analytics",
    "Explore Premium profiles",
    "People also viewed",
    "Ad Options",
}


class ProfileExtractor(SectionExtractor):
    """Profile identity (name/location/about)."""

    async def get_name_and_location(self) -> Tuple[str, Optional[str]]:
        """Extract name and location from profile."""
        try:
            name = await self.safe_extract_text("h1", default="")
            if not name:
                for h2 in await self.page.locator("h2").all():
                    txt = (await h2.text_content() or "").strip()
                    if (
                        txt
                        and txt not in SECTION_HEADINGS
                        and "notification" not in txt.lower()
                    ):
                        name = txt
                        break

            location = None
            if name:
                main_text = await self.page.locator("main").first.inner_text()
                location = self.location_from_header_lines(main_text, name)

            return name if name else "Unknown", location
        except Exception as e:
            logger.warning(f"Error getting name/location: {e}")
            return "Unknown", None

    @staticmethod
    def location_from_header_lines(text: str, name: str) -> Optional[str]:
        """
        Location sits after name/(pronouns)/headline and before Contact info.
        Taking the last header line avoids picking suggested-profile headlines.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header: List[str] = []
        past_name = False
        for line in lines:
            if not past_name:
                if line == name:
                    past_name = True
                continue
            lower = line.lower()
            if (
                lower.startswith("contact")
                or "follower" in lower
                or "connection" in lower
            ):
                break
            if line in {"·", "•"}:
                continue
            if (
                "/" in line
                and len(line) <= 20
                and any(p in line for p in ("Him", "Her", "Them"))
            ):
                continue
            header.append(line)
        if not header:
            return None
        return header[-1]

    async def check_open_to_work(self) -> bool:
        """Check if profile has open to work badge."""
        try:
            img_title = await self.get_attribute_safe(
                ".pv-top-card-profile-picture img", "title", default=""
            )
            return "#OPEN_TO_WORK" in img_title.upper()
        except Exception:
            return False

    async def get_about(self) -> Optional[str]:
        """Extract about section from profile sections."""
        try:
            for section in await self.page.locator("section").all():
                txt = await section.inner_text()
                lines = [line.strip() for line in txt.splitlines() if line.strip()]
                if not lines or lines[0] != "About":
                    continue
                body = []
                for line in lines[1:]:
                    if line in SECTION_HEADINGS or line in {"… more", "... more"}:
                        break
                    body.append(line)
                if body:
                    return "\n".join(body).strip()
            return None
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")
            return None
