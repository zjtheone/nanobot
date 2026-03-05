# Agent Team 日志使用指南

## ✅ 最终日志格式

### 日志流程

```
1. 📥 消息路由 → 显示接收消息的 agent
2. 🤖 消息处理 → 显示处理消息的 agent  
3. 🔄 工具调用 → 从上下文推断 agent
4. ✅ 任务完成 → 显示完成的 agent
```

---

## 📊 日志示例

### 完整工作流

```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 实现完整的打卡系统...

🤖 [orchestrator] Processing: 实现完整的打卡系统...

🔄 Tool call: create_implementation_plan({...})
🔄 Tool call: shell({...})
🔄 Tool call: write_file({path: "app/config.py"})
🔄 Tool call: write_file({path: "app/models/employee.py"})
🔄 Tool call: write_file({path: "app/api/employees.py"})

✅ Agent orchestrator completed task in 120.5s
```

**说明**:
- 📥 和 🤖 清楚显示是哪个 agent
- 🔄 工具调用紧跟在处理日志后，从上下文可知是同一个 agent
- ✅ 总结显示执行的 agent

---

## 🔍 查看日志技巧

### 查看消息路由
```bash
nanobot gateway --multi -i 2>&1 | grep "📥"
```

### 查看消息处理
```bash
nanobot gateway --multi -i 2>&1 | grep "🤖"
```

### 查看工具调用
```bash
nanobot gateway --multi -i 2>&1 | grep "🔄 Tool call"
```

### 查看任务完成
```bash
nanobot gateway --multi -i 2>&1 | grep "completed task"
```

### 查看完整流程
```bash
nanobot gateway --multi -i 2>&1 | grep -E "📥|🤖|🔄|✅"
```

---

## 📝 日志解读

### 场景 1: 单 Agent 执行
```
📥 [CODING] Routing message
🤖 [coding] Processing
🔄 Tool call: write_file
🔄 Tool call: exec
✅ Agent coding completed
```
**说明**: coding agent 独立完成所有工作

---

### 场景 2: Orchestrator 协调
```
📥 [ORCHESTRATOR] Routing message
🤖 [orchestrator] Processing
🔄 Tool call: create_implementation_plan
🔄 Tool call: write_file (创建项目结构)
🔄 Tool call: write_file (创建配置文件)
...
✅ Agent orchestrator completed in 120s
```
**说明**: orchestrator 直接执行所有任务

---

### 场景 3: 多 Agent 协作 (通过 spawn)
```
📥 [ORCHESTRATOR] Routing message
🤖 [orchestrator] Processing
🔄 Tool call: create_implementation_plan

# Spawn worker (在 agent 内部日志显示)
[worker-1] Processing: 搜索最佳实践
🔄 Tool call: web_search

# Worker 完成后，orchestrator 继续
🔄 Tool call: write_file (整合结果)
✅ Agent orchestrator completed
```
**说明**: orchestrator 分解任务给 worker，最后整合

---

## 🎯 最佳实践

### 1. 使用交互式模式
```bash
nanobot gateway --multi --interactive
```
这样可以看到所有实时日志。

### 2. 使用 tmux 分屏
```bash
tmux new -s nanobot
# 左侧：Gateway
# 右侧：输入消息
```

### 3. 日志过滤
```bash
# 只看关键日志
nanobot gateway --multi -i 2>&1 | \
  grep -E "📥|🤖|✅" | \
  grep -v "DEBUG"
```

---

## 📚 相关文档

- `GATEWAY_INTERACTIVE_USAGE.md` - Gateway 使用指南
- `AGENT_TEAM_CONFIG.md` - Agent Team 配置
- `AGENT_TEAM_FIX_SUMMARY.md` - 修复总结

---

**最后更新**: 2026-03-04
**状态**: ✅ 生产就绪
