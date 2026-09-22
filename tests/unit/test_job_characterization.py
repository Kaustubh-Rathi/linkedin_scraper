"""Characterization and deterministic production-path tests for Job extraction."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, Tag

import pytest

from linkedin_scraper import Job, JobScraper
from linkedin_scraper.ports.browser import BrowserPort, ElementPort

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html"


# ---------------------------------------------------------------------------
# Fixture DOM Parser & Test Browser Adapter
# ---------------------------------------------------------------------------


class JobFixtureElement(ElementPort):
    """BeautifulSoup-backed ElementPort stand-in."""

    def __init__(self, tag: Tag) -> None:
        self._tag = tag

    async def text_content(self, timeout: float = 2000) -> Optional[str]:
        return self._tag.get_text().strip()

    async def inner_text(self) -> str:
        return self._tag.get_text(separator="\n", strip=True)

    async def get_attribute(self, name: str, timeout: float = 2000) -> Optional[str]:
        val = self._tag.get(name)
        if isinstance(val, list):
            return " ".join(val)
        return val

    async def is_visible(self, timeout: float = 1000) -> bool:
        return True

    async def click(self) -> None:
        pass

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        sub_elements = self._tag.select(selector)
        return [JobFixtureElement(el) for el in sub_elements if isinstance(el, Tag)]


class JobFixtureBrowser(BrowserPort):
    """
    Deterministic BrowserPort stand-in serving HTML fixtures for job scraping.
    """

    def __init__(self, html_content: str, current_url: str = "https://www.linkedin.com/jobs/view/123456789/") -> None:
        self._url = current_url
        self._soup = BeautifulSoup(html_content, "html.parser")
        self.goto_history: List[str] = []

    @classmethod
    def from_fixture_file(cls, path: Path, current_url: str = "https://www.linkedin.com/jobs/view/123456789/") -> JobFixtureBrowser:
        content = path.read_text(encoding="utf-8")
        return cls(content, current_url=current_url)

    @property
    def url(self) -> str:
        return self._url

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: float = 60000) -> None:
        self._url = url
        self.goto_history.append(url)

    async def wait_for_selector(
        self, selector: str, timeout: float = 5000, state: str = "visible"
    ) -> None:
        pass

    async def wait_for_load_state(self, state: str = "domcontentloaded", timeout: float = 30000) -> None:
        pass

    async def wait_for_url(self, predicate_or_url: Any, timeout: float = 30000) -> None:
        pass

    async def wait_for_timeout(self, timeout: float) -> None:
        pass

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return None

    async def extract_text_safe(
        self, selector: str, default: str = "", timeout: float = 2000
    ) -> str:
        # Handle comma-separated selector lists
        selectors = [s.strip() for s in selector.split(",")]
        for sel in selectors:
            try:
                el = self._soup.select_one(sel)
                if el:
                    text = el.get_text(separator="\n", strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return default

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def click(self, selector: str) -> None:
        pass

    def locator(self, selector: str) -> Any:
        return self

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        selectors = [s.strip() for s in selector.split(",")]
        matched_tags: List[Tag] = []
        for sel in selectors:
            try:
                elements = self._soup.select(sel)
                for el in elements:
                    if isinstance(el, Tag) and el not in matched_tags:
                        matched_tags.append(el)
            except Exception:
                continue
        return [JobFixtureElement(t) for t in matched_tags]

    async def bring_to_front(self) -> None:
        pass

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        pass

    async def keyboard_press(self, key: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Production-Path Test: Full JobScraper.scrape() with job_details.html
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_full_production_job_scraper_path():
    """
    Exercise JobScraper -> real browser-facing acquisition logic -> real pure parser -> Job model.
    Zero internal method mocking. Real orchestration against job_details.html.
    """
    fixture_path = FIXTURES_DIR / "job_details.html"
    browser = JobFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/jobs/view/3891234567/"
    )
    scraper = JobScraper(browser)

    job = await scraper.scrape("https://www.linkedin.com/jobs/view/3891234567/")

    # 1. Identity and URL
    assert isinstance(job, Job)
    assert job.linkedin_url == "https://www.linkedin.com/jobs/view/3891234567/"
    assert job.job_title == "Software Engineer"

    # 2. Company Info
    assert job.company == "Acme Inc"
    assert job.company_linkedin_url == "https://www.linkedin.com/company/acme/"

    # 3. Top Card Parsed Details
    assert job.location == "San Francisco, CA"
    assert job.posted_date == "2 days ago"
    assert job.applicant_count == "100 applicants"

    # 4. Description
    assert job.job_description is not None
    assert "About the job" in job.job_description
    assert "Build great software with our team." in job.job_description

    # 5. Benefits field classification: MODEL-ONLY (not populated by scraper/parser)
    assert job.benefits is None


# ---------------------------------------------------------------------------
# Fallback Behavior Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_location_fallback_when_top_card_missing():
    """Verify location falls back to scanning main elements when top card is absent."""
    html = """
    <html><body><main>
      <h1>Staff Infrastructure Engineer</h1>
      <a href="https://www.linkedin.com/company/techcorp/">TechCorp</a>
      <span>Austin, Texas, United States</span>
      <article>Build high scale infrastructure.</article>
    </main></body></html>
    """
    browser = JobFixtureBrowser(html)
    scraper = JobScraper(browser)

    job = await scraper.scrape("https://www.linkedin.com/jobs/view/999001/")
    assert job.job_title == "Staff Infrastructure Engineer"
    assert job.location == "Austin, Texas, United States"
    assert job.posted_date is None
    assert job.applicant_count is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_posted_date_and_applicant_count_fallbacks():
    """Verify posted date and applicant count fallbacks activate when top-card description is missing."""
    html = """
    <html><body><main>
      <h1>Lead Site Reliability Engineer</h1>
      <a href="https://www.linkedin.com/company/cloud/">Cloud Global</a>
      <span>Remote</span>
      <span>3 weeks ago</span>
      <span>Over 200 applicants</span>
      <article>Help manage reliability.</article>
    </main></body></html>
    """
    browser = JobFixtureBrowser(html)
    scraper = JobScraper(browser)

    job = await scraper.scrape("https://www.linkedin.com/jobs/view/999002/")
    assert job.location == "Remote"
    assert job.posted_date == "3 weeks ago"
    assert job.applicant_count == "Over 200 applicants"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_description_container_fallback():
    """Verify description falls back to .jobs-description__content when article tag is absent."""
    html = """
    <html><body><main>
      <h1>Data Scientist</h1>
      <a href="https://www.linkedin.com/company/dataai/">Data AI</a>
      <div class="job-details-jobs-unified-top-card__primary-description-container">
        New York, NY · 1 day ago · 25 applicants
      </div>
      <div class="jobs-description__content">
        Develop advanced machine learning models and pipelines.
      </div>
    </main></body></html>
    """
    browser = JobFixtureBrowser(html)
    scraper = JobScraper(browser)

    job = await scraper.scrape("https://www.linkedin.com/jobs/view/999003/")
    assert job.job_description == "Develop advanced machine learning models and pipelines."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_missing_optional_fields_graceful():
    """Verify scraper gracefully returns None for missing optional fields."""
    html = """
    <html><body><main>
      <h1>Principal Architect</h1>
    </main></body></html>
    """
    browser = JobFixtureBrowser(html)
    scraper = JobScraper(browser)

    job = await scraper.scrape("https://www.linkedin.com/jobs/view/999004/")
    assert job.job_title == "Principal Architect"
    assert job.company is None
    assert job.company_linkedin_url is None
    assert job.location is None
    assert job.posted_date is None
    assert job.applicant_count is None
    assert job.job_description is None
    assert job.benefits is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_company_relative_url_normalization():
    """Verify relative company URLs are cleanly normalized to absolute https URLs."""
    html = """
    <html><body><main>
      <h1>Frontend Developer</h1>
      <a href="/company/designcraft/">DesignCraft Studio</a>
      <article>Design beautiful UIs.</article>
    </main></body></html>
    """
    browser = JobFixtureBrowser(html)
    scraper = JobScraper(browser)

    job = await scraper.scrape("https://www.linkedin.com/jobs/view/999005/")
    assert job.company == "DesignCraft Studio"
    assert job.company_linkedin_url == "https://www.linkedin.com/company/designcraft/"


# ---------------------------------------------------------------------------
# AST Purity & Zero-Leakage Test Gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_job_layer_playwright_zero_leakage_ast_gate():
    """Verify zero Playwright imports, Page refs, or raw_page accesses in Job scrapers and parsers."""
    src_dir = Path(__file__).resolve().parents[2] / "linkedin_scraper"
    job_scraper_file = src_dir / "scrapers" / "job" / "scraper.py"
    job_search_file = src_dir / "scrapers" / "job" / "search.py"
    job_parser_file = src_dir / "parsers" / "job.py"

    forbidden_modules = [
        "playwright",
        "playwright.async_api",
        "playwright.sync_api",
        "linkedin_scraper.core.browser",
    ]
    forbidden_calls = {
        "locator",
        "raw_page",
    }
    forbidden_names = {
        "Page",
        "Locator",
        "ElementHandle",
    }

    files_to_check = [job_scraper_file, job_search_file, job_parser_file]

    for file_path in files_to_check:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not (
                            alias.name == forbidden or alias.name.startswith(forbidden + ".")
                        ), f"Forbidden import '{alias.name}' in {file_path.name}:{node.lineno}"

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for forbidden in forbidden_modules:
                    assert not (
                        mod == forbidden or mod.startswith(forbidden + ".")
                    ), f"Forbidden import from '{mod}' in {file_path.name}:{node.lineno}"

            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr == "raw_page":
                    pytest.fail(f"Forbidden .raw_page access in {file_path.name}:{node.lineno}")
                if node.attr == "page" and isinstance(node.value, ast.Name) and node.value.id == "self":
                    pytest.fail(f"Forbidden self.page access in {file_path.name}:{node.lineno}")

            # Check type hint names in function definitions
            elif isinstance(node, ast.Name):
                if node.id in forbidden_names:
                    # Allow if inside a comment/docstring, but ast.Name is code
                    pytest.fail(f"Forbidden type/identifier reference '{node.id}' in {file_path.name}:{node.lineno}")
