"""Unit tests for search consumption, pagination workflow, and limit enforcement."""

import json
from typing import List
import pytest

from linkedin_scraper.search import (
    CompanySearchQuery,
    CompanySearchResult,
    EmployeeSearchQuery,
    EmployeeSearchResult,
    ExportFormat,
    JobSearchQuery,
    JobSearchResult,
    LinkedInSearchFacade,
    PersonSearchQuery,
    PersonSearchResult,
    PostSearchQuery,
    PostSearchResult,
    SearchPage,
    SearchWorkflowResult,
    consume_search,
    execute_search_workflow,
    iterate_search_pages,
    iterate_search_results,
)


class MockPaginatedPersonSearch:
    """Mock search port simulating paginated LinkedIn results."""

    def __init__(self, total_items: int = 25, page_size: int = 10):
        self.total_items = total_items
        self.page_size = page_size
        self.call_history: List[PersonSearchQuery] = []

    async def search_people(
        self, query: PersonSearchQuery
    ) -> SearchPage[PersonSearchResult]:
        self.call_history.append(query)
        start_idx = 0
        if query.continuation_token and query.continuation_token.isdigit():
            start_idx = int(query.continuation_token)

        requested_limit = query.limit or self.page_size
        end_idx = min(start_idx + requested_limit, self.total_items)

        items = [
            PersonSearchResult(
                name=f"Person {i}",
                linkedin_url=f"https://www.linkedin.com/in/person-{i}/",
                headline=f"Role {i}",
            )
            for i in range(start_idx, end_idx)
        ]

        has_more = end_idx < self.total_items
        next_token = str(end_idx) if has_more else None

        return SearchPage[PersonSearchResult](
            items=items,
            total_count=self.total_items,
            continuation_token=next_token,
            has_more=has_more,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iterate_search_pages_pagination():
    mock_search = MockPaginatedPersonSearch(total_items=25, page_size=10)
    query = PersonSearchQuery(keywords="Developer", limit=10)

    pages = []
    async for page in iterate_search_pages(mock_search.search_people, query):
        pages.append(page)

    # 25 items with page_size 10 -> 3 pages (10, 10, 5)
    assert len(pages) == 3
    assert len(pages[0].items) == 10
    assert pages[0].continuation_token == "10"
    assert pages[0].has_more is True

    assert len(pages[1].items) == 10
    assert pages[1].continuation_token == "20"
    assert pages[1].has_more is True

    assert len(pages[2].items) == 5
    assert pages[2].continuation_token is None
    assert pages[2].has_more is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iterate_search_pages_max_pages():
    mock_search = MockPaginatedPersonSearch(total_items=50, page_size=10)
    query = PersonSearchQuery(keywords="Developer", limit=10)

    pages = []
    async for page in iterate_search_pages(mock_search.search_people, query, max_pages=2):
        pages.append(page)

    assert len(pages) == 2
    assert len(pages[0].items) == 10
    assert len(pages[1].items) == 10


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iterate_search_pages_zero_and_empty():
    mock_search = MockPaginatedPersonSearch(total_items=0, page_size=10)
    query = PersonSearchQuery(keywords="Empty")

    # max_pages <= 0
    pages_zero = [p async for p in iterate_search_pages(mock_search.search_people, query, max_pages=0)]
    assert len(pages_zero) == 0

    # empty results
    pages_empty = [p async for p in iterate_search_pages(mock_search.search_people, query)]
    assert len(pages_empty) == 1
    assert len(pages_empty[0].items) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iterate_search_results_limit_enforcement():
    mock_search = MockPaginatedPersonSearch(total_items=50, page_size=10)
    query = PersonSearchQuery(keywords="Engineer", limit=10)

    # Request exactly 15 items
    collected: List[PersonSearchResult] = []
    async for item in iterate_search_results(mock_search.search_people, query, max_results=15):
        collected.append(item)

    assert len(collected) == 15
    assert collected[0].name == "Person 0"
    assert collected[14].name == "Person 14"

    # Verify query limit adjustment on final page
    assert len(mock_search.call_history) == 2
    assert mock_search.call_history[0].limit == 10
    assert mock_search.call_history[1].limit == 5  # remaining needed


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iterate_search_results_zero_and_page_size():
    mock_search = MockPaginatedPersonSearch(total_items=10, page_size=5)
    query = PersonSearchQuery(keywords="Test")

    # max_results <= 0
    res_zero = [i async for i in iterate_search_results(mock_search.search_people, query, max_results=0)]
    assert len(res_zero) == 0

    # with custom page_size
    res_ps = [i async for i in iterate_search_results(mock_search.search_people, query, max_results=3, page_size=2)]
    assert len(res_ps) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consume_search_helper():
    mock_search = MockPaginatedPersonSearch(total_items=22, page_size=10)
    query = PersonSearchQuery(keywords="Lead")

    results = await consume_search(mock_search.search_people, query, max_results=22, page_size=10)
    assert len(results) == 22
    assert results[-1].name == "Person 21"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_workflow_with_facade(tmp_path):
    mock_search = MockPaginatedPersonSearch(total_items=30, page_size=10)
    client = LinkedInSearchFacade(person_port=mock_search)
    query = PersonSearchQuery(keywords="Architect")

    csv_dest = tmp_path / "people_export.csv"
    workflow_result = await client.execute_workflow(
        query=query,
        max_results=12,
        page_size=10,
        export_format=ExportFormat.CSV,
        export_path=csv_dest,
    )

    assert len(workflow_result) == 12
    assert workflow_result.total_collected == 12
    assert workflow_result.pages_fetched == 2
    assert workflow_result.has_more is True

    # Test export container methods
    assert csv_dest.exists()
    csv_content = csv_dest.read_text(encoding="utf-8")
    assert "Person 0" in csv_content
    assert "Person 11" in csv_content

    # In-memory JSON export from container
    json_str = workflow_result.to_json()
    parsed = json.loads(json_str)
    assert len(parsed) == 12
    assert parsed[0]["name"] == "Person 0"

    # In-memory CSV export
    csv_str = workflow_result.to_csv()
    assert "Person 0" in csv_str

    # In-memory JSONL export
    jsonl_str = workflow_result.to_jsonl()
    assert len([l for l in jsonl_str.strip().split("\n") if l]) == 12

    # to_dicts
    dicts = workflow_result.to_dicts()
    assert len(dicts) == 12
    assert dicts[0]["name"] == "Person 0"

    # Iteration & Indexing
    iter_items = [x for x in workflow_result]
    assert len(iter_items) == 12
    assert workflow_result[0].name == "Person 0"


@pytest.mark.unit
def test_workflow_result_to_dicts_varied_types():
    class DummyObj:
        def __init__(self):
            self.x = 99

    res = SearchWorkflowResult(
        items=[
            PersonSearchResult(name="A", linkedin_url="https://a"),
            {"custom": 1},
            DummyObj(),
            "plain_str",
        ]
    )
    dicts = res.to_dicts()
    assert len(dicts) == 4
    assert dicts[0]["name"] == "A"
    assert dicts[1]["custom"] == 1
    assert dicts[2]["x"] == 99
    assert dicts[3]["value"] == "plain_str"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workflow_zero_and_negative_limits():
    mock_search = MockPaginatedPersonSearch(total_items=10)
    query = PersonSearchQuery(keywords="Test")

    res_zero = await execute_search_workflow(mock_search.search_people, query, max_results=0)
    assert len(res_zero) == 0
    assert res_zero.total_collected == 0

    res_neg = await execute_search_workflow(mock_search.search_people, query, max_results=-5)
    assert len(res_neg) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workflow_cycle_detection():
    # Simulate a buggy port that repeats the same token
    async def bad_search(q: PersonSearchQuery) -> SearchPage[PersonSearchResult]:
        return SearchPage[PersonSearchResult](
            items=[PersonSearchResult(name="Stuck", linkedin_url="https://linkedin.com/in/stuck")],
            continuation_token="same_token",
            has_more=True,
        )

    # Calling with query having continuation_token="same_token"
    q = PersonSearchQuery(continuation_token="same_token")
    result = await execute_search_workflow(bad_search, q, max_results=10)
    # Must stop after 1 page rather than loop infinitely
    assert len(result) == 1
    assert result.pages_fetched == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workflow_all_search_domains():
    """Verify workflow executes cleanly across all 5 query types with dynamic facade dispatch."""
    class MultiDomainMock:
        async def search_people(self, q: PersonSearchQuery) -> SearchPage[PersonSearchResult]:
            return SearchPage(items=[PersonSearchResult(name="P", linkedin_url="https://p")])

        async def search_companies(self, q: CompanySearchQuery) -> SearchPage[CompanySearchResult]:
            return SearchPage(items=[CompanySearchResult(name="C", linkedin_url="https://c")])

        async def search_jobs(self, q: JobSearchQuery) -> SearchPage[JobSearchResult]:
            return SearchPage(items=[JobSearchResult(job_title="J", linkedin_url="https://j")])

        async def search_posts(self, q: PostSearchQuery) -> SearchPage[PostSearchResult]:
            return SearchPage(items=[PostSearchResult(author_name="A")])

        async def search_employees(self, q: EmployeeSearchQuery) -> SearchPage[EmployeeSearchResult]:
            return SearchPage(items=[EmployeeSearchResult(name="E")])

    client = LinkedInSearchFacade(
        person_port=MultiDomainMock(),
        company_port=MultiDomainMock(),
        job_port=MultiDomainMock(),
        post_port=MultiDomainMock(),
        employee_port=MultiDomainMock(),
    )

    r_p = await client.execute_workflow(PersonSearchQuery(keywords="dev"), max_results=1)
    assert r_p[0].name == "P"

    r_c = await client.execute_workflow(CompanySearchQuery(keywords="tech"), max_results=1)
    assert r_c[0].name == "C"

    r_j = await client.execute_workflow(JobSearchQuery(keywords="eng"), max_results=1)
    assert r_j[0].job_title == "J"

    r_post = await client.execute_workflow(PostSearchQuery(keywords="ai"), max_results=1)
    assert r_post[0].author_name == "A"

    r_e = await client.execute_workflow(EmployeeSearchQuery(company_identifier="corp"), max_results=1)
    assert r_e[0].name == "E"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workflow_target_resolution_and_exceptions():
    class GenericSearchObj:
        async def search(self, q):
            return SearchPage(items=[PersonSearchResult(name="Generic", linkedin_url="https://g")])

    class PersonSearchObj:
        async def search_people(self, q):
            return SearchPage(items=[PersonSearchResult(name="PersonSpecific", linkedin_url="https://ps")])

    class CompanySearchObj:
        async def search_companies(self, q):
            return SearchPage(items=[CompanySearchResult(name="CompanySpecific", linkedin_url="https://cs")])

    class JobSearchObj:
        async def search_jobs(self, q):
            return SearchPage(items=[JobSearchResult(job_title="JobSpecific", linkedin_url="https://js")])

    class PostSearchObj:
        async def search_posts(self, q):
            return SearchPage(items=[PostSearchResult(author_name="PostSpecific")])

    class EmployeeSearchObj:
        async def search_employees(self, q):
            return SearchPage(items=[EmployeeSearchResult(name="EmployeeSpecific")])

    res_gen = await execute_search_workflow(GenericSearchObj(), PersonSearchQuery())
    assert res_gen[0].name == "Generic"

    res_p = await execute_search_workflow(PersonSearchObj(), PersonSearchQuery())
    assert res_p[0].name == "PersonSpecific"

    res_c = await execute_search_workflow(CompanySearchObj(), CompanySearchQuery())
    assert res_c[0].name == "CompanySpecific"

    res_j = await execute_search_workflow(JobSearchObj(), JobSearchQuery())
    assert res_j[0].job_title == "JobSpecific"

    res_post = await execute_search_workflow(PostSearchObj(), PostSearchQuery())
    assert res_post[0].author_name == "PostSpecific"

    res_e = await execute_search_workflow(EmployeeSearchObj(), EmployeeSearchQuery(company_identifier="abc"))
    assert res_e[0].name == "EmployeeSpecific"

    with pytest.raises(TypeError, match="Cannot resolve search callable"):
        await execute_search_workflow("invalid_target", PersonSearchQuery())
