"""Structural typing contracts for scraper services.

These protocols define in-process plugin boundaries that scraper
services must satisfy, independent of any concrete base class. Any object
matching the shape below is a valid service, whether or not it inherits
from :class:`~linkedin_scraper.scrapers.base.BaseScraper`.
"""

from __future__ import annotations

from typing import Any, List, Protocol, runtime_checkable
from playwright.async_api import Page


@runtime_checkable
class ScraperService(Protocol):
    """Contract for a scrape service (protocol / plugin boundary)."""

    page: Page

    async def scrape(self, linkedin_url: str, **kwargs: Any) -> Any: ...


@runtime_checkable
class SearchService(Protocol):
    """Contract for search-style services that return URL lists."""

    page: Page

    async def search(self, **kwargs: Any) -> List[Any]: ...
