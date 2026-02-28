# Nanobot CLI 交互体验优化

日期：2026-02-23

## 概述

为 nanobot agent 交互模式增加实时反馈，包括：思考过程展示、迭代步骤进度、Tool 执行前提示、Agent 状态指示。

采用回调事件架构，AgentLoop 中增加 4 个可选回调（默认 None），CLI 层通过 ToolProgressDisplay 实现展示，不影响现有功能。

## 修改文件

### 1. `nanobot/providers/base.py`

`LLMStreamChunk` 增加 `reasoning_content` 字段：

```python
@dataclass
class LLMStreamChunk:
    # ... 原有字段 ...
    reasoning_content: str | None = None  # 新增
```

### 2. `nanobot/providers/litellm_provider.py`

`stream_chat()` 中捕获 `delta.reasoning_content`：

```python
# Reasoning content (DeepSeek-R1, Claude extended thinking, etc.)
if hasattr(delta, "reasoning_content") and delta.reasoning_content:
    sc.reasoning_content = delta.reasoning_content
```

### 3. `nanobot/agent/loop.py`

**新增 4 个回调参数：**

```python
def __init__(self, ...,
    on_thinking: Callable[[str], None] | None = None,
    on_iteration: Callable[[int, int], None] | None = None,
    on_tool_start: Callable[[str, dict], None] | None = None,
    on_status: Callable[[str], None] | None = None,
):
```

**触发点（`process_direct_stream` 和 `_process_message` 中均已添加）：**

| 回调 | 触发位置 | 说明 |
|------|---------|------|
| `on_iteration(iteration, max)` | while 循环顶部 | 步骤进度 |
| `on_status("thinking")` | LLM 调用前 | 开始思考 |
| `on_thinking(content)` | streaming 中收到 reasoning_content / 非 streaming 收到 response.reasoning_content | 思考内容 |
| `on_status("executing_tools")` | tool 执行前 | 开始执行工具 |
| `on_tool_start(name, args)` | 每个 tool 执行前 | 工具启动提示 |
| `on_status("compacting_context")` | `_compact_context()` 触发时 | 上下文压缩 |

### 4. `nanobot/cli/progress.py`

`ToolProgressDisplay` 新增 3 个方法：

```python
def on_thinking(self, content: str) -> None:
    """dim italic 样式展示 reasoning content"""

def on_iteration(self, iteration: int, max_iterations: int) -> None:
    """第 1 步不显示，第 2 步起显示 ── Step N/max ──"""

def on_status(self, status: str) -> None:
    """显示 🤔/🔧/📦 状态标签"""
```

### 5. `nanobot/cli/commands.py`

AgentLoop 实例化时接线：

```python
agent_loop = AgentLoop(
    ...,
    on_thinking=progress.on_thinking,
    on_iteration=progress.on_iteration,
    on_tool_start=progress.on_tool_start,
    on_status=progress.on_status,
)
```

## 预期效果

```
You: refactor the auth module to use JWT

  🤔 Thinking...
  💭 Thinking...
  用户需要重构认证模块，我先读取当前代码...

  ⚙ read_file(src/auth.py)
  ✓ read_file → 142 lines (0.01s)

  [streaming 文本输出...]

  ── Step 2/20 ──
  🤔 Thinking...

  ⚙ write_file(src/auth.py)
  ✓ write_file → wrote 198 lines (0.02s)

  [最终回复...]

[tokens: 12,450 in + 3,200 out = 15,650 total]
```

## 验证

- 全部 63 个现有测试通过
- 所有回调默认 None，不影响 gateway 模式、测试、非 CLI 使用场景

---

## 优化: Thinking 输出换行过于频繁

### 问题

`on_thinking()` 以小 chunk（单个 token）为单位被调用，每个 chunk 通过 `console.print()` 输出会自动追加换行，导致思考内容每个词独占一行。

### 修复

**`nanobot/cli/progress.py`** — 改用 `sys.stderr.write()` 内联输出：

```python
_DIM_ITALIC = "\033[2;3m"
_RESET = "\033[0m"

def _end_thinking(self) -> None:
    """关闭当前 thinking 行的 ANSI 样式"""
    if self._thinking_has_content:
        sys.stderr.write(f"{_RESET}\n")
        self._thinking_has_content = False

def on_thinking(self, content: str) -> None:
    """流式内联输出，不强制换行"""
    if not self._thinking_has_content:
        sys.stderr.write(f"  {_DIM_ITALIC}")
        self._thinking_has_content = True
    sys.stderr.write(content)
    sys.stderr.flush()
```

`on_iteration()`、`on_status()`、`on_tool_start()` 均在输出前调用 `_end_thinking()` 确保 thinking 块正确结束。

---

## 功能: 计划步骤追踪与进度展示

### 概述

创建计划后自动解析为可追踪步骤，LLM 执行时通过工具标记步骤状态，CLI 实时显示 checklist 进度，进度注入后续 LLM 上下文。

### 修改文件

#### 1. `nanobot/agent/planner.py` — 步骤数据模型与追踪

新增 `PlanStep` dataclass 和 Planner 追踪方法：

```python
@dataclass
class PlanStep:
    id: int
    title: str
    status: str = "pending"  # pending | in_progress | completed
```

Planner 新增：
- `parse_steps(plan_content)` — 从 `####` 行解析步骤列表
- `update_step(step_id, status)` — 更新状态并触发回调
- `get_progress_context()` — 生成 `[x]/[>]/[ ]` checklist 文本供上下文注入
- `_save_steps()` / `_load_steps()` — JSON 持久化到 `implementation_plan_progress.json`

#### 2. `nanobot/agent/tools/planner.py` — 新增 UpdatePlanStepTool

```python
class UpdatePlanStepTool(Tool):
    name = "update_plan_step"
    # parameters: step_id (int) + status (enum: in_progress/completed)
    # execute: 调用 planner.update_step()，返回当前进度摘要
```

`PlanTool.execute()` 修改：创建计划后自动调用 `parse_steps()`。

#### 3. `nanobot/agent/context.py` — 上下文注入

`build_messages()` 新增 `plan_context: str | None` 参数，非空时追加到系统提示末尾。

#### 4. `nanobot/cli/progress.py` — CLI checklist 展示

`ToolProgressDisplay` 新增 `on_plan_progress(steps)` 方法：

```python
def on_plan_progress(self, steps: list) -> None:
    # ✓ 绿色已完成  ▸ 黄色进行中  ○ 灰色待办
```

#### 5. `nanobot/agent/loop.py` — 集成

- 构造函数新增 `on_plan_progress` 回调参数
- `_register_default_tools()` 注册 `UpdatePlanStepTool`，连接回调（dataclass → dict）
- `_process_message()` 和 `process_direct_stream()` 传入 `plan_context`

#### 6. `nanobot/cli/commands.py` — 连接回调

```python
agent_loop = AgentLoop(..., on_plan_progress=progress.on_plan_progress)
```

### 预期效果

```
You: 实现用户认证模块

  🤔 Thinking...
  💭 Thinking...
  分析需求，先创建实现计划...

  ⚙ create_implementation_plan(...)
  ✓ create_implementation_plan → Plan created (5 steps)

  📋 Plan Progress:
  ○ 1. [MODIFY] src/auth/handler.py
  ○ 2. [NEW] src/auth/jwt.py
  ○ 3. [MODIFY] src/middleware.py
  ○ 4. [NEW] tests/test_auth.py
  ○ 5. [MODIFY] src/config.py

  ── Step 2/20 ──
  ⚙ update_plan_step(1, in_progress)

  📋 Plan Progress:
  ▸ 1. [MODIFY] src/auth/handler.py
  ○ 2. [NEW] src/auth/jwt.py
  ○ 3. [MODIFY] src/middleware.py
  ○ 4. [NEW] tests/test_auth.py
  ○ 5. [MODIFY] src/config.py

  ...

  📋 Plan Progress:
  ✓ 1. [MODIFY] src/auth/handler.py
  ✓ 2. [NEW] src/auth/jwt.py
  ✓ 3. [MODIFY] src/middleware.py
  ▸ 4. [NEW] tests/test_auth.py
  ○ 5. [MODIFY] src/config.py
```

### 问题

使用 `deepseek-reasoner` 模型时，第二轮 LLM 调用报错：

```
Missing `reasoning_content` field in the assistant message at message index 47
```

### 根因

1. `process_direct_stream` streaming 模式下，`reasoning_content` 只触发了回调展示，没有累积并传递给 `add_assistant_message`，导致历史消息中 assistant 消息缺少该字段
2. `context.py` 中 `if reasoning_content:` 会跳过空字符串，而 DeepSeek-R1 API 要求所有 assistant 消息都必须包含 `reasoning_content` 字段

### 修复

**`nanobot/agent/loop.py`** — `process_direct_stream` 中累积 reasoning_content 并传递：

```python
# 新增累积变量
collected_reasoning = ""

# streaming 循环中累积
if chunk.reasoning_content:
    collected_reasoning += chunk.reasoning_content

# 两处 add_assistant_message 调用都传递 reasoning_content
messages = self.context.add_assistant_message(
    messages, collected_content or None, tool_call_dicts,
    reasoning_content=collected_reasoning or None,
)
```

**`nanobot/agent/context.py`** — 允许空字符串的 reasoning_content：

```python
# 修改前
if reasoning_content:
    msg["reasoning_content"] = reasoning_content

# 修改后
if reasoning_content is not None:
    msg["reasoning_content"] = reasoning_content
```
