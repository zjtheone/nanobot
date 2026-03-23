"""Browser file download management.

参考 OpenClaw pw-tools-core.downloads.ts 实现：
- CDP Download 事件监听
- 下载进度跟踪
- 文件保存路径管理
- 下载超时处理
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from loguru import logger


@dataclass
class DownloadInfo:
    """Download information."""

    id: str
    url: str
    suggested_filename: str
    save_path: str
    state: str = "in_progress"  # in_progress, completed, cancelled, failed
    received_bytes: int = 0
    total_bytes: int | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    error: str | None = None

    @property
    def progress(self) -> float:
        """Get download progress (0.0 - 1.0)."""
        if self.total_bytes is None or self.total_bytes == 0:
            return 0.0
        return min(1.0, self.received_bytes / self.total_bytes)

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def speed_bps(self) -> float:
        """Get download speed in bytes per second."""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.received_bytes / elapsed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "filename": self.suggested_filename,
            "save_path": self.save_path,
            "state": self.state,
            "progress": self.progress,
            "received_bytes": self.received_bytes,
            "total_bytes": self.total_bytes,
            "elapsed_seconds": self.elapsed_seconds,
            "speed_bps": self.speed_bps,
            "error": self.error,
        }


class DownloadManager:
    """Manage browser downloads."""

    def __init__(
        self,
        download_dir: str | None = None,
        timeout_seconds: float = 300.0,
    ):
        self.download_dir = download_dir or os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            "nanobot",
        )
        self.timeout_seconds = timeout_seconds
        self._downloads: dict[str, DownloadInfo] = {}
        self._pending_downloads: dict[str, asyncio.Future] = {}
        self._event_listeners: list[Callable[[DownloadInfo], None]] = []

    def _ensure_download_dir(self) -> str:
        """Ensure download directory exists."""
        os.makedirs(self.download_dir, exist_ok=True)
        return self.download_dir

    def _generate_download_id(self, url: str) -> str:
        """Generate unique download ID."""
        import hashlib

        timestamp = str(time.time())
        return hashlib.sha256(f"{url}:{timestamp}".encode()).hexdigest()[:16]

    def _resolve_save_path(self, filename: str) -> str:
        """Resolve save path for download."""
        self._ensure_download_dir()

        # Sanitize filename
        safe_filename = os.path.basename(filename)
        if not safe_filename:
            parsed = urlparse(filename)
            safe_filename = os.path.basename(parsed.path) or "download"

        # Remove invalid characters
        safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in "._-")

        save_path = os.path.join(self.download_dir, safe_filename)

        # Handle duplicate filenames
        base, ext = os.path.splitext(save_path)
        counter = 1
        while os.path.exists(save_path):
            save_path = f"{base}_{counter}{ext}"
            counter += 1

        return save_path

    def start_download(
        self,
        url: str,
        suggested_filename: str | None = None,
    ) -> DownloadInfo:
        """Start tracking a new download."""
        download_id = self._generate_download_id(url)

        download = DownloadInfo(
            id=download_id,
            url=url,
            suggested_filename=suggested_filename
            or os.path.basename(urlparse(url).path)
            or "download",
            save_path="",
        )

        self._downloads[download_id] = download

        logger.info(f"Download started: {download_id} - {download.suggested_filename}")

        return download

    def update_download(
        self,
        download_id: str,
        received_bytes: int | None = None,
        total_bytes: int | None = None,
        state: str | None = None,
        save_path: str | None = None,
        error: str | None = None,
    ) -> DownloadInfo | None:
        """Update download progress."""
        download = self._downloads.get(download_id)
        if not download:
            logger.warning(f"Download not found: {download_id}")
            return None

        if received_bytes is not None:
            download.received_bytes = received_bytes

        if total_bytes is not None:
            download.total_bytes = total_bytes

        if state is not None:
            download.state = state
            if state in ("completed", "cancelled", "failed"):
                download.end_time = time.time()

        if save_path is not None:
            download.save_path = save_path

        if error is not None:
            download.error = error

        # Notify listeners
        for listener in self._event_listeners:
            try:
                listener(download)
            except Exception as e:
                logger.error(f"Download listener error: {e}")

        # Complete pending future
        if (
            download.state in ("completed", "cancelled", "failed")
            and download_id in self._pending_downloads
        ):
            future = self._pending_downloads.pop(download_id)
            if not future.done():
                if download.state == "completed":
                    future.set_result(download.save_path)
                else:
                    future.set_exception(
                        Exception(f"Download failed: {download.error or download.state}")
                    )

        return download

    async def wait_for_download(
        self,
        download_id: str,
        timeout: float | None = None,
    ) -> str:
        """Wait for download to complete.

        Args:
            download_id: Download ID
            timeout: Timeout in seconds (default: self.timeout_seconds)

        Returns:
            Save path when download completes

        Raises:
            asyncio.TimeoutError: If download doesn't complete in time
            Exception: If download fails
        """
        if download_id not in self._downloads:
            raise ValueError(f"Download not found: {download_id}")

        download = self._downloads[download_id]

        # Already completed
        if download.state == "completed":
            return download.save_path
        if download.state in ("cancelled", "failed"):
            raise Exception(f"Download failed: {download.error or download.state}")

        # Create future if not exists
        if download_id not in self._pending_downloads:
            self._pending_downloads[download_id] = asyncio.Future()

        # Wait for completion
        timeout = timeout or self.timeout_seconds
        try:
            return await asyncio.wait_for(
                self._pending_downloads[download_id],
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # Cancel download
            self.update_download(download_id, state="cancelled", error="Timeout")
            raise

    def get_download(self, download_id: str) -> DownloadInfo | None:
        """Get download info."""
        return self._downloads.get(download_id)

    def list_downloads(self, active_only: bool = False) -> list[DownloadInfo]:
        """List all downloads."""
        downloads = list(self._downloads.values())
        if active_only:
            downloads = [d for d in downloads if d.state == "in_progress"]
        return downloads

    def add_event_listener(self, listener: Callable[[DownloadInfo], None]) -> None:
        """Add download event listener."""
        self._event_listeners.append(listener)

    def remove_event_listener(self, listener: Callable[[DownloadInfo], None]) -> None:
        """Remove download event listener."""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def cleanup_old_downloads(self, max_age_hours: float = 24.0) -> int:
        """Clean up old completed downloads.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of downloads cleaned up
        """
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        to_remove = []
        for download_id, download in self._downloads.items():
            if download.end_time is None:
                continue

            age = current_time - download.end_time
            if age > max_age_seconds:
                to_remove.append(download_id)

        for download_id in to_remove:
            del self._downloads[download_id]

        logger.info(f"Cleaned up {len(to_remove)} old downloads")
        return len(to_remove)


async def download_file_with_cdp(
    cdp_client: Any,
    url: str,
    save_dir: str,
    timeout_seconds: float = 300.0,
) -> str:
    """Download file using CDP.

    Args:
        cdp_client: CDP client instance
        url: URL to download
        save_dir: Directory to save file
        timeout_seconds: Download timeout

    Returns:
        Saved file path

    Raises:
        asyncio.TimeoutError: If download times out
        Exception: If download fails
    """
    import asyncio

    # Parse URL
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    # Create download manager
    manager = DownloadManager(download_dir=save_dir, timeout_seconds=timeout_seconds)

    # Set up download event listener
    download_id = None

    def on_download_progress(params: dict) -> None:
        nonlocal download_id

        if download_id is None:
            # First event - start tracking
            download_id = manager.start_download(
                url=params.get("url", url),
                suggested_filename=params.get("suggestedFilename"),
            ).id

        # Update progress
        manager.update_download(
            download_id,
            received_bytes=params.get("receivedBytes", 0),
            total_bytes=params.get("totalBytes"),
        )

    def on_download_completed(params: dict) -> None:
        if download_id is None:
            return

        # Determine final state
        state = "completed"
        if params.get("state") == "canceled":
            state = "cancelled"
        elif params.get("state") == "interrupted":
            state = "failed"

        # Get save path
        save_path = params.get("fullPath") or manager._downloads[download_id].save_path
        if not save_path:
            save_path = manager._resolve_save_path(
                params.get("suggestedFilename")
                or manager._downloads[download_id].suggested_filename
            )

        manager.update_download(
            download_id,
            state=state,
            save_path=save_path,
            error=params.get("danger") if state == "failed" else None,
        )

    # Register CDP event listeners
    # Note: This requires CDP client to support event subscription
    try:
        # Enable Download domain
        await cdp_client.send("Download.enable", {})

        # Set download behavior to download to specified directory
        await cdp_client.send(
            "Download.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": save_dir,
                "eventsEnabled": True,
            },
        )

        # Listen for download events
        # Note: Implementation depends on CDP client
        # This is a placeholder for actual event subscription

        # Navigate to URL to trigger download
        await cdp_client.send("Page.navigate", {"url": url})

        # Wait for download to complete
        if download_id:
            save_path = await manager.wait_for_download(download_id, timeout=timeout_seconds)
            return save_path

        # Fallback: wait for navigation to complete
        await asyncio.sleep(2)

        # Check if file was downloaded
        for filename in os.listdir(save_dir):
            file_path = os.path.join(save_dir, filename)
            if os.path.isfile(file_path):
                mtime = os.path.getmtime(file_path)
                if time.time() - mtime < 10:  # Downloaded in last 10 seconds
                    return file_path

        raise Exception("Download completed but file not found")

    finally:
        # Clean up event listeners
        pass


async def download_file_direct(
    url: str,
    save_dir: str,
    timeout_seconds: float = 300.0,
) -> str:
    """Download file directly using HTTP.

    Fallback method when CDP download is not available.

    Args:
        url: URL to download
        save_dir: Directory to save file
        timeout_seconds: Download timeout

    Returns:
        Saved file path

    Raises:
        asyncio.TimeoutError: If download times out
        Exception: If download fails
    """
    import httpx

    # Parse URL
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    # Resolve save path
    os.makedirs(save_dir, exist_ok=True)
    filename = os.path.basename(parsed.path) or "download"
    save_path = os.path.join(save_dir, filename)

    # Handle duplicate filenames
    base, ext = os.path.splitext(save_path)
    counter = 1
    while os.path.exists(save_path):
        save_path = f"{base}_{counter}{ext}"
        counter += 1

    # Download file
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            total_bytes = response.headers.get("content-length")
            total_bytes = int(total_bytes) if total_bytes else None

            received_bytes = 0
            with open(save_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    received_bytes += len(chunk)

    return save_path


__all__ = [
    "DownloadInfo",
    "DownloadManager",
    "download_file_direct",
    "download_file_with_cdp",
]
