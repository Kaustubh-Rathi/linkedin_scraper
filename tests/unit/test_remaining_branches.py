"""Targeted branch coverage tests for browser session, job search, accomplishments, and company details."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from linkedin_scraper.core.browser import BrowserManager
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.scrapers.company.scraper import CompanyScraper
from linkedin_scraper.scrapers.job.search import JobSearchScraper
from linkedin_scraper.scrapers.person.accomplishments import AccomplishmentsExtractor


# ===========================================================================
# 1. Browser Session Persistence Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_save_and_load_session(tmp_path):
    bm = BrowserManager(headless=True)
    bm._browser = MagicMock()
    bm._context = MagicMock()
    bm._page = MagicMock()
    bm._page.close = AsyncMock()

    bm._context.storage_state = AsyncMock(return_value={"cookies": [{"name": "li_at", "value": "secret"}], "origins": []})
    bm._context.close = AsyncMock()

    new_ctx = MagicMock()
    new_page = MagicMock()
    new_ctx.new_page = AsyncMock(return_value=new_page)
    new_ctx.add_cookies = AsyncMock()
    bm._browser.new_context = AsyncMock(return_value=new_ctx)

    session_path = tmp_path / "sess.json"
    await bm.save_session(str(session_path))
    assert session_path.exists()

    # Load session
    await bm.load_session(str(session_path))
    bm._browser.new_context.assert_awaited_once()



@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_load_session_missing_file(tmp_path):
    bm = BrowserManager(headless=True)
    bm._context = MagicMock()
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        await bm.load_session(str(missing))


# ===========================================================================
# 2. Job Search Scraper Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_job_search_scraper_collects_urls_with_scroll():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_load_state = AsyncMock()
    browser.wait_for_selector = AsyncMock()
    browser.evaluate = AsyncMock(return_value=1000)

    card = MagicMock(spec=ElementPort)
    card.get_attribute = AsyncMock(return_value="https://www.linkedin.com/jobs/view/999999/")
    card.text_content = AsyncMock(return_value="Dev Engineer\nAcme")
    card.is_visible = AsyncMock(return_value=True)
    browser.query_selector_all = AsyncMock(return_value=[card])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        scraper = JobSearchScraper(browser)
        urls = await scraper.search(keywords="dev", limit=1)

    assert len(urls) == 1
    assert "999999" in urls[0]



# ===========================================================================
# 3. Accomplishments Extractor Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_accomplishments_extractor_subpages():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    item = MagicMock(spec=ElementPort)
    item.inner_text = AsyncMock(return_value="Python Certified Professional\nPython Institute")
    item.text_content = AsyncMock(return_value="Python Certified Professional\nPython Institute")
    browser.query_selector_all = AsyncMock(return_value=[item])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        extractor = AccomplishmentsExtractor(browser)
        res = await extractor.get_accomplishments("https://www.linkedin.com/in/user/")

    assert isinstance(res, list)


# ===========================================================================
# 4. Company Scraper & Posts Scraper Branches
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_scraper_about_and_details():
    browser = MagicMock(spec=BrowserPort)
    browser.goto = AsyncMock()
    browser.wait_for_selector = AsyncMock()

    browser.extract_text_safe = AsyncMock(side_effect=lambda sel, default="", timeout=2000: "Acme Corp" if "h1" in sel else default)

    section = MagicMock(spec=ElementPort)
    section.inner_text = AsyncMock(return_value="Overview\nLeading provider of software.\nWebsite\nhttps://acme.example.com\nIndustry\nTechnology\nCompany size\n1,001-5,000 employees\nHeadquarters\nSan Francisco, CA")

    browser.query_selector_all = AsyncMock(return_value=[section])

    scraper = CompanyScraper(browser)
    company = await scraper.scrape("https://www.linkedin.com/company/acme/")
    assert company.name == "Acme Corp"
    assert company.company_size is not None or company.about_us is not None

