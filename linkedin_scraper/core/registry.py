"""Registry for scraper services.

Allows new scraper services to register themselves by name instead of
requiring callers to know about every concrete class, keeping module
boundaries decoupled (in-process factory / plugin discovery).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class ScraperRegistry:
    """Maps service names to factories that construct scraper instances."""

    def __init__(self) -> None:
        self._factories: Dict[str, Callable[..., Any]] = {}
        self._bootstrap: Optional[Callable[["ScraperRegistry"], None]] = None

    def set_bootstrap(
        self, callback: Optional[Callable[["ScraperRegistry"], None]]
    ) -> None:
        """Defer default registration until first create()/available() use."""
        self._bootstrap = callback

    def _ensure_bootstrapped(self) -> None:
        if self._bootstrap is None:
            return
        callback = self._bootstrap
        self._bootstrap = None
        callback(self)

    def register(self, name: str, factory: Callable[..., Any]) -> None:
        """
        Register a factory (usually a class) under a service name.

        Args:
            name: Unique name for the service
            factory: Callable that constructs the service instance
        """
        self._factories[name] = factory

    def is_registered(self, name: str) -> bool:
        """Return True if ``name`` is already registered (does not bootstrap)."""
        return name in self._factories

    def has(self, name: str) -> bool:
        """Return True if a service is registered under ``name`` (bootstraps defaults)."""
        self._ensure_bootstrapped()
        return name in self._factories

    def create(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Instantiate a registered service by name.

        Args:
            name: Registered service name
            *args: Positional arguments forwarded to the factory
            **kwargs: Keyword arguments forwarded to the factory

        Returns:
            The constructed service instance

        Raises:
            KeyError: If no service is registered under the given name
        """
        self._ensure_bootstrapped()
        if name not in self._factories:
            raise KeyError(
                "Unknown scraper service: {}. Registered: {}".format(
                    name, list(self._factories)
                )
            )
        return self._factories[name](*args, **kwargs)

    def available(self) -> List[str]:
        """Return the names of all registered services."""
        self._ensure_bootstrapped()
        return list(self._factories.keys())


# Module-level default registry
default_registry = ScraperRegistry()
