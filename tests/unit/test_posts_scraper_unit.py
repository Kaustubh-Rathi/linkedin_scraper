"""Unit tests for CompanyPostsScraper orchestration (mocked evaluate)."""
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.models import Post
from linkedin_scraper.scrapers.company.posts import CompanyPostsScraper


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_posts_exits_when_activity_found(fake_page_cls):
    page = fake_page_cls(evaluate_results=[True])
    scraper = CompanyPostsScraper(page)
    monkeypatch_trigger = AsyncMock()
    scraper._trigger_lazy_load = monkeypatch_trigger
    await scraper._wait_for_posts_to_load()
    monkeypatch_trigger.assert_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_posts_via_js_maps_posts(fake_page_cls):
    page = fake_page_cls(
        evaluate_results=[
            [
                {
                    "urn": "urn:li:activity:1",
                    "text": "Hello world from the company feed post content here",
                    "timeText": "1d",
                    "reactions": "12",
                    "comments": "3 comments",
                    "reposts": "1",
                    "images": [],
                }
            ]
        ]
    )
    scraper = CompanyPostsScraper(page)
    posts = await scraper._extract_posts_via_js()
    assert len(posts) == 1
    assert posts[0].urn == "urn:li:activity:1"
    assert "Hello world" in (posts[0].text or "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_posts_respects_limit(monkeypatch, fake_page_cls):
    page = fake_page_cls()
    scraper = CompanyPostsScraper(page)
    monkeypatch.setattr(scraper, "navigate_and_wait", AsyncMock())
    monkeypatch.setattr(scraper, "_wait_for_posts_to_load", AsyncMock())
    monkeypatch.setattr(
        scraper,
        "_extract_posts_via_js",
        AsyncMock(
            return_value=[
                Post(urn="urn:li:activity:1", text="a" * 30),
                Post(urn="urn:li:activity:2", text="b" * 30),
                Post(urn="urn:li:activity:3", text="c" * 30),
            ]
        ),
    )
    monkeypatch.setattr(scraper, "_scroll_for_more_posts", AsyncMock())
    posts = await scraper.scrape("https://www.linkedin.com/company/acme/", limit=2)
    assert len(posts) == 2
