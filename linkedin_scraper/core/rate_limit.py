"""Rate limit/security checkpoint detection, plus proactive request throttling.

Detection (``detect_rate_limit``) reacts to LinkedIn's signals; throttling
(``RequestThrottler``) is proactive: it serializes page requests (one at a
time) and enforces a minimum interval between them so sessions stay well
below LinkedIn's automation thresholds.
"""

import asyncio
import logging
import os
import random
import time
from typing import Any, Optional, Union

from ..ports.browser import BrowserPort
from ..selectors import RateLimit as RateLimitSelectors
from .exceptions import RateLimitError

logger = logging.getLogger(__name__)


class RequestThrottler:
    """Serialize and pace outbound page requests.

    Guarantees:
      * **one request at a time** — an async lock serializes callers;
      * **minimum spacing** — at least ``min_interval`` seconds (+ up to
        ``jitter`` seconds of random delay) pass between consecutive requests;
      * **optional budget** — when ``max_requests_per_hour`` is set, exceeding
        it raises :class:`RateLimitError` instead of hammering LinkedIn.

    The default instance's interval is configurable via the
    ``LINKEDIN_MIN_REQUEST_INTERVAL`` environment variable (seconds).
    """

    def __init__(
        self,
        min_interval: float = 2.0,
        jitter: float = 1.0,
        max_requests_per_hour: Optional[int] = None,
    ) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self.jitter = max(0.0, float(jitter))
        self.max_requests_per_hour = max_requests_per_hour
        self._lock = asyncio.Lock()
        self._last_request_at: Optional[float] = None
        self._request_times: list[float] = []

    async def acquire(self) -> None:
        """Wait until it is safe to issue the next request, then reserve the slot."""
        async with self._lock:
            now = time.monotonic()
            if self._last_request_at is not None and self.min_interval > 0:
                wait = self.min_interval - (now - self._last_request_at)
                if wait > 0:
                    wait += random.uniform(0.0, self.jitter)
                    logger.debug("Throttling next request for %.2fs", wait)
                    await asyncio.sleep(wait)

            if self.max_requests_per_hour is not None:
                cutoff = time.monotonic() - 3600
                self._request_times = [t for t in self._request_times if t > cutoff]
                if len(self._request_times) >= self.max_requests_per_hour:
                    raise RateLimitError(
                        "Local hourly request budget exhausted "
                        f"({self.max_requests_per_hour}/h).",
                        suggested_wait_time=3600,
                    )

            self._last_request_at = time.monotonic()
            self._request_times.append(self._last_request_at)

    async def __aenter__(self) -> "RequestThrottler":
        await self.acquire()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None


_default_throttler: Optional[RequestThrottler] = None


def get_default_throttler() -> RequestThrottler:
    """Return the process-wide shared throttler (one request at a time globally)."""
    global _default_throttler
    if _default_throttler is None:
        try:
            interval = float(os.getenv("LINKEDIN_MIN_REQUEST_INTERVAL", "2.0"))
        except ValueError:
            interval = 2.0
        _default_throttler = RequestThrottler(min_interval=interval)
    return _default_throttler


async def detect_rate_limit(page: Union[BrowserPort, Any]) -> None:
    """
    Detect if LinkedIn has rate limited the session or presented a security barrier.
    
    Args:
        page: BrowserPort instance or Playwright page object
        
    Raises:
        RateLimitError: If rate limiting or security checkpoint is detected
    """
    current_url = getattr(page, "url", "") or ""
    if callable(current_url):
        try:
            current_url = current_url()
        except Exception:
            current_url = ""

    # 1. URL-level detection
    if isinstance(current_url, str) and any(k in current_url for k in ("checkpoint", "authwall", "challenge")):
        logger.warning("LinkedIn security checkpoint detected at URL: %s", current_url)
        raise RateLimitError(
            "LinkedIn security checkpoint detected. "
            "You may need to verify your identity or wait before continuing.",
            suggested_wait_time=3600  # 1 hour
        )

    # 2. CAPTCHA iframe / challenge element detection
    try:
        if hasattr(page, "locator"):
            loc = page.locator(RateLimitSelectors.CAPTCHA)
            if hasattr(loc, "__await__"):
                loc = await loc
            count = 0
            if hasattr(loc, "count"):
                res = loc.count()
                count = (await res) if hasattr(res, "__await__") else res
            if count and count > 0:
                logger.warning("CAPTCHA challenge detected on page.")
                raise RateLimitError(
                    "CAPTCHA challenge detected. Manual intervention required.",
                    suggested_wait_time=3600,
                )
        elif hasattr(page, "query_selector_all"):
            captcha_elements = await page.query_selector_all(RateLimitSelectors.CAPTCHA)
            for el in captcha_elements:
                src = (await el.get_attribute("src") or "") if hasattr(el, "get_attribute") else ""
                title = (await el.get_attribute("title") or "") if hasattr(el, "get_attribute") else ""
                if isinstance(src, str) and isinstance(title, str):
                    if "captcha" in src.lower() or "captcha" in title.lower() or "challenge" in src.lower():
                        logger.warning("CAPTCHA challenge detected on page.")
                        raise RateLimitError(
                            "CAPTCHA challenge detected. Manual intervention required.",
                            suggested_wait_time=3600,
                        )
    except RateLimitError:
        raise
    except Exception as exc:
        logger.debug("Non-fatal error inspecting CAPTCHA frames: %s", exc)

    # 3. Rate-limit message text inspection
    # Look for specific error containers, not the entire body, to avoid
    # false positives from normal LinkedIn UI text that mentions these phrases.
    try:
        rate_limit_text: Union[str, Any, None] = None
        # LinkedIn rate-limit messages typically appear in specific containers
        rate_limit_selectors = list(RateLimitSelectors.BANNERS)
        for selector in rate_limit_selectors:
            try:
                if hasattr(page, "locator"):
                    loc = page.locator(selector)
                    loc = (await loc) if hasattr(loc, "__await__") else loc
                    if hasattr(loc, "count"):
                        count_res = loc.count()
                        count = (await count_res) if hasattr(count_res, "__await__") else count_res
                        if count and count > 0:
                            if hasattr(loc, "text_content"):
                                text_res = loc.text_content(timeout=1000)
                                rate_limit_text = (await text_res) if hasattr(text_res, "__await__") else text_res
                            break
                elif hasattr(page, "query_selector_all"):
                    elements = await page.query_selector_all(selector)
                    if elements:
                        text_res = elements[0].text_content(timeout=1000)
                        rate_limit_text = (await text_res) if hasattr(text_res, "__await__") else text_res
                        break
            except Exception:
                continue

        # Fallback: check for specific known rate-limit message elements
        if not rate_limit_text and hasattr(page, "locator"):
            try:
                loc = page.locator('div:has-text("Too Many Requests"), div:has-text("Rate Limit"), div:has-text("Slow Down")')
                loc = (await loc) if hasattr(loc, "__await__") else loc
                if hasattr(loc, "count"):
                    count_res = loc.count()
                    count = (await count_res) if hasattr(count_res, "__await__") else count_res
                    if count and count > 0:
                        if hasattr(loc, "text_content"):
                            text_res = loc.text_content(timeout=1000)
                            rate_limit_text = (await text_res) if hasattr(text_res, "__await__") else text_res
            except Exception:
                pass

        if rate_limit_text and isinstance(rate_limit_text, str):
            text_lower = rate_limit_text.lower()
            if any(
                phrase in text_lower
                for phrase in [
                    "too many requests",
                    "rate limit",
                    "slow down",
                    "try again later",
                ]
            ):
                logger.warning("Rate limit message detected on page: %s", current_url)
                raise RateLimitError(
                    "Rate limit message detected on page.",
                    suggested_wait_time=1800,  # 30 minutes
                )
    except RateLimitError:
        raise
    except Exception as exc:
        logger.debug("Non-fatal error inspecting rate limit text: %s", exc)
