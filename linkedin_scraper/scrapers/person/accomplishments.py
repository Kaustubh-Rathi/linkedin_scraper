"""Accomplishments (certifications, honors, publications, etc.) extraction."""

from __future__ import annotations

import asyncio
import logging

from ...core.exceptions import AuthenticationError, RateLimitError
from ...models import Accomplishment
from ...parsers.person import parse_accomplishment_item
from ...ports.browser import ElementPort
from ._extractor import SectionExtractor
from .links import profile_detail_url

logger = logging.getLogger(__name__)


class AccomplishmentsExtractor(SectionExtractor):
    """Extracts certification/honor/publication/etc. sections of a profile."""

    async def get_accomplishments(self, base_url: str) -> list[Accomplishment]:
        accomplishments: list[Accomplishment] = []

        accomplishment_sections = [
            ("certifications", "certification"),
            ("honors", "honor"),
            ("publications", "publication"),
            ("patents", "patent"),
            ("courses", "course"),
            ("projects", "project"),
            ("languages", "language"),
            ("organizations", "organization"),
        ]

        for url_path, category in accomplishment_sections:
            try:
                section_url = profile_detail_url(base_url, f"details/{url_path}/")
                await self.browser.goto(section_url, wait_until="domcontentloaded")
                try:
                    await self.browser.wait_for_selector("main", timeout=10000)
                except Exception as exc:
                    logger.debug("Selector wait for 'main' timed out in accomplishments/%s: %s", url_path, exc)
                await asyncio.sleep(1)

                nothing_elements = await self.browser.query_selector_all('text="Nothing to see for now"')
                if nothing_elements:
                    continue

                main_elements = await self.browser.query_selector_all("main")
                if main_elements:
                    main_txt = (await main_elements[0].text_content()) or ""
                    if "Nothing to see for now" in main_txt:
                        continue

                items = await self.browser.query_selector_all(
                    ".pvs-list__container .pvs-list__paged-list-item, main ul .pvs-list__paged-list-item, main ol .pvs-list__paged-list-item, .pvs-list__container > li, main ul > li, main ol > li"
                )

                seen_titles = set()
                for item in items:
                    try:
                        accomplishment = await self._parse_accomplishment_item(
                            item, category
                        )
                        if accomplishment and accomplishment.title not in seen_titles:
                            seen_titles.add(accomplishment.title)
                            accomplishments.append(accomplishment)
                    except Exception as e:
                        logger.debug("Error parsing %s item: %s", category, e)
                        continue

            except (AuthenticationError, RateLimitError):
                raise
            except Exception as e:
                logger.debug("Non-fatal error getting %ss: %s", category, e)
                continue

        return accomplishments

    async def _parse_accomplishment_item(
        self, item: ElementPort, category: str
    ) -> Accomplishment | None:
        """Extract raw text and URL attributes from item DOM and delegate to pure parser."""
        entities = await item.query_selector_all('div[data-view-name="profile-component-entity"]')
        if entities:
            span_elements = await entities[0].query_selector_all('span[aria-hidden="true"]')
        else:
            span_elements = await item.query_selector_all('span[aria-hidden="true"]')

        spans = [((await s.text_content()) or "") for s in span_elements]

        links = await item.query_selector_all('a[href*="credential"], a[href*="verify"]')
        credential_url = (
            (await links[0].get_attribute("href")) if links else None
        )

        return parse_accomplishment_item(spans, credential_url, category)
