"""Enhanced browser control tool with CDP support."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.browser.cdp import (
    BrowserConfig,
    BrowserManager,
    CdpClient,
    NavigationGuard,
    RunningBrowser,
)


class BrowserTool(Tool):
    """Browser control tool with Chrome DevTools Protocol.

    Features:
    - Launch and manage Chrome/Chromium
    - Navigate to URLs
    - Take screenshots
    - Extract page content
    - Execute JavaScript
    - Click elements, fill forms
    - Download files
    """

    name = "browser"
    description = (
        "Control a web browser. Can navigate, screenshot, extract content, and interact with pages."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "screenshot",
                    "extract",
                    "click",
                    "fill",
                    "evaluate",
                    "close",
                ],
                "description": "Action to perform",
            },
            "url": {"type": "string", "description": "URL to navigate to (for 'navigate' action)"},
            "selector": {
                "type": "string",
                "description": "CSS selector (for 'click', 'fill' actions)",
            },
            "value": {
                "type": "string",
                "description": "Value to fill or JavaScript to evaluate",
            },
            "full_page": {
                "type": "boolean",
                "description": "Full page screenshot",
                "default": False,
            },
        },
        "required": ["action"],
    }

    def __init__(
        self,
        config: BrowserConfig | None = None,
        navigation_guard: bool = True,
        allow_list: list[str] | None = None,
        headless: bool = True,
        sandbox: bool = True,
        proxy: str | None = None,
    ):
        self._config = config or BrowserConfig(headless=headless, sandbox=sandbox, proxy=proxy)
        self._manager: BrowserManager | None = None
        self._browser: RunningBrowser | None = None
        self._cdp: CdpClient | None = None
        self._navigation_guard = NavigationGuard(allow_list) if navigation_guard else None
        self._current_url: str | None = None

    @property
    def browser_manager(self) -> BrowserManager:
        """Get or create browser manager."""
        if not self._manager:
            self._manager = BrowserManager(self._config)
        return self._manager

    async def _ensure_browser(self) -> RunningBrowser:
        """Ensure browser is running."""
        if not self._browser or self._browser.pid not in self.browser_manager.running_browsers:
            self._browser = await self.browser_manager.launch()
            self._cdp = await self.browser_manager.get_cdp_client(self._browser)
            logger.info(f"Browser launched: PID {self._browser.pid}")
        return self._browser

    async def _execute_cdp(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute CDP command."""
        if not self._cdp:
            await self._ensure_browser()

        result = await self._cdp.send(method, params)

        if "error" in result:
            error = result["error"]
            raise RuntimeError(f"CDP error {error.get('code')}: {error.get('message')}")

        return result.get("result", {})

    async def execute(
        self,
        action: str,
        url: str | None = None,
        selector: str | None = None,
        value: str | None = None,
        full_page: bool = False,
        **kwargs: Any,
    ) -> str:
        """Execute browser action."""
        try:
            await self._ensure_browser()

            if action == "navigate":
                return await self._navigate(url or "about:blank")
            elif action == "screenshot":
                return await self._screenshot(full_page=full_page)
            elif action == "extract":
                return await self._extract()
            elif action == "click":
                return await self._click(selector or "body")
            elif action == "fill":
                return await self._fill(selector or "", value or "")
            elif action == "evaluate":
                return await self._evaluate(value or "")
            elif action == "close":
                return await self._close()
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.error(f"Browser tool error: {e}")
            return f"Error: {e}"

    async def _navigate(self, url: str) -> str:
        """Navigate to URL."""
        # SSRF protection
        if self._navigation_guard:
            allowed, reason = self._navigation_guard.is_allowed(url)
            if not allowed:
                return f"Error: Navigation blocked - {reason}"

        logger.info(f"Navigating to: {url}")

        await self._execute_cdp("Page.enable")
        await self._execute_cdp("Page.navigate", {"url": url})

        # Wait for load
        await asyncio.sleep(1.0)

        self._current_url = url
        return f"Navigated to: {url}"

    async def _screenshot(self, full_page: bool = False) -> str:
        """Take screenshot."""
        logger.info(f"Taking screenshot (full_page={full_page})")

        result = await self._execute_cdp(
            "Page.captureScreenshot",
            {
                "format": "png",
                "fromSurface": True,
                "captureBeyondViewport": full_page,
            },
        )

        # Decode base64 image data
        image_data = result.get("data", "")
        if image_data:
            # Return as data URL
            return f"data:image/png;base64,{image_data[:1000]}... (truncated)"

        return "Screenshot taken (image data available)"

    async def _extract(self) -> str:
        """Extract page content."""
        logger.info("Extracting page content")

        # Get document structure
        result = await self._execute_cdp("DOM.getDocument", {"depth": 5})
        root = result.get("root", {})

        # Extract text content
        js = """
        () => {
            return document.body.innerText.slice(0, 10000);
        }
        """

        eval_result = await self._execute_cdp("Runtime.evaluate", {"expression": js})
        text = eval_result.get("result", {}).get("value", "")

        title = ""
        try:
            title_result = await self._execute_cdp(
                "Runtime.evaluate", {"expression": "document.title"}
            )
            title = title_result.get("result", {}).get("value", "")
        except Exception:
            pass

        return f"Title: {title}\n\n{text[:5000]}"

    async def _click(self, selector: str) -> str:
        """Click element."""
        logger.info(f"Clicking: {selector}")

        # Find element
        query_result = await self._execute_cdp(
            "DOM.querySelector",
            {
                "nodeId": 1,
                "selector": selector,
            },
        )

        node_id = query_result.get("nodeId", 0)
        if node_id == 0:
            return f"Error: Element not found: {selector}"

        # Get box model
        box_result = await self._execute_cdp("DOM.getBoxModel", {"nodeId": node_id})
        model = box_result.get("model", {})
        content = model.get("content", [])

        if not content:
            return f"Error: Element not visible: {selector}"

        # Click at center
        x = (content[0] + content[4]) / 2
        y = (content[1] + content[5]) / 2

        await self._execute_cdp(
            "Input.dispatchMouseEvent",
            {
                "type": "mousePressed",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )

        await self._execute_cdp(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )

        return f"Clicked: {selector}"

    async def _fill(self, selector: str, value: str) -> str:
        """Fill input field."""
        logger.info(f"Filling {selector} with: {value[:50]}...")

        # Find element
        query_result = await self._execute_cdp(
            "DOM.querySelector",
            {
                "nodeId": 1,
                "selector": selector,
            },
        )

        node_id = query_result.get("nodeId", 0)
        if node_id == 0:
            return f"Error: Element not found: {selector}"

        # Focus and type
        await self._execute_cdp("DOM.focus", {"nodeId": node_id})

        for char in value:
            await self._execute_cdp(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyDown",
                    "text": char,
                },
            )
            await self._execute_cdp(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyUp",
                    "text": char,
                },
            )

        return f"Filled {selector}"

    async def _evaluate(self, js: str) -> str:
        """Execute JavaScript."""
        logger.info(f"Evaluating JS: {js[:100]}...")

        result = await self._execute_cdp(
            "Runtime.evaluate",
            {
                "expression": js,
                "returnByValue": True,
            },
        )

        value = result.get("result", {}).get("value", "")
        return str(value)

    async def _close(self) -> str:
        """Close browser."""
        logger.info("Closing browser")

        try:
            if self._cdp:
                await self._cdp.close()
                self._cdp = None

            if self._browser and self._manager:
                await self._manager.stop(self._browser)
                self._browser = None

            return "Browser closed"
        except Exception as e:
            return f"Error closing browser: {e}"

    def __del__(self):
        """Cleanup on deletion."""
        try:
            if self._manager:
                self._manager.cleanup()
        except Exception:
            pass


# Lazy import asyncio to avoid circular imports
import asyncio

__all__ = ["BrowserTool"]
