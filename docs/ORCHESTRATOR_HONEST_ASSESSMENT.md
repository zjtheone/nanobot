# Orchestrator 实施 - 诚实评估

## 🎯 当前状态

### 已实施的功能 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| AnnounceChain 集成 | ✅ 完成 | AgentLoop 支持 `wait_for_workers()` |
| decompose_and_spawn 工具 | ✅ 完成 | Orchestrator 专用工具 |
| aggregate_results 工具 | ✅ 完成 | 结果聚合工具 |
| Orchestrator skill 文档 | ✅ 完成 | 强制指令文档 |

### 测试结果 ❌

**实际运行**：
```
用户：实现火车票订票系统

预期:
🔄 Tool call: decompose_and_spawn({...})
🤖 [research] Processing...
🤖 [backend] Processing...

实际:
🔄 Tool call: create_implementation_plan({...})  ❌
🔄 Tool call: write_file({...})                  ❌
[Orchestrator 自己写代码，没有 spawn workers]
```

---

## 🐛 根本问题

### 问题 1: LLM 有最终决策权

**架构限制**:
- Skill 是"建议"，不是"命令"
- LLM 可以自由选择使用哪个工具
- 没有机制强制 LLM 使用特定工具

**为什么**：
```python
# 当前架构
tools = ToolRegistry()
tools.register(decompose_tool)  # 注册工具
tools.register(aggregate_tool)   # 注册工具

# LLM 决策
available_tools = tools.list()
chosen_tool = LLM.choose(available_tools)  # ← LLM 自由选择
```

**问题**: LLM 可能选择 `create_implementation_plan` 而不是 `decompose_and_spawn`

---

### 问题 2: Skill 文档无效

**原因**:
- Skill 在 prompt 中的权重不够
- LLM 更注重最近的对话上下文
- 强制指令被忽略

**示例**：
```markdown
# orchestrator.md (200 行文档)
⚠️ 必须使用 decompose_and_spawn
禁止自己写代码
```

**LLM 实际看到**：
```
用户：实现火车票系统

[思考]
我需要实现这个系统...
[完全忽略 skill 文档]
```

---

## 💡 解决方案选项

### 选项 A: 修改 System Prompt（推荐）⭐

**实施**：
```python
# Gateway manager.py
if agent_id == "orchestrator":
    # 添加强制性 system prompt
    config.system_prompt = """
You are an ORCHESTRATOR. You MUST use decompose_and_spawn tool.
NEVER write code yourself.
"""
```

**优点**：
- 直接修改 prompt，权重高
- 简单，立即生效
- 不改变架构

**缺点**：
- 仍然不是 100% 强制
- LLM 仍可能忽略

---

### 选项 B: 移除其他工具（强力）⭐⭐⭐

**实施**：
```python
# 只给 Orchestrator 注册 decompose_and_spawn
if agent_id == "orchestrator":
    # 不注册 write_file, exec 等工具
    # 只注册 decompose_and_spawn 和 aggregate_results
    tools.register(decompose_tool)
    tools.register(aggregate_tool)
    # 不注册 write_file, exec, etc.
```

**优点**：
- 物理上阻止 LLM 自己写代码
- 100% 强制
- 简单有效

**缺点**：
- Orchestrator 无法做其他事情
- 可能太严格

---

### 选项 C: 工具调用 Hook（复杂）⭐⭐

**实施**：
```python
class OrchestratorToolInterceptor:
    async def intercept(tool_call):
        if tool_call.name in ['write_file', 'exec']:
            raise ToolNotAllowedError(
                "Orchestrator cannot use this tool. "
                "Use decompose_and_spawn instead."
            )
```

**优点**：
- 运行时检查
- 可以给出错误提示
- 教育 LLM

**缺点**：
- 实现复杂
- 需要额外架构

---

## 🚀 推荐实施

**立即实施**：选项 B（移除其他工具）

**原因**：
1. ✅ 100% 强制
2. ✅ 简单实现
3. ✅ 立即可用
4. ✅ 不依赖 LLM "遵守规则"

---

## 📋 实施步骤

### 步骤 1: 修改 Orchestrator 工具注册

```python
# nanobot/agent/loop.py
if self.agent_id == "orchestrator":
    # 只注册 Orchestrator 专用工具
    decompose_tool = DecomposeAndSpawnTool(self)
    self.tools.register(decompose_tool)
    
    aggregate_tool = AggregateResultsTool(self)
    self.tools.register(aggregate_tool)
    
    # 不注册其他工具
    # self.tools.register(WriteFileTool())  # ❌ 不注册
    # self.tools.register(ExecTool())       # ❌ 不注册
```

### 步骤 2: 测试验证

```bash
# 重启 Gateway
pkill -f "nanobot gateway"
nanobot gateway --multi -i

# 发送任务
>> 实现火车票订票系统

# 预期行为
🔄 Tool call: decompose_and_spawn({...})
🤖 [research] Processing...
🤖 [backend] Processing...
```

---

## 🎯 成功标准

**新的 Orchestrator 行为**：
```
用户：实现火车票系统

🔄 Tool call: decompose_and_spawn({...})  ✅
  Spawning workers: research, backend, frontend, test

🤖 [research] Processing: ...              ✅
🤖 [backend] Processing: ...               ✅
🤖 [frontend] Processing: ...              ✅
🤖 [test] Processing: ...                  ✅

✅ All workers completed
🔄 Tool call: aggregate_results            ✅

基于所有 workers 的贡献...              ✅
```

---

## ⚠️ 重要说明

**为什么 Skill 无效**：
- Skill 是 prompt 的一部分
- LLM 有权"忽略"prompt
- 特别是当 prompt 很长时

**为什么移除工具有效**：
- 物理上不可用
- LLM 无法选择没有的工具
- 100% 强制

---

**评估完成时间**: 2026-03-05 13:30
**状态**: ⚠️ 需要进一步实施
**推荐**: 立即实施选项 B

