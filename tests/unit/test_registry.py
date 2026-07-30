"""Tests for linkedin_scraper.core.registry.ScraperRegistry."""
import pytest

from linkedin_scraper.core.registry import ScraperRegistry, default_registry
from linkedin_scraper.scrapers import (
    PersonScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
    CompanyPostsScraper,
)


class DummyService:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


@pytest.mark.unit
def test_register_and_create_returns_instance():
    registry = ScraperRegistry()
    registry.register("dummy", DummyService)

    instance = registry.create("dummy", 1, key="value")

    assert isinstance(instance, DummyService)
    assert instance.args == (1,)
    assert instance.kwargs == {"key": "value"}


@pytest.mark.unit
def test_available_lists_registered_names():
    registry = ScraperRegistry()
    assert registry.available() == []

    registry.register("dummy", DummyService)
    registry.register("other", DummyService)

    assert set(registry.available()) == {"dummy", "other"}


@pytest.mark.unit
def test_create_unknown_service_raises_key_error():
    registry = ScraperRegistry()

    with pytest.raises(KeyError):
        registry.create("does-not-exist")


@pytest.mark.unit
def test_create_unknown_service_error_lists_registered():
    registry = ScraperRegistry()
    registry.register("known", DummyService)

    with pytest.raises(KeyError, match="known"):
        registry.create("unknown")


@pytest.mark.unit
def test_default_registry_has_all_builtin_services():
    names = default_registry.available()
    for expected in ("person", "company", "job", "job_search", "company_posts"):
        assert expected in names


@pytest.mark.unit
def test_default_registry_create_person_returns_person_scraper():
    scraper = default_registry.create("person", "fake-page")
    assert isinstance(scraper, PersonScraper)


@pytest.mark.unit
def test_default_registry_create_company_returns_company_scraper():
    scraper = default_registry.create("company", "fake-page")
    assert isinstance(scraper, CompanyScraper)


@pytest.mark.unit
def test_default_registry_create_job_returns_job_scraper():
    scraper = default_registry.create("job", "fake-page")
    assert isinstance(scraper, JobScraper)


@pytest.mark.unit
def test_default_registry_create_job_search_returns_job_search_scraper():
    scraper = default_registry.create("job_search", "fake-page")
    assert isinstance(scraper, JobSearchScraper)


@pytest.mark.unit
def test_default_registry_create_company_posts_returns_company_posts_scraper():
    scraper = default_registry.create("company_posts", "fake-page")
    assert isinstance(scraper, CompanyPostsScraper)
