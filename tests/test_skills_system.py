"""Tests for enhanced skills system."""

import pytest
import tempfile
import os
from pathlib import Path

from nanobot.skills.frontmatter import (
    parse_frontmatter,
    extract_metadata,
    parse_skill_file,
    SkillMetadata,
)
from nanobot.skills.eligibility import (
    evaluate_eligibility,
    has_binary,
    has_env,
    resolve_runtime_platform,
    EligibilityResult,
)
from nanobot.skills.loader import (
    SkillLoader,
    discover_skills,
    looks_like_skills_dir,
    resolve_bundled_skills_dir,
    SkillEntry,
)
from nanobot.skills.integration import SkillsIntegration


class TestFrontmatterParsing:
    """Test YAML frontmatter parsing."""

    def test_parse_simple_frontmatter(self):
        """Test parsing simple frontmatter."""
        content = """---
name: test-skill
description: A test skill
emoji: 🧪
---

# Content
"""
        result = parse_frontmatter(content)

        assert result["name"] == "test-skill"
        assert result["description"] == "A test skill"
        assert result["emoji"] == "🧪"

    def test_parse_frontmatter_with_lists(self):
        """Test parsing frontmatter with lists."""
        content = """---
name: test-skill
os: ["darwin", "linux"]
requires:
  bins: ["node", "npm"]
  env: ["API_KEY"]
---

# Content
"""
        result = parse_frontmatter(content)

        assert result["os"] == ["darwin", "linux"]
        assert "bins" in result["requires"]
        assert "env" in result["requires"]

    def test_parse_empty_frontmatter(self):
        """Test parsing empty frontmatter."""
        content = """---
---

# Content
"""
        result = parse_frontmatter(content)
        assert isinstance(result, dict)

    def test_parse_no_frontmatter(self):
        """Test parsing content without frontmatter."""
        content = "# Just content"
        result = parse_frontmatter(content)
        assert result == {}


class TestMetadataExtraction:
    """Test metadata extraction from frontmatter."""

    def test_extract_basic_metadata(self):
        """Test extracting basic metadata."""
        frontmatter = {
            "name": "test-skill",
            "description": "Test description",
            "emoji": "🧪",
            "homepage": "https://example.com",
        }

        metadata = extract_metadata(frontmatter)

        assert metadata.name == "test-skill"
        assert metadata.description == "Test description"
        assert metadata.emoji == "🧪"
        assert metadata.homepage == "https://example.com"

    def test_extract_requirements(self):
        """Test extracting requirements."""
        frontmatter = {
            "name": "test-skill",
            "description": "Test",
            "requires": {
                "bins": ["node"],
                "env": ["API_KEY"],
            },
        }

        metadata = extract_metadata(frontmatter)

        assert metadata.requires_bins == ["node"]
        assert metadata.requires_env == ["API_KEY"]


class TestSkillFileParsing:
    """Test complete skill file parsing."""

    def test_parse_skill_file(self, tmp_path):
        """Test parsing a complete skill file."""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"

        content = """---
name: test-skill
description: A test skill
requires:
  bins: ["python3"]
---

# Test Skill

This is a test skill.
"""
        skill_file.write_text(content)

        metadata, commands, skill_content = parse_skill_file(str(skill_file))

        assert metadata.name == "test-skill"
        assert metadata.description == "A test skill"
        assert metadata.requires_bins == ["python3"]
        assert "test skill" in skill_content.lower()


class TestEligibilityEvaluation:
    """Test skill eligibility evaluation."""

    def test_always_eligible(self):
        """Test always eligible skills."""
        result = evaluate_eligibility(always=True)

        assert result.eligible is True

    def test_os_mismatch(self):
        """Test OS compatibility check."""
        result = evaluate_eligibility(
            os_list=["win32"],  # Require Windows
        )

        # On macOS/Linux, this should fail
        current_os = resolve_runtime_platform()
        if current_os != "win32":
            assert result.eligible is False
            assert result.os_mismatch is True

    def test_missing_binary(self):
        """Test missing binary detection."""
        result = evaluate_eligibility(
            requires_bins=["nonexistent_binary_xyz"],
        )

        assert result.eligible is False
        assert result.missing_bins is not None

    def test_existing_binary(self):
        """Test existing binary detection."""
        result = evaluate_eligibility(
            requires_bins=["python3"],
        )

        # Should pass if python3 exists
        if has_binary("python3"):
            assert result.eligible is True

    def test_missing_env_var(self):
        """Test missing environment variable."""
        result = evaluate_eligibility(
            requires_env=["NONEXISTENT_ENV_VAR_XYZ"],
        )

        assert result.eligible is False
        assert result.missing_env is not None

    def test_combined_requirements(self):
        """Test combined requirements."""
        result = evaluate_eligibility(
            os_list=["darwin", "linux", "win32"],  # All OS
            requires_bins=["python3"],
            requires_env=[],
        )

        # Should pass if python3 exists
        if has_binary("python3"):
            assert result.eligible is True


class TestRuntimePlatform:
    """Test runtime platform detection."""

    def test_resolve_platform(self):
        """Test platform resolution."""
        platform = resolve_runtime_platform()
        assert platform in ["darwin", "linux", "win32", "unknown"]


class TestSkillLoader:
    """Test skill loader functionality."""

    def test_looks_like_skills_dir(self, tmp_path):
        """Test skills directory detection."""
        # Empty dir is not a skills dir
        assert looks_like_skills_dir(str(tmp_path)) is False

        # Dir with .md files is a skills dir
        (tmp_path / "test.md").touch()
        assert looks_like_skills_dir(str(tmp_path)) is True

        # Clean up
        (tmp_path / "test.md").unlink()

        # Dir with SKILL.md is a skills dir
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").touch()
        assert looks_like_skills_dir(str(tmp_path)) is True

    def test_discover_skills(self, tmp_path):
        """Test skill discovery."""
        # Create a skills directory
        skill1 = tmp_path / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("""---
name: skill-one
description: First skill
---
# Content
""")

        skill2 = tmp_path / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("""---
name: skill-two
description: Second skill
---
# Content
""")

        skills = discover_skills(str(tmp_path), "test")

        assert len(skills) == 2
        assert any(s.name == "skill-one" for s in skills)
        assert any(s.name == "skill-two" for s in skills)

    def test_skill_loader_creation(self):
        """Test skill loader can be created."""
        loader = SkillLoader()
        assert loader is not None

    def test_load_all_skills(self):
        """Test loading all skills."""
        loader = SkillLoader()
        skills = loader.load_all()

        # Should return a list
        assert isinstance(skills, list)

        # Should find bundled skills
        assert len(skills) > 0


class TestSkillsIntegration:
    """Test skills system integration."""

    def test_integration_creation(self):
        """Test skills integration can be created."""
        integration = SkillsIntegration(
            workspace=Path("."),
            skills_enabled=False,  # Disable for testing
        )
        assert integration is not None

    def test_integration_disabled(self):
        """Test disabled skills system."""
        integration = SkillsIntegration(
            workspace=Path("."),
            skills_enabled=False,
        )

        result = integration.initialize()
        assert result is False

    def test_get_skill_context_empty(self):
        """Test skill context when no skills."""
        integration = SkillsIntegration(
            workspace=Path("."),
            skills_enabled=False,
        )

        context = integration.get_skill_context()
        assert context == ""

    def test_list_skills(self):
        """Test listing skills."""
        integration = SkillsIntegration(
            workspace=Path("."),
            skills_enabled=True,
        )

        integration.initialize()
        skills = integration.list_skills()

        assert isinstance(skills, list)


class TestEligibilityResult:
    """Test EligibilityResult dataclass."""

    def test_eligible_result(self):
        """Test eligible result."""
        result = EligibilityResult(eligible=True)

        assert result.eligible is True
        assert result.reason is None

    def test_ineligible_result_with_reason(self):
        """Test ineligible result with reason."""
        result = EligibilityResult(
            eligible=False,
            reason="Missing dependency",
        )

        assert result.eligible is False
        assert result.reason == "Missing dependency"


@pytest.mark.asyncio
class TestSkillsAsync:
    """Async tests for skills system."""

    async def test_integration_initialization(self):
        """Test async initialization."""
        integration = SkillsIntegration(
            workspace=Path("."),
            skills_enabled=True,
        )

        # Initialize should complete without error
        try:
            integration.initialize()
        except Exception as e:
            pytest.fail(f"Initialization failed: {e}")


# Integration tests with actual skill files
class TestBundledSkills:
    """Test bundled skill files."""

    def test_github_skill_exists(self):
        """Test GitHub skill file exists and is valid."""
        from nanobot.skills.loader import resolve_bundled_skills_dir

        bundled_dir = resolve_bundled_skills_dir()
        if bundled_dir:
            github_skill = Path(bundled_dir) / "github" / "SKILL.md"
            if github_skill.exists():
                metadata, _, _ = parse_skill_file(str(github_skill))
                assert metadata.name == "github"

    def test_weather_skill_exists(self):
        """Test weather skill file exists and is valid."""
        from nanobot.skills.loader import resolve_bundled_skills_dir

        bundled_dir = resolve_bundled_skills_dir()
        if bundled_dir:
            weather_skill = Path(bundled_dir) / "weather" / "SKILL.md"
            if weather_skill.exists():
                metadata, _, _ = parse_skill_file(str(weather_skill))
                assert metadata.name == "weather"
