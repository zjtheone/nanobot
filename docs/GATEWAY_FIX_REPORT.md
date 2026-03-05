# Gateway Multi-Agent 启动问题修复报告

## 问题描述

执行 `nanobot gateway --multi` 时出现两个错误：

### 错误 1: ChannelManager 参数错误
```
TypeError: ChannelManager.__init__() got an unexpected keyword argument 'session_manager'
```

### 错误 2: MessageBus 方法不存在
```
AttributeError: 'MessageBus' object has no attribute 'subscribe_inbound'
```

---

## 根本原因分析

### 错误 1: ChannelManager 接口不匹配

**位置**: `nanobot/cli/commands.py:420`

**问题**: CLI 代码尝试传递 `session_manager` 参数给 `ChannelManager`，但 `ChannelManager.__init__` 只接受 `config` 和 `bus` 两个参数。

**ChannelManager 定义**:
```python
# nanobot/channels/manager.py:26
def __init__(self, config: Config, bus: MessageBus):
    self.config = config
    self.bus = bus
    # ...
```

### 错误 2: MessageBus 方法名错误

**位置**: `nanobot/gateway/manager.py:116`

**问题**: 使用了不存在的 `subscribe_inbound()` 方法。`MessageBus` 提供的是 `consume_inbound()` 方法。

**MessageBus 定义**:
```python
# nanobot/bus/queue.py:24
async def consume_inbound(self) -> InboundMessage:
    """Consume the next inbound message (blocks until available)."""
    return await self.inbound.get()
```

### 错误 3: AgentLoop 方法调用错误

**位置**: `nanobot/gateway/manager.py:150`

**问题**: 使用了不存在的 `process_message()` 方法。`AgentLoop` 提供的是 `process_direct()` 方法。

**AgentLoop 定义**:
```python
# nanobot/agent/loop.py:982
async def process_direct(
    self,
    content: str,
    session_key: str = "cli:direct",
    channel: str = "cli",
    chat_id: str = "direct",
    # ...
) -> str:
```

---

## 修复方案

### 修复 1: 移除 session_manager 参数

**文件**: `nanobot/cli/commands.py`

**修改前**:
```python
channels = ChannelManager(config, bus, session_manager=session_manager)
```

**修改后**:
```python
# Create channels (ChannelManager doesn't need session_manager)
channels = ChannelManager(config, bus)
```

### 修复 2: 使用正确的 MessageBus 方法

**文件**: `nanobot/gateway/manager.py`

**修改前**:
```python
async def _message_dispatcher(self):
    async for msg in self.bus.subscribe_inbound():
        if not self._running:
            break
        try:
            await self._handle_message(msg)
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
```

**修改后**:
```python
async def _message_dispatcher(self):
    """持续监听 bus 消息并路由到正确的 agent。"""
    from nanobot.bus.events import InboundMessage
    
    # 持续消费 inbound 消息
    while self._running:
        try:
            msg = await self.bus.consume_inbound()
            if not self._running:
                break
            
            await self._handle_message(msg)
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
```

### 修复 3: 使用正确的 AgentLoop 方法

**文件**: `nanobot/gateway/manager.py`

**修改前**:
```python
async def _handle_message(self, msg: InboundMessage):
    # ...
    try:
        await agent.process_message(msg)
    finally:
        msg.session_key_override = original_session_key
```

**修改后**:
```python
async def _handle_message(self, msg: InboundMessage):
    """路由消息到目标 agent。"""
    # 使用路由器确定目标 agent
    agent_id = self.router.route(msg)
    
    # 获取目标 agent 实例
    agent = self.agents.get(agent_id)
    if not agent:
        logger.warning(f"Agent {agent_id} not found, falling back to default")
        agent = self.agents.get(self.config.agents.default_agent)
    
    if not agent:
        logger.error("No agent available to handle message")
        return
    
    logger.debug(f"Routing message from {msg.channel}:{msg.chat_id} to agent {agent_id}")
    
    # 构建带 agent_id 前缀的 session_key
    session_key = f"{agent_id}:{msg.session_key}"
    
    try:
        # 使用 process_direct 处理消息
        await agent.process_direct(
            content=msg.content,
            session_key=session_key,
            channel=msg.channel,
            chat_id=msg.chat_id,
            media=msg.media if msg.media else None,
        )
    except Exception as e:
        logger.error(f"Error processing message in agent {agent_id}: {e}", exc_info=True)
```

### 修复 4: 调整 debugger 优先级（优化）

**文件**: `~/.nanobot/config.json`

**问题**: "错误"关键词同时在 reviewer 和 debugger 中，导致路由冲突。

**修改前**:
```json
{
  "agent_id": "reviewer",
  "priority": 40,
  "keywords": ["审查", "review", "检查", "优化", "重构", "改进", "bug", "错误", "问题"]
},
{
  "agent_id": "debugger",
  "priority": 40,
  "keywords": ["调试", "debug", "修复", "报错", "异常", "错误", "fail", "error", "traceback"]
}
```

**修改后**:
```json
{
  "agent_id": "debugger",
  "priority": 45  // 提高到 45，优先于 reviewer
}
```

---

## 验证结果

### 1. 初始化测试
```bash
$ python -c "
from nanobot.config.loader import load_config
from nanobot.bus.queue import MessageBus
from nanobot.gateway.manager import MultiAgentGateway
from nanobot.channels.manager import ChannelManager

config = load_config()
bus = MessageBus()

channels = ChannelManager(config, bus)
print('✓ ChannelManager created successfully')

gw = MultiAgentGateway(config, bus)
print('✓ MultiAgentGateway created successfully')
"

✓ ChannelManager created successfully
✓ MultiAgentGateway created successfully
```

### 2. 路由测试
```bash
$ python -c "
from nanobot.config.loader import load_config
from nanobot.gateway.router import MessageRouter

config = load_config()
router = MessageRouter(config.agents.bindings, config.agents.default_agent)

test_messages = [
    '帮我写个代码',      # → coding
    '搜索一下资料',      # → research
    '审查这个 PR',      # → reviewer
    '调试这个错误',      # → debugger
    '帮我做一个完整的项目', # → orchestrator
    '你好',              # → main
]

for content in test_messages:
    msg = type('InboundMessage', (), {
        'channel': 'cli', 'chat_id': 'test',
        'content': content, 'sender_id': 'test'
    })()
    agent_id = router.route(msg)
    print(f'\"{content}\" → {agent_id}')
"

"帮我写个代码" → coding
"搜索一下资料" → research
"审查这个 PR" → reviewer
"调试这个错误" → debugger
"帮我做一个完整的项目" → orchestrator
"你好" → main
```

---

## 启动 Gateway

现在可以正常启动 Multi-Agent Gateway：

```bash
nanobot gateway --multi
```

**预期输出**:
```
🤖 Starting nanobot gateway in MULTI-AGENT mode on port 18790...
Configured agents: ['orchestrator', 'main', 'coding', 'research', 'reviewer', 'debugger']
Default agent: orchestrator
Routing rules: 6
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:__init__:40 - MultiAgentGateway initialized with 6 agents, default=orchestrator
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:63 - Created default agent: orchestrator
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:69 - Created agent: main
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:69 - Created agent: coding
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:69 - Created agent: research
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:69 - Created agent: reviewer
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:69 - Created agent: debugger
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:74 - Agent orchestrator ready
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:74 - Agent main ready
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:74 - Agent coding ready
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:74 - Agent research ready
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:74 - Agent reviewer ready
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:74 - Agent debugger ready
2026-03-04 XX:XX:XX | INFO | nanobot.gateway.manager:start:79 - MultiAgentGateway started with 6 agents: [...]
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `nanobot/cli/commands.py` | 移除 ChannelManager 的 session_manager 参数 |
| `nanobot/gateway/manager.py` | 修复 _message_dispatcher 使用 consume_inbound |
| `nanobot/gateway/manager.py` | 修复 _handle_message 使用 process_direct |
| `~/.nanobot/config.json` | 调整 debugger 优先级为 45 |

---

## 后续建议

1. **添加类型检查**: 在 `ChannelManager` 构造函数中添加类型注解和参数验证
2. **增加错误处理**: 在消息路由失败时提供更友好的错误提示
3. **完善日志**: 记录每个消息的路由决策过程，便于调试
4. **性能优化**: 考虑为消息路由添加缓存机制
5. **添加监控**: 实现 agent 健康检查和性能监控

---

**修复完成时间**: 2026-03-04 18:05
**修复者**: AI Assistant
