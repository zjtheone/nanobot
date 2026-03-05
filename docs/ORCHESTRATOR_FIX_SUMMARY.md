# Orchestrator Worker Spawn 修复总结

## 🎯 修复目标

让 Orchestrator 真正成为**任务协调者**，而不是**独行者**。

**修复前**: 所有工作都是 orchestrator 自己完成 ❌
**修复后**: Orchestrator 分解任务并 spawn workers 并行工作 ✅

---

## 🔧 修复内容

### 1. 创建 Orchestrator Skill ✅

**文件**: `nanobot/skills/orchestrator.md`

**核心内容**:
- 明确 orchestrator 的角色是"协调者"不是"执行者"
- 强制要求复杂任务必须分解并 spawn workers
- 提供详细的 spawn 决策树和最佳实践
- 包含好/坏行为示例

**关键指令**:
```markdown
## ⚠️ 核心原则

### ✅ 必须做的
1. **分解复杂任务** - 将大任务分解为 3-5 个可并行的子任务
2. **Spawn 专业 Worker** - 为每个子任务创建专门的 worker agent
3. **等待并聚合** - 等待所有 worker 完成后，整合结果
4. **使用批量 spawn** - 一次性 spawn 所有 worker，让他们并行工作

### ❌ 禁止做的
1. **不要自己完成所有工作**
2. **不要串行执行**
3. **不要跳过 spawn** - 复杂任务必须 spawn workers
```

---

### 2. 修改配置文件 ✅

**修改**: `/Users/cengjian/.nanobot/config.json`

```json
{
  "agents": {
    "agent_list": [
      {
        "id": "orchestrator",
        "skills": ["orchestrator"],  // ← 新增
        ...
      }
    ]
  }
}
```

---

### 3. 优化 Spawn 工具描述 ✅

**文件**: `nanobot/agent/tools/spawn.py`

**改进前**:
```python
"Spawn a subagent to execute a task in the background."
```

**改进后**:
```python
"Spawn subagents to execute tasks in parallel.

**Best Practice**: For complex tasks, use `batch` spawn to create 
multiple workers that work in PARALLEL.

**When to use batch spawn**:
- Full-stack development (backend + frontend + tests)
- Research projects (multiple topics in parallel)
- Code review (multiple aspects)
- Data analysis (cleaning + analysis + visualization)

**Example - Batch Spawn (Recommended)**:
{
  "batch": [
    {"task": "Research best practices", "label": "research-worker"},
    {"task": "Implement backend API", "label": "backend-worker"},
    {"task": "Implement frontend UI", "label": "frontend-worker"},
    {"task": "Write tests", "label": "test-worker"}
  ],
  "wait": true,
  "timeout": 600
}"
```

---

## 📊 预期效果对比

### 修复前 ❌

```
📥 [ORCHESTRATOR] Routing message
🤖 [orchestrator] Processing: 实现订票系统...

🔄 [orchestrator] Tool call: create_implementation_plan
🔄 [orchestrator] Tool call: shell
🔄 [orchestrator] Tool call: write_file (config.py)
🔄 [orchestrator] Tool call: write_file (models/user.py)
🔄 [orchestrator] Tool call: write_file (models/station.py)
🔄 [orchestrator] Tool call: write_file (api/tickets.py)
... (所有工作都是 orchestrator 自己完成)

✅ Agent orchestrator completed task in 180s
```

**问题**:
- ❌ 没有 spawn 任何 worker
- ❌ 所有工作串行执行
- ❌ 耗时长 (180s)
- ❌ 没有发挥多 agent 优势

---

### 修复后 ✅

```
📥 [ORCHESTRATOR] Routing message
🤖 [orchestrator] Processing: 实现订票系统...

🔄 [orchestrator] Tool call: spawn(batch=[
  {"task": "调研最佳实践", "label": "research-worker"},
  {"task": "实现后端 API", "label": "backend-worker"},
  {"task": "实现前端界面", "label": "frontend-worker"},
  {"task": "编写测试", "label": "test-worker"}
])

# Workers 并行工作
📥 [RESEARCH-WORKER] Routing message
🤖 [research-worker] Processing: 调研最佳实践...
🔄 [research-worker] Tool call: web_search({...})

📥 [BACKEND-WORKER] Routing message
🤖 [backend-worker] Processing: 实现后端 API...
🔄 [backend-worker] Tool call: write_file({...})

📥 [FRONTEND-WORKER] Routing message
🤖 [frontend-worker] Processing: 实现前端界面...
🔄 [frontend-worker] Tool call: write_file({...})

📥 [TEST-WORKER] Routing message
🤖 [test-worker] Processing: 编写测试...
🔄 [test-worker] Tool call: write_file({...})

# Workers 完成后，orchestrator 聚合
🔄 [orchestrator] Tool call: write_file({整合结果})

✅ Agent orchestrator completed task in 60s
```

**优势**:
- ✅ 4 个 workers 并行工作
- ✅ 耗时短 (60s vs 180s)
- ✅ 专业分工，质量更高
- ✅ 真正发挥多 agent 优势

---

## 🎯 测试方法

### 快速测试

```bash
# 1. 启动 Gateway
nanobot gateway --multi -i

# 2. 发送复杂任务
>> 实现一个完整的订票系统

# 3. 观察日志
# 应该看到:
# 🔄 [orchestrator] Tool call: spawn(batch=[...])
# 🤖 [research-worker] Processing: ...
# 🤖 [backend-worker] Processing: ...
# 🤖 [frontend-worker] Processing: ...
```

### 使用测试脚本

```bash
./test_orchestrator_fix.sh
```

---

## 📋 修改文件清单

| 文件 | 修改内容 | 行数 |
|------|---------|------|
| `nanobot/skills/orchestrator.md` | 新建 Orchestrator Skill | 182 |
| `~/.nanobot/config.json` | 添加 orchestrator skill | +1 |
| `nanobot/agent/tools/spawn.py` | 优化工具描述 | ~30 |
| `test_orchestrator_fix.sh` | 测试脚本 | 60 |

---

## 🎓 使用建议

### 适合 Spawn Workers 的任务

✅ **应该 Spawn**:
- 全栈开发（订票系统、电商网站）
- 数据分析平台
- 调研报告（市场调研、竞品分析）
- 复杂算法实现

❌ **不应该 Spawn**:
- 简单函数（快速排序）
- 简单查询（什么是 API）
- 单一任务（写个 SQL）

### Spawn 最佳实践

1. **数量**: 3-5 个 workers
2. **并行**: 使用 batch 一次性 spawn
3. **等待**: 设置 `wait: true`
4. **超时**: 根据任务复杂度设置
5. **标签**: 使用描述性的 label

---

## 🔍 故障排查

### 问题 1: 还是没有 spawn workers

**可能原因**:
1. Skill 没有正确加载
2. LLM 选择不遵循 skill

**解决方法**:
```bash
# 检查 skill 是否加载
cat ~/.nanobot/config.json | grep -A 5 '"orchestrator"'

# 重启 Gateway
pkill -f "nanobot gateway"
nanobot gateway --multi -i
```

### 问题 2: Spawn 了但串行执行

**可能原因**: 没有使用 batch spawn

**解决方法**: 确保使用:
```json
{
  "batch": [...],
  "wait": true
}
```

---

## 📚 相关文档

- `AGENT_TEAM_ORCHESTRATOR_ANALYSIS.md` - 问题分析
- `orchestrator.md` - Orchestrator Skill
- `test_orchestrator_fix.sh` - 测试脚本

---

**修复完成时间**: 2026-03-05
**状态**: ✅ 待测试验证

---

🎉 **现在 Orchestrator 应该真正成为协调者了！**
