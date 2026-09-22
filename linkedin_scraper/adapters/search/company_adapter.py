"""
LinkedIn Company Search Adapter.

Adapter implementing CompanySearchPort using BrowserPort, LinkedInSearchUrlBuilder, and
parse_company_search_card. The shared search pipeline (navigation guard, card waiting, scrolling,
card parsing, and pagination) lives in BaseLinkedInSearchAdapter.
"""

from __future__ import annotations

from linkedin_scraper.adapters.search.base import BaseLinkedInSearchAdapter
from linkedin_scraper.parsers.search import parse_company_search_card
from linkedin_scraper.search.ports import CompanySearchPort
from linkedin_scraper.search.queries import CompanySearchQuery
from linkedin_scraper.search.results import CompanySearchResult, SearchPage
from linkedin_scraper.selectors import SearchCards

CARD_SELECTOR = SearchCards.COMPANY_CARD
URL_MARKERS = SearchCards.COMPANY_URL_MARKERS
ENTITY_LABEL = 'company'

COMPANY_CARDS_JS = """() => {
                const results = [];
                const seenUrls = new Set();

                for (const a of document.querySelectorAll('a[href*="/company/"]')) {
                    const href = a.getAttribute('href') || '';
                    if (!href) continue;
                    const cleanUrl = href.split('?')[0].split('#')[0].replace(/\\/$/, '') + '/';

                    if (seenUrls.has(cleanUrl)) continue;

                    let card = a.closest('li') || a.closest('[class*="entity-result"]') || (a.parentElement && a.parentElement.parentElement);
                    if (!card) continue;

                    const rawLines = [];
                    const seen = new Set();

                    const collectText = (el) => {
                        if (!el) return;
                        for (const child of el.childNodes) {
                            if (child.nodeType === 3) {
                                const t = child.textContent.trim();
                                if (t && t.length > 1 && !seen.has(t)) {
                                    seen.add(t);
                                    rawLines.push(t);
                                }
                            } else if (child.nodeType === 1) {
                                collectText(child);
                            }
                        }
                    };
                    collectText(card);

                    const lines = rawLines.filter(l => {
                        const lo = l.toLowerCase();
                        if (lo === 'follow' || lo === 'following') return false;
                        return true;
                    });

                    if (!lines.length) continue;

                    const name = lines[0];
                    let industry = null;
                    let location = null;
                    let followers = null;

                    for (let i = 1; i < lines.length; i++) {
                        const line = lines[i];
                        if (/followers?$/i.test(line)) {
                            followers = line;
                        } else if (!industry) {
                            industry = line;
                        } else if (!location) {
                            location = line;
                        }
                    }

                    seenUrls.add(cleanUrl);
                    results.push({
                        name: name,
                        linkedin_url: cleanUrl,
                        industry: industry,
                        location: location,
                        followers_count: followers
                    });
                }
                return results;
            }"""


class LinkedInCompanySearchAdapter(BaseLinkedInSearchAdapter[CompanySearchResult], CompanySearchPort):
    """Adapter implementing CompanySearchPort for LinkedIn company search."""

    async def search_companies(
        self, query: CompanySearchQuery
    ) -> SearchPage[CompanySearchResult]:
        """Execute company search with a typed query."""
        return await self._run_search(
            url=self._url_builder.build_company_url(query),
            limit=query.limit,
            continuation_token=query.continuation_token,
            entity_label=ENTITY_LABEL,
            card_selector=CARD_SELECTOR,
            url_markers=URL_MARKERS,
            parser=parse_company_search_card,
            js_body=COMPANY_CARDS_JS,
            element_field_name='name',
        )
