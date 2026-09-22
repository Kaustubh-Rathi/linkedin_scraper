"""Tests for linkedin_scraper.core.exceptions."""
import pytest

from linkedin_scraper.core.exceptions import (
    AuthenticationError,
    ElementNotFoundError,
    LinkedInScraperException,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ScrapingError,
)


@pytest.mark.unit
def test_rate_limit_error_default_suggested_wait_time():
    error = RateLimitError("slow down")
    assert error.suggested_wait_time == 300
    assert str(error) == "slow down"


@pytest.mark.unit
def test_rate_limit_error_custom_suggested_wait_time():
    error = RateLimitError("checkpoint hit", suggested_wait_time=3600)
    assert error.suggested_wait_time == 3600


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc_cls",
    [
        AuthenticationError,
        RateLimitError,
        ElementNotFoundError,
        ProfileNotFoundError,
        NetworkError,
        ScrapingError,
    ],
)
def test_all_exceptions_are_linkedin_scraper_exceptions(exc_cls):
    if exc_cls is RateLimitError:
        instance = exc_cls("message")
    else:
        instance = exc_cls("message")
    assert isinstance(instance, LinkedInScraperException)
    assert isinstance(instance, Exception)


@pytest.mark.unit
def test_linkedin_scraper_exception_is_base_exception():
    assert issubclass(LinkedInScraperException, Exception)


@pytest.mark.unit
def test_exceptions_are_distinct_types():
    assert not isinstance(AuthenticationError("x"), RateLimitError)
    assert not isinstance(RateLimitError("x"), AuthenticationError)
