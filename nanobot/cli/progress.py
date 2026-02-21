"""Tool execution progress display for CLI."""

import time

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text


console = Console(stderr=True)


class ToolProgressDisplay:
    """
    Displays tool execution progress in the CLI with spinners and status.

    Usage:
        display = ToolProgressDisplay()
        display.on_tool_start("read_file", {"path": "loop.py"})
        display.on_tool_complete("read_file", "796 lines", 0.02)
    """

    def __init__(self, show_diff: bool = True):
        self._show_diff = show_diff
        self._start_times: dict[str, float] = {}

    def on_tool_start(self, name: str, args: dict) -> None:
        """Display tool start with a brief description."""
        self._start_times[name] = time.time()
        summary = self._summarize_args(name, args)
        console.print(f"  [dim]⚙ {name}({summary})[/dim]", highlight=False)

    def on_tool_complete(self, name: str, result_preview: str, duration: float) -> None:
        """Display tool completion with result preview and timing."""
        # Truncate preview
        preview = result_preview.replace("\n", " ")[:80]
        dur = f"{duration:.2f}s" if duration >= 0.01 else "<0.01s"
        console.print(f"  [green]✓[/green] [dim]{name}[/dim] → {preview} [dim]({dur})[/dim]", highlight=False)

    def on_tool_error(self, name: str, error: str) -> None:
        """Display tool error."""
        err_preview = error.replace("\n", " ")[:100]
        console.print(f"  [red]✗[/red] [dim]{name}[/dim] → {err_preview}", highlight=False)

    def show_diff(self, diff_text: str) -> None:
        """Display a colored unified diff."""
        if not self._show_diff or not diff_text:
            return
        try:
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
            console.print(syntax)
        except Exception:
            # Fallback to plain text
            console.print(diff_text)

    def show_cost(self, usage: dict, cost: float | None = None) -> None:
        """Display token usage and estimated cost."""
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        parts = [f"tokens: {prompt:,} in + {completion:,} out = {total:,} total"]
        if cost is not None:
            parts.append(f"~${cost:.4f}")
        console.print(f"\n[dim][{' | '.join(parts)}][/dim]", highlight=False)

    def _summarize_args(self, name: str, args: dict) -> str:
        """Create a brief summary of tool arguments."""
        if name in ("read_file", "write_file", "edit_file"):
            return args.get("path", "?")
        if name == "exec":
            cmd = args.get("command", "?")
            return cmd[:50] + "..." if len(cmd) > 50 else cmd
        if name == "grep":
            return f"{args.get('pattern', '?')} in {args.get('path', '.')}"
        if name in ("git_commit",):
            return args.get("message", "?")[:40]
        if name == "git_checkout":
            return args.get("target", "?")
        # Generic: show first arg value
        for v in args.values():
            s = str(v)
            return s[:40] + "..." if len(s) > 40 else s
        return ""
