# Agent Team 日志修复总结

## 🐛 问题

### 问题 1: 日志无法区分 agent
```
2026-03-04 22:07:15 | INFO | Routing message from cli:interactive to agent orchestrator
2026-03-04 22:07:15 | INFO | Processing message from cli:user: 设计一个完整的图书管理系统
```
看不出是哪个 agent 在处理

### 问题 2: 变量作用域错误
```
ERROR | cannot access local variable 'key' where it is not associated with a value
```
`key` 在使用前未定义

---

## ✅ 修复方案

### 修复 1: 增强 Gateway 路由日志

**文件**: `nanobot/gateway/manager.py`

```python
# 修复前
logger.debug(f"Routing message from {msg.channel}:{msg.chat_id} to agent {agent_id}")

# 修复后
logger.info(f"\n📥 [{agent_id.upper()}] Routing message from {msg.channel}:{msg.chat_id}")
logger.info(f"   Content: {msg.content[:80]}...\n")
```

**输出**:
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 设计一个完整的图书管理系统...
```

---

### 修复 2: 增强 Agent 处理日志

**文件**: `nanobot/agent/loop.py`

```python
# 修复前（顺序错误）
agent_id = key.split(":")[0] if key and ":" in key else "unknown"
preview = msg.content[:80] + "..."
logger.info(f"🤖 [{agent_id}] Processing: {preview}")
key = session_key or msg.session_key  # ← key 在这里才定义！

# 修复后（正确顺序）
key = session_key or msg.session_key  # ← 先定义 key
agent_id = key.split(":")[0] if key and ":" in key else "unknown"
preview = msg.content[:80] + "..."
logger.info(f"🤖 [{agent_id}] Processing: {preview}")
```

**输出**:
```
🤖 [orchestrator] Processing: 设计一个完整的图书管理系统...
```

---

## 🎯 改进效果

### 日志对比

| 改进前 | 改进后 |
|--------|--------|
| ❌ 看不出哪个 agent | ✅ 大写显示 agent_id |
| ❌ 无消息预览 | ✅ 显示消息前 80 字符 |
| ❌ 格式不统一 | ✅ 使用 emoji 图标 |
| ❌ 难以快速扫描 | ✅ 清晰的分隔和缩进 |

---

## 📊 使用技巧

### 查看特定 Agent 日志
```bash
# 只看 orchestrator
nanobot gateway --multi -i 2>&1 | grep "\[ORCHESTRATOR\]"

# 只看 coding
nanobot gateway --multi -i 2>&1 | grep "\[CODING\]"
```

### 查看消息路由
```bash
nanobot gateway --multi -i 2>&1 | grep "📥"
```

### 查看处理过程
```bash
nanobot gateway --multi -i 2>&1 | grep "🤖"
```

### 查看工具调用
```bash
nanobot gateway --multi -i 2>&1 | grep "Tool call"
```

---

## 📝 完整日志示例

```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 帮我设计一个图书管理系统...

🤖 [orchestrator] Processing: 帮我设计一个图书管理系统...

🔄 Tool call: create_implementation_plan({...})
🔄 Tool call: read_file({...})
🔄 Tool call: shell({...})
🔄 Tool call: write_file({...})

✅ Agent orchestrator completed task in 15.2s
```

---

## 🔍 故障排查

### 错误: `cannot access local variable`

**原因**: 变量在使用前未定义

**解决**: 确保变量定义在使用之前
```python
# ❌ 错误
result = some_func(value)
value = get_value()

# ✅ 正确
value = get_value()
result = some_func(value)
```

---

## 📚 相关文档

- `GATEWAY_INTERACTIVE_USAGE.md` - Gateway 使用指南
- `AGENT_TEAM_CONFIG.md` - Agent Team 配置
- `AGENT_TEAM_LOGGING.md` - 日志详细说明

---

**修复完成时间**: 2026-03-04
**修复文件**: 
- `nanobot/gateway/manager.py` (日志增强)
- `nanobot/agent/loop.py` (变量顺序修复)
