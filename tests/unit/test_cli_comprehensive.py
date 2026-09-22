"""Comprehensive unit tests covering CLI commands, subcommands, and main routing."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from linkedin_scraper.cli import commands
from linkedin_scraper.cli.main import main as entrypoint_main
from linkedin_scraper.models import Company, Job, Post



from linkedin_scraper.search import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PostSearchResult,
    SearchWorkflowResult,
)


class _MockContextManager:
    def __init__(self, browser):
        self.browser = browser

    async def __aenter__(self):
        return self.browser

    async def __aexit__(self, *args):
        return False


# ===========================================================================
# 1. CLI Commands Tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_login_success(tmp_path):
    browser_manager = MagicMock()
    browser_manager.browser_port = MagicMock()
    browser_manager.browser_port.goto = AsyncMock()
    browser_manager.save_session = AsyncMock()

    with patch("linkedin_scraper.cli.commands.BrowserManager", return_value=_MockContextManager(browser_manager)):
        with patch("linkedin_scraper.cli.commands.wait_for_manual_login", new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = None
            code = await commands.cmd_login(session=str(tmp_path / "sess.json"), timeout_ms=60000)
            assert code == 0
            browser_manager.save_session.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_login_failure(tmp_path):
    browser_manager = MagicMock()
    browser_manager.browser_port = MagicMock()
    browser_manager.browser_port.goto = AsyncMock()

    with patch("linkedin_scraper.cli.commands.BrowserManager", return_value=_MockContextManager(browser_manager)):
        with patch("linkedin_scraper.cli.commands.wait_for_manual_login", side_effect=TimeoutError("Timed out")):
            code = await commands.cmd_login(session=str(tmp_path / "sess.json"), timeout_ms=60000)
            assert code == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_company_dumps_json(tmp_path):
    browser = MagicMock()
    browser.browser_port = MagicMock()
    company = Company(
        linkedin_url="https://www.linkedin.com/company/microsoft/",
        name="Microsoft",
    )
    out = tmp_path / "company.json"

    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch.object(
            commands, "CompanyScraper", return_value=MagicMock(scrape=AsyncMock(return_value=company))
        ):
            code = await commands.cmd_company(
                "https://www.linkedin.com/company/microsoft/",
                session="s.json",
                output=str(out),
            )
    assert code == 0
    assert "Microsoft" in out.read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_jobs_with_details(tmp_path):
    browser = MagicMock()
    browser.browser_port = MagicMock()
    job = Job(
        linkedin_url="https://www.linkedin.com/jobs/view/123/",
        job_title="Software Engineer",
        company="Microsoft",
    )
    out = tmp_path / "jobs.json"

    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch.object(
            commands, "JobSearchScraper", return_value=MagicMock(search=AsyncMock(return_value=["https://www.linkedin.com/jobs/view/123/"]))
        ):
            with patch.object(
                commands, "JobScraper", return_value=MagicMock(scrape=AsyncMock(return_value=job))
            ):
                code = await commands.cmd_jobs(
                    keywords="engineer",
                    location="Remote",
                    limit=1,
                    session="s.json",
                    scrape_details=True,
                    output=str(out),
                )
    assert code == 0
    assert "Software Engineer" in out.read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_posts_dumps_json(tmp_path):
    browser = MagicMock()
    browser.browser_port = MagicMock()
    posts = [Post(urn="urn:li:activity:1", text="Sample post")]
    out = tmp_path / "posts.json"

    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch.object(
            commands, "CompanyPostsScraper", return_value=MagicMock(scrape=AsyncMock(return_value=posts))
        ):
            code = await commands.cmd_posts(
                "https://www.linkedin.com/company/microsoft/",
                limit=1,
                session="s.json",
                output=str(out),
            )
    assert code == 0
    assert "urn:li:activity:1" in out.read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_search_all_entity_types_stdout(capsys):
    browser = MagicMock()
    browser.browser_port = MagicMock()

    mock_facade = MagicMock()

    # 1. companies
    workflow_res = SearchWorkflowResult[CompanySearchResult](
        items=[CompanySearchResult(name="Acme Corp", linkedin_url="https://www.linkedin.com/company/acme/")],
        total_collected=1,
        pages_fetched=1,
    )
    mock_facade.execute_workflow = AsyncMock(return_value=workflow_res)

    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch("linkedin_scraper.search.LinkedInSearchFacade.from_browser", return_value=mock_facade):
            code = await commands.cmd_search(
                entity_type="companies",
                keywords="Acme",
                location="US",
                limit=5,
            )
    assert code == 0

    # 2. jobs
    workflow_job = SearchWorkflowResult[JobSearchResult](
        items=[JobSearchResult(job_title="Dev", linkedin_url="https://www.linkedin.com/jobs/view/1/")],
        total_collected=1,
        pages_fetched=1,
    )
    mock_facade.execute_workflow = AsyncMock(return_value=workflow_job)
    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch("linkedin_scraper.search.LinkedInSearchFacade.from_browser", return_value=mock_facade):
            code = await commands.cmd_search(
                entity_type="jobs",
                keywords="Dev",
                company="Acme",
                limit=5,
            )
    assert code == 0

    # 3. posts
    workflow_post = SearchWorkflowResult[PostSearchResult](
        items=[PostSearchResult(post_url="https://www.linkedin.com/feed/update/1/", text_snippet="Hello")],
        total_collected=1,
        pages_fetched=1,
    )
    mock_facade.execute_workflow = AsyncMock(return_value=workflow_post)
    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch("linkedin_scraper.search.LinkedInSearchFacade.from_browser", return_value=mock_facade):
            code = await commands.cmd_search(
                entity_type="posts",
                keywords="Hello",
                company="Acme",
                limit=5,
            )
    assert code == 0

    # 4. employees
    workflow_emp = SearchWorkflowResult[EmployeeSearchResult](
        items=[EmployeeSearchResult(name="Bob", linkedin_url="https://www.linkedin.com/in/bob/")],
        total_collected=1,
        pages_fetched=1,
    )
    mock_facade.execute_workflow = AsyncMock(return_value=workflow_emp)
    with patch.object(commands, "session_browser", return_value=_MockContextManager(browser)):
        with patch("linkedin_scraper.search.LinkedInSearchFacade.from_browser", return_value=mock_facade):
            code = await commands.cmd_search(
                entity_type="employees",
                keywords="Bob",
                company="Acme",
                title="Engineer",
                location="Seattle",
                limit=5,
            )
    assert code == 0


# ===========================================================================
# 2. CLI Main Entrypoint Dispatch Tests
# ===========================================================================


@pytest.mark.unit
def test_main_dispatch_subcommands():
    with patch("linkedin_scraper.cli.commands.cmd_login", new_callable=AsyncMock) as mock_login:
        mock_login.return_value = 0
        assert entrypoint_main(["login", "--timeout-minutes", "1"]) == 0
        mock_login.assert_awaited_once()

    with patch("linkedin_scraper.cli.commands.cmd_person", new_callable=AsyncMock) as mock_person:
        mock_person.return_value = 0
        assert entrypoint_main(["person", "https://www.linkedin.com/in/satya/"]) == 0
        mock_person.assert_awaited_once()

    with patch("linkedin_scraper.cli.commands.cmd_company", new_callable=AsyncMock) as mock_company:
        mock_company.return_value = 0
        assert entrypoint_main(["company", "https://www.linkedin.com/company/msft/"]) == 0
        mock_company.assert_awaited_once()

    with patch("linkedin_scraper.cli.commands.cmd_jobs", new_callable=AsyncMock) as mock_jobs:
        mock_jobs.return_value = 0
        assert entrypoint_main(["jobs", "--keywords", "python"]) == 0
        mock_jobs.assert_awaited_once()

    with patch("linkedin_scraper.cli.commands.cmd_posts", new_callable=AsyncMock) as mock_posts:
        mock_posts.return_value = 0
        assert entrypoint_main(["posts", "https://www.linkedin.com/company/msft/"]) == 0
        mock_posts.assert_awaited_once()

    with patch("linkedin_scraper.cli.commands.cmd_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = 0
        assert entrypoint_main(["search", "people", "--keywords", "engineer"]) == 0
        mock_search.assert_awaited_once()


@pytest.mark.unit
def test_main_handles_file_not_found():
    with patch("linkedin_scraper.cli.commands.cmd_person", side_effect=FileNotFoundError("missing session")):
        code = entrypoint_main(["person", "https://www.linkedin.com/in/satya/"])
        assert code == 1


@pytest.mark.unit
def test_main_handles_generic_exception():
    with patch("linkedin_scraper.cli.commands.cmd_person", side_effect=RuntimeError("unexpected crash")):
        code = entrypoint_main(["person", "https://www.linkedin.com/in/satya/"])
        assert code == 1



