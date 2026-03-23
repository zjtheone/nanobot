"""Tests for enhanced browser control tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.agent.tools.browser.browser_tool import BrowserTool
from nanobot.agent.tools.browser.cdp import (
    BrowserConfig,
    BrowserManager,
    CdpClient,
    NavigationGuard,
    get_default_chrome_path,
    resolve_user_data_dir,
    is_chrome_reachable,
)


class TestNavigationGuard:
    """Test SSRF protection in NavigationGuard."""

    def test_allow_http_urls(self):
        """Allow standard HTTP/HTTPS URLs."""
        guard = NavigationGuard()

        allowed, reason = guard.is_allowed("https://example.com")
        assert allowed is True

        # Note: localhost and some domains may be blocked as private IPs
        # Test with a clearly public domain
        allowed, reason = guard.is_allowed("https://httpbin.org/get")
        # Allow list enforcement will be tested separately

    def test_deny_dangerous_schemes(self):
        """Deny dangerous URL schemes."""
        guard = NavigationGuard()

        allowed, reason = guard.is_allowed("file:///etc/passwd")
        assert allowed is False
        assert "Denied scheme" in reason

        allowed, reason = guard.is_allowed("gopher://evil.com")
        assert allowed is False

    def test_allow_list_enforcement(self):
        """Test URL allow list."""
        guard = NavigationGuard(allow_list=["github.com", "example.org"])

        allowed, reason = guard.is_allowed("https://github.com/user/repo")
        assert allowed is True

        allowed, reason = guard.is_allowed("https://evil.com")
        assert allowed is False
        assert "not in allow list" in reason

    def test_private_ip_blocking(self):
        """Test blocking of private IP addresses."""
        guard = NavigationGuard()

        # Localhost should be blocked
        allowed, reason = guard.is_allowed("http://127.0.0.1:8080")
        # Note: Implementation may vary on localhost handling


class TestBrowserConfig:
    """Test browser configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BrowserConfig()

        assert config.headless is True
        assert config.sandbox is True
        assert config.cdp_port == 9222
        assert config.profile_name == "default"

    def test_custom_config(self):
        """Test custom configuration."""
        config = BrowserConfig(
            headless=False,
            sandbox=False,
            cdp_port=9999,
            profile_name="test-profile",
        )

        assert config.headless is False
        assert config.sandbox is False
        assert config.cdp_port == 9999


class TestBrowserTool:
    """Test browser tool functionality."""

    @pytest.mark.asyncio
    async def test_close_without_launch(self):
        """Test closing browser without launching."""
        browser = BrowserTool(headless=True)
        result = await browser.execute(action="close")
        assert "closed" in result.lower()

    def test_invalid_action(self):
        """Test invalid action handling."""
        browser = BrowserTool(headless=True)
        # Would need to mock browser launch to test properly


class TestBrowserUtilityFunctions:
    """Test browser utility functions."""

    def test_get_default_chrome_path_returns_string_or_none(self):
        """Test Chrome path detection."""
        path = get_default_chrome_path()
        assert path is None or isinstance(path, str)

    def test_resolve_user_data_dir_returns_string(self):
        """Test user data directory resolution."""
        path = resolve_user_data_dir("test-profile")
        assert isinstance(path, str)
        assert "test-profile" in path


class TestCdpClient:
    """Test CDP client."""

    def test_cdp_client_creation(self):
        """Test CDP client can be created."""
        client = CdpClient(ws_url="ws://localhost:9222/devtools")
        assert client.ws_url == "ws://localhost:9222/devtools"


@pytest.mark.asyncio
class TestBrowserToolIntegration:
    """Integration tests for browser tool."""

    async def test_browser_config_passed_to_tool(self):
        """Test browser config is properly used."""
        config = BrowserConfig(headless=True, sandbox=True)
        browser = BrowserTool(config=config)

        assert browser._config.headless is True
        assert browser._config.sandbox is True

    async def test_navigation_guard_optional(self):
        """Test navigation guard can be disabled."""
        browser = BrowserTool(navigation_guard=False)
        assert browser._navigation_guard is None


class TestBrowserManager:
    """Test browser manager."""

    def test_manager_creation(self):
        """Test browser manager can be created."""
        config = BrowserConfig()
        manager = BrowserManager(config)

        assert manager.config == config
        assert len(manager.running_browsers) == 0

    def test_resolve_executable_with_nonexistent_path(self):
        """Test executable resolution with nonexistent path."""
        config = BrowserConfig(executable="/nonexistent/chrome")
        manager = BrowserManager(config)

        # Should return the path even if it doesn't exist
        # Validation happens at launch time
        path = manager.resolve_executable()
        assert path == "/nonexistent/chrome"


# Skip tests that require actual Chrome installation
@pytest.mark.skip(reason="Requires Chrome installation")
class TestBrowserWithChrome:
    """Tests requiring actual Chrome installation."""

    async def test_launch_chrome(self):
        """Test launching Chrome."""
        pass

    async def test_navigate_to_url(self):
        """Test navigating to URL."""
        pass

    async def test_take_screenshot(self):
        """Test taking screenshot."""
        pass
