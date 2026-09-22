"""Unit tests for the LinkedInSearchFacade unified search service."""

from unittest.mock import MagicMock
import pytest

from linkedin_scraper.adapters.search import (
    LinkedInCompanySearchAdapter,
    LinkedInEmployeeSearchAdapter,
    LinkedInJobSearchAdapter,
    LinkedInPersonSearchAdapter,
    LinkedInPostSearchAdapter,
)
from linkedin_scraper.ports.browser import BrowserPort
from linkedin_scraper.search import (
    CompanySearchQuery,
    CompanySearchResult,
    EmployeeSearchQuery,
    EmployeeSearchResult,
    JobSearchQuery,
    JobSearchResult,
    LinkedInSearchFacade,
    PersonSearchQuery,
    PersonSearchResult,
    PostSearchQuery,
    PostSearchResult,
    SearchPage,
)
from linkedin_scraper.search.ports import (
    CompanySearchPort,
    EmployeeSearchPort,
    JobSearchPort,
    PersonSearchPort,
    PostSearchPort,
)


class DummyPersonPort:
    def __init__(self, return_page: SearchPage[PersonSearchResult]):
        self.return_page = return_page
        self.received_query: PersonSearchQuery | None = None

    async def search_people(
        self, query: PersonSearchQuery
    ) -> SearchPage[PersonSearchResult]:
        self.received_query = query
        return self.return_page


class DummyCompanyPort:
    def __init__(self, return_page: SearchPage[CompanySearchResult]):
        self.return_page = return_page
        self.received_query: CompanySearchQuery | None = None

    async def search_companies(
        self, query: CompanySearchQuery
    ) -> SearchPage[CompanySearchResult]:
        self.received_query = query
        return self.return_page


class DummyJobPort:
    def __init__(self, return_page: SearchPage[JobSearchResult]):
        self.return_page = return_page
        self.received_query: JobSearchQuery | None = None

    async def search_jobs(
        self, query: JobSearchQuery
    ) -> SearchPage[JobSearchResult]:
        self.received_query = query
        return self.return_page


class DummyPostPort:
    def __init__(self, return_page: SearchPage[PostSearchResult]):
        self.return_page = return_page
        self.received_query: PostSearchQuery | None = None

    async def search_posts(
        self, query: PostSearchQuery
    ) -> SearchPage[PostSearchResult]:
        self.received_query = query
        return self.return_page


class DummyEmployeePort:
    def __init__(self, return_page: SearchPage[EmployeeSearchResult]):
        self.return_page = return_page
        self.received_query: EmployeeSearchQuery | None = None

    async def search_employees(
        self, query: EmployeeSearchQuery
    ) -> SearchPage[EmployeeSearchResult]:
        self.received_query = query
        return self.return_page


def test_dependency_injection_assignment():
    """Verify ports are stored on instance attributes correctly."""
    person_port = DummyPersonPort(SearchPage())
    company_port = DummyCompanyPort(SearchPage())
    job_port = DummyJobPort(SearchPage())
    post_port = DummyPostPort(SearchPage())
    employee_port = DummyEmployeePort(SearchPage())

    client = LinkedInSearchFacade(
        person_port=person_port,
        company_port=company_port,
        job_port=job_port,
        post_port=post_port,
        employee_port=employee_port,
    )

    assert client.person_port is person_port
    assert client.company_port is company_port
    assert client.job_port is job_port
    assert client.post_port is post_port
    assert client.employee_port is employee_port


@pytest.mark.asyncio
async def test_person_search_delegation():
    expected_result = SearchPage(
        items=[PersonSearchResult(name="Jane Doe", linkedin_url="https://linkedin.com/in/janedoe")],
        total_count=1,
        continuation_token="10",
        has_more=True,
    )
    port = DummyPersonPort(expected_result)
    client = LinkedInSearchFacade(person_port=port)
    query = PersonSearchQuery(keywords="Engineer")

    res = await client.search_people(query)

    assert port.received_query is query
    assert res is expected_result
    assert res.items[0].name == "Jane Doe"


@pytest.mark.asyncio
async def test_company_search_delegation():
    expected_result = SearchPage(
        items=[CompanySearchResult(name="Acme Corp", linkedin_url="https://linkedin.com/company/acme")],
        total_count=1,
    )
    port = DummyCompanyPort(expected_result)
    client = LinkedInSearchFacade(company_port=port)
    query = CompanySearchQuery(keywords="Tech")

    res = await client.search_companies(query)

    assert port.received_query is query
    assert res is expected_result
    assert res.items[0].name == "Acme Corp"


@pytest.mark.asyncio
async def test_job_search_delegation():
    expected_result = SearchPage(
        items=[JobSearchResult(job_title="Software Architect", linkedin_url="https://linkedin.com/jobs/view/999")],
        total_count=1,
    )
    port = DummyJobPort(expected_result)
    client = LinkedInSearchFacade(job_port=port)
    query = JobSearchQuery(keywords="Architect")

    res = await client.search_jobs(query)

    assert port.received_query is query
    assert res is expected_result
    assert res.items[0].job_title == "Software Architect"


@pytest.mark.asyncio
async def test_post_search_delegation():
    expected_result = SearchPage(
        items=[PostSearchResult(author_name="Alice Specialist", text_snippet="Python 3.14 announcement")],
        total_count=1,
    )
    port = DummyPostPort(expected_result)
    client = LinkedInSearchFacade(post_port=port)
    query = PostSearchQuery(keywords="Python")

    res = await client.search_posts(query)

    assert port.received_query is query
    assert res is expected_result
    assert res.items[0].author_name == "Alice Specialist"


@pytest.mark.asyncio
async def test_employee_search_delegation():
    expected_result = SearchPage(
        items=[EmployeeSearchResult(name="Bob Developer", designation="Senior Staff")],
        total_count=1,
    )
    port = DummyEmployeePort(expected_result)
    client = LinkedInSearchFacade(employee_port=port)
    query = EmployeeSearchQuery(company_identifier="google.com")

    res = await client.search_employees(query)

    assert port.received_query is query
    assert res is expected_result
    assert res.items[0].name == "Bob Developer"


@pytest.mark.asyncio
async def test_unconfigured_ports_raise_not_implemented_error():
    client = LinkedInSearchFacade()

    with pytest.raises(NotImplementedError, match="PersonSearchPort is not configured"):
        await client.search_people(PersonSearchQuery())

    with pytest.raises(NotImplementedError, match="CompanySearchPort is not configured"):
        await client.search_companies(CompanySearchQuery())

    with pytest.raises(NotImplementedError, match="JobSearchPort is not configured"):
        await client.search_jobs(JobSearchQuery())

    with pytest.raises(NotImplementedError, match="PostSearchPort is not configured"):
        await client.search_posts(PostSearchQuery())

    with pytest.raises(NotImplementedError, match="EmployeeSearchPort is not configured"):
        await client.search_employees(EmployeeSearchQuery(company_identifier="google"))


def test_ports_protocol_compliance():
    """Verify dummy ports adhere to runtime checkable protocols."""
    assert isinstance(DummyPersonPort(SearchPage()), PersonSearchPort)
    assert isinstance(DummyCompanyPort(SearchPage()), CompanySearchPort)
    assert isinstance(DummyJobPort(SearchPage()), JobSearchPort)
    assert isinstance(DummyPostPort(SearchPage()), PostSearchPort)
    assert isinstance(DummyEmployeePort(SearchPage()), EmployeeSearchPort)


def test_facade_from_browser_factory():
    """Verify LinkedInSearchFacade.from_browser instantiates all standard search adapters."""
    mock_browser = MagicMock(spec=BrowserPort)
    client = LinkedInSearchFacade.from_browser(mock_browser)

    assert isinstance(client.person_port, LinkedInPersonSearchAdapter)
    assert isinstance(client.company_port, LinkedInCompanySearchAdapter)
    assert isinstance(client.job_port, LinkedInJobSearchAdapter)
    assert isinstance(client.post_port, LinkedInPostSearchAdapter)
    assert isinstance(client.employee_port, LinkedInEmployeeSearchAdapter)


@pytest.mark.asyncio
async def test_facade_dynamic_search_and_consume():
    """Verify facade search() dynamic dispatch and consume() helper."""
    expected_page = SearchPage(
        items=[PersonSearchResult(name="Charlie", linkedin_url="https://linkedin.com/in/charlie")],
        has_more=False,
    )
    port = DummyPersonPort(expected_page)
    client = LinkedInSearchFacade(person_port=port)

    # Dynamic search dispatch
    res = await client.search(PersonSearchQuery(keywords="Charlie"))
    assert res.items[0].name == "Charlie"

    # Consume helper
    items = await client.consume(PersonSearchQuery(keywords="Charlie"), max_results=1)
    assert len(items) == 1
    assert items[0].name == "Charlie"
