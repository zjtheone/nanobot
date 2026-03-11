# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**nanobot** is an ultra-lightweight personal AI assistant framework (~4,000 lines of core agent code). Python package name: `nanobot-ai`. Requires Python >=3.11.

## Build & Development Commands

```bash
# Install from source (editable)
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check nanobot/
ruff format nanobot/

# Run all tests
python -m pytest tests/ -xvs

# Run a single test file
python -m pytest tests/test_cron.py -xvs

# Run a single test
python -m pytest tests/test_cron.py::test_function_name -xvs

# Verify core line count
bash core_agent_lines.sh
```

## Lint Configuration

Ruff is configured in `pyproject.toml`: line-length 100, target Python 3.11, rules `E,F,I,N,W`, ignores `E501`. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.

## Architecture

### Core Loop (`nanobot/agent/loop.py`)
The `AgentLoop` class is the engine: receive message from bus → build context (history + memory + skills) → call LLM with streaming → execute tool calls in a loop (max 20 iterations) → send response via bus.

### Message Bus (`nanobot/bus/`)
`InboundMessage` flows in from channels, `OutboundMessage` flows out. Decouples channels from the agent loop.

### Provider Registry (`nanobot/providers/registry.py`)
Single source of truth for LLM providers. Declarative `ProviderSpec` dataclass — adding a new provider requires only:
1. Add a `ProviderSpec` to `PROVIDERS` in `registry.py`
2. Add a field to `ProvidersConfig` in `config/schema.py`

No if-elif chains. Env vars, model prefixing, config matching, and status display all derive automatically.

### Channels (`nanobot/channels/`)
Plugin-based chat integrations. Each channel extends `BaseChannel`. The `ChannelManager` auto-discovers and loads enabled channels. Supported: Telegram, Discord, Slack, WhatsApp (bridge), Feishu, DingTalk, Mochat, Email, QQ, Matrix.

### Configuration (`nanobot/config/`)
Pydantic v2 models in `schema.py`, loaded from `~/.nanobot/config.json` via `loader.py`.

### Context Assembly (`nanobot/agent/context.py`)
`ContextBuilder` assembles the system prompt from: bootstrap files (AGENTS.md, SOUL.md, USER.md, TOOLS.md, IDENTITY.md), project instructions, repository map, memory, skills, and conversation history.

### Memory (`nanobot/agent/memory.py`)
Two-layer: `MEMORY.md` (long-term facts/decisions) and `HISTORY.md` (timestamped timeline). Optional vector memory via `memory_vector.py` using sentence-transformers + sqlite-vec.

### Tools (`nanobot/agent/tools/`)
Central `ToolRegistry` in `registry.py`. Built-in tools: filesystem (read/write/edit/list), shell (exec), web (search/fetch), git, MCP, spawn (subagent), cron, memory search.

### Skills (`nanobot/skills/`)
Markdown files with YAML frontmatter. Builtin skills in `nanobot/skills/`, user skills in `~/.nanobot/workspace/skills/`.

### Sessions (`nanobot/session/manager.py`)
Per-user/per-channel conversation tracking keyed by `channel:chat_id`.

## Entry Points

- **CLI**: `nanobot/cli/commands.py` — Typer app. Main commands: `onboard`, `agent`, `gateway`, `status`, `cron`
- **Package script**: `nanobot = "nanobot.cli.commands:app"` (defined in `pyproject.toml`)

## Key Directories Outside Main Package

- `bridge/` — WhatsApp bridge (TypeScript/Node.js)
- `web_console/` — Streamlit-based web UI
- `tests/` — pytest test suite
- `docs/` — Documentation and images
