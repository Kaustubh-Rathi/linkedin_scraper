"""Contact info dialog extraction and outbound (Featured/custom) link collection."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from ...core.exceptions import AuthenticationError, RateLimitError
from ...models import Contact
from ...parsers.person import parse_contact_dialog_heading_and_links
from ...parsers.person_links import (
    classify_link,
    contact_type_from_heading,
    merge_contacts,
    profile_detail_url,
    unwrap_href,
)
from ...ports.browser import ElementPort
from ...selectors import PersonProfile as PersonSelectors
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class ContactsExtractor(SectionExtractor):
    """Extracts the contact-info dialog and outbound profile links."""

    async def extract_outbound_links(self) -> list[Contact]:
        """Collect Featured/custom outbound links from the current profile page."""
        contacts: list[Contact] = []
        try:
            links = await self.browser.query_selector_all(PersonSelectors.MAIN_ANCHORS)
            seen = set()
            for link in links:
                try:
                    href = ((await link.get_attribute("href")) or "").strip()
                    if not href:
                        continue
                    href = unwrap_href(href)
                    parsed_host = urlparse(href).netloc.lower()
                    path = urlparse(href).path.lower()
                    if "linkedin.com" in parsed_host or href.startswith("/"):
                        if href.startswith("/") or any(
                            p in path
                            for p in (
                                "/in/",
                                "/company/",
                                "/school/",
                                "/feed/",
                                "/mynetwork/",
                                "/jobs/",
                                "/messaging/",
                                "/notifications/",
                                "/preload/",
                                "/login",
                            )
                        ):
                            if not href.startswith("http") or "linkedin.com" in parsed_host:
                                continue
                    if href in seen:
                        continue
                    if not href.startswith("http"):
                        continue
                    if "linkedin.com" in urlparse(href).netloc.lower():
                        continue
                    label = ((await link.text_content()) or "").strip() or None
                    if label and len(label) > 80:
                        label = label[:80]
                    contact = classify_link(href, label)
                    seen.add(href)
                    contacts.append(contact)
                except Exception as exc:
                    logger.debug("Error parsing single outbound link: %s", exc)
                    continue
        except Exception as e:
            logger.debug("Error extracting outbound links: %s", e)
        return contacts

    async def get_contacts(self, base_url: str) -> list[Contact]:
        """Extract linked and plain-text fields from the contact-info dialog."""
        contacts: list[Contact] = []
        try:
            contact_url = profile_detail_url(base_url, "overlay/contact-info/")
            await self._goto(contact_url)
            try:
                await self.browser.wait_for_selector(
                    PersonSelectors.CONTACT_DIALOG_WAIT, timeout=5000
                )
            except Exception as exc:
                logger.debug("Contact info dialog wait timed out: %s", exc)

            dialogs = await self.browser.query_selector_all(
                PersonSelectors.CONTACT_DIALOG
            )
            if dialogs:
                dialog = dialogs[0]
                sections = await dialog.query_selector_all("section")
                if not sections:
                    sections = [dialog]
                for section in sections:
                    headings = await section.query_selector_all(
                        PersonSelectors.CONTACT_HEADING
                    )
                    if not headings:
                        continue
                    heading_text = ((await headings[0].text_content()) or "").strip()
                    contact_type = contact_type_from_heading(heading_text)
                    if not contact_type:
                        continue
                    links = await section.query_selector_all(PersonSelectors.CONTACT_LINK)
                    if links:
                        link_items = []
                        for link in links:
                            raw_href = ((await link.get_attribute("href")) or "").strip()
                            text = ((await link.text_content()) or "").strip()
                            if not raw_href:
                                continue
                            label = await self._contact_label(section)
                            link_items.append((raw_href, text, label))
                        parsed = parse_contact_dialog_heading_and_links(
                            heading_text, link_items, None
                        )
                        contacts.extend(parsed)
                    else:
                        plain_text = await section.inner_text()
                        parsed = parse_contact_dialog_heading_and_links(
                            heading_text, [], plain_text
                        )
                        contacts.extend(parsed)

            outbound = await self.extract_outbound_links()
            return merge_contacts(contacts, outbound)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            logger.warning("Error getting contacts: %s", e)
            return contacts

    @staticmethod
    async def _contact_label(container: ElementPort) -> str | None:
        """Return labels such as Mobile, Personal, or Work."""
        elements = await container.query_selector_all(
            PersonSelectors.CONTACT_LABEL_SPANS
        )
        for element in elements:
            text = ((await element.text_content()) or "").strip()
            if text.startswith("(") and text.endswith(")"):
                return text[1:-1].strip() or None
        return None
