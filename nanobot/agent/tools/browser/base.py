"""Browser backend abstraction layer.

Defines the interface for browser backends (CDP/Playwright).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class BrowserConsoleMessage:
    """Browser console message."""

    type: str  # log, error, warning, info, debug
    text: str
    timestamp: str
    url: str | None = None
    line_number: int | None = None
    column_number: int | None = None


@dataclass
class BrowserNetworkRequest:
    """Browser network request."""

    id: str
    url: str
    method: str
    status: int | None = None
    status_text: str | None = None
    timestamp: str | None = None
    resource_type: str | None = None  # Document, Stylesheet, Image, etc.
    request_headers: dict[str, str] | None = None
    response_headers: dict[str, str] | None = None


@dataclass
class BrowserTab:
    """Browser tab information."""

    id: str
    title: str
    url: str
    favicon_url: str | None = None
    is_active: bool = False


@dataclass
class BrowserSnapshot:
    """Browser page snapshot."""

    format: str  # ai, aria, role, text
    content: str
    incremental: str | None = None
    timestamp: str | None = None


class BrowserBackend(ABC):
    """Abstract base class for browser backends."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to browser."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from browser."""
        pass

    @abstractmethod
    async def navigate(self, url: str) -> str:
        """Navigate to URL.

        Returns:
            Final URL after navigation
        """
        pass

    @abstractmethod
    async def screenshot(self, full_page: bool = False) -> bytes:
        """Take screenshot.

        Returns:
            Image bytes (PNG format)
        """
        pass

    @abstractmethod
    async def extract_content(self) -> str:
        """Extract page content.

        Returns:
            Page text content
        """
        pass

    @abstractmethod
    async def click(self, selector: str) -> None:
        """Click element by selector."""
        pass

    @abstractmethod
    async def fill(self, selector: str, value: str) -> None:
        """Fill input field."""
        pass

    @abstractmethod
    async def evaluate(self, javascript: str) -> Any:
        """Execute JavaScript.

        Returns:
            Evaluation result
        """
        pass

    @abstractmethod
    async def get_snapshot(
        self,
        format: str = "ai",
        full_page: bool = False,
    ) -> BrowserSnapshot:
        """Get page snapshot.

        Args:
            format: Snapshot format (ai/aria/role/text)
            full_page: Include full page content

        Returns:
            Page snapshot
        """
        pass

    @abstractmethod
    async def get_console_messages(self) -> list[BrowserConsoleMessage]:
        """Get console messages.

        Returns:
            List of console messages
        """
        pass

    @abstractmethod
    async def get_network_requests(self) -> list[BrowserNetworkRequest]:
        """Get network requests.

        Returns:
            List of network requests
        """
        pass

    @abstractmethod
    async def get_tabs(self) -> list[BrowserTab]:
        """Get open tabs.

        Returns:
            List of tabs
        """
        pass

    @abstractmethod
    async def open_tab(self, url: str) -> str:
        """Open new tab.

        Args:
            url: URL to open

        Returns:
            Tab ID
        """
        pass

    @abstractmethod
    async def close_tab(self, tab_id: str) -> None:
        """Close tab.

        Args:
            tab_id: Tab ID to close
        """
        pass

    @abstractmethod
    async def focus_tab(self, tab_id: str) -> None:
        """Focus tab.

        Args:
            tab_id: Tab ID to focus
        """
        pass

    @abstractmethod
    async def save_pdf(self, path: str) -> str:
        """Save page as PDF.

        Args:
            path: Output file path

        Returns:
            Saved file path
        """
        pass

    @abstractmethod
    async def download_file(self, url: str, save_dir: str) -> str:
        """Download file.

        Args:
            url: File URL
            save_dir: Directory to save file

        Returns:
            Saved file path
        """
        pass

    @abstractmethod
    async def upload_file(self, selector: str, file_paths: list[str]) -> None:
        """Upload file.

        Args:
            selector: File input selector
            file_paths: Paths to files to upload
        """
        pass

    @property
    @abstractmethod
    def current_url(self) -> str | None:
        """Get current URL."""
        pass

    @property
    @abstractmethod
    def page_title(self) -> str | None:
        """Get page title."""
        pass


__all__ = [
    "BrowserBackend",
    "BrowserConsoleMessage",
    "BrowserNetworkRequest",
    "BrowserSnapshot",
    "BrowserTab",
]
