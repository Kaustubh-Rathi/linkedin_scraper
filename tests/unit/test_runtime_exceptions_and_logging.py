"""Verification of runtime exceptions, error causes, context logging, and secret sanitization."""

import logging
from unittest.mock import AsyncMock, MagicMock
import pytest

from linkedin_scraper.core.auth import (
    AuthenticationError,
    login_with_credentials,
    login_with_cookie,
)
from linkedin_scraper.core.exceptions import (
    RateLimitError,
    RequiredFieldExtractionError,
    ScrapingError,
)
from linkedin_scraper.core.rate_limit import detect_rate_limit
from linkedin_scraper.ports.browser import BrowserPort, ElementPort
from linkedin_scraper.scrapers.company.scraper import CompanyScraper
from linkedin_scraper.scrapers.person.scraper import PersonScraper


# ===========================================================================
# 1. Navigation / Timeout Failure Cause Preservation
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigation_timeout_preserves_cause():
    browser = MagicMock(spec=BrowserPort)
    original_error = TimeoutError("Page navigation timed out after 30000ms")
    browser.goto = AsyncMock(side_effect=original_error)

    scraper = PersonScraper(browser)
    with pytest.raises(ScrapingError) as exc_info:
        await scraper.scrape("https://www.linkedin.com/in/satyanadella/")

    assert exc_info.value.__cause__ is original_error
    assert "Failed to scrape person profile" in str(exc_info.value)


# ===========================================================================
# 2. Browser Disconnect / Crash Handling
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_disconnect_handling(caplog):
    browser = MagicMock(spec=BrowserPort)
    browser.url = "https://www.linkedin.com/in/satyanadella/"
    browser.goto = AsyncMock()
    browser.extract_text_safe = AsyncMock(return_value="Satya Nadella")

    nav_item = MagicMock(spec=ElementPort)
    main_el = MagicMock(spec=ElementPort)
    main_el.query_selector_all = AsyncMock(return_value=[])
    main_el.inner_text = AsyncMock(return_value="Satya Nadella\nRedmond, WA")

    def dynamic_query(sel):
        if "captcha" in sel or "nav" in sel or "feed" in sel or "dialog" in sel:
            return [nav_item]
        if "main" in sel:
            return [main_el]
        if "img" in sel or "section" in sel:
            return []
        raise RuntimeError("Section query disconnected")



    browser.query_selector_all = AsyncMock(side_effect=dynamic_query)

    with caplog.at_level(logging.DEBUG):
        scraper = PersonScraper(browser)
        person = await scraper.scrape("https://www.linkedin.com/in/satyanadella/")

    assert person.name == "Satya Nadella"
    assert any("disconnected" in rec.message for rec in caplog.records)




# ===========================================================================
# 3. Rate-Limit Detection & Suggested Wait Time
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_detection_suggested_wait_time():
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge/"

    with pytest.raises(RateLimitError) as exc_info:
        await detect_rate_limit(page)

    assert exc_info.value.suggested_wait_time == 3600
    assert "security checkpoint" in str(exc_info.value).lower()


# ===========================================================================
# 4. Missing Required Field Enforcement & Context Logging
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_required_field_person_and_company_logged(caplog):
    browser = MagicMock(spec=BrowserPort)
    browser.url = "https://www.linkedin.com/feed/"
    browser.goto = AsyncMock()
    browser.extract_text_safe = AsyncMock(return_value="")
    browser.query_selector_all = AsyncMock(return_value=[])

    with caplog.at_level(logging.ERROR):
        # 1. Person
        person_scraper = PersonScraper(browser)
        with pytest.raises(RequiredFieldExtractionError) as p_exc:
            await person_scraper.scrape("https://www.linkedin.com/in/empty-profile/")
        assert p_exc.value.field_name == "name"
        assert p_exc.value.entity_url == "https://www.linkedin.com/in/empty-profile/"

        # 2. Company
        company_scraper = CompanyScraper(browser)
        with pytest.raises(RequiredFieldExtractionError) as c_exc:
            await company_scraper.scrape("https://www.linkedin.com/company/empty-corp/")
        assert c_exc.value.field_name == "name"
        assert c_exc.value.entity_url == "https://www.linkedin.com/company/empty-corp/"

    error_messages = [rec.message for rec in caplog.records if rec.levelno >= logging.ERROR]
    assert any("Failed to extract required field 'name' for person profile" in msg for msg in error_messages)
    assert any("Failed to extract required field 'name' for company" in msg for msg in error_messages)



# ===========================================================================
# 5. Auth / Session Challenge Detection & URL Logging
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_challenge_detection(caplog):
    page = MagicMock()
    # Initially on login page, then transitions to challenge after submit
    page.url = "https://www.linkedin.com/login"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()

    async def click_submit(*args, **kwargs):
        page.url = "https://www.linkedin.com/checkpoint/challenge/12345"

    page.click = AsyncMock(side_effect=click_submit)
    page.wait_for_url = AsyncMock()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationError) as exc_info:
            await login_with_credentials(page, email="user@example.com", password="SecretPassword123!", warm_up=False)

    assert "checkpoint" in str(exc_info.value).lower()
    assert "https://www.linkedin.com/checkpoint/challenge/12345" in str(exc_info.value)



# ===========================================================================
# 6. Log Audit: No Passwords, Tokens, or Raw Cookies Emitted
# ===========================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_log_sanitization_no_secrets(caplog):
    secret_password = "SuperSecretPassword987!"
    secret_cookie = "AQEDAT8z1234567890abcdefghijklmnopqrstuvwxyz"
    sensitive_email = "confidential_ceo@enterprise.com"

    page = MagicMock()
    page.url = "https://www.linkedin.com/login"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_url = AsyncMock()

    with caplog.at_level(logging.DEBUG):
        # 1. Login with credentials
        try:
            await login_with_credentials(
                page, email=sensitive_email, password=secret_password, warm_up=False
            )
        except Exception:
            pass

        # 2. Login with cookie
        page.add_cookies = AsyncMock()
        try:
            await login_with_cookie(page, cookie_value=secret_cookie)
        except Exception:
            pass

    all_logs = " ".join([rec.message for rec in caplog.records])

    # Assert secret credentials NEVER appear in raw logs
    assert secret_password not in all_logs
    assert secret_cookie not in all_logs
    assert sensitive_email not in all_logs  # should be redacted as con***
    assert "con***" in all_logs
