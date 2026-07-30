"""Unit tests for CompanyScraper DOM helpers (FakePage, no live LinkedIn)."""
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.scrapers.company.scraper import CompanyScraper


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_name_returns_h1(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(count=1, text="Example Corp")
    )
    scraper = CompanyScraper(page)
    assert await scraper._get_name() == "Example Corp"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_name_unknown_on_error(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        locator_factory=lambda selector: fake_locator_cls(
            raise_on_text=RuntimeError("missing")
        )
    )
    # inner_text raises via FakeLocator only when text_content raises; override
    loc = fake_locator_cls(count=1)

    async def boom():
        raise RuntimeError("boom")

    loc.inner_text = boom
    page = fake_page_cls(locator_factory=lambda s: loc)
    scraper = CompanyScraper(page)
    assert await scraper._get_name() == "Unknown Company"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_about_finds_about_us_section(fake_page_cls, fake_locator_cls):
    paragraph = fake_locator_cls(count=1, text="We build things.")
    section = fake_locator_cls(count=1, text="About us\nWe build things.")
    section._children = [paragraph]
    # locator('p').all() uses children; also need section.inner_text

    async def section_inner():
        return "About us\nWe build things."

    section.inner_text = section_inner

    def factory(selector):
        if selector == "section":
            return fake_locator_cls(count=1, children=[section])
        if selector == "p":
            return fake_locator_cls(count=1, children=[paragraph], text="We build things.")
        return fake_locator_cls()

    # CompanyScraper iterates sections via page.locator('section').all()
    page = fake_page_cls()

    async def sections_all():
        return [section]

    section_root = fake_locator_cls(count=1)
    section_root.all = sections_all
    section.locator = lambda sel: fake_locator_cls(
        count=1, children=[paragraph], text="We build things."
    )
    page.locator = lambda sel: section_root if sel == "section" else fake_locator_cls()

    scraper = CompanyScraper(page)
    about = await scraper._get_about()
    assert about == "We build things."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_overview_classifies_info_items(fake_page_cls, fake_locator_cls):
    items = [
        fake_locator_cls(count=1, text="Software Development"),
        fake_locator_cls(count=1, text="1,001-5,000 employees"),
        fake_locator_cls(count=1, text="San Francisco, California"),
    ]
    for item in items:

        async def make_inner(t=item._text):
            return t

        item.inner_text = make_inner

    info_root = fake_locator_cls(count=3, children=items)

    async def info_all():
        return items

    info_root.all = info_all

    link = fake_locator_cls(
        count=1, text="Visit website", attribute="https://example.com"
    )

    async def links_all():
        return [link]

    links_root = fake_locator_cls(count=1, children=[link])
    links_root.all = links_all

    def factory(selector):
        if "info-item" in selector:
            return info_root
        if selector == "a":
            return links_root
        if selector == "dt":
            return fake_locator_cls(count=0, children=[])
        return fake_locator_cls()

    page = fake_page_cls(locator_factory=factory)
    scraper = CompanyScraper(page)
    overview = await scraper._get_overview()
    assert overview["industry"] == "Software Development"
    assert overview["company_size"] == "1,001-5,000 employees"
    assert overview["headquarters"] == "San Francisco, California"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_wires_fields(monkeypatch, fake_page_cls):
    page = fake_page_cls()
    scraper = CompanyScraper(page)
    monkeypatch.setattr(scraper, "navigate_and_wait", AsyncMock())
    monkeypatch.setattr(scraper, "_get_name", AsyncMock(return_value="Acme"))
    monkeypatch.setattr(scraper, "_get_about", AsyncMock(return_value="About"))
    monkeypatch.setattr(
        scraper,
        "_get_overview",
        AsyncMock(
            return_value={
                "website": None,
                "phone": None,
                "headquarters": "SF",
                "founded": None,
                "industry": "Tech",
                "company_type": None,
                "company_size": "100",
                "specialties": None,
            }
        ),
    )
    company = await scraper.scrape("https://www.linkedin.com/company/acme/")
    assert company.name == "Acme"
    assert company.about_us == "About"
    assert company.industry == "Tech"
    assert company.headquarters == "SF"
