"""Enhanced navigation guard with SSRF protection.

参考 OpenClaw navigation-guard.ts 实现：
- 导航前 URL 检查
- 重定向链追踪
- 代理环境检测
- 导航结果验证
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import ipaddress

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# 允许的导航协议
NETWORK_NAVIGATION_PROTOCOLS = {"http:", "https:"}
SAFE_NON_NETWORK_URLS = {"about:blank"}


@dataclass
class SSRFPolicy:
    """SSRF protection policy."""

    allow_private_network: bool = False
    allowed_hosts: list[str] | None = None
    blocked_hosts: list[str] | None = None
    allowed_protocols: set[str] | None = None


@dataclass
class BrowserNavigationRequest:
    """Browser navigation request."""

    url_value: str
    redirected_from_value: BrowserNavigationRequest | None = None

    def url(self) -> str:
        return self.url_value

    def redirected_from(self) -> BrowserNavigationRequest | None:
        return self.redirected_from_value


class NavigationGuardError(Exception):
    """Navigation guard error."""

    pass


def has_proxy_env_configured() -> bool:
    """Check if proxy environment variables are configured."""
    proxy_vars = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ]
    return any(os.environ.get(var) for var in proxy_vars)


def is_private_ip_v4(ip: str) -> bool:
    """Check if IPv4 address is private."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
    except ValueError:
        return False


def is_private_ip_v6(ip: str) -> bool:
    """Check if IPv6 address is private."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IP addresses."""
    try:
        return socket.gethostbyname_ex(hostname)[2]
    except socket.gaierror:
        return []


def is_private_network_allowed(policy: SSRFPolicy | None) -> bool:
    """Check if private network access is allowed by policy."""
    if policy is None:
        return False
    return policy.allow_private_network


async def resolve_hostname_with_policy(
    hostname: str,
    policy: SSRFPolicy | None = None,
    lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
) -> None:
    """Resolve hostname with SSRF policy check.

    Args:
        hostname: Hostname to resolve
        policy: SSRF policy
        lookup_fn: Custom DNS lookup function

    Raises:
        NavigationGuardError: If hostname resolves to blocked IP
    """
    if lookup_fn:
        ips = await lookup_fn(hostname)
    else:
        ips = resolve_hostname(hostname)

    if not ips:
        return

    for ip in ips:
        if policy and not policy.allow_private_network:
            if is_private_ip_v4(ip) or is_private_ip_v6(ip):
                raise NavigationGuardError(
                    f"Navigation blocked: hostname {hostname} resolves to private IP {ip}"
                )

        if policy and policy.blocked_hosts:
            if ip in policy.blocked_hosts:
                raise NavigationGuardError(
                    f"Navigation blocked: hostname {hostname} resolves to blocked IP {ip}"
                )


async def assert_navigation_allowed(
    url: str,
    policy: SSRFPolicy | None = None,
    lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
) -> None:
    """Assert that navigation URL is allowed.

    Args:
        url: URL to validate
        policy: SSRF policy
        lookup_fn: Custom DNS lookup function

    Raises:
        NavigationGuardError: If URL is not allowed
    """
    raw_url = (url or "").strip()
    if not raw_url:
        raise NavigationGuardError("url is required")

    try:
        parsed = urlparse(raw_url)
    except Exception:
        raise NavigationGuardError(f"Invalid URL: {raw_url}")

    # Check protocol
    if parsed.scheme not in NETWORK_NAVIGATION_PROTOCOLS:
        if parsed.path in ("blank",):  # about:blank
            return
        raise NavigationGuardError(f"Navigation blocked: unsupported protocol '{parsed.scheme}'")

    # Check proxy environment
    if has_proxy_env_configured() and not is_private_network_allowed(policy):
        raise NavigationGuardError(
            "Navigation blocked: strict browser SSRF policy cannot be "
            "enforced while proxy environment variables are set"
        )

    # Check hostname
    hostname = parsed.hostname
    if hostname:
        await resolve_hostname_with_policy(hostname, policy, lookup_fn)


async def assert_navigation_redirect_chain_allowed(
    request: BrowserNavigationRequest | None,
    policy: SSRFPolicy | None = None,
    lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
) -> None:
    """Assert that navigation redirect chain is allowed.

    Args:
        request: Navigation request with redirect chain
        policy: SSRF policy
        lookup_fn: Custom DNS lookup function

    Raises:
        NavigationGuardError: If any URL in chain is not allowed
    """
    chain: list[str] = []
    current = request

    while current:
        chain.append(current.url())
        current = current.redirected_from()

    # Check chain in reverse order (original -> final)
    for url in reversed(chain):
        await assert_navigation_allowed(url, policy, lookup_fn)


async def assert_navigation_result_allowed(
    url: str,
    policy: SSRFPolicy | None = None,
    lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
) -> None:
    """Assert that final navigation result URL is allowed.

    Best-effort post-navigation guard for final page URLs.
    Only validates network URLs (http/https) and about:blank to avoid false
    positives on browser-internal error pages (e.g. chrome-error://).

    Args:
        url: Final URL after navigation
        policy: SSRF policy
        lookup_fn: Custom DNS lookup function

    Raises:
        NavigationGuardError: If URL is not allowed
    """
    raw_url = (url or "").strip()
    if not raw_url:
        return

    try:
        parsed = urlparse(raw_url)
    except Exception:
        return

    # Only check network URLs and about:blank
    if parsed.scheme in NETWORK_NAVIGATION_PROTOCOLS or (
        parsed.path == "blank" and parsed.scheme == "about"
    ):
        await assert_navigation_allowed(raw_url, policy, lookup_fn)


def is_allowed_non_network_url(parsed: Any) -> bool:
    """Check if non-network URL is allowed.

    Args:
        parsed: Parsed URL object

    Returns:
        True if allowed
    """
    return parsed.path in ("blank",) and parsed.scheme == "about"


class NavigationGuard:
    """Enhanced navigation guard with SSRF protection."""

    def __init__(
        self,
        allow_list: list[str] | None = None,
        policy: SSRFPolicy | None = None,
    ):
        self.allow_list = allow_list or []
        self.policy = policy or SSRFPolicy()

        if self.allow_list:
            self.policy.allowed_hosts = self.allow_list

    def is_allowed(self, url: str) -> tuple[bool, str]:
        """Check if URL is safe to navigate to (synchronous version).

        Args:
            url: URL to check

        Returns:
            Tuple of (allowed, reason)
        """
        try:
            parsed = urlparse(url)

            # Check denied schemes
            if parsed.scheme not in NETWORK_NAVIGATION_PROTOCOLS:
                if is_allowed_non_network_url(parsed):
                    return True, ""
                return False, f"Denied scheme: {parsed.scheme}"

            # Check allow list
            if self.allow_list:
                netloc = parsed.netloc.lower()
                for allowed in self.allow_list:
                    if netloc.endswith(allowed.lower()) or netloc == allowed.lower():
                        return True, ""
                return False, f"URL not in allow list: {netloc}"

            # Block private IP ranges
            hostname = parsed.hostname
            if hostname:
                ips = resolve_hostname(hostname)
                for ip in ips:
                    if is_private_ip_v4(ip) or is_private_ip_v6(ip):
                        return False, f"Private IP address: {hostname} -> {ip}"

            return True, ""
        except Exception as e:
            return False, str(e)

    async def assert_allowed(
        self,
        url: str,
        lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
    ) -> None:
        """Assert URL is allowed (async version).

        Args:
            url: URL to validate
            lookup_fn: Custom DNS lookup function

        Raises:
            NavigationGuardError: If URL is not allowed
        """
        await assert_navigation_allowed(url, self.policy, lookup_fn)

    async def assert_redirect_chain_allowed(
        self,
        request: BrowserNavigationRequest | None,
        lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
    ) -> None:
        """Assert redirect chain is allowed.

        Args:
            request: Navigation request with redirect chain
            lookup_fn: Custom DNS lookup function

        Raises:
            NavigationGuardError: If any URL in chain is not allowed
        """
        await assert_navigation_redirect_chain_allowed(request, self.policy, lookup_fn)

    async def assert_result_allowed(
        self,
        url: str,
        lookup_fn: Callable[[str], Awaitable[list[str]]] | None = None,
    ) -> None:
        """Assert navigation result is allowed.

        Args:
            url: Final URL after navigation
            lookup_fn: Custom DNS lookup function

        Raises:
            NavigationGuardError: If URL is not allowed
        """
        await assert_navigation_result_allowed(url, self.policy, lookup_fn)


__all__ = [
    "NavigationGuard",
    "NavigationGuardError",
    "SSRFPolicy",
    "assert_navigation_allowed",
    "assert_navigation_redirect_chain_allowed",
    "assert_navigation_result_allowed",
    "has_proxy_env_configured",
    "is_private_ip_v4",
    "is_private_ip_v6",
]
