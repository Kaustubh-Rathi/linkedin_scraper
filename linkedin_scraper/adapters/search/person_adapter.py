"""
LinkedIn Person Search Adapter.

Adapter implementing PersonSearchPort using BrowserPort, LinkedInSearchUrlBuilder, and
parse_person_search_card. The shared search pipeline (navigation guard, card waiting, scrolling,
card parsing, and pagination) lives in BaseLinkedInSearchAdapter.
"""

from __future__ import annotations

from linkedin_scraper.adapters.search.base import BaseLinkedInSearchAdapter
from linkedin_scraper.parsers.search import parse_person_search_card
from linkedin_scraper.search.ports import PersonSearchPort
from linkedin_scraper.search.queries import PersonSearchQuery
from linkedin_scraper.search.results import PersonSearchResult, SearchPage
from linkedin_scraper.selectors import SearchCards

CARD_SELECTOR = SearchCards.PERSON_CARD
URL_MARKERS = SearchCards.PERSON_URL_MARKERS
ENTITY_LABEL = 'person'

PERSON_CARDS_JS = """() => {
                const UI_ACTIONS = new Set([
                    'connect', 'follow', 'message', 'pending', 'view full profile',
                    'withdraw', 'following', '1st', '2nd', '3rd+', '• 1st', '• 2nd', '• 3rd+'
                ]);

                const results = [];
                const seenUrls = new Set();

                for (const a of document.querySelectorAll('a[href*="/in/"]')) {
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
                        if (UI_ACTIONS.has(lo)) return false;
                        if (/^(•\\s*)?(1st|2nd|3rd\\+?)$/.test(l.trim())) return false;
                        if (/followers?$/i.test(l)) return false;
                        return true;
                    });

                    if (!lines.length) continue;

                    const name = lines[0];
                    const headline = lines[1] || null;
                    const location = lines[2] || null;

                    let currentCompany = null;
                    if (headline && headline.includes(' at ')) {
                        currentCompany = headline.split(' at ').pop().trim();
                    }

                    seenUrls.add(cleanUrl);
                    results.push({
                        name: name,
                        linkedin_url: cleanUrl,
                        headline: headline,
                        location: location,
                        current_company: currentCompany
                    });
                }
                return results;
            }"""


class LinkedInPersonSearchAdapter(BaseLinkedInSearchAdapter[PersonSearchResult], PersonSearchPort):
    """Adapter implementing PersonSearchPort for LinkedIn person search."""

    async def search_people(
        self, query: PersonSearchQuery
    ) -> SearchPage[PersonSearchResult]:
        """Execute person search with a typed query."""
        return await self._run_search(
            url=self._url_builder.build_person_url(query),
            limit=query.limit,
            continuation_token=query.continuation_token,
            entity_label=ENTITY_LABEL,
            card_selector=CARD_SELECTOR,
            url_markers=URL_MARKERS,
            parser=parse_person_search_card,
            js_body=PERSON_CARDS_JS,
            element_field_name='name',
        )
