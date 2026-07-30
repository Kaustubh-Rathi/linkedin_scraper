"""Rate limit and security checkpoint detection."""

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .exceptions import RateLimitError


async def detect_rate_limit(page: Page) -> None:
    """
    Detect if LinkedIn has rate limited the session.
    
    Args:
        page: Playwright page object
        
    Raises:
        RateLimitError: If rate limiting is detected
    """
    # Check for common rate limit indicators
    
    # Check URL for security challenges
    current_url = page.url
    if 'linkedin.com/checkpoint' in current_url or 'authwall' in current_url:
        raise RateLimitError(
            "LinkedIn security checkpoint detected. "
            "You may need to verify your identity or wait before continuing.",
            suggested_wait_time=3600  # 1 hour
        )
    
    # Check for CAPTCHA
    try:
        captcha = await page.locator('iframe[title*="captcha" i], iframe[src*="captcha" i]').count()
        if captcha > 0:
            raise RateLimitError(
                "CAPTCHA challenge detected. Manual intervention required.",
                suggested_wait_time=3600
            )
    except RateLimitError:
        raise
    except Exception:
        pass
    
    # Check for rate limit messages
    try:
        body_text = await page.locator('body').text_content(timeout=1000)
        if body_text:
            body_lower = body_text.lower()
            if any(phrase in body_lower for phrase in [
                'too many requests',
                'rate limit',
                'slow down',
                'try again later'
            ]):
                raise RateLimitError(
                    "Rate limit message detected on page.",
                    suggested_wait_time=1800  # 30 minutes
                )
    except PlaywrightTimeoutError:
        pass
