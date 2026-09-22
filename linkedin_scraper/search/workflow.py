"""Search consumption workflow, pagination runner, and export pipeline orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Iterator,
    TextIO,
    TypeVar,
)

from pydantic import BaseModel, Field

from .export import ExportFormat, export_results, infer_export_format
from .queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
    SearchQuery,
)
from .results import SearchPage

logger = logging.getLogger(__name__)

ItemT = TypeVar("ItemT")
QueryT = TypeVar("QueryT", bound=SearchQuery[Any])
AsyncSearchCallable = Callable[[QueryT], Awaitable[SearchPage[ItemT]]]


class SearchWorkflowResult(BaseModel, Generic[ItemT]):
    """
    Structured outcome of an executed search consumption workflow.

    Encapsulates collected result items, pagination statistics, and built-in export helpers.
    """

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    items: list[ItemT] = Field(default_factory=list)
    total_collected: int = 0
    pages_fetched: int = 0
    has_more: bool = False
    last_continuation_token: str | None = None
    query_keywords: str | None = None

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[ItemT]:  # type: ignore[override]
        return iter(self.items)

    def __getitem__(self, index: int) -> ItemT:
        return self.items[index]

    def to_dicts(self) -> list[dict[str, Any]]:
        """Serialize all result items into a list of dictionaries."""
        dicts: list[dict[str, Any]] = []
        for item in self.items:
            if isinstance(item, BaseModel):
                dicts.append(item.model_dump(mode="python"))
            elif isinstance(item, dict):
                dicts.append(dict(item))
            elif hasattr(item, "__dict__"):
                dicts.append(dict(item.__dict__))
            else:
                dicts.append({"value": str(item)})
        return dicts

    def export(
        self,
        format: str | ExportFormat = ExportFormat.JSON,
        destination: str | Path | TextIO | None = None,
        **kwargs: Any,
    ) -> str:
        """Export collected results to CSV, JSON, or JSONL format."""
        return export_results(
            self.items,
            format=format,
            destination=destination,
            **kwargs,
        )

    def to_csv(
        self, destination: str | Path | TextIO | None = None
    ) -> str:
        """Export collected results to CSV format."""
        return self.export(format=ExportFormat.CSV, destination=destination)

    def to_json(
        self,
        destination: str | Path | TextIO | None = None,
        indent: int = 2,
    ) -> str:
        """Export collected results to formatted JSON."""
        return self.export(
            format=ExportFormat.JSON, destination=destination, indent=indent
        )

    def to_jsonl(
        self, destination: str | Path | TextIO | None = None
    ) -> str:
        """Export collected results to JSON Lines format."""
        return self.export(format=ExportFormat.JSONL, destination=destination)


async def iterate_search_pages(
    search_fn: AsyncSearchCallable[QueryT, ItemT],
    initial_query: QueryT,
    max_pages: int | None = None,
) -> AsyncIterator[SearchPage[ItemT]]:
    """
    Asynchronously stream search pages from a search port or search callable,
    following continuation tokens until exhausted or max_pages reached.
    """
    if max_pages is not None and max_pages <= 0:
        return

    current_query = initial_query
    pages_count = 0

    while True:
        page = await search_fn(current_query)
        yield page
        pages_count += 1

        if max_pages is not None and pages_count >= max_pages:
            break

        # Stop if no further pages or token unchanged
        if not page.has_more or not page.continuation_token or not page.items:
            break

        if page.continuation_token == current_query.continuation_token:
            logger.debug(
                "Continuation token did not advance (%s); terminating pagination.",
                page.continuation_token,
            )
            break

        current_query = current_query.model_copy(
            update={"continuation_token": page.continuation_token}
        )


async def iterate_search_results(
    search_fn: AsyncSearchCallable[QueryT, ItemT],
    initial_query: QueryT,
    max_results: int | None = None,
    page_size: int | None = None,
) -> AsyncIterator[ItemT]:
    """
    Asynchronously stream individual search result items across pages,
    enforcing an exact max_results ceiling.
    """
    if max_results is not None and max_results <= 0:
        return

    current_query = initial_query
    if page_size is not None and page_size > 0:
        current_query = current_query.model_copy(update={"limit": page_size})

    collected = 0

    while True:
        # Constrain next page request limit to only what is remaining
        if max_results is not None:
            remaining = max_results - collected
            if remaining <= 0:
                break
            if current_query.limit > remaining:
                current_query = current_query.model_copy(
                    update={"limit": max(1, min(remaining, 1000))}
                )

        page = await search_fn(current_query)

        for item in page.items:
            yield item
            collected += 1
            if max_results is not None and collected >= max_results:
                return

        if not page.has_more or not page.continuation_token or not page.items:
            break

        if page.continuation_token == current_query.continuation_token:
            break

        current_query = current_query.model_copy(
            update={"continuation_token": page.continuation_token}
        )


async def consume_search(
    search_fn: AsyncSearchCallable[QueryT, ItemT],
    initial_query: QueryT,
    max_results: int | None = None,
    page_size: int | None = None,
) -> list[ItemT]:
    """
    Execute a search query and consume all matching result items up to max_results into a list.
    """
    results: list[ItemT] = []
    async for item in iterate_search_results(
        search_fn, initial_query, max_results=max_results, page_size=page_size
    ):
        results.append(item)
    return results


async def execute_search_workflow(
    search_target: AsyncSearchCallable[QueryT, ItemT] | Any,
    query: QueryT,
    max_results: int | None = None,
    page_size: int | None = None,
    export_format: str | ExportFormat | None = None,
    export_path: str | Path | None = None,
) -> SearchWorkflowResult[ItemT]:
    """
    High-level search consumption workflow.

    Executes query across pages, enforces result limits, tracks pagination metrics,
    and optionally exports the results to disk in the requested format (CSV/JSON/JSONL).

    :param search_target: Async search function or a search client instance with .search() / .search_*()
    :param query: Typed search query (PersonSearchQuery, CompanySearchQuery, etc.)
    :param max_results: Maximum number of items to collect.
    :param page_size: Page size per request.
    :param export_format: Format to export to ('json', 'csv', 'jsonl'). Auto-detected if export_path given.
    :param export_path: Optional destination file path to save exported results.
    :return: SearchWorkflowResult containing items, metrics, and export methods.
    """
    # Resolve search function from target if a client/facade instance is passed
    search_fn: AsyncSearchCallable[QueryT, ItemT]
    if isinstance(query, PersonSearchQuery) and hasattr(search_target, "search_people"):
        search_fn = search_target.search_people
    elif isinstance(query, CompanySearchQuery) and hasattr(search_target, "search_companies"):
        search_fn = search_target.search_companies
    elif isinstance(query, JobSearchQuery) and hasattr(search_target, "search_jobs"):
        search_fn = search_target.search_jobs
    elif isinstance(query, PostSearchQuery) and hasattr(search_target, "search_posts"):
        search_fn = search_target.search_posts
    elif isinstance(query, EmployeeSearchQuery) and hasattr(search_target, "search_employees"):
        search_fn = search_target.search_employees
    elif callable(search_target):
        search_fn = search_target
    elif hasattr(search_target, "search") and callable(search_target.search):
        search_fn = search_target.search
    else:
        raise TypeError(
            f"Cannot resolve search callable from target: {type(search_target)}"
        )

    if max_results is not None and max_results <= 0:
        return SearchWorkflowResult[ItemT](
            items=[],
            total_collected=0,
            pages_fetched=0,
            has_more=False,
            last_continuation_token=None,
            query_keywords=query.keywords,
        )

    current_query = query
    if page_size is not None and page_size > 0:
        current_query = current_query.model_copy(update={"limit": page_size})

    items: list[ItemT] = []
    pages_fetched = 0
    last_token: str | None = None
    has_more_flag = False

    while True:
        if max_results is not None:
            remaining = max_results - len(items)
            if remaining <= 0:
                break
            if current_query.limit > remaining:
                current_query = current_query.model_copy(
                    update={"limit": max(1, min(remaining, 1000))}
                )

        page = await search_fn(current_query)
        pages_fetched += 1
        last_token = page.continuation_token
        has_more_flag = page.has_more

        for item in page.items:
            items.append(item)
            if max_results is not None and len(items) >= max_results:
                break

        if max_results is not None and len(items) >= max_results:
            break

        if not page.has_more or not page.continuation_token or not page.items:
            break

        if page.continuation_token == current_query.continuation_token:
            break

        current_query = current_query.model_copy(
            update={"continuation_token": page.continuation_token}
        )

    workflow_result = SearchWorkflowResult[ItemT](
        items=items,
        total_collected=len(items),
        pages_fetched=pages_fetched,
        has_more=has_more_flag and (max_results is None or len(items) >= (max_results or 0)),
        last_continuation_token=last_token,
        query_keywords=query.keywords,
    )

    # Optional export execution
    if export_path is not None or export_format is not None:
        fmt: ExportFormat
        if export_format is not None:
            fmt = ExportFormat.from_str(export_format)
        elif export_path is not None:
            fmt = infer_export_format(export_path, default=ExportFormat.JSON)
        else:
            fmt = ExportFormat.JSON

        workflow_result.export(format=fmt, destination=export_path)

    return workflow_result

