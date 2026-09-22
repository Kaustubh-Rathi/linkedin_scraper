"""Async command runners for the LinkedIn scraper CLI."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from .. import (
    BrowserManager,
    CompanyPostsScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
    LinkedInSearchFacade,
    PersonScraper,
    wait_for_manual_login,
)
from ..search.export import export_results, infer_export_format


def _dump_result(result: Any, output: str | None) -> None:
    """Write a Pydantic model or list as JSON/CSV to a file or stdout."""
    fmt = infer_export_format(output) if output else "json"
    text = export_results(result, format=fmt)

    if output:
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
        print(f"Wrote {output}", file=sys.stderr)
    else:
        print(text)


@asynccontextmanager
async def session_browser(
    session: str, headed: bool = False
) -> AsyncIterator[BrowserManager]:
    """Open a browser and load a saved LinkedIn session."""
    async with BrowserManager(headless=not headed) as browser:
        await browser.load_session(session)
        yield browser


async def cmd_login(session: str, timeout_ms: int = 300000) -> int:
    """Open a headed browser and save a LinkedIn session after manual login."""
    print("Opening LinkedIn login page...", file=sys.stderr)
    async with BrowserManager(headless=False) as manager:
        browser = manager.browser_port
        await browser.goto("https://www.linkedin.com/login")
        print(
            f"Log in in the browser window (up to {timeout_ms // 60000} minutes)...",
            file=sys.stderr,
        )
        try:
            await wait_for_manual_login(browser, timeout=timeout_ms)
        except Exception as exc:
            print(f"Login failed: {exc}", file=sys.stderr)
            return 1
        await manager.save_session(session)
        print(f"Session saved to {session}", file=sys.stderr)
    return 0


async def cmd_person(
    url: str,
    session: str,
    headed: bool = False,
    output: str | None = None,
) -> int:
    async with session_browser(session, headed=headed) as manager:
        person = await PersonScraper(manager.browser_port).scrape(url)
        _dump_result(person, output)
    return 0


async def cmd_company(
    url: str,
    session: str,
    headed: bool = False,
    output: str | None = None,
) -> int:
    async with session_browser(session, headed=headed) as manager:
        company = await CompanyScraper(manager.browser_port).scrape(url)
        _dump_result(company, output)
    return 0


async def cmd_jobs(
    keywords: str | None,
    location: str | None,
    limit: int,
    session: str,
    headed: bool = False,
    output: str | None = None,
    scrape_details: bool = False,
) -> int:
    async with session_browser(session, headed=headed) as manager:
        urls = await JobSearchScraper(manager.browser_port).search(
            keywords=keywords, location=location, limit=limit
        )
        if not scrape_details:
            _dump_result(urls, output)
            return 0
        jobs = []
        scraper = JobScraper(manager.browser_port)
        for job_url in urls:
            jobs.append(await scraper.scrape(job_url))
        _dump_result(jobs, output)
    return 0


async def cmd_posts(
    url: str,
    limit: int,
    session: str,
    headed: bool = False,
    output: str | None = None,
) -> int:
    async with session_browser(session, headed=headed) as manager:
        posts = await CompanyPostsScraper(manager.browser_port).scrape(url, limit=limit)
        _dump_result(posts, output)
    return 0


async def cmd_search(
    entity_type: str,
    keywords: str | None = None,
    location: str | None = None,
    company: str | None = None,
    title: str | None = None,
    limit: int = 25,
    page_size: int = 10,
    export_format: str | None = None,
    session: str = "linkedin_session.json",
    headed: bool = False,
    output: str | None = None,
) -> int:
    """Execute typed search query across entities, consuming pages and exporting results."""
    from ..search import (
        CompanySearchFilter,
        CompanySearchQuery,
        EmployeeSearchFilter,
        EmployeeSearchQuery,
        JobSearchFilter,
        JobSearchQuery,
        PersonSearchFilter,
        PersonSearchQuery,
        PostSearchFilter,
        PostSearchQuery,
    )

    t = entity_type.lower().strip()
    query: Any
    if t in ("people", "person"):
        query = PersonSearchQuery(
            keywords=keywords,
            limit=page_size,
            filters=PersonSearchFilter(
                location=[location] if location else [],
                current_company=[company] if company else [],
                title=title,
            ),
        )
    elif t in ("companies", "company"):
        query = CompanySearchQuery(
            keywords=keywords,
            limit=page_size,
            filters=CompanySearchFilter(
                location=[location] if location else [],
            ),
        )
    elif t in ("jobs", "job"):
        query = JobSearchQuery(
            keywords=keywords,
            limit=page_size,
            filters=JobSearchFilter(
                location=[location] if location else [],
                companies=[company] if company else [],
            ),
        )
    elif t in ("posts", "post"):
        query = PostSearchQuery(
            keywords=keywords,
            limit=page_size,
            filters=PostSearchFilter(
                author_company=[company] if company else [],
            ),
        )
    elif t in ("employees", "employee"):
        if not company:
            print("Error: --company is required for employee search", file=sys.stderr)
            return 1
        query = EmployeeSearchQuery(
            company_identifier=company,
            keywords=keywords,
            limit=page_size,
            filters=EmployeeSearchFilter(
                location=[location] if location else [],
                title=title,
            ),
        )
    else:
        print(f"Error: Unknown search entity type: {entity_type}", file=sys.stderr)
        return 1

    async with session_browser(session, headed=headed) as manager:
        client = LinkedInSearchFacade.from_browser(manager.browser_port)
        workflow_result = await client.execute_workflow(
            query=query,
            max_results=limit,
            page_size=page_size,
            export_format=export_format,
            export_path=output,
        )
        if not output:
            fmt = export_format or "json"
            print(workflow_result.export(format=fmt))
        else:
            print(f"Wrote {len(workflow_result.items)} results to {output}", file=sys.stderr)
    return 0
