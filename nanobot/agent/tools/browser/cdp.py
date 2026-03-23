"""Browser control via CDP (Chrome DevTools Protocol).

参考 OpenClaw 的浏览器实现，提供：
- Chrome/Chromium 启动和管理
- CDP WebSocket 通信
- 页面导航、截图、DOM 操作
- 配置文件管理
- SSRF 防护
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import urlparse

import httpx
from loguru import logger


def is_loopback_host(hostname: str) -> bool:
    """Check if hostname is loopback address."""
    return hostname in ("127.0.0.1", "localhost", "::1", "[::1]")


# CDP 超时配置（参考 OpenClaw）
CHROME_LAUNCH_READY_TIMEOUT_MS = 5000
CHROME_REACHABILITY_TIMEOUT_MS = 3000
CHROME_WS_READY_TIMEOUT_MS = 3000
SCREENSHOT_TIMEOUT_MS = 10000


@dataclass
class BrowserExecutable:
    """Browser executable information."""

    path: str
    browser_type: Literal["chrome", "chromium", "edge", "brave"]
    version: str | None = None


@dataclass
class BrowserConfig:
    """Browser configuration."""

    executable: str | None = None
    profile_name: str = "default"
    user_data_dir: str | None = None
    cdp_port: int = 9222
    headless: bool = True
    sandbox: bool = True
    proxy: str | None = None
    color: str = "#4285F4"  # 配置文件颜色标识


@dataclass
class RunningBrowser:
    """Running browser instance."""

    pid: int
    executable: str
    user_data_dir: str
    cdp_port: int
    started_at: float
    proc: subprocess.Popen | None = None


def get_default_chrome_path() -> str | None:
    """Get default Chrome/Chromium path for current platform."""
    system = platform.system()

    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif system == "Linux":
        paths = [
            "google-chrome",
            "chromium",
            "chromium-browser",
            "google-chrome-stable",
            "google-chrome-beta",
            "brave-browser",
            "microsoft-edge",
        ]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\%USER%\AppData\Local\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
        ]
    else:
        return None

    for path in paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
        # Try finding in PATH for Linux
        if system == "Linux":
            chrome_path = shutil.which(path)
            if chrome_path:
                return chrome_path

    return None


def resolve_user_data_dir(profile_name: str = "default") -> str:
    """Resolve user data directory for browser profile."""
    from nanobot.config.paths import get_data_dir

    base_dir = get_data_dir()
    return os.path.join(base_dir, "browser", profile_name, "user-data")


def normalize_cdp_ws_url(ws_url: str, cdp_url: str) -> str:
    """Normalize CDP WebSocket URL."""
    from urllib.parse import urlparse

    ws = urlparse(ws_url)
    cdp = urlparse(cdp_url)

    # Check if wildcard bind (0.0.0.0 or ::)
    is_wildcard = ws.hostname in ("0.0.0.0", "[::]")

    # Rewrite loopback or wildcard to external host
    ws_hostname = ws.hostname or ""
    cdp_hostname = cdp.hostname or ""

    if (is_loopback_host(ws_hostname) or is_wildcard) and not is_loopback_host(cdp_hostname):
        # Reconstruct URL with new hostname
        new_url = f"{cdp.scheme}://{cdp_hostname}"
        if cdp.port:
            new_url += f":{cdp.port}"
        elif cdp.scheme == "https":
            new_url += ":443"
        else:
            new_url += ":80"
        new_url += ws.path
        if ws.query:
            new_url += f"?{ws.query}"
        return new_url

    # Upgrade to WSS if CDP is HTTPS
    if cdp.scheme == "https" and ws.scheme == "ws":
        ws_url = ws_url.replace("ws://", "wss://")

    return ws_url


async def fetch_json(url: str, timeout_ms: int = 1500) -> dict[str, Any] | None:
    """Fetch JSON from URL."""
    try:
        async with httpx.AsyncClient(timeout=timeout_ms / 1000.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
        return None


async def is_chrome_reachable(
    cdp_url: str, timeout_ms: int = CHROME_REACHABILITY_TIMEOUT_MS
) -> bool:
    """Check if Chrome CDP endpoint is reachable."""
    try:
        version = await fetch_json(f"{cdp_url}/json/version", timeout_ms)
        return version is not None
    except Exception:
        return False


async def get_chrome_websocket_url(
    cdp_url: str, timeout_ms: int = CHROME_REACHABILITY_TIMEOUT_MS
) -> str | None:
    """Get WebSocket debugger URL from CDP endpoint."""
    try:
        version = await fetch_json(f"{cdp_url}/json/version", timeout_ms)
        if not version:
            return None

        ws_url = version.get("webSocketDebuggerUrl", "").strip()
        if not ws_url:
            return None

        return normalize_cdp_ws_url(ws_url, cdp_url)
    except Exception as e:
        logger.error(f"Failed to get WebSocket URL: {e}")
        return None


@dataclass
class CdpClient:
    """Chrome DevTools Protocol client."""

    ws_url: str
    _ws = None
    _msg_id: int = 0
    _pending: dict[int, asyncio.Future] = field(default_factory=dict)

    async def connect(self):
        """Connect to CDP WebSocket."""
        try:
            import websockets

            self._ws = await websockets.connect(self.ws_url)

            # Start message listener
            asyncio.create_task(self._listen())
        except Exception as e:
            logger.error(f"Failed to connect to CDP: {e}")
            raise

    async def _listen(self):
        """Listen for CDP events and responses."""
        try:
            async for message in self._ws:
                data = json.loads(message)
                msg_id = data.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending[msg_id].set_result(data)
        except Exception as e:
            logger.error(f"CDP listen error: {e}")

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send CDP command."""
        if not self._ws:
            raise RuntimeError("Not connected to CDP")

        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}

        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self._pending[self._msg_id] = future

        await self._ws.send(json.dumps(msg))

        try:
            result = await asyncio.wait_for(future, timeout=10.0)
            return result
        finally:
            del self._pending[self._msg_id]

    async def close(self):
        """Close CDP connection."""
        if self._ws:
            await self._ws.close()


class BrowserManager:
    """Manage browser instances and CDP connections."""

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self.running_browsers: dict[int, RunningBrowser] = {}

    def resolve_executable(self) -> str:
        """Resolve browser executable path."""
        if self.config.executable:
            return self.config.executable

        exe = get_default_chrome_path()
        if not exe:
            raise RuntimeError(
                "Chrome/Chromium not found. Install Chrome or set executable path in config. "
                "On macOS: brew install --cask google-chrome"
            )
        return exe

    def resolve_user_data_dir(self) -> str:
        """Resolve user data directory."""
        if self.config.user_data_dir:
            return self.config.user_data_dir
        return resolve_user_data_dir(self.config.profile_name)

    async def launch(self) -> RunningBrowser:
        """Launch Chrome/Chromium with CDP enabled."""
        import time

        exe = self.resolve_executable()
        user_data_dir = self.resolve_user_data_dir()

        # Ensure user data directory exists
        os.makedirs(user_data_dir, exist_ok=True)

        # Find available CDP port
        cdp_port = self.config.cdp_port
        while True:
            try:
                import socket

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", cdp_port))
                    break
            except OSError:
                cdp_port += 1

        # Build Chrome arguments
        args = [
            exe,
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            f"--window-size=1280,800",
        ]

        if self.config.headless:
            args.append("--headless=new")

        if not self.config.sandbox:
            args.extend(["--no-sandbox", "--disable-setuid-sandbox"])

        if self.config.proxy:
            args.append(f"--proxy-server={self.config.proxy}")

        # Disable features that might interfere
        args.extend(
            [
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
            ]
        )

        logger.info(f"Launching Chrome: {exe} on port {cdp_port}")

        # Start Chrome process
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        started_at = time.time()

        browser = RunningBrowser(
            pid=proc.pid,
            executable=exe,
            user_data_dir=user_data_dir,
            cdp_port=cdp_port,
            started_at=started_at,
            proc=proc,
        )

        self.running_browsers[proc.pid] = browser

        # Wait for Chrome to be ready
        cdp_url = f"http://127.0.0.1:{cdp_port}"
        for attempt in range(CHROME_LAUNCH_READY_TIMEOUT_MS // 100):
            if await is_chrome_reachable(cdp_url, 100):
                logger.info(f"Chrome launched successfully on port {cdp_port}")
                return browser
            await asyncio.sleep(0.1)

        raise RuntimeError(f"Chrome failed to launch within {CHROME_LAUNCH_READY_TIMEOUT_MS}ms")

    async def stop(self, browser: RunningBrowser) -> bool:
        """Stop running browser instance."""
        try:
            if browser.proc:
                browser.proc.terminate()
                browser.proc.wait(timeout=5)

            del self.running_browsers[browser.pid]
            logger.info(f"Stopped Chrome (PID: {browser.pid})")
            return True
        except Exception as e:
            logger.error(f"Failed to stop Chrome: {e}")
            return False

    async def get_cdp_client(self, browser: RunningBrowser) -> CdpClient:
        """Get CDP client for running browser."""
        cdp_url = f"http://127.0.0.1:{browser.cdp_port}"
        ws_url = await get_chrome_websocket_url(cdp_url)

        if not ws_url:
            raise RuntimeError(
                f"Failed to get CDP WebSocket URL for Chrome on port {browser.cdp_port}"
            )

        client = CdpClient(ws_url=ws_url)
        await client.connect()
        return client

    def cleanup(self):
        """Clean up all running browsers."""
        import signal

        for browser in list(self.running_browsers.values()):
            try:
                if browser.proc:
                    os.kill(browser.pid, signal.SIGTERM)
            except Exception as e:
                logger.error(f"Failed to cleanup browser {browser.pid}: {e}")

        self.running_browsers.clear()


# Navigation guard for SSRF protection
class NavigationGuard:
    """Protect against SSRF attacks by validating navigation URLs."""

    def __init__(self, allow_list: list[str] | None = None):
        self.allow_list = allow_list or []
        self.denied_schemes = {"file", "gopher", "ftp"}

    def is_allowed(self, url: str) -> tuple[bool, str]:
        """Check if URL is safe to navigate to."""
        try:
            parsed = urlparse(url)

            # Check denied schemes
            if parsed.scheme.lower() in self.denied_schemes:
                return False, f"Denied scheme: {parsed.scheme}"

            # Only allow http/https
            if parsed.scheme.lower() not in ("http", "https"):
                return False, f"Unsupported scheme: {parsed.scheme}"

            # Check allow list
            if self.allow_list:
                netloc = parsed.netloc.lower()
                for allowed in self.allow_list:
                    if netloc.endswith(allowed.lower()):
                        return True, ""
                return False, f"URL not in allow list: {netloc}"

            # Block private IP ranges
            hostname = parsed.hostname
            if hostname and self._is_private_ip(hostname):
                return False, f"Private IP address: {hostname}"

            return True, ""
        except Exception as e:
            return False, str(e)

    def _is_private_ip(self, hostname: str) -> bool:
        """Check if hostname resolves to private IP."""
        import socket

        try:
            ips = socket.gethostbyname_ex(hostname)[2]
            for ip in ips:
                if self._is_private_ip_v4(ip):
                    return True
            return False
        except socket.gaierror:
            return False

    def _is_private_ip_v4(self, ip: str) -> bool:
        """Check if IPv4 address is private."""
        import ipaddress

        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_private or addr.is_loopback or addr.is_link_local
        except ValueError:
            return False


__all__ = [
    "BrowserConfig",
    "BrowserExecutable",
    "BrowserManager",
    "CdpClient",
    "NavigationGuard",
    "RunningBrowser",
    "get_default_chrome_path",
    "resolve_user_data_dir",
]
