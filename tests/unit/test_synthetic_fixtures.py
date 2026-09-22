"""
Synthetic HTML Fixture & Parser Robustness Tests (Agent 14).

Validates pure search parsers and search adapters against realistic synthetic HTML snapshots
representing DOM drift, whitespace variations, missing optional fields, malformed cards,
and post/feed update structures.
"""

from __future__ import annotations

import html.parser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.adapters.search.company_adapter import LinkedInCompanySearchAdapter
from linkedin_scraper.adapters.search.employee_adapter import LinkedInEmployeeSearchAdapter
from linkedin_scraper.adapters.search.job_adapter import LinkedInJobSearchAdapter
from linkedin_scraper.adapters.search.person_adapter import LinkedInPersonSearchAdapter
from linkedin_scraper.adapters.search.post_adapter import LinkedInPostSearchAdapter
from linkedin_scraper.parsers.posts import parse_company_posts
from linkedin_scraper.parsers.search import (
    parse_company_search_card,
    parse_employee_search_card,
    parse_job_search_card,
    parse_person_search_card,
    parse_post_search_card,
)
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.parsers.posts import (
    extract_time_from_text,
    parse_count,
)
from linkedin_scraper.search.queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
)


# ---------------------------------------------------------------------------
# Lightweight HTML DOM Parser using standard library html.parser
# ---------------------------------------------------------------------------


class ParsedNode:
    """A DOM element node parsed from synthetic HTML."""

    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional[ParsedNode] = None) -> None:
        self.tag = tag.lower()
        self.attrs = attrs
        self.parent = parent
        self.children: List[ParsedNode] = []
        self.text_parts: List[str] = []

    @property
    def full_text(self) -> str:
        parts: List[str] = []
        for p in self.text_parts:
            parts.append(p)
        for child in self.children:
            parts.append(child.full_text)
        return "".join(parts)


class SimpleHTMLTreeBuilder(html.parser.HTMLParser):
    """Builds a lightweight DOM tree from HTML string."""

    def __init__(self) -> None:
        super().__init__()
        self.root = ParsedNode("root", {})
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_dict = {k: v or "" for k, v in attrs}
        node = ParsedNode(tag, attr_dict, parent=self.current)
        self.current.children.append(node)
        self.current = node

    def handle_endtag(self, tag: str) -> None:
        if self.current.parent is not None:
            self.current = self.current.parent

    def handle_data(self, data: str) -> None:
        self.current.text_parts.append(data)


class SyntheticFixtureElement(ElementPort):
    """ElementPort implementation backed by a ParsedNode."""

    def __init__(self, node: ParsedNode) -> None:
        self._node = node

    async def text_content(self, timeout: float = 2000) -> Optional[str]:
        return self._node.full_text

    async def get_attribute(self, name: str, timeout: float = 2000) -> Optional[str]:
        return self._node.attrs.get(name)

    async def is_visible(self, timeout: float = 1000) -> bool:
        return True

    async def click(self) -> None:
        pass


class SyntheticFixtureBrowser(BrowserPort):
    """
    BrowserPort implementation that reads synthetic HTML fixtures from disk
    and evaluates selectors deterministically against parsed HTML elements.
    """

    def __init__(self, html_content: str, current_url: str = "https://www.linkedin.com/search/results/all/") -> None:
        self._html = html_content
        self._url = current_url
        self.goto_calls: List[Dict[str, Any]] = []
        self.evaluate_calls: List[str] = []

        parser = SimpleHTMLTreeBuilder()
        parser.feed(html_content)
        self._root = parser.root

    @classmethod
    def from_fixture_file(cls, path: Path, current_url: str) -> SyntheticFixtureBrowser:
        content = path.read_text(encoding="utf-8")
        return cls(content, current_url=current_url)

    @property
    def url(self) -> str:
        return self._url

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: float = 60000) -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        if not any(k in self._url for k in ("login", "authwall", "checkpoint")):
            self._url = url

    async def wait_for_selector(self, selector: str, timeout: float = 5000, state: str = "visible") -> None:
        elements = await self.query_selector_all(selector)
        if not elements:
            raise TimeoutError(f"Selector '{selector}' not found in fixture DOM")

    async def wait_for_load_state(self, state: str = "domcontentloaded", timeout: float = 30000) -> None:
        pass

    async def wait_for_url(self, predicate_or_url: Any, timeout: float = 30000) -> None:
        pass

    async def wait_for_timeout(self, timeout: float) -> None:
        pass

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        self.evaluate_calls.append(expression)
        return None

    async def extract_text_safe(self, selector: str, default: str = "", timeout: float = 2000) -> str:
        elements = await self.query_selector_all(selector)
        if elements:
            text = await elements[0].text_content()
            return text or default
        return default

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def click(self, selector: str) -> None:
        pass

    def locator(self, selector: str) -> Any:
        mock = AsyncMock()
        mock.count = AsyncMock(return_value=0)
        mock.text_content = AsyncMock(return_value="")
        return mock

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        """Match selectors such as `a[href*="/in/"]` or `a[href*="/feed/update/"], a[href*="/posts/"]`."""
        sub_selectors = [s.strip() for s in selector.split(",")]
        matched_nodes: List[ParsedNode] = []
        seen_nodes: Set[ParsedNode] = set()

        def match_single_selector(node: ParsedNode, sel: str) -> bool:
            if node.tag != "a":
                return False
            href = node.attrs.get("href", "")
            if "href*=" in sel:
                target = sel.split("href*=")[1].strip("]\"' ")
                return target in href
            return False

        def traverse(node: ParsedNode) -> None:
            for sel in sub_selectors:
                if match_single_selector(node, sel):
                    if node not in seen_nodes:
                        seen_nodes.add(node)
                        matched_nodes.append(node)
                    break
            for child in node.children:
                traverse(child)

        traverse(self._root)
        return [SyntheticFixtureElement(n) for n in matched_nodes]

    async def bring_to_front(self) -> None:
        pass

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        pass

    async def keyboard_press(self, key: str) -> None:
        pass


# ===========================================================================
# 1. Person Search Fixture & Parser Robustness
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_search_adapter_with_synthetic_html_fixture(html_fixtures_dir: Path):
    """Verify Person search adapter against realistic HTML fixture containing drift variations."""
    fixture_path = html_fixtures_dir / "search_people_results.html"
    browser = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/people/"
    )
    adapter = LinkedInPersonSearchAdapter(browser)

    page = await adapter.search_people(PersonSearchQuery(keywords="engineer", limit=10))

    assert len(page.items) >= 4

    # 1. Clean standard profile
    satya = next((p for p in page.items if "satyanadella" in p.linkedin_url), None)
    assert satya is not None
    assert satya.name == "Satya Nadella"
    assert satya.linkedin_url == "https://www.linkedin.com/in/satyanadella/"

    # 2. Whitespace / badge variation
    alice = next((p for p in page.items if "alicesmith" in p.linkedin_url), None)
    assert alice is not None
    assert "Alice Smith" in alice.name
    assert alice.linkedin_url == "https://www.linkedin.com/in/alicesmith/"

    # 3. Missing optional fields
    bob = next((p for p in page.items if "bob-jones" in p.linkedin_url), None)
    assert bob is not None
    assert bob.name == "Bob Jones"
    assert bob.linkedin_url == "https://www.linkedin.com/in/bob-jones/"

    # 4. Alternative layout
    carol = next((p for p in page.items if "carol-danvers" in p.linkedin_url), None)
    assert carol is not None
    assert carol.name == "Carol Danvers"
    assert carol.linkedin_url == "https://www.linkedin.com/in/carol-danvers/"


@pytest.mark.unit
def test_pure_person_search_card_drift_variations():
    """Test pure parse_person_search_card on dirty/drifted dictionary inputs."""
    # Extra whitespace in name and URL
    card1 = parse_person_search_card({
        "name": "   \n John Doe \t  ",
        "url": "  https://www.linkedin.com/in/johndoe/  ",
        "headline": "  Principal Architect \n  ",
        "location": " San Francisco, CA ",
        "company": " TechCorp ",
    })
    assert card1.name == "John Doe"
    assert card1.linkedin_url == "https://www.linkedin.com/in/johndoe/"
    assert card1.headline == "Principal Architect"
    assert card1.location == "San Francisco, CA"
    assert card1.current_company == "TechCorp"

    # Missing optional fields return None
    card2 = parse_person_search_card({
        "name": "Jane Smith",
        "linkedin_url": "https://www.linkedin.com/in/janesmith",
    })
    assert card2.headline is None
    assert card2.location is None
    assert card2.current_company is None

    # Blank whitespace optional fields normalize to None
    card3 = parse_person_search_card({
        "name": "Alex",
        "linkedin_url": "https://www.linkedin.com/in/alex",
        "headline": "   ",
        "location": "\t\n",
        "current_company": "",
    })
    assert card3.headline is None
    assert card3.location is None
    assert card3.current_company is None

    # Missing required name raises ValueError
    with pytest.raises(ValueError, match="missing required field 'name'"):
        parse_person_search_card({"linkedin_url": "https://www.linkedin.com/in/alex", "name": "  "})

    # Missing required URL raises ValueError
    with pytest.raises(ValueError, match="missing required field 'linkedin_url'"):
        parse_person_search_card({"name": "Alex", "linkedin_url": ""})


# ===========================================================================
# 2. Company Search Fixture & Parser Robustness
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_search_adapter_with_synthetic_html_fixture(html_fixtures_dir: Path):
    """Verify Company search adapter against realistic HTML fixture."""
    fixture_path = html_fixtures_dir / "search_companies_results.html"
    browser = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/companies/"
    )
    adapter = LinkedInCompanySearchAdapter(browser)

    page = await adapter.search_companies(CompanySearchQuery(keywords="tech", limit=10))

    assert len(page.items) >= 4

    # 1. Standard company
    msft = next((c for c in page.items if "microsoft" in c.linkedin_url), None)
    assert msft is not None
    assert msft.name == "Microsoft"
    assert msft.linkedin_url == "https://www.linkedin.com/company/microsoft/"

    # 2. Formatted followers
    openai = next((c for c in page.items if "openai" in c.linkedin_url), None)
    assert openai is not None
    assert openai.name == "OpenAI"

    # 3. Verified badge with whitespace
    google = next((c for c in page.items if "google" in c.linkedin_url), None)
    assert google is not None
    assert "Google" in google.name

    # 4. Tracking params stripped
    anthropic = next((c for c in page.items if "anthropic-ai" in c.linkedin_url), None)
    assert anthropic is not None
    assert anthropic.linkedin_url == "https://www.linkedin.com/company/anthropic-ai/"


@pytest.mark.unit
def test_pure_company_search_card_drift_variations():
    """Test pure parse_company_search_card on follower count variations and missing fields."""
    # Standard follower number string
    c1 = parse_company_search_card({
        "name": "Acme Inc",
        "url": "https://www.linkedin.com/company/acme",
        "followers": "21,450,000 followers",
    })
    assert c1.followers_count == 21450000

    # 4.2M follower format
    c2 = parse_company_search_card({
        "name": "AI Lab",
        "linkedin_url": "https://www.linkedin.com/company/ailab",
        "followers_count": "4.2M followers",
    })
    assert c2.followers_count == 4200000

    # 750k follower format
    c3 = parse_company_search_card({
        "name": "Cloud Co",
        "linkedin_url": "https://www.linkedin.com/company/cloudco",
        "followers_count": "750k followers",
    })
    assert c3.followers_count == 750000

    # Missing follower field
    c4 = parse_company_search_card({
        "name": "Stealth Co",
        "linkedin_url": "https://www.linkedin.com/company/stealth",
        "followers_count": None,
    })
    assert c4.followers_count is None

    # Missing required name raises ValueError
    with pytest.raises(ValueError, match="missing required field 'name'"):
        parse_company_search_card({"url": "https://www.linkedin.com/company/stealth", "name": None})

    # Missing required URL raises ValueError
    with pytest.raises(ValueError, match="missing required field 'linkedin_url'"):
        parse_company_search_card({"name": "Stealth", "url": "   "})


# ===========================================================================
# 3. Job Search Fixture & Parser Robustness
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_adapter_with_synthetic_html_fixture(html_fixtures_dir: Path):
    """Verify Job search adapter against realistic HTML fixture."""
    fixture_path = html_fixtures_dir / "search_jobs_results.html"
    browser = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/jobs/search/"
    )
    adapter = LinkedInJobSearchAdapter(browser)

    page = await adapter.search_jobs(JobSearchQuery(keywords="python", limit=10))

    assert len(page.items) >= 3

    # 1. Standard job with full fields
    j1 = next((j for j in page.items if "3891234567" in j.linkedin_url), None)
    assert j1 is not None
    assert "Senior Python Engineer" in j1.job_title
    assert j1.linkedin_url == "https://www.linkedin.com/jobs/view/3891234567/"

    # 2. Job with 1 week ago posted date
    j2 = next((j for j in page.items if "3891234568" in j.linkedin_url), None)
    assert j2 is not None
    assert "Lead Systems Architect" in j2.job_title

    # 3. Job with badges and tracking params
    j3 = next((j for j in page.items if "3891234569" in j.linkedin_url), None)
    assert j3 is not None
    assert "Staff Machine Learning Engineer" in j3.job_title
    assert j3.linkedin_url == "https://www.linkedin.com/jobs/view/3891234569/"


@pytest.mark.unit
def test_pure_job_search_card_drift_variations():
    """Test pure parse_job_search_card on edge cases and field mappings."""
    j1 = parse_job_search_card({
        "title": "  Senior Backend Engineer \n ",
        "url": "https://www.linkedin.com/jobs/view/12345/?trk=abc",
        "company": "  Google ",
        "location": " Mountain View, CA ",
        "posted_at": " 3 days ago ",
        "easy_apply": True,
    })
    assert j1.job_title == "Senior Backend Engineer"
    assert j1.company_name == "Google"
    assert j1.location == "Mountain View, CA"
    assert j1.posted_date == "3 days ago"
    assert j1.easy_apply is True

    # Missing optional fields
    j2 = parse_job_search_card({
        "job_title": "Security Researcher",
        "linkedin_url": "https://www.linkedin.com/jobs/view/999/",
    })
    assert j2.company_name is None
    assert j2.location is None
    assert j2.posted_date is None
    assert j2.easy_apply is False

    # Missing required title
    with pytest.raises(ValueError, match="missing required field 'job_title'"):
        parse_job_search_card({"job_title": "", "linkedin_url": "https://linkedin.com/jobs/view/1"})

    # Missing required URL
    with pytest.raises(ValueError, match="missing required field 'linkedin_url'"):
        parse_job_search_card({"job_title": "Engineer", "linkedin_url": None})


# ===========================================================================
# 4. Post Search Fixture & Parser Robustness
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_search_adapter_with_synthetic_html_fixture(html_fixtures_dir: Path):
    """Verify Post search adapter against realistic HTML fixture."""
    fixture_path = html_fixtures_dir / "search_posts_results.html"
    browser = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/content/"
    )
    adapter = LinkedInPostSearchAdapter(browser)

    page = await adapter.search_posts(PostSearchQuery(keywords="ai", limit=10))

    assert len(page.items) >= 3

    # 1. Standard /feed/update/ link
    p1 = next((p for p in page.items if p.linkedin_url and "7198765432100000001" in p.linkedin_url), None)
    assert p1 is not None
    assert p1.linkedin_url == "https://www.linkedin.com/feed/update/urn:li:activity:7198765432100000001/"
    assert "Thrilled to share" in (p1.text_snippet or "")

    # 2. /posts/ link format
    p2 = next((p for p in page.items if p.linkedin_url and "7198765432100000002" in p.linkedin_url), None)
    assert p2 is not None
    assert p2.linkedin_url is not None and "elena-rostova" in p2.linkedin_url
    assert "open-sourced" in (p2.text_snippet or "")

    # 3. Deduplication of duplicate links within card
    urls = [p.linkedin_url for p in page.items]
    assert len(urls) == len(set(urls))



@pytest.mark.unit
def test_pure_post_search_card_drift_variations():
    """Test pure parse_post_search_card on reaction formatting and field fallbacks."""
    # Reactions count string variants: '1,245 reactions', '1.5k', '500K', '10'
    p1 = parse_post_search_card({
        "linkedin_url": "https://www.linkedin.com/feed/update/urn:li:activity:123/",
        "author": "  Jane Doe  ",
        "headline": "  VP Engineering  ",
        "snippet": "  Exciting news!  ",
        "posted_at": " 2d • Edited ",
        "reactions": " 1,245 reactions ",
    })
    assert p1.author_name == "Jane Doe"
    assert p1.author_headline == "VP Engineering"
    assert p1.text_snippet == "Exciting news!"
    assert p1.posted_date == "2d • Edited"
    assert p1.reactions_count == 1245

    # Multiplier reaction formats (1.5k, 2M)
    p2 = parse_post_search_card({
        "url": "https://www.linkedin.com/posts/item-1/",
        "reactions_count": "1.5k",
    })
    assert p2.reactions_count == 1500

    p3 = parse_post_search_card({
        "url": "https://www.linkedin.com/posts/item-2/",
        "reactions_count": "2M",
    })
    assert p3.reactions_count == 2000000

    # Missing optional fields gracefully set to None
    p4 = parse_post_search_card({})
    assert p4.linkedin_url is None
    assert p4.author_name is None
    assert p4.author_headline is None
    assert p4.text_snippet is None
    assert p4.posted_date is None
    assert p4.reactions_count is None


# ===========================================================================
# 5. Employee Search Fixture & Parser Robustness
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_employee_search_adapter_with_synthetic_html_fixture(html_fixtures_dir: Path):
    """Verify Employee search adapter against realistic HTML fixture."""
    fixture_path = html_fixtures_dir / "search_employees_results.html"
    browser = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/people/"
    )
    adapter = LinkedInEmployeeSearchAdapter(browser)

    page = await adapter.search_employees(
        EmployeeSearchQuery(company_identifier="microsoft", limit=10)
    )

    assert len(page.items) >= 3

    # 1. Clean employee
    e1 = next((e for e in page.items if "marcus-vance" in (e.linkedin_url or "")), None)
    assert e1 is not None
    assert e1.name == "Marcus Vance"
    assert e1.company_name == "microsoft"

    # 2. Whitespace employee
    e2 = next((e for e in page.items if "priya-patel" in (e.linkedin_url or "")), None)
    assert e2 is not None
    assert "Priya Patel" in e2.name
    assert e2.company_name == "microsoft"

    # 3. Out of network member
    e3 = next((e for e in page.items if "ACoAAB555999" in (e.linkedin_url or "")), None)
    assert e3 is not None
    assert e3.name == "LinkedIn Member"


@pytest.mark.unit
def test_pure_employee_search_card_drift_variations():
    """Test pure parse_employee_search_card on field fallbacks and missing fields."""
    e1 = parse_employee_search_card({
        "name": "   David Miller  ",
        "url": " https://www.linkedin.com/in/dmiller/ ",
        "title": " Lead Architect ",
        "company": " Acme ",
    })
    assert e1.name == "David Miller"
    assert e1.linkedin_url == "https://www.linkedin.com/in/dmiller/"
    assert e1.designation == "Lead Architect"
    assert e1.company_name == "Acme"

    # Missing required name raises ValueError
    with pytest.raises(ValueError, match="missing required field 'name'"):
        parse_employee_search_card({"designation": "Manager", "company": "Acme"})


# ===========================================================================
# 6. Post / Feed Update Structures (Company Posts Parsing)
# ===========================================================================


@pytest.mark.unit
def test_company_posts_parser_with_synthetic_feed_data():
    """Verify company post parsing helpers and post_from_js_data on rich feed structures."""
    feed_data = [
        {
            "urn": "urn:li:activity:7100000000000000001",
            "text": "We are excited to introduce our new open platform capabilities for intelligent agent workflows.",
            "timeText": "3d • Edited",
            "reactions": "1,850 reactions",
            "comments": "95 comments",
            "reposts": "42 reposts",
            "images": [
                "https://media.licdn.com/dms/image/v2/D5622AQ/feedshare-shrink_800/0/1234567?e=123"
            ],
        },
        {
            "urn": "urn:li:activity:7100000000000000002",
            "text": "Deep dive into our latest research benchmarking foundation models across code reasoning.",
            "timeText": "2 weeks ago • Visible to anyone",
            "reactions": "520 reactions",
            "comments": "18 comments",
            "reposts": "5 reposts",
            "images": [],
        },
        {
            "urn": "urn:li:activity:7100000000000000003",
            "text": "Registration for our annual developer summit is now officially open!",
            "timeText": "Just now • Published",
            "reactions": "0",
            "comments": "0",
            "reposts": "0",
            "images": [],
        },
    ]

    posts = parse_company_posts(feed_data)

    assert len(posts) == 3

    # Post 1 assertions
    assert posts[0].urn == "urn:li:activity:7100000000000000001"
    assert posts[0].linkedin_url == "https://www.linkedin.com/feed/update/urn:li:activity:7100000000000000001/"
    assert posts[0].posted_date == "3d"
    assert posts[0].reactions_count == 1850
    assert posts[0].comments_count == 95
    assert posts[0].reposts_count == 42
    assert len(posts[0].image_urls) == 1

    # Post 2 assertions (relative time "2 weeks ago")
    assert posts[1].urn == "urn:li:activity:7100000000000000002"
    assert posts[1].posted_date == "2 weeks ago"
    assert posts[1].reactions_count == 520
    assert posts[1].comments_count == 18
    assert posts[1].reposts_count == 5

    # Post 3 assertions ("Just now" bullet split)
    assert posts[2].urn == "urn:li:activity:7100000000000000003"
    assert posts[2].posted_date == "Just now"


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw_time,expected",
    [
        ("3d • Edited", "3d"),
        ("5h", "5h"),
        ("10m • Public", "10m"),
        ("2 weeks ago • Visible to anyone", "2 weeks ago"),
        ("1 month ago", "1 month ago"),
        ("3 years ago", "3 years ago"),
        ("Just now • Shared", "Just now"),
        ("Moments ago \u2022 Anyone", "Moments ago"),
        ("", None),
        (None, None),
    ],
)
def test_extract_time_from_text_robustness(raw_time: Optional[str], expected: Optional[str]):
    """Test extract_time_from_text handles diverse real-world LinkedIn time strings."""
    assert extract_time_from_text(raw_time or "") == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw_count,expected",
    [
        ("1,850 reactions", 1850),
        ("520 comments", 520),
        ("42 reposts", 42),
        ("10,000+", 10000),
        ("0", 0),
        ("no count", None),
        ("", None),
    ],
)
def test_parse_count_robustness(raw_count: str, expected: Optional[int]):
    """Test parse_count handles comma numbers, trailing text, and non-digit cases."""
    assert parse_count(raw_count) == expected


@pytest.mark.unit
def test_parse_company_posts_skips_malformed_entries():
    """Ensure parse_company_posts ignores dictionaries missing urn or text."""
    invalid_data = [
        {"urn": "urn:li:activity:123"},  # missing text
        {"text": "Some text without URN"},  # missing urn
        {"other": "random field"},
    ]
    assert parse_company_posts(invalid_data) == []


# ===========================================================================
# 7. Malformed & Edge Cases Fixture Verification
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_malformed_and_edge_cases_fixture(html_fixtures_dir: Path):
    """
    Verify all search adapters against search_malformed_and_edge_cases.html.
    Ensures invalid hrefs, non-matching links, and empty anchors are cleanly skipped,
    while valid cards with unusual attributes or whitespace are correctly extracted.
    """
    fixture_path = html_fixtures_dir / "search_malformed_and_edge_cases.html"

    # Person adapter against edge cases fixture
    browser_person = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/people/"
    )
    person_adapter = LinkedInPersonSearchAdapter(browser_person)
    person_page = await person_adapter.search_people(PersonSearchQuery(keywords="test", limit=10))

    # Should extract valid persons and skip empty href/fragment-only
    person_urls = [p.linkedin_url for p in person_page.items]
    assert "https://www.linkedin.com/in/john-doe-123456/" in person_urls
    assert "https://www.linkedin.com/in/jane-smith-999/" in person_urls
    # Malformed card with empty name is skipped rather than fabricating a placeholder
    empty_p = next((p for p in person_page.items if "empty-name" in p.linkedin_url), None)
    assert empty_p is None

    # Company adapter against edge cases fixture
    browser_co = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/companies/"
    )
    co_adapter = LinkedInCompanySearchAdapter(browser_co)
    co_page = await co_adapter.search_companies(CompanySearchQuery(keywords="test", limit=10))

    co_urls = [c.linkedin_url for c in co_page.items]
    assert "https://www.linkedin.com/company/mega-corp-inc/" in co_urls

    # Job adapter against edge cases fixture
    browser_job = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/jobs/search/"
    )
    job_adapter = LinkedInJobSearchAdapter(browser_job)
    job_page = await job_adapter.search_jobs(JobSearchQuery(keywords="test", limit=10))

    job_urls = [j.linkedin_url for j in job_page.items]
    assert "https://www.linkedin.com/jobs/view/9988776655/" in job_urls
    # Job link with missing/empty title is strictly skipped
    empty_job = next((j for j in job_page.items if "1122334455" in j.linkedin_url), None)
    assert empty_job is None

    # Post adapter against edge cases fixture
    browser_post = SyntheticFixtureBrowser.from_fixture_file(
        fixture_path, current_url="https://www.linkedin.com/search/results/content/"
    )
    post_adapter = LinkedInPostSearchAdapter(browser_post)
    post_page = await post_adapter.search_posts(PostSearchQuery(keywords="test", limit=10))

    post_urls = [p.linkedin_url for p in post_page.items if p.linkedin_url]
    assert any("8888777766665555444" in u for u in post_urls)
    assert any("8888777766665555445" in u for u in post_urls)

