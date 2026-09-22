"""Characterization, Playwright isolation, and deterministic tests for Company Posts."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from bs4 import BeautifulSoup
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper import CompanyPostsScraper, Post
from linkedin_scraper.parsers.posts import (
    parse_company_posts,
)
from linkedin_scraper.ports.browser import BrowserPort, ElementPort

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html"


# ---------------------------------------------------------------------------
# Recording Fixture BrowserPort for Company Posts
# ---------------------------------------------------------------------------


class PostFixtureBrowser(BrowserPort):
    """
    Deterministic BrowserPort stand-in serving HTML fixtures for post scraping
    while recording all browser-level interactions.
    """

    def __init__(
        self,
        html_content: str,
        current_url: str = "https://www.linkedin.com/company/microsoft/posts/",
    ) -> None:
        self._url = current_url
        self._html = html_content
        self._soup = BeautifulSoup(html_content, "html.parser")
        self.goto_history: List[str] = []
        self.recorded_calls: List[Tuple[str, Dict[str, Any]]] = []
        self.keyboard_press_calls: List[str] = []

    @classmethod
    def from_fixture_file(
        cls,
        path: Path,
        current_url: str = "https://www.linkedin.com/company/microsoft/posts/",
    ) -> PostFixtureBrowser:
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
        self.recorded_calls.append(("goto", {"url": url, "wait_until": wait_until, "timeout": timeout}))

    async def wait_for_selector(
        self, selector: str, timeout: float = 5000, state: str = "visible"
    ) -> None:
        self.recorded_calls.append(
            ("wait_for_selector", {"selector": selector, "state": state})
        )

    async def wait_for_load_state(
        self, state: str = "domcontentloaded", timeout: float = 30000
    ) -> None:
        self.recorded_calls.append(("wait_for_load_state", {"state": state, "timeout": timeout}))

    async def wait_for_url(
        self, predicate_or_url: Any, timeout: float = 30000
    ) -> None:
        self.recorded_calls.append(("wait_for_url", {"target": predicate_or_url}))

    async def wait_for_timeout(self, timeout: float) -> None:
        self.recorded_calls.append(("wait_for_timeout", {"timeout": timeout}))

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        self.recorded_calls.append(("evaluate", {"expression": expression, "arg": arg}))

        # 1. Check if checking activity URNs in HTML for wait_for_posts_to_load
        if "document.body.innerHTML.includes" in expression:
            return "urn:li:activity:" in self._html

        # 2. Scroll simulation
        if "window.scrollTo" in expression or "scrollHeight" in expression:
            return None

        # 3. Post extraction simulation based on DOM fixture
        if "const urnMatches" in expression or "data-urn" in expression:
            return self._extract_posts_from_soup()

        return None

    def _extract_posts_from_soup(self) -> List[Dict[str, Any]]:
        """Simulate the browser DOM JavaScript post extraction against fixture soup."""
        posts: List[Dict[str, Any]] = []
        containers = self._soup.find_all(attrs={"data-urn": re.compile(r"urn:li:activity:")})
        seen_urns = set()

        for el in containers:
            urn = el.get("data-urn")
            if not urn or urn in seen_urns:
                continue
            seen_urns.add(urn)

            text = ""
            text_selectors = [
                ".feed-shared-update-v2__description",
                ".update-components-text",
                ".feed-shared-text",
                '[data-test-id="main-feed-activity-card__commentary"]',
                ".break-words.whitespace-pre-wrap",
            ]

            for sel in text_selectors:
                text_el = el.select_one(sel)
                if text_el:
                    t = text_el.get_text(separator="\n", strip=True)
                    lines = [l.strip() for l in t.split("\n") if l.strip()]
                    is_repeated = len(lines) >= 2 and lines[0] == lines[1]
                    if len(t) > len(text) and len(t) > 20 and not is_repeated:
                        text = t

            if not text or len(text) < 30:
                for sub in el.find_all(["div", "span"]):
                    t = sub.get_text(separator="\n", strip=True)
                    lines = [l.strip() for l in t.split("\n") if l.strip()]
                    is_repeated = len(lines) >= 2 and lines[0] == lines[1]
                    is_actor = sub.find_parent(class_=re.compile(r"feed-shared-actor|actor|social-details")) is not None
                    if (
                        len(t) > len(text)
                        and len(t) > 50
                        and "followers" not in t
                        and "reactions" not in t
                        and not is_repeated
                        and not is_actor
                        and not re.match(r"^\d+[hdwmy]\s", t)
                    ):
                        text = t

            if not text or len(text) < 20:
                continue

            time_el = el.select_one(
                '[class*="actor__sub-description"], [class*="update-components-actor__sub-description"]'
            )
            time_text = time_el.get_text(strip=True) if time_el else ""

            reactions_el = el.select_one(
                'button[aria-label*="reaction"], [class*="social-details-social-counts__reactions"]'
            )
            reactions = reactions_el.get_text(strip=True) if reactions_el else ""

            comments_el = el.select_one('button[aria-label*="comment"]')
            comments = comments_el.get_text(strip=True) if comments_el else ""

            reposts_el = el.select_one('button[aria-label*="repost"]')
            reposts = reposts_el.get_text(strip=True) if reposts_el else ""

            images: List[str] = []
            for img in el.find_all("img"):
                src = img.get("src", "")
                if "media" in src and "profile" not in src and "logo" not in src:
                    images.append(src)

            posts.append({
                "urn": urn,
                "text": text[:2000],
                "timeText": time_text,
                "reactions": reactions,
                "comments": comments,
                "reposts": reposts,
                "images": images,
            })

        return posts

    async def extract_text_safe(
        self, selector: str, default: str = "", timeout: float = 2000
    ) -> str:
        return default

    async def fill(self, selector: str, value: str) -> None:
        self.recorded_calls.append(("fill", {"selector": selector, "value": value}))

    async def click(self, selector: str) -> None:
        self.recorded_calls.append(("click", {"selector": selector}))

    def locator(self, selector: str) -> Any:
        return self

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        return []

    async def bring_to_front(self) -> None:
        self.recorded_calls.append(("bring_to_front", {}))

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        self.recorded_calls.append(("add_cookies", {"cookies": cookies}))

    async def keyboard_press(self, key: str) -> None:
        self.keyboard_press_calls.append(key)
        self.recorded_calls.append(("keyboard_press", {"key": key}))


# ===========================================================================
# 1. Production-Path Characterization Tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_posts_scraper_production_path(html_fixtures_dir: Path):
    """
    End-to-end production path test for CompanyPostsScraper.
    Executes full acquisition via BrowserPort -> pure parser -> Post domain models.
    """
    fixture_path = html_fixtures_dir / "feed_posts_update.html"
    browser = PostFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/company/microsoft/posts/"
    )
    scraper = CompanyPostsScraper(browser)

    posts = await scraper.scrape("https://www.linkedin.com/company/microsoft", limit=5)

    assert len(posts) >= 4

    # Post 1: Full structured update (Microsoft)
    p1 = next((p for p in posts if p.urn == "urn:li:activity:7100000000000000001"), None)
    assert p1 is not None
    assert p1.urn == "urn:li:activity:7100000000000000001"
    assert p1.linkedin_url == "https://www.linkedin.com/feed/update/urn:li:activity:7100000000000000001/"
    assert "intelligent agent workflows" in (p1.text or "")
    assert p1.posted_date == "3d"
    assert p1.reactions_count == 1850
    assert p1.comments_count == 95
    assert p1.reposts_count == 42
    assert len(p1.image_urls) == 1
    assert "feedshare-shrink_800" in p1.image_urls[0]

    # Post 2: Alternative commentary selector (Acme Corporation)
    p2 = next((p for p in posts if p.urn == "urn:li:activity:7100000000000000002"), None)
    assert p2 is not None
    assert "benchmarking foundation models" in (p2.text or "")
    assert p2.posted_date == "2 weeks ago"
    assert p2.reactions_count == 520
    assert p2.comments_count == 18

    # Post 3: update-components-text (Global Tech Innovations)
    p3 = next((p for p in posts if p.urn == "urn:li:activity:7100000000000000003"), None)
    assert p3 is not None
    assert "Registration for our annual developer summit" in (p3.text or "")
    assert p3.posted_date == "Just now"

    # Post 4: Fallback nested container (Google LLC)
    p4 = next((p for p in posts if p.urn == "urn:li:activity:7100000000000000004"), None)
    assert p4 is not None
    assert "infrastructure team scaled throughput" in (p4.text or "")
    assert p4.posted_date == "5h"
    assert p4.reactions_count == 3400

    # Post 6: Repeated actor header handled generically without pollution
    p6 = next((p for p in posts if p.urn == "urn:li:activity:7100000000000000006"), None)
    assert p6 is not None
    assert "Announcing our Q3 product roadmap" in (p6.text or "")
    assert p6.reactions_count == 780
    assert p6.comments_count == 45
    assert p6.reposts_count == 12

    # Verify BrowserPort recording calls
    called_methods = {call[0] for call in browser.recorded_calls}
    assert "goto" in called_methods
    assert "wait_for_load_state" in called_methods
    assert "wait_for_timeout" in called_methods
    assert "evaluate" in called_methods


# ===========================================================================
# 2. Generic Actor Handling & Hardcoded Filter Removal Tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generic_actor_handling_multiple_companies():
    """
    Verify that posts from diverse companies (Microsoft, Acme, OpenAI, Google)
    are all parsed identically without company-specific branches.
    """
    sample_feed_data = [
        {
            "urn": "urn:li:activity:100",
            "text": "Microsoft announcement regarding cloud services infrastructure update.",
            "timeText": "1d",
            "reactions": "100",
            "comments": "10",
            "reposts": "5",
            "images": [],
        },
        {
            "urn": "urn:li:activity:200",
            "text": "Acme Corporation product launch and quarterly financial updates.",
            "timeText": "2d",
            "reactions": "200",
            "comments": "20",
            "reposts": "8",
            "images": [],
        },
        {
            "urn": "urn:li:activity:300",
            "text": "OpenAI research publication on autonomous code generation capabilities.",
            "timeText": "3d",
            "reactions": "300",
            "comments": "30",
            "reposts": "15",
            "images": [],
        },
        {
            "urn": "urn:li:activity:400",
            "text": "Google AI advances in multi-modal foundational architectures.",
            "timeText": "4d",
            "reactions": "400",
            "comments": "40",
            "reposts": "25",
            "images": [],
        },
    ]

    posts = parse_company_posts(sample_feed_data)
    assert len(posts) == 4
    assert all(isinstance(p, Post) for p in posts)
    assert posts[0].urn == "urn:li:activity:100"
    assert posts[1].urn == "urn:li:activity:200"
    assert posts[2].urn == "urn:li:activity:300"
    assert posts[3].urn == "urn:li:activity:400"


@pytest.mark.unit
def test_no_hardcoded_company_names_in_production_scraper():
    """
    Verify AST and source code of scrapers/company/posts.py contain
    zero hardcoded company filter strings (e.g. Microsoft, Google, OpenAI, Amazon).
    """
    scraper_path = (
        Path(__file__).resolve().parents[2]
        / "linkedin_scraper"
        / "scrapers"
        / "company"
        / "posts.py"
    )
    code = scraper_path.read_text(encoding="utf-8")

    forbidden_company_tokens = ["Microsoft", "Google", "Amazon", "OpenAI", "Acme"]
    for token in forbidden_company_tokens:
        # Ignore comments or docstrings if any, check in actual code lines
        lines = [
            line
            for line in code.splitlines()
            if not line.strip().startswith(("#", '"""', "'''", "*"))
        ]
        active_code = "\n".join(lines)
        assert token not in active_code, (
            f"Found forbidden hardcoded company name '{token}' in production code: {scraper_path}"
        )


# ===========================================================================
# 3. Playwright Isolation & AST Leakage Gates
# ===========================================================================


@pytest.mark.unit
def test_company_posts_scraper_has_zero_playwright_leakage():
    """Verify scrapers/company/posts.py has zero direct Playwright imports or references."""
    scraper_path = (
        Path(__file__).resolve().parents[2]
        / "linkedin_scraper"
        / "scrapers"
        / "company"
        / "posts.py"
    )
    code = scraper_path.read_text(encoding="utf-8")
    tree = ast.parse(code)

    playwright_imports: List[str] = []
    page_refs: List[str] = []
    locator_refs: List[str] = []
    element_handle_refs: List[str] = []
    raw_page_refs: List[str] = []
    self_page_refs: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "playwright" in node.module:
                playwright_imports.append(node.module)
        elif isinstance(node, ast.Import):
            for n in node.names:
                if "playwright" in n.name:
                    playwright_imports.append(n.name)
        elif isinstance(node, ast.Name):
            if node.id == "Page":
                page_refs.append(node.id)
            elif node.id == "Locator":
                locator_refs.append(node.id)
            elif node.id == "ElementHandle":
                element_handle_refs.append(node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr == "raw_page":
                raw_page_refs.append(node.attr)
            if node.attr == "page" and isinstance(node.value, ast.Name) and node.value.id == "self":
                self_page_refs.append("self.page")

    assert len(playwright_imports) == 0, f"Found Playwright imports: {playwright_imports}"
    assert len(page_refs) == 0, f"Found Page references: {page_refs}"
    assert len(locator_refs) == 0, f"Found Locator references: {locator_refs}"
    assert len(element_handle_refs) == 0, f"Found ElementHandle references: {element_handle_refs}"
    assert len(raw_page_refs) == 0, f"Found raw_page references: {raw_page_refs}"
    assert len(self_page_refs) == 0, f"Found self.page references: {self_page_refs}"


@pytest.mark.unit
def test_posts_parser_purity():
    """Verify parsers/posts.py has zero browser, scraper, or Playwright dependencies."""
    parser_path = (
        Path(__file__).resolve().parents[2]
        / "linkedin_scraper"
        / "parsers"
        / "posts.py"
    )
    code = parser_path.read_text(encoding="utf-8")
    tree = ast.parse(code)

    forbidden_modules = ["playwright", "ports", "scrapers", "core.browser"]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for forbidden in forbidden_modules:
                assert forbidden not in node.module, (
                    f"Pure posts parser imports forbidden module: {node.module}"
                )
        elif isinstance(node, ast.Import):
            for n in node.names:
                for forbidden in forbidden_modules:
                    assert forbidden not in n.name, (
                        f"Pure posts parser imports forbidden module: {n.name}"
                    )


# ===========================================================================
# 4. Lazy-Loading, Scrolling, and Bounded Termination Tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lazy_loading_retry_loop_termination(fake_page_cls):
    """Verify _wait_for_posts_to_load executes retry attempts and triggers lazy load."""
    page = fake_page_cls(evaluate_results=[False, True])
    scraper = CompanyPostsScraper(page)
    trigger_mock = AsyncMock()
    scraper._trigger_lazy_load = trigger_mock

    await scraper._wait_for_posts_to_load()
    assert trigger_mock.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrolling_uses_keyboard_end():
    """Verify _scroll_for_more_posts calls browser.keyboard_press('End')."""
    browser = PostFixtureBrowser("<html></html>")
    scraper = CompanyPostsScraper(browser)

    await scraper._scroll_for_more_posts()

    assert "End" in browser.keyboard_press_calls
    assert any(c[0] == "keyboard_press" and c[1].get("key") == "End" for c in browser.recorded_calls)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_posts_bounded_by_limit_and_deduplication(monkeypatch, fake_page_cls):
    """Verify _scrape_posts halts once limit is reached and deduplicates existing URNs."""
    page = fake_page_cls()
    scraper = CompanyPostsScraper(page)
    monkeypatch.setattr(scraper, "navigate_and_wait", AsyncMock())
    monkeypatch.setattr(scraper, "_wait_for_posts_to_load", AsyncMock())

    # Return batches with duplicate URNs across scrolls
    batch1 = [
        Post(urn="urn:li:activity:1", text="First post commentary text content"),
        Post(urn="urn:li:activity:2", text="Second post commentary text content"),
    ]
    batch2 = [
        Post(urn="urn:li:activity:2", text="Second post duplicate commentary"),
        Post(urn="urn:li:activity:3", text="Third post commentary text content"),
        Post(urn="urn:li:activity:4", text="Fourth post commentary text content"),
    ]

    extract_mock = AsyncMock(side_effect=[batch1, batch2])
    monkeypatch.setattr(scraper, "_extract_posts_via_js", extract_mock)
    scroll_mock = AsyncMock()
    monkeypatch.setattr(scraper, "_scroll_for_more_posts", scroll_mock)

    posts = await scraper.scrape("https://www.linkedin.com/company/acme/", limit=3)

    assert len(posts) == 3
    assert [p.urn for p in posts] == [
        "urn:li:activity:1",
        "urn:li:activity:2",
        "urn:li:activity:3",
    ]


# ===========================================================================
# 5. Field Inventory & Model Verification
# ===========================================================================


@pytest.mark.unit
def test_post_model_field_inventory():
    """Verify Post model field definitions and defaults."""
    post = Post(
        linkedin_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
        urn="urn:li:activity:1",
        text="Sample post text",
        posted_date="3d",
        reactions_count=100,
        comments_count=10,
        reposts_count=5,
        image_urls=["https://example.com/img1.jpg"],
    )

    assert post.linkedin_url == "https://www.linkedin.com/feed/update/urn:li:activity:1/"
    assert post.urn == "urn:li:activity:1"
    assert post.text == "Sample post text"
    assert post.posted_date == "3d"
    assert post.reactions_count == 100
    assert post.comments_count == 10
    assert post.reposts_count == 5
    assert post.image_urls == ["https://example.com/img1.jpg"]
    assert post.video_url is None
    assert post.article_url is None


@pytest.mark.unit
def test_post_repr_formatting():
    """Verify __repr__ formats text preview and engagement metrics."""
    post = Post(
        urn="urn:li:activity:1",
        text="Short post",
        posted_date="2d",
        reactions_count=50,
        comments_count=5,
    )
    rep = repr(post)
    assert "Short post" in rep
    assert "2d" in rep
    assert "50" in rep
    assert "5" in rep


# ===========================================================================
# 6. Backward Compatibility Gate
# ===========================================================================


@pytest.mark.unit
def test_company_posts_scraper_initialization_compatibility(fake_page_cls):
    """Verify CompanyPostsScraper accepts positional and keyword arguments for page_or_browser."""
    page = fake_page_cls()

    # 1. Positional argument
    scraper1 = CompanyPostsScraper(page)
    assert scraper1.browser is not None

    # 2. Keyword argument (legacy 'page')
    scraper2 = CompanyPostsScraper(page=page)
    assert scraper2.browser is not None
