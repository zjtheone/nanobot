# Agent Team 日志格式说明

## 📊 日志图标说明

| 图标 | 说明 | 示例 |
|------|------|------|
| 📥 | 消息路由 | `[ORCHESTRATOR] Routing message` |
| 🤖 | 消息处理 | `[orchestrator] Processing` |
| 🔄 | 工具调用 | `[coding] Tool call: write_file` |
| ✅ | 任务完成 | `Agent xxx completed` |

---

## 🎯 日志层级

### 1. 消息路由（Gateway 层）
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 实现完整的打卡系统...
```
**说明**: 显示消息路由到哪个 agent

---

### 2. 消息处理（Agent 层）
```
🤖 [orchestrator] Processing: 实现完整的打卡系统...
```
**说明**: 显示哪个 agent 在处理消息

---

### 3. 工具调用（子 Agent 层）⭐ **新增**
```
🔄 [orchestrator] Tool call: create_implementation_plan({...})
🔄 [coding] Tool call: write_file({...})
🔄 [research] Tool call: web_search({...})
```
**说明**: 
- 显示**具体哪个子 agent**在执行工具
- orchestrator 直接执行的工具显示 `[orchestrator]`
- spawn 的子 agent 执行的工具显示子 agent 的 ID

---

## 📝 完整日志示例

### 场景 1: Orchestrator 直接执行
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 设计一个系统架构...

🤖 [orchestrator] Processing: 设计一个系统架构...

🔄 [orchestrator] Tool call: create_implementation_plan({...})
🔄 [orchestrator] Tool call: read_file({...})
🔄 [orchestrator] Tool call: write_file({...})

✅ Agent orchestrator completed task in 15.2s
```

---

### 场景 2: Orchestrator + Workers 协作
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 开发一个完整的打卡系统...

🤖 [orchestrator] Processing: 开发一个完整的打卡系统...

🔄 [orchestrator] Tool call: create_implementation_plan({...})

# Orchestrator 分解任务，spawn 多个 worker
🔄 [worker-1] Tool call: web_search({...})
🔄 [worker-2] Tool call: write_file({...})
🔄 [worker-3] Tool call: shell({...})

# Worker 完成后，orchestrator 继续
🔄 [orchestrator] Tool call: update_plan_step({...})
🔄 [orchestrator] Tool call: write_file({...})

✅ Agent orchestrator completed task in 45.8s
```

---

### 场景 3: 多 Agent 并行
```
📥 [CODING] Routing message from cli:interactive
   Content: 实现用户登录功能...

🤖 [coding] Processing: 实现用户登录功能...

🔄 [coding] Tool call: write_file({...})
🔄 [coding] Tool call: exec({...})

# 同时另一个 agent 也在处理
📥 [REVIEWER] Routing message from cli:interactive
   Content: 审查代码...

🤖 [reviewer] Processing: 审查代码...

🔄 [reviewer] Tool call: read_file({...})
🔄 [reviewer] Tool call: edit_file({...})
```

---

## 🔍 日志过滤技巧

### 只看特定 Agent
```bash
# 只看 orchestrator
nanobot gateway --multi -i 2>&1 | grep "\[orchestrator\]"

# 只看 coding
nanobot gateway --multi -i 2>&1 | grep "\[coding\]"
```

### 只看工具调用
```bash
nanobot gateway --multi -i 2>&1 | grep "🔄"
```

### 只看消息路由
```bash
nanobot gateway --multi -i 2>&1 | grep "📥"
```

### 只看特定工具
```bash
# 只看文件写入
nanobot gateway --multi -i 2>&1 | grep "Tool call: write_file"

# 只看 shell 命令
nanobot gateway --multi -i 2>&1 | grep "Tool call: shell"
```

---

## 📋 日志级别

| 级别 | 说明 | 颜色 |
|------|------|------|
| INFO | 正常执行 | 白色 |
| DEBUG | 详细信息 | 灰色 |
| WARNING | 警告 | 黄色 |
| ERROR | 错误 | 红色 |

---

## 🎯 实际案例

### 案例 1: 打卡系统开发
```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 实现完整的打卡系统...

🤖 [orchestrator] Processing: 实现完整的打卡系统...

🔄 [orchestrator] Tool call: create_implementation_plan({...})
🔄 [orchestrator] Tool call: shell({...})
🔄 [orchestrator] Tool call: write_file({path: "requirements.txt"})
🔄 [orchestrator] Tool call: write_file({path: "app/config.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/models/employee.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/models/attendance.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/schemas/employee.py"})
🔄 [orchestrator] Tool call: write_file({path: "app/api/employees.py"})

✅ Agent orchestrator completed task in 120.5s
```

---

## 📚 相关文档

- `GATEWAY_INTERACTIVE_USAGE.md` - Gateway 使用指南
- `AGENT_TEAM_CONFIG.md` - Agent Team 配置
- `AGENT_TEAM_FIX_SUMMARY.md` - 修复总结

---

**最后更新**: 2026-03-04
**版本**: 2.0 (带子 Agent 标识)
