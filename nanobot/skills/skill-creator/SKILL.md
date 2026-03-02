---
name: skill-creator
description: Create or update AgentSkills. Use when designing, structuring, or packaging skills with scripts, references, and assets.
---

# Skill Creator

This skill provides guidance for creating effective skills.

## About Skills

Skills are modular, self-contained packages that extend the agent's capabilities by providing specialized knowledge, workflows, and tools.

### What Skills Provide

1. **Specialized workflows** - Multi-step procedures for specific domains
2. **Tool integrations** - Instructions for working with specific file formats or APIs
3. **Domain expertise** - Company-specific knowledge, schemas, business logic
4. **Bundled resources** - Scripts, references, and assets for complex and repetitive tasks

## Core Principles

### Concise is Key

**The context window is a public good.** Only add context the agent doesn't already have. Prefer concise examples over verbose explanations.

### Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/          - Executable code
    ├── references/       - Documentation (loaded as needed)
    └── assets/           - Files for output (templates, icons, etc.)
```

### Progressive Disclosure

Skills use a three-level loading system:

1. **Metadata** - Always in context (~100 words)
2. **SKILL.md body** - When skill triggers (target <500 lines)
3. **Bundled resources** - As needed by the agent

**Key principle:** Keep only core workflow in SKILL.md. Move variant-specific details to reference files.

For detailed design patterns, see [design-principles.md](references/design-principles.md).

## Skill Creation Process

Follow these steps in order:

1. **Understand** the skill with concrete examples
2. **Plan** reusable contents (scripts, references, assets)
3. **Initialize** the skill (run `init_skill.py`)
4. **Edit** the skill (implement resources and write SKILL.md)
5. **Package** the skill (run `package_skill.py`)
6. **Iterate** based on real usage

For complete workflow details, see [creation-process.md](references/creation-process.md).

### Quick Reference

**Initialize a new skill:**

```bash
scripts/init_skill.py my-skill --path skills/public [--resources scripts,references] [--examples]
```

**Package a skill:**

```bash
scripts/package_skill.py <path/to/skill-folder>
```

The packaging script automatically validates:
- YAML frontmatter format and required fields
- Skill naming conventions and directory structure
- Description completeness and quality
- File organization and resource references

## What NOT to Include

A skill should only contain essential files. **Do NOT create:**

- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md

The skill should only contain information needed for the agent to do the job at hand.

## Related References

- [Design Principles](references/design-principles.md) - Core principles for effective skill design
- [Creation Process](references/creation-process.md) - Complete workflow for creating skills
- [Workflows](references/workflows.md) - Sequential workflows and conditional logic
- [Output Patterns](references/output-patterns.md) - Template and example patterns
