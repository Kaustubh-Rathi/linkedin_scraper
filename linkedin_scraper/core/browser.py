"""Browser lifecycle management and Playwright adapter implementation."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Locator,
    Page,
    Playwright,
    ViewportSize,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from ..ports.browser import BrowserPort, ElementPort
from .exceptions import NetworkError

logger = logging.getLogger(__name__)


class PlaywrightElementAdapter:
    """Adapter wrapping Playwright Locator or ElementHandle to conform to ElementPort."""

    def __init__(self, target: Union[Locator, ElementHandle, Any]):
        self._target = target

    async def text_content(self, timeout: float = 2000) -> Optional[str]:
        if isinstance(self._target, ElementHandle):
            return await self._target.text_content()
        if hasattr(self._target, "text_content"):
            return await self._target.text_content(timeout=timeout)
        return None

    async def inner_text(self) -> str:
        if isinstance(self._target, ElementHandle):
            return await self._target.inner_text()
        if hasattr(self._target, "inner_text"):
            return await self._target.inner_text()
        text = await self.text_content()
        return text or ""

    async def get_attribute(self, name: str, timeout: float = 2000) -> Optional[str]:
        if isinstance(self._target, ElementHandle):
            return await self._target.get_attribute(name)
        if hasattr(self._target, "get_attribute"):
            return await self._target.get_attribute(name, timeout=timeout)
        return None

    async def is_visible(self, timeout: float = 1000) -> bool:
        if isinstance(self._target, ElementHandle):
            return await self._target.is_visible()
        if hasattr(self._target, "is_visible"):
            return await self._target.is_visible(timeout=timeout)
        return False

    async def click(self) -> None:
        if hasattr(self._target, "click"):
            await self._target.click()

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        if hasattr(self._target, "query_selector_all"):
            elements = await self._target.query_selector_all(selector)
            return [PlaywrightElementAdapter(e) for e in elements]
        if hasattr(self._target, "locator"):
            locator = self._target.locator(selector)
            if hasattr(locator, "all"):
                locators = await locator.all()
                return [PlaywrightElementAdapter(item) for item in locators]
        return []


class PlaywrightBrowserAdapter:
    """Adapter wrapping Playwright Page object to conform to BrowserPort protocol."""

    def __init__(self, page: Page):
        self._page = page

    @property
    def raw_page(self) -> Page:
        """Expose raw Playwright page for infrastructure/internal mechanics when strictly needed."""
        return self._page

    @property
    def url(self) -> str:
        return self._page.url

    async def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: float = 60000,
    ) -> None:
        await self._page.goto(url, wait_until=wait_until, timeout=timeout)  # type: ignore

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 5000,
        state: str = "visible",
    ) -> None:
        await self._page.wait_for_selector(selector, timeout=timeout, state=state)  # type: ignore

    async def wait_for_load_state(
        self,
        state: str = "domcontentloaded",
        timeout: float = 30000,
    ) -> None:
        await self._page.wait_for_load_state(state, timeout=timeout)  # type: ignore

    async def wait_for_url(
        self,
        predicate_or_url: Any,
        timeout: float = 30000,
    ) -> None:
        await self._page.wait_for_url(predicate_or_url, timeout=timeout)

    async def wait_for_timeout(self, timeout: float) -> None:
        await self._page.wait_for_timeout(timeout)

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        if arg is not None:
            return await self._page.evaluate(expression, arg)
        return await self._page.evaluate(expression)

    async def extract_text_safe(
        self,
        selector: str,
        default: str = "",
        timeout: float = 2000,
    ) -> str:
        if hasattr(self._page, "extract_text_safe"):
            res = await self._page.extract_text_safe(selector, default, timeout)
            return str(res) if res is not None else default
        try:
            if hasattr(self._page, "locator"):
                element = self._page.locator(selector).first
                text = await element.text_content(timeout=timeout)
                return text.strip() if text else default
            elements = await self.query_selector_all(selector)
            if elements:
                text = await elements[0].text_content(timeout=timeout)
                return text.strip() if text else default
            return default
        except (PlaywrightTimeoutError, asyncio.TimeoutError):
            return default
        except Exception:
            return default

    async def fill(self, selector: str, value: str) -> None:
        await self._page.fill(selector, value)

    async def click(self, selector: str) -> None:
        await self._page.click(selector)

    async def locator(self, selector: str) -> Any:
        if hasattr(self._page, "locator"):
            return self._page.locator(selector)
        return None

    async def query_selector_all(self, selector: str) -> List[ElementPort]:
        if hasattr(self._page, "query_selector_all"):
            elements = await self._page.query_selector_all(selector)
            return [
                e if isinstance(e, PlaywrightElementAdapter) else PlaywrightElementAdapter(e)
                for e in elements
            ]
        elif hasattr(self._page, "locator"):
            loc = self._page.locator(selector)
            items = await loc.all()
            return [PlaywrightElementAdapter(i) for i in items]
        return []

    async def bring_to_front(self) -> None:
        await self._page.bring_to_front()

    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        await self._page.context.add_cookies(cookies)  # type: ignore[arg-type]

    async def keyboard_press(self, key: str) -> None:
        await self._page.keyboard.press(key)


class BrowserManager:
    """Async context manager for Playwright browser lifecycle."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[ViewportSize] = None,
        user_agent: Optional[str] = None,
        **launch_options: Any
    ):
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport: ViewportSize = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.launch_options = launch_options

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._adapter: Optional[PlaywrightBrowserAdapter] = None
        self._is_authenticated = False

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def start(self) -> None:
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                **self.launch_options
            )

            logger.info(f"Browser launched (headless={self.headless})")

            context_options: Dict[str, Any] = {
                "viewport": self.viewport,
            }
            if self.user_agent:
                context_options["user_agent"] = self.user_agent

            self._context = await self._browser.new_context(**context_options)
            self._page = await self._context.new_page()
            self._adapter = PlaywrightBrowserAdapter(self._page)

            logger.info("Browser context and page created")

        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}") from e

    async def close(self) -> None:
        try:
            if self._page:
                try:
                    await self._page.close()
                except Exception as page_err:
                    logger.debug("Error closing page: %s", page_err)
                finally:
                    self._page = None
                    self._adapter = None

            if self._context:
                try:
                    await self._context.close()
                except Exception as ctx_err:
                    logger.debug("Error closing context: %s", ctx_err)
                finally:
                    self._context = None

            if self._browser:
                try:
                    await self._browser.close()
                except Exception as br_err:
                    logger.debug("Error closing browser: %s", br_err)
                finally:
                    self._browser = None

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as pw_err:
                    logger.debug("Error stopping playwright: %s", pw_err)
                finally:
                    self._playwright = None

            logger.info("Browser closed")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    def get_browser_port(self) -> BrowserPort:
        """Get the BrowserPort adapter instance."""
        if not self._adapter:
            raise RuntimeError("Browser not started. Use async context manager or call start().")
        return self._adapter

    @property
    def browser_port(self) -> BrowserPort:
        """Get the BrowserPort adapter instance."""
        return self.get_browser_port()

    async def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Browser context not initialized. Call start() first.")
        page = await self._context.new_page()
        return page

    @property
    def page(self) -> Page:
        """
        Get the main page (deprecated for application logic, use browser_port).
        """
        if not self._page:
            raise RuntimeError("Browser not started. Use async context manager or call start().")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Browser context not initialized.")
        return self._context

    @property
    def browser(self) -> Browser:
        if not self._browser:
            raise RuntimeError("Browser not started.")
        return self._browser

    async def save_session(self, filepath: str) -> None:
        if not self._context:
            raise RuntimeError("No browser context to save")

        storage_state = await self._context.storage_state()
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(storage_state, f, indent=2)

        logger.info(f"Session saved to {filepath}")

    async def load_session(self, filepath: str) -> None:
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")

        if self._context:
            await self._context.close()

        if not self._browser:
            raise RuntimeError("Browser not started")

        self._context = await self._browser.new_context(
            storage_state=filepath,
            viewport=self.viewport,
            user_agent=self.user_agent
        )

        if self._page:
            await self._page.close()
        self._page = await self._context.new_page()
        self._adapter = PlaywrightBrowserAdapter(self._page)
        self._is_authenticated = True

        logger.info(f"Session loaded from {filepath}")

    async def set_cookie(self, name: str, value: str, domain: str = ".linkedin.com") -> None:
        if not self._context:
            raise RuntimeError("No browser context")

        await self._context.add_cookies([{
            "name": name,
            "value": value,
            "domain": domain,
            "path": "/"
        }])

        logger.debug(f"Cookie set: {name}")

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        self._is_authenticated = value
