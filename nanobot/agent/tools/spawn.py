"""Spawn tool for creating background subagents with A2A policy enforcement."""

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool
from nanobot.session.keys import SessionKey, extract_agent_id

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager
    from nanobot.config.loader import Config
    from nanobot.agent.policy_engine import AgentToAgentPolicyEngine


class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution.

    Supports:
    - Same-agent subagent spawning
    - Cross-agent spawning (with policy enforcement)
    - Nested subagent spawning (with depth limits)
    """

    def __init__(
        self,
        manager: "SubagentManager",
        config: "Config | None" = None,
        policy_engine: "AgentToAgentPolicyEngine | None" = None,
    ):
        self._manager = manager
        self._config = config
        self._policy_engine = policy_engine
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"
        self._agent_id = "default"
        self._spawn_depth = 0

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        agent_id: str | None = None,
        spawn_depth: int = 0,
    ) -> None:
        """Set the origin context for subagent announcements.

        Args:
            channel: Origin channel
            chat_id: Origin chat ID
            session_key: Origin session key
            agent_id: Origin agent ID
            spawn_depth: Current spawn depth
        """
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = session_key or f"{channel}:{chat_id}"
        self._agent_id = agent_id or "default"
        self._spawn_depth = spawn_depth

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done.\n"
            "\nParameters:\n"
            "- task: The task for the subagent to complete (required)\n"
            "- label: Optional short label for the task (for display)\n"
            "- agent_id: Optional target agent ID (default: same as current agent)\n"
            "\nNote: Cross-agent spawning requires tools.agent_to_agent.enabled=true"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Optional target agent ID (default: same as current agent)",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        agent_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task.

        Args:
            task: Task description
            label: Optional label
            agent_id: Optional target agent ID
            **kwargs: Additional arguments

        Returns:
            Result message (success or error)
        """
        target_agent_id = agent_id or self._agent_id

        # Check A2A policy
        policy_result = self._check_spawn_policy(target_agent_id)
        if policy_result.is_denied:
            return f"Error: {policy_result.message}"

        # Get spawn depth limit
        max_depth = self._get_max_spawn_depth()

        try:
            # Spawn the subagent
            result = await self._manager.spawn(
                task=task,
                label=label,
                origin_channel=self._origin_channel,
                origin_chat_id=self._origin_chat_id,
                session_key=self._session_key,
                target_agent_id=target_agent_id,
                parent_depth=self._spawn_depth,
                max_depth=max_depth,
            )
            return result
        except Exception as e:
            return f"Error spawning subagent: {str(e)}"

    def _check_spawn_policy(self, target_agent_id: str) -> "PolicyDecision":
        """Check if spawning is allowed by policy.

        Args:
            target_agent_id: Target agent ID

        Returns:
            PolicyDecision
        """
        # If no policy engine, allow all (backward compatibility)
        if not self._policy_engine:
            from nanobot.agent.policy_engine import PolicyDecision, PolicyCheckResult

            return PolicyDecision(
                result=PolicyCheckResult.ALLOWED,
                message="No policy engine configured, allowing spawn",
            )

        # Check policy
        return self._policy_engine.check_spawn_allowed(
            requester_agent_id=self._agent_id,
            target_agent_id=target_agent_id,
            current_depth=self._spawn_depth,
        )

    def _get_max_spawn_depth(self) -> int:
        """Get the maximum spawn depth from configuration.

        Returns:
            Maximum spawn depth
        """
        if self._config:
            try:
                agent_config = self._config.agents.get_agent(self._agent_id)
                return agent_config.subagents.max_spawn_depth
            except Exception:
                pass

        # Default: no nesting
        return 1
