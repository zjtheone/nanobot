# Commit 差异分析报告

## cab901b → b6891c2 功能演进分析

### 概述

从 `cab901b`（Merge PR #1228）演进到 `b6891c2`（feat: improve a），这是一次大规模的功能扩展。总计修改 **175 个文件**，新增约 **39,159 行**，删除约 **1,774 行**，净增约 **37,385 行**代码。中间经历约 29 个 commit，涵盖多 Agent 通信、代码智能、向量记忆、Web Console、Gateway 等多个子系统的构建。

### 中间 Commit 链

```
cab901b  Merge PR #1228: fix(web): use self.api_key instead of undefined api_key
   ↓ (29 commits)
b6891c2  feat: improve a
```

关键里程碑 commit：
- `909fa68` feat: init Agent to Agent feature
- `a1daece` feat: improve memory with vector, sqlite and so on
- `8789a5a` feat: upgrade EditFileTool to Aider-style block and add self-healing loop
- `0d88b6c` feat: add webconsole base on streamlit
- `a2f1bd5` feat: add markdown docs
- `70d5244` feat: improve agent teams
- `9dfcea7` feat: inprove agent teams

---

## 一、全新构建的模块（约 120+ 文件）

### 1. Agent-to-Agent (A2A) 通信系统

| 文件 | 说明 |
|------|------|
| `nanobot/agent/a2a/__init__.py` | A2A 模块入口 |
| `nanobot/agent/a2a/queue.py` | A2A 消息队列 |
| `nanobot/agent/a2a/router.py` | A2A 路由器 |
| `nanobot/agent/a2a/types.py` | A2A 类型定义（AgentMessage、MessagePriority 等） |
| `nanobot/agent/a2a_flow.py` | A2A 流程控制 |
| `nanobot/agent/announce_chain.py` | 子 agent 结果通知链，支持 Orchestrator 模式下的结果聚合 |
| `nanobot/agent/pingpong_dialog.py` | Agent 间乒乓对话（自动多轮交互） |
| `nanobot/agent/policy_engine.py` | A2A 策略引擎（allow/deny 列表、深度限制） |
| `nanobot/session/keys.py` | 结构化 SessionKey 对象（agent_id、session_type） |
| `nanobot/agent/tools/broadcast.py` | 广播工具 |
| `nanobot/agent/tools/orchestrator.py` | 编排器工具（DecomposeAndSpawnTool、AggregateResultsTool） |

### 2. Agent Team 系统

| 文件 | 说明 |
|------|------|
| `nanobot/agent/team/__init__.py` | Team 模块入口 |
| `nanobot/agent/team/manager.py` | 团队管理器 |
| `nanobot/agent/team/budget.py` | 预算控制 |
| `nanobot/agent/team/errors.py` | 错误处理（可重试错误判断、SubagentError） |
| `nanobot/agent/team/orchestrator.py` | 团队编排器 |
| `nanobot/cli/teams.py` | 团队 CLI 命令 |
| `nanobot/skills/orchestrator.md` | 编排器 skill 定义 |

### 3. 代码智能系统

| 文件 | 说明 |
|------|------|
| `nanobot/agent/code/repomap.py` | 仓库地图（项目结构概览） |
| `nanobot/agent/code/folding.py` | 代码折叠引擎（智能上下文压缩） |
| `nanobot/agent/code/symbol_index.py` | 符号索引 |
| `nanobot/agent/code/lsp.py` | LSP 管理器（语言服务器协议集成） |
| `nanobot/agent/tools/code.py` | ReadFileMapTool |
| `nanobot/agent/tools/code_focused.py` | ReadFileFocusedTool（焦点模式读取） |
| `nanobot/agent/tools/lsp.py` | LSP 工具（定义跳转、引用查找、悬停信息） |
| `nanobot/agent/tools/search.py` | 搜索工具 |
| `nanobot/agent/tools/search_semantic.py` | 语义搜索工具（FindDefinitions、FindReferences） |
| `nanobot/agent/tools/refactor.py` | 重构工具（RefactorRename） |

### 4. 向量记忆系统

| 文件 | 说明 |
|------|------|
| `nanobot/agent/memory_vector.py` | 向量记忆适配器（1049 行，支持 sqlite-vec 后端） |
| `nanobot/agent/memory_processing/query_parser.py` | 查询解析器 |
| `nanobot/agent/memory_processing/query_types.py` | 查询类型定义 |
| `nanobot/agent/memory_processing/reranker.py` | 重排序器 |
| `nanobot/agent/memory_processing/cross_encoder_wrapper.py` | 交叉编码器封装 |
| `nanobot/agent/cross_encoder_wrapper.py` | 交叉编码器 |
| `nanobot/agent/reranker.py` | 重排序器 |
| `nanobot/agent/tools/memory_search.py` | 语义记忆搜索工具 |

### 5. 基础设施增强模块

| 文件 | 说明 |
|------|------|
| `nanobot/agent/checkpoint.py` | 文件检查点/快照系统（支持撤销） |
| `nanobot/agent/tools/undo.py` | 撤销工具（UndoTool、ListChangesTool） |
| `nanobot/agent/tools/batch_edit.py` | 批量编辑工具 |
| `nanobot/agent/tools/git.py` | Git 工具集（Status、Diff、Commit、Log、Checkout） |
| `nanobot/agent/compaction.py` | 对话压缩器（上下文窗口管理） |
| `nanobot/agent/hooks.py` | Hook 注册系统 |
| `nanobot/agent/metrics.py` | 指标追踪器 |
| `nanobot/agent/permissions.py` | 权限门控（auto/confirm_writes/confirm_all/yolo） |
| `nanobot/agent/planner.py` | 规划器 |
| `nanobot/agent/verify.py` | 自动验证（代码修改后自动 build/test） |
| `nanobot/agent/file_watcher.py` | 文件监视器 |
| `nanobot/agent/diagnostics/` | 诊断解析器和工具 |
| `nanobot/agent/tools/terminal.py` | 持久 Shell 工具（有状态会话） |
| `nanobot/agent/tools/planner.py` | 规划工具 |
| `nanobot/agent/tools/metrics.py` | 指标查询工具 |

### 6. 终端/沙箱系统

| 文件 | 说明 |
|------|------|
| `nanobot/agent/terminal/docker_session.py` | Docker 沙箱会话 |
| `nanobot/agent/terminal/session.py` | 持久 Shell 会话 |

### 7. Gateway 系统

| 文件 | 说明 |
|------|------|
| `nanobot/gateway/__init__.py` | Gateway 模块入口 |
| `nanobot/gateway/http_server.py` | HTTP 服务器 |
| `nanobot/gateway/manager.py` | Gateway 管理器（多 agent 路由） |
| `nanobot/gateway/router.py` | 消息路由器 |
| `nanobot/config/agent_loader.py` | Agent 配置加载器 |

### 8. MCP 独立模块

| 文件 | 说明 |
|------|------|
| `nanobot/mcp/__init__.py` | MCP 模块入口 |
| `nanobot/mcp/client.py` | MCP 客户端 |
| `nanobot/mcp/config.py` | MCP 配置 |
| `nanobot/mcp/registry.py` | MCP 注册表（从 loop.py 内联逻辑提取为独立模块） |

### 9. Web Console

| 文件 | 说明 |
|------|------|
| `web_console/app.py` | 基于 Streamlit 的 Web 应用 |
| `web_console/agent_bridge.py` | Agent 桥接层 |
| `web_console/chat_interface.py` | 聊天界面 |
| `web_console/session_manager.py` | 会话管理 |
| `web_console/config.py` | 配置 |
| `web_console/styles.py` | 样式 |
| `web_console/subagent_monitor.py` | 子 agent 监控 |

### 10. CLI 子命令

| 文件 | 说明 |
|------|------|
| `nanobot/cli/sessions.py` | 会话管理 CLI（list、show） |
| `nanobot/cli/subagents.py` | 子 agent CLI |
| `nanobot/cli/progress.py` | 进度显示 |

### 11. 文档与测试

- `docs/` — 约 40 个文档文件，涵盖 A2A 指南、团队配置、Gateway 使用、Web Console 实现、安全策略等
- `tests/` — 约 20 个测试文件，覆盖 A2A 通信、Gateway 路由、编排器、记忆向量、预算控制等
- 根目录 4 个 `AGENT_TEAM_*.md` 规划文档

---

## 二、核心模块的重构与增强

### 1. `nanobot/agent/loop.py`（核心 Agent 循环）

这是变更量最大的文件，从精简的非流式循环演进为功能完备的 Agent 引擎。

**新增能力：**
- 新增 `stream_chat` 流式处理，支持逐 chunk 输出文本和 thinking 内容
- 新增 `agent_id` 概念，支持多 agent 身份标识
- 新增参数：`frequency_penalty`、`thinking_budget`、`sandbox`、`permission_mode`、`auto_verify`、`auto_verify_command`、`context_window`、`memory_search_config`、`agents_config`
- 新增全套回调函数：`on_tool_call`、`on_thinking`、`on_iteration`、`on_tool_start`、`on_status`、`on_plan_progress`
- 新增 CheckpointManager、PermissionGate、MetricsTracker、ConversationCompactor、HookRegistry、MCPManager、LSPManager 的初始化
- 新增 Docker 沙箱支持（根据 `sandbox` 配置选择 DockerSession 或 ShellSession）
- 新增 A2A 通信方法：`send_request`、`send_response`、`send_notification`、`broadcast`、`receive_message`、`wait_for_workers`、`get_worker_results`
- 新增 `_consolidate_memory()` 方法，使用 LLM 进行对话摘要和记忆更新
- 新增 `_auto_verify()` 方法，代码修改后自动运行 build/test

**工具注册扩展：**
- 从约 10 个基础工具扩展到约 30 个，新增 git、undo、batch_edit、code（RepoMap）、code_focused（Folding）、lsp（定义/引用/悬停）、refactor、metrics、search_semantic、planner、terminal（持久 Shell）等

**默认参数调整：**

| 参数 | cab901b | b6891c2 |
|------|---------|---------|
| temperature | 0.1 | 0.7 |
| max_iterations | 40 | 20 |
| max_tokens | 4096 | 8192 |
| memory_window | 100 | 50 |

**移除：**
- 移除了 `_TOOL_RESULT_MAX_CHARS = 500` 截断限制
- 移除了 `_consolidation_tasks`、`_consolidation_locks`、`_active_tasks`、`_processing_lock` 等并发控制（简化为 `_consolidating` set）
- 移除了 `channels_config` 参数

### 2. `nanobot/agent/context.py`（上下文构建器）

**新增能力：**
- 新增 RepoMap、FoldingEngine、SymbolIndex、ContextManager 的初始化
- 新增项目指令文件加载（CLAUDE.md、NANOBOT.md、.nanobot.md、CONTRIBUTING.md），向上遍历 5 层目录查找项目根
- 新增仓库地图注入到系统提示词
- 新增 `plan_context` 参数支持
- 新增 "repair" 作为默认 skill
- 系统提示词大幅扩展：新增详细的编码方法论（Understand → Plan → Make Changes → Verify → Iterate）、工具使用指南

**移除：**
- 移除了 `_build_runtime_context()` 静态方法，改为将 channel/chat_id 直接拼接到系统提示词
- `build_messages()` 不再插入独立的 runtime context user message

### 3. `nanobot/agent/subagent.py`（子 Agent 管理器）

**新增能力：**
- 新增 A2A 支持（AnnounceChainManager、SessionKey）
- 新增跨 agent 生成（`target_agent_id` 参数）
- 新增嵌套深度控制（`parent_depth`、`max_depth`）
- 新增重试机制（`_run_subagent_with_retry`，支持指数退避、超时、可重试错误判断）
- 新增 `get_task_info()` 方法（查询运行中任务状态）
- 新增 `_publish_announce_via_bus()` 方法
- `_announce_result()` 增加 depth、session_key、parent_session_key 参数
- 子 agent 提示词增加深度信息和嵌套生成能力说明
- 子 agent 在未达到最大深度时可以使用 SpawnTool 生成自己的子 agent

### 4. `nanobot/agent/tools/spawn.py`（Spawn 工具）

**新增能力：**
- 新增策略引擎集成（PolicyEngine，检查 A2A 策略）
- 新增批量生成（batch spawn）功能，支持并行生成多个子 agent
- 新增跨 agent 生成（`agent_id` 参数）
- 新增深度控制（`_spawn_depth`、`_get_max_spawn_depth()`）
- `set_context()` 扩展为接受 session_key、agent_id、spawn_depth

### 5. `nanobot/agent/tools/filesystem.py`（文件系统工具）

**ReadFileTool：**
- 新增行号显示（`{line_num:>6}: {line}` 格式）
- 新增行范围读取（start_line/end_line 参数）
- 新增 200 行截断保护（大文件自动截断并提示使用范围读取）

**WriteFileTool：**
- 新增 CheckpointManager 快照（写入前自动备份，支持撤销）

**EditFileTool（重大升级）：**
- 从简单的 `old_text → new_text` 替换升级为 Aider 风格的 SEARCH/REPLACE 块
- 支持灵活的空白匹配（自动缩进对齐）
- 支持多个 SEARCH/REPLACE 块在一次调用中应用
- 生成 unified diff 输出

**ListDirTool：**
- 新增 100 项截断限制

**其他变更：**
- `_resolve_path()` 移除了 workspace 参数（不再支持相对路径自动解析到 workspace）
- 移除了 `_not_found_message()` 相似度匹配错误提示

### 6. `nanobot/agent/tools/shell.py`（Shell 执行工具）

- 新增 Docker 沙箱会话支持（`session` 参数，可委托给 DockerSession）
- 移除了 `path_append` 参数
- `format` 命令的正则匹配范围扩大
- 移除了进程超时后的 `wait()` 清理（潜在的文件描述符泄漏风险）

### 7. `nanobot/config/schema.py`（配置 Schema）

**新增配置模型：**
- `AgentConfig` — 完整的单 agent 配置（id、name、workspace、model、temperature、max_tokens、context_window、auto_verify、sandbox、permission_mode、thinking_budget、subagents 等）
- `SubagentConfig` — 子 agent 配置（max_spawn_depth、max_children_per_agent、max_concurrent、run_timeout_seconds 等）
- `AgentBinding` — 消息路由规则（channel/chat_id/keyword 匹配到特定 agent）
- `TeamConfig` — Agent Team 分组（members、leader、strategy: parallel/sequential/leader_delegate）
- `AgentToAgentPolicy` — A2A 通信策略（enabled、allow/deny 列表、max_ping_pong_turns）
- `SessionVisibilityPolicy` — 会话可见性策略（self/tree/agent/all）
- `MemorySearchConfig` — 向量记忆搜索配置（embedding provider、chunking、reranker、vector backend 等，约 30 个配置项）
- `MCPConfig` — 独立的 MCP 配置

**AgentsConfig 扩展：**
- 从简单的 defaults 扩展为完整的多 agent 配置
- 新增 `agent_list`、`bindings`、`teams`、`default_agent` 字段
- 新增 `get_agent()`、`has_agent()`、`list_agent_ids()`、`get_team()` 等方法

**ExecToolConfig：**
- 新增 `sandbox_image` 字段；移除了 `path_append`

**ProvidersConfig：**
- 新增 `ollama` provider（Ollama 本地 LLM）
- 移除了 `siliconflow`、`volcengine`、`openai_codex`、`github_copilot`

**其他：**
- 移除了 `Base` 基类（不再支持 camelCase 兼容）
- 移除了 `MatrixConfig`、`HeartbeatConfig`
- `ChannelsConfig` 移除了 `send_progress`、`send_tool_hints` 全局开关

### 8. `nanobot/providers/litellm_provider.py`（LiteLLM Provider）

**新增能力：**
- 新增 `stream_chat()` 流式方法（完整的 chunk 处理，支持 text、reasoning、tool_call delta）
- 新增 `_build_kwargs()` 公共方法（chat 和 stream_chat 共用）
- 新增 debug 日志写入 `/tmp/nanobot_debug_prompt.json`
- 新增 `frequency_penalty` 和 `thinking_budget` 参数
- 新增 Gemini 模型自动升级逻辑（gemini-pro → gemini-2.5-flash）
- 新增 `num_retries=3` 自动重试

**移除：**
- 移除了 `_sanitize_messages()` 方法（非标准字段过滤）
- 移除了 `_supports_cache_control()` 和 `_apply_cache_control()` 精确 prompt caching
- JSON 解析从 `json_repair.loads` 改为 `json.loads`（降低了容错性）

### 9. `nanobot/providers/base.py`（Provider 基类）

- 新增 `LLMStreamChunk` 数据类（delta_content、tool_call 增量、reasoning_content、usage）
- 新增 `stream_chat()` 抽象方法（默认实现回退到非流式 chat）
- `chat()` 签名新增 `frequency_penalty` 和 `thinking_budget` 参数

### 10. `nanobot/providers/custom_provider.py`（Custom Provider）

- 新增完整的 `stream_chat()` 流式实现

### 11. `nanobot/providers/registry.py`（Provider 注册表）

- 新增 Ollama provider（`ollama_chat` 前缀，本地部署，默认 `http://localhost:11434`）
- OpenAI Codex 和 Github Copilot 的 keywords 和 skip_prefixes 扩展

### 12. `nanobot/cli/commands.py`（CLI 命令）

**新增：**
- 新增 `session` 子命令（list、show — 查看会话详情和最近消息）
- 新增 Gateway 模式（`_agent_gateway_mode`、`_send_to_gateway`，通过 HTTP API 连接 Gateway 进行交互式聊天）
- 新增 subagents、sessions、teams CLI 集成
- `status` 命令新增 Gateway 状态检查（通过 psutil 检测进程，显示 agent 列表、team、路由规则）

**移除：**
- 移除了 `provider` 子命令和 OAuth 登录功能（openai-codex、github-copilot）
- `cron_run` 命令移除了实际的 agent 执行逻辑

### 13. `nanobot/session/manager.py`（会话管理器）

**新增：**
- 新增 `SessionKey` 对象支持（结构化的 agent_id + session_type）
- 新增 `spawn_depth`、`parent_session_key` 字段
- 新增 `create()` 方法（强制创建新会话，覆盖已有）
- 新增 `get_sessions_by_agent()` — 按 agent 过滤会话
- 新增 `get_child_sessions()` — 获取子 agent 会话
- 新增 `_extract_agent_id()` — 从 session key 提取 agent ID

### 14. `nanobot/agent/memory.py`（记忆存储）

- 新增向量记忆集成（VectorMemoryAdapter，根据 memory_search_config 初始化）
- 新增 `semantic_search()` 方法（语义搜索）
- 新增 `sync_vector_memory()` 方法（触发向量索引同步）

### 15. `nanobot/agent/tools/registry.py`（工具注册表）

- 错误消息更详细（列出 expected/received 参数）
- 移除了 `[Analyze the error above and try a different approach.]` 自动提示后缀
- 工具未找到时不再列出可用工具名

---

## 三、总结对比

| 维度 | cab901b（之前） | b6891c2（之后） |
|------|----------------|----------------|
| Agent 模型 | 单 agent + 简单 subagent | 多 agent（A2A 通信、Team、Orchestrator） |
| 代码智能 | 无 | LSP、RepoMap、SymbolIndex、Folding |
| 记忆系统 | 纯文件（MEMORY.md + HISTORY.md） | 向量搜索 + 语义重排序 + 文件记忆 |
| LLM 交互 | 仅非流式 | 流式 + 非流式 |
| 文件编辑 | 简单 old_text → new_text | Aider 风格 SEARCH/REPLACE（灵活空白匹配） |
| 沙箱 | 无 | Docker 沙箱支持 |
| 权限 | 无 | PermissionGate + PolicyEngine |
| Gateway | 无 | HTTP 多 agent 网关 |
| Web UI | 无 | Streamlit Web Console |
| MCP | 内联到 loop.py | 独立 MCP 模块 |
| 工具数量 | ~10 个 | ~30 个 |
| Provider | 含 OAuth 登录，无 Ollama | 含 Ollama，无 OAuth |
| 配置 | 单 agent defaults | 多 agent 配置、Team、Binding、A2A 策略 |
| CLI | 基础命令 + OAuth 登录 | 新增 session/subagents/teams 子命令 + Gateway 模式 |
| 测试 | 无独立测试 | 约 20 个测试文件 |
| 文档 | 无 | 约 40 个文档文件 |

### 核心演进方向

1. **从单 agent 到多 agent 协作** — 引入 A2A 通信、Team 编排、Orchestrator 模式，支持 agent 间消息传递、任务分解与结果聚合
2. **从简单工具到代码智能** — 引入 LSP 集成、RepoMap、符号索引、代码折叠，使 agent 具备 IDE 级别的代码理解能力
3. **从文件记忆到向量记忆** — 引入 sqlite-vec 向量数据库、语义搜索、交叉编码器重排序，大幅提升记忆检索精度
4. **从非流式到流式** — LLM 交互支持流式输出，改善用户体验（实时看到生成过程）
5. **从无沙箱到 Docker 沙箱** — 代码执行可在隔离的 Docker 容器中运行，提升安全性
6. **从 CLI 到多端** — 新增 Web Console（Streamlit）和 Gateway HTTP API，支持多种接入方式

### 风险与关注点

- 代码量净增 37K+ 行，复杂度显著增长，需关注可维护性
- 移除了 `json_repair.loads` 改用 `json.loads`，降低了 LLM 输出的容错性
- 移除了进程超时后的 `wait()` 清理，存在文件描述符泄漏风险
- 移除了 prompt caching 精确控制（`_supports_cache_control`），可能影响 token 成本
- 向量记忆系统依赖 sqlite-vec，增加了部署复杂度
- 部分新模块（如 A2A、Team）的测试覆盖需持续完善
