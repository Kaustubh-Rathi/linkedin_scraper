"""Tests for the structural typing contracts in linkedin_scraper.protocols."""
from unittest.mock import MagicMock

import pytest

from linkedin_scraper.protocols import ScraperService, SearchService
from linkedin_scraper.scrapers import CompanyScraper, JobSearchScraper, PersonScraper


@pytest.mark.unit
def test_person_scraper_is_scraper_service():
    scraper = PersonScraper(MagicMock())
    assert isinstance(scraper, ScraperService)


@pytest.mark.unit
def test_company_scraper_is_scraper_service():
    scraper = CompanyScraper(MagicMock())
    assert isinstance(scraper, ScraperService)


@pytest.mark.unit
def test_job_search_scraper_is_search_service():
    scraper = JobSearchScraper(MagicMock())
    assert isinstance(scraper, SearchService)


@pytest.mark.unit
def test_job_search_scraper_is_not_scraper_service():
    """JobSearchScraper exposes `search`, not `scrape`."""
    scraper = JobSearchScraper(MagicMock())
    assert not isinstance(scraper, ScraperService)


@pytest.mark.unit
def test_person_scraper_is_not_search_service():
    """PersonScraper exposes `scrape`, not `search`."""
    scraper = PersonScraper(MagicMock())
    assert not isinstance(scraper, SearchService)


@pytest.mark.unit
def test_scraper_service_is_runtime_checkable():
    assert getattr(ScraperService, "_is_runtime_protocol", False) is True


@pytest.mark.unit
def test_search_service_is_runtime_checkable():
    assert getattr(SearchService, "_is_runtime_protocol", False) is True
