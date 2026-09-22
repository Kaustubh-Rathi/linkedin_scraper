"""LinkedIn search URL builder and search adapters."""

from linkedin_scraper.core.rate_limit import RequestThrottler, get_default_throttler
from linkedin_scraper.ports.browser import BrowserPort
from linkedin_scraper.search.services import LinkedInSearchFacade, register_browser_composer

from .company_adapter import LinkedInCompanySearchAdapter
from .employee_adapter import LinkedInEmployeeSearchAdapter
from .job_adapter import LinkedInJobSearchAdapter
from .person_adapter import LinkedInPersonSearchAdapter
from .post_adapter import LinkedInPostSearchAdapter
from .url_builder import LinkedInSearchUrlBuilder

__all__ = [
    "LinkedInSearchUrlBuilder",
    "LinkedInJobSearchAdapter",
    "LinkedInPersonSearchAdapter",
    "LinkedInCompanySearchAdapter",
    "LinkedInPostSearchAdapter",
    "LinkedInEmployeeSearchAdapter",
    "create_default_facade",
]


def create_default_facade(
    browser: BrowserPort,
    url_builder: LinkedInSearchUrlBuilder | None = None,
    throttler: RequestThrottler | None = None,
) -> LinkedInSearchFacade:
    """
    Compose a LinkedInSearchFacade wired with the standard LinkedIn search adapters.

    Lives in the adapters (infrastructure) layer so that the search application
    layer depends only on SearchPort abstractions (dependency inversion).
    All adapters share ONE throttler instance so searches issue one request
    at a time across entity types.
    """
    shared_throttler = throttler or get_default_throttler()
    builder = url_builder or LinkedInSearchUrlBuilder()
    return LinkedInSearchFacade(
        person_port=LinkedInPersonSearchAdapter(browser, url_builder=builder, throttler=shared_throttler),
        company_port=LinkedInCompanySearchAdapter(browser, url_builder=builder, throttler=shared_throttler),
        job_port=LinkedInJobSearchAdapter(browser, url_builder=builder, throttler=shared_throttler),
        post_port=LinkedInPostSearchAdapter(browser, url_builder=builder, throttler=shared_throttler),
        employee_port=LinkedInEmployeeSearchAdapter(browser, url_builder=builder, throttler=shared_throttler),
    )

register_browser_composer(create_default_facade)



