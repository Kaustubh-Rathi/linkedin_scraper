"""Unit tests for accomplishments empty-state branches."""
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.scrapers.base import BaseScraper
from linkedin_scraper.scrapers.person.accomplishments import AccomplishmentsExtractor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_accomplishments_skips_nothing_to_see(fake_page_cls, fake_locator_cls):
    nothing = fake_locator_cls(count=1)

    def factory(selector):
        if "Nothing to see" in selector:
            return nothing
        return fake_locator_cls(count=0)

    page = fake_page_cls(locator_factory=factory)
    host = BaseScraper(page)
    host.navigate_and_wait = AsyncMock()
    host.wait_and_focus = AsyncMock()
    extractor = AccomplishmentsExtractor(host)
    result = await extractor.get_accomplishments("https://www.linkedin.com/in/example/")
    assert result == []


@pytest.mark.unit
def test_registry_has_and_is_registered():
    from linkedin_scraper.core.registry import ScraperRegistry

    reg = ScraperRegistry()
    assert reg.is_registered("person") is False
    assert reg.has("x") is False
    reg.register("x", lambda: None)
    assert reg.is_registered("x") is True
    assert reg.has("x") is True
