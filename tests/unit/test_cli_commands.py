"""Unit tests for CLI command runners (mocked browser)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_scraper.cli import commands
from linkedin_scraper.models import Person


class _CM:
    def __init__(self, browser):
        self.browser = browser

    async def __aenter__(self):
        return self.browser

    async def __aexit__(self, *args):
        return False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_person_dumps_json(tmp_path):
    browser = MagicMock()
    browser.page = object()
    browser.load_session = AsyncMock()
    person = Person(
        linkedin_url="https://www.linkedin.com/in/example/",
        name="Ada",
    )
    out = tmp_path / "person.json"

    with patch.object(commands, "session_browser", return_value=_CM(browser)):
        with patch.object(
            commands, "PersonScraper", return_value=MagicMock(scrape=AsyncMock(return_value=person))
        ):
            code = await commands.cmd_person(
                "https://www.linkedin.com/in/example/",
                session="s.json",
                output=str(out),
            )
    assert code == 0
    assert "Ada" in out.read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cmd_jobs_urls_only():
    browser = MagicMock()
    browser.page = object()
    browser.load_session = AsyncMock()
    urls = ["https://www.linkedin.com/jobs/view/1/"]

    with patch.object(commands, "session_browser", return_value=_CM(browser)):
        with patch.object(
            commands,
            "JobSearchScraper",
            return_value=MagicMock(search=AsyncMock(return_value=urls)),
        ):
            code = await commands.cmd_jobs(
                keywords="eng",
                location=None,
                limit=5,
                session="s.json",
                scrape_details=False,
            )
    assert code == 0


@pytest.mark.unit
def test_dump_result_list_of_dicts(capsys):
    commands._dump_result([{"a": 1}], output=None)
    captured = capsys.readouterr()
    assert '"a": 1' in captured.out
