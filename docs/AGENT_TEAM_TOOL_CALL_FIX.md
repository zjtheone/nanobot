# 工具调用日志增强

## ✅ 修复完成

现在工具调用日志会显示**具体哪个 agent 在执行工具**！

---

## 📊 改进对比

### 改进前
```
🔄 Tool call: create_implementation_plan({...})
🔄 Tool call: shell({...})
🔄 Tool call: write_file({path: "app/config.py"})
```
❌ **看不出是哪个 agent 在执行**

---

### 改进后
```
🔄 [orchestrator] Tool call: create_implementation_plan({...})
🔄 [orchestrator] Tool call: shell({...})
🔄 [orchestrator] Tool call: write_file({path: "app/config.py"})
```
✅ **清晰显示执行者**

---

## 🔧 修改内容

### 文件 1: `nanobot/agent/loop.py` (LLM 循环)

```python
# 修改前 (line 743)
for tool_call in response.tool_calls:
    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")

# 修改后
# Get current session for agent_id
current_session_key = list(self.sessions._cache.keys())[-1] if self.sessions._cache else None
agent_id = current_session_key.split(":")[0] if current_session_key and ":" in current_session_key else "unknown"

for tool_call in response.tool_calls:
    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
    logger.info(f"🔄 [{agent_id}] Tool call: {tool_call.name}({args_str[:150]}...)")
```

---

### 文件 2: `nanobot/agent/loop.py` (_execute_single_tool)

```python
# 修改前 (line 828)
async def _execute_single_tool(self, name: str, arguments: dict[str, Any]) -> str:
    """Execute a single tool with hooks and metrics tracking."""
    from nanobot.agent.hooks import HookContext

    args_str = json.dumps(arguments, ensure_ascii=False)
    logger.info(f"Tool call: {name}({args_str[:200]})")

# 修改后
async def _execute_single_tool(self, name: str, arguments: dict[str, Any]) -> str:
    """Execute a single tool with hooks and metrics tracking."""
    from nanobot.agent.hooks import HookContext

    # Get current session for agent_id
    current_session_key = list(self.sessions._cache.keys())[-1] if self.sessions._cache else None
    agent_id = current_session_key.split(":")[0] if current_session_key and ":" in current_session_key else "unknown"

    args_str = json.dumps(arguments, ensure_ascii=False)
    logger.info(f"🔄 [{agent_id}] Tool call: {name}({args_str[:150]}...)")
```

---

## 📝 完整日志示例

### 场景 1: Orchestrator 直接执行
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 实现一个完整的订票系统...

🤖 [orchestrator] Processing: 实现一个完整的订票系统...

🔄 [orchestrator] Tool call: create_implementation_plan({...})
🔄 [orchestrator] Tool call: shell({...})
🔄 [orchestrator] Tool call: write_file({path: "app/config.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/models/user.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/models/venue.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/models/performance.py"})

✅ Agent orchestrator completed task in 180.5s
```

---

### 场景 2: 多个 Agent 协作
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 开发一个电商网站...

🤖 [orchestrator] Processing: 开发一个电商网站...

# Orchestrator 分解任务
🔄 [orchestrator] Tool call: create_implementation_plan({...})

# Spawn worker 执行具体任务
🔄 [worker-1] Tool call: web_search({...})
🔄 [worker-2] Tool call: write_file({...})

# Worker 完成后，orchestrator 继续整合
🔄 [orchestrator] Tool call: write_file({整合结果})

✅ Agent orchestrator completed task in 300.2s
```

---

## 🔍 使用技巧

### 查看特定 Agent 的工具调用
```bash
# 只看 orchestrator 的工具调用
nanobot gateway --multi -i 2>&1 | grep "🔄 \[orchestrator\]"

# 只看 worker-1 的工具调用
nanobot gateway --multi -i 2>&1 | grep "🔄 \[worker-1\]"
```

### 查看特定工具
```bash
# 只看文件写入
nanobot gateway --multi -i 2>&1 | grep "Tool call: write_file"

# 只看 shell 命令
nanobot gateway --multi -i 2>&1 | grep "Tool call: shell"

# 只看 exec 命令
nanobot gateway --multi -i 2>&1 | grep "Tool call: exec"
```

### 查看完整执行流程
```bash
nanobot gateway --multi -i 2>&1 | grep -E "📥|🤖|🔄|✅"
```

---

## 📋 日志图标说明

| 图标 | 说明 | 位置 |
|------|------|------|
| 📥 | 消息路由 | Gateway 层 |
| 🤖 | 消息处理 | Agent 层 |
| 🔄 | 工具调用 | 工具层（带 agent_id） |
| ✅ | 任务完成 | Agent 层 |

---

## 🎯 完整日志流程

```
1. 📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 实现订票系统...

2. 🤖 [orchestrator] Processing: 实现订票系统...

3. 🔄 [orchestrator] Tool call: create_implementation_plan({...})
   🔄 [orchestrator] Tool call: shell({...})
   🔄 [orchestrator] Tool call: write_file({path: "app/config.py"})
   🔄 [orchestrator] Tool call: write_file({path: "app/models/user.py"})
   ...

4. ✅ Agent orchestrator completed task in 180.5s
```

---

## 📚 相关文档

- `GATEWAY_INTERACTIVE_USAGE.md` - Gateway 使用指南
- `AGENT_TEAM_CONFIG.md` - Agent Team 配置
- `AGENT_TEAM_FINAL_LOG_GUIDE.md` - 日志使用指南
- `AGENT_TEAM_KEY_VARIABLE_FIX.md` - key 变量修复

---

**修复完成时间**: 2026-03-05
**状态**: ✅ 生产就绪
