"""LinkedIn search URL builder and search adapters."""

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
) -> LinkedInSearchFacade:
    """
    Compose a LinkedInSearchFacade wired with the standard LinkedIn search adapters.

    Lives in the adapters (infrastructure) layer so that the search application
    layer depends only on SearchPort abstractions (dependency inversion).
    """
    builder = url_builder or LinkedInSearchUrlBuilder()
    return LinkedInSearchFacade(
        person_port=LinkedInPersonSearchAdapter(browser, url_builder=builder),
        company_port=LinkedInCompanySearchAdapter(browser, url_builder=builder),
        job_port=LinkedInJobSearchAdapter(browser, url_builder=builder),
        post_port=LinkedInPostSearchAdapter(browser, url_builder=builder),
        employee_port=LinkedInEmployeeSearchAdapter(browser, url_builder=builder),
    )

register_browser_composer(create_default_facade)



