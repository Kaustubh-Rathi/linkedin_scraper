"""
Company scraper for LinkedIn.

Extracts company information from LinkedIn company pages.
"""
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
from ...models.company import Company
from ...parsers.company import (
    parse_about_section,
    parse_company_name,
    parse_company_overview,
)
from ...ports.browser import BrowserPort
from ...selectors import Company as CompanySelectors
from ..base import BaseScraper

logger = logging.getLogger(__name__)


def _build_about_url(url: str) -> str:
    """Normalize a company LinkedIn URL to its /about/ subpage."""
    base = url.split("?")[0].split("#")[0].rstrip("/")
    if base.endswith("/about"):
        base = base[:-len("/about")]
    return f"{base}/about/"


class CompanyScraper(BaseScraper):
    """
    Scraper for LinkedIn company pages.

    Example:
        async with BrowserManager() as browser:
            scraper = CompanyScraper(browser.browser_port)
            company = await scraper.scrape("https://www.linkedin.com/company/microsoft/")
            print(company.to_json())
    """

    def __init__(
        self,
        page_or_browser: BrowserPort | Any = None,
        callback: ProgressCallback | None = None,
        *,
        page: BrowserPort | Any = None,
        throttler: Any | None = None,
    ):
        """
        Initialize company scraper.

        Args:
            page_or_browser: BrowserPort instance or legacy page object
            callback: Optional progress callback
            page: Keyword argument alias for page_or_browser (for backward compatibility)
        """
        super().__init__(page_or_browser, callback, page=page, throttler=throttler)

    async def scrape(self, linkedin_url: str) -> Company:
        """
        Scrape a LinkedIn company page.

        Args:
            linkedin_url: URL of the LinkedIn company page

        Returns:
            Company object with scraped data

        Raises:
            AuthenticationError: If not logged in
            RequiredFieldExtractionError: If required fields (e.g. name) cannot be extracted
            ScrapingError: If scraping fails
        """
        logger.info(f"Starting company scraping: {linkedin_url}")
        await self.callback.on_start("company", linkedin_url)

        if not linkedin_url:
            raise RequiredFieldExtractionError(field_name="linkedin_url", entity_url=linkedin_url)

        try:
            # Navigate to /about/ subpage — overview fields are only present there
            about_url = _build_about_url(linkedin_url)
            await self.navigate_and_wait(about_url)
            await self.callback.on_progress("Navigated to company about page", 10)

            # Extract basic info
            name = await self._get_name()
            if not name:
                logger.error("Failed to extract required field 'name' for company %s", linkedin_url)
                raise RequiredFieldExtractionError(field_name="name", entity_url=linkedin_url)
            await self.callback.on_progress(f"Got company name: {name}", 20)

            about_us = await self._get_about()
            await self.callback.on_progress("Got about section", 30)

            # Extract overview details
            overview = await self._get_overview()
            await self.callback.on_progress("Got overview details", 50)

            # Create company object
            company = Company(
                linkedin_url=linkedin_url,
                name=name,
                about_us=about_us,
                website=overview.get("website"),
                phone=overview.get("phone"),
                headquarters=overview.get("headquarters"),
                founded=overview.get("founded"),
                industry=overview.get("industry"),
                company_type=overview.get("company_type"),
                company_size=overview.get("company_size"),
                specialties=overview.get("specialties"),
            )

            await self.callback.on_progress("Scraping complete", 100)
            await self.callback.on_complete("company", company)

            logger.info("Successfully scraped company: %s", name)
            return company
        except (AuthenticationError, RateLimitError, RequiredFieldExtractionError) as direct_err:
            logger.error("Error while scraping company %s: %s", linkedin_url, direct_err)
            await self.callback.on_error(direct_err)
            raise
        except Exception as e:
            logger.exception("Unexpected error while scraping company %s: %s", linkedin_url, e)
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to scrape company profile: {e}") from e

    async def _get_name(self) -> str | None:
        """Extract company name from h1 or h2 heading within main/top-card or document title."""
        raw_name = await self.browser.extract_text_safe("h1", default="")
        if not raw_name:
            logger.debug("Company h1 heading not found; falling back to candidate h2 headings")
            try:
                for h2 in await self.browser.query_selector_all(
                    CompanySelectors.NAME_HEADINGS
                ):
                    txt = (await h2.inner_text() or "").strip()
                    if (
                        txt
                        and "notification" not in txt.lower()
                        and txt not in (
                            "About",
                            "Overview",
                            "Highlights",
                            "Jobs",
                            "People",
                            "Posts",
                            "Life",
                            "Similar pages",
                            "Affiliated pages",
                            "Locations",
                            "Commitments",
                            "Hybrid workplace",
                        )
                        and not txt.startswith("Interested in")
                    ):
                        raw_name = txt
                        break
            except Exception as exc:
                logger.debug("Query selector for h2 failed: %s", exc)

        if not raw_name:
            try:
                title = await self.browser.evaluate("document.title || ''")
                title_text = str(title).strip() if title is not None else ""
                if title_text and ":" in title_text:
                    raw_name = title_text.split(":")[0].strip()
                elif title_text and "|" in title_text:
                    raw_name = title_text.split("|")[0].strip()
            except Exception as exc:
                logger.debug("Document title fallback for company name failed: %s", exc)

        return parse_company_name(raw_name)





    async def _get_about(self) -> str | None:
        """Extract about/description section."""
        # 1. Try modern SDUI Overview heading and paragraph extraction via JS
        try:
            desc = await self.browser.evaluate("""() => {
                const headings = Array.from(document.querySelectorAll('h2, h3, div, p'));
                for (const h of headings) {
                    const txt = (h.innerText || h.textContent || '').trim();
                    if (txt === 'Overview' || txt === 'About us' || txt === 'About') {
                        let sib = h.nextElementSibling;
                        if (!sib && h.parentElement) {
                            sib = h.parentElement.nextElementSibling;
                        }
                        if (!sib && h.parentElement && h.parentElement.parentElement) {
                            sib = h.parentElement.parentElement.nextElementSibling;
                        }
                        if (sib) {
                            const pEl = sib.querySelector('p');
                            if (pEl) {
                                const pTxt = (pEl.innerText || pEl.textContent || '').trim();
                                if (pTxt && pTxt.length > 20) return pTxt;
                            }
                            const firstLine = (sib.innerText || sib.textContent || '').trim().split('\\n\\n')[0].trim();
                            if (firstLine && firstLine.length > 20 && !firstLine.startsWith('Website')) return firstLine;
                        }
                    }
                }
                return null;
            }""")
            about_text = str(desc).strip() if desc is not None else ""
            if about_text:
                return about_text
        except Exception as exc:
            logger.debug("JS evaluation for about section failed: %s", exc)

        # 2. Legacy section fallback
        sections = await self.browser.query_selector_all("section")
        sections_data: list[tuple[str, list[str]]] = []
        for section in sections:
            section_text = await section.inner_text()
            if any(k in section_text[:50].lower() for k in ["about us", "overview", "about"]):
                paragraphs = await section.query_selector_all("p")
                p_texts = [await p.inner_text() for p in paragraphs]
                sections_data.append((section_text, p_texts))
        return parse_about_section(sections_data)

    async def _get_raw_overview(
        self,
    ) -> tuple[list[str], list[tuple[str, str]], list[tuple[str, str]]]:
        """
        Acquire raw overview data from DOM.

        Uses JS evaluation to extract SDUI label-value pairs from the modern /about/ page,
        with dt/dd and legacy `.org-top-card-summary-info-list__info-item` as fallbacks.

        Returns:
            Tuple of (info_item_texts, links_data, dt_dd_pairs)
        """
        # 1. Try SDUI label-value extraction via JS (modern LinkedIn /about/ page)
        dt_dd_pairs: list[tuple[str, str]] = []
        try:
            sdui_pairs = await self.browser.evaluate("""() => {
                const LABELS = [
                    'Website', 'Phone', 'Phone number',
                    'Headquarters', 'Location',
                    'Founded', 'Industry', 'Industries',
                    'Company size', 'Size', 'Company type', 'Type',
                    'Specialties'
                ];
                const pairs = [];
                const allElements = document.querySelectorAll('div, p, span, dt, dd, li');
                const seen = new Set();

                for (const el of allElements) {
                    const txt = (el.innerText || el.textContent || '').trim();
                    if (!txt) continue;

                    for (const label of LABELS) {
                        if (txt === label || txt.toLowerCase() === label.toLowerCase()) {
                            if (seen.has(label)) continue;
                            let value = '';
                            // 1. Try: next element sibling
                            let sib = el.nextElementSibling;
                            if (sib) {
                                const sibTxt = (sib.innerText || sib.textContent || '').trim();
                                if (sibTxt && sibTxt.toLowerCase() !== label.toLowerCase() && sibTxt.length < 2000) {
                                    value = sibTxt;
                                }
                            }
                            // 2. Try: parent's next element sibling
                            if (!value && el.parentElement) {
                                sib = el.parentElement.nextElementSibling;
                                if (sib) {
                                    const sibTxt = (sib.innerText || sib.textContent || '').trim();
                                    if (sibTxt && sibTxt.toLowerCase() !== label.toLowerCase() && sibTxt.length < 2000) {
                                        value = sibTxt;
                                    }
                                }
                            }
                            if (value) {
                                if (label === 'Company size' || label === 'Size') {
                                    value = value.split('\\n')[0].trim();
                                }
                                pairs.push([label, value]);
                                seen.add(label);
                            }
                            break;
                        }
                    }
                }
                return pairs;
            }""")
            if isinstance(sdui_pairs, list):
                for item in sdui_pairs:
                    if isinstance(item, list) and len(item) == 2:
                        dt_dd_pairs.append((str(item[0]), str(item[1])))
        except Exception as exc:
            logger.debug("SDUI JS evaluation for overview failed: %s", exc)

        # 2. Legacy dt/dd fallback if SDUI extraction yielded nothing
        if not dt_dd_pairs:
            dl_elements = await self.browser.query_selector_all(
                CompanySelectors.DEFINITION_LIST
            )
            if dl_elements:
                for dl in dl_elements:
                    dts = await dl.query_selector_all(CompanySelectors.DEFINITION_TERM)
                    dds = await dl.query_selector_all(CompanySelectors.DEFINITION_VALUE)
                    if len(dts) == len(dds):
                        for dt, dd in zip(dts, dds):
                            label = await dt.inner_text()
                            val = await dd.inner_text()
                            if label:
                                dt_dd_pairs.append((label, val))
            if not dt_dd_pairs:
                dt_elements = await self.browser.query_selector_all(
                    CompanySelectors.DEFINITION_TERM
                )
                dd_elements = await self.browser.query_selector_all(
                    CompanySelectors.DEFINITION_VALUE
                )
                if dt_elements and len(dt_elements) == len(dd_elements):
                    for dt, dd in zip(dt_elements, dd_elements):
                        label = await dt.inner_text()
                        val = await dd.inner_text()
                        if label:
                            dt_dd_pairs.append((label, val))

        # 3. Info items (legacy top-card list, present on older pages)
        info_items = await self.browser.query_selector_all(
            CompanySelectors.OVERVIEW_INFO_ITEM
        )
        info_texts = [await item.inner_text() for item in info_items]

        # 4. Links (for website detection)
        links = await self.browser.query_selector_all(CompanySelectors.ALL_ANCHORS)
        links_data: list[tuple[str, str]] = []
        for link in links:
            href = await link.get_attribute("href")
            if href and isinstance(href, str):
                text = await link.inner_text()
                links_data.append((href, text))

        return info_texts, links_data, dt_dd_pairs

    async def _get_overview(self) -> dict[str, str | None]:
        """
        Extract company overview details (website, industry, size, etc.).

        Returns dict with: website, phone, headquarters, founded, industry,
        company_type, company_size, specialties
        """
        info_texts, links_data, dt_dd_pairs = await self._get_raw_overview()
        return parse_company_overview(
            info_item_texts=info_texts,
            links=links_data,
            dt_dd_pairs=dt_dd_pairs,
        )
