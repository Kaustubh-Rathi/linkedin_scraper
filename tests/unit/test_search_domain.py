"""Unit tests for search domain models, filters, queries, results, ports, and services."""

import pytest
from pydantic import ValidationError

from linkedin_scraper.search.filters import (
    CompanySearchFilter,
    CompanySize,
    ConnectionDegree,
    DatePosted,
    EmployeeSearchFilter,
    EmploymentType,
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
    SearchQuery,
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


# --- Filter Validation Tests ---

def test_person_search_filter_cleaning():
    filter_obj = PersonSearchFilter(
        title="  Software Engineer  ",
        location=[" New York ", "", None, "New York", " San Francisco "],
        connection_degrees=[ConnectionDegree.FIRST, ConnectionDegree.SECOND],
    )
    assert filter_obj.title == "Software Engineer"
    assert filter_obj.location == ["New York", "San Francisco"]
    assert filter_obj.connection_degrees == [ConnectionDegree.FIRST, ConnectionDegree.SECOND]


def test_person_search_filter_none_title():
    filter_obj = PersonSearchFilter(title="   ")
    assert filter_obj.title is None


def test_company_search_filter_validation():
    filter_obj = CompanySearchFilter(
        location=["  Remote ", "Remote"],
        company_size=[CompanySize.SIZE_11_50, CompanySize.SIZE_10000_PLUS],
    )
    assert filter_obj.location == ["Remote"]
    assert filter_obj.company_size == [CompanySize.SIZE_11_50, CompanySize.SIZE_10000_PLUS]


def test_job_search_filter_validation():
    filter_obj = JobSearchFilter(
        date_posted=DatePosted.PAST_24H,
        experience_levels=[ExperienceLevel.ENTRY_LEVEL],
        employment_types=[EmploymentType.FULL_TIME],
        workplace_types=[WorkplaceType.REMOTE],
        easy_apply_only=True,
    )
    assert filter_obj.date_posted == DatePosted.PAST_24H
    assert filter_obj.easy_apply_only is True


def test_post_search_filter_validation():
    filter_obj = PostSearchFilter(
        date_posted=DatePosted.PAST_WEEK,
        sort_by=SortBy.DATE,
    )
    assert filter_obj.sort_by == SortBy.DATE


def test_employee_search_filter_validation():
    filter_obj = EmployeeSearchFilter(
        title=" Engineering Manager ",
        department=[" R&D ", "R&D", " Operations "],
    )
    assert filter_obj.title == "Engineering Manager"
    assert filter_obj.department == ["R&D", "Operations"]


# --- Query Validation & Composition Tests ---

def test_search_query_keyword_and_limit_validation():
    query = SearchQuery(keywords="  python developer  ", limit=50, filters={})
    assert query.keywords == "python developer"
    assert query.limit == 50

    query_none = SearchQuery(keywords="   ", filters={})
    assert query_none.keywords is None

    query_token = SearchQuery(continuation_token="  token123  ", filters={})
    assert query_token.continuation_token == "token123"

    query_token_none = SearchQuery(continuation_token="   ", filters={})
    assert query_token_none.continuation_token is None

    with pytest.raises(ValidationError):
        SearchQuery(limit=0, filters={})

    with pytest.raises(ValidationError):
        SearchQuery(limit=1001, filters={})


def test_person_search_query_defaults():
    query = PersonSearchQuery(keywords="Developer")
    assert query.keywords == "Developer"
    assert isinstance(query.filters, PersonSearchFilter)


def test_employee_search_query_validation():
    query = EmployeeSearchQuery(company_identifier=" google.com ")
    assert query.company_identifier == "google.com"

    with pytest.raises(ValidationError):
        EmployeeSearchQuery(company_identifier="   ")


def test_other_entity_queries():
    c_query = CompanySearchQuery(keywords="Tech")
    assert isinstance(c_query.filters, CompanySearchFilter)

    j_query = JobSearchQuery(keywords="Backend")
    assert isinstance(j_query.filters, JobSearchFilter)

    p_query = PostSearchQuery(keywords="AI")
    assert isinstance(p_query.filters, PostSearchFilter)


# --- Result Models & SearchPage Tests ---

def test_result_dto_instantiation():
    person_res = PersonSearchResult(
        name="Alice",
        linkedin_url="https://www.linkedin.com/in/alice",
        headline="Tech Lead",
    )
    assert person_res.name == "Alice"

    company_res = CompanySearchResult(
        name="Acme Inc",
        linkedin_url="https://www.linkedin.com/company/acme",
    )
    assert company_res.name == "Acme Inc"

    job_res = JobSearchResult(
        job_title="DevOps Engineer",
        linkedin_url="https://www.linkedin.com/jobs/view/12345",
    )
    assert job_res.job_title == "DevOps Engineer"

    post_res = PostSearchResult(
        author_name="Bob",
        text_snippet="Hello World",
    )
    assert post_res.author_name == "Bob"

    emp_res = EmployeeSearchResult(
        name="Charlie",
        designation="Product Manager",
    )
    assert emp_res.name == "Charlie"


def test_search_page_container():
    page = SearchPage(
        items=["item1", "item2"],
        total_count=100,
        continuation_token="cursor_abc",
        has_more=True,
    )
    assert len(page.items) == 2
    assert page.total_count == 100
    assert page.continuation_token == "cursor_abc"
    assert page.has_more is True


# --- Ports Runtime Verification ---

def test_ports_runtime_checkable():
    class DummyPersonAdapter:
        async def search_people(self, query: PersonSearchQuery) -> SearchPage[PersonSearchResult]:
            return SearchPage()

    class DummyCompanyAdapter:
        async def search_companies(self, query: CompanySearchQuery) -> SearchPage[CompanySearchResult]:
            return SearchPage()

    class DummyJobAdapter:
        async def search_jobs(self, query: JobSearchQuery) -> SearchPage[JobSearchResult]:
            return SearchPage()

    class DummyPostAdapter:
        async def search_posts(self, query: PostSearchQuery) -> SearchPage[PostSearchResult]:
            return SearchPage()

    class DummyEmployeeAdapter:
        async def search_employees(self, query: EmployeeSearchQuery) -> SearchPage[EmployeeSearchResult]:
            return SearchPage()

    assert isinstance(DummyPersonAdapter(), PersonSearchPort)
    assert isinstance(DummyCompanyAdapter(), CompanySearchPort)
    assert isinstance(DummyJobAdapter(), JobSearchPort)
    assert isinstance(DummyPostAdapter(), PostSearchPort)
    assert isinstance(DummyEmployeeAdapter(), EmployeeSearchPort)


# --- LinkedInSearchFacade Tests ---

@pytest.mark.asyncio
async def test_search_domain_service_delegation():
    class MockPersonPort:
        async def search_people(self, query: PersonSearchQuery) -> SearchPage[PersonSearchResult]:
            return SearchPage(items=[PersonSearchResult(name="Person A", linkedin_url="https://linkedin.com/in/a")])

    class MockCompanyPort:
        async def search_companies(self, query: CompanySearchQuery) -> SearchPage[CompanySearchResult]:
            return SearchPage(items=[CompanySearchResult(name="Company A", linkedin_url="https://linkedin.com/company/a")])

    class MockJobPort:
        async def search_jobs(self, query: JobSearchQuery) -> SearchPage[JobSearchResult]:
            return SearchPage(items=[JobSearchResult(job_title="Job A", linkedin_url="https://linkedin.com/jobs/view/1")])

    class MockPostPort:
        async def search_posts(self, query: PostSearchQuery) -> SearchPage[PostSearchResult]:
            return SearchPage(items=[PostSearchResult(author_name="Post Author")])

    class MockEmployeePort:
        async def search_employees(self, query: EmployeeSearchQuery) -> SearchPage[EmployeeSearchResult]:
            return SearchPage(items=[EmployeeSearchResult(name="Emp A")])

    service = LinkedInSearchFacade(
        person_port=MockPersonPort(),
        company_port=MockCompanyPort(),
        job_port=MockJobPort(),
        post_port=MockPostPort(),
        employee_port=MockEmployeePort(),
    )

    res_p = await service.search_people(PersonSearchQuery())
    assert res_p.items[0].name == "Person A"

    res_c = await service.search_companies(CompanySearchQuery())
    assert res_c.items[0].name == "Company A"

    res_j = await service.search_jobs(JobSearchQuery())
    assert res_j.items[0].job_title == "Job A"

    res_post = await service.search_posts(PostSearchQuery())
    assert res_post.items[0].author_name == "Post Author"

    res_emp = await service.search_employees(EmployeeSearchQuery(company_identifier="acme"))
    assert res_emp.items[0].name == "Emp A"


@pytest.mark.asyncio
async def test_search_domain_service_unconfigured_ports():
    service = LinkedInSearchFacade()

    with pytest.raises(NotImplementedError):
        await service.search_people(PersonSearchQuery())

    with pytest.raises(NotImplementedError):
        await service.search_companies(CompanySearchQuery())

    with pytest.raises(NotImplementedError):
        await service.search_jobs(JobSearchQuery())

    with pytest.raises(NotImplementedError):
        await service.search_posts(PostSearchQuery())

    with pytest.raises(NotImplementedError):
        await service.search_employees(EmployeeSearchQuery(company_identifier="acme"))
