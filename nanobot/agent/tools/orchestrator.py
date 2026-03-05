"""Orchestrator-specific tools for task decomposition and worker management."""

from typing import Any

from nanobot.agent.tools.base import Tool


class DecomposeAndSpawnTool(Tool):
    """Tool for Orchestrator to decompose tasks and spawn workers.
    
    This is the PRIMARY tool for Orchestrator agents.
    It combines task decomposition, worker spawning, and result aggregation.
    
    Usage:
        {
            "tool": "decompose_and_spawn",
            "parameters": {
                "task": "Build a complete e-commerce website",
                "workers": [
                    {"label": "research", "task": "Research best practices"},
                    {"label": "backend", "task": "Implement backend API"},
                    {"label": "frontend", "task": "Implement frontend UI"},
                    {"label": "test", "task": "Write tests"}
                ],
                "timeout": 600
            }
        }
    """
    
    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
        self._agent_id = agent_loop.agent_id if hasattr(agent_loop, 'agent_id') else 'default'
        self._bus = agent_loop.bus if hasattr(agent_loop, 'bus') else None
    
    @property
    def name(self) -> str:
        return "decompose_and_spawn"
    
    @property
    def description(self) -> str:
        return (
            "**Orchestrator's primary tool** - Decompose a complex task and spawn workers in parallel.\n\n"
            "This tool:\n"
            "1. Spawns multiple workers to work in parallel\n"
            "2. Waits for all workers to complete\n"
            "3. Aggregates results from all workers\n\n"
            "**Parameters:**\n"
            "- `task`: Main task description\n"
            "- `workers`: List of {label, task} for each worker\n"
            "- `timeout`: Timeout in seconds (default: 600)\n\n"
            "**Example:**\n"
            "```json\n"
            "{\n"
            '  "task": "Build an e-commerce site",\n'
            '  "workers": [\n'
            '    {"label": "backend", "task": "Implement API"},\n'
            '    {"label": "frontend", "task": "Implement UI"}\n'
            '  ],\n'
            '  "timeout": 600\n'
            "}\n"
            "```\n\n"
            "**Use this tool for ALL complex tasks as an Orchestrator!**"
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Main task to decompose",
                },
                "workers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "Worker label (e.g., 'backend', 'frontend')",
                            },
                            "task": {
                                "type": "string",
                                "description": "Subtask for this worker",
                            },
                        },
                        "required": ["label", "task"],
                    },
                    "description": "List of workers to spawn",
                },
                "timeout": {
                    "type": "integer",
                    "default": 600,
                    "description": "Timeout in seconds",
                },
            },
            "required": ["task", "workers"],
        }
    
    async def execute(
        self,
        task: str,
        workers: list[dict],
        timeout: int = 600,
        **kwargs: Any,
    ) -> dict:
        """
        Execute task decomposition and worker spawning.
        
        Args:
            task: Main task description
            workers: List of {label, task} for each worker
            timeout: Timeout in seconds
        
        Returns:
            Aggregated results from all workers
        """
        from nanobot.agent.tools.spawn import SpawnTool
        from loguru import logger
        
        logger.info(
            "Orchestrator decomposing task: '{}' with {} workers",
            task[:100],
            len(workers),
        )
        
        # Use SpawnTool to spawn workers
        spawn_tool = SpawnTool(
            manager=self.agent_loop.subagents if hasattr(self.agent_loop, 'subagents') else None,
        )

        # Set context from agent_loop so spawn has proper session/agent info
        if hasattr(self.agent_loop, 'agent_id'):
            spawn_tool.set_context(
                channel="orchestrator",
                chat_id="decompose",
                session_key=getattr(self.agent_loop, '_current_session_key', None),
                agent_id=self.agent_loop.agent_id,
                spawn_depth=0,
            )
        
        # Spawn all workers in batch
        batch_tasks = [
            {"task": w["task"], "label": w["label"]}
            for w in workers
        ]
        
        spawn_result = await spawn_tool.execute(
            batch=batch_tasks,
            wait=True,
            timeout=timeout,
        )

        logger.info("All workers spawned, waiting for results...")

        # Wait for workers to complete via announce_chain
        session_key = getattr(self.agent_loop, '_current_session_key', None)
        if not session_key:
            session_key = f"{self.agent_loop.agent_id}:current"

        aggregation = await self.agent_loop.announce_chain.wait_for_children(
            parent_session_key=session_key,
            timeout=timeout,
            poll_interval=1.0,
        )

        if aggregation:
            logger.info(
                "All {} workers completed, aggregating results",
                len(aggregation.children),
            )
            return {
                "success": True,
                "task": task,
                "worker_count": len(aggregation.children),
                "results": [child.to_dict() for child in aggregation.children],
                "summary": aggregation.get_summary(),
            }
        else:
            # Timeout — return partial results from spawn
            logger.warning("Timeout waiting for workers after {}s", timeout)
            return {
                "success": False,
                "task": task,
                "worker_count": len(workers),
                "spawn_result": spawn_result,
                "error": f"Timeout after {timeout}s waiting for workers",
            }


class AggregateResultsTool(Tool):
    """Tool for Orchestrator to aggregate worker results."""
    
    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
    
    @property
    def name(self) -> str:
        return "aggregate_results"
    
    @property
    def description(self) -> str:
        return (
            "Aggregate results from spawned workers.\n\n"
            "Use this after spawn/wait to combine all worker outputs into a final result.\n\n"
            "**Parameters:** None (automatically aggregates from current session)\n\n"
            "**Returns:** Aggregated summary of all worker results"
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    async def execute(self, **kwargs: Any) -> dict:
        """Aggregate results from workers."""
        if hasattr(self.agent_loop, 'get_worker_results'):
            results = self.agent_loop.get_worker_results()
            return {
                "success": True,
                "result_count": len(results),
                "results": results,
            }
        else:
            return {
                "success": False,
                "error": "Worker results not available yet",
                "results": [],
            }
