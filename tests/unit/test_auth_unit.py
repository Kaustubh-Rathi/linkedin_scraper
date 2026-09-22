"""Unit tests for linkedin_scraper.core.auth (mocked page, no real browser)."""
import pytest

from linkedin_scraper.core import auth as auth_module
from linkedin_scraper.core.auth import (
    is_logged_in,
    load_credentials_from_env,
    login_with_credentials,
)
from linkedin_scraper.core.exceptions import AuthenticationError


@pytest.mark.unit
def test_load_credentials_from_env_reads_email_and_password(monkeypatch, tmp_path):
    # Avoid picking up a real .env file from the repo/cwd.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LINKEDIN_EMAIL", "person@example.com")
    monkeypatch.setenv("LINKEDIN_PASSWORD", "hunter2")
    monkeypatch.delenv("LINKEDIN_USERNAME", raising=False)

    email, password = load_credentials_from_env()

    assert email == "person@example.com"
    assert password == "hunter2"


@pytest.mark.unit
def test_load_credentials_from_env_falls_back_to_username(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LINKEDIN_EMAIL", raising=False)
    monkeypatch.setenv("LINKEDIN_USERNAME", "fallback@example.com")
    monkeypatch.setenv("LINKEDIN_PASSWORD", "secret")

    email, password = load_credentials_from_env()

    assert email == "fallback@example.com"
    assert password == "secret"


@pytest.mark.unit
def test_load_credentials_from_env_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LINKEDIN_EMAIL", raising=False)
    monkeypatch.delenv("LINKEDIN_USERNAME", raising=False)
    monkeypatch.delenv("LINKEDIN_PASSWORD", raising=False)

    email, password = load_credentials_from_env()

    assert email is None
    assert password is None


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/login",
        "https://www.linkedin.com/authwall",
        "https://www.linkedin.com/checkpoint/lg/sign-in-another-account",
        "https://www.linkedin.com/challenge/",
        "https://www.linkedin.com/uas/login",
    ],
)
async def test_is_logged_in_false_on_auth_blocker_urls(url, fake_page_cls):
    page = fake_page_cls(url=url)
    assert await is_logged_in(page) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_true_via_nav_elements(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        url="https://www.linkedin.com/in/example/",
        locator_factory=lambda selector: fake_locator_cls(count=1),
    )
    assert await is_logged_in(page) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_true_on_authenticated_only_page(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        url="https://www.linkedin.com/feed/",
        locator_factory=lambda selector: fake_locator_cls(count=0),
    )
    assert await is_logged_in(page) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_false_when_no_nav_and_not_authenticated_page(fake_page_cls, fake_locator_cls):
    page = fake_page_cls(
        url="https://www.linkedin.com/pub/some-random-page",
        locator_factory=lambda selector: fake_locator_cls(count=0),
    )
    assert await is_logged_in(page) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_returns_false_on_exception(fake_page_cls):
    page = fake_page_cls(url="https://www.linkedin.com/feed/")

    def raising_locator(selector):
        raise RuntimeError("dom exploded")

    page.locator = raising_locator

    assert await is_logged_in(page) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_raises_when_no_credentials(monkeypatch, fake_page_cls):
    monkeypatch.setattr(
        auth_module, "load_credentials_from_env", lambda: (None, None)
    )
    page = fake_page_cls()

    with pytest.raises(AuthenticationError, match="credentials not provided"):
        await login_with_credentials(page, email=None, password=None)
