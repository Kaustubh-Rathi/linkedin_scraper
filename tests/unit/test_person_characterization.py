"""Characterization and deterministic production-path tests for Person extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from bs4 import BeautifulSoup, Tag

import pytest

from linkedin_scraper import Person, PersonScraper
from linkedin_scraper.scrapers.person.accomplishments import AccomplishmentsExtractor
from linkedin_scraper.scrapers.person.contacts import ContactsExtractor
from linkedin_scraper.scrapers.person.education import EducationExtractor
from linkedin_scraper.scrapers.person.experience import ExperienceExtractor
from linkedin_scraper.scrapers.person.interests import InterestsExtractor
from linkedin_scraper.scrapers.person.profile import ProfileExtractor

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html" / "person"


# ---------------------------------------------------------------------------
# Fixture DOM Parser & Test Browser Adapter
# ---------------------------------------------------------------------------


class FixtureLocator:
    """BeautifulSoup-backed Locator stand-in for deterministic DOM navigation."""

    def __init__(self, elements: Sequence[Tag | Any], browser: Optional[PersonFixtureBrowser] = None) -> None:
        self._elements = [e for e in elements if isinstance(e, Tag)]
        self._browser = browser

    @property
    def first(self) -> FixtureLocator:
        return FixtureLocator(self._elements[:1] if self._elements else [], self._browser)

    async def count(self) -> int:
        return len(self._elements)

    async def all(self) -> List[FixtureLocator]:
        return [FixtureLocator([el], self._browser) for el in self._elements]

    async def text_content(self, timeout: Optional[float] = None) -> Optional[str]:
        if not self._elements:
            return None
        return self._elements[0].get_text().strip()

    async def inner_text(self) -> str:
        if not self._elements:
            return ""
        return self._elements[0].get_text(separator="\n", strip=True)

    async def get_attribute(
        self, name: str, timeout: Optional[float] = None
    ) -> Optional[str]:
        if not self._elements:
            return None
        val = self._elements[0].get(name)
        if isinstance(val, list):
            return " ".join(val)
        return val

    async def is_visible(self, timeout: Optional[float] = None) -> bool:
        return len(self._elements) > 0

    async def click(self, timeout: Optional[float] = None) -> None:
        if self._browser and self._elements:
            elem = self._elements[0]
            # If this is a tab element, activate its tab name
            tab_name = elem.get("data-tab") or elem.get_text().strip()
            if tab_name:
                self._browser.active_tab = tab_name
        return None

    def locator(self, selector: str) -> FixtureLocator:
        if not self._elements:
            return FixtureLocator([], self._browser)

        results: List[Tag] = []
        for elem in self._elements:
            matched = self._query_element(elem, selector)
            for m in matched:
                if m not in results:
                    results.append(m)
        return FixtureLocator(results, self._browser)

    async def query_selector_all(self, selector: str) -> List[FixtureLocator]:
        return await self.locator(selector).all()

    def _query_element(self, elem: Tag, selector: str) -> List[Tag]:
        # Handle xpath=.. (parent navigation)
        if selector == "xpath=.." or selector == "xpath=parent::*":
            parent = elem.parent
            return [parent] if isinstance(parent, Tag) else []

        if selector.startswith("xpath=ancestor::"):
            curr = elem.parent
            while curr and isinstance(curr, Tag):
                if curr.name == "section" or "tablist" in (curr.get("role", "") or ""):
                    return [curr]
                curr = curr.parent
            return [elem.parent] if isinstance(elem.parent, Tag) else []

        # Handle text selector: text="value"
        if selector.startswith('text="') and selector.endswith('"'):
            target_text = selector[6:-1]
            return elem.find_all(string=re.compile(re.escape(target_text)))

        # Handle :has-text("...")
        if ":has-text(" in selector:
            parts = selector.split(":has-text(")
            tag_name = parts[0].strip() or None
            text_match = parts[1].rstrip(")").strip('"').strip("'")
            candidates = elem.select(tag_name) if tag_name else elem.find_all()
            return [c for c in candidates if isinstance(c, Tag) and text_match in c.get_text()]

        # Handle tabpanel filtering when active tab is set
        if selector == '[role="tabpanel"]' or selector == '[role="tabpanel"], tabpanel':
            panels = elem.select('[role="tabpanel"]')
            if self._browser and self._browser.active_tab:
                matched_panels = [p for p in panels if p.get("data-tabpanel", "").lower() == self._browser.active_tab.lower()]
                if matched_panels:
                    return matched_panels
            return panels

        # Handle direct child selector > li
        if selector.strip().startswith(">"):
            tag_name = selector.strip().lstrip(">").strip()
            return [c for c in elem.find_all(tag_name, recursive=False) if isinstance(c, Tag)]

        # Standard CSS selector
        try:
            return elem.select(selector)
        except Exception:
            return []


class PersonFixtureBrowser:
    """
    Deterministic BrowserPort stand-in serving static HTML fixtures for person scraping.
    """

    def __init__(self, base_url: str = "https://www.linkedin.com/in/alex-morgan/") -> None:
        self.url = base_url
        self.active_tab: Optional[str] = "Companies"
        self._fixtures: Dict[str, str] = {}
        self._current_soup: BeautifulSoup = BeautifulSoup("<html><body></body></html>", "html.parser")
        self.goto_history: List[str] = []
        self._load_fixtures()
        self._set_page_for_url(base_url)

    def _load_fixtures(self) -> None:
        self._fixtures["profile"] = (FIXTURES_DIR / "person_profile.html").read_text(encoding="utf-8")
        self._fixtures["experience"] = (FIXTURES_DIR / "person_experience.html").read_text(encoding="utf-8")
        self._fixtures["education"] = (FIXTURES_DIR / "person_education.html").read_text(encoding="utf-8")
        self._fixtures["contacts"] = (FIXTURES_DIR / "person_contacts_dialog.html").read_text(encoding="utf-8")
        self._fixtures["accomplishments"] = (FIXTURES_DIR / "person_accomplishments.html").read_text(encoding="utf-8")
        self._fixtures["interests"] = (FIXTURES_DIR / "person_interests.html").read_text(encoding="utf-8")

    def _set_page_for_url(self, url: str) -> None:
        if "details/experience" in url:
            self._current_soup = BeautifulSoup(self._fixtures["experience"], "html.parser")
        elif "details/education" in url:
            self._current_soup = BeautifulSoup(self._fixtures["education"], "html.parser")
        elif "overlay/contact-info" in url:
            self._current_soup = BeautifulSoup(self._fixtures["contacts"], "html.parser")
        elif "details/interests" in url:
            self._current_soup = BeautifulSoup(self._fixtures["interests"], "html.parser")
        elif "details/" in url:
            # Check which accomplishment category is requested
            category_match = re.search(r"details/([^/]+)/?", url)
            cat_name = category_match.group(1) if category_match else ""
            base_soup = BeautifulSoup(self._fixtures["accomplishments"], "html.parser")
            matched_section = base_soup.find("section", attrs={"data-category": cat_name})
            if matched_section:
                page_html = (
                    "<html><body><header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>"
                    f"<main>{matched_section}</main></body></html>"
                )
                self._current_soup = BeautifulSoup(page_html, "html.parser")
            else:
                empty_html = (
                    "<html><body><header><nav><a class='global-nav__primary-link' href='/feed'>Home</a></nav></header>"
                    "<main><div>Nothing to see for now</div></main></body></html>"
                )
                self._current_soup = BeautifulSoup(empty_html, "html.parser")
        else:
            self._current_soup = BeautifulSoup(self._fixtures["profile"], "html.parser")

    @property
    def raw_page(self) -> PersonFixtureBrowser:
        return self

    def locator(self, selector: str) -> FixtureLocator:
        root_tag = self._current_soup.find("html") or self._current_soup
        if isinstance(root_tag, Tag):
            return FixtureLocator([root_tag], self).locator(selector)
        return FixtureLocator([], self)

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 60000) -> None:
        self.url = url
        self.goto_history.append(url)
        self._set_page_for_url(url)

    async def wait_for_selector(
        self, selector: str, timeout: Optional[float] = None, state: Optional[str] = None
    ) -> None:
        return None

    async def wait_for_load_state(self, state: str = "load", timeout: Optional[float] = None) -> None:
        return None

    async def wait_for_timeout(self, timeout: float) -> None:
        return None

    async def bring_to_front(self) -> None:
        return None

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return None

    async def query_selector_all(self, selector: str) -> List[FixtureLocator]:
        return await self.locator(selector).all()

    async def extract_text_safe(self, selector: str, default: str = "", timeout: float = 2000) -> str:
        return await self.safe_extract_text(selector, default, timeout)

    async def safe_extract_text(self, selector: str, default: str = "", timeout: float = 2000) -> str:
        loc = self.locator(selector).first
        if await loc.count() > 0:
            text = await loc.text_content()
            return text.strip() if text else default
        return default

    async def get_attribute_safe(
        self, selector: str, attribute: str, default: str = "", timeout: float = 2000
    ) -> str:
        loc = self.locator(selector).first
        if await loc.count() > 0:
            val = await loc.get_attribute(attribute)
            return val if val is not None else default
        return default


# ---------------------------------------------------------------------------
# Section 8 Characterization Tests: Individual Section Extractors & Pure Parsers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_characterization_profile_extractor():
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)
    extractor = ProfileExtractor(scraper)

    name, location = await extractor.get_name_and_location()
    assert name == "Alex Morgan"
    assert location == "San Francisco Bay Area"

    open_to_work = await extractor.check_open_to_work()
    assert open_to_work is True

    about = await extractor.get_about()
    assert about is not None
    assert "Distributed systems engineer with 10+ years experience" in about
    assert "billions of requests daily" in about


@pytest.mark.asyncio
async def test_characterization_experience_extractor():
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)
    extractor = ExperienceExtractor(scraper)

    experiences = await extractor.get_experiences("https://www.linkedin.com/in/alex-morgan/")
    assert len(experiences) == 3

    # Normal position
    exp0 = experiences[0]
    assert exp0.position_title == "Staff Software Engineer"
    assert exp0.institution_name == "Acme Corp"
    assert exp0.linkedin_url == "https://www.linkedin.com/company/acme-corp/"
    assert exp0.from_date == "Jan 2022"
    assert exp0.to_date == "Present"
    assert exp0.duration == "2 yrs 8 mos"
    assert exp0.location == "San Francisco, California, United States"
    assert "10B+ daily messages" in (exp0.description or "")

    # Grouped position role 1
    exp1 = experiences[1]
    assert exp1.position_title == "Senior Backend Engineer"
    assert exp1.institution_name == "Global Tech Industries"
    assert exp1.linkedin_url == "https://www.linkedin.com/company/global-tech/"
    assert exp1.from_date == "Jun 2020"
    assert exp1.to_date == "Dec 2021"
    assert exp1.duration == "1 yr 7 mos"
    assert exp1.location == "Austin, Texas, United States"
    assert "$50M+ daily transactions" in (exp1.description or "")

    # Grouped position role 2
    exp2 = experiences[2]
    assert exp2.position_title == "Software Engineer"
    assert exp2.institution_name == "Global Tech Industries"
    assert exp2.linkedin_url == "https://www.linkedin.com/company/global-tech/"
    assert exp2.from_date == "Sep 2018"
    assert exp2.to_date == "May 2020"
    assert exp2.duration == "1 yr 9 mos"
    assert exp2.location == "Austin, Texas, United States"
    assert "Python and Go" in (exp2.description or "")


@pytest.mark.asyncio
async def test_characterization_education_extractor():
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)
    extractor = EducationExtractor(scraper)

    educations = await extractor.get_educations("https://www.linkedin.com/in/alex-morgan/")
    assert len(educations) == 2

    edu0 = educations[0]
    assert edu0.institution_name == "Stanford University"
    assert edu0.degree == "Master of Science - MS, Computer Science"
    assert edu0.from_date == "2016"
    assert edu0.to_date == "2018"
    assert edu0.linkedin_url == "https://www.linkedin.com/school/stanford-university/"
    assert "Grade: 3.95 GPA" in (edu0.description or "")
    assert "Stanford AI Lab" in (edu0.description or "")

    edu1 = educations[1]
    assert edu1.institution_name == "UC Berkeley"
    assert edu1.degree == "Bachelor of Science - BS, Electrical Engineering and Computer Science"
    assert edu1.from_date == "2012"
    assert edu1.to_date == "2016"
    assert edu1.linkedin_url == "https://www.linkedin.com/school/uc-berkeley/"
    assert "Grade: 3.88 GPA" in (edu1.description or "")
    assert "Eta Kappa Nu" in (edu1.description or "")


@pytest.mark.asyncio
async def test_characterization_contacts_extractor():
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)
    extractor = ContactsExtractor(scraper)

    contacts = await extractor.get_contacts("https://www.linkedin.com/in/alex-morgan/")
    types = {c.type: c.value for c in contacts}

    assert "email" in types
    assert types["email"] == "alex.morgan@example.com"

    assert "phone" in types
    assert types["phone"] == "+14155550199"

    assert "website" in types
    assert types["website"] == "https://alexdev.io"

    assert "github" in types
    assert types["github"] == "https://github.com/alexmorgan"

    assert "twitter" in types
    assert types["twitter"] == "https://twitter.com/alexmorgan_dev"

    assert "address" in types
    assert "100 Market St" in types["address"]

    # Verify deduplication: alexdev.io appeared twice in fixture, should only exist once in merged
    website_contacts = [c for c in contacts if c.value == "https://alexdev.io"]
    assert len(website_contacts) == 1


@pytest.mark.asyncio
async def test_characterization_accomplishments_extractor():
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)
    extractor = AccomplishmentsExtractor(scraper)

    accomplishments = await extractor.get_accomplishments("https://www.linkedin.com/in/alex-morgan/")
    assert len(accomplishments) >= 5

    by_title = {a.title: a for a in accomplishments}

    # Certification
    cert = by_title.get("AWS Certified Solutions Architect - Professional")
    assert cert is not None
    assert cert.category == "certification"
    assert cert.issuer == "Amazon Web Services"
    assert cert.issued_date == "Jan 2023"
    assert cert.credential_id == "AWS-987654321"
    assert cert.credential_url == "https://aws.amazon.com/verification/credential/AWS-987654321"
    # Gap check: Accomplishment.description is not extracted by current implementation
    assert cert.description is None

    # Publication
    pub = by_title.get("High-Throughput Stream Processing in Distributed Systems")
    assert pub is not None
    assert pub.category == "publication"
    assert pub.issuer == "IEEE Transactions on Software Engineering"
    assert pub.issued_date == "Mar 2022"

    # Project
    proj = by_title.get("OpenEventStream Engine")
    assert proj is not None
    assert proj.category == "project"
    assert proj.issued_date == "Jan 2023"

    # Language
    lang = by_title.get("English")
    assert lang is not None
    assert lang.category == "language"
    assert lang.issuer == "Native or bilingual proficiency"

    # Organization
    org = by_title.get("Association for Computing Machinery")
    assert org is not None
    assert org.category == "organization"
    assert org.issued_date == "2018"


@pytest.mark.asyncio
async def test_characterization_interests_extractor():
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)
    extractor = InterestsExtractor(scraper)

    interests = await extractor.get_interests("https://www.linkedin.com/in/alex-morgan/")
    assert len(interests) >= 2

    by_name = {i.name: i for i in interests}
    assert "Google" in by_name
    assert by_name["Google"].category == "company"
    assert by_name["Google"].linkedin_url == "https://www.linkedin.com/company/google"

    assert "Microsoft" in by_name
    assert by_name["Microsoft"].category == "company"
    assert by_name["Microsoft"].linkedin_url == "https://www.linkedin.com/company/microsoft"


# ---------------------------------------------------------------------------
# Section 7 & 8: Full Production Path Test (PersonScraper.scrape)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_production_person_scraper_path():
    """
    Exercise PersonScraper -> real extractors -> fixture-backed browser -> pure parsers -> Person model.
    Zero sub-extractor mocking. Real orchestration.
    """
    browser = PersonFixtureBrowser("https://www.linkedin.com/in/alex-morgan/")
    scraper = PersonScraper(browser)

    person = await scraper.scrape("https://www.linkedin.com/in/alex-morgan/")

    # 1. Profile Verification
    assert isinstance(person, Person)
    assert person.linkedin_url == "https://www.linkedin.com/in/alex-morgan/"
    assert person.name == "Alex Morgan"
    assert person.location == "San Francisco Bay Area"
    assert person.open_to_work is True
    assert person.about is not None
    assert "Distributed systems engineer" in person.about

    # 2. Experiences Verification
    assert len(person.experiences) == 3
    assert person.experiences[0].position_title == "Staff Software Engineer"
    assert person.experiences[0].institution_name == "Acme Corp"
    assert person.experiences[0].from_date == "Jan 2022"
    assert person.experiences[0].to_date == "Present"
    assert person.experiences[0].duration == "2 yrs 8 mos"
    assert person.experiences[0].location == "San Francisco, California, United States"

    assert person.experiences[1].position_title == "Senior Backend Engineer"
    assert person.experiences[1].institution_name == "Global Tech Industries"
    assert person.experiences[1].from_date == "Jun 2020"
    assert person.experiences[1].to_date == "Dec 2021"

    assert person.experiences[2].position_title == "Software Engineer"
    assert person.experiences[2].institution_name == "Global Tech Industries"
    assert person.experiences[2].from_date == "Sep 2018"
    assert person.experiences[2].to_date == "May 2020"

    # 3. Educations Verification
    assert len(person.educations) == 2
    assert person.educations[0].institution_name == "Stanford University"
    assert person.educations[0].degree == "Master of Science - MS, Computer Science"
    assert person.educations[0].from_date == "2016"
    assert person.educations[0].to_date == "2018"

    assert person.educations[1].institution_name == "UC Berkeley"
    assert person.educations[1].degree == "Bachelor of Science - BS, Electrical Engineering and Computer Science"
    assert person.educations[1].from_date == "2012"
    assert person.educations[1].to_date == "2016"

    # 4. Contacts Verification
    assert len(person.contacts) >= 5
    contact_types = {c.type for c in person.contacts}
    assert "email" in contact_types
    assert "phone" in contact_types
    assert "website" in contact_types
    assert "github" in contact_types
    assert "twitter" in contact_types

    # 5. Accomplishments Verification
    assert len(person.accomplishments) >= 5
    cert = next(a for a in person.accomplishments if a.title == "AWS Certified Solutions Architect - Professional")
    assert cert.category == "certification"
    assert cert.issuer == "Amazon Web Services"
    assert cert.credential_id == "AWS-987654321"

    # 6. Interests Verification
    assert len(person.interests) >= 2
    interest_names = {i.name for i in person.interests}
    assert "Google" in interest_names
    assert "Microsoft" in interest_names


# ---------------------------------------------------------------------------
# Section 18 & 19: AST Purity & Dependency Direction Gates
# ---------------------------------------------------------------------------


def test_parser_purity_ast_gate():
    """Verify zero browser/playwright/scraper dependencies in parsers package for person."""
    import ast

    parsers_dir = Path(__file__).resolve().parents[2] / "linkedin_scraper" / "parsers"
    person_parser_file = parsers_dir / "person.py"
    person_links_file = parsers_dir / "person_links.py"

    forbidden_modules = [
        "playwright",
        "linkedin_scraper.core.browser",
        "linkedin_scraper.ports.browser",
        "linkedin_scraper.scrapers",
        "scrapers",
    ]
    forbidden_calls = {
        "goto",
        "click",
        "locator",
        "evaluate",
        "query_selector",
        "screenshot",
    }

    for file_path in [person_parser_file, person_links_file]:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not (
                            alias.name == forbidden or alias.name.startswith(forbidden + ".")
                        ), f"Forbidden import {alias.name} in {file_path.name}:{node.lineno}"

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                # Check for relative imports to scrapers
                if node.level > 1 and "scrapers" in mod:
                    pytest.fail(f"Forbidden relative scrapers import in {file_path.name}:{node.lineno}")
                for forbidden in forbidden_modules:
                    assert not (
                        mod == forbidden or mod.startswith(forbidden + ".")
                    ), f"Forbidden import from {mod} in {file_path.name}:{node.lineno}"

            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in forbidden_calls:
                    pytest.fail(f"Forbidden call .{func.attr}() in {file_path.name}:{node.lineno}")
