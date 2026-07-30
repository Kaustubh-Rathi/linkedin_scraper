"""Experience section fetching, parsing, and deduplication."""

from __future__ import annotations

import logging
from typing import Dict, FrozenSet, List, Optional, Tuple

from ...models import Experience
from .links import attach_organization_urls, profile_detail_url
from .parser import (
    _looks_like_job_title,
    item_text_and_url,
    parse_experience_lines,
    parse_experiences_text,
)
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class ExperienceExtractor(SectionExtractor):
    """Extracts and normalizes the Experience section of a profile."""

    async def get_experiences(self, base_url: str) -> List[Experience]:
        """Extract experiences from the details/experience page (complete list)."""
        try:
            return await self._fetch_experiences_from_details(base_url)
        except Exception as e:
            logger.warning(
                f"Error getting experiences: {e}. The experience section may not be available or the page structure has changed."
            )
            return []

    async def _fetch_experiences_from_details(self, base_url: str) -> List[Experience]:
        """Scrape complete experience cards, with text as a fallback."""
        exp_url = profile_detail_url(base_url, "details/experience/")
        await self.navigate_and_wait(exp_url)
        await self.wait_for_detail_section("Experience")
        await self.scroll_page_to_bottom(pause_time=0.3, max_scrolls=4)

        experiences = await self._parse_experience_cards()
        if experiences:
            return self._dedupe_experiences(experiences)

        page_text = await self.page.locator("main").first.inner_text()
        experiences = parse_experiences_text(page_text)
        if experiences:
            experiences = await attach_organization_urls(
                self.page, experiences, "/company/"
            )
            return self._dedupe_experiences(experiences)

        await self.navigate_and_wait(base_url)
        experiences = await self._parse_experience_cards()
        return self._dedupe_experiences(experiences)

    async def _parse_experience_cards(self) -> List[Experience]:
        """Parse visible DOM cards, including grouped company roles."""
        experiences = []
        last_org_url = None
        items = await self.locate_profile_component_items()
        for item in items:
            try:
                lines, company_url = await item_text_and_url(item, "/company/")
                if company_url is None:
                    _, company_url = await item_text_and_url(item, "/school/")
                if company_url:
                    last_org_url = company_url
                else:
                    company_url = last_org_url
                parsed = parse_experience_lines(lines, company_url)
                experiences.extend(parsed)
            except Exception as exc:
                logger.debug("Error parsing experience card: %s", exc)
        return experiences

    @staticmethod
    def _dedupe_experiences(experiences: List[Experience]) -> List[Experience]:
        """Remove duplicate cards emitted by overlapping LinkedIn selectors."""
        by_identity: Dict[
            Tuple[Optional[str], Optional[str], Optional[str], FrozenSet[str]],
            Experience,
        ] = {}
        for experience in experiences:
            identity = (
                experience.from_date,
                experience.to_date,
                experience.duration,
                frozenset(
                    value
                    for value in (
                        experience.position_title,
                        experience.institution_name,
                    )
                    if value
                ),
            )
            existing = by_identity.get(identity)
            if existing is None:
                by_identity[identity] = experience
                continue

            prefer_new = False
            if experience.linkedin_url and not existing.linkedin_url:
                prefer_new = True
            elif _looks_like_job_title(
                experience.position_title or ""
            ) and not _looks_like_job_title(existing.position_title or ""):
                prefer_new = True
            if prefer_new:
                by_identity[identity] = experience
        return list(by_identity.values())
