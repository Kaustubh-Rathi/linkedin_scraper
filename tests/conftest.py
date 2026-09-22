"""
Pytest configuration and fixtures for linkedin_scraper tests.
"""
import pytest
from pathlib import Path
from linkedin_scraper import BrowserManager
from linkedin_scraper.callbacks import SilentCallback
from linkedin_scraper.core.rate_limit import get_default_throttler


@pytest.fixture(autouse=True)
def _disable_throttle_delays():
    """Zero out the shared request throttler so offline tests run instantly.

    Production code still throttles (one request at a time, min interval);
    tests must not sleep between navigations.
    """
    throttler = get_default_throttler()
    saved_interval, saved_jitter = throttler.min_interval, throttler.jitter
    throttler.min_interval = 0.0
    throttler.jitter = 0.0
    yield
    throttler.min_interval, throttler.jitter = saved_interval, saved_jitter


# Session file path
SESSION_FILE = Path(__file__).parent.parent / "linkedin_session.json"


@pytest.fixture
async def browser():
    """
    Fixture that provides a BrowserManager instance.
    Automatically loads session if available.
    
    Note: Uses headless=False for LinkedIn compatibility.
    LinkedIn may block or behave differently in headless mode.
    """
    async with BrowserManager(headless=False) as browser_manager:
        # Try to load session if it exists
        if SESSION_FILE.exists():
            await browser_manager.load_session(str(SESSION_FILE))
        yield browser_manager


@pytest.fixture
async def browser_with_session():
    """
    Fixture that provides a BrowserManager with loaded session.
    Skips test if session file doesn't exist.
    
    Note: Uses headless=False for LinkedIn compatibility.
    LinkedIn may block or behave differently in headless mode.
    """
    if not SESSION_FILE.exists():
        pytest.skip("Session file not found. See README for session setup instructions.")

    async with BrowserManager(headless=False) as browser_manager:
        await browser_manager.load_session(str(SESSION_FILE))
        yield browser_manager


@pytest.fixture
def silent_callback():
    """Fixture that provides a SilentCallback for testing without output."""
    return SilentCallback()


# Test profile URLs
@pytest.fixture
def test_profile_urls():
    """Fixture that provides test LinkedIn profile URLs."""
    return {
        "bill_gates": "https://www.linkedin.com/in/williamhgates/",
        "satya_nadella": "https://www.linkedin.com/in/satyanadella/",
        "reid_hoffman": "https://www.linkedin.com/in/reidhoffman/"
    }


@pytest.fixture
def test_company_urls():
    """Fixture that provides test LinkedIn company URLs."""
    return {
        "microsoft": "https://www.linkedin.com/company/microsoft/",
        "google": "https://www.linkedin.com/company/google/",
        "apple": "https://www.linkedin.com/company/apple/"
    }


@pytest.fixture
def test_job_search_params():
    """Fixture that provides test job search parameters."""
    return {
        "keywords": "software engineer",
        "location": "San Francisco, CA",
        "limit": 5
    }


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring LinkedIn session"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "live: mark test as live E2E test requiring real LinkedIn network and authentication"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test requiring full setup"
    )
