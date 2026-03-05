# Team Exec 问题根因分析

## 🐛 问题确认

您的观察是正确的：**仍然是一个 agent 在执行，不是多 agent 并行！**

### 日志证据

```
🤖 [team] Processing: Task: 实现库房管理系统...
🔄 [team] Tool call: spawn({"batch": [...]})  ← 调用了 spawn
🔄 [team] Tool call: spawn({"label": "coding-core", ...})
🔄 [team] Tool call: exec({...})
🔄 [team] Tool call: write_file({...})  ← 还是同一个 agent 在写文件
... (全是 [team])
```

**关键观察**: 没有看到 `🤖 [coding-worker] Processing` 或 `🤖 [reviewer-worker] Processing` 的日志！

---

## 🔍 根本原因

### 原因 1: Session Key 格式问题

```python
# 当前代码
session_key=f"team:{team_name}:{task[:50]}"

# 导致 agent_id 提取为 "team" 而不是 "orchestrator"
agent_id = key.split(":")[0]  # "team"
```

### 原因 2: Gateway 生命周期

```python
# teams exec 流程
await gw.start()
result = await orchestrator.process_direct(...)  # Orchestrator 执行
await gw.stop()  # ← 立即关闭！
```

**问题**: Gateway 在 spawned workers 完成前就关闭了！

### 原因 3: Spawn 的异步性

```python
# Orchestrator 调用 spawn
await spawn(batch=[...], wait=False)  # 默认不等待

# Spawn 返回后，orchestrator 继续执行
# 但 workers 可能还在后台运行
# Gateway 关闭时，workers 被终止
```

---

## ✅ 正确的解决方案

### 方案 A: 增强等待逻辑（复杂）

```python
# 需要跟踪 spawned workers
# 等待所有 workers 完成
# 复杂且容易出错
```

### 方案 B: 直接调用 Team Members（推荐）⭐

**不通过 orchestrator 分解，直接调用 team members！**

```python
# 伪代码
async def exec_team(team_name, task):
    # 1. 获取 team 配置
    team = get_team(team_name)
    
    # 2. 直接 spawn team members
    workers = []
    for member_id in team.members:
        worker = await spawn(
            task=f"{member_id}: {task}",
            agent_id=member_id,
            wait=False
        )
        workers.append(worker)
    
    # 3. 等待所有 workers
    results = await asyncio.gather(*workers)
    
    # 4. 聚合结果
    return aggregate(results)
```

**优点**:
- 100% 确保多 agent 执行
- 不依赖 orchestrator 的决策
- 简单直接

---

## 🎯 实施方案

### 修改 `nanobot/cli/teams.py`

**核心思路**: 不调用 orchestrator，直接 spawn team members！

```python
@app.command("exec")
def exec_team(team_name, task, timeout=600, wait=True):
    """Execute task using team members directly."""
    
    # 1. Get team config
    team = get_team(team_name)
    
    # 2. Start gateway
    gw = MultiAgentGateway(config, bus)
    await gw.start()
    
    # 3. Spawn team members directly
    console.print(f"🚀 Spawning {len(team.members)} workers...")
    
    workers = []
    for member_id in team.members:
        member_task = f"""
You are {member_id} from team {team_name}.

Task: {task}

Your role:
- If you are 'coding': Implement the code
- If you are 'research': Research best practices
- If you are 'reviewer': Review code quality
- If you are 'debugger': Test and debug

Provide your contribution to the team project.
"""
        worker = asyncio.create_task(
            gw.get_agent(member_id).process_direct(
                content=member_task,
                session_key=f"team:{team_name}:{member_id}",
                channel="cli",
                chat_id="team-exec"
            )
        )
        workers.append((member_id, worker))
    
    # 4. Wait for all workers
    console.print("⏳ Waiting for workers to complete...")
    
    results = {}
    for member_id, worker in workers:
        try:
            result = await asyncio.wait_for(worker, timeout=timeout)
            results[member_id] = result
            console.print(f"✅ {member_id} completed")
        except Exception as e:
            console.print(f"❌ {member_id} failed: {e}")
    
    # 5. Aggregate results
    console.print("\n📊 Team Results:")
    for member_id, result in results.items():
        console.print(f"\n[cyan]{member_id}:[/cyan]")
        console.print(result[:500])
    
    await gw.stop()
```

---

## 📊 对比

| 方式 | 多 Agent 保证 | 复杂度 | 推荐度 |
|------|------------|--------|--------|
| 通过 orchestrator | ❌ 依赖 LLM 决策 | 高 | ❌ |
| 直接 spawn members | ✅ 100% 保证 | 低 | ✅ |

---

## 💡 结论

**当前 `teams exec` 的问题**:
- 依赖 orchestrator  spawn workers（LLM 可能选择不 spawn）
- Gateway 在 workers 完成前关闭
- 没有真正等待 spawned workers

**推荐修复方案**:
- 不通过 orchestrator
- 直接 spawn team members
- 显式等待所有 workers 完成

---

**建议**: 重新设计 `teams exec` 命令，采用直接 spawn 方案！

