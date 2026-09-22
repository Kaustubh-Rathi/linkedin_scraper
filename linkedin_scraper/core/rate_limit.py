"""Rate limit and security checkpoint detection."""

import logging
from typing import Any, Union

from ..ports.browser import BrowserPort
from .exceptions import RateLimitError

logger = logging.getLogger(__name__)


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
            loc = page.locator(
                'iframe[title*="captcha" i], iframe[src*="captcha" i], div[class*="captcha" i]'
            )
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
            captcha_elements = await page.query_selector_all(
                'iframe[title*="captcha" i], iframe[src*="captcha" i], div[class*="captcha" i]'
            )
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
        rate_limit_selectors = [
            '[data-testid="rate-limit-banner"]',
            '.rate-limit-message',
            '.artdeco-toast-item--error',
            '.artdeco-banner--error',
            '[class*="rate-limit"]',
            '[class*="rateLimit"]',
        ]
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
