---
name: github
description: GitHub integration for repositories, issues, and pull requests
emoji: 🐙
homepage: https://github.com
os: ["darwin", "linux", "win32"]
requires:
  env: ["GITHUB_TOKEN"]
always: false
---

# GitHub Skill

GitHub integration for Nanobot.

## Commands

- `gh_repo <repo>` - Get repository information
- `gh_issue <repo> <number>` - Get issue details
- `gh_pr <repo> <number>` - Get pull request details
- `gh_search <query>` - Search repositories

## Dependencies

- `GITHUB_TOKEN` environment variable

## Usage

```
@github gh_repo nanobot/nanobot
@github gh_issue nanobot/nanobot 123
@github search "ai assistant"
```
