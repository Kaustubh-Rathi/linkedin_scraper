"""Characterization and deterministic production-path tests for Company extraction."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Tag

import pytest

from linkedin_scraper import Company, CompanyScraper
from linkedin_scraper.ports.browser import BrowserPort, ElementPort

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html"


# ---------------------------------------------------------------------------
# Fixture DOM Parser & Test Browser Adapter
# ---------------------------------------------------------------------------


class CompanyFixtureElement(ElementPort):
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
        selectors = [s.strip() for s in selector.split(",")]
        matched_tags: List[Tag] = []
        for sel in selectors:
            try:
                elements = self._tag.select(sel)
                for el in elements:
                    if isinstance(el, Tag) and el not in matched_tags:
                        matched_tags.append(el)
            except Exception:
                continue
        return [CompanyFixtureElement(t) for t in matched_tags]


class CompanyFixtureBrowser(BrowserPort):
    """
    Deterministic BrowserPort stand-in serving HTML fixtures for company scraping.
    """

    def __init__(
        self,
        html_content: str,
        current_url: str = "https://www.linkedin.com/company/example-corp/",
    ) -> None:
        self._url = current_url
        self._soup = BeautifulSoup(html_content, "html.parser")
        self.goto_history: List[str] = []
        self.recorded_calls: List[Tuple[str, Dict[str, Any]]] = []

    @classmethod
    def from_fixture_file(
        cls,
        path: Path,
        current_url: str = "https://www.linkedin.com/company/example-corp/",
    ) -> CompanyFixtureBrowser:
        content = path.read_text(encoding="utf-8")
        return cls(content, current_url=current_url)

    @property
    def url(self) -> str:
        return self._url

    async def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: float = 60000,
    ) -> None:
        self._url = url
        self.goto_history.append(url)
        self.recorded_calls.append(("goto", {"url": url, "wait_until": wait_until}))

    async def wait_for_selector(
        self, selector: str, timeout: float = 5000, state: str = "visible"
    ) -> None:
        self.recorded_calls.append(
            ("wait_for_selector", {"selector": selector, "state": state})
        )

    async def wait_for_load_state(
        self, state: str = "domcontentloaded", timeout: float = 30000
    ) -> None:
        self.recorded_calls.append(("wait_for_load_state", {"state": state}))

    async def wait_for_url(
        self, predicate_or_url: Any, timeout: float = 30000
    ) -> None:
        self.recorded_calls.append(("wait_for_url", {"target": predicate_or_url}))

    async def wait_for_timeout(self, timeout: float) -> None:
        self.recorded_calls.append(("wait_for_timeout", {"timeout": timeout}))

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        self.recorded_calls.append(("evaluate", {"expression": expression, "arg": arg}))
        return None

    async def extract_text_safe(
        self, selector: str, default: str = "", timeout: float = 2000
    ) -> str:
        self.recorded_calls.append(
            ("extract_text_safe", {"selector": selector, "default": default})
        )
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
        self.recorded_calls.append(("fill", {"selector": selector, "value": value}))

    async def click(self, selector: str) -> None:
        self.recorded_calls.append(("click", {"selector": selector}))

    def locator(self, selector: str) -> Any:
        return self

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        self.recorded_calls.append(("query_selector_all", {"selector": selector}))
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
        return [CompanyFixtureElement(t) for t in matched_tags]

    async def bring_to_front(self) -> None:
        self.recorded_calls.append(("bring_to_front", {}))

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        self.recorded_calls.append(("add_cookies", {"count": len(cookies)}))

    async def keyboard_press(self, key: str) -> None:
        self.recorded_calls.append(("keyboard_press", {"key": key}))


# ---------------------------------------------------------------------------
# Production-Path Test: Full CompanyScraper.scrape() with company_overview.html
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_full_production_company_scraper_path():
    """
    Exercise CompanyScraper -> real browser-facing acquisition -> real pure parser -> Company model.
    Zero internal method mocking. Real orchestration against company_overview.html.
    """
    fixture_path = FIXTURES_DIR / "company_overview.html"
    browser = CompanyFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/company/example-corp/"
    )
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/example-corp/")

    # 1. Identity and URL
    assert isinstance(company, Company)
    assert company.linkedin_url == "https://www.linkedin.com/company/example-corp/"
    assert company.name == "Example Corp"

    # 2. About section
    assert company.about_us == "We build example products for developers worldwide."

    # 3. Overview details
    assert company.industry == "Software Development"
    assert company.company_size == "1,001-5,000 employees"
    assert company.headquarters == "San Francisco, California"
    assert company.website == "https://example.com"

    # 4. Fallback fields (absent from top card, verified None)
    assert company.phone is None
    assert company.founded is None
    assert company.company_type is None
    assert company.specialties is None

    # 5. Model-only fields verified as default
    assert company.headcount is None
    assert company.showcase_pages == []
    assert company.affiliated_companies == []
    assert company.employees == []


# ---------------------------------------------------------------------------
# Fallback Behavior Tests: DT/DD Legacy Page Structure
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_dt_dd_fallback_all_fields():
    """
    Verify DT/DD fallback structure populates all legacy overview fields
    when modern top-card summary items are absent.
    """
    fixture_path = FIXTURES_DIR / "company_dt_dd_fallback.html"
    browser = CompanyFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/company/legacy-corp/"
    )
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/legacy-corp/")

    assert company.name == "Legacy Corp"
    assert company.about_us == "Pioneering enterprise solutions since 1980."
    assert company.website == "https://legacycorp.example.com"
    assert company.industry == "Software"
    assert company.company_size == "500-1,000 employees"
    assert company.headquarters == "Seattle, WA"
    assert company.company_type == "Privately Held"
    assert company.founded == "1980"
    assert company.specialties == "Enterprise Software, Cloud"
    assert company.phone == "1-800-555-0199"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_loose_dt_dd_fallback():
    """Verify loose dt and dd elements (without dl wrapper) are successfully extracted."""
    html = """
    <html><body><main>
      <h1>Loose DT Corp</h1>
      <dt>Website</dt>
      <dd>https://loosedt.example.com</dd>
      <dt>Industry</dt>
      <dd>Healthcare</dd>
    </main></body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/loose-dt/")
    assert company.name == "Loose DT Corp"
    assert company.website == "https://loosedt.example.com"
    assert company.industry == "Healthcare"



@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_missing_fields_graceful():
    """Verify scraper gracefully returns None/defaults for missing optional fields."""
    html = """
    <html><body><main>
      <h1>Minimal Co</h1>
    </main></body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/minimal-co/")
    assert company.name == "Minimal Co"
    assert company.about_us is None
    assert company.website is None
    assert company.industry is None
    assert company.headquarters is None
    assert company.company_size is None
    assert company.phone is None
    assert company.founded is None
    assert company.company_type is None
    assert company.specialties is None
    assert company.headcount is None
    assert company.showcase_pages == []
    assert company.affiliated_companies == []
    assert company.employees == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_missing_h1_raises_required_field_error():
    """Verify scraper raises RequiredFieldExtractionError when h1 is absent."""
    from linkedin_scraper.core.exceptions import RequiredFieldExtractionError

    html = """
    <html><body><main>
      <p>No heading here</p>
    </main></body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    with pytest.raises(RequiredFieldExtractionError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/company/unknown-co/")
    assert exc_info.value.field_name == "name"
    assert "https://www.linkedin.com/company/unknown-co/" in str(exc_info.value)



@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_external_link_filtering():
    """Verify website link selector ignores internal LinkedIn links and prefers external URLs."""
    html = """
    <html><body><main>
      <h1>Tech Solutions</h1>
      <a href="https://www.linkedin.com/company/tech-solutions/jobs/">See jobs</a>
      <a href="https://www.linkedin.com/feed/">LinkedIn Feed</a>
      <a href="https://techsolutions.io">Visit website</a>
    </main></body></html>
    """
    browser = CompanyFixtureBrowser(html)
    scraper = CompanyScraper(browser)

    company = await scraper.scrape("https://www.linkedin.com/company/tech-solutions/")
    assert company.name == "Tech Solutions"
    assert company.website == "https://techsolutions.io"


@pytest.mark.unit
def test_company_model_validation_rejects_invalid_url():
    """Verify Company model validates that URL contains /company/."""
    with pytest.raises(ValueError, match="Must be a valid LinkedIn company URL"):
        Company(linkedin_url="https://www.linkedin.com/in/someone/")


# ---------------------------------------------------------------------------
# AST Purity & Zero-Leakage Test Gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_company_layer_playwright_zero_leakage_ast_gate():
    """Verify zero Playwright imports, Page refs, or raw_page accesses in Company scrapers and parsers."""
    src_dir = Path(__file__).resolve().parents[2] / "linkedin_scraper"
    company_scraper_file = src_dir / "scrapers" / "company" / "scraper.py"
    company_parser_file = src_dir / "parsers" / "company.py"

    forbidden_modules = [
        "playwright",
        "playwright.async_api",
        "playwright.sync_api",
        "linkedin_scraper.core.browser",
    ]
    forbidden_names = {
        "Page",
        "Locator",
        "ElementHandle",
    }

    files_to_check = [company_scraper_file, company_parser_file]

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
                    pytest.fail(
                        f"Forbidden type/identifier reference '{node.id}' in {file_path.name}:{node.lineno}"
                    )


# ---------------------------------------------------------------------------
# Parser Purity Gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_company_parser_purity_gate():
    """Verify parsers/company.py has 0 browser/DOM/scraper dependencies."""
    src_dir = Path(__file__).resolve().parents[2] / "linkedin_scraper"
    parser_file = src_dir / "parsers" / "company.py"

    tree = ast.parse(parser_file.read_text(encoding="utf-8"), filename=str(parser_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "playwright" not in alias.name
                assert "ports" not in alias.name
                assert "scrapers" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "playwright" not in mod
            assert "ports" not in mod
            assert "scrapers" not in mod


# ---------------------------------------------------------------------------
# Runtime Browser Boundary Test
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_runtime_browser_boundary_recording():
    """Verify CompanyScraper uses only BrowserPort protocol operations during execution."""
    fixture_path = FIXTURES_DIR / "company_overview.html"
    browser = CompanyFixtureBrowser.from_fixture_file(fixture_path)
    scraper = CompanyScraper(browser)

    await scraper.scrape("https://www.linkedin.com/company/example-corp/")

    method_names = [call[0] for call in browser.recorded_calls]
    assert "goto" in method_names
    assert "extract_text_safe" in method_names
    assert "query_selector_all" in method_names

    # Verify no raw Playwright attributes or calls were made
    for call_name, _ in browser.recorded_calls:
        assert call_name in {
            "goto",
            "extract_text_safe",
            "query_selector_all",
            "wait_for_selector",
            "wait_for_load_state",
            "wait_for_url",
            "wait_for_timeout",
            "evaluate",
            "fill",
            "click",
            "bring_to_front",
            "add_cookies",
            "keyboard_press",
        }


# ---------------------------------------------------------------------------
# Backward Compatibility & Public API
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_company_scraper_public_api_compatibility():
    """Verify CompanyScraper constructor backward compatibility (positional and keyword)."""
    # BrowserPort direct
    browser = CompanyFixtureBrowser("<html></html>")
    scraper1 = CompanyScraper(browser)
    assert scraper1.browser is browser

    # Keyword page=
    scraper2 = CompanyScraper(page=browser)
    assert scraper2.browser is browser

    # Positional page_or_browser
    scraper3 = CompanyScraper(browser, callback=None)
    assert scraper3.browser is browser
