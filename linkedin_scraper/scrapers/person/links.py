"""Internal URL and contact helpers for the person scraper."""

from __future__ import annotations

import logging
from typing import Any

from ...parsers.person import clean_lines
from ...parsers.person_links import (
    SOCIAL_HOSTS,
    classify_link,
    contact_type_from_heading,
    merge_contacts,
    profile_detail_url,
    unwrap_href,
)
from ...ports.browser import BrowserPort, ElementPort

logger = logging.getLogger(__name__)


async def extract_item_text_and_url(
    item: ElementPort | Any, url_fragment: str
) -> tuple[list[str], str | None]:
    """Extract one card's visible lines and organization URL from the browser DOM."""
    href = None
    if hasattr(item, "query_selector_all"):
        links = await item.query_selector_all(f'a[href*="{url_fragment}"]')
        if links:
            href = await links[0].get_attribute("href")
    elif hasattr(item, "locator"):
        link = item.locator(f'a[href*="{url_fragment}"]').first
        if await link.count() > 0:
            href = await link.get_attribute("href")
    if href and href.startswith("/"):
        href = f"https://www.linkedin.com{href}"

    text = ""
    if hasattr(item, "inner_text"):
        text = await item.inner_text()
    elif hasattr(item, "text_content"):
        text = (await item.text_content()) or ""
    return clean_lines(text), href


async def attach_organization_urls(
    browser_or_page: BrowserPort | Any, items: list, url_fragment: str
) -> list:
    """Attach company/school URLs from page links when text parsing omitted them."""
    link_map: dict[str, str] = {}
    try:
        browser: BrowserPort = (
            browser_or_page.browser
            if hasattr(browser_or_page, "browser")
            else browser_or_page
        )
        if hasattr(browser, "query_selector_all"):
            links = await browser.query_selector_all(f'a[href*="{url_fragment}"]')
        else:
            links = []

        for link in links:
            href = ((await link.get_attribute("href")) or "").strip()
            text = ((await link.text_content()) or "").strip()
            if not href or not text:
                continue
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            link_map[text.lower()] = href
    except Exception as exc:
        logger.debug("Error collecting organization URLs: %s", exc)
        return items

    enriched = []
    for item in items:
        if item.linkedin_url or not item.institution_name:
            enriched.append(item)
            continue
        name = item.institution_name.lower()
        matched_href: str | None = link_map.get(name)
        if matched_href is None:
            for text, candidate in link_map.items():
                if name in text or text in name:
                    matched_href = candidate
                    break
        if matched_href:
            item = item.model_copy(update={"linkedin_url": matched_href})
        enriched.append(item)
    return enriched


__all__ = [
    "SOCIAL_HOSTS",
    "profile_detail_url",
    "unwrap_href",
    "classify_link",
    "contact_type_from_heading",
    "merge_contacts",
    "extract_item_text_and_url",
    "attach_organization_urls",
]
