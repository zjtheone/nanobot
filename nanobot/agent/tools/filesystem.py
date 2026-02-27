"""File system tools: read, write, edit."""

import difflib
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


def _resolve_path(path: str, workspace: Path | None = None, allowed_dir: Path | None = None) -> Path:
    """Resolve path against workspace (if relative) and enforce directory restriction."""
    p = Path(path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    resolved = p.resolve()
    if allowed_dir:
        try:
            resolved.relative_to(allowed_dir.resolve())
        except ValueError:
            raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
    return resolved


class ReadFileTool(Tool):
    """Tool to read file contents with line numbers."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return (
            "Read the contents of a file with line numbers. "
            "Optionally specify start_line and end_line to read a range. "
            "Large files are truncated to 200 lines — use start_line/end_line to read sections."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional start line number (1-indexed, inclusive)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional end line number (1-indexed, inclusive)"
                },
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, start_line: int = 0, end_line: int = 0, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"
            
            content = file_path.read_text(encoding="utf-8")
            all_lines = content.splitlines()
            total = len(all_lines)
            
            # Apply range if specified
            if start_line > 0 or end_line > 0:
                s = max(1, start_line) if start_line > 0 else 1
                e = min(total, end_line) if end_line > 0 else total
                selected = all_lines[s - 1:e]
                numbered = [f"{s + i:>6}: {line}" for i, line in enumerate(selected)]
                header = f"[{path}] Lines {s}-{e} of {total}\n"
                return header + "\n".join(numbered)
            
            # Full file with truncation
            max_lines = 200
            if total <= max_lines:
                numbered = [f"{i:>6}: {line}" for i, line in enumerate(all_lines, 1)]
                header = f"[{path}] {total} lines\n"
                return header + "\n".join(numbered)
            else:
                # Show first 200 lines with a note
                numbered = [f"{i:>6}: {line}" for i, line in enumerate(all_lines[:max_lines], 1)]
                header = f"[{path}] {total} lines (showing first {max_lines})\n"
                footer = f"\n... ({total - max_lines} more lines. Use start_line/end_line to read further.)"
                return header + "\n".join(numbered) + footer
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(self, allowed_dir: Path | None = None, checkpoint: "CheckpointManager | None" = None):
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Snapshot before writing
            if self._checkpoint:
                self._checkpoint.snapshot(file_path)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""

    def __init__(self, allowed_dir: Path | None = None, checkpoint: "CheckpointManager | None" = None):
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file. "
            "If old_text appears multiple times, provide start_line to disambiguate. "
            "Returns a unified diff showing the change."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace",
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace with",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Line number hint to disambiguate when old_text appears multiple times (1-indexed)",
                },
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(
        self, path: str, old_text: str, new_text: str, start_line: int = 0, **kwargs: Any
    ) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")
            old_lines = content.splitlines(keepends=True)

            if old_text not in content:
<<<<<<< HEAD
                return "Error: old_text not found in file. Make sure it matches exactly."
=======
                return self._not_found_message(old_text, content, path)
>>>>>>> origin/main

            count = content.count(old_text)

            if count > 1 and start_line > 0:
                # Use start_line to pick the right occurrence
                target_idx = start_line - 1  # 0-indexed
                search_from = 0
                for line_no, line in enumerate(old_lines):
                    pos = content.find(old_text, search_from)
                    if pos == -1:
                        break
                    # Check if this occurrence starts at or after the target line
                    line_start = sum(len(l) for l in old_lines[:line_no])
                    if pos >= line_start and line_no >= target_idx:
                        new_content = content[:pos] + new_text + content[pos + len(old_text):]
                        break
                    search_from = pos + 1
                else:
                    new_content = content.replace(old_text, new_text, 1)
            elif count > 1:
                return (
                    f"Warning: old_text appears {count} times. "
                    "Provide start_line to specify which occurrence to replace."
                )
            else:
                new_content = content.replace(old_text, new_text, 1)

            # Snapshot before writing
            if self._checkpoint:
                self._checkpoint.snapshot(file_path)

            file_path.write_text(new_content, encoding="utf-8")

            # Generate unified diff
            new_lines = new_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
            )
            diff_text = "".join(diff)

            if diff_text:
                return f"Successfully edited {path}\n\n{diff_text}"
            return f"Successfully edited {path} (no visible diff)"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        """Build a helpful error when old_text is not found."""
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, i

        if best_ratio > 0.5:
            diff = "\n".join(difflib.unified_diff(
                old_lines, lines[best_start : best_start + window],
                fromfile="old_text (provided)", tofile=f"{path} (actual, line {best_start + 1})",
                lineterm="",
            ))
            return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
        return f"Error: old_text not found in {path}. No similar text found. Verify the file content."


class ListDirTool(Tool):
    """Tool to list directory contents."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(path, self._allowed_dir)
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"
            
            items = []
            for i, item in enumerate(sorted(dir_path.iterdir())):
                if i >= 100:
                    items.append(f"... (total {len(list(dir_path.iterdir()))} items, showing first 100)")
                    break
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")
            
            if not items:
                return f"Directory {path} is empty"
            
            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
