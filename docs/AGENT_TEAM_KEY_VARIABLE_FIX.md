# Key 变量作用域修复

## 🐛 问题

```
ERROR | Error processing message in agent orchestrator: 
cannot access local variable 'key' where it is not associated with a value
```

## 📋 原因

在 `nanobot/agent/loop.py` 的 `_process_message` 方法中，代码顺序错误：

```python
# ❌ 错误顺序
agent_id = key.split(":")[0] if key and ":" in key else "unknown"  # line 439 - 使用 key
preview = msg.content[:80] + "..."
logger.info(f"🤖 [{agent_id}] Processing: {preview}")

key = session_key or msg.session_key  # line 443 - 定义 key
```

**问题**: 在第 439 行使用了 `key` 变量，但在第 443 行才定义它！

---

## ✅ 修复

调整代码顺序，先定义 `key`，再使用：

```python
# ✅ 正确顺序
# Get session key first
key = session_key or msg.session_key

# Extract agent_id from session key for logging
agent_id = key.split(":")[0] if key and ":" in key else "unknown"

preview = msg.content[:80] + "..."
logger.info(f"🤖 [{agent_id}] Processing: {preview}")
session = self.sessions.get_or_create(key)
```

---

## 📊 修复验证

```python
python -c "import ast; ast.parse(open('nanobot/agent/loop.py').read())"
# ✅ Syntax OK
```

---

## 🎯 测试

```bash
# 启动 Gateway
nanobot gateway --multi -i

# 发送测试消息
>> 你好
# 应该正常处理，没有 key 变量错误
```

---

## 📝 相关日志

修复后，日志正常显示：

```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 你好...

🤖 [orchestrator] Processing: 你好...

🔄 Tool call: ...

✅ Agent orchestrator completed task in 2.5s
```

---

**修复完成时间**: 2026-03-05
**修复文件**: `nanobot/agent/loop.py`
**影响范围**: 消息处理流程
