"""Additional auth unit tests covering login branches (mocked page)."""
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.core import auth as auth_module
from linkedin_scraper.core.auth import (
    login_with_cookie,
    login_with_credentials,
    wait_for_manual_login,
    warm_up_browser,
)
from linkedin_scraper.core.exceptions import AuthenticationError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_warm_up_browser_visits_sites(fake_page_cls):
    page = fake_page_cls()
    await warm_up_browser(page)
    assert len(page.goto_calls) >= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_checkpoint_raises(monkeypatch, fake_page_cls):
    monkeypatch.setattr(auth_module, "warm_up_browser", AsyncMock())
    monkeypatch.setattr(auth_module, "detect_rate_limit", AsyncMock())
    page = fake_page_cls(url="https://www.linkedin.com/login")
    page._wait_for_url_target = "https://www.linkedin.com/checkpoint/challenge/"

    with pytest.raises(AuthenticationError, match="checkpoint"):
        await login_with_credentials(
            page, email="a@b.com", password="secret", warm_up=False
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_authwall_raises(monkeypatch, fake_page_cls):
    monkeypatch.setattr(auth_module, "warm_up_browser", AsyncMock())
    monkeypatch.setattr(auth_module, "detect_rate_limit", AsyncMock())
    page = fake_page_cls(url="https://www.linkedin.com/login")
    page._wait_for_url_target = "https://www.linkedin.com/authwall"

    with pytest.raises(AuthenticationError, match="wall"):
        await login_with_credentials(
            page, email="a@b.com", password="secret", warm_up=False
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_credentials_success_when_logged_in(monkeypatch, fake_page_cls):
    monkeypatch.setattr(auth_module, "warm_up_browser", AsyncMock())
    monkeypatch.setattr(auth_module, "detect_rate_limit", AsyncMock())
    monkeypatch.setattr(auth_module, "is_logged_in", AsyncMock(return_value=True))
    page = fake_page_cls(url="https://www.linkedin.com/login")
    page._wait_for_url_target = "https://www.linkedin.com/feed/"

    await login_with_credentials(
        page, email="a@b.com", password="secret", warm_up=False
    )
    assert ("#username", "a@b.com") in page.fill_calls
    assert ("#password", "secret") in page.fill_calls


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_with_cookie_invalid_raises(monkeypatch, fake_page_cls):
    monkeypatch.setattr(auth_module, "is_logged_in", AsyncMock(return_value=False))
    page = fake_page_cls(
        url="https://www.linkedin.com/feed/",
        routes={"/feed/": "https://www.linkedin.com/login"},
    )

    with pytest.raises(AuthenticationError, match="Cookie"):
        await login_with_cookie(page, "bad-cookie")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_manual_login_success(monkeypatch, fake_page_cls):
    monkeypatch.setattr(auth_module, "is_logged_in", AsyncMock(return_value=True))
    page = fake_page_cls(url="https://www.linkedin.com/feed/")
    await wait_for_manual_login(page, timeout=1000)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_manual_login_timeout(monkeypatch, fake_page_cls):
    monkeypatch.setattr(auth_module, "is_logged_in", AsyncMock(return_value=False))
    page = fake_page_cls(url="https://www.linkedin.com/login")
    with pytest.raises(AuthenticationError, match="timeout"):
        await wait_for_manual_login(page, timeout=10)
