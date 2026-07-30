"""Contact info dialog extraction and outbound (Featured/custom) link collection."""

from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urlparse

from ...models import Contact
from .links import (
    classify_link,
    contact_type_from_heading,
    merge_contacts,
    profile_detail_url,
    unwrap_href,
)
from ._extractor import SectionExtractor

logger = logging.getLogger(__name__)


class ContactsExtractor(SectionExtractor):
    """Extracts the contact-info dialog and outbound profile links."""

    async def extract_outbound_links(self) -> List[Contact]:
        """Collect Featured/custom outbound links from the current profile page."""
        contacts: List[Contact] = []
        try:
            links = await self.page.locator("main a[href]").all()
            seen = set()
            for link in links:
                try:
                    href = (await link.get_attribute("href") or "").strip()
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
                    label = (await link.text_content() or "").strip() or None
                    if label and len(label) > 80:
                        label = label[:80]
                    contact = classify_link(href, label)
                    seen.add(href)
                    contacts.append(contact)
                except Exception:
                    continue
        except Exception as e:
            logger.debug("Error extracting outbound links: %s", e)
        return contacts

    async def get_contacts(self, base_url: str) -> List[Contact]:
        """Extract linked and plain-text fields from the contact-info dialog."""
        contacts = []
        try:
            contact_url = profile_detail_url(base_url, "overlay/contact-info/")
            await self.navigate_and_wait(contact_url)
            try:
                await self.page.wait_for_selector("main, [role='dialog']", timeout=5000)
            except Exception:
                pass

            dialog = self.page.locator('dialog, [role="dialog"]').first
            if await dialog.count() > 0:
                for heading in await dialog.locator("h3").all():
                    heading_text = (await heading.text_content() or "").strip()
                    contact_type = contact_type_from_heading(heading_text)
                    if not contact_type:
                        continue
                    container = heading.locator("xpath=..")
                    links = await container.locator("a[href]").all()
                    if links:
                        for link in links:
                            raw_href = (await link.get_attribute("href") or "").strip()
                            text = (await link.text_content() or "").strip()
                            if not raw_href:
                                continue
                            href = unwrap_href(raw_href)
                            label = await self._contact_label(container)
                            if href.startswith("mailto:"):
                                value = href[7:]
                            elif href.startswith("tel:"):
                                value = href[4:]
                            elif contact_type in {"linkedin", "website", "twitter"}:
                                value = href
                            else:
                                value = text or href
                            if contact_type == "website":
                                contacts.append(classify_link(value, label))
                            else:
                                contacts.append(
                                    Contact(
                                        type=contact_type,
                                        value=value,
                                        label=label,
                                    )
                                )
                    else:
                        plain_value = self.plain_contact_value(
                            await container.inner_text(), heading_text
                        )
                        if plain_value:
                            contacts.append(
                                Contact(type=contact_type, value=plain_value)
                            )

            outbound = await self.extract_outbound_links()
            return merge_contacts(contacts, outbound)
        except Exception as e:
            logger.warning(f"Error getting contacts: {e}")
            return contacts

    @staticmethod
    async def _contact_label(container) -> Optional[str]:
        """Return labels such as Mobile, Personal, or Work."""
        for element in await container.locator("span, generic").all():
            text = (await element.text_content() or "").strip()
            if text.startswith("(") and text.endswith(")"):
                return text[1:-1].strip() or None
        return None

    @staticmethod
    def plain_contact_value(text: str, heading: str) -> Optional[str]:
        """Remove a contact heading while retaining a non-linked value."""
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and line.strip().lower() != heading.lower()
        ]
        return "\n".join(lines).strip() or None
