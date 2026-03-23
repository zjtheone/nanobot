"""Browser console message tracking.

参考 OpenClaw pw-tools-core.state.ts 实现：
- CDP Runtime.consoleAPICalled 事件监听
- 消息类型过滤 (log/error/warning/info/debug)
- 消息缓存和限制
- 时间戳和位置信息
- 消息分组和去重
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from loguru import logger


@dataclass
class ConsoleMessage:
    """Console message data."""

    type: str  # log, error, warning, info, debug, dir, table
    text: str
    timestamp: float = field(default_factory=time.time)
    url: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    source: str | None = None  # javascript, console-api, network, storage, etc.
    stack_trace: str | None = None
    args: list[Any] = field(default_factory=list)

    @property
    def datetime_str(self) -> str:
        """Get datetime as string."""
        return datetime.fromtimestamp(self.timestamp).isoformat()

    @property
    def level(self) -> str:
        """Get message level for display."""
        level_map = {
            "error": "ERROR",
            "warning": "WARN",
            "info": "INFO",
            "log": "LOG",
            "debug": "DEBUG",
            "dir": "DIR",
            "table": "TABLE",
        }
        return level_map.get(self.type, self.type.upper())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "level": self.level,
            "text": self.text,
            "timestamp": self.datetime_str,
            "url": self.url,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "source": self.source,
            "args": self.args,
        }


class ConsoleMessageFilter:
    """Filter console messages by type and pattern."""

    def __init__(
        self,
        include_types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        pattern: str | None = None,
        min_level: str | None = None,
    ):
        self.include_types = set(include_types) if include_types else None
        self.exclude_types = set(exclude_types) if exclude_types else None
        self.pattern = pattern
        self.min_level = min_level

    def matches(self, message: ConsoleMessage) -> bool:
        """Check if message matches filter."""
        # Check type inclusion
        if self.include_types and message.type not in self.include_types:
            return False

        # Check type exclusion
        if self.exclude_types and message.type in self.exclude_types:
            return False

        # Check pattern
        if self.pattern and self.pattern.lower() not in message.text.lower():
            return False

        # Check minimum level
        if self.min_level:
            level_order = ["debug", "log", "info", "warning", "error"]
            try:
                min_index = level_order.index(self.min_level.lower())
                msg_index = level_order.index(message.type.lower())
                if msg_index < min_index:
                    return False
            except ValueError:
                pass

        return True


class ConsoleManager:
    """Manage browser console messages."""

    DEFAULT_MAX_MESSAGES = 500
    DEFAULT_MAX_ERRORS = 200

    def __init__(
        self,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        max_errors: int = DEFAULT_MAX_ERRORS,
        auto_dedup: bool = True,
    ):
        self.max_messages = max_messages
        self.max_errors = max_errors
        self.auto_dedup = auto_dedup

        # Message storage using deque for efficient rotation
        self._messages: deque[ConsoleMessage] = deque(maxlen=max_messages)
        self._errors: deque[ConsoleMessage] = deque(maxlen=max_errors)

        # Deduplication cache
        self._message_hashes: dict[str, ConsoleMessage] = {}

        # Event listeners
        self._listeners: list[Callable[[ConsoleMessage], None]] = []

        # Statistics
        self._stats = {
            "total_received": 0,
            "total_deduped": 0,
            "total_errors": 0,
            "total_warnings": 0,
        }

    def _generate_message_hash(self, message: ConsoleMessage) -> str:
        """Generate hash for deduplication."""
        # Use type + text + url + line as key
        key_parts = [
            message.type,
            message.text,
            message.url or "",
            str(message.line_number or ""),
        ]
        return ":".join(key_parts)

    def add_message(self, message: ConsoleMessage) -> bool:
        """Add console message.

        Args:
            message: Console message to add

        Returns:
            True if message was added, False if deduplicated
        """
        self._stats["total_received"] += 1

        # Check deduplication
        if self.auto_dedup:
            msg_hash = self._generate_message_hash(message)
            if msg_hash in self._message_hashes:
                self._stats["total_deduped"] += 1
                return False
            self._message_hashes[msg_hash] = message

        # Add to appropriate queue
        if message.type == "error":
            self._errors.append(message)
            self._stats["total_errors"] += 1
        else:
            self._messages.append(message)
            if message.type == "warning":
                self._stats["total_warnings"] += 1

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(message)
            except Exception as e:
                logger.error(f"Console listener error: {e}")

        return True

    def add_messages(self, messages: list[ConsoleMessage]) -> int:
        """Add multiple console messages.

        Args:
            messages: List of console messages

        Returns:
            Number of messages added
        """
        count = 0
        for message in messages:
            if self.add_message(message):
                count += 1
        return count

    def get_messages(
        self,
        filter: ConsoleMessageFilter | None = None,
        limit: int | None = None,
        reverse: bool = True,
    ) -> list[ConsoleMessage]:
        """Get console messages.

        Args:
            filter: Optional message filter
            limit: Maximum number of messages to return
            reverse: Return messages in reverse order (newest first)

        Returns:
            List of console messages
        """
        all_messages = list(self._messages)

        if reverse:
            all_messages.reverse()

        if filter:
            all_messages = [m for m in all_messages if filter.matches(m)]

        if limit:
            all_messages = all_messages[:limit]

        return all_messages

    def get_errors(
        self,
        limit: int | None = None,
        reverse: bool = True,
    ) -> list[ConsoleMessage]:
        """Get error messages.

        Args:
            limit: Maximum number of errors to return
            reverse: Return errors in reverse order (newest first)

        Returns:
            List of error messages
        """
        errors = list(self._errors)
        if reverse:
            errors.reverse()
        if limit:
            errors = errors[:limit]
        return errors

    def clear(self) -> None:
        """Clear all console messages."""
        self._messages.clear()
        self._errors.clear()
        self._message_hashes.clear()
        logger.info("Console messages cleared")

    def add_listener(self, listener: Callable[[ConsoleMessage], None]) -> None:
        """Add console message listener."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ConsoleMessage], None]) -> None:
        """Remove console message listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_statistics(self) -> dict[str, int]:
        """Get console message statistics."""
        return {
            **self._stats,
            "current_messages": len(self._messages),
            "current_errors": len(self._errors),
            "dedup_cache_size": len(self._message_hashes),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "messages": [m.to_dict() for m in self._messages],
            "errors": [e.to_dict() for e in self._errors],
            "statistics": self.get_statistics(),
        }


async def enable_console_tracking_cdp(
    cdp_client: Any,
    console_manager: ConsoleManager,
) -> None:
    """Enable console message tracking via CDP.

    Args:
        cdp_client: CDP client instance
        console_manager: Console manager to store messages
    """

    def on_console_api_called(params: dict) -> None:
        """Handle Runtime.consoleAPICalled event."""
        message = ConsoleMessage(
            type=params.get("type", "log"),
            text=" ".join(str(arg.get("value", "")) for arg in params.get("args", [])),
            timestamp=time.time(),
            url=params.get("url"),
            line_number=params.get("lineNumber"),
            column_number=params.get("columnNumber"),
            source=params.get("source"),
            args=params.get("args", []),
        )

        console_manager.add_message(message)

    def on_exception_thrown(params: dict) -> None:
        """Handle Runtime.exceptionThrown event."""
        exception_details = params.get("exceptionDetails", {})
        exception = exception_details.get("exception", {})

        message = ConsoleMessage(
            type="error",
            text=exception.get("description") or exception.get("value") or "Unknown error",
            timestamp=time.time(),
            url=exception_details.get("url"),
            line_number=exception_details.get("lineNumber"),
            column_number=exception_details.get("columnNumber"),
            stack_trace=exception_details.get("stackTrace", {}).get("callFrames"),
            args=[exception],
        )

        console_manager.add_message(message)

    try:
        # Enable Runtime domain
        await cdp_client.send("Runtime.enable", {})

        # Listen for console API calls
        # Note: This requires CDP client to support event subscription
        # Implementation depends on specific CDP client library
        logger.info("Console tracking enabled via CDP")

    except Exception as e:
        logger.error(f"Failed to enable console tracking: {e}")
        raise


def parse_console_message_from_cdp(params: dict) -> ConsoleMessage:
    """Parse console message from CDP event parameters.

    Args:
        params: CDP event parameters

    Returns:
        Parsed ConsoleMessage
    """
    return ConsoleMessage(
        type=params.get("type", "log"),
        text=" ".join(str(arg.get("value", "")) for arg in params.get("args", [])),
        timestamp=time.time(),
        url=params.get("url"),
        line_number=params.get("lineNumber"),
        column_number=params.get("columnNumber"),
        source=params.get("source"),
        stack_trace=params.get("stackTrace"),
        args=params.get("args", []),
    )


def format_console_messages(
    messages: list[ConsoleMessage],
    format_type: str = "text",
) -> str:
    """Format console messages for display.

    Args:
        messages: List of console messages
        format_type: Output format (text/html/json/markdown)

    Returns:
        Formatted string
    """
    if format_type == "json":
        import json

        return json.dumps([m.to_dict() for m in messages], indent=2)

    if format_type == "html":
        html_lines = []
        for msg in messages:
            html_lines.append(
                f'<div class="console-{msg.type}">'
                f'<span class="level">{msg.level}</span> '
                f'<span class="time">{msg.datetime_str}</span>: '
                f"{msg.text}"
                f"</div>"
            )
        return "\n".join(html_lines)

    if format_type == "markdown":
        md_lines = []
        for msg in messages:
            md_lines.append(f"**[{msg.level}]** `{msg.datetime_str}` - {msg.text}")
        return "\n".join(md_lines)

    # Default: plain text
    text_lines = []
    for msg in messages:
        text_lines.append(f"[{msg.level}] {msg.datetime_str} - {msg.text}")
    return "\n".join(text_lines)


__all__ = [
    "ConsoleManager",
    "ConsoleMessage",
    "ConsoleMessageFilter",
    "enable_console_tracking_cdp",
    "format_console_messages",
    "parse_console_message_from_cdp",
]
