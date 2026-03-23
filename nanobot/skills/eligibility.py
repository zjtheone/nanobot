"""Skill runtime eligibility evaluation and dependency checking.

参考 OpenClaw 的 config.ts 和 eligibility evaluation 实现：
- 运行时资格评估
- 二进制依赖检查
- 环境变量验证
- OS 兼容性检查
"""

import os
import platform
import shutil
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class EligibilityResult:
    """Skill eligibility evaluation result."""

    eligible: bool
    reason: str | None = None
    missing_bins: list[str] | None = None
    missing_env: list[str] | None = None
    os_mismatch: bool = False
    config_mismatch: bool = False


@dataclass
class EligibilityContext:
    """Context for eligibility evaluation."""

    os: str
    has_bin: Callable[[str], bool]
    has_env: Callable[[str], bool]
    is_config_path_truthy: Callable[[str], bool] | None = None


def has_binary(name: str) -> bool:
    """Check if binary/command is available in PATH."""
    return shutil.which(name) is not None


def has_env(name: str) -> bool:
    """Check if environment variable is set and non-empty."""
    return bool(os.environ.get(name))


def is_config_path_truthy(config_path: str) -> bool:
    """Check if config path is truthy (default implementation)."""
    return True


def resolve_runtime_platform() -> str:
    """Resolve current platform."""
    system = platform.system().lower()

    if system == "darwin":
        return "darwin"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "win32"
    else:
        return "unknown"


def evaluate_eligibility(
    os_list: list[str] | None = None,
    requires_bins: list[str] | None = None,
    requires_any_bins: list[str] | None = None,
    requires_env: list[str] | None = None,
    requires_config: list[str] | None = None,
    always: bool = False,
    has_bin_fn: Callable[[str], bool] | None = None,
    has_env_fn: Callable[[str], bool] | None = None,
    is_config_truthy_fn: Callable[[str], bool] | None = None,
) -> EligibilityResult:
    """Evaluate skill eligibility."""
    if always:
        return EligibilityResult(eligible=True)

    has_bin = has_bin_fn or has_binary
    has_environment = has_env_fn or has_env
    is_config_truthy = is_config_truthy_fn or is_config_path_truthy

    current_os = resolve_runtime_platform()

    if os_list:
        if current_os not in os_list:
            return EligibilityResult(
                eligible=False,
                reason=f"OS mismatch: requires {os_list}, current is {current_os}",
                os_mismatch=True,
            )

    if requires_bins:
        missing_bins = [b for b in requires_bins if not has_bin(b)]
        if missing_bins:
            return EligibilityResult(
                eligible=False,
                reason=f"Missing binaries: {', '.join(missing_bins)}",
                missing_bins=missing_bins,
            )

    if requires_any_bins:
        if not any(has_bin(b) for b in requires_any_bins):
            return EligibilityResult(
                eligible=False,
                reason=f"Missing at least one binary from: {', '.join(requires_any_bins)}",
                missing_bins=requires_any_bins,
            )

    if requires_env:
        missing_env = [e for e in requires_env if not has_environment(e)]
        if missing_env:
            return EligibilityResult(
                eligible=False,
                reason=f"Missing environment variables: {', '.join(missing_env)}",
                missing_env=missing_env,
            )

    if requires_config:
        config_mismatch = False
        for config_path in requires_config:
            if not is_config_truthy(config_path):
                config_mismatch = True
                break

        if config_mismatch:
            return EligibilityResult(
                eligible=False,
                reason="Config requirements not met",
                config_mismatch=True,
            )

    return EligibilityResult(eligible=True)


def check_skill_dependencies(
    skill_metadata: dict[str, Any],
    check_env: bool = True,
    check_bins: bool = True,
    check_os: bool = True,
) -> EligibilityResult:
    """Check skill dependencies from metadata dict.

    Args:
        skill_metadata: Skill metadata from frontmatter
        check_env: Check environment variables
        check_bins: Check binaries
        check_os: Check OS compatibility

    Returns:
        EligibilityResult
    """
    os_list = None
    requires_bins = []
    requires_any_bins = []
    requires_env = []
    requires_config = []
    always = False

    if check_os:
        os_list = skill_metadata.get("os")

    requires = skill_metadata.get("requires", {})

    if check_bins:
        requires_bins.extend(requires.get("bins", []))
        requires_any_bins.extend(requires.get("any_bins", []))

    if check_env:
        requires_env.extend(requires.get("env", []))

    requires_config.extend(requires.get("config", []))
    always = skill_metadata.get("always", False)

    return evaluate_eligibility(
        os_list=os_list,
        requires_bins=requires_bins or None,
        requires_any_bins=requires_any_bins or None,
        requires_env=requires_env or None,
        requires_config=requires_config or None,
        always=always,
    )


def get_install_instructions(
    skill_metadata: dict[str, Any],
    platform: str | None = None,
) -> list[dict[str, Any]]:
    """Get installation instructions for skill.

    Args:
        skill_metadata: Skill metadata
        platform: Target platform (auto-detect if None)

    Returns:
        List of install instructions
    """
    if platform is None:
        platform = resolve_runtime_platform()

    instructions = []
    install_specs = skill_metadata.get("install", [])

    for spec in install_specs:
        if not isinstance(spec, dict):
            continue

        spec_os = spec.get("os")
        if spec_os and platform not in spec_os:
            continue

        instructions.append(spec)

    return instructions


def format_install_command(
    install_spec: dict[str, Any],
    platform: str | None = None,
) -> str:
    """Format install command from spec.

    Args:
        install_spec: Install specification
        platform: Target platform

    Returns:
        Shell command string
    """
    if platform is None:
        platform = resolve_runtime_platform()

    kind = install_spec.get("kind", "download")
    package = install_spec.get("package")
    module = install_spec.get("module")
    url = install_spec.get("url")

    if kind == "node" or kind == "npm":
        if package:
            return f"npm install -g {package}"
        elif module:
            return f"npm install -g {module}"

    elif kind == "pip" or kind == "uv":
        if package:
            return f"pip install {package}"

    elif kind == "brew":
        if package:
            return f"brew install {package}"

    elif kind == "go":
        if module:
            return f"go install {module}"

    elif kind == "download":
        if url:
            return f"curl -fsSL {url} | bash"

    return f"# Unknown install kind: {kind}"


def get_missing_dependencies(
    skill_metadata: dict[str, Any],
) -> dict[str, list[str]]:
    """Get detailed list of missing dependencies.

    Returns:
        Dict with keys: bins, env, os
    """
    missing = {
        "bins": [],
        "env": [],
        "os": [],
    }

    os_list = skill_metadata.get("os")
    if os_list and resolve_runtime_platform() not in os_list:
        missing["os"].extend(os_list)

    requires = skill_metadata.get("requires", {})

    requires_bins = requires.get("bins", [])
    if requires_bins:
        missing["bins"].extend([b for b in requires_bins if not has_binary(b)])

    requires_any_bins = requires.get("any_bins", [])
    if requires_any_bins and not any(has_binary(b) for b in requires_any_bins):
        missing["bins"].extend(requires_any_bins)

    requires_env = requires.get("env", [])
    if requires_env:
        missing["env"].extend([e for e in requires_env if not has_env(e)])

    return missing


def can_auto_install(
    skill_metadata: dict[str, Any],
) -> tuple[bool, str | None]:
    """Check if skill can be auto-installed.

    Returns:
        Tuple of (can_install, reason)
    """
    install_specs = skill_metadata.get("install", [])

    if not install_specs:
        return False, "No install specs defined"

    for spec in install_specs:
        if not isinstance(spec, dict):
            continue

        kind = spec.get("kind")

        if kind in ("node", "npm", "pip", "brew", "go"):
            return True, None

    return False, f"Unsupported install kind: {install_specs[0].get('kind', 'unknown')}"


class EligibilityChecker:
    """Reusable eligibility checker with custom context."""

    def __init__(
        self,
        custom_bin_checker: Callable[[str], bool] | None = None,
        custom_env_checker: Callable[[str], bool] | None = None,
        custom_config_checker: Callable[[str], bool] | None = None,
    ):
        self.has_bin = custom_bin_checker or has_binary
        self.has_env = custom_env_checker or has_env
        self.is_config_truthy = custom_config_checker or is_config_path_truthy

    def check(
        self,
        skill_metadata: dict[str, Any],
    ) -> EligibilityResult:
        """Check skill eligibility."""
        requires = skill_metadata.get("requires", {})

        return evaluate_eligibility(
            os_list=skill_metadata.get("os"),
            requires_bins=requires.get("bins"),
            requires_any_bins=requires.get("any_bins"),
            requires_env=requires.get("env"),
            requires_config=requires.get("config"),
            always=skill_metadata.get("always", False),
            has_bin_fn=self.has_bin,
            has_env_fn=self.has_env,
            is_config_truthy_fn=self.is_config_truthy,
        )

    def get_install_commands(
        self,
        skill_metadata: dict[str, Any],
    ) -> list[str]:
        """Get install commands for skill."""
        instructions = get_install_instructions(skill_metadata)
        return [format_install_command(inst) for inst in instructions]


__all__ = [
    "EligibilityChecker",
    "EligibilityContext",
    "EligibilityResult",
    "can_auto_install",
    "check_skill_dependencies",
    "evaluate_eligibility",
    "format_install_command",
    "get_install_instructions",
    "get_missing_dependencies",
    "has_binary",
    "has_env",
    "resolve_runtime_platform",
]
