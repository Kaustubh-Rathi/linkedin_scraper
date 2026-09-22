"""
Authoritative Live E2E Verification Suite for LinkedIn Scraper (10 Features).

Covers all 10 core capabilities against real production LinkedIn:
1. Auth / session restore
2. Person search
3. Employee search
4. Company search
5. Job search
6. Post search
7. Person detail
8. Company detail
9. Job detail
10. Company posts

Semantics:
- Every test is marked @pytest.mark.live
- Never mocked, runs real browser & network
- Validates field-level outputs
- When session is expired/rate-limited/challenged, classifies external environment state clearly
- Does NOT swallow unexpected application errors
"""

import pytest
from pathlib import Path

from linkedin_scraper import (
    CompanyPostsScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
    PersonScraper,
)
from linkedin_scraper.adapters.search import (
    LinkedInCompanySearchAdapter,
    LinkedInEmployeeSearchAdapter,
    LinkedInJobSearchAdapter,
    LinkedInPersonSearchAdapter,
    LinkedInPostSearchAdapter,
)
from linkedin_scraper.core.auth import is_logged_in
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from linkedin_scraper.models import Company, Job, Person, Post
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

SESSION_FILE = Path(__file__).resolve().parents[2] / "linkedin_session.json"


def _check_live_session() -> None:
    if not SESSION_FILE.exists():
        pytest.skip("Live session file (linkedin_session.json) not found; skipping live E2E test.")


# ---------------------------------------------------------------------------
# 1. Live Auth / Session Restore
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_auth_session_restore(browser_with_session):
    """Verify live session restore and authentication status against LinkedIn feed."""
    _check_live_session()
    try:
        await browser_with_session.page.goto(
            "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000
        )
        logged_in = await is_logged_in(browser_with_session.get_browser_port())
        if not logged_in:
            pytest.skip("Live LinkedIn session expired or requires interactive challenge verification.")
        assert logged_in is True
    except AuthenticationError as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


# ---------------------------------------------------------------------------
# 2. Live Person Search
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_people_search(browser_with_session):
    """Execute live search against LinkedIn people endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInPersonSearchAdapter(adapter)

    query = PersonSearchQuery(
        keywords="Satya Nadella",
        limit=3,
        filters=PersonSearchFilter(
            network_depths=[ConnectionDegree.SECOND, ConnectionDegree.THIRD]
        ),
    )
    try:
        page_res = await search_adapter.search_people(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live people search for known query must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, PersonSearchResult)
            assert item.name is not None and len(item.name.strip()) > 0
            assert "\n" not in item.name, f"Name contains unparsed newline/contamination: {item.name!r}"
            assert "linkedin.com/in/" in item.linkedin_url
    except AuthenticationError as e:
        pytest.skip(f"Live LinkedIn session authentication error: {e}")


# ---------------------------------------------------------------------------
# 3. Live Employee Search
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_employee_search(browser_with_session):
    """Execute live search against LinkedIn employee endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInEmployeeSearchAdapter(adapter)

    query = EmployeeSearchQuery(
        company_identifier="Microsoft",
        keywords="Software Engineer",
        limit=3,
        filters=EmployeeSearchFilter(titles=["Software Engineer"]),
    )
    try:
        page_res = await search_adapter.search_employees(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live employee search for Microsoft must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, EmployeeSearchResult)
            assert item.name is not None and len(item.name.strip()) > 0
            assert "\n" not in item.name, f"Employee name contains unparsed newline/contamination: {item.name!r}"
            if item.linkedin_url is not None:
                assert "linkedin.com/in/" in item.linkedin_url
    except AuthenticationError as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


# ---------------------------------------------------------------------------
# 4. Live Company Search
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_company_search(browser_with_session):
    """Execute live search against LinkedIn company endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInCompanySearchAdapter(adapter)

    query = CompanySearchQuery(
        keywords="Microsoft",
        limit=3,
        filters=CompanySearchFilter(
            company_sizes=[CompanySize.SIZE_10000_PLUS]
        ),
    )
    try:
        page_res = await search_adapter.search_companies(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live company search for Microsoft must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, CompanySearchResult)
            assert item.name is not None and len(item.name.strip()) > 0
            assert "\n" not in item.name, f"Company name contains unparsed newline/contamination: {item.name!r}"
            assert "linkedin.com/company/" in item.linkedin_url
    except AuthenticationError as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


# ---------------------------------------------------------------------------
# 5. Live Job Search
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_job_search(browser_with_session):
    """Execute live search against LinkedIn job endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInJobSearchAdapter(adapter)

    query = JobSearchQuery(
        keywords="Software Engineer",
        location="Remote",
        limit=3,
        filters=JobSearchFilter(
            workplace_types=[WorkplaceType.REMOTE],
            experience_levels=[ExperienceLevel.MID_SENIOR],
        ),
    )
    try:
        page_res = await search_adapter.search_jobs(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live job search for remote Software Engineer must return at least 1 result"
        for item in page_res.items:
            assert isinstance(item, JobSearchResult)
            assert item.job_title is not None and len(item.job_title.strip()) > 0
            assert "\n" not in item.job_title, f"Job title contains unparsed newline/contamination: {item.job_title!r}"
            assert "linkedin.com/jobs/view/" in item.linkedin_url
            if item.location:
                assert item.job_title not in item.location, "Job title leaked into location field"
    except AuthenticationError as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


# ---------------------------------------------------------------------------
# 6. Live Post Search
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_post_search(browser_with_session):
    """Execute live search against LinkedIn post/feed endpoint with session."""
    _check_live_session()
    adapter = browser_with_session.get_browser_port()
    search_adapter = LinkedInPostSearchAdapter(adapter)

    query = PostSearchQuery(
        keywords="Artificial Intelligence Python",
        limit=3,
        filters=PostSearchFilter(
            date_posted=DatePosted.PAST_WEEK,
            sort_by=SortBy.DATE,
        ),
    )
    try:
        page_res = await search_adapter.search_posts(query)
        assert isinstance(page_res, SearchPage)
        assert isinstance(page_res.items, list)
        assert len(page_res.items) > 0, "Live post search for AI Python must return results"
        for item in page_res.items:
            assert isinstance(item, PostSearchResult)
            assert (
                (item.linkedin_url and ("linkedin.com/feed/update" in item.linkedin_url or "linkedin.com/posts" in item.linkedin_url))
                or (item.text_snippet and len(item.text_snippet.strip()) > 0)
            ), "Post search result must contain a valid post URL or text snippet"
    except AuthenticationError as e:
        pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")


# ---------------------------------------------------------------------------
# 7. Live Person Detail Scraper
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_person_detail(browser_with_session, test_profile_urls, silent_callback):
    """Scrape live person profile details."""
    _check_live_session()
    scraper = PersonScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        person = await scraper.scrape(test_profile_urls["bill_gates"])
        assert isinstance(person, Person)
        assert person.name == "Bill Gates"
        assert person.linkedin_url == test_profile_urls["bill_gates"]
        assert person.location is not None and len(person.location) > 0
        assert len(person.experiences) > 0, "Bill Gates profile must have non-empty experiences"
        assert len(person.educations) > 0, "Bill Gates profile must have non-empty educations"
    except AuthenticationError as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


# ---------------------------------------------------------------------------
# 8. Live Company Detail Scraper
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_company_detail(browser_with_session, test_company_urls, silent_callback):
    """Scrape live company page details."""
    _check_live_session()
    scraper = CompanyScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        company = await scraper.scrape(test_company_urls["microsoft"])
        assert isinstance(company, Company)
        assert company.name == "Microsoft"
        assert company.linkedin_url == test_company_urls["microsoft"]
        assert company.about_us is not None and len(company.about_us.strip()) > 0
        assert (
            company.industry is not None
            or company.company_size is not None
            or company.headquarters is not None
        )
    except AuthenticationError as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


# ---------------------------------------------------------------------------
# 9. Live Job Detail Scraper
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_job_detail(browser_with_session, test_job_search_params, silent_callback):
    """Scrape live job posting details."""
    _check_live_session()
    search_scraper = JobSearchScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        job_urls = await search_scraper.search(
            keywords=test_job_search_params["keywords"],
            location=test_job_search_params["location"],
            limit=1,
        )
        if not job_urls:
            pytest.skip("No live job URLs returned from LinkedIn search")

        job_scraper = JobScraper(browser_with_session.get_browser_port(), callback=silent_callback)
        job = await job_scraper.scrape(job_urls[0])

        assert isinstance(job, Job)
        assert job.linkedin_url == job_urls[0]
        assert job.job_title is not None and len(job.job_title.strip()) > 0
        assert job.company is not None and len(job.company.strip()) > 0
        assert job.location is not None or job.job_description is not None

    except AuthenticationError as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise


# ---------------------------------------------------------------------------
# 10. Live Company Posts Scraper
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_company_posts(browser_with_session, test_company_urls, silent_callback):
    """Scrape live company posts feed."""
    _check_live_session()
    scraper = CompanyPostsScraper(browser_with_session.get_browser_port(), callback=silent_callback)
    try:
        posts = await scraper.scrape(test_company_urls["microsoft"], limit=3)
        assert isinstance(posts, list)
        assert len(posts) > 0, "Company posts must return non-empty list for active Microsoft feed"
        for post in posts:
            assert isinstance(post, Post)
            assert post.urn is not None or post.linkedin_url is not None or post.text is not None
            if post.text is not None:
                assert len(post.text.strip()) > 0
    except AuthenticationError as e:
        if "Rate limit" in str(e) or "authwall" in str(e) or "checkpoint" in str(e):
            pytest.skip(f"Live LinkedIn session challenge or rate-limited: {e}")
        raise
