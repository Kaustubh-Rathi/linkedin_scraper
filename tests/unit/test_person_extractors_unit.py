"""Unit tests for person section extractors."""

import pytest

from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from linkedin_scraper.models import Education, Experience
from linkedin_scraper.scrapers.person.accomplishments import AccomplishmentsExtractor
from linkedin_scraper.scrapers.person.contacts import ContactsExtractor
from linkedin_scraper.scrapers.person.education import EducationExtractor
from linkedin_scraper.scrapers.person.experience import ExperienceExtractor
from linkedin_scraper.scrapers.person.interests import InterestsExtractor
from linkedin_scraper.scrapers.person.profile import ProfileExtractor
from linkedin_scraper.scrapers.person.scraper import PersonScraper


# ---------------------------------------------------------------------------
# InterestsExtractor
# ---------------------------------------------------------------------------


class MockElement:
    def __init__(self, text="", href=None, children=None):
        self._text = text
        self._href = href
        self._children = children or []

    async def text_content(self, timeout=2000):
        return self._text

    async def inner_text(self):
        return self._text

    async def get_attribute(self, name, timeout=2000):
        if name == "href":
            return self._href
        if name == "title":
            return self._text
        return None

    async def click(self):
        pass

    async def query_selector_all(self, selector):
        return self._children


class MockBrowserForPerson:
    def __init__(self, url="https://www.linkedin.com/in/test/", elements_map=None, text_safe_map=None):
        self.url = url
        self._elements_map = elements_map or {}
        self._text_safe_map = text_safe_map or {}
        self.goto_calls = []

    async def goto(self, url, **kw):
        self.goto_calls.append(url)

    async def wait_for_load_state(self, *a, **kw):
        pass

    async def wait_for_selector(self, *a, **kw):
        pass

    async def wait_for_timeout(self, *a, **kw):
        pass

    async def evaluate(self, script, arg=None):
        return "complete"

    async def query_selector_all(self, selector):
        if "tabpanel" in selector:
            return self._elements_map.get("tabpanel", [])
        if "tab" in selector:
            return self._elements_map.get("tab", [])
        for k, v in self._elements_map.items():
            if k in selector or selector in k:
                return v
        return []

    async def extract_text_safe(self, selector, default="", timeout=2000):
        return self._text_safe_map.get(selector, default)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interests_extractor_tab_flow():
    link_el = MockElement(text="Microsoft", href="https://www.linkedin.com/company/microsoft/")
    span_el = MockElement(text="Microsoft")
    item_el = MockElement(text="Microsoft", href="https://www.linkedin.com/company/microsoft/", children=[link_el, span_el])
    panel_el = MockElement(text="Companies", children=[item_el])
    tab_el = MockElement(text="Companies")

    browser = MockBrowserForPerson(
        elements_map={
            "tab": [tab_el],
            "tabpanel": [panel_el],
            "li": [item_el],
            "a": [link_el],
            "span": [span_el],
        }
    )

    extractor = InterestsExtractor(browser)
    interests = await extractor.get_interests("https://www.linkedin.com/in/test/")
    assert len(interests) == 1
    assert interests[0].name == "Microsoft"
    assert interests[0].category == "company"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interests_extractor_re_raises_auth_error():
    browser = MockBrowserForPerson()

    async def raise_auth(sel):
        raise AuthenticationError("Auth failed")

    browser.query_selector_all = raise_auth
    extractor = InterestsExtractor(browser)
    with pytest.raises(AuthenticationError):
        await extractor.get_interests("https://www.linkedin.com/in/test/")


# ---------------------------------------------------------------------------
# AccomplishmentsExtractor
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_accomplishments_extractor_re_raises_rate_limit():
    browser = MockBrowserForPerson()

    async def raise_rate(url, **kw):
        raise RateLimitError("Rate limit encountered")

    browser.goto = raise_rate
    extractor = AccomplishmentsExtractor(browser)
    with pytest.raises(RateLimitError):
        await extractor.get_accomplishments("https://www.linkedin.com/in/test/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_accomplishments_extractor_skips_empty():
    nothing_el = MockElement(text="Nothing to see for now")
    browser = MockBrowserForPerson(elements_map={"Nothing to see": [nothing_el]})

    extractor = AccomplishmentsExtractor(browser)
    accomplishments = await extractor.get_accomplishments("https://www.linkedin.com/in/test/")
    assert accomplishments == []


# ---------------------------------------------------------------------------
# ContactsExtractor
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_plain_contact_value():
    text = "Phone\n+1 555-0100 (Mobile)"
    val = ContactsExtractor.plain_contact_value(text, "Phone")
    assert val == "+1 555-0100 (Mobile)"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_re_raises_auth_error():
    browser = MockBrowserForPerson()

    async def raise_auth(url, **kw):
        raise AuthenticationError("Auth error")

    browser.goto = raise_auth
    extractor = ContactsExtractor(browser)
    with pytest.raises(AuthenticationError):
        await extractor.get_contacts("https://www.linkedin.com/in/test/")


# ---------------------------------------------------------------------------
# EducationExtractor
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_education_extractor_re_raises_auth_error():
    browser = MockBrowserForPerson()

    async def raise_auth(url, **kw):
        raise AuthenticationError("Session expired")

    browser.goto = raise_auth
    extractor = EducationExtractor(browser)
    with pytest.raises(AuthenticationError):
        await extractor.get_educations("https://www.linkedin.com/in/test/")


@pytest.mark.unit
def test_education_extractor_dedupe():
    edus = [
        Education(institution_name="MIT", degree="B.S.", from_date="2016", to_date="2020"),
        Education(institution_name="MIT", degree="B.S.", from_date="2016", to_date="2020"),
        Education(institution_name="Stanford", degree="M.S.", from_date="2020", to_date="2022"),
    ]
    deduped = EducationExtractor._dedupe_educations(edus)
    assert len(deduped) == 2


# ---------------------------------------------------------------------------
# ExperienceExtractor
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_experience_extractor_re_raises_rate_limit():
    browser = MockBrowserForPerson()

    async def raise_rate(url, **kw):
        raise RateLimitError("Blocked")

    browser.goto = raise_rate
    extractor = ExperienceExtractor(browser)
    with pytest.raises(RateLimitError):
        await extractor.get_experiences("https://www.linkedin.com/in/test/")


@pytest.mark.unit
def test_experience_extractor_dedupe():
    exps = [
        Experience(institution_name="Acme", position_title="Engineer", from_date="2020", to_date="Present"),
        Experience(institution_name="Acme", position_title="Engineer", from_date="2020", to_date="Present", linkedin_url="https://www.linkedin.com/company/acme/"),
    ]
    deduped = ExperienceExtractor._dedupe_experiences(exps)
    assert len(deduped) == 1
    assert deduped[0].linkedin_url == "https://www.linkedin.com/company/acme/"


# ---------------------------------------------------------------------------
# ProfileExtractor
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_profile_extractor_name_and_location():
    browser = MockBrowserForPerson(text_safe_map={"h1": "Alex Smith"})

    extractor = ProfileExtractor(browser)
    name, location = await extractor.get_name_and_location()
    assert name == "Alex Smith"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_profile_extractor_open_to_work():
    img_el = MockElement(text="Alex Smith #OPEN_TO_WORK")

    browser = MockBrowserForPerson(elements_map={".pv-top-card-profile-picture": [img_el]})

    extractor = ProfileExtractor(browser)
    assert await extractor.check_open_to_work() is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_profile_extractor_get_about():
    section_el = MockElement(text="About\nExperienced distributed systems architect and builder.")
    browser = MockBrowserForPerson(elements_map={"section": [section_el]})

    extractor = ProfileExtractor(browser)
    about = await extractor.get_about()
    assert about is not None
    assert "Experienced distributed systems architect" in about


# ---------------------------------------------------------------------------
# PersonScraper Error Handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_propagates_authentication_error():
    browser = MockBrowserForPerson(url="https://www.linkedin.com/login")
    scraper = PersonScraper(browser)
    with pytest.raises(AuthenticationError):
        await scraper.scrape("https://www.linkedin.com/in/test-profile/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_wraps_unexpected_error():
    nav_link = MockElement(text="Home", href="/feed/")
    browser = MockBrowserForPerson(elements_map={".global-nav": [nav_link]})

    async def raise_crash(url, **kw):
        raise RuntimeError("Browser process disconnected")

    browser.goto = raise_crash
    scraper = PersonScraper(browser)
    with pytest.raises(ScrapingError, match="Failed to scrape person profile"):
        await scraper.scrape("https://www.linkedin.com/in/test-profile/")
