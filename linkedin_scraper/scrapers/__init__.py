"""Scraper modules for LinkedIn."""

from typing import Optional

from .base import BaseScraper
from .person import PersonScraper
from .company import CompanyScraper, CompanyPostsScraper
from .job import JobScraper, JobSearchScraper

from ..core.registry import ScraperRegistry, default_registry


def register_defaults(registry: Optional[ScraperRegistry] = None) -> None:
    """Register built-in scrapers on ``registry`` (defaults to ``default_registry``)."""
    reg = default_registry if registry is None else registry
    if reg.is_registered("person"):
        return
    reg.register("person", PersonScraper)
    reg.register("company", CompanyScraper)
    reg.register("job", JobScraper)
    reg.register("job_search", JobSearchScraper)
    reg.register("company_posts", CompanyPostsScraper)


default_registry.set_bootstrap(register_defaults)

__all__ = [
    "BaseScraper",
    "PersonScraper",
    "CompanyScraper",
    "JobScraper",
    "JobSearchScraper",
    "CompanyPostsScraper",
    "register_defaults",
]
