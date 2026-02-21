
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.agent.planner import Planner

class PlanTool(Tool):
    """
    Tool to generate an implementation plan.
    """
    def __init__(self, planner: Planner):
        self.planner = planner

    @property
    def name(self) -> str:
        return "create_implementation_plan"

    @property
    def description(self) -> str:
        return (
            "Analyze requirements and create a detailed IMPLEMENTATION_PLAN.md. "
            "Use this BEFORE writing code for complex tasks."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "string",
                    "description": "Detailed description of what needs to be implemented."
                }
            },
            "required": ["requirements"]
        }

    async def execute(self, requirements: str, **kwargs: Any) -> str:
        try:
            plan = await self.planner.create_plan(requirements)
            return (
                f"Plan created successfully at {self.planner.plan_path}.\n"
                "Please ask the user to review 'implementation_plan.md' before proceeding."
            )
        except Exception as e:
            return f"Error creating plan: {str(e)}"
