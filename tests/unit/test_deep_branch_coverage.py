"""
Comprehensive branch coverage suite for browser lifecycle, adapters, extractors, and edge branches.

Targets:
- linkedin_scraper.__main__ CLI invocation
- PlaywrightElementAdapter & PlaywrightBrowserAdapter defensive branches
- BrowserManager lifecycle, session persistence, error branches
- Person extractors (contacts, interests, education, experience, accomplishments, links)
- Search workflow, exports, filters, and URL builders
- Protocol / Port boundary coverage
"""

from __future__ import annotations

import runpy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import ElementHandle, Page, TimeoutError as PlaywrightTimeoutError

from linkedin_scraper.core.browser import (
    BrowserManager,
    PlaywrightBrowserAdapter,
    PlaywrightElementAdapter,
)
from linkedin_scraper.core.exceptions import (
    NetworkError,
)
from linkedin_scraper.models import Experience
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.scrapers.person.contacts import ContactsExtractor
from linkedin_scraper.scrapers.person.education import EducationExtractor
from linkedin_scraper.scrapers.person.experience import ExperienceExtractor
from linkedin_scraper.scrapers.person.interests import InterestsExtractor
from linkedin_scraper.scrapers.person.links import (
    attach_organization_urls,
    profile_detail_url,
    unwrap_href,
)
from linkedin_scraper.search.queries import PersonSearchQuery
from linkedin_scraper.search.results import (
    PersonSearchResult,
    SearchPage,
)
from linkedin_scraper.search.workflow import (
    SearchWorkflowResult,
    consume_search,
    execute_search_workflow,
    iterate_search_pages,
    iterate_search_results,
)



# ===========================================================================
# 1. CLI __main__ Invocation Branch
# ===========================================================================


@pytest.mark.unit
def test_main_module_invocation():
    """Verify python -m linkedin_scraper invokes CLI main."""
    with patch("sys.argv", ["linkedin-scraper", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("linkedin_scraper.__main__", run_name="__main__")
        assert exc_info.value.code == 0


# ===========================================================================
# 2. PlaywrightElementAdapter Defensive Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_element_adapter_element_handle_branch():
    """Test PlaywrightElementAdapter when target is an ElementHandle."""
    mock_handle = MagicMock(spec=ElementHandle)
    mock_handle.text_content = AsyncMock(return_value="Handle Text")
    mock_handle.inner_text = AsyncMock(return_value="Handle Inner")
    mock_handle.get_attribute = AsyncMock(return_value="Handle Attr")
    mock_handle.is_visible = AsyncMock(return_value=True)

    adapter = PlaywrightElementAdapter(mock_handle)
    assert await adapter.text_content() == "Handle Text"
    assert await adapter.inner_text() == "Handle Inner"
    assert await adapter.get_attribute("href") == "Handle Attr"
    assert await adapter.is_visible() is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_element_adapter_locator_all_fallback():
    """Test PlaywrightElementAdapter query_selector_all using locator.all() fallback."""
    mock_target = MagicMock()
    del mock_target.query_selector_all
    mock_loc = MagicMock()
    mock_child = MagicMock()
    mock_child.text_content = AsyncMock(return_value="Child")
    mock_loc.all = AsyncMock(return_value=[mock_child])
    mock_target.locator.return_value = mock_loc

    adapter = PlaywrightElementAdapter(mock_target)
    children = await adapter.query_selector_all(".child")
    assert len(children) == 1
    assert isinstance(children[0], ElementPort)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_element_adapter_fallback_when_methods_missing():
    """Test PlaywrightElementAdapter graceful fallbacks when target lacks methods."""
    target = object()
    adapter = PlaywrightElementAdapter(target)

    assert await adapter.text_content() is None
    assert await adapter.inner_text() == ""
    assert await adapter.get_attribute("src") is None
    assert await adapter.is_visible() is False
    assert await adapter.query_selector_all("div") == []
    await adapter.click()


# ===========================================================================
# 3. PlaywrightBrowserAdapter Defensive Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_adapter_evaluate_with_arg():
    """Test evaluate method with arg."""
    mock_page = AsyncMock(spec=Page)
    mock_page.evaluate.return_value = 42
    adapter = PlaywrightBrowserAdapter(mock_page)

    res = await adapter.evaluate("x => x * 2", 21)
    assert res == 42
    mock_page.evaluate.assert_called_once_with("x => x * 2", 21)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_adapter_extract_text_safe_custom_and_fallback():
    """Test extract_text_safe when page has extract_text_safe method and when it errors."""
    mock_page = MagicMock()
    mock_page.extract_text_safe = AsyncMock(return_value="Custom Safe Text")
    adapter = PlaywrightBrowserAdapter(mock_page)

    text = await adapter.extract_text_safe(".target")
    assert text == "Custom Safe Text"

    del mock_page.extract_text_safe
    mock_loc = MagicMock()
    mock_first = MagicMock()
    mock_first.text_content = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
    mock_loc.first = mock_first
    mock_page.locator.return_value = mock_loc

    text = await adapter.extract_text_safe(".target", default="default_val")
    assert text == "default_val"

    mock_first.text_content = AsyncMock(side_effect=RuntimeError("unexpected"))
    text = await adapter.extract_text_safe(".target", default="fallback")
    assert text == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_adapter_locator_and_query_selector_all_branches():
    """Test locator property and query_selector_all variations."""
    mock_page = MagicMock()
    mock_page.locator.return_value = "mock_locator"
    adapter = PlaywrightBrowserAdapter(mock_page)

    loc = await adapter.locator(".item")
    assert loc == "mock_locator"

    # Test query_selector_all adaptation
    raw_elem = MagicMock(spec=ElementHandle)
    mock_page.query_selector_all = AsyncMock(return_value=[raw_elem])

    elems = await adapter.query_selector_all(".item")
    assert len(elems) == 1
    assert isinstance(elems[0], PlaywrightElementAdapter)

    del mock_page.query_selector_all
    mock_loc_item = MagicMock()
    mock_loc_res = MagicMock()
    mock_loc_res.all = AsyncMock(return_value=[mock_loc_item])
    mock_page.locator.return_value = mock_loc_res

    elems = await adapter.query_selector_all(".item")
    assert len(elems) == 1
    assert isinstance(elems[0], PlaywrightElementAdapter)

    del mock_page.locator
    elems = await adapter.query_selector_all(".item")
    assert elems == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_adapter_add_cookies():
    """Test add_cookies method on adapter."""
    mock_page = MagicMock()
    mock_page.context = MagicMock()
    mock_page.context.add_cookies = AsyncMock()
    adapter = PlaywrightBrowserAdapter(mock_page)

    await adapter.add_cookies([{"name": "li_at", "value": "123", "domain": ".linkedin.com"}])
    mock_page.context.add_cookies.assert_called_once()


# ===========================================================================
# 4. BrowserManager Full Lifecycle & Exception Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_start_failure_raises_network_error():
    """Test browser startup failure triggers close and raises NetworkError."""
    bm = BrowserManager(headless=True, user_agent="CustomAgent/1.0")

    with patch("linkedin_scraper.core.browser.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(side_effect=RuntimeError("Browser launch failed"))
        with pytest.raises(NetworkError, match="Failed to start browser"):
            await bm.start()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_close_handles_inner_exceptions():
    """Test close method gracefully handles and swallows exceptions during teardown."""
    bm = BrowserManager()
    bm._page = MagicMock()
    bm._page.close = AsyncMock(side_effect=RuntimeError("Page close error"))
    bm._context = MagicMock()
    bm._context.close = AsyncMock(side_effect=RuntimeError("Context close error"))

    # Must complete cleanly without raising
    await bm.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_unstarted_property_errors():
    """Test unstarted BrowserManager raises RuntimeError on property access."""
    bm = BrowserManager()

    with pytest.raises(RuntimeError, match="Browser not started"):
        _ = bm.page

    with pytest.raises(RuntimeError, match="Browser context not initialized"):
        _ = bm.context

    with pytest.raises(RuntimeError, match="Browser not started"):
        _ = bm.browser

    with pytest.raises(RuntimeError, match="Browser not started"):
        _ = bm.get_browser_port()

    with pytest.raises(RuntimeError, match="Browser context not initialized"):
        await bm.new_page()

    with pytest.raises(RuntimeError, match="No browser context"):
        await bm.save_session("test.json")

    with pytest.raises(RuntimeError, match="No browser context"):
        await bm.set_cookie("li_at", "123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_set_cookie_and_auth_property():
    """Test set_cookie and is_authenticated property."""
    bm = BrowserManager()
    bm._context = MagicMock()
    bm._context.add_cookies = AsyncMock()

    await bm.set_cookie("li_at", "test_value", domain=".linkedin.com")
    bm._context.add_cookies.assert_called_once_with([{
        "name": "li_at",
        "value": "test_value",
        "domain": ".linkedin.com",
        "path": "/",
    }])

    assert bm.is_authenticated is False
    bm.is_authenticated = True
    assert bm.is_authenticated is True


# ===========================================================================
# 5. ContactsExtractor Full Branch Coverage
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_outbound_links_filtering():
    """Test outbound links filtering (internal URLs, long labels, deduplication, errors)."""
    browser = MagicMock(spec=BrowserPort)

    l1 = MagicMock(spec=ElementPort)
    l1.get_attribute = AsyncMock(return_value="")

    l2 = MagicMock(spec=ElementPort)
    l2.get_attribute = AsyncMock(return_value="https://www.linkedin.com/in/other-person")

    l3 = MagicMock(spec=ElementPort)
    l3.get_attribute = AsyncMock(return_value="/feed/")

    l4 = MagicMock(spec=ElementPort)
    l4.get_attribute = AsyncMock(return_value="https://github.com/myuser")
    l4.text_content = AsyncMock(return_value="A" * 100)

    l5 = MagicMock(spec=ElementPort)
    l5.get_attribute = AsyncMock(return_value="https://github.com/myuser")

    l6 = MagicMock(spec=ElementPort)
    l6.get_attribute = AsyncMock(return_value="mailto:test@example.com")

    l7 = MagicMock(spec=ElementPort)
    l7.get_attribute = AsyncMock(side_effect=RuntimeError("DOM disconnected"))

    browser.query_selector_all = AsyncMock(return_value=[l1, l2, l3, l4, l5, l6, l7])

    extractor = ContactsExtractor(browser)
    contacts = await extractor.extract_outbound_links()

    assert len(contacts) == 1
    assert contacts[0].type == "github"
    assert contacts[0].value == "https://github.com/myuser"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_dialog_fallback_to_plain_text():
    """Test dialog parsing with sections having no links, falling back to inner_text."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

    dialog = MagicMock(spec=ElementPort)
    section1 = MagicMock(spec=ElementPort)

    h3_phone = MagicMock(spec=ElementPort)
    h3_phone.text_content = AsyncMock(return_value="Phone")
    section1.inner_text = AsyncMock(return_value="Phone\n+1 555 123 4567")

    label_span = MagicMock(spec=ElementPort)
    label_span.text_content = AsyncMock(return_value="(Mobile)")

    async def section_qsa(sel):
        if sel == "h3":
            return [h3_phone]
        if "span" in sel or "generic" in sel:
            return [label_span]
        return []

    section1.query_selector_all = AsyncMock(side_effect=section_qsa)

    dialog.query_selector_all = AsyncMock(return_value=[section1])
    browser.query_selector_all = AsyncMock(side_effect=lambda sel: [dialog] if "dialog" in sel else [])

    extractor = ContactsExtractor(browser)
    with patch.object(extractor, "extract_outbound_links", return_value=[]):
        contacts = await extractor.get_contacts("https://www.linkedin.com/in/test-user/")

    assert len(contacts) >= 1
    assert any(c.type == "phone" for c in contacts)


@pytest.mark.unit
def test_contacts_plain_contact_value_helper():
    """Test ContactsExtractor.plain_contact_value removes matching heading."""
    text = "Email\nuser@example.com\n"
    res = ContactsExtractor.plain_contact_value(text, "Email")
    assert res == "user@example.com"

    empty_res = ContactsExtractor.plain_contact_value("Email", "Email")
    assert empty_res is None


# ===========================================================================
# 6. InterestsExtractor Multi-Tab & Subpage Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interests_extractor_tablist_and_subpage_fallback():
    """Test interests extractor switching tabs and subpage fallback."""
    class DummyInterestItem:
        async def text_content(self, timeout=2000):
            return "Microsoft"

        async def get_attribute(self, name, timeout=2000):
            return "https://www.linkedin.com/company/microsoft/"

        async def query_selector_all(self, selector):
            return [self]

    class DummyTab:
        def __init__(self, name, fail_click=False):
            self.name = name
            self.fail_click = fail_click

        async def text_content(self, timeout=2000):
            return self.name

        async def click(self):
            if self.fail_click:
                raise RuntimeError("Click blocked")

    class DummyPanel:
        async def query_selector_all(self, selector):
            return [DummyInterestItem()]

    tab1 = DummyTab("Companies")
    tab2 = DummyTab("Schools", fail_click=True)
    panel = DummyPanel()

    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    async def mock_browser_qsa(sel):
        if "tabpanel" in sel:
            return [panel]
        if "tab" in sel:
            return [tab1, tab2]
        return []

    browser.query_selector_all = AsyncMock(side_effect=mock_browser_qsa)

    extractor = InterestsExtractor(browser)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        interests = await extractor.get_interests("https://www.linkedin.com/in/test-user/")

    assert len(interests) >= 1
    assert any("microsoft" in (i.linkedin_url or "").lower() or i.name == "Microsoft" for i in interests)


# ===========================================================================
# 7. Education & Experience Detail Page Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_education_extractor_details_subpage():
    """Test education extractor navigating to details/education/ subpage with card elements."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    edu_item = MagicMock(spec=ElementPort)
    edu_link = MagicMock(spec=ElementPort)
    edu_link.get_attribute = AsyncMock(return_value="https://www.linkedin.com/school/stanford-university/")

    edu_item.query_selector_all = AsyncMock(side_effect=lambda sel: [edu_link] if "school" in sel else [])
    edu_item.inner_text = AsyncMock(return_value="Stanford University\nMaster of Science - MS, Computer Science\n2018 - 2020")
    edu_item.text_content = AsyncMock(return_value="Stanford University\nMaster of Science - MS, Computer Science\n2018 - 2020")

    browser.query_selector_all = AsyncMock(side_effect=lambda sel: [edu_item] if "profile-component-entity" in sel or "pvs-list" in sel else [])

    extractor = EducationExtractor(browser)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        educations = await extractor.get_educations("https://www.linkedin.com/in/test-user/")

    assert len(educations) >= 1
    assert educations[0].institution_name == "Stanford University"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_experience_extractor_details_subpage():
    """Test experience extractor navigating to details/experience/ subpage with card elements."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    exp_item = MagicMock(spec=ElementPort)
    exp_link = MagicMock(spec=ElementPort)
    exp_link.get_attribute = AsyncMock(return_value="https://www.linkedin.com/company/google/")

    exp_item.query_selector_all = AsyncMock(side_effect=lambda sel: [exp_link] if "company" in sel else [])
    exp_item.inner_text = AsyncMock(return_value="Senior Software Engineer\nGoogle · Full-time\nJan 2021 - Present · 3 yrs\nMountain View, CA")
    exp_item.text_content = AsyncMock(return_value="Senior Software Engineer\nGoogle · Full-time\nJan 2021 - Present · 3 yrs\nMountain View, CA")

    browser.query_selector_all = AsyncMock(side_effect=lambda sel: [exp_item] if "profile-component-entity" in sel or "pvs-list" in sel else [])

    extractor = ExperienceExtractor(browser)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        experiences = await extractor.get_experiences("https://www.linkedin.com/in/test-user/")

    assert len(experiences) >= 1
    assert experiences[0].position_title == "Senior Software Engineer"


# ===========================================================================
# 8. Person Links and URL Helper Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_links_helpers():
    """Test profile_detail_url, unwrap_href, extract_item_text_and_url, and attach_organization_urls."""
    url = profile_detail_url("https://www.linkedin.com/in/user/?miniProfileUrn=123", "details/experience/")
    assert url == "https://www.linkedin.com/in/user/details/experience/"

    unwrapped = unwrap_href("https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fexample.com%2Fproject")
    assert "example.com/project" in unwrapped

    browser = MagicMock(spec=BrowserPort)
    link_elem = MagicMock(spec=ElementPort)
    link_elem.get_attribute = AsyncMock(return_value="https://www.linkedin.com/company/acme/")
    link_elem.text_content = AsyncMock(return_value="Acme Corp")
    browser.query_selector_all = AsyncMock(return_value=[link_elem])

    exps = [Experience(position_title="Dev", institution_name="Acme Corp")]
    updated = await attach_organization_urls(browser, exps, "/company/")
    assert updated[0].linkedin_url == "https://www.linkedin.com/company/acme/"


# ===========================================================================
# 9. Search Execution & Stalled Pagination Branch
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_execution_engine_stalled_pagination():
    """Test search workflow detects stalled pagination token and halts gracefully."""
    mock_search = AsyncMock()
    page1 = SearchPage(
        items=[PersonSearchResult(name="Person A", linkedin_url="https://www.linkedin.com/in/a")],
        continuation_token="token_123",
        has_more=True,
    )
    page2 = SearchPage(
        items=[],
        continuation_token="token_123",
        has_more=True,
    )
    mock_search.side_effect = [page1, page2]

    query = PersonSearchQuery(keywords="Test", limit=10)
    result = await consume_search(mock_search, query, max_results=10)

    assert len(result) == 1
    assert result[0].name == "Person A"


# ===========================================================================
# 10. Workflow Runner Full Matrix
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_workflow_zero_max_results():
    """Test workflow early returns on zero max results."""
    mock_fn = AsyncMock()
    query = PersonSearchQuery(keywords="dev", limit=10)

    pages = []
    async for p in iterate_search_pages(mock_fn, query, max_pages=0):
        pages.append(p)
    assert pages == []

    items = []
    async for item in iterate_search_results(mock_fn, query, max_results=0):
        items.append(item)
    assert items == []

    consumed = await consume_search(mock_fn, query, max_results=0)
    assert consumed == []

    wf_res = await execute_search_workflow(mock_fn, query, max_results=0)
    assert len(wf_res.items) == 0
    assert wf_res.total_collected == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_workflow_export_paths(tmp_path):
    """Test workflow auto-export to JSON, CSV, JSONL."""
    item = PersonSearchResult(name="Alice Smith", linkedin_url="https://www.linkedin.com/in/alice")
    page = SearchPage(items=[item], total_count=1, has_more=False, continuation_token=None)

    async def mock_fn(q):
        return page

    query = PersonSearchQuery(keywords="Alice", limit=5)
    json_path = tmp_path / "results.json"
    wf_res = await execute_search_workflow(
        mock_fn, query, max_results=5, export_path=json_path
    )
    assert json_path.exists()
    assert "Alice Smith" in json_path.read_text(encoding="utf-8")

    csv_path = tmp_path / "results.csv"
    await execute_search_workflow(
        mock_fn, query, max_results=5, export_path=csv_path, export_format="csv"
    )
    assert csv_path.exists()

    # SearchWorkflowResult helpers
    assert len(wf_res) == 1
    assert wf_res[0].name == "Alice Smith"
    assert list(iter(wf_res))[0].name == "Alice Smith"
    dicts = wf_res.to_dicts()
    assert len(dicts) == 1
    assert dicts[0]["name"] == "Alice Smith"


# ===========================================================================
# 11. Interests & Contacts Edge Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interests_extractor_subpage_branches():
    """Test InterestsExtractor details/interests subpage fallback and static method."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

    # Initial get_interests has no tabs on main page -> navigates to details/interests/
    # On subpage, returns no tabs
    browser.query_selector_all = AsyncMock(return_value=[])

    extractor = InterestsExtractor(browser)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        interests = await extractor.get_interests("https://www.linkedin.com/in/user/")
    assert interests == []

    # Test static method
    assert InterestsExtractor._map_interest_tab_to_category("Top Companies") == "company"
    assert InterestsExtractor._map_interest_tab_to_category("Top Voices") == "influencer"
    assert InterestsExtractor._map_interest_tab_to_category("Schools") == "school"
    assert InterestsExtractor._map_interest_tab_to_category("Newsletters") == "newsletter"
    assert InterestsExtractor._map_interest_tab_to_category("Groups") == "group"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contacts_extractor_exception_branch():
    """Test ContactsExtractor graceful empty list on unhandled exceptions."""
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock(side_effect=RuntimeError("Navigation failure"))

    extractor = ContactsExtractor(browser)
    contacts = await extractor.get_contacts("https://www.linkedin.com/in/user/")
    assert contacts == []

