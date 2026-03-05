"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Dict

import json_repair
from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMStreamChunk, LLMProvider
from nanobot.agent.checkpoint import CheckpointManager
from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryStore
from nanobot.agent.permissions import PermissionGate, PermissionResult
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.orchestrator import DecomposeAndSpawnTool, AggregateResultsTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.subagent import SubagentManager
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import ExecToolConfig, AgentsConfig
    from nanobot.cron.service import CronService


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        agent_id: str = "default",  # Agent identifier
        model: str | None = None,
        max_iterations: int = 20,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        memory_window: int = 50,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        context_window: int = 120000,
        on_tool_call: Callable[[str, str, str], None] | None = None,
        auto_verify: bool = True,
        auto_verify_command: str = "",
        sandbox: bool = False,
        permission_mode: str = "auto",
        thinking_budget: int = 0,
        memory_search_config: Optional[Dict[str, Any]] = None,
        mcp_servers: dict | None = None,
        on_thinking: Callable[[str], None] | None = None,
        on_iteration: Callable[[int, int], None] | None = None,
        on_tool_start: Callable[[str, dict], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_plan_progress: Callable[[list], None] | None = None,
        agents_config: "AgentsConfig | None" = None,  # 新增：用于 Broadcast 工具
    ):
        from nanobot.config.schema import ExecToolConfig
        from nanobot.cron.service import CronService

        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.agent_id = agent_id  # Agent identifier for A2A and Orchestrator
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.frequency_penalty = frequency_penalty
        self.memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.context_window = context_window
        self.on_tool_call = on_tool_call
        self.auto_verify = auto_verify
        self.auto_verify_command = auto_verify_command
        self.sandbox = sandbox
        self.thinking_budget = thinking_budget
        self.memory_search_config = memory_search_config
        self.on_thinking = on_thinking
        self.on_iteration = on_iteration
        self.on_tool_start = on_tool_start
        self.on_status = on_status
        self.on_plan_progress = on_plan_progress

        # MCP support (from nanobot version)
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        
        # Store agents config for Broadcast tool
        self._agents_config = agents_config
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()  # Session keys with consolidation in progress

        # Checkpoint system (Phase 1A)
        self.checkpoint = CheckpointManager(workspace)

        # Permission gate (Phase 1C)
        self.permission_gate = PermissionGate(
            mode=permission_mode,
            workspace=str(workspace),
        )

        self.context = ContextBuilder(workspace, memory_search_config)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        # Persistent shell session (Shell or Docker)
        if self.sandbox:
            from nanobot.agent.terminal.docker_session import DockerSession

            image = self.exec_config.sandbox_image
            self.shell_session = DockerSession(workspace, image=image)
        else:
            from nanobot.agent.terminal.session import ShellSession

            self.shell_session = ShellSession(workspace)

        # LSP Manager (Phase 7)
        from nanobot.agent.code.lsp import LSPManager

        self.lsp_manager = LSPManager(workspace)

        # Metrics Tracker (Phase 9)
        from nanobot.agent.metrics import MetricsTracker

        self.metrics = MetricsTracker(workspace)

        # Conversation compactor (Phase 2B)
        from nanobot.agent.compaction import ConversationCompactor

        self.compactor = ConversationCompactor(provider, model=self.model)

        # Hooks system (Phase 4B)
        from nanobot.agent.hooks import HookRegistry

        self.hooks = HookRegistry()

        # MCP manager (Phase 4A)
        from nanobot.mcp.registry import MCPManager

        self.mcp_manager = MCPManager()

        self._running = False
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir, checkpoint=self.checkpoint))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir, checkpoint=self.checkpoint))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))

        # Undo / checkpoint tools (Phase 1A)
        from nanobot.agent.tools.undo import UndoTool, ListChangesTool

        self.tools.register(UndoTool(self.checkpoint))
        self.tools.register(ListChangesTool(self.checkpoint))

        # Git tools (Phase 1B)
        from nanobot.agent.tools.git import (
            GitStatusTool,
            GitDiffTool,
            GitCommitTool,
            GitLogTool,
            GitCheckoutTool,
        )

        ws = str(self.workspace)
        self.tools.register(GitStatusTool(ws))
        self.tools.register(GitDiffTool(ws))
        self.tools.register(GitCommitTool(ws))
        self.tools.register(GitLogTool(ws))
        self.tools.register(GitCheckoutTool(ws))

        # Batch edit tool (Phase 4C)
        from nanobot.agent.tools.batch_edit import BatchEditTool

        self.tools.register(BatchEditTool(self.checkpoint, allowed_dir=allowed_dir))

        # Shell tools
        # Standard exec tool (stateless or sandboxed)
        self.tools.register(
            ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                session=self.shell_session if self.sandbox else None,
            )
        )

        # Persistent shell tool (stateful)
        from nanobot.agent.tools.terminal import ShellTool

        self.tools.register(ShellTool(self.shell_session))

        # Code Intelligence Tools

        # Code Intelligence Tools
        from nanobot.agent.tools.code import ReadFileMapTool

        if self.context.repomap:
            self.tools.register(ReadFileMapTool(self.workspace, self.context.repomap))

        # Smart Context (Focus Mode)
        from nanobot.agent.tools.code_focused import ReadFileFocusedTool

        if hasattr(self.context, "folding_engine") and self.context.folding_engine:
            self.tools.register(ReadFileFocusedTool(self.workspace, self.context.folding_engine))

        # Semantic Search (LSP-Lite) - Phase 7
        from nanobot.agent.tools.lsp import LSPDefinitionTool, LSPReferencesTool, LSPHoverTool

        self.tools.register(LSPDefinitionTool(self.lsp_manager))
        self.tools.register(LSPReferencesTool(self.lsp_manager))
        self.tools.register(LSPHoverTool(self.lsp_manager))

        # Refactoring Tools (Phase 8)
        from nanobot.agent.tools.refactor import RefactorRenameTool

        self.tools.register(RefactorRenameTool(self.lsp_manager))

        # Metrics Tool (Phase 9)
        from nanobot.agent.tools.metrics import GetMetricsTool

        self.tools.register(GetMetricsTool(self.metrics))

        # Legacy Semantic Search (Index-based) - Keep for fallback or dedicated indexing
        from nanobot.agent.tools.search_semantic import FindDefinitionsTool, FindReferencesTool

        if hasattr(self.context, "symbol_index") and self.context.symbol_index:
            self.tools.register(FindDefinitionsTool(self.workspace, self.context.symbol_index))
            self.tools.register(FindReferencesTool(self.workspace, self.context.symbol_index))

        # Diagnostics (Phase 4)
        from nanobot.agent.diagnostics.tool import DiagnosticTool

        self.tools.register(DiagnosticTool(self.workspace))

        # Planning (Phase 5)
        from nanobot.agent.planner import Planner
        from nanobot.agent.tools.planner import PlanTool, UpdatePlanStepTool

        self.planner = Planner(self.provider, self.context, self.workspace)
        self.tools.register(PlanTool(self.planner))

        # Memory Search Tool (Phase 6)
        from nanobot.agent.tools.memory_search import MemorySearchTool
        self.tools.register(MemorySearchTool(self.context.memory))
        self.tools.register(UpdatePlanStepTool(self.planner))

        # Wire plan progress callback
        if self.on_plan_progress:
            from dataclasses import asdict
            self.planner._on_plan_progress = lambda steps: self.on_plan_progress(
                [asdict(s) for s in steps]
            )

        # Search tools
        from nanobot.agent.tools.search import GrepTool, FindFilesTool

        self.tools.register(GrepTool(allowed_dir=allowed_dir))
        self.tools.register(FindFilesTool(allowed_dir=allowed_dir))

        # Shell tool
        self.tools.register(
            ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
            )
        )

        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())

        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Orchestrator tools (for task decomposition)
        if self.agent_id == "orchestrator":
            decompose_tool = DecomposeAndSpawnTool(self)
            self.tools.register(decompose_tool)
            
            aggregate_tool = AggregateResultsTool(self)
            self.tools.register(aggregate_tool)
            logger.info("Registered Orchestrator tools for agent {}", self.agent_id)
        
        # Broadcast tool (for team communication)
        if self._agents_config:
            from nanobot.agent.tools.broadcast import BroadcastTool
            broadcast_tool = BroadcastTool(
                manager=self.subagents,
                agents_config=self._agents_config,
            )
            # Set context for broadcast tool
            broadcast_tool.set_context(
                channel="cli",
                chat_id="direct",
                session_key="cli:direct",
                agent_id="default",
            )
            self.tools.register(broadcast_tool)

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        # Start MCP servers and register their tools
        await self._start_mcp_servers()

        try:
            while self._running:
                try:
                    # Wait for next message
                    msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)

                    # Process it
                    try:
                        response = await self._process_message(msg)
                        if response:
                            await self.bus.publish_outbound(response)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        # Send error response
                        await self.bus.publish_outbound(
                            OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=f"Sorry, I encountered an error: {str(e)}",
                            )
                        )
                except asyncio.TimeoutError:
                    continue
        finally:
            if hasattr(self, "lsp_manager"):
                logger.info("Shutting down LSP manager...")
                await self.lsp_manager.shutdown()
            if hasattr(self, "mcp_manager"):
                logger.info("Shutting down MCP servers...")
                await self.mcp_manager.stop_all()
            # Close persistent shell session
            if hasattr(self, "shell_session") and hasattr(self.shell_session, "close"):
                try:
                    await self.shell_session.close()
                except Exception:
                    pass
            # Clean up checkpoints
            if hasattr(self, "checkpoint"):
                self.checkpoint.cleanup()

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _start_mcp_servers(self) -> None:
        """Start configured MCP servers and register their tools."""
        try:
            from nanobot.config.loader import load_config

            config = load_config()
            if config.mcp.servers:
                from nanobot.mcp.config import MCPConfig

                mcp_config = MCPConfig(
                    servers={name: server for name, server in config.mcp.servers.items()}
                )
                tools = await self.mcp_manager.start_servers(mcp_config)
                for tool in tools:
                    self.tools.register(tool)
                if tools:
                    logger.info(f"Registered {len(tools)} MCP tools")
        except Exception as e:
            logger.debug(f"MCP startup skipped: {e}")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.
            session_key: Override session key (used by process_direct).
            on_progress: Optional callback for intermediate output (defaults to bus publish).

        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)

        # Get session key first
        key = session_key or msg.session_key
        
        # Extract agent_id from session key for logging
        agent_id = key.split(":")[0] if key and ":" in key else "unknown"
        
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"🤖 [{agent_id}] Processing: {preview}")
        session = self.sessions.get_or_create(key)

        # Handle slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            # Capture messages before clearing (avoid race condition with background task)
            messages_to_archive = session.messages.copy()
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)

            async def _consolidate_and_cleanup():
                temp_session = Session(key=session.key)
                temp_session.messages = messages_to_archive
                await self._consolidate_memory(temp_session, archive_all=True)

            asyncio.create_task(_consolidate_and_cleanup())
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="New session started. Memory consolidation in progress.",
            )
        if cmd == "/help":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐈 nanobot commands:\n/new — Start a new conversation\n/help — Show available commands",
            )

        # Memory consolidation when session grows too large
        if len(session.messages) > self.memory_window and session.key not in self._consolidating:
            self._consolidating.add(session.key)

            async def _consolidate_and_unlock():
                try:
                    await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)

            asyncio.create_task(_consolidate_and_unlock())

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)

        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(max_messages=self.memory_window),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            plan_context=self.planner.get_progress_context(),
        )

        # Agent loop
        iteration = 0
        final_content = None
        total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        while iteration < self.max_iterations:
            iteration += 1

            # Notify iteration progress
            if self.on_iteration:
                try:
                    self.on_iteration(iteration, self.max_iterations)
                except Exception:
                    pass

            # Trim context if approaching window limit
            messages = self._trim_context(messages)
            messages = await self._compact_context(messages)

            # Notify status: thinking
            if self.on_status:
                try:
                    self.on_status("thinking")
                except Exception:
                    pass

            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                frequency_penalty=self.frequency_penalty,
                thinking_budget=self.thinking_budget,
            )

            # Track token usage
            if response.usage:
                for k in total_usage:
                    total_usage[k] += response.usage.get(k, 0)

                # Record metrics (Phase 9)
                self.metrics.record_tokens(
                    prompt=response.usage.get("prompt_tokens", 0),
                    completion=response.usage.get("completion_tokens", 0),
                )

            # Notify thinking content (non-streaming)
            if response.reasoning_content and self.on_thinking:
                try:
                    self.on_thinking(response.reasoning_content)
                except Exception:
                    pass

            # Handle tool calls
            if response.has_tool_calls:
                # Notify status: executing tools
                if self.on_status:
                    try:
                        self.on_status("executing_tools")
                    except Exception:
                        pass

                # Notify tool start for each tool
                for tc in response.tool_calls:
                    if self.on_tool_start:
                        try:
                            self.on_tool_start(tc.name, tc.arguments)
                        except Exception:
                            pass

                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),  # Must be JSON string
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages,
                    response.content,
                    tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                # Execute tools (with permission checks and parallel read-only execution)
                executed_tools = []
                last_modified_file = ""
                tool_results = await self._execute_tools(response.tool_calls)
                for tool_call, result in zip(response.tool_calls, tool_results):
                    result_preview = result[:120] + "..." if len(result) > 120 else result

                    # Notify callback
                    if self.on_tool_call:
                        try:
                            args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                            self.on_tool_call(tool_call.name, args_str[:100], result_preview)
                        except Exception:
                            pass

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
                    executed_tools.append(tool_call.name)
                    if tool_call.name in ("write_file", "edit_file"):
                        last_modified_file = tool_call.arguments.get("path", "")

                # Auto-verify after file modifications
                messages, _has_errors = await self._auto_verify(messages, executed_tools, last_modified_file)
            else:
                # No tool calls, we're done
                final_content = response.content
                if response.finish_reason == "error":
                    logger.warning("LLM returned error response, skipping session storage")
                break

        if final_content is None:
            if iteration >= self.max_iterations:
                final_content = f"I have reached the maximum number of steps ({self.max_iterations}) for this task. Please ask me to 'continue' if you want me to proceed."
            else:
                final_content = "I've completed processing but have no response to give."

        # Append token usage info
        if total_usage.get("total_tokens", 0) > 0:
            logger.info(f"Token usage: {total_usage}")

        # Log response preview
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info(f"Response to {msg.channel}:{msg.sender_id}: {preview}")

        # Save to session (skip error responses to avoid polluting history)
        is_error = response.finish_reason == "error" if response else False
        session.add_message("user", msg.content)
        if not is_error:
            session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata={**(msg.metadata or {}), "usage": total_usage},
        )

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).

        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")

        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)

        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )

        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                frequency_penalty=self.frequency_penalty,
            )

            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages,
                    response.content,
                    tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                # Get current session for agent_id
                current_session_key = list(self.sessions._cache.keys())[-1] if self.sessions._cache else None
                agent_id = current_session_key.split(":")[0] if current_session_key and ":" in current_session_key else "unknown"
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"🔄 [{agent_id}] Tool call: {tool_call.name}({args_str[:150]}...)")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break

        if final_content is None:
            final_content = "Background task completed."

        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=origin_channel, chat_id=origin_chat_id, content=final_content
        )

    async def _execute_tools(self, tool_calls: list) -> list[str]:
        """
        Execute tool calls with permission checks and parallel read-only execution.

        Read-only tools run concurrently; write/dangerous tools run sequentially.
        """
        from nanobot.agent.permissions import READ_ONLY_TOOLS

        results: list[str | None] = [None] * len(tool_calls)

        # Separate into parallel (read-only) and sequential groups
        parallel_indices = []
        sequential_indices = []
        for i, tc in enumerate(tool_calls):
            # Permission check
            decision = self.permission_gate.check(tc.name, tc.arguments)
            if decision.result == PermissionResult.DENY:
                results[i] = f"Permission denied: {decision.reason}"
                continue
            if decision.result == PermissionResult.ASK:
                approved = await self.permission_gate.request_approval(
                    tc.name,
                    tc.arguments,
                    description=f"{tc.name}({json.dumps(tc.arguments, ensure_ascii=False)[:100]})",
                )
                if not approved:
                    results[i] = "Tool call rejected by user."
                    continue

            if tc.name in READ_ONLY_TOOLS:
                parallel_indices.append(i)
            else:
                sequential_indices.append(i)

        # Execute read-only tools in parallel
        if parallel_indices:

            async def _run(idx: int) -> tuple[int, str]:
                tc = tool_calls[idx]
                return idx, await self._execute_single_tool(tc.name, tc.arguments)

            parallel_results = await asyncio.gather(
                *[_run(i) for i in parallel_indices],
                return_exceptions=True,
            )
            for item in parallel_results:
                if isinstance(item, Exception):
                    continue
                idx, result = item
                results[idx] = result

        # Execute write/dangerous tools sequentially
        for i in sequential_indices:
            tc = tool_calls[i]
            results[i] = await self._execute_single_tool(tc.name, tc.arguments)

        # Fill any remaining None slots (permission denied before categorization)
        return [r or "Error: tool execution skipped" for r in results]

    async def _execute_single_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a single tool with hooks and metrics tracking."""
        from nanobot.agent.hooks import HookContext

        # Get current session for agent_id
        current_session_key = list(self.sessions._cache.keys())[-1] if self.sessions._cache else None
        agent_id = current_session_key.split(":")[0] if current_session_key and ":" in current_session_key else "unknown"

        args_str = json.dumps(arguments, ensure_ascii=False)
        logger.info(f"🔄 [{agent_id}] Tool call: {name}({args_str[:150]}...)")

        # Pre-hooks
        ctx = HookContext(tool_name=name, params=arguments)
        ctx = await self.hooks.run_pre_hooks(ctx)
        if ctx.cancelled:
            return f"Tool call cancelled by hook: {name}"
        if ctx.modified_params:
            arguments = ctx.modified_params

        start_time = time.time()
        success = True
        error_msg = None

        try:
            result = await self.tools.execute(name, arguments)
        except Exception as e:
            success = False
            error_msg = str(e)
            result = f"Tool Execution Error: {e}"

        duration = time.time() - start_time
        self.metrics.record_tool_call(name, success, duration, error_msg)

        # Post-hooks
        ctx.result = result
        ctx = await self.hooks.run_post_hooks(ctx)
        if ctx.modified_result:
            result = ctx.modified_result

        return result

    def _trim_context(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Tier 1 context trimming: truncate long tool outputs.

        For Tier 2 (smart compaction via LLM summary), see _compact_context().
        """
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)

        if total_chars <= self.context_window:
            return messages

        logger.info(f"Context trimming: {total_chars} chars exceeds {self.context_window} limit")

        # Keep system prompt (first message) and last N messages
        keep_tail = 20  # Keep last 20 messages (10 tool call/result pairs)
        if len(messages) <= keep_tail + 1:
            return messages  # Not enough to trim

        trimmed = [messages[0]]  # system prompt
        middle = messages[1:-keep_tail]
        tail = messages[-keep_tail:]

        for msg in middle:
            if msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                if len(content) > 1000:
                    msg = {
                        **msg,
                        "content": content[:1000] + f"... [trimmed, was {len(content)} chars]",
                    }
            elif msg.get("role") == "assistant" and not msg.get("tool_calls"):
                content = str(msg.get("content", ""))
                if len(content) > 500:
                    msg = {
                        **msg,
                        "content": content[:500] + f"... [trimmed, was {len(content)} chars]",
                    }
            trimmed.append(msg)

        trimmed.extend(tail)
        new_chars = sum(len(str(m.get("content", ""))) for m in trimmed)
        logger.info(f"Context trimmed: {total_chars} -> {new_chars} chars")

        return trimmed

    async def _compact_context(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Tier 2 smart compaction: summarize old messages via LLM when context is large.

        Called after Tier 1 trimming if context still exceeds 70% of window.
        """
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        threshold = int(self.context_window * 0.7)

        if total_chars <= threshold:
            return messages
        logger.info(f"Smart compaction triggered: {total_chars} chars > {threshold} threshold")
        if self.on_status:
            try:
                self.on_status("compacting_context")
            except Exception:
                pass
        return await self.compactor.compact(messages, keep_recent=10)

    async def _auto_verify(
        self,
        messages: list[dict[str, Any]],
        executed_tools: list[str],
        last_modified_file: str = "",
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        Run auto-verification after file modifications.

        Detects project type and runs appropriate build/check command.
        Injects the result as a system message so the LLM can see errors.
        """
        if not self.auto_verify:
            return messages, False

        from nanobot.agent.verify import should_verify, get_verify_command

        if not should_verify(executed_tools):
            return messages, False

        verify_cmd = get_verify_command(
            self.workspace, self.auto_verify_command, last_modified_file
        )
        if not verify_cmd:
            return messages, False

        logger.info(f"Auto-verify: running '{verify_cmd}'")

        if self.on_tool_call:
            try:
                self.on_tool_call("auto_verify", verify_cmd[:60], "running...")
            except Exception:
                pass

        # Run verification using ExecTool (or direct subprocess)
        try:
            result = await self.tools.execute("exec", {"command": verify_cmd})
        except Exception as e:
            result = f"Auto-verify error: {e}"

        result_preview = result[:120] + "..." if len(result) > 120 else result

        if self.on_tool_call:
            try:
                self.on_tool_call("auto_verify", verify_cmd[:60], result_preview)
            except Exception:
                pass

        # Inject verification result as a system message
        verify_msg = f"[Auto-verification] `{verify_cmd}`:\n{result}"
        
        # Check if there are errors (heuristic)
        has_errors = any(w in result.lower() for w in ['error:', 'failed', 'traceback', 'exception'])
        
        if has_errors:
            verify_msg += "\n\n[SYSTEM CRITICAL] The verification FAILED. You MUST use tools to fix these errors before returning a final answer to the user. Do not stop until it passes."
            
        messages.append({"role": "user", "content": verify_msg})
        logger.info(f"Auto-verify result: {result_preview}")

        return messages, has_errors

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        media: list[str] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier (overrides channel:chat_id for session lookup).
            channel: Source channel (for tool context routing).
            chat_id: Source chat ID (for tool context routing).
            media: Optional list of media file paths.
            on_progress: Optional callback for intermediate output.

        Returns:
            The agent's response.
        """
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            media=media,
        )

        response = await self._process_message(
            msg, session_key=session_key, on_progress=on_progress
        )
        return response.content if response else ""

    async def process_direct_stream(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        media: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """
        Process a message with streaming output.

        Yields text chunks as they arrive from the LLM.
        Tool calls are handled internally (not streamed).

        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).

        Yields:
            Text chunks from the LLM response.
        """
        # Get or create session
        session = self.sessions.get_or_create(session_key)

        # Build initial messages
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=content,
            media=media,
            channel=channel,
            chat_id=chat_id,
            plan_context=self.planner.get_progress_context(),
        )

        iteration = 0
        final_content_parts: list[str] = []
        total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        is_error_response = False

        while iteration < self.max_iterations:
            iteration += 1
            messages = self._trim_context(messages)
            messages = await self._compact_context(messages)

            # Notify iteration progress
            if self.on_iteration:
                try:
                    self.on_iteration(iteration, self.max_iterations)
                except Exception:
                    pass

            # Notify status: thinking
            if self.on_status:
                try:
                    self.on_status("thinking")
                except Exception:
                    pass

            # Collect the full response via streaming
            collected_content = ""
            collected_reasoning = ""
            tool_calls_data: dict[int, dict[str, Any]] = {}  # index -> {id, name, args}
            is_final_text = True  # Will be set to False if we see tool calls

            async for chunk in self.provider.stream_chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                frequency_penalty=self.frequency_penalty,
                thinking_budget=self.thinking_budget,
            ):
                # Force event loop to process other tasks (like SIGINT/Ctrl+C)
                await asyncio.sleep(0)

                # Track usage
                if chunk.usage:
                    for k in total_usage:
                        total_usage[k] += chunk.usage.get(k, 0)

                # Reasoning content — notify callback and accumulate
                if chunk.reasoning_content:
                    collected_reasoning += chunk.reasoning_content
                    if self.on_thinking:
                        try:
                            self.on_thinking(chunk.reasoning_content)
                        except Exception:
                            pass

                # Text content — collect now, yield only for final response
                # (yielding intermediate text causes repeated rendering when
                # Rich Live display interleaves with stderr progress output)
                if chunk.delta_content:
                    collected_content += chunk.delta_content

                # Detect error responses
                if chunk.finish_reason == "error":
                    is_error_response = True

                # Tool call deltas — collect them
                if chunk.tool_call_index is not None:
                    is_final_text = False
                    idx = chunk.tool_call_index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {"id": "", "name": "", "args": ""}
                    if chunk.tool_call_id:
                        tool_calls_data[idx]["id"] = chunk.tool_call_id
                    if chunk.tool_call_name:
                        tool_calls_data[idx]["name"] = chunk.tool_call_name
                    if chunk.tool_call_arguments_delta:
                        tool_calls_data[idx]["args"] += chunk.tool_call_arguments_delta

            if is_final_text and not tool_calls_data:
                # Final text response — yield it and we're done
                if collected_content:
                    yield collected_content
                    final_content_parts.append(collected_content)
                break

            # Process tool calls
            if tool_calls_data:
                # Build tool_call dicts for context
                tool_call_dicts = []
                parsed_calls = []
                truncated_calls = []
                for idx in sorted(tool_calls_data.keys()):
                    tc_data = tool_calls_data[idx]
                    try:
                        if not tc_data["args"]:
                            logger.warning(
                                f"Tool call '{tc_data['name']}' (id={tc_data['id']}) has empty arguments "
                                f"- possible output token truncation or streaming issue"
                            )
                            truncated_calls.append(tc_data)
                        args = json.loads(tc_data["args"]) if tc_data["args"] else {}
                    except json.JSONDecodeError as e:
                        # Log the parse error with full context for debugging
                        logger.warning(
                            f"Tool call JSON decode error: name={tc_data['name']}, "
                            f"error={e}, raw_args={tc_data['args'][:200] if tc_data['args'] else 'EMPTY'}"
                        )
                        truncated_calls.append(tc_data)
                        args = {"_raw": tc_data["args"], "_parse_error": str(e)}

                    tool_call_dicts.append(
                        {
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {"name": tc_data["name"], "arguments": tc_data["args"]},
                        }
                    )
                    parsed_calls.append((tc_data["id"], tc_data["name"], args))

                # If ALL tool calls are truncated, skip execution and ask LLM to retry
                if truncated_calls and len(truncated_calls) == len(parsed_calls):
                    logger.warning(
                        f"All {len(truncated_calls)} tool call(s) have empty/invalid arguments. "
                        f"Likely output truncated by max_tokens. Asking LLM to retry."
                    )
                    messages = self.context.add_assistant_message(
                        messages,
                        collected_content or None,
                        tool_call_dicts,
                        reasoning_content=collected_reasoning or None,
                    )
                    # Return error for each truncated tool call so LLM can retry
                    for tc_data in tool_call_dicts:
                        messages = self.context.add_tool_result(
                            messages,
                            tc_data["id"],
                            tc_data["function"]["name"],
                            "Error: tool call arguments were truncated (output too long). "
                            "Please reduce your output text and call tools one at a time with shorter content.",
                        )
                    continue

                messages = self.context.add_assistant_message(
                    messages,
                    collected_content or None,
                    tool_call_dicts,
                    reasoning_content=collected_reasoning or None,
                )

                # Execute each tool (with permission + parallel)
                from nanobot.providers.base import ToolCallRequest

                # Notify status: executing tools
                if self.on_status:
                    try:
                        self.on_status("executing_tools")
                    except Exception:
                        pass

                # Notify tool start for each tool
                for tc_id, tc_name, tc_args in parsed_calls:
                    if self.on_tool_start:
                        try:
                            self.on_tool_start(tc_name, tc_args)
                        except Exception:
                            pass

                tc_objects = [
                    ToolCallRequest(id=tc_id, name=tc_name, arguments=tc_args)
                    for tc_id, tc_name, tc_args in parsed_calls
                ]
                tool_results = await self._execute_tools(tc_objects)

                executed_tools_stream = []
                last_modified_file_stream = ""
                for (tc_id, tc_name, tc_args), result in zip(parsed_calls, tool_results):
                    result_preview = result[:120] + "..." if len(result) > 120 else result

                    if self.on_tool_call:
                        try:
                            args_str = json.dumps(tc_args, ensure_ascii=False)
                            self.on_tool_call(tc_name, args_str[:100], result_preview)
                        except Exception:
                            pass

                    messages = self.context.add_tool_result(messages, tc_id, tc_name, result)
                    executed_tools_stream.append(tc_name)
                    if tc_name in ("write_file", "edit_file"):
                        last_modified_file_stream = tc_args.get("path", "")

                # Auto-verify after file modifications
                messages, _has_errors = await self._auto_verify(
                    messages, executed_tools_stream, last_modified_file_stream
                )

        # Save to session (skip error/empty responses to avoid polluting history)
        final_text = "".join(final_content_parts) if final_content_parts else ""
        session.add_message("user", content)
        if final_text and not is_error_response:
            session.add_message("assistant", final_text)
        self.sessions.save(session)

        # Yield usage summary as a special final chunk
        if total_usage.get("total_tokens", 0) > 0:
            yield f"\n\n[tokens: {total_usage['prompt_tokens']:,} in + {total_usage['completion_tokens']:,} out = {total_usage['total_tokens']:,} total]"

        # Warn if max iterations reached
        if iteration >= self.max_iterations and not final_content_parts:
            yield f"\n\n[WARNING] I have reached the maximum number of steps ({self.max_iterations}). Please ask me to 'continue' to proceed."

    async def _consolidate_memory(self, session, archive_all: bool = False) -> None:
        """Consolidate old messages into MEMORY.md + HISTORY.md.

        Args:
            archive_all: If True, clear all messages and reset session (for /new command).
                        If False, only write to files without modifying session.
        """
        memory = MemoryStore(self.workspace)

        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info(
                "Memory consolidation (archive_all): {} total messages archived",
                len(session.messages),
            )
        else:
            keep_count = self.memory_window // 2
            if len(session.messages) <= keep_count:
                logger.debug(
                    "Session {}: No consolidation needed (messages={}, keep={})",
                    session.key,
                    len(session.messages),
                    keep_count,
                )
                return

            messages_to_process = len(session.messages) - session.last_consolidated
            if messages_to_process <= 0:
                logger.debug(
                    "Session {}: No new messages to consolidate (last_consolidated={}, total={})",
                    session.key,
                    session.last_consolidated,
                    len(session.messages),
                )
                return

            old_messages = session.messages[session.last_consolidated : -keep_count]
            if not old_messages:
                return
            logger.info(
                "Memory consolidation started: {} total, {} new to consolidate, {} keep",
                len(session.messages),
                len(old_messages),
                keep_count,
            )

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(
                f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}"
            )
        conversation = "\n".join(lines)
        current_memory = memory.read_long_term()

        prompt = f"""You are a memory consolidation agent. Process this conversation and return a JSON object with exactly two keys:

1. "history_entry": A paragraph (2-5 sentences) summarizing the key events/decisions/topics. Start with a timestamp like [YYYY-MM-DD HH:MM]. Include enough detail to be useful when found by grep search later.

2. "memory_update": The updated long-term memory content. Add any new facts: user location, preferences, personal info, habits, project context, technical decisions, tools/services used. If nothing new, return the existing content unchanged.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{conversation}

**IMPORTANT**: Both values MUST be strings, not objects or arrays.

Example:
{{
  "history_entry": "[2026-02-14 22:50] User asked about...",
  "memory_update": "- Host: HARRYBOOK-T14P\\n- Name: Nado"
}}

Respond with ONLY valid JSON, no markdown fences."""

        try:
            response = await self.provider.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a memory consolidation agent. Respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
            )
            text = (response.content or "").strip()
            if not text:
                logger.warning("Memory consolidation: LLM returned empty response, skipping")
                return
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json_repair.loads(text)
            if not isinstance(result, dict):
                logger.warning(
                    "Memory consolidation: unexpected response type, skipping. Response: {}",
                    text[:200],
                )
                return

            if entry := result.get("history_entry"):
                # Defensive: ensure entry is a string (LLM may return dict)
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                memory.append_history(entry)
            if update := result.get("memory_update"):
                # Defensive: ensure update is a string
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    memory.write_long_term(update)

            if archive_all:
                session.last_consolidated = 0
            else:
                session.last_consolidated = len(session.messages) - keep_count
            logger.info(
                "Memory consolidation done: {} messages, last_consolidated={}",
                len(session.messages),
                session.last_consolidated,
            )
        except Exception as e:
            logger.error("Memory consolidation failed: {}", e)

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers

        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    # ==========================================================================
    # A2A (Agent-to-Agent) Communication Methods
    # ==========================================================================
    
    async def send_request(
        self,
        to_agent: str,
        content: str,
        timeout: int = 300,
        priority: str = "normal",
    ) -> AgentMessage:
        """
        Send request to another agent and wait for response.
        
        Args:
            to_agent: Target agent ID
            content: Request content
            timeout: Timeout in seconds
            priority: Message priority ("low", "normal", "high", "urgent")
        
        Returns:
            Response message
        
        Raises:
            ValueError: If A2A router not initialized or target agent not found
            asyncio.TimeoutError: If request timed out
        """
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")
        
        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }
        
        return await self.a2a_router.send_request(
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=content,
            timeout=timeout,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
        )
    
    async def send_response(
        self,
        request_id: str,
        to_agent: str,
        content: str,
        priority: str = "normal",
    ) -> bool:
        """
        Send response to a request.
        
        Args:
            request_id: Original request ID
            to_agent: Original requester agent ID
            content: Response content
            priority: Message priority
        
        Returns:
            True if response was sent
        """
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")
        
        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }
        
        return await self.a2a_router.send_response(
            from_agent=self.agent_id,
            to_agent=to_agent,
            request_id=request_id,
            content=content,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
        )
    
    async def send_notification(
        self,
        to_agent: str,
        content: str,
        priority: str = "normal",
    ) -> bool:
        """
        Send notification to another agent (no response expected).
        
        Args:
            to_agent: Target agent ID
            content: Notification content
            priority: Message priority
        
        Returns:
            True if notification was sent
        """
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")
        
        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }
        
        return await self.a2a_router.send_notification(
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=content,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
        )
    
    async def broadcast(
        self,
        content: str,
        priority: str = "normal",
        exclude: list[str] | None = None,
    ) -> int:
        """
        Broadcast message to all agents.
        
        Args:
            content: Broadcast content
            priority: Message priority
            exclude: List of agent IDs to exclude
        
        Returns:
            Number of agents that received the broadcast
        """
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")
        
        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }
        
        return await self.a2a_router.broadcast(
            from_agent=self.agent_id,
            content=content,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
            exclude=exclude,
        )
    
    async def receive_message(
        self,
        timeout: float | None = None,
    ) -> AgentMessage:
        """
        Receive next message from mailbox.
        
        Args:
            timeout: Maximum time to wait (None = wait forever)
        
        Returns:
            Next agent message
        
        Raises:
            ValueError: If A2A router not initialized
            asyncio.TimeoutError: If timeout exceeded
        """
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")
        
        return await self.a2a_router.get_message(
            agent_id=self.agent_id,
            timeout=timeout,
        )

    # ==========================================================================
    # AnnounceChain Methods (for Orchestrator pattern)
    # ==========================================================================
    
    async def wait_for_workers(
        self,
        timeout: float = 600,
        poll_interval: float = 1.0,
    ) -> dict | None:
        """
        Wait for all spawned workers to complete and aggregate results.
        
        This is the key method for Orchestrator pattern:
        1. Orchestrator spawns workers
        2. Workers complete and send announce events
        3. This method waits and aggregates all results
        
        Args:
            timeout: Maximum time to wait (seconds)
            poll_interval: Polling interval (seconds)
        
        Returns:
            Aggregated results from all workers, or None if timeout
        """
        from loguru import logger
        
        # Get current session key
        # For Orchestrator, we use a session key pattern like "orchestrator:<task_id>"
        # Workers will have parent_session_key pointing to this
        
        # Find all child sessions for this agent
        current_session_key = f"{self.agent_id}:current"  # Simplified for now
        
        logger.info(
            "Orchestrator waiting for workers (timeout: {}s)...",
            timeout,
        )
        
        # Wait for children
        result = await self.announce_chain.wait_for_children(
            parent_session_key=current_session_key,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        
        if result:
            logger.info(
                "All {} workers completed, aggregating results...",
                len(result.children),
            )
            return {
                "success": True,
                "worker_count": len(result.children),
                "results": [child.to_dict() for child in result.children],
                "summary": result.get_summary(),
            }
        else:
            logger.warning("Timeout waiting for workers")
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "worker_count": 0,
                "results": [],
            }
    
    def get_worker_results(self) -> list:
        """
        Get results from completed workers.
        
        Returns:
            List of worker results
        """
        current_session_key = f"{self.agent_id}:current"
        aggregation = self.announce_chain.get_aggregation(current_session_key)
        
        if aggregation:
            return [child.to_dict() for child in aggregation.children]
        return []
