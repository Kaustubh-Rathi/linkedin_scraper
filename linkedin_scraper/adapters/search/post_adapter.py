"""
LinkedIn Post (Content) Search Adapter.

Verified live (2026-09): content search result cards expose **no permalink
anchor and no ``data-urn``**. Cards are located by their accessibility heading
text (``"Feed post"``) and parsed from their rendered text lines. Posts
therefore use ``requires_url=False`` — ``linkedin_url`` falls back to the
author's profile URL when LinkedIn provides no post permalink.
"""

from __future__ import annotations

from linkedin_scraper.adapters.search.base import BaseLinkedInSearchAdapter
from linkedin_scraper.parsers.search import (
    parse_post_search_card,
    parse_post_search_card_from_lines,
)
from linkedin_scraper.search.ports import PostSearchPort
from linkedin_scraper.search.queries import PostSearchQuery
from linkedin_scraper.search.results import PostSearchResult, SearchPage
from linkedin_scraper.selectors import SearchCards

CARD_SELECTOR = SearchCards.CONTENT_WAIT
URL_MARKERS = SearchCards.POST_URL_MARKERS
ENTITY_LABEL = 'post'

#: Locates post cards by their accessibility heading, then walks up to the
#: card container (the smallest ancestor holding substantial content).
POST_CARDS_JS = """() => {
                const isHeading = (t) => {
                    const s = (t || '').trim().toLowerCase();
                    return s === 'feed post' || /^feed post number \\d+$/.test(s);
                };

                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, span, div'))
                    .filter(el => isHeading(el.innerText || el.textContent || ''));

                const results = [];
                const seen = new Set();

                for (const h of headings) {
                    let card = h;
                    for (let i = 0; i < 8 && card.parentElement; i++) {
                        card = card.parentElement;
                        if ((card.innerText || '').length > 250) break;
                    }
                    const text = card.innerText || '';
                    if (text.length < 120) continue;

                    const author = card.querySelector('a[href*="/in/"]');
                    const permalinkEl = card.querySelector('a[href*="/feed/update/"], a[href*="/posts/"]');
                    const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                    if (lines.length < 3) continue;

                    const key = lines[1] + '::' + lines.slice(-1)[0];
                    if (seen.has(key)) continue;
                    seen.add(key);

                    results.push({
                        lines: lines.slice(0, 80),
                        author_href: author ? author.getAttribute('href') : null,
                        permalink: permalinkEl ? permalinkEl.getAttribute('href') : null,
                        card_key: key
                    });
                }
                return results;
            }"""


class LinkedInPostSearchAdapter(BaseLinkedInSearchAdapter[PostSearchResult], PostSearchPort):
    """Adapter implementing PostSearchPort for LinkedIn content search."""

    async def search_posts(
        self, query: PostSearchQuery
    ) -> SearchPage[PostSearchResult]:
        """Execute post search with a typed query."""
        return await self._run_search(
            url=self._url_builder.build_post_url(query),
            limit=query.limit,
            continuation_token=query.continuation_token,
            entity_label=ENTITY_LABEL,
            card_selector=CARD_SELECTOR,
            url_markers=URL_MARKERS,
            parser=parse_post_search_card_from_lines,
            element_parser=parse_post_search_card,
            js_body=POST_CARDS_JS,
            element_field_name='text_snippet',
            requires_url=False,
            dedupe_field='card_key',
        )
