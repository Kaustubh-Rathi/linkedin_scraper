"""Targeted branch coverage tests for person extractors, links, and page actions."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from linkedin_scraper.core.page_actions import (
    click_see_more_buttons,
    extract_text_safe,
    handle_modal_close,
    scroll_to_half,
)
from linkedin_scraper.models import Experience
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.scrapers.person.contacts import ContactsExtractor
from linkedin_scraper.scrapers.person.education import EducationExtractor
from linkedin_scraper.scrapers.person.experience import ExperienceExtractor
from linkedin_scraper.scrapers.person.interests import InterestsExtractor
from linkedin_scraper.scrapers.person.links import (
    attach_organization_urls,
    extract_item_text_and_url,
)


# ===========================================================================
# 1. Page Actions Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_locator_branch():
    page = MagicMock(spec=["locator"])
    element = MagicMock()
    element.text_content = AsyncMock(return_value="  Hello World  ")
    loc = MagicMock()
    loc.first = element
    page.locator.return_value = loc

    text = await extract_text_safe(page, "h1")
    assert text == "Hello World"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_text_safe_exception_returns_default():
    page = MagicMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(side_effect=RuntimeError("Timeout"))

    text = await extract_text_safe(page, "h1", default="Fallback")
    assert text == "Fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scroll_to_half_exception():
    page = MagicMock()
    page.evaluate = AsyncMock(side_effect=RuntimeError("Scroll crash"))
    # Should not raise
    await scroll_to_half(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_click_see_more_locator_branch():
    page = MagicMock(spec=["locator"])
    element = MagicMock()
    element.is_visible = AsyncMock(side_effect=[True, False])
    element.click = AsyncMock()
    loc = MagicMock()
    loc.first = element
    page.locator.return_value = loc

    with patch("asyncio.sleep", new_callable=AsyncMock):
        count = await click_see_more_buttons(page, max_attempts=2)
    assert count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_click_see_more_exception_breaks():
    page = MagicMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(side_effect=RuntimeError("Crash"))

    count = await click_see_more_buttons(page, max_attempts=2)
    assert count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_modal_close_locator_branch():
    page = MagicMock(spec=["locator"])
    element = MagicMock()
    element.is_visible = AsyncMock(return_value=True)
    element.click = AsyncMock()
    loc = MagicMock()
    loc.first = element
    page.locator.return_value = loc

    with patch("asyncio.sleep", new_callable=AsyncMock):
        closed = await handle_modal_close(page)
    assert closed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_modal_close_exception():
    page = MagicMock(spec=["query_selector_all"])
    page.query_selector_all = AsyncMock(side_effect=RuntimeError("Crash"))

    closed = await handle_modal_close(page)
    assert closed is False


# ===========================================================================
# 2. Links Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_item_text_and_url_locator_and_text_content():
    item = MagicMock(spec=["locator", "text_content"])
    link = MagicMock()
    link.count = AsyncMock(return_value=1)
    link.get_attribute = AsyncMock(return_value="/company/acme/")
    loc = MagicMock()
    loc.first = link
    item.locator.return_value = loc
    item.text_content = AsyncMock(return_value="Acme Corp\nSenior Engineer")

    lines, href = await extract_item_text_and_url(item, "/company/")
    assert href == "https://www.linkedin.com/company/acme/"
    assert lines == ["Acme Corp", "Senior Engineer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_attach_organization_urls_fuzzy_and_exception():
    # 1. Fuzzy match
    browser = MagicMock(spec=["query_selector_all"])
    link_el = MagicMock()
    link_el.get_attribute = AsyncMock(return_value="/company/acme-corp/")
    link_el.text_content = AsyncMock(return_value="Acme Corporation Global")
    browser.query_selector_all = AsyncMock(return_value=[link_el])

    exp = Experience(
        position_title="Software Engineer",
        institution_name="Acme",
    )
    enriched = await attach_organization_urls(browser, [exp], "/company/")
    assert enriched[0].linkedin_url == "https://www.linkedin.com/company/acme-corp/"

    # 2. Exception handling
    bad_browser = MagicMock(spec=["query_selector_all"])
    bad_browser.query_selector_all = AsyncMock(side_effect=RuntimeError("Crash"))
    res = await attach_organization_urls(bad_browser, [exp], "/company/")
    assert res == [exp]


# ===========================================================================
# 3. Contacts Extractor Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_plain_text_and_label():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    # Create dialog with a section that has no links but plain text (e.g. Phone)
    dialog = MagicMock(spec=ElementPort)
    section = MagicMock(spec=ElementPort)

    heading = MagicMock(spec=ElementPort)
    heading.text_content = AsyncMock(return_value="Phone")

    label_span = MagicMock(spec=ElementPort)
    label_span.text_content = AsyncMock(return_value="(Mobile)")

    section.query_selector_all = AsyncMock(side_effect=[
        [heading],       # headings
        [],              # links
        [label_span],    # _contact_label spans
    ])
    section.inner_text = AsyncMock(return_value="Phone\n+1 555 123 4567")

    dialog.query_selector_all = AsyncMock(return_value=[section])
    browser.query_selector_all = AsyncMock(side_effect=[
        [dialog],        # dialogs
        [],              # outbound links in main
    ])

    extractor = ContactsExtractor(browser)
    contacts = await extractor.get_contacts("https://www.linkedin.com/in/user/")
    assert len(contacts) > 0
    assert any("+1 555 123 4567" in c.value for c in contacts)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_error_handling():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock(side_effect=RuntimeError("Nav error"))

    extractor = ContactsExtractor(browser)
    contacts = await extractor.get_contacts("https://www.linkedin.com/in/user/")
    assert contacts == []


# ===========================================================================
# 4. Interests Extractor Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interests_extractor_subpage_fallback():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    tab = MagicMock(spec=ElementPort)
    tab.text_content = AsyncMock(return_value="Companies")
    tab.click = AsyncMock()

    tabpanel = MagicMock(spec=ElementPort)
    item = MagicMock(spec=ElementPort)
    link = MagicMock(spec=ElementPort)
    link.get_attribute = AsyncMock(return_value="https://www.linkedin.com/company/microsoft/")

    span = MagicMock(spec=ElementPort)
    span.text_content = AsyncMock(return_value="Microsoft")

    item.query_selector_all = AsyncMock(side_effect=[
        [link],      # a, link
        [span],      # span text elements
    ])
    tabpanel.query_selector_all = AsyncMock(return_value=[item])

    # 1st call on profile: no tabs; 2nd call on details/interests/: tabs found; 3rd: tabpanels
    browser.query_selector_all = AsyncMock(side_effect=[
        [],             # main page tabs
        [tab],          # subpage tabs
        [tabpanel],     # subpage tabpanels
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        extractor = InterestsExtractor(browser)
        interests = await extractor.get_interests("https://www.linkedin.com/in/user/")

    assert len(interests) == 1
    assert interests[0].name == "Microsoft"
    assert interests[0].category == "company"


# ===========================================================================
# 5. Education & Experience Extractor Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_education_extractor_subpage_navigation():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    item = MagicMock(spec=ElementPort)
    item.inner_text = AsyncMock(return_value="Harvard University\nBachelor of Science\n2010 - 2014")
    link = MagicMock(spec=ElementPort)
    link.get_attribute = AsyncMock(return_value="/school/harvard-university/")
    item.query_selector_all = AsyncMock(return_value=[link])

    browser.query_selector_all = AsyncMock(return_value=[item])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        extractor = EducationExtractor(browser)
        edu = await extractor.get_educations("https://www.linkedin.com/in/user/")

    assert len(edu) == 1
    assert "Harvard" in edu[0].institution_name


@pytest.mark.unit
@pytest.mark.asyncio
async def test_experience_extractor_subpage_navigation():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    item = MagicMock(spec=ElementPort)
    item.inner_text = AsyncMock(return_value="Senior Software Engineer\nGoogle\nJan 2020 - Present")
    link = MagicMock(spec=ElementPort)
    link.get_attribute = AsyncMock(return_value="/company/google/")
    item.query_selector_all = AsyncMock(return_value=[link])

    browser.query_selector_all = AsyncMock(return_value=[item])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        extractor = ExperienceExtractor(browser)
        exp = await extractor.get_experiences("https://www.linkedin.com/in/user/")

    assert len(exp) == 1
    assert "Google" in exp[0].institution_name

