"""LinkedIn Scraper - Async Playwright-based scraper for LinkedIn."""

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("linkedin_scraper")
except Exception:  # pragma: no cover - fallback for editable/source trees
    __version__ = "3.1.2"

# Ports
# Callbacks
from .callbacks import (
    ConsoleCallback,
    JSONLogCallback,
    MultiCallback,
    ProgressCallback,
    SilentCallback,
)

# Core modules
from .core import (
    AuthenticationError,
    BrowserManager,
    ElementNotFoundError,
    # Exceptions
    LinkedInScraperException,
    NetworkError,
    PlaywrightBrowserAdapter,
    ProfileNotFoundError,
    RateLimitError,
    RequestThrottler,
    RequiredFieldExtractionError,
    ScrapingError,
    get_default_throttler,
    is_logged_in,
    load_credentials_from_env,
    login_with_cookie,
    login_with_credentials,
    wait_for_manual_login,
)

# Models
from .models import (
    Accomplishment,
    Company,
    CompanySummary,
    Contact,
    Education,
    Employee,
    Experience,
    Interest,
    Job,
    Person,
    Post,
)
from .ports import BrowserPort, ElementPort

# Scrapers
from .scrapers import (
    CompanyPostsScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
    PersonScraper,
)

# Search facade and workflow
from .search import (
    ExportFormat,
    LinkedInSearchFacade,
    SearchWorkflowResult,
    consume_search,
    execute_search_workflow,
    export_results,
    export_to_csv,
    export_to_json,
    export_to_jsonl,
)

__all__ = [
    # Version
    "__version__",
    # Ports
    "BrowserPort",
    "ElementPort",
    # Core
    "BrowserManager",
    "PlaywrightBrowserAdapter",
    "RequestThrottler",
    "get_default_throttler",
    "login_with_credentials",
    "login_with_cookie",
    "is_logged_in",
    "wait_for_manual_login",
    "load_credentials_from_env",
    # Scrapers
    "PersonScraper",
    "CompanyScraper",
    "JobScraper",
    "JobSearchScraper",
    "CompanyPostsScraper",
    # Exceptions
    "LinkedInScraperException",
    "AuthenticationError",
    "RateLimitError",
    "ElementNotFoundError",
    "ProfileNotFoundError",
    "NetworkError",
    "ScrapingError",
    "RequiredFieldExtractionError",
    # Callbacks
    "ProgressCallback",
    "ConsoleCallback",
    "SilentCallback",
    "JSONLogCallback",
    "MultiCallback",
    # Models
    "Person",
    "Experience",
    "Education",
    "Contact",
    "Accomplishment",
    "Interest",
    "Company",
    "CompanySummary",
    "Employee",
    "Job",
    "Post",
    # Search facade and workflow
    "LinkedInSearchFacade",
    "SearchWorkflowResult",
    "consume_search",
    "execute_search_workflow",
    "ExportFormat",
    "export_results",
    "export_to_csv",
    "export_to_json",
    "export_to_jsonl",
]
