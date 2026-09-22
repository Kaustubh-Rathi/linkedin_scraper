"""
LinkedIn Job Search Adapter.

Adapter implementing JobSearchPort using BrowserPort, LinkedInSearchUrlBuilder, and
parse_job_search_card. The shared search pipeline (navigation guard, card waiting, scrolling,
card parsing, and pagination) lives in BaseLinkedInSearchAdapter.
"""

from __future__ import annotations

from linkedin_scraper.adapters.search.base import BaseLinkedInSearchAdapter
from linkedin_scraper.parsers.search import parse_job_search_card
from linkedin_scraper.search.ports import JobSearchPort
from linkedin_scraper.search.queries import JobSearchQuery
from linkedin_scraper.search.results import JobSearchResult, SearchPage
from linkedin_scraper.selectors import SearchCards

CARD_SELECTOR = SearchCards.JOB_CARD
URL_MARKERS = SearchCards.JOB_URL_MARKERS
ENTITY_LABEL = 'job'

JOB_CARDS_JS = """() => {
                const results = [];
                const seenUrls = new Set();

                for (const a of document.querySelectorAll('a[href*="/jobs/view/"]')) {
                    const href = a.getAttribute('href') || '';
                    if (!href) continue;
                    const cleanUrl = href.split('?')[0].split('#')[0].replace(/\\/$/, '') + '/';

                    if (seenUrls.has(cleanUrl)) continue;

                    let card = a.closest('li') || a.closest('[class*="job-card"]') || a.closest('[class*="entity-result"]') || (a.parentElement && a.parentElement.parentElement);
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

                    const title = (a.innerText || a.textContent || (rawLines.length ? rawLines[0] : '')).trim().split('\\n')[0].trim();
                    if (!title) continue;

                    let company = null;
                    let location = null;
                    let postedDate = null;
                    let easyApply = false;

                    const remaining = rawLines.filter(l => l !== title && !l.toLowerCase().includes('view job'));
                    if (remaining.length > 0) company = remaining[0];
                    if (remaining.length > 1) location = remaining[1];

                    for (const l of remaining) {
                        if (l.toLowerCase().includes('easy apply')) easyApply = true;
                        if (/(\\d+[hdwmy]|\\d+\\s*(hour|day|week|month|year)s?\\s*ago)/i.test(l)) {
                            postedDate = l;
                        }
                    }

                    seenUrls.add(cleanUrl);
                    results.push({
                        job_title: title,
                        linkedin_url: cleanUrl,
                        company_name: company,
                        location: location,
                        posted_date: postedDate,
                        easy_apply: easyApply
                    });
                }
                return results;
            }"""


class LinkedInJobSearchAdapter(BaseLinkedInSearchAdapter[JobSearchResult], JobSearchPort):
    """Adapter implementing JobSearchPort for LinkedIn job search."""

    async def search_jobs(
        self, query: JobSearchQuery
    ) -> SearchPage[JobSearchResult]:
        """Execute job search with a typed query."""
        return await self._run_search(
            url=self._url_builder.build_job_url(query),
            limit=query.limit,
            continuation_token=query.continuation_token,
            entity_label=ENTITY_LABEL,
            card_selector=CARD_SELECTOR,
            url_markers=URL_MARKERS,
            parser=parse_job_search_card,
            js_body=JOB_CARDS_JS,
            element_field_name='job_title',
        )
