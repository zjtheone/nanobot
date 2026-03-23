"""Skills system integration for AgentLoop.

Provides skill loading, eligibility checking, and skill-based tool registration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger


class SkillsIntegration:
    """Skills system integration manager."""

    def __init__(
        self,
        workspace: Path | None = None,
        skills_enabled: bool = True,
        bundled_skills_dir: str | None = None,
        workspace_skills_dir: str | None = None,
        managed_skills_dir: str | None = None,
        allow_bundled: bool = True,
    ):
        self.workspace = workspace or Path.cwd()
        self.skills_enabled = skills_enabled
        self.bundled_skills_dir = bundled_skills_dir
        self.workspace_skills_dir = workspace_skills_dir
        self.managed_skills_dir = managed_skills_dir
        self.allow_bundled = allow_bundled

        self._loader = None
        self._loaded_skills = []
        self._eligible_skills = []

    def initialize(self) -> bool:
        """Initialize skills system."""
        if not self.skills_enabled:
            logger.info("Skills system disabled")
            return False

        try:
            from nanobot.skills.loader import (
                SkillLoader,
                resolve_bundled_skills_dir,
                resolve_workspace_skills_dir,
            )

            bundled_dir = self.bundled_skills_dir or resolve_bundled_skills_dir()
            workspace_dir = self.workspace_skills_dir or resolve_workspace_skills_dir(
                str(self.workspace)
            )

            self._loader = SkillLoader(
                bundled_dir=bundled_dir,
                workspace_dir=workspace_dir,
                managed_dir=self.managed_skills_dir,
            )

            self._loaded_skills = self._loader.load_all()
            self._eligible_skills = self._loader.get_eligible_skills()

            logger.info(
                f"Skills system initialized: {len(self._loaded_skills)} skills loaded, "
                f"{len(self._eligible_skills)} eligible"
            )

            return True
        except Exception as e:
            logger.error(f"Failed to initialize skills system: {e}")
            return False

    def get_skill_context(self) -> str:
        """Get skill context for agent prompt."""
        if not self._eligible_skills:
            return ""

        lines = ["## Available Skills", ""]

        for skill in self._eligible_skills:
            emoji = skill.metadata.emoji or "🔧"
            lines.append(f"- {emoji} **{skill.name}**: {skill.metadata.description}")

            if skill.metadata.requires_env:
                env_vars = ", ".join(f"`{env}`" for env in skill.metadata.requires_env)
                lines.append(f"  - Requires: {env_vars}")

        lines.append("")
        lines.append("Use skills by mentioning them in your requests.")

        return "\n".join(lines)

    def get_skills_by_name(self, names: list[str]) -> list[dict[str, Any]]:
        """Get skills by names."""
        skills = []

        for skill in self._eligible_skills:
            if skill.name in names:
                skills.append(
                    {
                        "name": skill.name,
                        "description": skill.metadata.description,
                        "commands": [],
                    }
                )

        return skills

    def list_skills(self) -> list[dict[str, Any]]:
        """List all skills."""
        if not self._loader:
            return []

        return self._loader.list_skills()

    def get_skill_content(self, skill_name: str) -> str | None:
        """Get skill content."""
        if not self._loader:
            return None

        return self._loader.get_skill_content(skill_name)

    def reload_skills(self) -> int:
        """Reload skills and return count."""
        if not self._loader:
            return 0

        self._loaded_skills = self._loader.load_all()
        self._eligible_skills = self._loader.get_eligible_skills()

        return len(self._eligible_skills)

    def is_skill_available(self, skill_name: str) -> bool:
        """Check if skill is available and eligible."""
        for skill in self._eligible_skills:
            if skill.name == skill_name:
                return True
        return False

    def get_eligible_count(self) -> int:
        """Get count of eligible skills."""
        return len(self._eligible_skills)

    def get_loaded_count(self) -> int:
        """Get count of loaded skills."""
        return len(self._loaded_skills)


__all__ = ["SkillsIntegration"]
