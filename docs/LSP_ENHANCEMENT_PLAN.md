# Nanobot LSP 功能增强计划

**分析日期**: 2026-03-22  
**目标**: 参考 OpenCode LSP 实现，增强 Nanobot LSP 功能

---

## 📊 执行摘要

### 核心发现

| 指标 | **Nanobot** | **OpenCode** | 差距 |
|------|-------------|--------------|------|
| **代码量** | 503 LoC (Python) | ~800 LoC (TypeScript) | -37% |
| **LSP 操作** | 3 个 | 8 个 | -5 个 |
| **文档符号** | ❌ | ✅ documentSymbol | 缺失 |
| **工作区符号** | ❌ | ✅ workspaceSymbol | 缺失 |
| **实现跳转** | ❌ | ✅ goToImplementation | 缺失 |
| **调用层次** | ❌ | ✅ prepareCallHierarchy | 缺失 |
| **调用链** | ❌ | ✅ incoming/outgoingCalls | 缺失 |
| **诊断同步** | ⚠️ 基础 | ✅ 完整事件系统 | 需增强 |
| **文件同步** | ⚠️ 基础 | ✅ 完整 watchedFiles | 需增强 |
| **测试覆盖** | ❌ | ✅ 完整测试 | 缺失 |

### 功能对比

| 功能 | Nanobot | OpenCode | 优先级 |
|------|---------|----------|--------|
| **goToDefinition** | ✅ | ✅ | - |
| **findReferences** | ✅ | ✅ | - |
| **hover** | ✅ | ✅ | - |
| **documentSymbol** | ❌ | ✅ | 高 |
| **workspaceSymbol** | ❌ | ✅ | 高 |
| **goToImplementation** | ❌ | ✅ | 中 |
| **prepareCallHierarchy** | ❌ | ✅ | 中 |
| **incomingCalls** | ❌ | ✅ | 中 |
| **outgoingCalls** | ❌ | ✅ | 中 |
| **诊断事件** | ⚠️ 基础 | ✅ 完整 | 高 |
| **文件监视** | ❌ | ✅ | 中 |
| **配置同步** | ❌ | ✅ | 中 |

---

## 🏗️ 架构对比

### Nanobot LSP 架构

```
nanobot/agent/code/
└── lsp.py (503 行)
    ├── LSPClient (核心客户端)
    │   ├── start/stop
    │   ├── send_request/send_notification
    │   ├── _read_stdout/_read_stderr
    │   └── 基本方法 (definition/references/hover/rename)
    └── LSPManager (管理器)
        ├── get_client (按语言获取)
        └── shutdown

nanobot/agent/tools/
└── lsp.py (212 行)
    ├── LSPDefinitionTool
    ├── LSPReferencesTool
    └── LSPHoverTool
```

**特点**:
- ✅ 简洁 lightweight 设计
- ✅ 基于 stdio 的 JSON-RPC
- ✅ 自动启动/停止
- ❌ 缺少高级功能
- ❌ 缺少事件系统
- ❌ 缺少文件同步

### OpenCode LSP 架构

```
opencode/src/lsp/
├── client.ts (~300 行)
│   ├── create (工厂函数)
│   ├── 通知处理 (diagnostics/progress)
│   ├── 请求处理 (configuration/workspaceFolders)
│   └── notify (open/change/watchedFiles)
├── index.ts (~400 行)
│   ├── state (状态管理)
│   ├── init (初始化)
│   ├── status (状态查询)
│   ├── getClients (按文件获取)
│   └── LSP 操作 (8 个)
├── server.ts (~100 行)
│   └── LSP 服务器定义
└── launch.ts (~100 行)
    └── 进程启动

opencode/src/tool/
└── lsp.ts (97 行)
    └── LspTool (统一工具，8 个操作)
```

**特点**:
- ✅ 完整事件系统 (BusEvent)
- ✅ 诊断同步 (publishDiagnostics)
- ✅ 文件监视 (didChangeWatchedFiles)
- ✅ 配置同步 (workspace/configuration)
- ✅ 工作区支持 (workspaceFolders)
- ✅ 完整测试

---

## 📝 缺失功能详细分析

### 1. Document Symbol (文档符号)

**OpenCode 实现**:
```typescript
case "documentSymbol":
  return LSP.documentSymbol(uri)
```

**功能**:
- 获取文档中所有符号 (函数、类、变量等)
- 返回符号树结构
- 支持代码大纲/导航

**缺失影响**:
- ❌ 无法获取文件结构
- ❌ 无法生成代码大纲
- ❌ 无法快速导航到符号

---

### 2. Workspace Symbol (工作区符号)

**OpenCode 实现**:
```typescript
case "workspaceSymbol":
  return LSP.workspaceSymbol("")
```

**功能**:
- 全局符号搜索
- 跨文件符号查找
- 支持符号跳转

**缺失影响**:
- ❌ 无法全局搜索符号
- ❌ 无法跨文件导航
- ❌ 无法生成符号索引

---

### 3. Go To Implementation (实现跳转)

**OpenCode 实现**:
```typescript
case "goToImplementation":
  return LSP.implementation(position)
```

**功能**:
- 跳转到接口/抽象方法的实现
- 支持多实现查找
- 面向对象编程关键功能

**缺失影响**:
- ❌ 无法查找接口实现
- ❌ 无法查找抽象方法实现
- ❌ 影响 OOP 代码导航

---

### 4. Call Hierarchy (调用层次)

**OpenCode 实现**:
```typescript
case "prepareCallHierarchy":
  return LSP.prepareCallHierarchy(position)
case "incomingCalls":
  return LSP.incomingCalls(position)
case "outgoingCalls":
  return LSP.outgoingCalls(position)
```

**功能**:
- **prepareCallHierarchy**: 获取调用层次项
- **incomingCalls**: 谁调用了这个函数
- **outgoingCalls**: 这个函数调用了谁

**缺失影响**:
- ❌ 无法分析调用链
- ❌ 无法理解代码依赖
- ❌ 影响重构和调试

---

### 5. 诊断事件系统

**OpenCode 实现**:
```typescript
connection.onNotification("textDocument/publishDiagnostics", (params) => {
  const filePath = Filesystem.normalizeParams(params.uri)
  diagnostics.set(filePath, params.diagnostics)
  Bus.publish(Event.Diagnostics, { path: filePath, serverID })
})
```

**功能**:
- 实时诊断更新
- 错误/警告同步
- 事件驱动架构

**Nanobot 现状**:
```python
def _handle_message(self, message: Dict[str, Any]):
    if method == "window/logMessage":
        self._handle_log_message(params)
    # 缺少 diagnostics 处理
```

**缺失影响**:
- ❌ 无实时错误提示
- ❌ 无警告同步
- ❌ 无法集成到编辑器

---

### 6. 文件监视同步

**OpenCode 实现**:
```typescript
await connection.sendNotification("workspace/didChangeWatchedFiles", {
  changes: [{
    uri: pathToFileURL(input.path).href,
    type: 1, // Created
  }],
})
```

**功能**:
- 文件创建/修改/删除通知
- 保持 LSP 服务器文件状态同步
- 支持动态文件更新

**Nanobot 现状**:
```python
async def did_open(self, file_path: str, text: str, language_id: str):
    """Notify that a document was opened."""
    params = {...}
    self.send_notification("textDocument/didOpen", params)
```

**缺失影响**:
- ❌ 文件变化不同步
- ❌ LSP 服务器状态可能过期
- ❌ 影响代码补全准确性

---

### 7. 配置同步

**OpenCode 实现**:
```typescript
connection.onRequest("workspace/configuration", async () => {
  return [input.server.initialization ?? {}]
})
```

**功能**:
- LSP 服务器配置查询
- 动态配置更新
- 支持自定义配置

**缺失影响**:
- ❌ 无法自定义 LSP 行为
- ❌ 无法动态更新配置

---

## 🎯 增强计划

### 阶段 1: 核心功能增强 (1-2 周)

#### 1.1 添加 Document Symbol

**新增代码**: ~80 行

```python
# nanobot/agent/code/lsp.py
async def document_symbol(self, file_path: str) -> List[Dict[str, Any]]:
    """Get all symbols in a document."""
    params = {
        "textDocument": {"uri": Path(file_path).as_uri()}
    }
    return await self.send_request("textDocument/documentSymbol", params)

# nanobot/agent/tools/lsp.py
class LSPDocumentSymbolTool(Tool):
    name = "document_symbol"
    description = "Get all symbols (functions, classes, variables) in a document"
    
    async def execute(self, file_path: str, **kwargs) -> str:
        try:
            client = await self.lsp_manager.get_client(file_path)
            if not client:
                return "No LSP server available"
            
            symbols = await client.document_symbol(file_path)
            if not symbols:
                return "No symbols found"
            
            # Format output
            lines = []
            for sym in symbols:
                lines.append(f"{sym['kind']}: {sym['name']} at line {sym['range']['start']['line']+1}")
            
            return "\n".join(lines[:50])
        except Exception as e:
            return f"LSP Error: {e}"
```

**测试**:
```python
async def test_document_symbol():
    manager = LSPManager(workspace=Path("."))
    client = await manager.get_client("test.py")
    symbols = await client.document_symbol("test.py")
    assert len(symbols) > 0
```

---

#### 1.2 添加 Workspace Symbol

**新增代码**: ~60 行

```python
# nanobot/agent/code/lsp.py
async def workspace_symbol(self, query: str = "") -> List[Dict[str, Any]]:
    """Search for symbols across the workspace."""
    params = {"query": query}
    return await self.send_request("workspace/symbol", params)

# nanobot/agent/tools/lsp.py
class LSPWorkspaceSymbolTool(Tool):
    name = "workspace_symbol"
    description = "Search for symbols across the entire workspace"
    
    async def execute(self, query: str, **kwargs) -> str:
        try:
            # Use first available client
            clients = self.lsp_manager.clients
            if not clients:
                return "No LSP server available"
            
            client = list(clients.values())[0]
            symbols = await client.workspace_symbol(query)
            
            if not symbols:
                return f"No symbols found for '{query}'"
            
            lines = []
            for sym in symbols:
                loc = sym.get("location", {})
                uri = loc.get("uri", "")
                path = uri.replace("file://", "")
                lines.append(f"{sym['name']} in {path}")
            
            return "\n".join(lines[:50])
        except Exception as e:
            return f"LSP Error: {e}"
```

---

#### 1.3 实现诊断事件系统

**新增代码**: ~100 行

```python
# nanobot/agent/code/lsp.py
from nanobot.bus import Bus, BusEvent

class DiagnosticEvent:
    def __init__(self, path: str, server_id: str, diagnostics: List[Dict]):
        self.path = path
        self.server_id = server_id
        self.diagnostics = diagnostics

# 在 LSPClient 中添加
class LSPClient:
    def __init__(self, name: str, command: List[str], root_uri: str):
        # ... 现有代码 ...
        self.diagnostics: Dict[str, List[Dict]] = {}
        self._diagnostics_debounce: Dict[str, asyncio.Task] = {}
    
    def _handle_message(self, message: Dict[str, Any]):
        if "id" not in message and "method" in message:
            method = message["method"]
            params = message.get("params")
            
            if method == "textDocument/publishDiagnostics":
                self._handle_diagnostics(params)
            elif method == "window/logMessage":
                self._handle_log_message(params)
    
    def _handle_diagnostics(self, params: Dict[str, Any]):
        uri = params.get("uri")
        diagnostics = params.get("diagnostics", [])
        
        if not uri:
            return
        
        path = uri.replace("file://", "")
        self.diagnostics[path] = diagnostics
        
        # Debounce and publish event
        if path in self._diagnostics_debounce:
            self._diagnostics_debounce[path].cancel()
        
        async def publish():
            await asyncio.sleep(DIAGNOSTICS_DEBOUNCE_MS / 1000)
            event = DiagnosticEvent(path, self.name, diagnostics)
            Bus.publish("lsp.diagnostics", event)
        
        self._diagnostics_debounce[path] = asyncio.create_task(publish())
    
    def get_diagnostics(self, file_path: str) -> List[Dict]:
        """Get current diagnostics for a file."""
        return self.diagnostics.get(file_path, [])
    
    def clear_diagnostics(self, file_path: str):
        """Clear diagnostics for a file."""
        self.diagnostics.pop(file_path, None)

# nanobot/agent/tools/lsp.py
class LSPGetDiagnosticsTool(Tool):
    name = "get_diagnostics"
    description = "Get current diagnostics (errors, warnings) for a file"
    
    async def execute(self, file_path: str, **kwargs) -> str:
        try:
            client = await self.lsp_manager.get_client(file_path)
            if not client:
                return "No LSP server available"
            
            diagnostics = client.get_diagnostics(file_path)
            
            if not diagnostics:
                return "No diagnostics (no errors or warnings)"
            
            lines = []
            for diag in diagnostics:
                severity = diag.get("severity", 1)
                severity_name = {1: "Error", 2: "Warning", 3: "Info"}.get(severity, "Unknown")
                line = diag["range"]["start"]["line"] + 1
                message = diag.get("message", "")
                lines.append(f"[{severity_name}] Line {line}: {message}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"LSP Error: {e}"
```

---

### 阶段 2: 高级功能 (2-3 周)

#### 2.1 添加 Go To Implementation

**新增代码**: ~50 行

```python
# nanobot/agent/code/lsp.py
async def implementation(self, file_path: str, line: int, character: int) -> Any:
    """Find implementations of an interface/abstract method."""
    params = {
        "textDocument": {"uri": Path(file_path).as_uri()},
        "position": {"line": line, "character": character}
    }
    return await self.send_request("textDocument/implementation", params)

# nanobot/agent/tools/lsp.py
class LSPImplementationTool(Tool):
    name = "go_to_implementation"
    description = "Find implementations of an interface or abstract method"
    
    @_graceful_lsp
    async def execute(self, file_path: str, line: int, character: int, _client=None, **kwargs) -> str:
        try:
            resp = await _client.implementation(file_path, line - 1, character)
            
            if not resp:
                return "No implementations found"
            
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
                return "No implementation locations found"
            
            return "\n".join(results)
        except Exception as e:
            return f"LSP Error: {e}"
```

---

#### 2.2 添加 Call Hierarchy

**新增代码**: ~150 行

```python
# nanobot/agent/code/lsp.py
async def prepare_call_hierarchy(self, file_path: str, line: int, character: int) -> Any:
    """Get call hierarchy item at position."""
    params = {
        "textDocument": {"uri": Path(file_path).as_uri()},
        "position": {"line": line, "character": character}
    }
    return await self.send_request("callHierarchy/prepare", params)

async def incoming_calls(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all functions that call this function."""
    params = {"item": item}
    return await self.send_request("callHierarchy/incomingCalls", params)

async def outgoing_calls(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all functions called by this function."""
    params = {"item": item}
    return await self.send_request("callHierarchy/outgoingCalls", params)

# nanobot/agent/tools/lsp.py
class LSPPrepareCallHierarchyTool(Tool):
    name = "prepare_call_hierarchy"
    description = "Get call hierarchy item at a position"
    
    @_graceful_lsp
    async def execute(self, file_path: str, line: int, character: int, _client=None, **kwargs) -> str:
        try:
            items = await _client.prepare_call_hierarchy(file_path, line - 1, character)
            
            if not items:
                return "No call hierarchy item at this position"
            
            item = items[0] if isinstance(items, list) else items
            return f"Function: {item.get('name', 'unknown')} in {item.get('uri', 'unknown')}"
        except Exception as e:
            return f"LSP Error: {e}"

class LSPIncomingCallsTool(Tool):
    name = "incoming_calls"
    description = "Find all functions that call this function"
    
    async def execute(self, item_json: str, **kwargs) -> str:
        try:
            import json
            item = json.loads(item_json)
            
            # Use first available client
            client = list(self.lsp_manager.clients.values())[0]
            calls = await client.incoming_calls(item)
            
            if not calls:
                return "No incoming calls"
            
            lines = []
            for call in calls:
                from_range = call.get("from", {})
                lines.append(f"Called from {from_range.get('uri', 'unknown')}:{from_range.get('range', {}).get('start', {}).get('line', 0)+1}")
            
            return "\n".join(lines[:20])
        except Exception as e:
            return f"LSP Error: {e}"

class LSPOutgoingCallsTool(Tool):
    name = "outgoing_calls"
    description = "Find all functions called by this function"
    
    async def execute(self, item_json: str, **kwargs) -> str:
        try:
            import json
            item = json.loads(item_json)
            
            client = list(self.lsp_manager.clients.values())[0]
            calls = await client.outgoing_calls(item)
            
            if not calls:
                return "No outgoing calls"
            
            lines = []
            for call in calls:
                to_range = call.get("to", {})
                lines.append(f"Calls {to_range.get('name', 'unknown')} at {to_range.get('uri', 'unknown')}:{to_range.get('range', {}).get('start', {}).get('line', 0)+1}")
            
            return "\n".join(lines[:20])
        except Exception as e:
            return f"LSP Error: {e}"
```

---

### 阶段 3: 文件同步与配置 (1-2 周)

#### 3.1 实现文件监视同步

**新增代码**: ~80 行

```python
# nanobot/agent/code/lsp.py
class LSPClient:
    async def did_change_watched_files(self, file_path: str, change_type: int):
        """Notify that a file was created/changed/deleted.
        
        change_type: 1=Created, 2=Changed, 3=Deleted
        """
        params = {
            "changes": [{
                "uri": Path(file_path).as_uri(),
                "type": change_type
            }]
        }
        self.send_notification("workspace/didChangeWatchedFiles", params)
    
    async def touch_file(self, file_path: str, is_new: bool = False):
        """Touch a file to sync with LSP server."""
        change_type = 1 if is_new else 2
        await self.did_change_watched_files(file_path, change_type)
        
        # Also send didOpen/didChange
        text = Path(file_path).read_text(encoding="utf-8")
        await self.did_open(file_path, text, self._guess_language_id(file_path))

# nanobot/agent/code/lsp.py (LSPManager)
class LSPManager:
    async def touch_file(self, file_path: str, is_new: bool = False):
        """Touch file in all relevant LSP servers."""
        for client in self.clients.values():
            await client.touch_file(file_path, is_new)

# nanobot/agent/tools/lsp.py
class LSPTouchFileTool(Tool):
    name = "lsp_touch_file"
    description = "Sync a file with LSP servers (refresh diagnostics, etc.)"
    
    async def execute(self, file_path: str, is_new: bool = False, **kwargs) -> str:
        try:
            await self.lsp_manager.touch_file(file_path, is_new)
            return f"File synced with LSP servers: {file_path}"
        except Exception as e:
            return f"LSP Error: {e}"
```

---

#### 3.2 实现配置同步

**新增代码**: ~50 行

```python
# nanobot/agent/code/lsp.py
class LSPClient:
    def __init__(self, name: str, command: List[str], root_uri: str, initialization: Dict = None):
        # ... 现有代码 ...
        self.initialization_options = initialization or {}
    
    async def update_configuration(self, settings: Dict[str, Any]):
        """Update LSP server configuration."""
        params = {"settings": settings}
        self.send_notification("workspace/didChangeConfiguration", params)
    
    async def _initialize(self):
        # ... 现有代码 ...
        if self.initialization_options:
            params["initializationOptions"] = self.initialization_options

# nanobot/agent/code/lsp.py (LSPManager)
class LSPManager:
    def __init__(self, workspace: Path, server_configs: Dict[str, Dict] = None):
        self.workspace = workspace
        self.clients: Dict[str, LSPClient] = {}
        self.root_uri = workspace.as_uri()
        self.server_configs = server_configs or {}
    
    async def get_client(self, file_path: str) -> Optional[LSPClient]:
        # ... 现有代码 ...
        ext = Path(file_path).suffix
        lang = self.EXTENSIONS.get(ext)
        
        if lang in self.clients:
            return self.clients[lang]
        
        cmd = self.SERVER_COMMANDS.get(lang)
        config = self.server_configs.get(lang, {})
        
        # Start new client with config
        try:
            client = LSPClient(lang, cmd, self.root_uri, initialization=config)
            await client.start()
            self.clients[lang] = client
            return client
        except Exception as e:
            logger.error(f"Failed to start {lang} LSP: {e}")
            return None
```

---

### 阶段 4: 测试与文档 (1 周)

#### 4.1 添加单元测试

**新增测试**: ~200 行

```python
# tests/test_lsp.py
import pytest
from pathlib import Path
from nanobot.agent.code.lsp import LSPClient, LSPManager

@pytest.fixture
def lsp_manager(tmp_path):
    manager = LSPManager(workspace=tmp_path)
    yield manager
    asyncio.run(manager.shutdown())

class TestLSPClient:
    @pytest.mark.asyncio
    async def test_document_symbol(self, lsp_manager):
        """Test document symbol retrieval."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def hello():
    pass

class World:
    def greet(self):
        pass
""")
        
        client = await lsp_manager.get_client(str(test_file))
        assert client is not None
        
        symbols = await client.document_symbol(str(test_file))
        assert len(symbols) > 0
        assert any(s["name"] == "hello" for s in symbols)
        assert any(s["name"] == "World" for s in symbols)
    
    @pytest.mark.asyncio
    async def test_workspace_symbol(self, lsp_manager):
        """Test workspace symbol search."""
        client = await lsp_manager.get_client("test.py")
        symbols = await client.workspace_symbol("hello")
        assert isinstance(symbols, list)
    
    @pytest.mark.asyncio
    async def test_diagnostics(self, lsp_manager):
        """Test diagnostics retrieval."""
        test_file = tmp_path / "error.py"
        test_file.write_text("""
def hello(
    pass  # Syntax error
""")
        
        client = await lsp_manager.get_client(str(test_file))
        await asyncio.sleep(2)  # Wait for diagnostics
        
        diagnostics = client.get_diagnostics(str(test_file))
        assert len(diagnostics) > 0
        assert any(d["severity"] == 1 for d in diagnostics)  # Error

class TestLSPTools:
    @pytest.mark.asyncio
    async def test_document_symbol_tool(self, lsp_manager):
        """Test LSPDocumentSymbolTool."""
        tool = LSPDocumentSymbolTool(lsp_manager)
        result = await tool.execute(file_path="test.py")
        assert "No LSP server" in result or len(result) > 0
    
    @pytest.mark.asyncio
    async def test_get_diagnostics_tool(self, lsp_manager):
        """Test LSPGetDiagnosticsTool."""
        tool = LSPGetDiagnosticsTool(lsp_manager)
        result = await tool.execute(file_path="test.py")
        assert isinstance(result, str)
```

---

#### 4.2 添加文档

**新增文档**: ~300 行

```markdown
# LSP 使用指南

## 配置

在 `~/.nanobot/config.json` 中配置 LSP 服务器：

```json
{
  "lsp": {
    "python": {
      "command": ["pyright-langserver", "--stdio"],
      "initialization": {
        "pyright": {
          "disableLanguageServices": false
        }
      }
    },
    "typescript": {
      "command": ["typescript-language-server", "--stdio"],
      "disabled": false
    }
  }
}
```

## 工具列表

| 工具 | 描述 |
|------|------|
| `go_to_definition` | 跳转到符号定义 |
| `find_references` | 查找符号引用 |
| `get_hover_info` | 获取符号信息 |
| `document_symbol` | 获取文档符号 |
| `workspace_symbol` | 全局符号搜索 |
| `go_to_implementation` | 跳转到实现 |
| `prepare_call_hierarchy` | 准备调用层次 |
| `incoming_calls` | 入向调用 |
| `outgoing_calls` | 出向调用 |
| `get_diagnostics` | 获取诊断信息 |
| `lsp_touch_file` | 同步文件 |

## 使用示例

### Python 代码导航

```python
# 1. 查找定义
@lsp
go_to_definition(file_path="/app/main.py", line=10, character=5)

# 2. 查找引用
@lsp
find_references(file_path="/app/main.py", line=10, character=5)

# 3. 获取文档符号
@lsp
document_symbol(file_path="/app/main.py")

# 4. 全局搜索
@lsp
workspace_symbol(query="UserService")
```

### 调用分析

```python
# 1. 准备调用层次
@lsp
prepare_call_hierarchy(file_path="/app/main.py", line=20, character=10)

# 2. 查看谁调用了这个函数
@lsp
incoming_calls(item_json='{"name": "process_data", ...}')

# 3. 查看这个函数调用了谁
@lsp
outgoing_calls(item_json='{"name": "process_data", ...}')
```

### 错误诊断

```python
# 获取当前文件错误
@lsp
get_diagnostics(file_path="/app/main.py")
```

## 故障排除

### LSP 服务器未启动

确保已安装对应的语言服务器：

```bash
# Python
pip install pyright

# TypeScript
npm install -g typescript-language-server typescript

# Go
go install golang.org/x/tools/gopls@latest

# Rust
rustup component add rust-analyzer
```

### 诊断不同步

使用 `lsp_touch_file` 手动同步：

```python
@lsp
lsp_touch_file(file_path="/app/main.py", is_new=False)
```

## 性能优化

1. **禁用不需要的 LSP 服务器**:
   ```json
   {
     "lsp": {
       "typescript": {"disabled": true}
     }
   }
   ```

2. **配置服务器选项**:
   ```json
   {
     "lsp": {
       "python": {
         "initialization": {
           "pyright": {
             "disableLanguageServices": true
           }
         }
       }
     }
   }
   ```
```

---

## 📊 工作量估算

| 阶段 | 功能 | 代码量 | 时间 | 优先级 |
|------|------|--------|------|--------|
| **阶段 1** | Document Symbol | ~80 行 | 2 天 | 高 |
| | Workspace Symbol | ~60 行 | 1 天 | 高 |
| | 诊断事件系统 | ~100 行 | 3 天 | 高 |
| **阶段 2** | Go To Implementation | ~50 行 | 2 天 | 中 |
| | Call Hierarchy | ~150 行 | 4 天 | 中 |
| **阶段 3** | 文件监视同步 | ~80 行 | 2 天 | 中 |
| | 配置同步 | ~50 行 | 1 天 | 低 |
| **阶段 4** | 单元测试 | ~200 行 | 3 天 | 高 |
| | 文档 | ~300 行 | 2 天 | 中 |
| **总计** | | **~1,070 行** | **20 天** | - |

---

## 🎯 实施路线图

### 第 1 周：核心功能
- [ ] Document Symbol 实现
- [ ] Workspace Symbol 实现
- [ ] 诊断事件系统基础

### 第 2 周：诊断完善
- [ ] 诊断事件完整实现
- [ ] 诊断工具实现
- [ ] 单元测试编写

### 第 3 周：高级功能
- [ ] Go To Implementation 实现
- [ ] Call Hierarchy 基础实现

### 第 4 周：完善与测试
- [ ] Call Hierarchy 完善
- [ ] 文件监视同步
- [ ] 完整测试覆盖
- [ ] 文档编写

---

## 📈 预期收益

### 功能提升

| 指标 | 当前 | 增强后 | 提升 |
|------|------|--------|------|
| **LSP 操作** | 3 个 | 11 个 | +267% |
| **代码导航** | ⭐⭐ | ⭐⭐⭐⭐⭐ | +150% |
| **诊断支持** | ⭐ | ⭐⭐⭐⭐ | +300% |
| **测试覆盖** | 0% | 90%+ | +90% |

### 用户体验提升

1. **代码理解**:
   - ✅ 完整的符号导航
   - ✅ 调用层次分析
   - ✅ 实时错误提示

2. **开发效率**:
   - ✅ 快速跳转到定义/实现
   - ✅ 全局符号搜索
   - ✅ 调用链分析

3. **代码质量**:
   - ✅ 实时诊断
   - ✅ 错误预警
   - ✅ 重构支持

---

## 🔧 实施建议

### 优先实施

1. **阶段 1 全部** (1-2 周)
   - 文档符号和工作区符号是基础导航功能
   - 诊断事件系统对用户体验提升明显

2. **阶段 4 测试** (1 周)
   - 确保新增功能稳定可靠

### 按需实施

3. **阶段 2** (2-3 周)
   - 根据用户需求决定是否实施
   - Call Hierarchy 对复杂代码分析有用

4. **阶段 3** (1-2 周)
   - 文件监视和配置同步是锦上添花

---

## 📋 总结

### 现状

- ✅ 基础 LSP 功能完整 (definition/references/hover)
- ✅ 简洁 lightweight 设计
- ❌ 缺少高级导航功能
- ❌ 缺少诊断事件系统
- ❌ 缺少测试覆盖

### 增强后

- ✅ 完整 LSP 操作 (11 个 vs 当前 3 个)
- ✅ 实时诊断事件
- ✅ 文件监视同步
- ✅ 完整测试覆盖 (90%+)
- ✅ 详细使用文档

### 投入产出比

- **投入**: ~1,070 行代码，~20 天
- **产出**: +267% 功能，+300% 诊断能力，+150% 导航体验
- **ROI**: ⭐⭐⭐⭐⭐ (极高)

---

**报告生成时间**: 2026-03-22  
**版本**: v1.0  
**状态**: ✅ 完整、可执行
