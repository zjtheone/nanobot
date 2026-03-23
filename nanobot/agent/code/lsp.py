import asyncio
import json
import os
import shutil
from typing import Any, Optional, Dict, List, Tuple
from pathlib import Path
from urllib.parse import unquote, urlparse
from loguru import logger


class LSPClient:
    """
    A lightweight JSON-RPC 2.0 client for Language Server Protocol (LSP).
    Communicates with language servers via stdio.
    """

    DEFAULT_TIMEOUT = 30.0  # seconds for normal requests
    INIT_TIMEOUT = 45.0  # seconds for initialize handshake

    def __init__(self, name: str, command: List[str], root_uri: str):
        self.name = name
        self.command = command
        self.root_uri = root_uri
        self.workspace = Path(urlparse(root_uri).path)
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self.capabilities: Dict[str, Any] = {}
        self._initialized = False
        self.diagnostics: Dict[str, List[Dict]] = {}  # path -> diagnostics
        self.initialization_options: Dict[str, Any] = {}
        self.env: Dict[str, str] = {}  # extra environment variables

    async def start(self):
        """Start the language server subprocess."""
        if self.process:
            return

        logger.info(f"Starting LSP server '{self.name}': {' '.join(self.command)}")
        try:
            env = os.environ.copy()
            env.update(self.env)
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            self._reader_task = asyncio.create_task(self._read_stdout())
            self._stderr_task = asyncio.create_task(self._read_stderr())

            await self._initialize()

        except Exception as e:
            logger.error(f"Failed to start LSP server '{self.name}': {e}")
            raise

    async def stop(self):
        """Stop the language server."""
        if not self.process:
            return

        try:
            await self.send_request("shutdown", timeout=5.0)
            self.send_notification("exit")
        except Exception:
            pass

        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.kill()

        if self._reader_task:
            self._reader_task.cancel()
        if self._stderr_task:
            self._stderr_task.cancel()

        self.process = None

    async def _initialize(self):
        """Send initialize request."""
        params = {
            "processId": os.getpid(),
            "rootUri": self.root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": False,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                        "didSave": True,
                    },
                    "completion": {"dynamicRegistration": False},
                    "hover": {"dynamicRegistration": False},
                    "signatureHelp": {"dynamicRegistration": False},
                    "definition": {"dynamicRegistration": False},
                    "references": {"dynamicRegistration": False},
                    "documentHighlight": {"dynamicRegistration": False},
                    "documentSymbol": {"dynamicRegistration": False},
                    "codeAction": {"dynamicRegistration": False},
                    "formatting": {"dynamicRegistration": False},
                    "rangeFormatting": {"dynamicRegistration": False},
                    "onTypeFormatting": {"dynamicRegistration": False},
                    "rename": {"dynamicRegistration": False},
                    "publishDiagnostics": {"relatedInformation": True},
                },
                "workspace": {
                    "didChangeConfiguration": {"dynamicRegistration": False},
                    "workspaceFolders": True,
                },
            },
            "initializationOptions": self.initialization_options,
            "workspaceFolders": [
                {"uri": self.root_uri, "name": self.workspace.name}
            ],
            "trace": "off",
        }

        response = await self.send_request(
            "initialize", params, timeout=self.INIT_TIMEOUT
        )
        self.capabilities = response.get("capabilities", {}) if response else {}
        self.send_notification("initialized", {})
        self._initialized = True
        logger.info(
            f"LSP server '{self.name}' initialized. Capabilities: {list(self.capabilities.keys())}"
        )

    async def send_request(
        self, method: str, params: Any = None, timeout: float | None = None
    ) -> Any:
        """Send a JSON-RPC request and wait for the response with timeout."""
        if not self.process:
            raise RuntimeError("LSP server not running")

        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        self._request_id += 1
        request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future

        await self._send_payload(request)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"LSP request '{method}' timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"LSP request '{method}' failed: {e}")
            raise
        finally:
            self._pending_requests.pop(request_id, None)

    def send_notification(self, method: str, params: Any = None):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process:
            return

        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        asyncio.create_task(self._send_payload(notification))

    async def _send_payload(self, payload: Dict[str, Any]):
        """Encode and write payload to stdin."""
        if not self.process or not self.process.stdin:
            return

        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")

        try:
            self.process.stdin.write(header + body)
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"Failed to send LSP payload: {e}")

    async def _read_stdout(self):
        """Read and decode JSON-RPC messages from stdout."""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                content_length = 0
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        break

                    line = line.strip()
                    if not line:
                        break

                    if line.startswith(b"Content-Length:"):
                        content_length = int(line.split(b":")[1].strip())

                if content_length == 0:
                    if self.process.returncode is not None:
                        break
                    continue

                body = await self.process.stdout.readexactly(content_length)

                try:
                    message = json.loads(body.decode("utf-8"))
                    self._handle_message(message)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode LSP message: {body[:100]}")
                except Exception as e:
                    logger.error(f"Error handling LSP message: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"LSP stdout reader crashed: {e}")

    async def _read_stderr(self):
        """Log stderr output from the language server."""
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                logger.debug(f"LSP [{self.name}] stderr: {line.decode().strip()}")
        except Exception:
            pass

    def _handle_message(self, message: Dict[str, Any]):
        """Handle an incoming JSON-RPC message."""
        if "id" in message and "method" not in message:
            # Response
            request_id = message.get("id")
            if request_id in self._pending_requests:
                future = self._pending_requests[request_id]
                if not future.done():
                    if "error" in message:
                        future.set_exception(RuntimeError(message["error"]))
                    else:
                        future.set_result(message.get("result"))
        elif "method" in message:
            method = message["method"]
            params = message.get("params")

            if method == "textDocument/publishDiagnostics":
                self._handle_diagnostics(params)
            elif method == "window/logMessage":
                self._handle_log_message(params)
            # Respond to server requests that require a response
            elif "id" in message:
                self._handle_server_request(message)

    def _handle_server_request(self, message: Dict[str, Any]):
        """Handle requests from server that need a response."""
        method = message["method"]
        request_id = message["id"]

        result: Any = None
        if method == "workspace/configuration":
            # Return initialization options for each requested section
            params = message.get("params", {})
            items = params.get("items", [])
            result = [self.initialization_options.get(item.get("section", ""), {}) for item in items]
        elif method == "client/registerCapability":
            result = None  # Accept dynamic registration
        elif method == "client/unregisterCapability":
            result = None
        elif method == "window/workDoneProgress/create":
            result = None
        elif method == "workspace/workspaceFolders":
            result = [{"uri": self.root_uri, "name": self.workspace.name}]

        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        asyncio.create_task(self._send_payload(response))

    def _handle_diagnostics(self, params: Dict[str, Any]):
        """Handle diagnostics notification from LSP server."""
        uri = params.get("uri")
        diagnostics = params.get("diagnostics", [])

        if not uri:
            return

        path = unquote(urlparse(uri).path)
        self.diagnostics[path] = diagnostics

        logger.debug(f"LSP [{self.name}] diagnostics for {path}: {len(diagnostics)} issues")

    def _handle_log_message(self, params: Any):
        if not params:
            return
        msg_type = params.get("type", 4)
        message = params.get("message", "")

        if msg_type == 1:
            logger.error(f"LSP [{self.name}]: {message}")
        elif msg_type == 2:
            logger.warning(f"LSP [{self.name}]: {message}")
        else:
            logger.debug(f"LSP [{self.name}]: {message}")

    # --- Diagnostics Wait ---

    async def wait_for_diagnostics(
        self, file_path: str, timeout: float = 3.0, debounce: float = 0.15
    ) -> List[Dict[str, Any]]:
        """Wait for diagnostics to stabilize for a file.

        Polls diagnostics with debounce interval. Returns when diagnostics
        haven't changed for one debounce period, or when timeout is reached.
        """
        end_time = asyncio.get_event_loop().time() + timeout
        last_count = -1
        while asyncio.get_event_loop().time() < end_time:
            await asyncio.sleep(debounce)
            current = self.diagnostics.get(file_path, [])
            if len(current) == last_count and last_count >= 0:
                return current  # Stabilized
            last_count = len(current)
        return self.diagnostics.get(file_path, [])

    # --- Convenience Methods ---

    async def did_open(self, file_path: str, text: str, language_id: str):
        """Notify that a document was opened."""
        params = {
            "textDocument": {
                "uri": Path(file_path).as_uri(),
                "languageId": language_id,
                "version": 1,
                "text": text,
            }
        }
        self.send_notification("textDocument/didOpen", params)
        self.diagnostics.pop(file_path, None)

    async def did_change(self, file_path: str, text: str, version: int):
        """Notify that a document changed."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri(), "version": version},
            "contentChanges": [{"text": text}],
        }
        self.send_notification("textDocument/didChange", params)

    async def did_close(self, file_path: str):
        """Notify that a document was closed."""
        params = {"textDocument": {"uri": Path(file_path).as_uri()}}
        self.send_notification("textDocument/didClose", params)

    async def did_change_watched_files(self, file_path: str, change_type: int):
        """Notify that a file was created/changed/deleted.

        change_type: 1=Created, 2=Changed, 3=Deleted
        """
        params = {"changes": [{"uri": Path(file_path).as_uri(), "type": change_type}]}
        self.send_notification("workspace/didChangeWatchedFiles", params)

    async def touch_file(self, file_path: str, is_new: bool = False):
        """Touch a file to sync with LSP server."""
        change_type = 1 if is_new else 2
        await self.did_change_watched_files(file_path, change_type)

        try:
            text = Path(file_path).read_text(encoding="utf-8")
            language_id = self._guess_language_id(file_path)
            await self.did_open(file_path, text, language_id)
        except Exception as e:
            logger.error(f"Failed to touch file {file_path}: {e}")

    def _guess_language_id(self, file_path: str) -> str:
        """Guess language ID from file extension."""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_IDS.get(ext, "plaintext")

    def get_diagnostics(self, file_path: str) -> List[Dict[str, Any]]:
        """Get current diagnostics for a file."""
        return self.diagnostics.get(file_path, [])

    def clear_diagnostics(self, file_path: str):
        """Clear diagnostics for a file."""
        self.diagnostics.pop(file_path, None)

    # --- LSP Operations ---

    async def definition(self, file_path: str, line: int, character: int) -> Any:
        """Find definition."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
        }
        return await self.send_request("textDocument/definition", params)

    async def references(self, file_path: str, line: int, character: int) -> Any:
        """Find references."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": True},
        }
        return await self.send_request("textDocument/references", params)

    async def hover(self, file_path: str, line: int, character: int) -> Any:
        """Get hover info."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
        }
        return await self.send_request("textDocument/hover", params)

    async def document_symbol(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all symbols in a document."""
        params = {"textDocument": {"uri": Path(file_path).as_uri()}}
        return await self.send_request("textDocument/documentSymbol", params) or []

    async def workspace_symbol(self, query: str = "") -> List[Dict[str, Any]]:
        """Search for symbols across the workspace."""
        params = {"query": query}
        return await self.send_request("workspace/symbol", params) or []

    async def implementation(self, file_path: str, line: int, character: int) -> Any:
        """Find implementations of an interface or abstract method."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
        }
        return await self.send_request("textDocument/implementation", params)

    async def prepare_call_hierarchy(
        self, file_path: str, line: int, character: int
    ) -> Any:
        """Get call hierarchy item at position."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
        }
        return await self.send_request("callHierarchy/prepare", params)

    async def incoming_calls(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all functions that call this function."""
        params = {"item": item}
        return await self.send_request("callHierarchy/incomingCalls", params) or []

    async def outgoing_calls(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all functions called by this function."""
        params = {"item": item}
        return await self.send_request("callHierarchy/outgoingCalls", params) or []

    async def rename(
        self, file_path: str, line: int, character: int, new_name: str
    ) -> Any:
        """Rename a symbol."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
            "newName": new_name,
        }
        return await self.send_request("textDocument/rename", params)


# --- Language ID Mapping ---

LANGUAGE_IDS: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".zig": "zig",
    ".ex": "elixir",
    ".exs": "elixir",
    ".lua": "lua",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".jsonc": "json",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".html": "html",
    ".htm": "html",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".toml": "toml",
    ".xml": "xml",
    ".sql": "sql",
    ".md": "markdown",
    ".r": "r",
    ".R": "r",
    ".scala": "scala",
    ".dart": "dart",
    ".vue": "vue",
    ".svelte": "svelte",
}


# --- Workspace Edit ---


def apply_workspace_edit(workspace_path: Path, edit: Dict[str, Any]) -> List[str]:
    """
    Apply a WorkspaceEdit to the file system.
    Returns a list of modified file paths.
    """
    modified_files = []

    def apply_text_edits(content: str, changes: List[Dict[str, Any]]) -> str:
        lines = content.splitlines(keepends=True)
        full_text = "".join(lines)

        # Sort changes in reverse order to avoid offset shifting
        changes.sort(
            key=lambda c: (
                c["range"]["start"]["line"],
                c["range"]["start"]["character"],
            ),
            reverse=True,
        )

        for change in changes:
            start_line = change["range"]["start"]["line"]
            start_char = change["range"]["start"]["character"]
            end_line = change["range"]["end"]["line"]
            end_char = change["range"]["end"]["character"]
            new_text = change["newText"]

            start_offset = 0
            end_offset = 0
            found_start = False
            found_end = False

            offset = 0
            for i, line in enumerate(lines):
                if not found_start and i == start_line:
                    start_offset = offset + start_char
                    found_start = True

                if not found_end and i == end_line:
                    end_offset = offset + end_char
                    found_end = True
                    break

                offset += len(line)

            if found_start and found_end:
                full_text = full_text[:start_offset] + new_text + full_text[end_offset:]

        return full_text

    changes = edit.get("changes", {})
    document_changes = edit.get("documentChanges", [])

    if document_changes:
        for doc_edit in document_changes:
            if "textDocument" in doc_edit:
                uri = doc_edit["textDocument"]["uri"]
                edits = doc_edit["edits"]
                if uri not in changes:
                    changes[uri] = []
                changes[uri].extend(edits)

    for uri, file_changes in changes.items():
        if not uri.startswith("file://"):
            continue

        path_str = unquote(urlparse(uri).path)
        file_path = Path(path_str)
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            new_content = apply_text_edits(content, file_changes)
            file_path.write_text(new_content, encoding="utf-8")
            modified_files.append(str(file_path))
            logger.info(f"Applied LSP edits to {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply edits to {file_path}: {e}")

    return modified_files


# --- LSP Manager ---

# Project root marker files per language
PROJECT_MARKERS: Dict[str, List[str]] = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "tox.ini"],
    "typescript": ["tsconfig.json", "package.json"],
    "javascript": ["package.json", "jsconfig.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
    "kotlin": ["build.gradle.kts", "build.gradle", "settings.gradle.kts"],
    "c": ["CMakeLists.txt", "Makefile", "meson.build", "compile_commands.json"],
    "cpp": ["CMakeLists.txt", "Makefile", "meson.build", "compile_commands.json"],
    "ruby": ["Gemfile", ".ruby-version"],
    "lua": [".luarc.json", ".luarc.jsonc"],
    "swift": ["Package.swift", "*.xcodeproj"],
    "zig": ["build.zig"],
    "elixir": ["mix.exs"],
    "bash": [".bashrc"],  # fallback to workspace
    "yaml": [],
    "css": ["package.json"],
    "html": ["package.json"],
    "json": ["package.json"],
    "dockerfile": ["Dockerfile", "docker-compose.yml"],
    "scala": ["build.sbt"],
    "dart": ["pubspec.yaml"],
    "csharp": ["*.csproj", "*.sln"],
}


class LSPManager:
    """
    Manages multiple LSP clients for different languages.
    Supports NearestRoot project detection, broken server tracking,
    and spawn deduplication.
    """

    # Default server commands (language -> [command, args...])
    SERVER_COMMANDS: Dict[str, List[str]] = {
        "python": ["pyright-langserver", "--stdio"],
        "go": ["gopls"],
        "typescript": ["typescript-language-server", "--stdio"],
        "javascript": ["typescript-language-server", "--stdio"],
        "rust": ["rust-analyzer"],
        "java": ["jdtls"],
        "c": ["clangd"],
        "cpp": ["clangd"],
        "ruby": ["ruby-lsp"],
        "kotlin": ["kotlin-language-server"],
        "swift": ["sourcekit-lsp"],
        "zig": ["zls"],
        "elixir": ["elixir-ls"],
        "bash": ["bash-language-server", "start"],
        "lua": ["lua-language-server"],
        "yaml": ["yaml-language-server", "--stdio"],
        "css": ["vscode-css-language-server", "--stdio"],
        "html": ["vscode-html-language-server", "--stdio"],
        "json": ["vscode-json-language-server", "--stdio"],
        "dockerfile": ["docker-langserver", "--stdio"],
        "scala": ["metals"],
        "dart": ["dart", "language-server"],
        "csharp": ["OmniSharp", "-lsp"],
        "vue": ["vue-language-server", "--stdio"],
        "svelte": ["svelteserver", "--stdio"],
    }

    # Extension -> language mapping
    EXTENSIONS: Dict[str, str] = {
        ".py": "python",
        ".pyi": "python",
        ".go": "go",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".cc": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".swift": "swift",
        ".zig": "zig",
        ".ex": "elixir",
        ".exs": "elixir",
        ".sh": "bash",
        ".bash": "bash",
        ".lua": "lua",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".css": "css",
        ".scss": "css",
        ".less": "css",
        ".html": "html",
        ".htm": "html",
        ".json": "json",
        ".jsonc": "json",
        ".dockerfile": "dockerfile",
        ".scala": "scala",
        ".dart": "dart",
        ".vue": "vue",
        ".svelte": "svelte",
    }

    def __init__(
        self,
        workspace: Path,
        server_configs: Optional[Dict[str, Dict]] = None,
        lsp_config: Optional[Any] = None,
    ):
        self.workspace = workspace
        # Key: (lang, project_root_str) -> LSPClient
        self.clients: Dict[Tuple[str, str], LSPClient] = {}
        self.root_uri = workspace.as_uri()
        self.server_configs = server_configs or {}

        # Broken server tracking: set of (lang, root) keys that failed
        self._broken: set[Tuple[str, str]] = set()

        # Spawn deduplication: ongoing spawn tasks
        self._spawning: Dict[Tuple[str, str], asyncio.Task] = {}

        # Apply LSP config overrides
        if lsp_config:
            self._apply_config(lsp_config)

    def _apply_config(self, lsp_config: Any):
        """Apply LspConfig overrides to server commands and configs."""
        if not hasattr(lsp_config, "servers"):
            return
        for lang, server_cfg in lsp_config.servers.items():
            if server_cfg.disabled:
                # Remove from available servers
                self.SERVER_COMMANDS.pop(lang, None)
                continue
            if server_cfg.command:
                self.SERVER_COMMANDS[lang] = list(server_cfg.command)
            if server_cfg.initialization_options:
                self.server_configs[lang] = {
                    "initializationOptions": dict(server_cfg.initialization_options)
                }
            if server_cfg.env:
                # Store env in server_configs for later use
                cfg = self.server_configs.setdefault(lang, {})
                cfg["env"] = dict(server_cfg.env)

    def _find_project_root(self, file_path: str, lang: str) -> Path:
        """Find the nearest project root by walking up from file_path.

        Looks for language-specific marker files (pyproject.toml, package.json,
        go.mod, Cargo.toml, etc.) and returns the directory containing the first
        match. Falls back to workspace root.
        """
        markers = PROJECT_MARKERS.get(lang, [])
        if not markers:
            return self.workspace

        current = Path(file_path).parent.resolve()
        workspace_resolved = self.workspace.resolve()

        while True:
            for marker in markers:
                if "*" in marker:
                    # Glob pattern (e.g., "*.csproj")
                    if list(current.glob(marker)):
                        return current
                elif (current / marker).exists():
                    return current

            if current == workspace_resolved or current == current.parent:
                break
            current = current.parent

        return self.workspace

    async def get_client(self, file_path: str) -> Optional[LSPClient]:
        """Get or start a client for the given file.

        Uses NearestRoot to find the correct project root, deduplicates
        concurrent spawn requests, and tracks broken servers.
        """
        ext = Path(file_path).suffix.lower()
        lang = self.EXTENSIONS.get(ext)

        if not lang:
            return None

        # Find project root
        project_root = self._find_project_root(file_path, lang)
        key = (lang, str(project_root))

        # Check if broken
        if key in self._broken:
            return None

        # Return existing client
        if key in self.clients:
            client = self.clients[key]
            if client.process and client.process.returncode is None:
                return client
            # Client died — remove and retry
            del self.clients[key]

        # Deduplicate concurrent spawn requests
        if key in self._spawning:
            try:
                return await self._spawning[key]
            except Exception:
                return None

        # Determine command
        cmd = list(self.SERVER_COMMANDS.get(lang, []))
        if not cmd:
            return None

        # Check binary availability
        if not shutil.which(cmd[0]):
            logger.warning(f"LSP server for {lang} ({cmd[0]}) not found in PATH.")
            self._broken.add(key)
            return None

        # Spawn
        task = asyncio.create_task(self._spawn_client(key, lang, cmd, project_root))
        self._spawning[key] = task

        try:
            return await task
        finally:
            self._spawning.pop(key, None)

    async def _spawn_client(
        self, key: Tuple[str, str], lang: str, cmd: List[str], project_root: Path
    ) -> Optional[LSPClient]:
        """Spawn a new LSP client."""
        config = self.server_configs.get(lang, {})
        root_uri = project_root.as_uri()

        try:
            client = LSPClient(lang, cmd, root_uri)
            client.initialization_options = config.get("initializationOptions", {})
            client.env = config.get("env", {})
            await client.start()
            self.clients[key] = client
            logger.info(f"Started LSP server for {lang} at {project_root}")
            return client
        except Exception as e:
            logger.error(f"Failed to start {lang} LSP at {project_root}: {e}")
            self._broken.add(key)
            return None

    async def get_client_for_lang(self, lang: str) -> Optional[LSPClient]:
        """Get any existing client for a given language (for workspace-wide queries)."""
        for (client_lang, _root), client in self.clients.items():
            if client_lang == lang and client.process and client.process.returncode is None:
                return client
        return None

    async def touch_file(self, file_path: str, is_new: bool = False):
        """Touch file in the relevant LSP server for its language."""
        ext = Path(file_path).suffix.lower()
        lang = self.EXTENSIONS.get(ext)
        if not lang:
            return

        client = await self.get_client(file_path)
        if client:
            await client.touch_file(file_path, is_new)

    async def touch_file_and_wait(
        self, file_path: str, timeout: float = 3.0
    ) -> List[Dict[str, Any]]:
        """Touch file and wait for diagnostics to stabilize."""
        ext = Path(file_path).suffix.lower()
        lang = self.EXTENSIONS.get(ext)
        if not lang:
            return []

        client = await self.get_client(file_path)
        if not client:
            return []

        await client.touch_file(file_path)
        return await client.wait_for_diagnostics(file_path, timeout=timeout)

    async def collect_diagnostics(
        self, file_path: str, severity_filter: int | None = 1
    ) -> List[Dict[str, Any]]:
        """Collect diagnostics for a file, optionally filtered by severity.

        severity_filter: 1=Error only, 2=Error+Warning, None=all
        """
        client = await self.get_client(file_path)
        if not client:
            return []

        diags = client.get_diagnostics(file_path)
        if severity_filter is not None:
            diags = [d for d in diags if d.get("severity", 1) <= severity_filter]
        return diags

    async def shutdown(self):
        """Stop all clients."""
        # Cancel any in-flight spawns
        for task in self._spawning.values():
            task.cancel()
        self._spawning.clear()

        for client in self.clients.values():
            await client.stop()
        self.clients.clear()
        self._broken.clear()
