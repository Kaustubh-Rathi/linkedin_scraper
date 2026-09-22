"""Browser abstraction layer and ports.

This module defines the BrowserPort protocol and supporting contracts,
abstracting browser operations away from Playwright or any specific automation engine.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ElementPort(Protocol):
    """Abstraction for DOM element interactions."""

    async def text_content(self, timeout: float = 2000) -> str | None:
        """Extract text content of element."""
        ...

    async def inner_text(self) -> str:
        """Extract rendered text content of element."""
        ...

    async def get_attribute(self, name: str, timeout: float = 2000) -> str | None:
        """Get attribute value of element."""
        ...

    async def is_visible(self, timeout: float = 1000) -> bool:
        """Check if element is visible."""
        ...

    async def click(self) -> None:
        """Click element."""
        ...

    async def query_selector_all(self, selector: str) -> list[ElementPort]:
        """Find all matching child elements as ElementPort list."""
        ...


@runtime_checkable
class BrowserPort(Protocol):
    """Abstraction for browser navigation, state, and interaction capabilities."""

    @property
    def url(self) -> str:
        """Get current page URL."""
        ...

    async def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: float = 60000,
    ) -> None:
        """Navigate to URL and wait for load state."""
        ...

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 5000,
        state: str = "visible",
    ) -> None:
        """Wait for element matching selector to reach state."""
        ...

    async def wait_for_load_state(
        self,
        state: str = "domcontentloaded",
        timeout: float = 30000,
    ) -> None:
        """Wait for specific load state."""
        ...

    async def wait_for_url(
        self,
        predicate_or_url: Any,
        timeout: float = 30000,
    ) -> None:
        """Wait for URL to match pattern or predicate."""
        ...

    async def wait_for_timeout(self, timeout: float) -> None:
        """Pause execution for specified duration in milliseconds."""
        ...

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        """Evaluate JavaScript expression on page."""
        ...

    async def extract_text_safe(
        self,
        selector: str,
        default: str = "",
        timeout: float = 2000,
    ) -> str:
        """Safely extract text from element, returning default on failure."""
        ...

    async def fill(self, selector: str, value: str) -> None:
        """Fill input field matching selector."""
        ...

    async def click(self, selector: str) -> None:
        """Click element matching selector."""
        ...

    async def locator(self, selector: str) -> Any:
        """Return element or locator matching selector."""
        ...

    async def query_selector_all(self, selector: str) -> list[ElementPort]:
        """Find all matching elements as ElementPort list."""
        ...

    async def bring_to_front(self) -> None:
        """Bring page to front / focus."""
        ...

    async def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """Add cookies to current browser context."""
        ...

    async def keyboard_press(self, key: str) -> None:
        """Press keyboard key."""
        ...
