"""Skills section extraction from a person profile."""

from __future__ import annotations

import logging

from ...core.exceptions import AuthenticationError, RateLimitError
from ...parsers.person import parse_skill_name
from ...ports.browser import ElementPort
from ...selectors import PersonProfile as PersonSelectors
from ..base import PROFILE_COMPONENT_ITEMS
from ._extractor import SectionExtractor
from .links import profile_detail_url

logger = logging.getLogger(__name__)


class SkillsExtractor(SectionExtractor):
    """Extracts the Skills section (details/skills) of a profile."""

    async def get_skills(self, base_url: str) -> list[str]:
        """Extract skill names from the details/skills page (complete list)."""
        try:
            return await self._fetch_skills_from_details(base_url)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning(
                "Error getting skills: %s. The skills section may not be available or the page structure has changed.",
                e,
            )
            return []

    async def _fetch_skills_from_details(self, base_url: str) -> list[str]:
        skills_url = profile_detail_url(base_url, "details/skills/")
        await self._goto(skills_url)
        await self._wait_for_detail_section("Skills")

        items = await self.browser.query_selector_all(PROFILE_COMPONENT_ITEMS)
        if not items:
            items = await self.browser.query_selector_all(
                PersonSelectors.DETAIL_LIST_ITEMS
            )

        skills: list[str] = []
        seen: set[str] = set()
        for item in items:
            try:
                skill = await self._parse_skill_item(item)
                if skill and skill.lower() not in seen:
                    seen.add(skill.lower())
                    skills.append(skill)
            except Exception as exc:
                logger.debug("Error parsing skill card: %s", exc)
        return skills

    async def _parse_skill_item(self, item: ElementPort) -> str | None:
        """Extract raw span texts from a skill card and delegate to the pure parser."""
        entities = await item.query_selector_all(PersonSelectors.ENTITY)
        if entities:
            span_elements = await entities[0].query_selector_all(
                PersonSelectors.HIDDEN_SPAN
            )
        else:
            span_elements = await item.query_selector_all(PersonSelectors.HIDDEN_SPAN)

        spans = [((await s.text_content()) or "") for s in span_elements]
        return parse_skill_name(spans)
