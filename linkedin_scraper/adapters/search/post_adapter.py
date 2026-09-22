"""
LinkedIn Post Search Adapter.

Adapter implementing PostSearchPort using BrowserPort, LinkedInSearchUrlBuilder, and
parse_post_search_card. The shared search pipeline (navigation guard, card waiting, scrolling,
card parsing, and pagination) lives in BaseLinkedInSearchAdapter.
"""

from __future__ import annotations

from linkedin_scraper.adapters.search.base import BaseLinkedInSearchAdapter
from linkedin_scraper.parsers.search import parse_post_search_card
from linkedin_scraper.search.ports import PostSearchPort
from linkedin_scraper.search.queries import PostSearchQuery
from linkedin_scraper.search.results import PostSearchResult, SearchPage

CARD_SELECTOR = 'a[href*="/feed/update/"], a[href*="/posts/"]'
URL_MARKERS = ("/feed/update/", "/posts/")
ENTITY_LABEL = 'post'


class LinkedInPostSearchAdapter(BaseLinkedInSearchAdapter[PostSearchResult], PostSearchPort):
    """Adapter implementing PostSearchPort for LinkedIn post search."""

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
            parser=parse_post_search_card,
            js_body=None,
            element_field_name='text_snippet',
        )
