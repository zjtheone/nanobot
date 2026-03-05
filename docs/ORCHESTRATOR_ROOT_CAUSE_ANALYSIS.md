# Orchestrator 问题根因分析

## 🔍 为什么所有修复都无效？

### 测试日志分析

```
🤖 [orchestrator] Processing: 实现库房管理系统...
🔄 [orchestrator] Tool call: list_dir({...})
🔄 [orchestrator] Tool call: read_file({...})
🔄 [orchestrator] Tool call: write_file({...})
🔄 [orchestrator] Tool call: write_file({...})
... (全是 orchestrator 自己完成)
```

**观察**: Orchestrator 完全没有 spawn workers 的意图。

---

## 🐛 根本原因

### 1. Skill/Bootstrap 只是"建议"，不是"强制"

```markdown
# Orchestrator Skill (orchestrator.md)
## ⚠️ 核心原则
1. **分解复杂任务** - 将大任务分解为 3-5 个可并行的子任务
2. **Spawn 专业 Worker** - 为每个子任务创建专门的 worker agent
```

**问题**: LLM **可以自由选择是否遵循**这些指令。

**LLM 的思考过程**:
```
用户要求：实现库房管理系统

选项 A: 遵循 skill 指令
- 分析任务，分解为子任务
- spawn research-worker, backend-worker, frontend-worker
- 等待完成，聚合结果
- 步骤复杂，容易出错

选项 B: 直接完成（当前选择）
- 直接创建 implementation_plan
- 直接写代码
- 简单直接，成功率高

选择: B（更简单）
```

### 2. LLM 的"惰性"倾向

LLM 倾向于选择**最简单**的路径完成任务：
- spawn workers 需要额外的步骤和复杂性
- 直接完成更"高效"
- 没有惩罚机制

### 3. 架构设计问题

**NanoBot 的设计哲学**:
- Agent 是**自主**的，不是**被控制**的
- Skill/Bootstrap 是**建议**，不是**命令**
- LLM 有**最终决策权**

**矛盾**:
- 我们想要**强制** orchestrator spawn workers
- 但架构设计是**自主决策**

---

## ✅ 可行的解决方案

### 方案 A: 代码级强制（违背架构）

```python
# nanobot/agent/loop.py
async def process_message(self, msg, ...):
    if self.agent_id == "orchestrator":
        if self._is_complex_task(msg.content):
            # 强制 spawn workers
            await self._force_spawn_workers(msg.content)
            return
```

**优点**: 100% 有效
**缺点**: 
- 违背 NanoBot 架构哲学
- 硬编码逻辑，难以维护
- **不推荐**

---

### 方案 B: 改变设计思路（推荐）⭐

**核心思路**: 不依赖 orchestrator **自动** spawn，而是**用户/系统触发**

#### 实现方式 1: 专用 CLI 命令

```bash
# 用户明确指定使用 team 模式
nanobot team exec --team=dev-team "实现库房管理系统"
```

**优点**:
- 明确意图
- 符合架构
- 用户可控

#### 实现方式 2: Orchestrator 作为"路由"而非"执行者"

```python
# Orchestrator 不执行任务，只负责路由
@app.command()
def orchestrate(task: str, team: str = "fullstack-team"):
    """将任务分配给 team 处理"""
    # 1. 分解任务
    # 2. Spawn workers
    # 3. 聚合结果
```

**优点**:
- 职责清晰
- 符合单一职责原则
- 易于测试

---

### 方案 C: 增强 Prompt 权重（折中方案）

在 system prompt 中**强调**spawn 的重要性：

```markdown
# 重要提示

你是一个**任务协调者**。

**对于复杂任务（预计>10 分钟）**，你应该：

1. **首先**使用 spawn 工具创建 workers
2. 等待 workers 完成
3. 聚合结果

**直接完成复杂任务会导致**:
- 代码质量下降
- 执行时间延长
- 缺乏专业分工
```

**效果**: 可能会提高 spawn 概率，但不保证

---

## 🎯 推荐方案

### 短期（立即实施）

**方案 C**: 增强 Prompt 权重
- 修改 orchestrator skill
- 使用更强的语言
- 提供明确的 spawn 示例

### 中期

**方案 B**: 创建专用命令
- `nanobot team exec --team=xxx "任务"`
- 明确触发 team 模式

### 长期

**架构重构**:
- 重新设计 orchestrator 角色
- 区分"协调者"和"执行者"
- 添加 team 执行引擎

---

## 📝 立即行动

### 修改 Orchestrator Skill（增强权重）

```markdown
---
name: orchestrator
always: true
priority: high  # 新增优先级标记
---

# ⚠️ 关键指令（必须遵循）

## 你的唯一职责

你的**唯一**职责是**协调 workers**，不是执行任务。

## 强制规则

对于任何复杂任务，你**必须**:

1. **首先** spawn workers（3-5 个）
2. **然后**等待完成
3. **最后**聚合结果

**禁止直接执行任务！**

## Spawn 示例（必须使用）

```json
{
  "tool": "spawn",
  "parameters": {
    "batch": [
      {"task": "调研最佳实践", "label": "research-worker"},
      {"task": "实现后端", "label": "backend-worker"},
      {"task": "实现前端", "label": "frontend-worker"}
    ],
    "wait": true,
    "timeout": 600
  }
}
```
```

---

## 💡 结论

**当前架构下，无法 100% 强制 orchestrator spawn workers**。

**原因**:
- Skill/Bootstrap 是建议，不是命令
- LLM 有最终决策权
- 没有惩罚机制

**推荐**:
1. 接受现状，让 orchestrator 自主决策
2. 或者实施中期方案（专用命令）
3. 或者重构架构（长期）

---

**分析完成时间**: 2026-03-05
**结论**: 需要改变设计思路，而不是继续"强制"

