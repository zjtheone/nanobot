"""Skill frontmatter parsing and metadata extraction.

参考 OpenClaw 的 frontmatter.ts 实现：
- YAML 前后文解析
- 技能元数据提取
- 技能命令定义
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillInstallSpec:
    """Skill installation specification."""

    kind: str  # "node", "npm", "pip", "brew", "download"
    package: str | None = None
    module: str | None = None
    url: str | None = None
    target_dir: str | None = None
    extract: bool = True
    strip_components: int = 0


@dataclass
class SkillMetadata:
    """Skill metadata parsed from frontmatter."""

    name: str
    description: str
    emoji: str | None = None
    homepage: str | None = None
    os: list[str] = field(default_factory=list)
    requires_bins: list[str] = field(default_factory=list)
    requires_any_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)
    requires_config: list[str] = field(default_factory=list)
    install: list[SkillInstallSpec] = field(default_factory=list)
    always: bool = False
    skill_key: str | None = None
    primary_env: str | None = None
    version: str | None = None
    author: str | None = None
    license: str | None = None


@dataclass
class SkillCommand:
    """Skill command definition."""

    name: str
    skill_name: str
    description: str
    dispatch_kind: str = "tool"  # "tool" | "script"
    tool_name: str | None = None
    arg_mode: str = "raw"  # "raw" | "parsed"


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content.

    Simple YAML parser that handles basic key-value pairs, lists, and nested objects.
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        return {}

    yaml_lines = []
    end_index = -1

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break
        yaml_lines.append(line)

    if end_index == -1:
        return {}

    return parse_yaml("\n".join(yaml_lines))


def parse_yaml(yaml_str: str) -> dict[str, Any]:
    """Simple YAML parser for skill frontmatter."""
    result: dict[str, Any] = {}
    lines = yaml_str.split("\n")
    current_key: str | None = None
    current_indent = 0
    current_list: list[Any] | None = None
    current_dict: dict[str, Any] | None = None
    dict_key: str | None = None

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0:
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()

                if value:
                    result[key] = parse_yaml_value(value)
                    current_list = None
                    current_dict = None
                else:
                    current_key = key
                    current_list = None
                    current_dict = None
        elif current_key:
            if stripped.startswith("- "):
                if current_list is None:
                    current_list = []
                    result[current_key] = current_list

                item = stripped[2:].strip()
                if ":" in item and not item.startswith('"'):
                    item_dict = {}
                    item_dict[item.split(":")[0].strip()] = parse_yaml_value(
                        item.split(":", 1)[1].strip()
                    )
                    current_list.append(item_dict)
                else:
                    current_list.append(parse_yaml_value(item))
            elif ":" in stripped:
                if current_dict is None:
                    current_dict = {}
                    result[current_key] = current_dict

                key, value = stripped.split(":", 1)
                current_dict[key.strip()] = parse_yaml_value(value.strip())

        i += 1

    return result


def parse_yaml_value(value: str) -> Any:
    """Parse YAML value to Python type."""
    if not value:
        return None

    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]

    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].split(",")
        return [parse_yaml_value(item.strip()) for item in items if item.strip()]

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value


def extract_metadata(frontmatter: dict[str, Any]) -> SkillMetadata:
    """Extract skill metadata from frontmatter."""
    metadata = SkillMetadata(
        name=frontmatter.get("name", "unknown"),
        description=frontmatter.get("description", ""),
        emoji=frontmatter.get("emoji"),
        homepage=frontmatter.get("homepage"),
        os=frontmatter.get("os", []),
        always=frontmatter.get("always", False),
        skill_key=frontmatter.get("skill_key") or frontmatter.get("name"),
        primary_env=frontmatter.get("primary_env"),
        version=frontmatter.get("version"),
        author=frontmatter.get("author"),
        license=frontmatter.get("license"),
    )

    requires = frontmatter.get("requires", {})
    if isinstance(requires, dict):
        metadata.requires_bins = requires.get("bins", [])
        metadata.requires_any_bins = requires.get("any_bins", [])
        metadata.requires_env = requires.get("env", [])
        metadata.requires_config = requires.get("config", [])

    install_specs = frontmatter.get("install", [])
    if isinstance(install_specs, list):
        for spec in install_specs:
            if isinstance(spec, dict):
                metadata.install.append(
                    SkillInstallSpec(
                        kind=spec.get("kind", "download"),
                        package=spec.get("package"),
                        module=spec.get("module"),
                        url=spec.get("url"),
                        target_dir=spec.get("target_dir"),
                        extract=spec.get("extract", True),
                        strip_components=spec.get("stripComponents", 0),
                    )
                )

    return metadata


def extract_commands(
    skill_path: str,
    frontmatter: dict[str, Any],
) -> list[SkillCommand]:
    """Extract command definitions from skill.

    Commands can be defined in:
    1. frontmatter.commands
    2. TOOLS.md or COMMANDS.md files
    """
    commands = []

    commands_data = frontmatter.get("commands", [])
    if isinstance(commands_data, list):
        skill_name = frontmatter.get("name", "unknown")
        for cmd in commands_data:
            if isinstance(cmd, dict):
                commands.append(
                    SkillCommand(
                        name=cmd.get("name", ""),
                        skill_name=skill_name,
                        description=cmd.get("description", ""),
                        dispatch_kind=cmd.get("dispatch", {}).get("kind", "tool"),
                        tool_name=cmd.get("dispatch", {}).get("toolName"),
                        arg_mode=cmd.get("dispatch", {}).get("argMode", "raw"),
                    )
                )

    commands_file = None
    skill_dir = os.path.dirname(skill_path)
    for filename in ["TOOLS.md", "COMMANDS.md", "CLI.md"]:
        candidate = os.path.join(skill_dir, filename)
        if os.path.exists(candidate):
            commands_file = candidate
            break

    if commands_file:
        try:
            with open(commands_file, "r", encoding="utf-8") as f:
                content = f.read()

            cmd_matches = re.findall(r"^-+\s*`([^`]+)`\s*-+\s*(.*?)(?=-+`|$)", content, re.DOTALL)
            for name, desc in cmd_matches:
                desc = desc.strip().split("\n")[0]
                commands.append(
                    SkillCommand(
                        name=name.strip(),
                        skill_name=frontmatter.get("name", "unknown"),
                        description=desc,
                    )
                )
        except Exception as e:
            pass

    return commands


def parse_skill_file(skill_path: str) -> tuple[SkillMetadata, list[SkillCommand], str]:
    """Parse complete skill file.

    Returns:
        metadata: Parsed metadata
        commands: Extracted commands
        content: Skill content (without frontmatter)
    """
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter = parse_frontmatter(content)
    metadata = extract_metadata(frontmatter)
    commands = extract_commands(skill_path, frontmatter)

    content_without_frontmatter = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content_without_frontmatter = parts[2].strip()

    return metadata, commands, content_without_frontmatter


def serialize_metadata(metadata: SkillMetadata) -> dict[str, Any]:
    """Serialize metadata to dictionary."""
    return {
        "name": metadata.name,
        "description": metadata.description,
        "emoji": metadata.emoji,
        "homepage": metadata.homepage,
        "os": metadata.os,
        "always": metadata.always,
        "skill_key": metadata.skill_key,
        "primary_env": metadata.primary_env,
        "version": metadata.version,
        "author": metadata.author,
        "license": metadata.license,
        "requires": {
            "bins": metadata.requires_bins,
            "any_bins": metadata.requires_any_bins,
            "env": metadata.requires_env,
            "config": metadata.requires_config,
        },
        "install": [
            {
                "kind": spec.kind,
                "package": spec.package,
                "module": spec.module,
                "url": spec.url,
                "target_dir": spec.target_dir,
                "extract": spec.extract,
                "stripComponents": spec.strip_components,
            }
            for spec in metadata.install
        ],
    }


def format_metadata_markdown(metadata: SkillMetadata) -> str:
    """Format metadata as markdown frontmatter."""
    lines = ["---", f"name: {metadata.name}", f"description: {metadata.description}"]

    if metadata.emoji:
        lines.append(f"emoji: {metadata.emoji}")

    if metadata.homepage:
        lines.append(f"homepage: {metadata.homepage}")

    if metadata.os:
        lines.append(f"os: {json.dumps(metadata.os)}")

    if metadata.always:
        lines.append("always: true")

    if metadata.skill_key:
        lines.append(f"skill_key: {metadata.skill_key}")

    requires = []
    if metadata.requires_bins:
        requires.append(f"  bins: {json.dumps(metadata.requires_bins)}")
    if metadata.requires_any_bins:
        requires.append(f"  any_bins: {json.dumps(metadata.requires_any_bins)}")
    if metadata.requires_env:
        requires.append(f"  env: {json.dumps(metadata.requires_env)}")
    if metadata.requires_config:
        requires.append(f"  config: {json.dumps(metadata.requires_config)}")

    if requires:
        lines.append("requires:")
        lines.extend(requires)

    if metadata.install:
        lines.append("install:")
        for spec in metadata.install:
            lines.append(f"  - kind: {spec.kind}")
            if spec.package:
                lines.append(f"    package: {spec.package}")
            if spec.module:
                lines.append(f"    module: {spec.module}")
            if spec.url:
                lines.append(f"    url: {spec.url}")

    lines.append("---")
    return "\n".join(lines)


__all__ = [
    "SkillCommand",
    "SkillInstallSpec",
    "SkillMetadata",
    "extract_commands",
    "extract_metadata",
    "format_metadata_markdown",
    "parse_frontmatter",
    "parse_skill_file",
    "parse_yaml",
    "serialize_metadata",
]
