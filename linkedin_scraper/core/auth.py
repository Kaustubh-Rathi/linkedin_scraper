"""Authentication functions for LinkedIn."""

import asyncio
import logging
import os
import time
from typing import Any, Optional, Tuple, Union

from dotenv import load_dotenv

from ..ports.browser import BrowserPort
from ..selectors import Auth as AuthSelectors
from .exceptions import AuthenticationError
from .rate_limit import detect_rate_limit

logger = logging.getLogger(__name__)


async def warm_up_browser(page: Union[BrowserPort, Any]) -> None:
    """
    Visit normal sites to gather cookies and appear more human-like.
    """
    sites = [
        "https://www.google.com",
        "https://www.wikipedia.org",
        "https://www.github.com",
    ]
    logger.info("Warming up browser by visiting normal sites...")
    for site in sites:
        try:
            await page.goto(site, wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(1)
            logger.debug("Visited warm-up site %s", site)
        except Exception as e:
            logger.debug("Could not visit warm-up site %s: %s", site, e)
            continue
    logger.info("Browser warm-up complete")


def load_credentials_from_env() -> Tuple[Optional[str], Optional[str]]:
    """Load LinkedIn credentials from .env file."""
    load_dotenv()
    email = os.getenv("LINKEDIN_EMAIL") or os.getenv("LINKEDIN_USERNAME")
    password = os.getenv("LINKEDIN_PASSWORD")
    return email, password


async def login_with_credentials(
    page: Union[BrowserPort, Any],
    email: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 30000,
    warm_up: bool = True,
) -> None:
    """Login to LinkedIn using email and password."""
    if not email or not password:
        env_email, env_password = load_credentials_from_env()
        email = email or env_email
        password = password or env_password

    if not email or not password:
        raise AuthenticationError(
            "LinkedIn credentials not provided. "
            "Either pass email/password parameters or set LINKEDIN_EMAIL "
            "and LINKEDIN_PASSWORD in your .env file."
        )

    if warm_up:
        await warm_up_browser(page)

    # Note: Do not log the password
    safe_identifier = email[:3] + "***" if len(email) > 3 else "***"
    logger.info("Initiating LinkedIn credential login for user: %s", safe_identifier)

    try:
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await detect_rate_limit(page)

        try:
            await page.wait_for_selector(
                AuthSelectors.LOGIN_USERNAME, timeout=timeout, state="visible"
            )
        except Exception as exc:
            if isinstance(exc, AuthenticationError):
                raise
            logger.error("Login form selector '#username' not found on page: %s", getattr(page, "url", ""))
            raise AuthenticationError(
                "Login form not found. LinkedIn may have changed their page structure "
                "or the site is experiencing issues."
            ) from exc

        await page.fill(AuthSelectors.LOGIN_USERNAME, email)
        await page.fill(AuthSelectors.LOGIN_PASSWORD, password)
        logger.debug("Credentials entered successfully")

        await page.click(AuthSelectors.LOGIN_SUBMIT)

        try:
            if hasattr(page, "wait_for_url"):
                await page.wait_for_url(
                    lambda url: "feed" in url or "checkpoint" in url or "authwall" in url or "challenge" in url,
                    timeout=timeout,
                )
        except Exception as nav_exc:
            current_url = getattr(page, "url", "")
            if "login" in current_url:
                logger.error("Login navigation failed; stayed on login URL: %s", current_url)
                raise AuthenticationError(
                    "Login failed. Please check your credentials. "
                    "The page did not navigate after clicking sign in."
                ) from nav_exc

        current_url = getattr(page, "url", "")
        if "checkpoint" in current_url or "challenge" in current_url:
            logger.warning("Security checkpoint encountered during login: %s", current_url)
            raise AuthenticationError(
                "LinkedIn security checkpoint detected. "
                "You may need to verify your identity manually. "
                "Consider using session persistence after manual verification. "
                f"Current URL: {current_url}"
            )

        if "authwall" in current_url:
            logger.warning("Authwall encountered during login: %s", current_url)
            raise AuthenticationError(
                "Authentication wall encountered. "
                "LinkedIn may be blocking automated access. "
                f"Current URL: {current_url}"
            )

        start_time = time.time()
        logged_in = False
        while (time.time() - start_time) * 1000 < 5000:
            if await is_logged_in(page):
                logger.info("✓ Successfully logged in to LinkedIn")
                logged_in = True
                break
            await asyncio.sleep(0.5)

        if not logged_in:
            logger.warning(
                "Could not verify login by finding navigation element. Proceeding anyway..."
            )

    except AuthenticationError:
        raise
    except Exception as e:
        logger.exception("Unexpected error during LinkedIn login: %s", e)
        raise AuthenticationError(f"Unexpected error during login: {e}") from e


async def login_with_cookie(page: Union[BrowserPort, Any], cookie_value: str) -> None:
    """Login to LinkedIn using li_at cookie."""
    logger.info("Initiating LinkedIn cookie authentication...")
    try:
        cookie = {
            "name": "li_at",
            "value": cookie_value,
            "domain": ".linkedin.com",
            "path": "/",
        }
        if hasattr(page, "add_cookies"):
            await page.add_cookies([cookie])
        elif hasattr(page, "context") and hasattr(page.context, "add_cookies"):
            await page.context.add_cookies([cookie])

        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

        current_url = getattr(page, "url", "")
        if "login" in current_url or "authwall" in current_url or "checkpoint" in current_url:
            logger.warning("Cookie authentication landed on unauthenticated URL: %s", current_url)
            raise AuthenticationError(
                "Cookie authentication failed. The cookie may be expired or invalid."
            )

        start_time = time.time()
        logged_in = False
        while (time.time() - start_time) * 1000 < 5000:
            if await is_logged_in(page):
                logger.info("✓ Successfully authenticated with cookie")
                logged_in = True
                break
            await asyncio.sleep(0.5)

        if not logged_in:
            logger.warning(
                "Could not verify cookie login via navigation element. Proceeding anyway..."
            )
    except AuthenticationError:
        raise
    except Exception as e:
        logger.exception("Cookie authentication error: %s", e)
        raise AuthenticationError(f"Cookie authentication error: {e}") from e


async def is_logged_in(page: Union[BrowserPort, Any]) -> bool:
    """Check if currently logged in to LinkedIn."""
    try:
        current_url = getattr(page, "url", "") or ""
        auth_blockers = [
            "/login",
            "/authwall",
            "/checkpoint",
            "/challenge",
            "/uas/login",
            "/uas/consumer-email-challenge",
        ]
        if any(pattern in current_url for pattern in auth_blockers):
            return False

        has_nav_elements = False
        if hasattr(page, "query_selector_all"):
            nav_items = await page.query_selector_all(AuthSelectors.NAV_MARKERS)
            has_nav_elements = len(nav_items) > 0
        elif hasattr(page, "locator"):
            loc = page.locator(AuthSelectors.NAV_MARKERS)
            count = await loc.count() if hasattr(loc, "count") else 0
            has_nav_elements = count > 0

        authenticated_only_pages = [
            "/feed",
            "/mynetwork",
            "/messaging",
            "/notifications",
        ]
        is_authenticated_page = any(
            pattern in current_url for pattern in authenticated_only_pages
        )

        return bool(has_nav_elements or is_authenticated_page)
    except Exception as e:
        logger.debug("Non-fatal evaluation error while checking login state: %s", e)
        return False


async def wait_for_manual_login(
    page: Union[BrowserPort, Any], timeout: int = 300000
) -> None:
    """Wait for user to manually complete login."""
    logger.info(
        "⏳ Please complete the login process manually in the browser. Waiting up to %s ms...",
        timeout,
    )
    start_time = asyncio.get_event_loop().time()

    while True:
        if await is_logged_in(page):
            logger.info("✓ Manual login completed successfully")
            return

        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        if elapsed > timeout:
            raise AuthenticationError(
                "Manual login timeout. Please try again and complete login faster."
            )
        await asyncio.sleep(1)
