"""File system tools: read, write, edit."""
import asyncio
import re
import difflib
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from loguru import logger


def _resolve_path(
    path: str, workspace: Path | None = None, allowed_dir: Path | None = None
) -> Path:
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


# --- Fuzzy Match Strategies ---


def _find_match(search: str, content: str) -> tuple[int, int, str] | None:
    """Try cascading match strategies to find search text in content.

    Returns (start_offset, end_offset, strategy_name) or None.
    Strategies are tried in order from most precise to most lenient.
    """
    # Strategy 1: Exact match
    idx = content.find(search)
    if idx != -1:
        return (idx, idx + len(search), "exact")

    # Normalize line endings for all subsequent strategies
    search_n = search.replace("\r\n", "\n")
    content_n = content.replace("\r\n", "\n")

    idx = content_n.find(search_n)
    if idx != -1:
        return (idx, idx + len(search_n), "exact-normalized")

    # Strategy 2: Whitespace-normalized match
    # Collapse runs of whitespace (except newlines) to single space
    def ws_normalize(s: str) -> str:
        return re.sub(r"[^\S\n]+", " ", s)

    search_ws = ws_normalize(search_n)
    content_ws = ws_normalize(content_n)
    idx = content_ws.find(search_ws)
    if idx != -1:
        # Map back to original offsets
        result = _map_normalized_offset(content_n, content_ws, idx, len(search_ws))
        if result:
            return (*result, "whitespace-normalized")

    # Strategy 3: Line-trimmed match (strip leading whitespace per line)
    search_lines = [l.lstrip() for l in search_n.splitlines()]
    content_lines = content_n.splitlines(keepends=True)
    content_stripped = [l.lstrip() for l in content_lines]

    match = _find_lines_match(search_lines, content_lines, content_stripped)
    if match:
        return (*match, "line-trimmed")

    # Strategy 4: Block-anchor match
    # Match first+last non-empty lines as anchors, allow fuzzy middle
    match = _block_anchor_match(search_n, content_n)
    if match:
        return (*match, "block-anchor")

    # Strategy 5: Escape-normalized match
    # Unescape common escape sequences
    def unescape(s: str) -> str:
        return (
            s.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace("\\\\", "\\")
        )

    search_esc = unescape(search_n)
    if search_esc != search_n:
        idx = content_n.find(search_esc)
        if idx != -1:
            return (idx, idx + len(search_esc), "escape-normalized")

    return None


def _map_normalized_offset(
    original: str, normalized: str, norm_start: int, norm_len: int
) -> tuple[int, int] | None:
    """Map an offset in normalized text back to the original text."""
    # Build mapping: normalized index -> original index
    orig_idx = 0
    norm_idx = 0
    start_orig = None
    end_orig = None

    while orig_idx < len(original) and norm_idx < len(normalized):
        if norm_idx == norm_start and start_orig is None:
            start_orig = orig_idx
        if norm_idx == norm_start + norm_len:
            end_orig = orig_idx
            break

        if original[orig_idx] == normalized[norm_idx]:
            orig_idx += 1
            norm_idx += 1
        elif normalized[norm_idx] == " " and original[orig_idx] in " \t":
            # Consume all whitespace in original for one space in normalized
            while orig_idx < len(original) and original[orig_idx] in " \t":
                orig_idx += 1
            norm_idx += 1
        else:
            orig_idx += 1

    if start_orig is not None and end_orig is None:
        end_orig = orig_idx

    if start_orig is not None and end_orig is not None:
        return (start_orig, end_orig)
    return None


def _find_lines_match(
    search_lines: list[str],
    content_lines: list[str],
    content_stripped: list[str],
) -> tuple[int, int] | None:
    """Find matching lines ignoring leading whitespace."""
    search_nonempty = [l for l in search_lines if l.strip()]
    if not search_nonempty:
        return None

    n = len(search_lines)
    for i in range(len(content_stripped) - n + 1):
        candidate = [l for l in content_stripped[i : i + n] if l.strip()]
        if candidate == search_nonempty:
            # Calculate offsets
            start = sum(len(l) for l in content_lines[:i])
            end = sum(len(l) for l in content_lines[: i + n])
            return (start, end)
    return None


def _block_anchor_match(search: str, content: str) -> tuple[int, int] | None:
    """Match using first and last non-empty lines as anchors.

    Middle lines are compared with SequenceMatcher, accepting >= 0.7 similarity.
    """
    search_lines = search.splitlines()
    content_lines = content.splitlines(keepends=True)

    # Get non-empty search lines
    nonempty = [(i, l) for i, l in enumerate(search_lines) if l.strip()]
    if len(nonempty) < 2:
        return None

    first_line = nonempty[0][1].strip()
    last_line = nonempty[-1][1].strip()
    n = len(search_lines)

    for i in range(len(content_lines) - n + 1):
        candidate = content_lines[i : i + n]
        candidate_nonempty = [l for l in candidate if l.strip()]

        if not candidate_nonempty:
            continue

        # Check anchors
        if candidate_nonempty[0].strip() != first_line:
            continue
        if candidate_nonempty[-1].strip() != last_line:
            continue

        # Check middle similarity
        if len(nonempty) > 2:
            middle_search = "\n".join(l.strip() for _, l in nonempty[1:-1])
            middle_candidate = "\n".join(
                l.strip() for l in candidate_nonempty[1:-1]
            )
            ratio = difflib.SequenceMatcher(
                None, middle_search, middle_candidate
            ).ratio()
            if ratio < 0.7:
                continue

        start = sum(len(l) for l in content_lines[:i])
        end = sum(len(l) for l in content_lines[: i + n])
        return (start, end)

    return None


class ReadFileTool(Tool):
    """Tool to read file contents with line numbers."""

    _MAX_CHARS = 128_000

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        lsp_manager: "Any | None" = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._lsp_manager = lsp_manager

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
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            size = file_path.stat().st_size
            if size > self._MAX_CHARS * 4:
                return (
                    f"Error: File too large ({size:,} bytes). "
                    f"Use exec tool with head/tail/grep to read portions."
                )

            content = file_path.read_text(encoding="utf-8")
            all_lines = content.splitlines()
            total = len(all_lines)

            # Fire-and-forget LSP prewarming
            if self._lsp_manager:
                try:
                    asyncio.create_task(
                        self._lsp_manager.touch_file(str(file_path))
                    )
                except Exception:
                    pass

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

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        checkpoint: "Any | None" = None,
        lsp_manager: "Any | None" = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint
        self._lsp_manager = lsp_manager

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
                "path": {"type": "string", "description": "The file path to write to"},
                "content": {"type": "string", "description": "The content to write"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            is_new = not file_path.exists()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if self._checkpoint:
                self._checkpoint.snapshot(file_path)
            file_path.write_text(content, encoding="utf-8")

            result = f"Successfully wrote {len(content)} bytes to {path}"

            # Auto-diagnostics after write
            if self._lsp_manager:
                diag_info = await _collect_post_edit_diagnostics(
                    self._lsp_manager, str(file_path), is_new=is_new
                )
                if diag_info:
                    result += f"\n\n{diag_info}"

            return result
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file using Aider-style SEARCH/REPLACE blocks.

    Uses cascading fuzzy match strategies:
    1. Exact match
    2. Whitespace-normalized (collapse runs of spaces)
    3. Line-trimmed (ignore leading whitespace)
    4. Block-anchor (first+last line anchors with fuzzy middle)
    5. Escape-normalized (unescape \\n, \\t, etc.)
    """

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        checkpoint: "Any | None" = None,
        lsp_manager: "Any | None" = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint
        self._lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit a file using Aider-style SEARCH/REPLACE blocks. "
            "You MUST format the 'blocks' parameter exactly like this:\n"
            "<<<<<<< SEARCH\n"
            "exact lines to find from the original file\n"
            "=======\n"
            "new lines to replace them with\n"
            ">>>>>>> REPLACE\n"
            "Include enough context lines in the SEARCH block to uniquely identify the location."
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
                "blocks": {
                    "type": "string",
                    "description": "The SEARCH/REPLACE block(s)",
                },
            },
            "required": ["path", "blocks"],
        }

    async def execute(self, path: str, blocks: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")
            old_lines = content.splitlines(keepends=True)

            pattern = re.compile(
                r"<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
                re.DOTALL | re.MULTILINE
            )

            matches = list(pattern.finditer(blocks))
            if not matches:
                return "Error: No valid SEARCH/REPLACE blocks found in 'blocks' parameter."

            new_content = content
            applied_count = 0
            strategies_used = []

            for match in matches:
                search = match.group("search")
                replace = match.group("replace")

                result = _find_match(search, new_content)

                if result:
                    start, end, strategy = result
                    # Apply replacement, preserving original indentation for line-trimmed
                    if strategy in ("line-trimmed", "block-anchor"):
                        # Re-indent replacement to match original
                        original_text = new_content[start:end]
                        replace_text = _reindent_replacement(
                            original_text, search, replace
                        )
                        new_content = new_content[:start] + replace_text + new_content[end:]
                    else:
                        new_content = new_content[:start] + replace + new_content[end:]
                    applied_count += 1
                    strategies_used.append(strategy)
                else:
                    # Show helpful error with closest match
                    error_msg = self._not_found_message(search, new_content, path)
                    return error_msg

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

            # Build result
            strategy_info = ""
            non_exact = [s for s in strategies_used if s != "exact"]
            if non_exact:
                strategy_info = f" (fuzzy: {', '.join(non_exact)})"

            result = f"Successfully applied {applied_count} edit block(s) to {path}{strategy_info}"

            if diff_text:
                result += f"\n\n{diff_text}"

            # Auto-diagnostics after edit
            if self._lsp_manager:
                diag_info = await _collect_post_edit_diagnostics(
                    self._lsp_manager, str(file_path)
                )
                if diag_info:
                    result += f"\n\n{diag_info}"

            return result
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
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="SEARCH block (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return (
                f"Error: SEARCH block not found in {path}.\n"
                f"Best match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
            )
        return (
            f"Error: SEARCH block not found in {path}. "
            "No similar text found. Verify the file content with read_file first."
        )


def _reindent_replacement(original_text: str, search: str, replace: str) -> str:
    """Re-indent replacement text to match the original file's indentation."""
    orig_lines = original_text.splitlines(keepends=True)
    if not orig_lines:
        return replace

    # Detect original indentation from first non-empty line
    original_indent = 0
    for line in orig_lines:
        if line.strip():
            original_indent = len(line) - len(line.lstrip())
            break

    # Detect search indentation
    search_indent = 0
    for line in search.splitlines():
        if line.strip():
            search_indent = len(line) - len(line.lstrip())
            break

    # Detect replace indentation
    replace_indent = 0
    for line in replace.splitlines():
        if line.strip():
            replace_indent = len(line) - len(line.lstrip())
            break

    # Re-indent: remove replace's base indent, add original indent
    result_lines = []
    for line in replace.splitlines(keepends=True):
        if line.strip():
            # Remove up to replace_indent spaces, then add original_indent
            stripped = line
            removed = 0
            while removed < replace_indent and stripped and stripped[0] == " ":
                stripped = stripped[1:]
                removed += 1
            result_lines.append(" " * original_indent + stripped)
        else:
            result_lines.append(line)

    return "".join(result_lines)


async def _collect_post_edit_diagnostics(
    lsp_manager: Any, file_path: str, is_new: bool = False, max_errors: int = 20
) -> str:
    """Collect LSP diagnostics after a file edit and format as summary."""
    try:
        diags = await lsp_manager.touch_file_and_wait(file_path, timeout=3.0)
        errors = [d for d in diags if d.get("severity") == 1]
        if not errors:
            return ""

        lines = [f"LSP Errors ({len(errors)}):"]
        for diag in errors[:max_errors]:
            line_num = diag.get("range", {}).get("start", {}).get("line", 0) + 1
            message = diag.get("message", "")
            source = diag.get("source", "")
            source_str = f" [{source}]" if source else ""
            lines.append(f"  Line {line_num}:{source_str} {message}")

        if len(errors) > max_errors:
            lines.append(f"  ... and {len(errors) - max_errors} more errors")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"Failed to collect post-edit diagnostics: {e}")
        return ""


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        self._workspace = workspace
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
            "properties": {"path": {"type": "string", "description": "The directory path to list"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(path, self._workspace, self._allowed_dir)
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
