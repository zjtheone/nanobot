# nanobot vs Claude Code 能力对比分析

## 一、核心架构对比

| 维度 | nanobot | Claude Code |
|------|---------|-------------|
| **代码量** | ~3,800 行核心代码 | 闭源，估计数十万行 |
| **设计哲学** | 轻量级、可扩展、研究友好 | 企业级、全功能、一体化 |
| **Provider 支持** | 多 Provider (OpenRouter/DeepSeek/本地等) | 仅 Anthropic Claude |
| **MCP 支持** | ✅ 完整支持 | ✅ 原生支持 (标准制定者) |

---

## 二、工具能力对比

### nanobot 已具备的工具

| 类别 | 工具 | Claude Code 对应 |
|------|------|------------------|
| **文件操作** | read_file, write_file, edit_file, list_dir, batch_edit | ✅ 完全具备 |
| **Shell 执行** | exec, shell (持久会话), Docker sandbox | ✅ 完全具备 |
| **代码智能** | LSP (definition/references/hover), refactor_rename, symbol_index | ✅ 完全具备 |
| **Git 集成** | git_status, git_diff, git_commit, git_log, git_checkout | ✅ 完全具备 |
| **搜索** | grep, find_files, search_semantic | ✅ 完全具备 |
| **Web** | web_search, web_fetch | ✅ 完全具备 |
| **MCP** | ✅ MCP Manager + Tool Wrapper | ✅ 原生支持 |
| **子代理** | spawn (后台任务) | ✅ Task/subagent |
| **调度** | cron (定时任务) | ⚠️ 有限支持 |
| **多渠道** | Telegram/Discord/Feishu/Slack/WhatsApp/Email/QQ | ❌ 无 |

### nanobot 独有特性

- **多渠道集成**: 支持 8+ 聊天平台 (Telegram, Discord, Feishu 等)
- **多 Provider**: 不绑定单一 LLM 提供商
- **轻量级**: 可读性强，适合研究和二次开发
- **Skills 系统**: 类似 Claude Code 的 Commands/Skills
- **Hooks 系统**: 前置/后置钩子
- **Memory 系统**: MEMORY.md + HISTORY.md 持久化
- **Checkpoint/Undo**: 文件修改回滚
- **权限控制**: Permission Gate (auto/ask/deny)

---

## 三、Claude Code 独有特性

| 特性 | 描述 | nanobot 状态 |
|------|------|--------------|
| **Extended Thinking** | Claude 独有的长推理模式 | ⚠️ 部分 (thinking_budget 参数存在) |
| **Prompt Caching** | 提示词缓存，节省 90% 输入 token | ✅ 已实现 |
| **CLAUDE.md** | 项目级指令文件 | ✅ 支持 (AGENTS.md/NANOBOT.md) |
| **Agent SDK** | 完整的 Agent 开发 SDK | ❌ 无 |
| **IDE 集成** | VSCode/JetBrains 原生插件 | ❌ 无 |
| **浏览器版本** | Web 端直接使用 | ❌ 无 |
| **CI/CD 集成** | GitHub Actions/GitLab CI 原生支持 | ⚠️ 需手动配置 |
| **MCP Tool Search** | 动态懒加载 MCP 工具 | ⚠️ 部分支持 |

---

## 四、能力差距分析

### ✅ nanobot 已达到 Claude Code 水平

1. **核心代码能力** - 文件读写、编辑、批量修改
2. **Shell 执行** - 命令执行、持久会话、沙箱模式
3. **代码智能** - LSP 集成、定义跳转、引用查找、重命名重构
4. **Git 工作流** - status/diff/commit/log/checkout
5. **MCP 协议** - 完整支持 stdio 和 HTTP 传输
6. **上下文管理** - 上下文窗口管理、智能压缩
7. **记忆系统** - 长期记忆 + 历史记录

### ⚠️ nanobot 部分实现

1. **Extended Thinking** - 参数存在但效果依赖 Provider
2. **子代理协调** - 有 spawn 但无复杂任务编排
3. **自动验证** - 有 auto_verify 但功能较简单

### ❌ nanobot 缺失

1. **IDE 集成** - 无 VSCode/JetBrains 插件
2. **Web 界面** - 无浏览器访问方式
3. **Agent SDK** - 无完整的 Agent 开发框架
4. **企业级部署** - 缺少多租户、审计日志等

---

## 五、结论

**nanobot 已具备 Claude Code 约 75-80% 的核心能力**

| 能力维度 | 对比结果 |
|----------|----------|
| 代码编辑与执行 | ✅ 完全对等 |
| 代码智能 (LSP) | ✅ 完全对等 |
| Git 工作流 | ✅ 完全对等 |
| MCP 扩展 | ✅ 完全对等 |
| 上下文管理 | ✅ 完全对等 |
| 推理能力 | ⚠️ 依赖底层 LLM |
| 用户体验 | ❌ 缺少 IDE/Web 集成 |
| 多渠道支持 | ✅ nanobot 独有优势 |

### nanobot 的独特价值

1. **超轻量**: 3800 行 vs Claude Code 的庞大代码库
2. **多 Provider**: 不绑定 Anthropic
3. **多渠道**: 一套代码支持 8+ 聊天平台
4. **可定制**: 开源、可读、可扩展

### 使用建议

| 需求 | 推荐方案 |
|------|----------|
| 完整 IDE 集成 | 用 Claude Code |
| 多渠道聊天机器人 | 用 nanobot |
| 研究/学习 Agent 架构 | 用 nanobot |
| 多 LLM Provider 支持 | 用 nanobot |

---

## 六、工具清单详情

### nanobot 内置工具 (22个)

| 工具名 | 文件 | 功能描述 |
|--------|------|----------|
| read_file | filesystem.py | 读取文件内容 |
| write_file | filesystem.py | 写入文件 |
| edit_file | filesystem.py | 编辑文件 (精确字符串替换) |
| list_dir | filesystem.py | 列出目录内容 |
| exec | shell.py | 执行 shell 命令 |
| shell | terminal.py | 持久 shell 会话 |
| grep | search.py | 内容搜索 |
| find_files | search.py | 文件搜索 |
| web_search | web.py | 网络搜索 |
| web_fetch | web.py | 获取网页内容 |
| git_status | git.py | Git 状态 |
| git_diff | git.py | Git 差异 |
| git_commit | git.py | Git 提交 |
| git_log | git.py | Git 日志 |
| git_checkout | git.py | Git 切换 |
| go_to_definition | lsp.py | LSP 定义跳转 |
| find_references | lsp.py | LSP 引用查找 |
| get_hover_info | lsp.py | LSP 悬停信息 |
| refactor_rename | refactor.py | 重命名重构 |
| spawn | spawn.py | 启动子代理 |
| message | message.py | 发送消息 |
| cron | cron.py | 定时任务 |

### 支持的 Provider (16个)

| Provider | 类型 | 特点 |
|----------|------|------|
| custom | 直接 | 任意 OpenAI 兼容端点 |
| openrouter | Gateway | 全球模型网关 |
| anthropic | 标准 | Claude 直连 |
| openai | 标准 | GPT 直连 |
| openai_codex | OAuth | Codex (OAuth 登录) |
| github_copilot | OAuth | GitHub Copilot |
| deepseek | 标准 | DeepSeek 直连 |
| gemini | 标准 | Gemini 直连 |
| zhipu | 标准 | 智谱 GLM |
| dashscope | 标准 | 阿里 Qwen |
| moonshot | 标准 | Kimi |
| minimax | 标准 | MiniMax |
| aihubmix | Gateway | API 网关 |
| siliconflow | Gateway | 硅基流动 |
| volcengine | Gateway | 火山引擎 |
| vllm | 本地 | 本地 vLLM 服务 |

---

*分析时间: 2026-02-21*
*nanobot 版本: v0.1.4*
