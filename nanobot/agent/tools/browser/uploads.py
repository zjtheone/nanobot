"""Browser file upload management.

参考 OpenClaw pw-tools-core.downloads.ts 实现：
- 文件上传对话框处理
- 多文件上传支持
- 文件类型验证
- 上传进度跟踪
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger


@dataclass
class UploadInfo:
    """File upload information."""

    id: str
    file_paths: list[str]
    selector: str
    state: str = "pending"  # pending, in_progress, completed, cancelled, failed
    uploaded_count: int = 0
    total_count: int = 0
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())
    end_time: float | None = None
    error: str | None = None

    @property
    def progress(self) -> float:
        """Get upload progress (0.0 - 1.0)."""
        if self.total_count == 0:
            return 0.0
        return min(1.0, self.uploaded_count / self.total_count)

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time or datetime.now().timestamp()
        return end - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_paths": self.file_paths,
            "selector": self.selector,
            "state": self.state,
            "progress": self.progress,
            "uploaded_count": self.uploaded_count,
            "total_count": self.total_count,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
        }


class UploadManager:
    """Manage browser file uploads."""

    def __init__(self, max_file_size_mb: float = 100.0, max_files: int = 10):
        self.max_file_size_mb = max_file_size_mb
        self.max_files = max_files
        self._uploads: dict[str, UploadInfo] = {}
        self._pending_uploads: dict[str, asyncio.Future] = {}

    def _generate_upload_id(self, file_paths: list[str]) -> str:
        """Generate unique upload ID."""
        import hashlib

        timestamp = str(datetime.now().timestamp())
        content = f"{':'.join(file_paths)}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def validate_file(self, file_path: str) -> tuple[bool, str | None]:
        """Validate file for upload.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file exists
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        # Check is file
        if not os.path.isfile(file_path):
            return False, f"Not a file: {file_path}"

        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            return False, f"File too large: {file_size_mb:.1f}MB > {self.max_file_size_mb}MB"

        # Check file type (basic check)
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            # Unknown type, allow
            pass

        return True, None

    def validate_files(self, file_paths: list[str]) -> tuple[bool, list[str]]:
        """Validate multiple files.

        Args:
            file_paths: List of file paths

        Returns:
            Tuple of (all_valid, error_messages)
        """
        if len(file_paths) > self.max_files:
            return False, [f"Too many files: {len(file_paths)} > {self.max_files}"]

        errors = []
        for file_path in file_paths:
            is_valid, error = self.validate_file(file_path)
            if not is_valid and error:
                errors.append(error)

        return len(errors) == 0, errors

    def start_upload(
        self,
        file_paths: list[str],
        selector: str,
    ) -> UploadInfo:
        """Start tracking a new upload."""
        upload_id = self._generate_upload_id(file_paths)

        upload = UploadInfo(
            id=upload_id,
            file_paths=file_paths,
            selector=selector,
            state="in_progress",
            total_count=len(file_paths),
            uploaded_count=0,
        )

        self._uploads[upload_id] = upload

        logger.info(f"Upload started: {upload_id} - {len(file_paths)} files to {selector}")

        return upload

    def update_upload(
        self,
        upload_id: str,
        uploaded_count: int | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> UploadInfo | None:
        """Update upload progress."""
        upload = self._uploads.get(upload_id)
        if not upload:
            logger.warning(f"Upload not found: {upload_id}")
            return None

        if uploaded_count is not None:
            upload.uploaded_count = uploaded_count

        if state is not None:
            upload.state = state
            if state in ("completed", "cancelled", "failed"):
                upload.end_time = datetime.now().timestamp()

        if error is not None:
            upload.error = error

        # Complete pending future
        if (
            upload.state in ("completed", "cancelled", "failed")
            and upload_id in self._pending_uploads
        ):
            future = self._pending_uploads.pop(upload_id)
            if not future.done():
                if upload.state == "completed":
                    future.set_result(upload)
                else:
                    future.set_exception(
                        Exception(f"Upload failed: {upload.error or upload.state}")
                    )

        return upload

    async def wait_for_upload(
        self,
        upload_id: str,
        timeout: float = 60.0,
    ) -> UploadInfo:
        """Wait for upload to complete.

        Args:
            upload_id: Upload ID
            timeout: Timeout in seconds

        Returns:
            Upload info when complete

        Raises:
            asyncio.TimeoutError: If upload doesn't complete in time
            Exception: If upload fails
        """
        if upload_id not in self._uploads:
            raise ValueError(f"Upload not found: {upload_id}")

        upload = self._uploads[upload_id]

        # Already completed
        if upload.state == "completed":
            return upload
        if upload.state in ("cancelled", "failed"):
            raise Exception(f"Upload failed: {upload.error or upload.state}")

        # Create future if not exists
        if upload_id not in self._pending_uploads:
            self._pending_uploads[upload_id] = asyncio.Future()

        # Wait for completion
        try:
            return await asyncio.wait_for(
                self._pending_uploads[upload_id],
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # Cancel upload
            self.update_upload(upload_id, state="cancelled", error="Timeout")
            raise

    def get_upload(self, upload_id: str) -> UploadInfo | None:
        """Get upload info."""
        return self._uploads.get(upload_id)

    def list_uploads(self, active_only: bool = False) -> list[UploadInfo]:
        """List all uploads."""
        uploads = list(self._uploads.values())
        if active_only:
            uploads = [u for u in uploads if u.state == "in_progress"]
        return uploads


async def upload_files_with_cdp(
    cdp_client: Any,
    selector: str,
    file_paths: list[str],
    timeout_seconds: float = 60.0,
) -> UploadInfo:
    """Upload files using CDP.

    Args:
        cdp_client: CDP client instance
        selector: CSS selector for file input
        file_paths: List of file paths to upload
        timeout_seconds: Upload timeout

    Returns:
        Upload info

    Raises:
        asyncio.TimeoutError: If upload times out
        Exception: If upload fails
    """
    # Create upload manager
    manager = UploadManager()

    # Validate files
    is_valid, errors = manager.validate_files(file_paths)
    if not is_valid:
        raise ValueError(f"Invalid files: {', '.join(errors)}")

    # Start tracking upload
    upload = manager.start_upload(file_paths, selector)

    try:
        # Find file input element
        query_result = await cdp_client.send(
            "DOM.querySelector",
            {
                "nodeId": 1,
                "selector": selector,
            },
        )

        node_id = query_result.get("nodeId", 0)
        if node_id == 0:
            raise ValueError(f"File input not found: {selector}")

        # Set files for upload using Runtime domain
        # This is the standard way to handle file uploads in CDP
        file_paths_absolute = [os.path.abspath(p) for p in file_paths]

        # Use DOM.setFileInputFiles to set files
        await cdp_client.send(
            "DOM.setFileInputFiles",
            {
                "nodeId": node_id,
                "files": file_paths_absolute,
            },
        )

        # Update upload progress
        manager.update_upload(upload.id, uploaded_count=len(file_paths))

        # Mark as completed
        manager.update_upload(upload.id, state="completed")

        logger.info(f"Upload completed: {upload.id} - {len(file_paths)} files")

        return upload

    except Exception as e:
        manager.update_upload(upload.id, state="failed", error=str(e))
        logger.error(f"Upload failed: {upload.id} - {e}")
        raise


async def upload_files_direct(
    selector: str,
    file_paths: list[str],
    cdp_client: Any,
) -> None:
    """Upload files directly by setting file input value.

    Alternative method for simple file uploads.

    Args:
        selector: CSS selector for file input
        file_paths: List of file paths to upload
        cdp_client: CDP client instance

    Raises:
        ValueError: If file input not found
        Exception: If upload fails
    """
    # Find file input element
    query_result = await cdp_client.send(
        "DOM.querySelector",
        {
            "nodeId": 1,
            "selector": selector,
        },
    )

    node_id = query_result.get("nodeId", 0)
    if node_id == 0:
        raise ValueError(f"File input not found: {selector}")

    # Convert to absolute paths
    file_paths_absolute = [os.path.abspath(p) for p in file_paths]

    # Set file input files
    await cdp_client.send(
        "DOM.setFileInputFiles",
        {
            "nodeId": node_id,
            "files": file_paths_absolute,
        },
    )


def validate_file_type(
    file_path: str,
    allowed_types: list[str] | None = None,
) -> tuple[bool, str | None]:
    """Validate file type.

    Args:
        file_path: Path to file
        allowed_types: List of allowed MIME types or extensions (e.g., ['.pdf', 'image/*'])

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not allowed_types:
        return True, None

    mime_type, _ = mimetypes.guess_type(file_path)
    file_ext = os.path.splitext(file_path)[1].lower()

    for allowed in allowed_types:
        # Check MIME type pattern
        if allowed.endswith("/*"):
            type_prefix = allowed[:-2]
            if mime_type and mime_type.startswith(type_prefix):
                return True, None
        # Check exact MIME type
        elif allowed.startswith("."):
            if file_ext == allowed.lower():
                return True, None
        else:
            if mime_type == allowed:
                return True, None

    return False, f"File type not allowed: {file_ext or mime_type}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe upload.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = os.path.basename(filename)

    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[: max_length - len(ext)] + ext

    return filename


__all__ = [
    "UploadInfo",
    "UploadManager",
    "sanitize_filename",
    "upload_files_direct",
    "upload_files_with_cdp",
    "validate_file_type",
]
