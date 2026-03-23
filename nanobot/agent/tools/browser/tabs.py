"""Browser tab management.

参考 OpenClaw server-context.tab-ops.ts 实现：
- 标签页列表获取 (CDP Target.getTargets)
- 新建标签页 (Target.createTarget)
- 关闭标签页 (Target.closeTarget)
- 切换标签页 (Target.attachToTarget)
- 标签页状态跟踪 (URL/标题/favicon)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from loguru import logger


@dataclass
class TabInfo:
    """Browser tab information."""

    id: str
    title: str = ""
    url: str = ""
    favicon_url: str | None = None
    is_active: bool = False
    is_incognito: bool = False
    created_time: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    can_close: bool = True
    parent_id: str | None = None

    @property
    def datetime_str(self) -> str:
        """Get creation datetime as string."""
        return datetime.fromtimestamp(self.created_time).isoformat()

    @property
    def age_seconds(self) -> float:
        """Get tab age in seconds."""
        return time.time() - self.created_time

    @property
    def idle_seconds(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_accessed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "favicon_url": self.favicon_url,
            "is_active": self.is_active,
            "is_incognito": self.is_incognito,
            "created_time": self.datetime_str,
            "age_seconds": self.age_seconds,
            "idle_seconds": self.idle_seconds,
            "can_close": self.can_close,
            "parent_id": self.parent_id,
        }


class TabManager:
    """Manage browser tabs."""

    def __init__(self, auto_track: bool = True):
        self.auto_track = auto_track
        self._tabs: dict[str, TabInfo] = {}
        self._active_tab_id: str | None = None
        self._listeners: list[Callable[[str, TabInfo], None]] = []

    def add_tab(self, tab: TabInfo) -> None:
        """Add tab to manager."""
        self._tabs[tab.id] = tab

        if tab.is_active:
            self._active_tab_id = tab.id

        self._notify_listeners("add", tab)
        logger.debug(f"Tab added: {tab.id} - {tab.title or 'Untitled'}")

    def remove_tab(self, tab_id: str) -> TabInfo | None:
        """Remove tab from manager."""
        tab = self._tabs.pop(tab_id, None)

        if tab:
            if self._active_tab_id == tab_id:
                self._active_tab_id = None

            self._notify_listeners("remove", tab)
            logger.debug(f"Tab removed: {tab_id}")

        return tab

    def update_tab(self, tab_id: str, **updates: Any) -> TabInfo | None:
        """Update tab information."""
        tab = self._tabs.get(tab_id)
        if not tab:
            logger.warning(f"Tab not found: {tab_id}")
            return None

        for key, value in updates.items():
            if hasattr(tab, key):
                setattr(tab, key, value)

        tab.last_accessed = time.time()

        if updates.get("is_active"):
            self._active_tab_id = tab_id

        self._notify_listeners("update", tab)
        return tab

    def get_tab(self, tab_id: str) -> TabInfo | None:
        """Get tab by ID."""
        return self._tabs.get(tab_id)

    def get_active_tab(self) -> TabInfo | None:
        """Get active tab."""
        if self._active_tab_id:
            return self._tabs.get(self._active_tab_id)
        return None

    def set_active_tab(self, tab_id: str) -> bool:
        """Set active tab."""
        if tab_id not in self._tabs:
            logger.warning(f"Tab not found: {tab_id}")
            return False

        # Deactivate current active tab
        if self._active_tab_id and self._active_tab_id in self._tabs:
            self._tabs[self._active_tab_id].is_active = False

        # Activate new tab
        self._tabs[tab_id].is_active = True
        self._active_tab_id = tab_id
        self._tabs[tab_id].last_accessed = time.time()

        logger.debug(f"Active tab changed to: {tab_id}")
        return True

    def list_tabs(
        self,
        active_only: bool = False,
        include_closed: bool = False,
    ) -> list[TabInfo]:
        """List all tabs."""
        tabs = list(self._tabs.values())

        if active_only:
            tabs = [t for t in tabs if t.is_active]

        # Sort by last accessed time (newest first)
        tabs.sort(key=lambda t: t.last_accessed, reverse=True)

        return tabs

    def find_tabs_by_url(self, url_pattern: str) -> list[TabInfo]:
        """Find tabs by URL pattern."""
        matching_tabs = []

        for tab in self._tabs.values():
            if url_pattern.lower() in tab.url.lower():
                matching_tabs.append(tab)

        return matching_tabs

    def find_tabs_by_title(self, title_pattern: str) -> list[TabInfo]:
        """Find tabs by title pattern."""
        matching_tabs = []

        for tab in self._tabs.values():
            if title_pattern.lower() in tab.title.lower():
                matching_tabs.append(tab)

        return matching_tabs

    def close_tabs(
        self,
        tab_ids: list[str] | None = None,
        exclude_active: bool = False,
        older_than_seconds: float | None = None,
    ) -> list[str]:
        """Close multiple tabs.

        Args:
            tab_ids: List of tab IDs to close (None = all tabs)
            exclude_active: Don't close active tab
            older_than_seconds: Only close tabs older than this

        Returns:
            List of closed tab IDs
        """
        tabs_to_close = []

        if tab_ids:
            tabs_to_close = [
                tab_id
                for tab_id in tab_ids
                if tab_id in self._tabs and not (exclude_active and tab_id == self._active_tab_id)
            ]
        else:
            tabs_to_close = list(self._tabs.keys())

        closed_ids = []
        current_time = time.time()

        for tab_id in tabs_to_close:
            tab = self._tabs[tab_id]

            if not tab.can_close:
                continue

            if exclude_active and tab_id == self._active_tab_id:
                continue

            if older_than_seconds and tab.age_seconds < older_than_seconds:
                continue

            self.remove_tab(tab_id)
            closed_ids.append(tab_id)

        logger.info(f"Closed {len(closed_ids)} tabs")
        return closed_ids

    def get_statistics(self) -> dict[str, int]:
        """Get tab statistics."""
        return {
            "total_tabs": len(self._tabs),
            "active_tabs": sum(1 for t in self._tabs.values() if t.is_active),
            "incognito_tabs": sum(1 for t in self._tabs.values() if t.is_incognito),
            "can_close": sum(1 for t in self._tabs.values() if t.can_close),
        }

    def add_listener(self, listener: Callable[[str, TabInfo], None]) -> None:
        """Add tab event listener."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, TabInfo], None]) -> None:
        """Remove tab event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event: str, tab: TabInfo) -> None:
        """Notify listeners of tab event."""
        for listener in self._listeners:
            try:
                listener(event, tab)
            except Exception as e:
                logger.error(f"Tab listener error: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tabs": [t.to_dict() for t in self._tabs.values()],
            "active_tab_id": self._active_tab_id,
            "statistics": self.get_statistics(),
        }


async def get_targets_cdp(cdp_client: Any) -> list[dict[str, Any]]:
    """Get browser targets via CDP.

    Args:
        cdp_client: CDP client instance

    Returns:
        List of target information dictionaries
    """
    try:
        result = await cdp_client.send("Target.getTargets", {})
        return result.get("targetInfos", [])
    except Exception as e:
        logger.error(f"Failed to get targets: {e}")
        return []


async def create_target_cdp(
    cdp_client: Any,
    url: str = "about:blank",
    new_window: bool = False,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Create new target via CDP.

    Args:
        cdp_client: CDP client instance
        url: URL to open
        new_window: Open in new window
        width: Window width
        height: Window height

    Returns:
        Target ID
    """
    params = {
        "url": url,
        "newWindow": new_window,
    }

    if width:
        params["width"] = width
    if height:
        params["height"] = height

    try:
        result = await cdp_client.send("Target.createTarget", params)
        return result.get("targetId", "")
    except Exception as e:
        logger.error(f"Failed to create target: {e}")
        raise


async def close_target_cdp(
    cdp_client: Any,
    target_id: str,
) -> bool:
    """Close target via CDP.

    Args:
        cdp_client: CDP client instance
        target_id: Target ID to close

    Returns:
        True if successfully closed
    """
    try:
        await cdp_client.send("Target.closeTarget", {"targetId": target_id})
        return True
    except Exception as e:
        logger.error(f"Failed to close target: {e}")
        return False


async def activate_target_cdp(
    cdp_client: Any,
    target_id: str,
) -> bool:
    """Activate target via CDP.

    Args:
        cdp_client: CDP client instance
        target_id: Target ID to activate

    Returns:
        True if successfully activated
    """
    try:
        await cdp_client.send("Target.activateTarget", {"targetId": target_id})
        return True
    except Exception as e:
        logger.error(f"Failed to activate target: {e}")
        return False


async def attach_to_target_cdp(
    cdp_client: Any,
    target_id: str,
    flatten: bool = True,
) -> str:
    """Attach to target via CDP.

    Args:
        cdp_client: CDP client instance
        target_id: Target ID to attach to
        flatten: Flatten iframe tree

    Returns:
        Session ID
    """
    try:
        result = await cdp_client.send(
            "Target.attachToTarget",
            {
                "targetId": target_id,
                "flatten": flatten,
            },
        )
        return result.get("sessionId", "")
    except Exception as e:
        logger.error(f"Failed to attach to target: {e}")
        raise


async def sync_tabs_from_cdp(
    cdp_client: Any,
    tab_manager: TabManager,
) -> list[TabInfo]:
    """Sync tabs from CDP targets.

    Args:
        cdp_client: CDP client instance
        tab_manager: Tab manager to update

    Returns:
        List of synced tabs
    """
    targets = await get_targets_cdp(cdp_client)

    synced_tabs = []
    for target in targets:
        if target.get("type") != "page":
            continue

        target_id = target.get("targetId", "")

        tab = TabInfo(
            id=target_id,
            title=target.get("title", ""),
            url=target.get("url", ""),
            is_active=target.get("active", False),
            is_incognito=target.get("browserContextId") is not None,
        )

        existing = tab_manager.get_tab(target_id)
        if existing:
            tab_manager.update_tab(
                target_id,
                title=tab.title,
                url=tab.url,
                is_active=tab.is_active,
            )
        else:
            tab_manager.add_tab(tab)

        synced_tabs.append(tab)

    logger.debug(f"Synced {len(synced_tabs)} tabs from CDP")
    return synced_tabs


def parse_tab_info_from_cdp(target: dict[str, Any]) -> TabInfo:
    """Parse tab info from CDP target.

    Args:
        target: CDP target dictionary

    Returns:
        Parsed TabInfo
    """
    return TabInfo(
        id=target.get("targetId", ""),
        title=target.get("title", ""),
        url=target.get("url", ""),
        favicon_url=target.get("faviconUrl"),
        is_active=target.get("active", False),
        is_incognito=target.get("browserContextId") is not None,
        can_close=target.get("type") == "page",
    )


__all__ = [
    "TabInfo",
    "TabManager",
    "activate_target_cdp",
    "attach_to_target_cdp",
    "close_target_cdp",
    "create_target_cdp",
    "get_targets_cdp",
    "parse_tab_info_from_cdp",
    "sync_tabs_from_cdp",
]
