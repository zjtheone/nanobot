#!/usr/bin/env python3
"""Test browser tool and skills system."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_browser_tool():
    """Test browser tool."""
    print("\n=== Testing Browser Tool ===\n")

    try:
        from nanobot.agent.tools.browser.browser_tool import BrowserTool

        browser = BrowserTool(headless=True, navigation_guard=True)

        print("✓ BrowserTool created successfully")

        result = await browser.execute(action="navigate", url="https://example.com")
        print(f"✓ Navigate result: {result}")

        await browser.execute(action="close")
        print("✓ Browser closed")

        return True
    except Exception as e:
        print(f"✗ Browser tool test failed: {e}")
        return False


async def test_skills_loader():
    """Test skills loader."""
    print("\n=== Testing Skills Loader ===\n")

    try:
        from nanobot.skills.loader import SkillLoader, resolve_bundled_skills_dir

        bundled_dir = resolve_bundled_skills_dir()
        print(f"✓ Resolved bundled skills dir: {bundled_dir}")

        loader = SkillLoader(bundled_dir=bundled_dir)
        skills = loader.load_all()

        print(f"✓ Loaded {len(skills)} skills")

        for skill in skills[:5]:
            print(f"  - {skill.name}: {skill.metadata.description} (eligible: {skill.eligible})")

        eligible = loader.get_eligible_skills()
        print(f"✓ Eligible skills: {len(eligible)}")

        return True
    except Exception as e:
        print(f"✗ Skills loader test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_frontmatter_parsing():
    """Test frontmatter parsing."""
    print("\n=== Testing Frontmatter Parsing ===\n")

    try:
        from nanobot.skills.frontmatter import parse_skill_file

        skills_dir = Path(__file__).parent / "nanobot" / "skills" / "bundled"

        if not skills_dir.exists():
            print("⚠ Skills directory not found, skipping test")
            return True

        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    metadata, commands, content = parse_skill_file(str(skill_md))
                    print(f"✓ Parsed skill: {metadata.name}")
                    print(f"  Description: {metadata.description}")
                    print(f"  Requires env: {metadata.requires_env}")

        return True
    except Exception as e:
        print(f"✗ Frontmatter parsing failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_eligibility():
    """Test eligibility evaluation."""
    print("\n=== Testing Eligibility Evaluation ===\n")

    try:
        from nanobot.skills.eligibility import evaluate_eligibility, has_binary

        result = evaluate_eligibility(
            os_list=["darwin", "linux", "win32"],
            requires_bins=["python3"],
            requires_env=[],
            always=False,
        )

        print(f"✓ Eligibility result: {result.eligible}")
        if result.reason:
            print(f"  Reason: {result.reason}")

        python_available = has_binary("python3")
        print(f"✓ Python3 available: {python_available}")

        return True
    except Exception as e:
        print(f"✗ Eligibility test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Nanobot Enhanced Features Test Suite")
    print("=" * 60)

    results = []

    results.append(("Frontmatter Parsing", test_frontmatter_parsing()))
    results.append(("Eligibility Evaluation", test_eligibility()))
    results.append(("Skills Loader", await test_skills_loader()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
