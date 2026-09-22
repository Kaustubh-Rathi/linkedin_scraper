"""Shared scaffolding for LinkedIn entity search adapters.

Every entity search adapter (person, company, job, post, employee) executes the
same pipeline:

    navigate -> rate-limit / auth-wall guard -> wait for result cards ->
    scroll -> JS card extraction (element fallback) -> parse cards -> paginate

This module factors that pipeline into one reusable generic base class so each
concrete adapter only declares its URL builder, card selector, parser, and the
entity-specific JavaScript extractor. That keeps adapters open for extension
(new entity types) while closed for modification of the shared flow (OCP) and
keeps each adapter focused on a single responsibility (SRP).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Generic, Sequence, TypeVar

from linkedin_scraper.adapters.search.url_builder import LinkedInSearchUrlBuilder
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError
from linkedin_scraper.core.rate_limit import (
    RequestThrottler,
    detect_rate_limit,
    get_default_throttler,
)
from linkedin_scraper.ports.browser import BrowserPort
from linkedin_scraper.search.results import SearchPage

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT")

#: LinkedIn only exposes roughly the first 1000 paginated search results.
MAX_SEARCH_RESULTS = 1000

#: URL fragments that indicate the session is not authenticated.
AUTH_WALL_MARKERS = ("login", "authwall", "checkpoint")

#: Exceptions that indicate a broken browser/transport rather than "no results".
CONNECTION_FAILURE_TYPES = (ConnectionError, RuntimeError, OSError)

CardParser = Callable[[dict], Any]


def clean_linkedin_url(url: str) -> str:
    """
    Normalize a LinkedIn URL by dropping query/fragment tracking segments.

    Returns an empty string when nothing usable remains (for example when the
    href was only a query string or fragment).
    """
    if not url:
        return ""
    base = url.strip().split("?")[0].split("#")[0].strip()
    if not base:
        return ""
    return f"{base.rstrip('/')}/"


def compute_pagination(
    continuation_token: str | None, result_count: int, limit: int
) -> tuple[str | None, bool]:
    """
    Compute the next continuation token and ``has_more`` flag.

    ``has_more`` is True only when a full page was returned and LinkedIn's
    ~1000 result cap has not been reached yet.
    """
    start_offset = 0
    if continuation_token and continuation_token.isdigit():
        start_offset = int(continuation_token)

    next_offset = start_offset + result_count
    has_more = result_count >= limit and next_offset < MAX_SEARCH_RESULTS
    return (str(next_offset) if has_more else None, has_more)


class BaseLinkedInSearchAdapter(Generic[ResultT]):
    """
    Template-method base class shared by all LinkedIn search adapters.

    Subclasses supply entity specifics through :meth:`_run_search`; the shared
    navigation, guard, scrolling, parsing, and pagination behaviour lives here.
    """

    def __init__(
        self,
        browser: BrowserPort,
        url_builder: LinkedInSearchUrlBuilder | None = None,
        throttler: RequestThrottler | None = None,
    ) -> None:
        self._browser = browser
        self._url_builder = url_builder or LinkedInSearchUrlBuilder()
        #: Shared by default so all adapters issue one request at a time.
        self._throttler = throttler or get_default_throttler()

    async def _guard_navigation(self, url: str, entity_label: str) -> None:
        """Throttle, navigate to ``url``, and fail fast on auth walls or rate limits."""
        logger.info("Navigating to %s search URL: %s", entity_label, url)
        async with self._throttler:
            await self._browser.goto(url, wait_until="domcontentloaded")

        await detect_rate_limit(self._browser)
        current_url = self._browser.url
        if any(marker in current_url for marker in AUTH_WALL_MARKERS):
            raise AuthenticationError(
                "Authentication wall or login page encountered during "
                f"{entity_label} search: {current_url}"
            )

    async def _wait_for_cards(
        self, card_selector: str, entity_label: str
    ) -> SearchPage[ResultT] | None:
        """
        Wait for result cards to render.

        Returns an empty page when the page legitimately has no results, or
        ``None`` when cards were found and the caller should continue.
        """
        try:
            await self._browser.wait_for_selector(card_selector, timeout=10000)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as exc:
            if isinstance(exc, CONNECTION_FAILURE_TYPES):
                logger.error(
                    "Browser connection failure during %s search: %s", entity_label, exc
                )
                raise
            logger.debug(
                "No %s search results found on page within timeout: %s",
                entity_label,
                exc,
            )
            return SearchPage[ResultT](
                items=[],
                total_count=0,
                continuation_token=None,
                has_more=False,
            )
        return None

    async def _scroll_for_more_cards(self) -> None:
        """Trigger lazy loading of additional rendered cards."""
        try:
            await self._browser.wait_for_timeout(1000)
            await self._browser.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await self._browser.wait_for_timeout(1000)
        except Exception as exc:
            logger.debug(
                "Scroll evaluation failed or was partially interrupted: %s", exc
            )

    async def _evaluate_card_data(self, js_body: str) -> list[Any] | None:
        """Run the entity JavaScript extractor, returning ``None`` on failure."""
        try:
            raw_eval = await self._browser.evaluate(js_body)
        except Exception as exc:
            logger.debug("JS card extraction failed, using element fallback: %s", exc)
            return None
        return raw_eval if isinstance(raw_eval, list) else None


    def _parse_raw_cards(
        self,
        card_data_list: Sequence[Any],
        limit: int,
        parser: CardParser,
        entity_label: str,
        requires_url: bool = True,
        dedupe_field: str | None = None,
    ) -> list[ResultT]:
        """Parse structured JS card dictionaries into view models.

        Set ``requires_url=False`` for surfaces where LinkedIn exposes no
        permalink (content search posts); ``dedupe_field`` then names the raw
        dict key used to de-duplicate identical cards.
        """
        results: list[ResultT] = []
        seen_keys: set[str] = set()

        for raw_data in card_data_list:
            if len(results) >= limit:
                break
            if not isinstance(raw_data, dict):
                continue

            url = raw_data.get("linkedin_url", "")
            if url:
                dedupe_key = url
            elif not requires_url:
                dedupe_key = str(raw_data.get(dedupe_field or "card_key", ""))
                if not dedupe_key:
                    continue
            else:
                continue

            if dedupe_key in seen_keys:
                continue
            try:
                results.append(parser(raw_data))
                seen_keys.add(dedupe_key)
            except RateLimitError:
                raise
            except ValueError as val_err:
                logger.warning(
                    "Skipping %s search card with invalid/missing required field: %s",
                    entity_label,
                    val_err,
                )
                continue
            except Exception as exc:
                logger.debug("Failed to parse %s search card: %s", entity_label, exc)
                continue
        return results

    async def _parse_element_cards(
        self,
        limit: int,
        card_selector: str,
        url_markers: Sequence[str],
        parser: CardParser,
        entity_label: str,
        element_field_name: str = "name",
        extra_fields: dict | None = None,
    ) -> list[ResultT]:
        """Element-by-element fallback used by fakes, posts, and legacy pages."""
        results: list[ResultT] = []
        seen_urls: set[str] = set()

        elements = await self._browser.query_selector_all(card_selector)
        for element in elements:
            if len(results) >= limit:
                break
            try:
                href = await element.get_attribute("href")
                if not href or not any(marker in href for marker in url_markers):
                    continue
                cleaned_url = clean_linkedin_url(href)
                if not cleaned_url or cleaned_url in seen_urls:
                    continue
                text_content = await element.text_content()
                raw_data = {
                    element_field_name: (text_content or "").strip(),
                    "linkedin_url": cleaned_url,
                    **(extra_fields or {}),
                }
                results.append(parser(raw_data))
                seen_urls.add(cleaned_url)
            except RateLimitError:
                raise
            except ValueError as val_err:
                logger.warning(
                    "Skipping %s search card with invalid/missing required field: %s",
                    entity_label,
                    val_err,
                )
                continue
            except Exception as exc:
                logger.debug(
                    "Failed to parse %s search card element: %s", entity_label, exc
                )
                continue
        return results

    def _build_page(
        self, results: list[ResultT], continuation_token: str | None, limit: int
    ) -> SearchPage[ResultT]:
        """Assemble the paginated response from parsed results."""
        next_token, has_more = compute_pagination(
            continuation_token, len(results), limit
        )
        return SearchPage[ResultT](
            items=results,
            total_count=None,
            continuation_token=next_token,
            has_more=has_more,
        )


    async def _run_search(
        self,
        *,
        url: str,
        limit: int,
        continuation_token: str | None,
        entity_label: str,
        card_selector: str,
        url_markers: Sequence[str],
        parser: CardParser,
        js_body: str | None = None,
        element_parser: CardParser | None = None,
        element_field_name: str = "name",
        element_extra_fields: dict | None = None,
        requires_url: bool = True,
        dedupe_field: str | None = None,
    ) -> SearchPage[ResultT]:
        """
        Execute the full shared search pipeline for one entity type.

        ``parser`` is used for the JavaScript card path; ``element_parser``
        (defaults to ``parser``) is used for the element-by-element fallback
        path. Particles that expose no permalink (content-search posts) declare
        ``requires_url=False`` and supply a ``dedupe_field``.
        """
        await self._guard_navigation(url, entity_label)

        empty_page = await self._wait_for_cards(card_selector, entity_label)
        if empty_page is not None:
            return empty_page

        await self._scroll_for_more_cards()

        card_data_list = (
            await self._evaluate_card_data(js_body) if js_body is not None else None
        )

        element_parser = element_parser or parser
        if card_data_list is not None:
            results = self._parse_raw_cards(
                card_data_list,
                limit,
                parser,
                entity_label,
                requires_url=requires_url,
                dedupe_field=dedupe_field,
            )
        else:
            results = await self._parse_element_cards(
                limit,
                card_selector,
                url_markers,
                element_parser,
                entity_label,
                element_field_name=element_field_name,
                extra_fields=element_extra_fields,
            )

        return self._build_page(results, continuation_token, limit)

