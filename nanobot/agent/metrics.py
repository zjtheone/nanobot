
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger

# Pricing per 1M tokens (input, output) — approximate
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.25, 1.25),
    "gpt-4o": (2.5, 10.0),
    "gpt-4": (30.0, 60.0),
    "gpt-3.5": (0.5, 1.5),
    "deepseek": (0.27, 1.10),
    "gemini-pro": (1.25, 5.0),
    "gemini-flash": (0.075, 0.30),
    "qwen": (0.5, 2.0),
}

@dataclass
class ToolCallRecord:
    timestamp: str
    tool_name: str
    success: bool
    duration_seconds: float
    error_message: str | None = None

@dataclass
class TokenUsageRecord:
    timestamp: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class MetricsTracker:
    """
    Tracks agent performance metrics:
    - Tool usage (success/fail, duration)
    - Token usage
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        # Store metrics in workspace/.nanobot/metrics.json for now to keep it project-specific
        self.metrics_dir = workspace / ".nanobot"
        self.metrics_file = self.metrics_dir / "metrics.json"
        self._ensure_storage()
        self._load()

    def _ensure_storage(self):
        if not self.metrics_dir.exists():
            self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        self.tool_calls: List[ToolCallRecord] = []
        self.token_usage: List[TokenUsageRecord] = []
        
        if self.metrics_file.exists():
            try:
                data = json.loads(self.metrics_file.read_text(encoding="utf-8"))
                for tc in data.get("tool_calls", []):
                    self.tool_calls.append(ToolCallRecord(**tc))
                for tu in data.get("token_usage", []):
                    self.token_usage.append(TokenUsageRecord(**tu))
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")

    def _save(self):
        try:
            data = {
                "tool_calls": [asdict(tc) for tc in self.tool_calls],
                "token_usage": [asdict(tu) for tu in self.token_usage],
                "last_updated": datetime.now().isoformat()
            }
            self.metrics_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def record_tool_call(self, tool_name: str, success: bool, duration: float, error: str | None = None):
        record = ToolCallRecord(
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            success=success,
            duration_seconds=duration,
            error_message=str(error) if error else None
        )
        self.tool_calls.append(record)
        # Auto-save every record for now (low volume)
        self._save()

    def record_tokens(self, prompt: int, completion: int):
        record = TokenUsageRecord(
            timestamp=datetime.now().isoformat(),
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion
        )
        self.token_usage.append(record)
        self._save()

    def estimate_cost(self, model: str = "") -> float:
        """Estimate total session cost based on model pricing."""
        pricing = self._match_pricing(model)
        if not pricing:
            return 0.0
        input_rate, output_rate = pricing
        total_input = sum(t.prompt_tokens for t in self.token_usage)
        total_output = sum(t.completion_tokens for t in self.token_usage)
        return (total_input * input_rate + total_output * output_rate) / 1_000_000

    def get_session_usage(self) -> dict[str, int]:
        """Get aggregated token usage for the current session."""
        return {
            "prompt_tokens": sum(t.prompt_tokens for t in self.token_usage),
            "completion_tokens": sum(t.completion_tokens for t in self.token_usage),
            "total_tokens": sum(t.total_tokens for t in self.token_usage),
        }

    def _match_pricing(self, model: str) -> tuple[float, float] | None:
        """Match a model name to pricing."""
        model_lower = model.lower()
        for key, pricing in MODEL_PRICING.items():
            if key in model_lower:
                return pricing
        return None

    def get_summary(self) -> str:
        """Generate a human-readable summary of metrics."""
        total_calls = len(self.tool_calls)
        if total_calls == 0:
            return "No tool calls recorded yet."

        # Tool Stats
        tool_stats: Dict[str, Dict] = {}
        for tc in self.tool_calls:
            if tc.tool_name not in tool_stats:
                tool_stats[tc.tool_name] = {"count": 0, "failures": 0, "total_time": 0.0}
            
            stats = tool_stats[tc.tool_name]
            stats["count"] += 1
            stats["total_time"] += tc.duration_seconds
            if not tc.success:
                stats["failures"] += 1
        
        lines = ["## Agent Metrics Report", f"Total Tool Calls: {total_calls}", ""]
        lines.append("| Tool | Count | Failure Rate | Avg Time |")
        lines.append("|---|---|---|---|")
        
        for name, stats in sorted(tool_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            fail_rate = (stats["failures"] / stats["count"]) * 100
            avg_time = stats["total_time"] / stats["count"]
            lines.append(f"| {name} | {stats['count']} | {fail_rate:.1f}% | {avg_time:.2f}s |")

        # Token Stats
        total_tokens = sum(t.total_tokens for t in self.token_usage)
        lines.append("")
        lines.append(f"**Total Tokens Consumed**: {total_tokens:,}")
        
        return "\n".join(lines)
