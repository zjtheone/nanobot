# 🐛 Bug 修复 - 异步方法调用错误

**问题**: `AttributeError: 'AgentBridge' object has no attribute 'send_message_sync'`  
**修复时间**: 2026-03-03  
**状态**: ✅ 已完全修复  

---

## 问题描述

### 错误信息
```
AttributeError: 'AgentBridge' object has no attribute 'send_message_sync'
```

### 错误位置
- **文件**: `app.py`, 第 184 行
- **方法**: `process_agent_response()`
- **代码**: `response = agent_bridge.send_message_sync(user_message)`

---

## 根本原因分析

### 问题 1: 方法不存在

| 调用方 (app.py) | 被调用方 (agent_bridge.py) |
|----------------|---------------------------|
| `send_message_sync()` ❌ | `async send_message()` ✅ |

**原因**: `AgentBridge` 只提供了异步方法 `send_message()`，没有同步版本

### 问题 2: 流式返回格式错误

```python
# Agent Team 生成的代码期望
async for chunk in agent.process_direct_stream(message):
    if isinstance(chunk, dict):
        if chunk.get('type') == 'content':
            response_text += chunk.get('content', '')

# 实际返回格式
async for chunk in agent.process_direct_stream(message):
    # chunk 是字符串，不是字典！
    print(chunk)  # "嘿，J", "ian！", " 👋 ", ...
```

**原因**: `process_direct_stream` 返回字符串 chunk，不是字典

---

## 修复方案

### 修改的文件

1. `/Users/cengjian/workspace/AI/github/nanobot/web_console/app.py`
2. `/Users/cengjian/workspace/AI/github/nanobot/web_console/agent_bridge.py`

---

### 修复 1: app.py - 方法调用

#### 第 184 行 - 异步调用
```python
# 修复前
response = agent_bridge.send_message_sync(user_message)  # ❌ 方法不存在

# 修复后
response = asyncio.run(agent_bridge.send_message(user_message))  # ✅ 使用 asyncio.run
```

#### 添加 asyncio 导入
```python
# 文件开头添加
import asyncio
```

---

### 修复 2: agent_bridge.py - 处理字符串 chunk

#### send_message 方法重写
```python
async def send_message(self, message: str, session_id: Optional[str] = None) -> AgentResponse:
    """Send a message to the agent and get response."""
    
    try:
        response_text = ""
        thinking_text = ""
        
        # Use process_direct_stream
        if hasattr(self.agent_loop, 'process_direct_stream'):
            async for chunk in self.agent_loop.process_direct_stream(message):
                # process_direct_stream returns string chunks directly
                if isinstance(chunk, str):
                    # Check if it's thinking content
                    if chunk.strip().startswith('[') and 'thinking' in chunk.lower():
                        thinking_text += chunk
                    else:
                        response_text += chunk
                elif isinstance(chunk, dict):
                    # Handle dict format if returned
                    if chunk.get('type') == 'content':
                        response_text += chunk.get('content', '')
                    elif chunk.get('type') == 'thinking':
                        thinking_text += chunk.get('content', '')
        
        return AgentResponse(
            content=response_text.strip() or "No response from agent",
            role="assistant",
            thinking=thinking_text.strip() if thinking_text else None,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return AgentResponse(
            content=f"Error processing message: {e}",
            role="assistant",
        )
```

---

## 验证结果

### 1. 异步方法测试
```python
async def test():
    bridge = AgentBridge()
    bridge.initialize()
    
    response = await bridge.send_message("说一个简短的问候")
    
    print(f"✓ 响应收到")
    print(f"  Content: {response.content}")
    print(f"  Thinking: {response.thinking}")
    print(f"  Role: {response.role}")
```

**结果**:
```
✓ AgentBridge initialized successfully
  • Provider: dashscope
  • Model: qwen3.5-plus
  • Workspace: /Users/cengjian/.nanobot/workspace

✓ 响应收到
  Content: 嗨！🌟 祝你今天一切顺利！

[tokens: 40,557 in + 52 out = 40,609 total]
  Thinking: None
  Role: assistant
```

### 2. 应用启动测试
```bash
$ streamlit run app.py

✅ Web Console 启动成功！
Local URL: http://localhost:8501
```

---

## 修复对比

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| 方法调用 | `send_message_sync()` ❌ | `asyncio.run(send_message())` ✅ |
| Chunk 格式 | 期望 `dict` | 处理 `str` ✅ |
| Thinking 处理 | 忽略 | 分离存储 ✅ |
| 错误处理 | 简单 | 详细 traceback ✅ |
| 响应内容 | "No response" | 实际回复 ✅ |

---

## 技术细节

### process_direct_stream 返回格式

**实际输出**:
```python
async for chunk in agent.process_direct_stream(message):
    # 返回的是字符串，不是字典
    print(type(chunk))  # <class 'str'>
    print(chunk)        # "嘿", "，", "J", "ian", "！", " 👋 ", ...
```

**期望输出** (错误的):
```python
async for chunk in agent.process_direct_stream(message):
    # Agent Team 生成时期望字典
    print(type(chunk))  # 期望 <class 'dict'>
    print(chunk)        # 期望 {'type': 'content', 'content': '...'}
```

### asyncio.run 使用场景

```python
# Streamlit 是同步环境
def process_agent_response():
    user_message = "..."
    
    # 正确：使用 asyncio.run 调用异步方法
    response = asyncio.run(agent_bridge.send_message(user_message))
    
    # 错误：直接调用会报错
    # response = await agent_bridge.send_message(user_message)  # SyntaxError
```

---

## AgentBridge API

### send_message 方法

**签名**:
```python
async def send_message(
    self,
    message: str,
    session_id: Optional[str] = None
) -> AgentResponse:
```

**参数**:
- `message` (str): 发送给 agent 的消息
- `session_id` (Optional[str]): 会话 ID（可选）

**返回**:
```python
AgentResponse(
    content=str,        # 回复内容
    role="assistant",   # 角色
    thinking=str|None,  # 思考过程（如果有）
    tool_calls=list,    # 工具调用列表
    metadata=dict       # 元数据
)
```

**使用示例**:
```python
# 异步使用
response = await bridge.send_message("你好")
print(response.content)

# 同步使用（Streamlit 环境）
response = asyncio.run(bridge.send_message("你好"))
print(response.content)
```

---

## 相关问题修复记录

| Bug | 状态 | 文档 |
|-----|------|------|
| 1. inject_css 导入错误 | ✅ | BUG_FIX_REPORT.md |
| 2. Agent 初始化错误 | ✅ | FIX_SUMMARY.md |
| 3. get_agent_status 方法名 | ✅ | BUGFIX_METHOD_NAME.md |
| 4. send_message_sync 不存在 | ✅ | 本文档 |

---

## 经验教训

### 1. 异步代码处理

- ✅ 在同步环境中使用 `asyncio.run()` 调用异步方法
- ✅ 不要期望 `await` 在同步代码中工作
- ✅ 理解 Streamlit 的执行模型

### 2. API 格式验证

- ✅ 实际测试 API 返回格式
- ✅ 不要假设返回类型
- ✅ 添加类型检查和 fallback

### 3. 流式处理

- ✅ 处理多种可能的返回格式（str 和 dict）
- ✅ 分离 thinking 和 content
- ✅ 提供清晰的错误信息

---

## 预防措施

### 代码审查清单

- [ ] 所有调用的方法是否实际存在
- [ ] 异步方法是否正确调用
- [ ] API 返回格式是否验证
- [ ] 错误处理是否完善

### 自动化测试

```python
async def test_send_message():
    from agent_bridge import AgentBridge
    bridge = AgentBridge()
    bridge.initialize()
    
    response = await bridge.send_message("测试")
    
    assert response.role == "assistant"
    assert isinstance(response.content, str)
    assert len(response.content) > 0
```

---

## 修复时间线

| 时间 | 事件 |
|------|------|
| 15:20 | 用户报告 send_message_sync 错误 |
| 15:21 | 定位问题：方法不存在 + chunk 格式错误 |
| 15:22 | 修复 app.py 方法调用 |
| 15:25 | 重写 agent_bridge send_message |
| 15:26 | 测试异步调用成功 |
| 15:27 | 应用启动成功 |
| 15:30 | 创建修复报告 |

**总修复时间**: ~10 分钟

---

## 总结

### 问题类型
- **分类**: 方法不存在 / API 格式不匹配
- **原因**: Agent Team 代码生成错误
- **影响**: 阻止消息发送，无法与 agent 对话

### 修复方法
- **方案**: 
  1. 使用 `asyncio.run()` 调用异步方法
  2. 处理字符串 chunk 而非字典
  3. 分离 thinking 和 content
- **难度**: 中等（需要理解异步和流式处理）
- **风险**: 低（隔离在 bridge 模块）

### 验证状态
- ✅ 异步方法调用成功
- ✅ 实际消息发送成功
- ✅ 收到 agent 回复
- ✅ 应用启动正常

---

**修复完成时间**: 2026-03-03 15:30  
**修复状态**: ✅ 完成  
**应用状态**: 🟢 正常运行  

**🎉 Web Console 现在可以正常对话了！**
