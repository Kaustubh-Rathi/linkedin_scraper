"""Tests for linkedin_scraper.core.retry.retry_async."""
import asyncio

import pytest

from linkedin_scraper.core.retry import retry_async


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_succeeds_first_try(monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    @retry_async(max_attempts=3, backoff=2.0)
    async def flaky():
        calls.append(1)
        return "ok"

    result = await flaky()

    assert result == "ok"
    assert len(calls) == 1
    assert sleep_calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_retries_then_succeeds(monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    @retry_async(max_attempts=3, backoff=2.0, exceptions=(ValueError,))
    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ValueError("not yet")
        return "success"

    result = await flaky()

    assert result == "success"
    assert attempts["count"] == 3
    # Two failures -> two waits, with exponential backoff (2**0, 2**1)
    assert sleep_calls == [1.0, 2.0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_exhausts_and_reraises(monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    @retry_async(max_attempts=3, backoff=2.0, exceptions=(ValueError,))
    async def always_fails():
        attempts["count"] += 1
        raise ValueError(f"attempt {attempts['count']}")

    with pytest.raises(ValueError, match="attempt 3"):
        await always_fails()

    assert attempts["count"] == 3
    # Only max_attempts - 1 sleeps happen (no wait after final failed attempt)
    assert len(sleep_calls) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_only_catches_specified_exceptions(monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    @retry_async(max_attempts=3, backoff=2.0, exceptions=(ValueError,))
    async def raises_type_error():
        raise TypeError("not retried")

    with pytest.raises(TypeError):
        await raises_type_error()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_preserves_function_metadata():
    @retry_async(max_attempts=2)
    async def documented():
        """A documented function."""
        return None

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "A documented function."
