"""Live LinkedIn and browser-boundary integration tests for search adapters.

Tests the five LinkedIn search adapters against real Playwright browser infrastructure:
1. LinkedInPersonSearchAdapter
2. LinkedInEmployeeSearchAdapter
3. LinkedInCompanySearchAdapter
4. LinkedInJobSearchAdapter
5. LinkedInPostSearchAdapter

Environment safety:
- Live LinkedIn searches skip cleanly when credentials or session file are absent or expired.
- Deterministic browser-boundary integration tests validate the full PlaywrightBrowserAdapter -> DOM
  pipeline against real HTML pages without calling external network/LinkedIn.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from linkedin_scraper import BrowserManager, PlaywrightBrowserAdapter
from linkedin_scraper.adapters.search import (
    LinkedInCompanySearchAdapter,
    LinkedInEmployeeSearchAdapter,
    LinkedInJobSearchAdapter,
    LinkedInPersonSearchAdapter,
    LinkedInPostSearchAdapter,
)
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError
from linkedin_scraper.search.filters import (
    CompanySearchFilter,
    CompanySize,
    ConnectionDegree,
    DatePosted,
    EmployeeSearchFilter,
    ExperienceLevel,
    JobSearchFilter,
    PersonSearchFilter,
    PostSearchFilter,
    SortBy,
    WorkplaceType,
)
from linkedin_scraper.search.ports import (
    CompanySearchPort,
    EmployeeSearchPort,
    JobSearchPort,
    PersonSearchPort,
    PostSearchPort,
)
from linkedin_scraper.search.queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
)
from linkedin_scraper.search.results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
    SearchPage,
)
from linkedin_scraper.search.services import LinkedInSearchFacade

SESSION_FILE = Path(__file__).parent.parent.parent / "linkedin_session.json"


# ===========================================================================
# Deterministic Browser-Boundary Integration Tests (Real Playwright Engine)
# ===========================================================================

MOCK_PERSON_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head><title>LinkedIn People Search</title></head>
<body>
  <div class="search-results-container">
    <li class="reusable-search__result-container">
      <div class="entity-result__item">
        <a class="app-aware-link" href="https://www.linkedin.com/in/alex-smith-12345?miniProfileUrn=urn%3Ali%3Afs_miniProfile%3A123">
          <span dir="ltr"><span aria-hidden="true">Alex Smith</span></span>
        </a>
        <div class="entity-result__primary-subtitle">Senior Staff Engineer at TechCorp</div>
        <div class="entity-result__secondary-subtitle">San Francisco Bay Area</div>
        <div class="entity-result__summary">Passionate about scalable distributed systems...</div>
      </div>
    </li>
    <li class="reusable-search__result-container">
      <div class="entity-result__item">
        <a class="app-aware-link" href="https://www.linkedin.com/in/alex-smith-12345?tracking=duplicate">
          <span dir="ltr"><span aria-hidden="true">Alex Smith</span></span>
        </a>
        <div class="entity-result__primary-subtitle">Senior Staff Engineer at TechCorp</div>
        <div class="entity-result__secondary-subtitle">San Francisco Bay Area</div>
      </div>
    </li>
    <li class="reusable-search__result-container">
      <div class="entity-result__item">
        <a class="app-aware-link" href="https://www.linkedin.com/in/maria-garcia-8899/?trackingId=xyz#profile">
          <span dir="ltr"><span aria-hidden="true">Maria Garcia</span></span>
        </a>
        <div class="entity-result__primary-subtitle">Engineering Manager at CloudScale</div>
        <div class="entity-result__secondary-subtitle">Austin, Texas, United States</div>
      </div>
    </li>
  </div>
</body>
</html>
"""

MOCK_COMPANY_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head><title>LinkedIn Companies Search</title></head>
<body>
  <div class="search-results-container">
    <li class="reusable-search__result-container">
      <div class="entity-result__item">
        <a class="app-aware-link" href="https://www.linkedin.com/company/techcorp-inc?trk=public_search">
          <span dir="ltr"><span aria-hidden="true">TechCorp Inc.</span></span>
        </a>
        <div class="entity-result__primary-subtitle">Computer Software · 10,001+ employees</div>
        <div class="entity-result__secondary-subtitle">San Francisco, California</div>
        <div class="entity-result__summary">Building the cloud platform for next-gen AI...</div>
      </div>
    </li>
    <li class="reusable-search__result-container">
      <div class="entity-result__item">
        <a class="app-aware-link" href="https://www.linkedin.com/company/cloudscale-systems/">
          <span dir="ltr"><span aria-hidden="true">CloudScale Systems</span></span>
        </a>
        <div class="entity-result__primary-subtitle">Information Technology & Services · 501-1,000 employees</div>
        <div class="entity-result__secondary-subtitle">Austin, TX</div>
      </div>
    </li>
  </div>
</body>
</html>
"""

MOCK_JOB_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head><title>LinkedIn Jobs Search</title></head>
<body>
  <div class="jobs-search-results-list">
    <div class="job-card-container" data-job-id="10101">
      <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/10101/?refId=abc&trackingId=def">
        Principal Distributed Systems Engineer
      </a>
      <div class="job-card-container__primary-description">TechCorp</div>
      <div class="job-card-container__metadata-item">San Francisco, CA (Remote)</div>
      <time datetime="2026-08-10">2 days ago</time>
    </div>
    <div class="job-card-container" data-job-id="20202">
      <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/20202/">
        Senior Backend Engineer - Python / Rust
      </a>
      <div class="job-card-container__primary-description">CloudScale</div>
      <div class="job-card-container__metadata-item">Austin, TX (On-site)</div>
      <time datetime="2026-08-12">1 day ago</time>
    </div>
  </div>
</body>
</html>
"""

MOCK_POST_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head><title>LinkedIn Posts Search</title></head>
<body>
  <div class="search-results-container">
    <div class="feed-shared-update-v2" data-urn="urn:li:activity:7123456789">
      <a class="app-aware-link update-components-actor__container-link" href="https://www.linkedin.com/feed/update/urn:li:activity:7123456789/?trackingId=feed">
        Excited to announce our new distributed indexing engine release today! #python #engineering
      </a>
    </div>
    <div class="feed-shared-update-v2" data-urn="urn:li:activity:7987654321">
      <a class="app-aware-link" href="https://www.linkedin.com/feed/update/urn:li:activity:7987654321/">
        We are hiring Staff Engineers across Austin and San Francisco. Join our team!
      </a>
    </div>
  </div>
</body>
</html>
"""

MOCK_AUTHWALL_HTML = """
<!DOCTYPE html>
<html>
<head><title>Sign Up | LinkedIn</title></head>
<body>
  <div class="authwall-join-form">Please sign in to view more results</div>
</body>
</html>
"""

MOCK_RATE_LIMIT_HTML = """
<!DOCTYPE html>
<html>
<head><title>LinkedIn</title></head>
<body>
  <div class="error-container">
    <h1>Too many requests</h1>
    <p>Please slow down and try again later.</p>
  </div>
</body>
</html>
"""


class StaticPageBrowserAdapter(PlaywrightBrowserAdapter):
    """PlaywrightBrowserAdapter subclass that preserves DOM content on goto for testing."""

    def __init__(self, page, simulated_url: str = "https://www.linkedin.com/search/results/all/"):
        super().__init__(page)
        self._simulated_url = simulated_url

    @property
    def url(self) -> str:
        return self._simulated_url

    @url.setter
    def url(self, value: str) -> None:
        self._simulated_url = value

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: float = 60000) -> None:
        # Avoid navigating away from the set_content HTML
        return


@pytest.mark.integration
@pytest.mark.asyncio
async def test_person_adapter_with_real_playwright():
    """Validate PersonSearchAdapter against real Playwright page with rendered HTML DOM."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_PERSON_SEARCH_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/search/results/people/")
        assert isinstance(adapter, PlaywrightBrowserAdapter)

        search_adapter = LinkedInPersonSearchAdapter(adapter)
        assert isinstance(search_adapter, PersonSearchPort)

        query = PersonSearchQuery(keywords="Alex Smith", limit=10)
        page_res = await search_adapter.search_people(query)

        assert isinstance(page_res, SearchPage)
        assert len(page_res.items) == 2  # 3 elements in HTML, but alex-smith is deduplicated
        assert all(isinstance(item, PersonSearchResult) for item in page_res.items)

        alex = page_res.items[0]
        assert alex.name == "Alex Smith"
        assert alex.linkedin_url == "https://www.linkedin.com/in/alex-smith-12345/"

        maria = page_res.items[1]
        assert maria.name == "Maria Garcia"
        assert maria.linkedin_url == "https://www.linkedin.com/in/maria-garcia-8899/"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_employee_adapter_with_real_playwright():
    """Validate EmployeeSearchAdapter against real Playwright page with rendered HTML DOM."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_PERSON_SEARCH_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/search/results/people/?currentCompany=%5B%221000%22%5D")

        search_adapter = LinkedInEmployeeSearchAdapter(adapter)
        assert isinstance(search_adapter, EmployeeSearchPort)

        query = EmployeeSearchQuery(company_identifier="TechCorp", keywords="Engineer", limit=5)
        page_res = await search_adapter.search_employees(query)

        assert isinstance(page_res, SearchPage)
        assert len(page_res.items) == 2
        assert all(isinstance(item, EmployeeSearchResult) for item in page_res.items)
        assert page_res.items[0].name == "Alex Smith"
        assert page_res.items[0].linkedin_url == "https://www.linkedin.com/in/alex-smith-12345/"
        assert page_res.items[0].company_name == "TechCorp"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_company_adapter_with_real_playwright():
    """Validate CompanySearchAdapter against real Playwright page with rendered HTML DOM."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_COMPANY_SEARCH_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/search/results/companies/")

        search_adapter = LinkedInCompanySearchAdapter(adapter)
        assert isinstance(search_adapter, CompanySearchPort)

        query = CompanySearchQuery(keywords="TechCorp", limit=10)
        page_res = await search_adapter.search_companies(query)

        assert isinstance(page_res, SearchPage)
        assert len(page_res.items) == 2
        assert all(isinstance(item, CompanySearchResult) for item in page_res.items)

        techcorp = page_res.items[0]
        assert techcorp.name == "TechCorp Inc."
        assert techcorp.linkedin_url == "https://www.linkedin.com/company/techcorp-inc/"

        cloudscale = page_res.items[1]
        assert cloudscale.name == "CloudScale Systems"
        assert cloudscale.linkedin_url == "https://www.linkedin.com/company/cloudscale-systems/"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_job_adapter_with_real_playwright():
    """Validate JobSearchAdapter against real Playwright page with rendered HTML DOM."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_JOB_SEARCH_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/jobs/search/")

        search_adapter = LinkedInJobSearchAdapter(adapter)
        assert isinstance(search_adapter, JobSearchPort)

        query = JobSearchQuery(keywords="Distributed Systems", limit=10)
        page_res = await search_adapter.search_jobs(query)

        assert isinstance(page_res, SearchPage)
        assert len(page_res.items) == 2
        assert all(isinstance(item, JobSearchResult) for item in page_res.items)

        job1 = page_res.items[0]
        assert "Principal Distributed Systems Engineer" in job1.job_title
        assert "https://www.linkedin.com/jobs/view/10101/" in job1.linkedin_url

        job2 = page_res.items[1]
        assert "Senior Backend Engineer" in job2.job_title
        assert "https://www.linkedin.com/jobs/view/20202/" in job2.linkedin_url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_adapter_with_real_playwright():
    """Validate PostSearchAdapter against real Playwright page with rendered HTML DOM."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_POST_SEARCH_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/search/results/content/")

        search_adapter = LinkedInPostSearchAdapter(adapter)
        assert isinstance(search_adapter, PostSearchPort)

        query = PostSearchQuery(keywords="distributed indexing engine", limit=10)
        page_res = await search_adapter.search_posts(query)

        assert isinstance(page_res, SearchPage)
        assert len(page_res.items) == 2
        assert all(isinstance(item, PostSearchResult) for item in page_res.items)

        post1 = page_res.items[0]
        assert "distributed indexing engine" in (post1.text_snippet or "")
        assert "urn:li:activity:7123456789" in (post1.linkedin_url or "")

        post2 = page_res.items[1]
        assert "hiring Staff Engineers" in (post2.text_snippet or "")
        assert "urn:li:activity:7987654321" in (post2.linkedin_url or "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_facade_composition_with_real_playwright():
    """Validate LinkedInSearchFacade orchestrating all 5 adapters over Playwright."""
    async with BrowserManager(headless=True) as bm:
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/search/results/all/")
        facade = LinkedInSearchFacade(
            person_port=LinkedInPersonSearchAdapter(adapter),
            employee_port=LinkedInEmployeeSearchAdapter(adapter),
            company_port=LinkedInCompanySearchAdapter(adapter),
            job_port=LinkedInJobSearchAdapter(adapter),
            post_port=LinkedInPostSearchAdapter(adapter),
        )

        await bm.page.set_content(MOCK_PERSON_SEARCH_HTML)
        person_res = await facade.search_people(PersonSearchQuery(keywords="Alex", limit=5))
        assert len(person_res.items) == 2

        await bm.page.set_content(MOCK_PERSON_SEARCH_HTML)
        emp_res = await facade.search_employees(EmployeeSearchQuery(company_identifier="TechCorp", limit=5))
        assert len(emp_res.items) == 2

        await bm.page.set_content(MOCK_COMPANY_SEARCH_HTML)
        company_res = await facade.search_companies(CompanySearchQuery(keywords="TechCorp", limit=5))
        assert len(company_res.items) == 2

        await bm.page.set_content(MOCK_JOB_SEARCH_HTML)
        job_res = await facade.search_jobs(JobSearchQuery(keywords="Engineer", limit=5))
        assert len(job_res.items) == 2

        await bm.page.set_content(MOCK_POST_SEARCH_HTML)
        post_res = await facade.search_posts(PostSearchQuery(keywords="hiring", limit=5))
        assert len(post_res.items) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_boundary_rate_limit_detection():
    """Validate rate limit detection on live Playwright engine DOM."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_RATE_LIMIT_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/search/results/people/")

        search_adapter = LinkedInPersonSearchAdapter(adapter)

        with pytest.raises(RateLimitError) as exc_info:
            await search_adapter.search_people(PersonSearchQuery(keywords="Rate Limit Test"))
        assert "Rate limit message detected" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_boundary_authwall_detection():
    """Validate authwall detection on live Playwright navigation."""
    async with BrowserManager(headless=True) as bm:
        await bm.page.set_content(MOCK_AUTHWALL_HTML)
        adapter = StaticPageBrowserAdapter(bm.page, simulated_url="https://www.linkedin.com/authwall?trk=test")

        search_adapter = LinkedInPersonSearchAdapter(adapter)

        # Test authwall detection
        with pytest.raises((AuthenticationError, RateLimitError)) as exc_info:
            await search_adapter.search_people(PersonSearchQuery(keywords="Authwall Test"))
        assert "authwall" in str(exc_info.value).lower() or "checkpoint" in str(exc_info.value).lower()


# ===========================================================================
# Live LinkedIn Network Integration Tests (Gracefully Skips if Session Absent)
# ===========================================================================


def _check_live_session():
    if not SESSION_FILE.exists():
        pytest.skip("Session file (linkedin_session.json) not found; skipping live LinkedIn network tests.")


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_linkedin_person_search(browser_with_session):
    """Execute real live search against LinkedIn people endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInPersonSearchAdapter(adapter)

    query = PersonSearchQuery(
        keywords="Satya Nadella",
        limit=5,
        filters=PersonSearchFilter(
            network_depths=[ConnectionDegree.SECOND, ConnectionDegree.THIRD]
        ),
    )
    try:
        page_res = await search_adapter.search_people(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live person search must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, PersonSearchResult)
            assert item.name is not None and len(item.name.strip()) > 0
            assert "\n" not in item.name, f"Name contains unparsed newline: {item.name!r}"
            assert "linkedin.com/in/" in item.linkedin_url
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_linkedin_company_search(browser_with_session):
    """Execute real live search against LinkedIn company endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInCompanySearchAdapter(adapter)

    query = CompanySearchQuery(
        keywords="Microsoft",
        limit=5,
        filters=CompanySearchFilter(
            company_sizes=[CompanySize.SIZE_10000_PLUS]
        ),
    )
    try:
        page_res = await search_adapter.search_companies(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live company search must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, CompanySearchResult)
            assert item.name is not None and len(item.name.strip()) > 0
            assert "\n" not in item.name, f"Company name contains unparsed newline: {item.name!r}"
            assert "linkedin.com/company/" in item.linkedin_url
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_linkedin_employee_search(browser_with_session):
    """Execute real live search against LinkedIn company employee endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInEmployeeSearchAdapter(adapter)

    query = EmployeeSearchQuery(
        company_identifier="Microsoft",
        keywords="Software Engineer",
        limit=5,
        filters=EmployeeSearchFilter(
            titles=["Software Engineer"]
        ),
    )
    try:
        page_res = await search_adapter.search_employees(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live employee search must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, EmployeeSearchResult)
            assert item.name is not None and len(item.name.strip()) > 0
            assert "\n" not in item.name, f"Employee name contains unparsed newline: {item.name!r}"
            assert item.linkedin_url is None or "linkedin.com/in/" in item.linkedin_url
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_linkedin_job_search(browser_with_session):
    """Execute real live search against LinkedIn job endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInJobSearchAdapter(adapter)

    query = JobSearchQuery(
        keywords="Software Engineer",
        location="Remote",
        limit=5,
        filters=JobSearchFilter(
            workplace_types=[WorkplaceType.REMOTE],
            experience_levels=[ExperienceLevel.MID_SENIOR],
        ),
    )
    try:
        page_res = await search_adapter.search_jobs(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live job search must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, JobSearchResult)
            assert item.job_title is not None and len(item.job_title.strip()) > 0
            assert "\n" not in item.job_title, f"Job title contains unparsed newline: {item.job_title!r}"
            assert "linkedin.com/jobs/view/" in item.linkedin_url
            if item.location:
                assert item.job_title not in item.location, "Job title leaked into location"
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_linkedin_post_search(browser_with_session):
    """Execute real live search against LinkedIn post/feed endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInPostSearchAdapter(adapter)

    query = PostSearchQuery(
        keywords="Artificial Intelligence Python",
        limit=5,
        filters=PostSearchFilter(
            date_posted=DatePosted.PAST_WEEK,
            sort_by=SortBy.DATE,
        ),
    )
    try:
        page_res = await search_adapter.search_posts(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live post search must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, PostSearchResult)
            assert (
                (item.linkedin_url and ("linkedin.com/feed/update" in item.linkedin_url or "linkedin.com/posts" in item.linkedin_url))
                or (item.text_snippet and len(item.text_snippet.strip()) > 0)
            ), "Post search result must contain a valid post URL or text snippet"
    except (AuthenticationError, RateLimitError) as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
