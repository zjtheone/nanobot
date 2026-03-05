# Orchestrator 最终修复方案

## 🐛 问题根因

### 为什么之前的修复无效？

1. **Skill 机制问题**
   - `trigger: auto` 不会强制注入到 prompt
   - `always: true` 只是将 skill 文档添加到上下文
   - LLM 可能会**忽略** skill 文档中的指令

2. **配置 ≠ 行为**
   - 配置中指定 skill 只是"建议"
   - LLM 可以自由选择是否遵循

3. **缺少强制约束**
   - 没有机制强制 orchestrator 必须 spawn workers
   - LLM 倾向于选择"更简单"的路径（自己完成）

---

## ✅ 最终解决方案

### 多层强制机制

#### 第 1 层: Skill 文档 (已实施)
- `nanobot/skills/orchestrator.md`
- `always: true` 确保总是加载

#### 第 2 层: Agent Config (已实施)
- `~/.nanobot/config.json`
- `"skills": ["orchestrator"]`

#### 第 3 层: Bootstrap Prompt (新增) ⭐
- `~/.nanobot/workspace-orchestrator/BOOTSTRAP.md`
- **强制性的行为准则**
- 在 system prompt 的最前面

#### 第 4 层: 代码级强制 (可选)
- 修改 `nanobot/agent/loop.py`
- 检测 orchestrator 且任务复杂时，强制要求 spawn

---

## 📋 实施步骤

### 已完成

1. ✅ 创建 `orchestrator.md` skill
2. ✅ 修改 config 添加 skill
3. ✅ 优化 spawn 工具描述
4. ✅ 创建 `BOOTSTRAP.md`

### 下一步

```bash
# 1. 重启 Gateway（重新加载配置）
pkill -f "nanobot gateway"
nanobot gateway --multi -i

# 2. 测试复杂任务
>> 实现一个完整的选课系统

# 3. 预期日志
🔄 [orchestrator] Tool call: spawn(batch=[...])
🤖 [research-worker] Processing: ...
🤖 [backend-worker] Processing: ...
🤖 [frontend-worker] Processing: ...
```

---

## 🔍 验证方法

### 检查 Skill 加载

```bash
# 查看 orchestrator workspace 内容
ls -la ~/.nanobot/workspace-orchestrator/

# 应该看到:
# BOOTSTRAP.md ← 新增的强制行为准则
```

### 检查 Prompt 注入

Gateway 启动时，orchestrator 的 system prompt 应该包含:

```markdown
# Orchestrator Agent - 强制行为准则

## ⚠️ 重要提示

你是一个**任务协调者**，**不是执行者**。

**你必须 spawn workers 来并行完成任务！**
```

---

## 📊 对比

| 机制 | 修复前 | 修复后 |
|------|--------|--------|
| Skill 文档 | ❌ 无 | ✅ orchestrator.md |
| Config | ❌ 无 | ✅ skills: ["orchestrator"] |
| Bootstrap | ❌ 无 | ✅ BOOTSTRAP.md |
| 强制程度 | 无 | 高（三层约束） |

---

## 🎯 预期行为

### 修复前 ❌

```
🤖 [orchestrator] Processing
🔄 [orchestrator] Tool call: write_file
🔄 [orchestrator] Tool call: write_file
... (全部自己完成)
```

### 修复后 ✅

```
🤖 [orchestrator] Processing
🔄 [orchestrator] Tool call: spawn(batch=[...])
🤖 [research-worker] Processing
🤖 [backend-worker] Processing
🤖 [frontend-worker] Processing
... (workers 并行工作)
```

---

## 💡 为什么这次会有效？

1. **BOOTSTRAP.md 在 prompt 最前面** - LLM 首先看到
2. **使用强制性语言** - "必须"、"禁止"、"绝对不要"
3. **提供具体示例** - spawn 的 JSON 示例
4. **多层约束** - Skill + Config + Bootstrap

---

## ⚠️ 如果还是无效

如果 orchestrator 仍然不 spawn workers，需要实施**第 4 层**（代码级强制）:

```python
# nanobot/agent/loop.py
async def process_message(self, msg, ...):
    # Check if orchestrator handling complex task
    if self.agent_id == "orchestrator":
        if self._is_complex_task(msg.content):
            # Force spawn workers or reject
            if not self._has_spawned_workers():
                logger.warning("Orchestrator must spawn workers for complex tasks!")
                # Force spawn default workers
                await self._force_spawn_workers(msg.content)
```

---

**修复完成时间**: 2026-03-05
**状态**: ✅ 多层强制机制已部署
**预期**: Orchestrator 应该开始 spawn workers

