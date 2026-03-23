"""Apply patch tool: parse and apply unified diff patches."""

import re
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from loguru import logger


def _parse_unified_diff(patch: str) -> list[dict[str, Any]]:
    """Parse a unified diff patch into a list of file operations.

    Returns list of dicts with keys:
        - action: "add" | "update" | "delete"
        - old_path: str | None
        - new_path: str | None
        - hunks: list of (old_start, old_count, new_start, new_count, lines)
    """
    files = []
    current = None

    lines = patch.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # File header: --- a/path or --- /dev/null
        if line.startswith("--- "):
            old_path = line[4:].strip()
            # Strip a/ prefix
            if old_path.startswith("a/"):
                old_path = old_path[2:]
            elif old_path == "/dev/null":
                old_path = None

            i += 1
            if i < len(lines) and lines[i].startswith("+++ "):
                new_path = lines[i][4:].strip()
                if new_path.startswith("b/"):
                    new_path = new_path[2:]
                elif new_path == "/dev/null":
                    new_path = None

                if old_path is None and new_path:
                    action = "add"
                elif new_path is None and old_path:
                    action = "delete"
                else:
                    action = "update"

                current = {
                    "action": action,
                    "old_path": old_path,
                    "new_path": new_path,
                    "hunks": [],
                }
                files.append(current)
                i += 1
                continue

        # Hunk header: @@ -start,count +start,count @@
        hunk_match = re.match(
            r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line
        )
        if hunk_match and current is not None:
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2) or "1")
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4) or "1")

            hunk_lines = []
            i += 1

            while i < len(lines):
                hl = lines[i]
                if hl.startswith("@@") or hl.startswith("--- ") or hl.startswith("diff "):
                    break
                hunk_lines.append(hl)
                i += 1

            current["hunks"].append(
                (old_start, old_count, new_start, new_count, hunk_lines)
            )
            continue

        i += 1

    return files


def _apply_hunks(
    content: str, hunks: list[tuple[int, int, int, int, list[str]]], drift_tolerance: int = 3
) -> str:
    """Apply hunks to file content with drift tolerance.

    drift_tolerance: number of lines to search above/below expected position.
    """
    content_lines = content.splitlines(keepends=True)

    # Process hunks in reverse order to preserve line numbers
    for old_start, old_count, new_start, new_count, hunk_lines in reversed(hunks):
        # Parse hunk lines
        remove_lines = []
        add_lines = []
        context_lines = []

        for hl in hunk_lines:
            if hl.startswith("-"):
                remove_lines.append(hl[1:])
            elif hl.startswith("+"):
                add_lines.append(hl[1:])
            elif hl.startswith(" "):
                context_lines.append(hl[1:])
                remove_lines.append(hl[1:])
                add_lines.append(hl[1:])
            elif hl == "\\ No newline at end of file":
                continue

        # Find the matching position (0-indexed)
        target_line = old_start - 1  # Convert to 0-indexed

        # Build expected lines (context + removed)
        expected = []
        for hl in hunk_lines:
            if hl.startswith("-") or hl.startswith(" "):
                expected.append(hl[1:])

        # Try to find match with drift
        best_pos = None
        for offset in range(drift_tolerance + 1):
            for delta in ([0, offset, -offset] if offset > 0 else [0]):
                pos = target_line + delta
                if pos < 0 or pos + len(expected) > len(content_lines):
                    continue

                # Check if expected lines match
                match = True
                for j, exp_line in enumerate(expected):
                    actual = content_lines[pos + j].rstrip("\n").rstrip("\r\n")
                    if actual != exp_line.rstrip("\n").rstrip("\r\n"):
                        match = False
                        break

                if match:
                    best_pos = pos
                    break
            if best_pos is not None:
                break

        if best_pos is None:
            # Fallback: apply at original position
            best_pos = target_line

        # Build new lines from hunk
        new_lines = []
        for hl in hunk_lines:
            if hl.startswith("+"):
                text = hl[1:]
                if not text.endswith("\n"):
                    text += "\n"
                new_lines.append(text)
            elif hl.startswith(" "):
                text = hl[1:]
                if not text.endswith("\n"):
                    text += "\n"
                new_lines.append(text)
            elif hl == "\\ No newline at end of file":
                if new_lines:
                    new_lines[-1] = new_lines[-1].rstrip("\n")

        # Replace old lines with new lines
        content_lines[best_pos : best_pos + len(expected)] = new_lines

    return "".join(content_lines)


class ApplyPatchTool(Tool):
    """Tool to apply unified diff patches for multi-file changes."""

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        checkpoint: Any | None = None,
        lsp_manager: Any | None = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint
        self._lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "apply_patch"

    @property
    def description(self) -> str:
        return (
            "Apply a unified diff patch to modify one or more files. "
            "Supports file creation, modification, and deletion. "
            "The patch should be in standard unified diff format "
            "(as produced by `diff -u` or `git diff`)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "The unified diff patch text",
                },
            },
            "required": ["patch"],
        }

    async def execute(self, patch: str, **kwargs: Any) -> str:
        try:
            file_ops = _parse_unified_diff(patch)
            if not file_ops:
                return "Error: No valid patch hunks found."

            results = []
            modified_paths = []

            for op in file_ops:
                action = op["action"]
                old_path = op["old_path"]
                new_path = op["new_path"]
                hunks = op["hunks"]

                if action == "add" and new_path:
                    # Create new file
                    file_path = self._resolve(new_path)
                    if file_path is None:
                        results.append(f"Error: Cannot resolve path {new_path}")
                        continue

                    # Build content from + lines
                    content_lines = []
                    for _os, _oc, _ns, _nc, hunk_lines in hunks:
                        for hl in hunk_lines:
                            if hl.startswith("+"):
                                content_lines.append(hl[1:])

                    content = "\n".join(content_lines)
                    if content and not content.endswith("\n"):
                        content += "\n"

                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    results.append(f"Created {new_path}")
                    modified_paths.append(str(file_path))

                elif action == "delete" and old_path:
                    file_path = self._resolve(old_path)
                    if file_path is None or not file_path.exists():
                        results.append(f"Error: File not found for deletion: {old_path}")
                        continue

                    if self._checkpoint:
                        self._checkpoint.snapshot(file_path)
                    file_path.unlink()
                    results.append(f"Deleted {old_path}")

                elif action == "update" and old_path:
                    file_path = self._resolve(old_path)
                    if file_path is None or not file_path.exists():
                        results.append(f"Error: File not found: {old_path}")
                        continue

                    if self._checkpoint:
                        self._checkpoint.snapshot(file_path)

                    content = file_path.read_text(encoding="utf-8")
                    new_content = _apply_hunks(content, hunks)
                    file_path.write_text(new_content, encoding="utf-8")

                    results.append(f"Updated {old_path}")
                    modified_paths.append(str(file_path))

            # Touch modified files for LSP diagnostics
            if self._lsp_manager and modified_paths:
                from nanobot.agent.tools.filesystem import _collect_post_edit_diagnostics

                for fpath in modified_paths:
                    diag_info = await _collect_post_edit_diagnostics(
                        self._lsp_manager, fpath
                    )
                    if diag_info:
                        results.append(diag_info)

            return "\n".join(results)

        except Exception as e:
            return f"Error applying patch: {str(e)}"

    def _resolve(self, path: str) -> Path | None:
        """Resolve a path relative to workspace."""
        p = Path(path)
        if not p.is_absolute() and self._workspace:
            p = self._workspace / p
        p = p.resolve()

        if self._allowed_dir:
            try:
                p.relative_to(self._allowed_dir.resolve())
            except ValueError:
                return None
        return p
