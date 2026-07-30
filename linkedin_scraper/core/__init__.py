"""Core modules for LinkedIn scraper."""

from .browser import BrowserManager
from .auth import (
    login_with_credentials,
    login_with_cookie,
    is_logged_in,
    wait_for_manual_login,
    load_credentials_from_env,
    warm_up_browser
)
from .exceptions import (
    LinkedInScraperException,
    AuthenticationError,
    RateLimitError,
    ElementNotFoundError,
    ProfileNotFoundError,
    NetworkError,
    ScrapingError
)
from .retry import retry_async
from .rate_limit import detect_rate_limit
from .page_actions import (
    wait_for_element_smart,
    extract_text_safe,
    scroll_to_bottom,
    scroll_to_half,
    click_see_more_buttons,
    handle_modal_close,
    is_page_loaded
)
from .registry import ScraperRegistry, default_registry

__all__ = [
    # Browser
    'BrowserManager',
    # Auth
    'login_with_credentials',
    'login_with_cookie',
    'is_logged_in',
    'wait_for_manual_login',
    'load_credentials_from_env',
    'warm_up_browser',
    # Exceptions
    'LinkedInScraperException',
    'AuthenticationError',
    'RateLimitError',
    'ElementNotFoundError',
    'ProfileNotFoundError',
    'NetworkError',
    'ScrapingError',
    # Utils
    'retry_async',
    'detect_rate_limit',
    'wait_for_element_smart',
    'extract_text_safe',
    'scroll_to_bottom',
    'scroll_to_half',
    'click_see_more_buttons',
    'handle_modal_close',
    'is_page_loaded',
    # Registry
    'ScraperRegistry',
    'default_registry',
]
