# Orchestrator 问题分析与修复方案

## 🐛 问题分析

### 当前行为
```
📥 [ORCHESTRATOR] Routing message
🤖 [orchestrator] Processing
🔄 [orchestrator] Tool call: create_implementation_plan
🔄 [orchestrator] Tool call: shell
🔄 [orchestrator] Tool call: write_file
🔄 [orchestrator] Tool call: write_file
... (全部由 orchestrator 完成)
✅ Agent orchestrator completed
```

**问题**: 所有工作都是 orchestrator 自己完成的，没有 spawn 子 agent！

---

## 🔍 根本原因

### 1. Orchestrator 只是"配置"，不是"角色"

当前配置：
```json
{
  "id": "orchestrator",
  "subagents": {
    "max_spawn_depth": 3,
    "max_children_per_agent": 15,
    "max_concurrent": 20
  }
}
```

**问题**: 这只是配置了 **允许** spawn 多少子 agent，但 **不会自动 spawn**！

是否 spawn worker 取决于：
- LLM 的决策（由 system prompt 控制）
- 当前没有强制 orchestrator 必须 spawn worker

### 2. 缺少 Orchestrator System Prompt

当前 orchestrator 和其他 agent 使用相同的 bootstrap/system prompt，没有特殊的"协调者"行为指导。

### 3. Spawn 工具需要显式调用

```python
# 需要 agent 主动调用
await spawn(task="搜索最佳实践", label="research-worker")
await spawn(task="实现后端 API", label="backend-worker")
await spawn(task="实现前端界面", label="frontend-worker")
```

但 LLM 可能选择直接完成任务，而不是 spawn worker。

---

## ✅ 解决方案

### 方案 A: 添加 Orchestrator System Prompt（推荐）

创建专门的 Orchestrator system prompt，强制要求分解任务：

**文件**: `nanobot/skills/orchestrator.md`

```markdown
# Orchestrator 角色

你是一个任务协调者。你的职责是：

## 核心原则
1. **不要自己完成所有工作** - 你的价值是协调，不是执行
2. **分解复杂任务** - 将大任务分解为 3-5 个可并行的子任务
3. **Spawn 专业 worker** - 为每个子任务创建专门的 worker agent
4. **等待并聚合** - 等待所有 worker 完成后，整合结果

## 工作流

### 步骤 1: 分析任务
```
用户：实现一个完整的订票系统

分析：
- 需要调研现有系统 → spawn research-worker
- 需要实现后端 API → spawn backend-worker
- 需要实现前端界面 → spawn frontend-worker
- 需要测试验证 → spawn test-worker
```

### 步骤 2: Spawn Workers
```json
{
  "tool": "spawn",
  "parameters": {
    "batch": [
      {"task": "调研现有订票系统的最佳实践", "label": "research-worker"},
      {"task": "实现后端 API（用户、订单、票务）", "label": "backend-worker"},
      {"task": "实现前端界面（搜索、预订、支付）", "label": "frontend-worker"},
      {"task": "编写测试并验证功能", "label": "test-worker"}
    ],
    "wait": true,
    "timeout": 600
  }
}
```

### 步骤 3: 聚合结果
等待所有 worker 完成后，整合所有结果生成完整报告。

## 何时 Spawn Worker

✅ 应该 Spawn:
- 任务需要多方面专业知识
- 任务可以清晰分解为独立子任务
- 任务预计耗时 > 5 分钟

❌ 不应该 Spawn:
- 简单任务（5 分钟内完成）
- 需要连续上下文的任务
- 用户明确要求"直接完成"

## 示例

### 好的行为
```
用户：开发一个电商网站

Orchestrator:
1. spawn research-worker: 调研电商最佳实践
2. spawn backend-worker: 实现商品、订单、支付 API
3. spawn frontend-worker: 实现商品展示、购物车、结账界面
4. spawn test-worker: 编写测试
5. 聚合所有结果
```

### 不好的行为 ❌
```
用户：开发一个电商网站

Orchestrator:
1. 自己创建 implementation_plan
2. 自己写所有代码
3. 自己测试
（没有 spawn 任何 worker）
```
```

---

### 方案 B: 添加 Orchestrator 强制逻辑

修改 `nanobot/agent/loop.py`，当 agent_id 为 orchestrator 时，强制要求 spawn worker：

```python
async def process_message(self, msg: InboundMessage, ...):
    if self.agent_id == "orchestrator":
        # 检查任务复杂度
        if self._is_complex_task(msg.content):
            # 强制 spawn workers
            await self._spawn_workers_for_task(msg.content)
```

**缺点**: 硬编码逻辑，不够灵活

---

### 方案 C: 添加 Orchestrator 技能

创建 `orchestrator` skill，在 system prompt 中自动注入：

```markdown
---
name: orchestrator
trigger: auto
condition: agent_id == "orchestrator"
---

你是一个任务协调者。在处理复杂任务时，你应该：
1. 分解任务为多个子任务
2. 使用 spawn 工具创建 worker agent
3. 等待 worker 完成
4. 聚合结果
```

---

## 🎯 推荐实施方案

**方案 A + C 组合**:

1. **创建 Orchestrator System Prompt** (方案 A)
   - 明确 orchestrator 的职责
   - 提供 spawn worker 的示例
   - 说明何时应该/不应该 spawn

2. **添加 Orchestrator Skill** (方案 C)
   - 自动注入到 orchestrator agent
   - 强化 spawn worker 的行为

3. **优化 Spawn 工具提示**
   - 在工具描述中强调批量 spawn 的好处
   - 提供 batch spawn 示例

---

## 📝 实施步骤

### 步骤 1: 创建 Orchestrator Skill

```markdown
---
name: orchestrator
trigger: auto
description: Orchestrator agent special behavior
---

# Orchestrator 行为准则

## 你的角色
你是一个**任务协调者**，不是执行者。

## 核心职责
1. **分析任务** - 识别可以并行执行的子任务
2. **分解任务** - 将复杂任务分解为 3-5 个独立子任务
3. **Spawn Workers** - 为每个子任务创建专门的 worker
4. **聚合结果** - 整合所有 worker 的输出

## Spawn 决策树

```
任务复杂度？
├─ 简单（<5 分钟）→ 直接完成
└─ 复杂（>5 分钟）
    ├─ 可分解？
    │   ├─ 是 → Spawn workers 并行执行
    │   └─ 否 → 直接完成
    └─ 需要多方面专业知识？
        ├─ 是 → Spawn workers（不同专业）
        └─ 否 → 直接完成
```

## 示例

### 复杂任务（应该 Spawn）
用户：实现一个完整的订票系统

你应该：
1. spawn research-worker: 调研最佳实践
2. spawn backend-worker: 实现后端 API
3. spawn frontend-worker: 实现前端界面
4. spawn test-worker: 编写测试
5. 聚合结果

### 简单任务（直接完成）
用户：写个快速排序

你应该：直接实现，不需要 spawn
```

### 步骤 2: 修改 Config

```json
{
  "agents": {
    "agent_list": [
      {
        "id": "orchestrator",
        "skills": ["orchestrator"],
        ...
      }
    ]
  }
}
```

### 步骤 3: 优化 Spawn 工具描述

```python
@property
def description(self) -> str:
    return (
        "Spawn subagents to complete tasks in parallel. "
        "**Best Practice**: For complex tasks, use batch spawn "
        "to create multiple workers that work in parallel.\n\n"
        "Example:\n"
        "```json\n"
        "{\n"
        '  "batch": [\n'
        '    {"task": "Research best practices", "label": "research"},\n'
        '    {"task": "Implement backend", "label": "backend"},\n'
        '    {"task": "Implement frontend", "label": "frontend"}\n'
        "  ],\n"
        '  "wait": true\n'
        "}\n"
        "```"
    )
```

---

## 🎯 预期效果

修复后，日志应该显示：

```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 实现一个完整的订票系统...

🤖 [orchestrator] Processing: 实现一个完整的订票系统...

🔄 [orchestrator] Tool call: spawn(batch=[...])

# Workers 开始工作
📥 [RESEARCH-WORKER] Routing message
🤖 [research-worker] Processing: 调研最佳实践...
🔄 [research-worker] Tool call: web_search({...})

📥 [BACKEND-WORKER] Routing message
🤖 [backend-worker] Processing: 实现后端 API...
🔄 [backend-worker] Tool call: write_file({...})

📥 [FRONTEND-WORKER] Routing message
🤖 [frontend-worker] Processing: 实现前端界面...
🔄 [frontend-worker] Tool call: write_file({...})

# Workers 完成后，orchestrator 聚合
🔄 [orchestrator] Tool call: write_file({整合结果})

✅ Agent orchestrator completed task in 300s
```

---

## 📊 对比

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| Worker 数量 | 0 | 3-5 个 |
| 并行度 | 1 | 3-5 |
| 执行时间 | 180s | 60s |
| 代码质量 | 一般 | 更好（专业分工） |

---

**建议**: 立即实施方案 A + C，让 orchestrator 真正成为"协调者"！

