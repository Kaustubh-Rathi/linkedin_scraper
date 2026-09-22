"""
Company posts scraper for LinkedIn feeds.

Acquires raw post data from LinkedIn company feed pages via BrowserPort,
and delegates semantic interpretation and model construction to pure parsers.
"""
from __future__ import annotations

import logging
from typing import Any

from ...callbacks import ProgressCallback
from ...core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from ...models.post import Post
from ...parsers.posts import build_posts_url, parse_company_posts
from ...ports.browser import BrowserPort
from ..base import BaseScraper

logger = logging.getLogger(__name__)


class CompanyPostsScraper(BaseScraper):
    """
    Scraper for LinkedIn company feed posts.

    Uses BrowserPort for page navigation, lazy loading, and feed extraction,
    and pure post parsers for model construction.
    """

    def __init__(
        self,
        page_or_browser: BrowserPort | Any = None,
        callback: ProgressCallback | None = None,
        *,
        page: BrowserPort | Any = None,
    throttler: Any | None = None,
    ):
        super().__init__(page_or_browser, callback, page=page, throttler=throttler)

    async def scrape(self, company_url: str, limit: int = 10) -> list[Post]:
        logger.info(f"Starting company posts scraping: {company_url}")
        await self.callback.on_start("company_posts", company_url)

        try:
            posts_url = build_posts_url(company_url)
            await self.navigate_and_wait(posts_url)
            await self.callback.on_progress("Navigated to posts page", 10)

            await self._wait_for_posts_to_load()
            await self.callback.on_progress("Posts loaded", 20)

            posts = await self._scrape_posts(limit)
            await self.callback.on_progress(f"Scraped {len(posts)} posts", 100)
            await self.callback.on_complete("company_posts", posts)

            logger.info(f"Successfully scraped {len(posts)} posts")
            return posts
        except (AuthenticationError, RateLimitError) as auth_or_rate_err:
            logger.error("Authentication or rate limit error while scraping posts for %s: %s", company_url, auth_or_rate_err)
            await self.callback.on_error(auth_or_rate_err)
            raise
        except Exception as e:
            logger.exception("Unexpected error while scraping posts for %s: %s", company_url, e)
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to scrape company posts: {e}") from e

    async def _wait_for_posts_to_load(self, timeout: int = 30000) -> None:
        try:
            await self.browser.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception as e:
            logger.debug(f"DOM load timeout: {e}")

        await self.browser.wait_for_timeout(3000)

        for attempt in range(3):
            await self._trigger_lazy_load()

            has_posts = await self.browser.evaluate(
                """() => {
                const hasH2 = Array.from(document.querySelectorAll('h2, h3'))
                    .some(h => (h.innerText || '').trim() === 'Feed post');
                return hasH2 || document.body.innerHTML.includes('urn:li:activity:');
            }"""
            )

            if has_posts:
                logger.debug(f"Posts found after attempt {attempt + 1}")
                return

            await self.browser.wait_for_timeout(2000)

        logger.warning("Posts may not have loaded fully")

    async def _trigger_lazy_load(self) -> None:
        await self.browser.evaluate(
            """() => {
            const scrollHeight = document.documentElement.scrollHeight;
            const steps = 8;
            const stepSize = Math.min(scrollHeight / steps, 400);

            for (let i = 1; i <= steps; i++) {
                setTimeout(() => window.scrollTo(0, stepSize * i), i * 200);
            }
        }"""
        )
        await self.browser.wait_for_timeout(2500)

        await self.browser.evaluate("window.scrollTo(0, 400)")
        await self.browser.wait_for_timeout(1000)

    async def _scrape_posts(self, limit: int) -> list[Post]:
        posts: list[Post] = []
        scroll_count = 0
        max_scrolls = (limit // 3) + 2

        while len(posts) < limit and scroll_count < max_scrolls:
            new_posts = await self._extract_posts_via_js()

            for post in new_posts:
                if post.urn and not any(p.urn == post.urn for p in posts):
                    posts.append(post)
                    if len(posts) >= limit:
                        break

            if len(posts) < limit:
                await self._scroll_for_more_posts()
                scroll_count += 1

        return posts[:limit]

    async def _extract_raw_posts_data(self) -> list[dict[str, Any]]:
        """Acquire raw post dictionaries from browser DOM evaluation."""
        data = await self.browser.evaluate(
            r"""() => {
            const posts = [];
            const seen = new Set();

            // Modern LinkedIn company posts page: each post has an H2 with text "Feed post"
            // The grandparent container (3 levels up from H2) is the card.
            const feedHeadings = Array.from(document.querySelectorAll('h2, h3'))
                .filter(h => (h.innerText || '').trim() === 'Feed post');

            for (let idx = 0; idx < feedHeadings.length; idx++) {
                const h2 = feedHeadings[idx];
                // Walk up to card container: h2 -> p1 -> p2 -> CARD
                const p1 = h2.parentElement;
                const p2 = p1 ? p1.parentElement : null;
                const card = p2 ? p2.parentElement : null;
                if (!card) continue;

                // Extract update URN if present, otherwise generate a stable pseudo-URN
                let urn = null;
                for (const a of card.querySelectorAll('a')) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/urn:li:activity:\d+/);
                    if (m) { urn = m[0]; break; }
                }
                if (!urn) {
                    urn = `urn:li:activity:feed_post_${idx}`;
                }
                if (seen.has(urn)) continue;
                seen.add(urn);

                // Posted date: short relative time like "13h", "4d", "2d"
                let postedDate = '';
                for (const el of card.querySelectorAll('span, p, time')) {
                    const t = (el.innerText || el.textContent || '').trim().replace(/[•\s]+$/, '').trim();
                    const m = t.match(/^(\d+[hdwmy]|\d+\s*(hour|day|week|month|year)s?\s*ago)/i);
                    if (m) {
                        postedDate = m[1];
                        break;
                    }
                }

                // Post text: collect non-trivial unique leaf text nodes
                const SKIP = new Set([
                    'feed post', 'microsoft', 'follow', 'following', 'more', '…', '·',
                    'see translation', 'load more', 'show translation'
                ]);
                const textParts = [];
                const seenText = new Set();

                const isLikelyNoise = (t) => {
                    if (!t || t.length < 3) return true;
                    const lo = t.toLowerCase().trim();
                    if (SKIP.has(lo)) return true;
                    if (/^\d+$/.test(t)) return true;
                    if (/^(\d+[hdwmy]|\d+\s*(hour|day|week|month|year)s?\s*ago)$/i.test(t)) return true;
                    if (/^#/.test(t) && t.length < 30) return false;  // hashtags are ok
                    return false;
                };

                const collectLeafText = (el) => {
                    if (!el) return;
                    for (const child of el.childNodes) {
                        if (child.nodeType === 3) {
                            const t = child.textContent.trim();
                            if (t && !seenText.has(t) && !isLikelyNoise(t)) {
                                seenText.add(t);
                                textParts.push(t);
                            }
                        } else if (child.nodeType === 1) {
                            collectLeafText(child);
                        }
                    }
                };
                collectLeafText(card);

                const text = textParts.join(' ').trim();

                // Reaction/comment/repost counts using aria-labels and button text
                let reactions = 0;
                let comments = 0;
                let reposts = 0;

                for (const btn of card.querySelectorAll('button, a, span')) {
                    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const txt = (btn.innerText || '').trim();

                    if (aria.includes('reaction') || txt.toLowerCase().includes('reaction')) {
                        const m = txt.match(/(\d[\d,]*)/);
                        if (m && !reactions) reactions = parseInt(m[1].replace(/,/g, ''), 10);
                    }
                    if (aria.includes('comment') || txt.toLowerCase().includes('comment')) {
                        const m = txt.match(/(\d[\d,]*)/);
                        if (m && !comments) comments = parseInt(m[1].replace(/,/g, ''), 10);
                    }
                    if (aria.includes('repost') || txt.toLowerCase().includes('repost')) {
                        const m = txt.match(/(\d[\d,]*)/);
                        if (m && !reposts) reposts = parseInt(m[1].replace(/,/g, ''), 10);
                    }
                }

                // Images
                const images = [];
                for (const img of card.querySelectorAll('img')) {
                    const src = img.src || '';
                    const alt = img.alt || '';
                    if (src && src.includes('media.licdn.com') &&
                        !src.includes('company-logo') && !src.includes('credibility') &&
                        !alt.toLowerCase().includes('cover') && !alt.toLowerCase().includes('logo')) {
                        images.push(src);
                    }
                }

                posts.push({
                    urn: urn,
                    text: text,
                    timeText: postedDate,
                    reactions: String(reactions),
                    comments: String(comments),
                    reposts: String(reposts),
                    images: images
                });
            }

            // Fallback: legacy data-urn based extraction if Feed post headings found nothing
            if (posts.length === 0) {
                const html = document.body.innerHTML;
                const urnMatches = html.matchAll(/urn:li:activity:(\\d+)/g);
                const seenUrns = new Set();

                for (const match of urnMatches) {
                    const urnVal = match[0];
                    if (seenUrns.has(urnVal)) continue;
                    seenUrns.add(urnVal);

                    const el = document.querySelector(`[data-urn="${urnVal}"]`);
                    if (!el) continue;

                    const textEl = el.querySelector('.feed-shared-update-v2__description, .update-components-text, .feed-shared-text');
                    const text = textEl ? (textEl.innerText || '').trim() : '';
                    if (!text || text.length < 20) continue;

                    const timeEl = el.querySelector('[class*="actor__sub-description"]');
                    const timeText = timeEl ? timeEl.innerText : '';

                    posts.push({
                        urn: urnVal,
                        text: text.substring(0, 2000),
                        timeText: timeText,
                        reactions: '',
                        comments: '',
                        reposts: '',
                        images: []
                    });
                }
            }

            return posts;
        }"""
        )
        return data if isinstance(data, list) else []

    async def _extract_posts_via_js(self) -> list[Post]:
        """Backward-compatible extraction method returning parsed Post models."""
        raw_data = await self._extract_raw_posts_data()
        return parse_company_posts(raw_data)

    async def _scroll_for_more_posts(self) -> None:
        try:
            await self.browser.keyboard_press("End")
            await self.browser.wait_for_timeout(1500)
        except Exception as e:
            logger.debug(f"Error scrolling: {e}")
