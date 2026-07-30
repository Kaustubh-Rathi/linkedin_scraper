"""Unit tests for JobScraper / JobSearchScraper (mocked, no live LinkedIn)."""
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.scrapers.job.scraper import JobScraper
from linkedin_scraper.scrapers.job.search import JobSearchScraper


@pytest.mark.unit
def test_build_search_url_with_params():
    scraper = JobSearchScraper(page=object())
    url = scraper._build_search_url(keywords="engineer", location="Remote")
    assert "keywords=engineer" in url
    assert "location=Remote" in url
    assert url.startswith("https://www.linkedin.com/jobs/search/")


@pytest.mark.unit
def test_build_search_url_empty():
    scraper = JobSearchScraper(page=object())
    assert scraper._build_search_url() == "https://www.linkedin.com/jobs/search/"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_job_urls_dedupes(fake_page_cls, fake_locator_cls):
    links = [
        fake_locator_cls(
            count=1, attribute="https://www.linkedin.com/jobs/view/111/?refId=a"
        ),
        fake_locator_cls(
            count=1, attribute="https://www.linkedin.com/jobs/view/111/?refId=b"
        ),
        fake_locator_cls(
            count=1, attribute="https://www.linkedin.com/jobs/view/222/"
        ),
    ]
    root = fake_locator_cls(count=3, children=links)

    async def all_links():
        return links

    root.all = all_links
    page = fake_page_cls(locator_factory=lambda s: root)
    scraper = JobSearchScraper(page)
    urls = await scraper._extract_job_urls(limit=10)
    assert len(urls) == 2
    assert all("/jobs/view/" in u for u in urls)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_read_top_card_parses_parts(fake_page_cls, fake_locator_cls):
    container = fake_locator_cls(
        count=1, text="San Francisco, CA · 2 days ago · 100 applicants"
    )

    async def inner():
        return "San Francisco, CA · 2 days ago · 100 applicants"

    container.inner_text = inner
    page = fake_page_cls(locator_factory=lambda s: container)
    scraper = JobScraper(page)
    location, posted, applicants = await scraper._read_top_card()
    assert location == "San Francisco, CA"
    assert posted == "2 days ago"
    assert applicants == "100 applicants"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_scrape_orchestration(monkeypatch, fake_page_cls):
    page = fake_page_cls()
    scraper = JobScraper(page)
    monkeypatch.setattr(scraper, "navigate_and_wait", AsyncMock())
    monkeypatch.setattr(scraper, "_get_job_title", AsyncMock(return_value="SE"))
    monkeypatch.setattr(scraper, "_get_company", AsyncMock(return_value="Acme"))
    monkeypatch.setattr(
        scraper, "_read_top_card", AsyncMock(return_value=("SF", "1 day ago", "10"))
    )
    monkeypatch.setattr(scraper, "_get_description", AsyncMock(return_value="Desc"))
    monkeypatch.setattr(
        scraper, "_get_company_url", AsyncMock(return_value="https://linkedin.com/company/acme")
    )
    job = await scraper.scrape("https://www.linkedin.com/jobs/view/123/")
    assert job.job_title == "SE"
    assert job.company == "Acme"
    assert job.location == "SF"
    assert job.posted_date == "1 day ago"
    assert job.applicant_count == "10"
