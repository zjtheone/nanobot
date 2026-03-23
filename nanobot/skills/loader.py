"""Bundled skills directory resolution and loading.

参考 OpenClaw 的 bundled-dir.ts 和 loader.ts 实现：
- 捆绑技能目录解析
- 技能加载机制
- 工作区技能发现
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nanobot.skills.frontmatter import (
    SkillMetadata,
    parse_skill_file,
    serialize_metadata,
)
from nanobot.skills.eligibility import (
    EligibilityResult,
    evaluate_eligibility,
)


@dataclass
class SkillEntry:
    """Loaded skill entry."""

    name: str
    path: str
    source: str  # "bundled", "workspace", "managed"
    metadata: SkillMetadata
    eligible: bool = True
    eligibility_reason: str | None = None


def looks_like_skills_dir(dir_path: str) -> bool:
    """Check if directory looks like a skills directory."""
    try:
        entries = os.listdir(dir_path)
        for entry in entries:
            if entry.startswith("."):
                continue

            full_path = os.path.join(dir_path, entry)

            if os.path.isfile(full_path) and entry.endswith(".md"):
                return True

            if os.path.isdir(full_path):
                skill_md = os.path.join(full_path, "SKILL.md")
                if os.path.exists(skill_md):
                    return True
    except Exception:
        return False

    return False


def resolve_bundled_skills_dir() -> str | None:
    """Resolve bundled skills directory.

    Search order:
    1. OPENCLAW_BUNDLED_SKILLS_DIR env var
    2. Sibling skills/ directory (for compiled binaries)
    3. nanobot/skills/ from package root
    4. Walk up directory tree looking for skills/
    """
    override = os.environ.get("NANOBOT_BUNDLED_SKILLS_DIR", "").strip()
    if override:
        return override

    try:
        exec_path = os.path.dirname(os.path.abspath(__file__))
        exec_dir = os.path.dirname(exec_path)
        sibling = os.path.join(exec_dir, "skills")
        if os.path.exists(sibling) and looks_like_skills_dir(sibling):
            return sibling
    except Exception:
        pass

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for depth in range(6):
            candidate = os.path.join(current_dir, "skills")
            if looks_like_skills_dir(candidate):
                return candidate

            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
    except Exception:
        pass

    return None


def resolve_workspace_skills_dir(workspace_root: str | None = None) -> str | None:
    """Resolve workspace skills directory."""
    if not workspace_root:
        workspace_root = os.getcwd()

    candidates = [
        os.path.join(workspace_root, ".nanobot", "skills"),
        os.path.join(workspace_root, "skills"),
        os.path.join(workspace_root, ".skills"),
    ]

    for candidate in candidates:
        if os.path.exists(candidate) and looks_like_skills_dir(candidate):
            return candidate

    return None


def discover_skills(
    skills_dir: str,
    source: str = "bundled",
) -> list[SkillEntry]:
    """Discover all skills in directory."""
    skills = []

    if not os.path.exists(skills_dir):
        return skills

    for entry in os.listdir(skills_dir):
        if entry.startswith("."):
            continue

        entry_path = os.path.join(skills_dir, entry)
        skill_md_path = None

        if os.path.isdir(entry_path):
            skill_md_path = os.path.join(entry_path, "SKILL.md")
        elif os.path.isfile(entry_path) and entry.endswith(".md"):
            skill_md_path = entry_path

        if skill_md_path and os.path.exists(skill_md_path):
            try:
                metadata, _, _ = parse_skill_file(skill_md_path)

                eligibility = evaluate_eligibility(
                    os_list=metadata.os,
                    requires_bins=metadata.requires_bins,
                    requires_any_bins=metadata.requires_any_bins,
                    requires_env=metadata.requires_env,
                    requires_config=metadata.requires_config,
                    always=metadata.always,
                )

                skills.append(
                    SkillEntry(
                        name=metadata.name,
                        path=skill_md_path,
                        source=source,
                        metadata=metadata,
                        eligible=eligibility.eligible,
                        eligibility_reason=eligibility.reason,
                    )
                )
            except Exception as e:
                pass

    return skills


class SkillLoader:
    """Skill loader for bundled and workspace skills."""

    def __init__(
        self,
        bundled_dir: str | None = None,
        workspace_dir: str | None = None,
        managed_dir: str | None = None,
    ):
        self.bundled_dir = bundled_dir or resolve_bundled_skills_dir()
        self.workspace_dir = workspace_dir
        self.managed_dir = managed_dir

        self._loaded_skills: dict[str, SkillEntry] = {}
        self._bundled_skills: list[SkillEntry] = []
        self._workspace_skills: list[SkillEntry] = []
        self._managed_skills: list[SkillEntry] = []

    def load_all(self) -> list[SkillEntry]:
        """Load all skills from all directories."""
        self._loaded_skills.clear()
        self._bundled_skills.clear()
        self._workspace_skills.clear()
        self._managed_skills.clear()

        if self.bundled_dir:
            self._bundled_skills = discover_skills(self.bundled_dir, "bundled")
            for skill in self._bundled_skills:
                self._loaded_skills[skill.name] = skill

        if self.workspace_dir:
            self._workspace_skills = discover_skills(self.workspace_dir, "workspace")
            for skill in self._workspace_skills:
                if skill.name not in self._loaded_skills:
                    self._loaded_skills[skill.name] = skill

        if self.managed_dir:
            self._managed_skills = discover_skills(self.managed_dir, "managed")
            for skill in self._managed_skills:
                if skill.name not in self._loaded_skills:
                    self._loaded_skills[skill.name] = skill

        return list(self._loaded_skills.values())

    def load_skill(self, skill_name: str) -> SkillEntry | None:
        """Load specific skill by name."""
        if skill_name in self._loaded_skills:
            return self._loaded_skills[skill_name]

        all_skills = self.load_all()
        return self._loaded_skills.get(skill_name)

    def get_eligible_skills(self) -> list[SkillEntry]:
        """Get all eligible skills."""
        return [s for s in self._loaded_skills.values() if s.eligible]

    def get_bundled_skills(self) -> list[SkillEntry]:
        """Get bundled skills."""
        return self._bundled_skills.copy()

    def get_workspace_skills(self) -> list[SkillEntry]:
        """Get workspace skills."""
        return self._workspace_skills.copy()

    def get_managed_skills(self) -> list[SkillEntry]:
        """Get managed skills."""
        return self._managed_skills.copy()

    def reload_skill(self, skill_name: str) -> SkillEntry | None:
        """Reload specific skill."""
        for skills_list in [self._bundled_skills, self._workspace_skills, self._managed_skills]:
            for i, skill in enumerate(skills_list):
                if skill.name == skill_name:
                    try:
                        metadata, _, _ = parse_skill_file(skill.path)
                        eligibility = evaluate_eligibility(
                            os_list=metadata.os,
                            requires_bins=metadata.requires_bins,
                            requires_any_bins=metadata.requires_any_bins,
                            requires_env=metadata.requires_env,
                            requires_config=metadata.requires_config,
                            always=metadata.always,
                        )

                        new_entry = SkillEntry(
                            name=skill_name,
                            path=skill.path,
                            source=skill.source,
                            metadata=metadata,
                            eligible=eligibility.eligible,
                            eligibility_reason=eligibility.reason,
                        )

                        skills_list[i] = new_entry
                        self._loaded_skills[skill_name] = new_entry
                        return new_entry
                    except Exception as e:
                        return None

        return None

    def get_skill_content(self, skill_name: str) -> str | None:
        """Get skill content (without frontmatter)."""
        skill = self.load_skill(skill_name)
        if not skill:
            return None

        try:
            _, _, content = parse_skill_file(skill.path)
            return content
        except Exception:
            return None

    def get_skill_metadata(self, skill_name: str) -> dict[str, Any] | None:
        """Get skill metadata as dict."""
        skill = self.load_skill(skill_name)
        if not skill:
            return None

        return serialize_metadata(skill.metadata)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all skills with basic info."""
        return [
            {
                "name": skill.name,
                "description": skill.metadata.description,
                "source": skill.source,
                "eligible": skill.eligible,
                "emoji": skill.metadata.emoji,
            }
            for skill in self._loaded_skills.values()
        ]


__all__ = [
    "SkillEntry",
    "SkillLoader",
    "discover_skills",
    "looks_like_skills_dir",
    "resolve_bundled_skills_dir",
    "resolve_workspace_skills_dir",
]
