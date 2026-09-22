"""Experience section fetching, parsing, and deduplication."""

from __future__ import annotations

import logging

from ...core.exceptions import AuthenticationError, RateLimitError
from ...core.page_actions import scroll_to_bottom
from ...models import Experience
from ...parsers.person import (
    _looks_like_job_title,
    parse_experience_lines,
    parse_experiences_text,
)
from ..base import PROFILE_COMPONENT_ITEMS
from ._extractor import SectionExtractor
from .links import attach_organization_urls, extract_item_text_and_url, profile_detail_url

logger = logging.getLogger(__name__)


class ExperienceExtractor(SectionExtractor):
    """Extracts and normalizes the Experience section of a profile."""

    async def get_experiences(self, base_url: str) -> list[Experience]:
        """Extract experiences from the details/experience page (complete list)."""
        try:
            return await self._fetch_experiences_from_details(base_url)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning(
                "Error getting experiences: %s. The experience section may not be available or the page structure has changed.",
                e,
            )
            return []

    async def get_volunteer_experiences(self, base_url: str) -> list[Experience]:
        """Extract volunteer experience from the details/volunteering-experiences page."""
        try:
            return await self._fetch_experiences_from_details(
                base_url,
                detail_path="details/volunteering-experiences/",
                heading="Volunteer",
            )
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning(
                "Error getting volunteer experiences: %s. The section may not be available or the page structure has changed.",
                e,
            )
            return []

    async def _fetch_experiences_from_details(
        self,
        base_url: str,
        detail_path: str = "details/experience/",
        heading: str = "Experience",
    ) -> list[Experience]:
        """Scrape complete experience cards, with text as a fallback."""
        exp_url = profile_detail_url(base_url, detail_path)
        await self._goto(exp_url)
        await self._wait_for_detail_section(heading)
        await scroll_to_bottom(self.browser, pause_time=0.3, max_scrolls=4)

        experiences = await self._parse_experience_cards()
        if experiences:
            return self._dedupe_experiences(experiences)

        main_elements = await self.browser.query_selector_all("main")
        if main_elements:
            page_text = await main_elements[0].inner_text()
            experiences = parse_experiences_text(page_text)
            if experiences:
                experiences = await attach_organization_urls(
                    self.browser, experiences, "/company/"
                )
                return self._dedupe_experiences(experiences)

        await self._goto(base_url)
        experiences = await self._parse_experience_cards()
        return self._dedupe_experiences(experiences)

    async def _parse_experience_cards(self) -> list[Experience]:
        """Parse visible DOM cards, including grouped company roles."""
        experiences = []
        last_org_url = None
        items = await self.browser.query_selector_all(PROFILE_COMPONENT_ITEMS)
        for item in items:
            try:
                lines, company_url = await extract_item_text_and_url(item, "/company/")
                if company_url is None:
                    _, company_url = await extract_item_text_and_url(item, "/school/")
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
    def _dedupe_experiences(experiences: list[Experience]) -> list[Experience]:
        """Remove duplicate cards emitted by overlapping LinkedIn selectors."""
        by_identity: dict[
            tuple[str | None, str | None, str | None, frozenset[str]],
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
