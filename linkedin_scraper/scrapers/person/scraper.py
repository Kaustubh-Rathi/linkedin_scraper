"""Person/Profile scraper for LinkedIn (orchestration only)."""

from __future__ import annotations

import logging
from typing import Any

from ...callbacks import ProgressCallback
from ...core.exceptions import (
    AuthenticationError,
    RateLimitError,
    RequiredFieldExtractionError,
    ScrapingError,
)
from ...models import Accomplishment, Interest, Person
from ...ports.browser import BrowserPort
from ..base import BaseScraper
from .accomplishments import AccomplishmentsExtractor
from .contacts import ContactsExtractor
from .education import EducationExtractor
from .experience import ExperienceExtractor
from .interests import InterestsExtractor
from .links import merge_contacts
from .profile import ProfileExtractor

logger = logging.getLogger(__name__)


class PersonScraper(BaseScraper):
    """Async scraper for LinkedIn person profiles.

    Section extractors are composed (not mixed in) so each area stays
    independently testable while this class only orchestrates the scrape.
    """

    def __init__(
        self,
        page_or_browser: BrowserPort | Any = None,
        callback: ProgressCallback | None = None,
        *,
        page: BrowserPort | Any = None,
    ):
        """
        Initialize person scraper.

        Args:
            page_or_browser: BrowserPort instance or legacy page object
            callback: Progress callback
            page: Keyword argument alias for page_or_browser (backward compatibility)
        """
        super().__init__(page_or_browser, callback, page=page)
        self._profile = ProfileExtractor(self.browser)
        self._experience = ExperienceExtractor(self.browser)
        self._education = EducationExtractor(self.browser)
        self._interests = InterestsExtractor(self.browser)
        self._accomplishments = AccomplishmentsExtractor(self.browser)
        self._contacts = ContactsExtractor(self.browser)

    async def scrape(
        self,
        linkedin_url: str,
        *,
        include_interests: bool = True,
        include_accomplishments: bool = True,
    ) -> Person:
        """
        Scrape a LinkedIn person profile.

        Args:
            linkedin_url: LinkedIn profile URL
            include_interests: Also scrape interests tabs (enabled by default)
            include_accomplishments: Also scrape certifications/honors/etc.
                (enabled by default for backward compatibility)

        Returns:
            Person object with scraped data

        Raises:
            AuthenticationError: If not logged in
            RequiredFieldExtractionError: If required fields (e.g. name) cannot be extracted
            ScrapingError: If scraping fails
        """
        if not linkedin_url:
            raise RequiredFieldExtractionError(field_name="linkedin_url", entity_url=linkedin_url)

        await self.callback.on_start("person", linkedin_url)

        try:
            await self.navigate_and_wait(linkedin_url)
            await self.callback.on_progress("Navigated to profile", 10)
            await self.ensure_logged_in()
            await self.browser.wait_for_selector("main", timeout=10000)

            name, location = await self._profile.get_name_and_location()
            if not name:
                logger.error("Failed to extract required field 'name' for person profile: %s", linkedin_url)
                raise RequiredFieldExtractionError(field_name="name", entity_url=linkedin_url)
            await self.callback.on_progress(f"Got name: {name}", 20)

            open_to_work = await self._profile.check_open_to_work()
            about = await self._profile.get_about()
            await self.callback.on_progress("Got about section", 30)

            profile_links = await self._contacts.extract_outbound_links()

            experiences = await self._experience.get_experiences(linkedin_url)
            await self.callback.on_progress(f"Got {len(experiences)} experiences", 55)

            educations = await self._education.get_educations(linkedin_url)
            await self.callback.on_progress(f"Got {len(educations)} educations", 70)

            interests: list[Interest] = []
            if include_interests:
                interests = await self._interests.get_interests(linkedin_url)
                await self.callback.on_progress(f"Got {len(interests)} interests", 80)

            accomplishments: list[Accomplishment] = []
            if include_accomplishments:
                accomplishments = await self._accomplishments.get_accomplishments(
                    linkedin_url
                )
                await self.callback.on_progress(
                    f"Got {len(accomplishments)} accomplishments", 90
                )

            contacts = await self._contacts.get_contacts(linkedin_url)
            contacts = merge_contacts(contacts, profile_links)
            await self.callback.on_progress(f"Got {len(contacts)} contacts", 95)

            person = Person(
                linkedin_url=linkedin_url,
                name=name,
                location=location,
                about=about,
                open_to_work=open_to_work,
                experiences=experiences,
                educations=educations,
                interests=interests,
                accomplishments=accomplishments,
                contacts=contacts,
            )

            await self.callback.on_progress("Scraping complete", 100)
            await self.callback.on_complete("person", person)
            return person

        except (AuthenticationError, RateLimitError, RequiredFieldExtractionError) as direct_err:
            logger.error("Error while scraping person %s: %s", linkedin_url, direct_err)
            await self.callback.on_error(direct_err)
            raise
        except Exception as e:
            logger.exception("Unexpected error while scraping person %s: %s", linkedin_url, e)
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to scrape person profile: {e}") from e

