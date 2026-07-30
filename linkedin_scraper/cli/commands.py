"""Async command runners for the LinkedIn scraper CLI."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from .. import (
    BrowserManager,
    CompanyPostsScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
    PersonScraper,
    wait_for_manual_login,
)


def _dump_result(result: Any, output: Optional[str]) -> None:
    """Write a Pydantic model or list as JSON to a file or stdout."""
    if isinstance(result, list):
        if result and hasattr(result[0], "model_dump"):
            payload = [item.model_dump() for item in result]
        else:
            payload = result
        text = json.dumps(payload, indent=2, default=str)
    elif hasattr(result, "model_dump_json"):
        text = result.model_dump_json(indent=2)
    else:
        text = json.dumps(result, indent=2, default=str)

    if output:
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
        print("Wrote {}".format(output), file=sys.stderr)
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
    async with BrowserManager(headless=False) as browser:
        await browser.page.goto("https://www.linkedin.com/login")
        print(
            "Log in in the browser window (up to {} minutes)...".format(
                timeout_ms // 60000
            ),
            file=sys.stderr,
        )
        try:
            await wait_for_manual_login(browser.page, timeout=timeout_ms)
        except Exception as exc:
            print("Login failed: {}".format(exc), file=sys.stderr)
            return 1
        await browser.save_session(session)
        print("Session saved to {}".format(session), file=sys.stderr)
    return 0


async def cmd_person(
    url: str,
    session: str,
    headed: bool = False,
    output: Optional[str] = None,
) -> int:
    async with session_browser(session, headed=headed) as browser:
        person = await PersonScraper(browser.page).scrape(url)
        _dump_result(person, output)
    return 0


async def cmd_company(
    url: str,
    session: str,
    headed: bool = False,
    output: Optional[str] = None,
) -> int:
    async with session_browser(session, headed=headed) as browser:
        company = await CompanyScraper(browser.page).scrape(url)
        _dump_result(company, output)
    return 0


async def cmd_jobs(
    keywords: Optional[str],
    location: Optional[str],
    limit: int,
    session: str,
    headed: bool = False,
    output: Optional[str] = None,
    scrape_details: bool = False,
) -> int:
    async with session_browser(session, headed=headed) as browser:
        urls = await JobSearchScraper(browser.page).search(
            keywords=keywords, location=location, limit=limit
        )
        if not scrape_details:
            _dump_result(urls, output)
            return 0
        jobs = []
        scraper = JobScraper(browser.page)
        for job_url in urls:
            jobs.append(await scraper.scrape(job_url))
        _dump_result(jobs, output)
    return 0


async def cmd_posts(
    url: str,
    limit: int,
    session: str,
    headed: bool = False,
    output: Optional[str] = None,
) -> int:
    async with session_browser(session, headed=headed) as browser:
        posts = await CompanyPostsScraper(browser.page).scrape(url, limit=limit)
        _dump_result(posts, output)
    return 0
