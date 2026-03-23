from typing import Any
from pathlib import Path
from nanobot.agent.tools.base import Tool
from nanobot.agent.code.lsp import LSPManager
from loguru import logger


def _graceful_lsp(func):
    """Decorator for graceful LSP degradation when no server is available."""

    async def wrapper(self, file_path: str, line: int, character: int, **kwargs: Any) -> str:
        try:
            client = await self.lsp_manager.get_client(file_path)
        except Exception as e:
            logger.debug(f"LSP unavailable for {file_path}: {e}")
            client = None

        if not client:
            ext = Path(file_path).suffix
            return (
                f"No LSP server available for {ext} files. "
                "Use grep/find_files for code navigation instead, "
                "or install a language server (e.g., pyright for Python, tsserver for TypeScript)."
            )

        return await func(self, file_path, line, character, _client=client, **kwargs)

    return wrapper


class LSPDefinitionTool(Tool):
    """Tool to find symbol definitions using LSP."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "go_to_definition"

    @property
    def description(self) -> str:
        return "Find the definition of a symbol at a specific line/character in a file. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file containing the symbol",
                },
                "line": {"type": "integer", "description": "Line number (1-based)"},
                "character": {
                    "type": "integer",
                    "description": "Character position (0-based column offset)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    @_graceful_lsp
    async def execute(
        self, file_path: str, line: int, character: int, _client=None, **kwargs: Any
    ) -> str:
        try:
            resp = await _client.definition(file_path, line - 1, character)

            if not resp:
                return "No definition found."

            locations = resp if isinstance(resp, list) else [resp]
            results = []

            for loc in locations:
                uri = loc.get("uri") or loc.get("targetUri")
                r = loc.get("range") or loc.get("targetRange")

                if uri and r:
                    path = uri.replace("file://", "")
                    start_line = r["start"]["line"] + 1
                    start_col = r["start"]["character"]
                    results.append(f"{path}:{start_line}:{start_col}")

            if not results:
                return "No definition locations found."

            return "\n".join(results)

        except Exception as e:
            return f"LSP Error: {e}"


class LSPReferencesTool(Tool):
    """Tool to find symbol references using LSP."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "find_references"

    @property
    def description(self) -> str:
        return "Find all references/usages of a symbol at a specific line/character. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file containing the symbol",
                },
                "line": {"type": "integer", "description": "Line number (1-based)"},
                "character": {
                    "type": "integer",
                    "description": "Character position (0-based column offset)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    @_graceful_lsp
    async def execute(
        self, file_path: str, line: int, character: int, _client=None, **kwargs: Any
    ) -> str:
        try:
            resp = await _client.references(file_path, line - 1, character)

            if not resp:
                return "No references found."

            results = []
            for loc in resp:
                uri = loc.get("uri")
                r = loc.get("range")
                if uri and r:
                    path = uri.replace("file://", "")
                    start_line = r["start"]["line"] + 1
                    results.append(f"{path}:{start_line}")

            results = list(dict.fromkeys(results))
            return (
                f"Found {len(results)} references:\n"
                + "\n".join(results[:50])
                + ("\n...(truncated)" if len(results) > 50 else "")
            )

        except Exception as e:
            return f"LSP Error: {e}"


class LSPHoverTool(Tool):
    """Tool to get hover information (types, docstrings)."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "get_hover_info"

    @property
    def description(self) -> str:
        return "Get type information and documentation for a symbol. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "line": {"type": "integer", "description": "Line number (1-based)"},
                "character": {
                    "type": "integer",
                    "description": "Character position (0-based column offset)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    @_graceful_lsp
    async def execute(
        self, file_path: str, line: int, character: int, _client=None, **kwargs: Any
    ) -> str:
        try:
            resp = await _client.hover(file_path, line - 1, character)
            if not resp or not resp.get("contents"):
                return "No hover info available."

            contents = resp["contents"]

            if isinstance(contents, dict) and "value" in contents:
                return contents["value"]
            elif isinstance(contents, list):
                return "\n".join(
                    [c if isinstance(c, str) else c.get("value", "") for c in contents]
                )
            elif isinstance(contents, str):
                return contents

            return str(contents)

        except Exception as e:
            return f"LSP Error: {e}"


class LSPDocumentSymbolTool(Tool):
    """Tool to get all symbols in a document."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "document_symbol"

    @property
    def description(self) -> str:
        return "Get all symbols (functions, classes, variables) in a document. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"}
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str, **kwargs: Any) -> str:
        try:
            client = await self.lsp_manager.get_client(file_path)
            if not client:
                ext = Path(file_path).suffix
                return f"No LSP server available for{ext} files. Install a language server (e.g., pyright for Python)."

            symbols = await client.document_symbol(file_path)
            if not symbols:
                return "No symbols found."

            lines = []
            for sym in symbols:
                kind = sym.get("kind", 0)
                name = sym.get("name", "unknown")
                range_info = sym.get("range", {})
                start = range_info.get("start", {})
                line_num = start.get("line", 0) + 1

                kind_names = {
                    1: "Module",
                    2: "Class",
                    3: "Enum",
                    4: "Interface",
                    5: "Method",
                    6: "Member",
                    7: "Property",
                    8: "Field",
                    9: "Constructor",
                    10: "EnumMember",
                    11: "Struct",
                    12: "Event",
                    13: "Operator",
                    14: "TypeParameter",
                    15: "Variable",
                    16: "Function",
                    17: "Constant",
                }
                kind_str = kind_names.get(kind, "Symbol")

                lines.append(f"{kind_str}: {name} at line {line_num}")

            return "\n".join(lines[:50]) + ("\n...(truncated)" if len(lines) > 50 else "")

        except Exception as e:
            return f"LSP Error: {e}"


class LSPWorkspaceSymbolTool(Tool):
    """Tool to search for symbols across the workspace."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "workspace_symbol"

    @property
    def description(self) -> str:
        return "Search for symbols across the entire workspace. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Symbol name to search for"}},
            "required": ["query"],
        }

    async def execute(self, query: str, **kwargs: Any) -> str:
        try:
            clients = self.lsp_manager.clients
            if not clients:
                return "No LSP server available."

            client = list(clients.values())[0]
            symbols = await client.workspace_symbol(query)

            if not symbols:
                return f"No symbols found for '{query}'."

            lines = []
            for sym in symbols:
                name = sym.get("name", "unknown")
                kind = sym.get("kind", 0)
                location = sym.get("location", {})
                uri = location.get("uri", "")
                path = uri.replace("file://", "")

                kind_names = {
                    1: "Module",
                    2: "Class",
                    3: "Enum",
                    4: "Interface",
                    5: "Method",
                    6: "Member",
                    7: "Property",
                    8: "Field",
                    15: "Variable",
                    16: "Function",
                }
                kind_str = kind_names.get(kind, "Symbol")

                lines.append(f"{kind_str}: {name} in {path}")

            return "\n".join(lines[:50]) + ("\n...(truncated)" if len(lines) > 50 else "")

        except Exception as e:
            return f"LSP Error: {e}"


class LSPImplementationTool(Tool):
    """Tool to find implementations of an interface or abstract method."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "go_to_implementation"

    @property
    def description(self) -> str:
        return "Find implementations of an interface or abstract method. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "line": {"type": "integer", "description": "Line number (1-based)"},
                "character": {
                    "type": "integer",
                    "description": "Character position (0-based column offset)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    @_graceful_lsp
    async def execute(
        self, file_path: str, line: int, character: int, _client=None, **kwargs: Any
    ) -> str:
        try:
            resp = await _client.implementation(file_path, line - 1, character)

            if not resp:
                return "No implementations found."

            locations = resp if isinstance(resp, list) else [resp]
            results = []

            for loc in locations:
                uri = loc.get("uri") or loc.get("targetUri")
                r = loc.get("range") or loc.get("targetRange")

                if uri and r:
                    path = uri.replace("file://", "")
                    start_line = r["start"]["line"] + 1
                    results.append(f"{path}:{start_line}")

            if not results:
                return "No implementation locations found."

            return "\n".join(results)

        except Exception as e:
            return f"LSP Error: {e}"


class LSPGetDiagnosticsTool(Tool):
    """Tool to get current diagnostics (errors, warnings) for a file."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "get_diagnostics"

    @property
    def description(self) -> str:
        return (
            "Get current diagnostics (errors, warnings) for a file. Requires a running LSP server."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"}
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str, **kwargs: Any) -> str:
        try:
            client = await self.lsp_manager.get_client(file_path)
            if not client:
                return "No LSP server available."

            diagnostics = client.get_diagnostics(file_path)

            if not diagnostics:
                return "No diagnostics (no errors or warnings)."

            lines = []
            for diag in diagnostics:
                severity = diag.get("severity", 1)
                severity_name = {1: "Error", 2: "Warning", 3: "Info", 4: "Hint"}.get(
                    severity, "Unknown"
                )
                line_num = diag["range"]["start"]["line"] + 1
                message = diag.get("message", "")
                source = diag.get("source", "")

                source_str = f" [{source}]" if source else ""
                lines.append(f"[{severity_name}] Line {line_num}:{source_str} {message}")

            return "\n".join(lines[:50]) + ("\n...(truncated)" if len(lines) > 50 else "")

        except Exception as e:
            return f"LSP Error: {e}"


class LSPTouchFileTool(Tool):
    """Tool to sync a file with LSP servers."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "lsp_touch_file"

    @property
    def description(self) -> str:
        return "Sync a file with LSP servers (refresh diagnostics, etc.). Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "is_new": {
                    "type": "boolean",
                    "description": "Whether this is a new file",
                    "default": False,
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str, is_new: bool = False, **kwargs: Any) -> str:
        try:
            await self.lsp_manager.touch_file(file_path, is_new)
            return f"File synced with LSP servers: {file_path}"
        except Exception as e:
            return f"LSP Error: {e}"
