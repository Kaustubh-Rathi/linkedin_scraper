"""Shared fakes/helpers for unit tests.

None of these fixtures touch a real browser or the network; they provide
lightweight stand-ins for Playwright's ``Page``/``Locator`` objects so pure
orchestration logic can be exercised in isolation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "html"


class FakeLocator:
    """Minimal stand-in for a Playwright ``Locator``."""

    def __init__(
        self,
        count: int = 0,
        text: Optional[str] = None,
        attribute: Optional[str] = None,
        raise_on_count: Optional[Exception] = None,
        raise_on_text: Optional[Exception] = None,
        raise_on_attribute: Optional[Exception] = None,
        children: Optional[List["FakeLocator"]] = None,
    ):
        self._count = count
        self._text = text
        self._attribute = attribute
        self._raise_on_count = raise_on_count
        self._raise_on_text = raise_on_text
        self._raise_on_attribute = raise_on_attribute
        self._children = children or []

    @property
    def first(self) -> "FakeLocator":
        return self

    async def count(self) -> int:
        if self._raise_on_count:
            raise self._raise_on_count
        return self._count

    async def text_content(self, timeout: Optional[float] = None) -> Optional[str]:
        if self._raise_on_text:
            raise self._raise_on_text
        return self._text

    async def inner_text(self) -> str:
        return self._text or ""

    async def get_attribute(self, name: str, timeout: Optional[float] = None) -> Optional[str]:
        if self._raise_on_attribute:
            raise self._raise_on_attribute
        return self._attribute

    async def is_visible(self, timeout: Optional[float] = None) -> bool:
        return self._count > 0

    async def click(self, timeout: Optional[float] = None) -> None:
        return None

    async def wait_for(self, timeout: Optional[float] = None) -> None:
        return None

    async def scroll_into_view_if_needed(self) -> None:
        return None

    def locator(self, selector: str) -> "FakeLocator":
        return self

    async def all(self) -> List["FakeLocator"]:
        if self._children:
            return list(self._children)
        return []


class FakeContext:
    """Stand-in for ``BrowserContext`` (cookie login)."""

    def __init__(self) -> None:
        self.cookies: List[Dict[str, Any]] = []

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        self.cookies.extend(cookies)


class FakePage:
    """Minimal stand-in for a Playwright ``Page`` used by rate-limit/auth tests."""

    def __init__(
        self,
        url: str = "https://www.linkedin.com/in/example/",
        locator_factory: Optional[Callable[[str], FakeLocator]] = None,
        evaluate_results: Optional[List[Any]] = None,
        routes: Optional[Dict[str, str]] = None,
    ):
        self.url = url
        self._locator_factory = locator_factory or (lambda selector: FakeLocator())
        self._evaluate_results = list(evaluate_results or [])
        self.goto_calls: List[Any] = []
        self.fill_calls: List[Any] = []
        self.click_calls: List[Any] = []
        self.context = FakeContext()
        self.keyboard = self
        self._routes = dict(routes or {})
        self._wait_for_url_target: Optional[str] = None

    def locator(self, selector: str) -> FakeLocator:
        return self._locator_factory(selector)

    async def evaluate(self, script: str) -> Any:
        if self._evaluate_results:
            return self._evaluate_results.pop(0)
        return None

    async def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_calls.append((url, kwargs))
        for prefix, target in self._routes.items():
            if prefix in url:
                self.url = target
                return
        self.url = url

    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[float] = None,
        state: Optional[str] = None,
    ) -> None:
        return None

    async def wait_for_load_state(self, state: str = "load", timeout: Optional[float] = None) -> None:
        return None

    async def wait_for_timeout(self, timeout: float) -> None:
        return None

    async def wait_for_url(self, predicate, timeout: Optional[float] = None) -> None:
        if self._wait_for_url_target:
            self.url = self._wait_for_url_target
            return
        if callable(predicate) and predicate(self.url):
            return
        if isinstance(predicate, str) and predicate in self.url:
            return

    async def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))

    async def click(self, selector: str) -> None:
        self.click_calls.append(selector)

    async def press(self, key: str) -> None:
        return None

    async def bring_to_front(self) -> None:
        return None


@pytest.fixture
def fake_locator_cls():
    """Return the ``FakeLocator`` class (instantiate as needed per test)."""
    return FakeLocator


@pytest.fixture
def fake_page_cls():
    """Return the ``FakePage`` class (instantiate as needed per test)."""
    return FakePage


@pytest.fixture
def html_fixtures_dir() -> Path:
    """Directory containing static HTML snapshots for scraper unit tests."""
    return FIXTURES_DIR
