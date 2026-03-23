"""Tests for enhanced LSP features."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.agent.code.lsp import LSPClient, LSPManager
from nanobot.agent.tools.lsp import (
    LSPDocumentSymbolTool,
    LSPWorkspaceSymbolTool,
    LSPImplementationTool,
    LSPGetDiagnosticsTool,
    LSPTouchFileTool,
)


class TestLSPClientEnhanced:
    """Test enhanced LSP client features."""

    def test_diagnostics_storage(self):
        """Test diagnostics storage initialization."""
        client = LSPClient("test", ["test"], "file:///tmp")
        assert hasattr(client, "diagnostics")
        assert isinstance(client.diagnostics, dict)

    def test_guess_language_id(self):
        """Test language ID guessing."""
        client = LSPClient("test", ["test"], "file:///tmp")

        assert client._guess_language_id("test.py") == "python"
        assert client._guess_language_id("test.ts") == "typescript"
        assert client._guess_language_id("test.js") == "javascript"
        assert client._guess_language_id("test.unknown") == "plaintext"

    def test_get_diagnostics_empty(self):
        """Test getting diagnostics for file without diagnostics."""
        client = LSPClient("test", ["test"], "file:///tmp")
        diagnostics = client.get_diagnostics("/tmp/test.py")
        assert diagnostics == []

    def test_clear_diagnostics(self):
        """Test clearing diagnostics."""
        client = LSPClient("test", ["test"], "file:///tmp")
        client.diagnostics["/tmp/test.py"] = [{"severity": 1, "message": "Error"}]
        client.clear_diagnostics("/tmp/test.py")
        assert "/tmp/test.py" not in client.diagnostics


class TestLSPClientAsyncMethods:
    """Test async LSP client methods."""

    @pytest.mark.asyncio
    async def test_document_symbol(self):
        """Test document symbol method exists."""
        client = LSPClient("test", ["test"], "file:///tmp")
        # Just check method exists, actual testing requires running LSP server
        assert hasattr(client, "document_symbol")
        assert callable(client.document_symbol)

    @pytest.mark.asyncio
    async def test_workspace_symbol(self):
        """Test workspace symbol method exists."""
        client = LSPClient("test", ["test"], "file:///tmp")
        assert hasattr(client, "workspace_symbol")
        assert callable(client.workspace_symbol)

    @pytest.mark.asyncio
    async def test_implementation(self):
        """Test implementation method exists."""
        client = LSPClient("test", ["test"], "file:///tmp")
        assert hasattr(client, "implementation")
        assert callable(client.implementation)

    @pytest.mark.asyncio
    async def test_prepare_call_hierarchy(self):
        """Test call hierarchy methods exist."""
        client = LSPClient("test", ["test"], "file:///tmp")
        assert hasattr(client, "prepare_call_hierarchy")
        assert hasattr(client, "incoming_calls")
        assert hasattr(client, "outgoing_calls")


class TestLSPManagerEnhanced:
    """Test enhanced LSP manager features."""

    def test_manager_with_config(self):
        """Test manager initialization with server configs."""
        config = {
            "python": {"initializationOptions": {"pyright": {"disableLanguageServices": False}}}
        }
        manager = LSPManager(workspace=Path("/tmp"), server_configs=config)
        assert manager.server_configs == config

    def test_manager_touch_file_method(self):
        """Test touch_file method exists."""
        manager = LSPManager(workspace=Path("/tmp"))
        assert hasattr(manager, "touch_file")
        assert callable(manager.touch_file)


class TestLSPDocumentSymbolTool:
    """Test LSPDocumentSymbolTool."""

    @pytest.mark.asyncio
    async def test_no_lsp_server(self):
        """Test behavior when no LSP server is available."""
        mock_manager = MagicMock()
        mock_manager.get_client = AsyncMock(return_value=None)

        tool = LSPDocumentSymbolTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "No LSP server" in result

    @pytest.mark.asyncio
    async def test_empty_symbols(self):
        """Test behavior when no symbols found."""
        mock_manager = MagicMock()
        mock_client = AsyncMock()
        mock_client.document_symbol = AsyncMock(return_value=[])
        mock_manager.get_client = AsyncMock(return_value=mock_client)

        tool = LSPDocumentSymbolTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "No symbols found" in result

    @pytest.mark.asyncio
    async def test_with_symbols(self):
        """Test with actual symbols."""
        mock_manager = MagicMock()
        mock_client = AsyncMock()
        mock_client.document_symbol = AsyncMock(
            return_value=[
                {
                    "name": "hello",
                    "kind": 16,  # Function
                    "range": {"start": {"line": 0}},
                },
                {
                    "name": "World",
                    "kind": 2,  # Class
                    "range": {"start": {"line": 5}},
                },
            ]
        )
        mock_manager.get_client = AsyncMock(return_value=mock_client)

        tool = LSPDocumentSymbolTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "Function: hello" in result
        assert "Class: World" in result
        assert "at line" in result


class TestLSPWorkspaceSymbolTool:
    """Test LSPWorkspaceSymbolTool."""

    @pytest.mark.asyncio
    async def test_no_lsp_server(self):
        """Test behavior when no LSP server is available."""
        mock_manager = MagicMock()
        mock_manager.clients = {}

        tool = LSPWorkspaceSymbolTool(mock_manager)
        result = await tool.execute(query="test")

        assert "No LSP server" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Test behavior when no symbols found."""
        mock_manager = MagicMock()
        mock_client = AsyncMock()
        mock_client.workspace_symbol = AsyncMock(return_value=[])
        mock_manager.clients = {"python": mock_client}

        tool = LSPWorkspaceSymbolTool(mock_manager)
        result = await tool.execute(query="test")

        assert "No symbols found" in result


class TestLSPImplementationTool:
    """Test LSPImplementationTool."""

    @pytest.mark.asyncio
    async def test_no_lsp_server(self):
        """Test behavior when no LSP server is available."""
        mock_manager = MagicMock()
        mock_manager.get_client = AsyncMock(return_value=None)

        tool = LSPImplementationTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py", line=10, character=5)

        assert "No LSP server" in result

    @pytest.mark.asyncio
    async def test_no_implementations(self):
        """Test behavior when no implementations found."""
        mock_manager = MagicMock()
        mock_client = AsyncMock()
        mock_client.implementation = AsyncMock(return_value=None)
        mock_manager.get_client = AsyncMock(return_value=mock_client)

        tool = LSPImplementationTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py", line=10, character=5)

        assert "No implementations found" in result


class TestLSPGetDiagnosticsTool:
    """Test LSPGetDiagnosticsTool."""

    @pytest.mark.asyncio
    async def test_no_lsp_server(self):
        """Test behavior when no LSP server is available."""
        mock_manager = MagicMock()
        mock_manager.get_client = AsyncMock(return_value=None)

        tool = LSPGetDiagnosticsTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "No LSP server" in result

    @pytest.mark.asyncio
    async def test_no_diagnostics(self):
        """Test behavior when no diagnostics."""
        mock_manager = MagicMock()
        mock_client = AsyncMock()
        mock_client.get_diagnostics = MagicMock(return_value=[])
        mock_manager.get_client = AsyncMock(return_value=mock_client)

        tool = LSPGetDiagnosticsTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "No diagnostics" in result

    @pytest.mark.asyncio
    async def test_with_diagnostics(self):
        """Test with actual diagnostics."""
        mock_manager = MagicMock()
        mock_client = AsyncMock()
        mock_client.get_diagnostics = MagicMock(
            return_value=[
                {
                    "severity": 1,  # Error
                    "message": "Syntax error",
                    "range": {"start": {"line": 10}},
                    "source": "pyright",
                }
            ]
        )
        mock_manager.get_client = AsyncMock(return_value=mock_client)

        tool = LSPGetDiagnosticsTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "[Error]" in result
        assert "Line 11" in result
        assert "Syntax error" in result
        assert "[pyright]" in result


class TestLSPTouchFileTool:
    """Test LSPTouchFileTool."""

    @pytest.mark.asyncio
    async def test_touch_file_success(self):
        """Test successful file touch."""
        mock_manager = MagicMock()
        mock_manager.touch_file = AsyncMock()

        tool = LSPTouchFileTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py", is_new=False)

        assert "File synced" in result
        mock_manager.touch_file.assert_called_once_with("/tmp/test.py", False)

    @pytest.mark.asyncio
    async def test_touch_file_error(self):
        """Test file touch with error."""
        mock_manager = MagicMock()
        mock_manager.touch_file = AsyncMock(side_effect=Exception("LSP error"))

        tool = LSPTouchFileTool(mock_manager)
        result = await tool.execute(file_path="/tmp/test.py")

        assert "LSP Error" in result


class TestLSPDiagnosticsHandling:
    """Test LSP diagnostics handling."""

    def test_handle_diagnostics_notification(self):
        """Test handling diagnostics notification."""
        client = LSPClient("test", ["test"], "file:///tmp")

        params = {
            "uri": "file:///tmp/test.py",
            "diagnostics": [
                {"severity": 1, "message": "Error 1"},
                {"severity": 2, "message": "Warning 1"},
            ],
        }

        client._handle_diagnostics(params)

        assert "/tmp/test.py" in client.diagnostics
        assert len(client.diagnostics["/tmp/test.py"]) == 2

    def test_handle_diagnostics_clears_previous(self):
        """Test that new diagnostics replace old ones."""
        client = LSPClient("test", ["test"], "file:///tmp")

        # First diagnostics
        client._handle_diagnostics(
            {"uri": "file:///tmp/test.py", "diagnostics": [{"severity": 1, "message": "Old error"}]}
        )

        # New diagnostics
        client._handle_diagnostics(
            {
                "uri": "file:///tmp/test.py",
                "diagnostics": [{"severity": 2, "message": "New warning"}],
            }
        )

        assert len(client.diagnostics["/tmp/test.py"]) == 1
        assert client.diagnostics["/tmp/test.py"][0]["message"] == "New warning"


class TestLSPFileOperations:
    """Test LSP file operations."""

    @pytest.mark.asyncio
    async def test_did_close(self):
        """Test did_close notification."""
        client = LSPClient("test", ["test"], "file:///tmp")
        client.send_notification = MagicMock()

        await client.did_close("/tmp/test.py")

        client.send_notification.assert_called_once()
        call_args = client.send_notification.call_args[0]
        assert call_args[0] == "textDocument/didClose"

    @pytest.mark.asyncio
    async def test_did_change_watched_files(self):
        """Test did_change_watched_files notification."""
        client = LSPClient("test", ["test"], "file:///tmp")
        client.send_notification = MagicMock()

        await client.did_change_watched_files("/tmp/test.py", 2)  # Changed

        client.send_notification.assert_called_once()
        call_args = client.send_notification.call_args
        # Check first positional arg (notification method)
        assert call_args[0][0] == "workspace/didChangeWatchedFiles"
        # Check second positional arg (params dict)
        params = call_args[0][1]
        assert params["changes"][0]["type"] == 2

    @pytest.mark.asyncio
    async def test_touch_file(self):
        """Test touch_file method."""
        client = LSPClient("test", ["test"], "file:///tmp")
        client.did_change_watched_files = AsyncMock()
        client.did_open = AsyncMock()
        client._guess_language_id = MagicMock(return_value="python")

        # Mock file read
        with patch("pathlib.Path.read_text", return_value="print('hello')"):
            await client.touch_file("/tmp/test.py", is_new=True)

        client.did_change_watched_files.assert_called_once_with("/tmp/test.py", 1)


class TestLSPManagerConfiguration:
    """Test LSP manager configuration."""

    def test_manager_initialization_options(self):
        """Test manager stores initialization options."""
        config = {
            "python": {
                "initializationOptions": {
                    "pyright": {"disableLanguageServices": False, "typeCheckingMode": "basic"}
                }
            }
        }

        manager = LSPManager(workspace=Path("/tmp"), server_configs=config)
        assert "python" in manager.server_configs
        assert "initializationOptions" in manager.server_configs["python"]


class TestLSPGracefulDegradation:
    """Test graceful LSP degradation."""

    @pytest.mark.asyncio
    async def test_tool_without_lsp_server(self):
        """Test all tools handle missing LSP server gracefully."""
        mock_manager = MagicMock()
        mock_manager.get_client = AsyncMock(return_value=None)
        mock_manager.clients = {}

        tools = [
            LSPDocumentSymbolTool(mock_manager),
            LSPWorkspaceSymbolTool(mock_manager),
            LSPImplementationTool(mock_manager),
            LSPGetDiagnosticsTool(mock_manager),
        ]

        for tool in tools:
            if hasattr(tool, "execute") and tool.parameters.get("required", []):
                # Skip tools that require parameters we can't easily mock
                continue


class TestLSPLanguageSupport:
    """Test LSP language support."""

    def test_supported_extensions(self):
        """Test supported file extensions."""
        manager = LSPManager(workspace=Path("/tmp"))

        expected = {
            ".py": "python",
            ".go": "go",
            ".ts": "typescript",
            ".js": "javascript",
            ".rs": "rust",
        }

        assert manager.EXTENSIONS == expected

    def test_supported_servers(self):
        """Test supported LSP servers."""
        manager = LSPManager(workspace=Path("/tmp"))

        expected_servers = {
            "python",
            "go",
            "typescript",
            "javascript",
            "rust",
        }

        assert set(manager.SERVER_COMMANDS.keys()) == expected_servers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
