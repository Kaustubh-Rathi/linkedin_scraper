"""Core modules for LinkedIn scraper."""

from ..ports.browser import BrowserPort, ElementPort
from .auth import (
    is_logged_in,
    load_credentials_from_env,
    login_with_cookie,
    login_with_credentials,
    wait_for_manual_login,
    warm_up_browser,
)
from .browser import BrowserManager, PlaywrightBrowserAdapter, PlaywrightElementAdapter
from .exceptions import (
    AuthenticationError,
    ElementNotFoundError,
    LinkedInScraperException,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    RequiredFieldExtractionError,
    ScrapingError,
)
from .page_actions import (
    click_see_more_buttons,
    extract_text_safe,
    handle_modal_close,
    is_page_loaded,
    scroll_to_bottom,
    scroll_to_half,
    wait_for_element_smart,
)
from .rate_limit import detect_rate_limit

__all__ = [
    # Browser & Ports
    'BrowserManager',
    'PlaywrightBrowserAdapter',
    'PlaywrightElementAdapter',
    'BrowserPort',
    'ElementPort',
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
    'RequiredFieldExtractionError',
    # Utils
    'detect_rate_limit',
    'wait_for_element_smart',
    'extract_text_safe',
    'scroll_to_bottom',
    'scroll_to_half',
    'click_see_more_buttons',
    'handle_modal_close',
    'is_page_loaded',
]
