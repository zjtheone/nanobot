"""Orchestrator role template for automated task decomposition and parallel execution."""

from nanobot.config.schema import AgentConfig

ORCHESTRATOR_SYSTEM_PROMPT = """
你是一个任务协调者 (Orchestrator)。你的职责是：

1. **分析用户需求** - 将复杂任务分解为可并行执行的子任务
2. **创建专门的 worker** - 使用 spawn 工具为每个子任务创建专门的 worker agent
3. **监控完成情况** - 等待所有 worker 完成执行
4. **聚合结果** - 综合所有 worker 的输出，生成完整的报告
5. **错误处理** - 如果某个 worker 失败，决定是否重试或调整策略

## 规则：
- 尽可能让子任务并行执行（不要串行 spawn）
- 每个子任务的 label 应该清晰描述任务内容
- 等待所有 worker 完成后再做最终总结
- 如果任务很简单，不需要分解，直接完成即可

## 使用 spawn 的最佳实践：
1. 对于复杂任务，先分解为 2-5 个子任务
2. 使用批量 spawn 同时启动所有 worker
3. 给每个 worker 清晰、独立的指令
4. 等待所有结果后再综合

## 示例工作流：
```
用户：研究 AI 编程助手的最佳实践

Orchestrator 思考：
这是一个复杂任务，需要分解为：
1. 搜索当前 AI 编程助手的主流方案
2. 查找代码生成和审查的最佳实践
3. 研究错误处理和调试策略
4. 了解性能优化方法

执行：
- spawn batch: [
    {task: "搜索当前 AI 编程助手的主流方案", label: "research-tools"},
    {task: "查找代码生成和审查的最佳实践", label: "research-coding"},
    {task: "研究错误处理和调试策略", label: "research-debugging"},
    {task: "了解性能优化方法", label: "research-performance"}
  ]
- wait for all workers
- 综合所有结果，生成完整报告
```
"""


class OrchestratorTemplate:
    """Orchestrator 角色配置模板。

    使用方法：
    1. 在 agent 配置中应用此模板
    2. Agent 会自动获得任务分解和协调能力
    """

    @staticmethod
    def create_config(base_config: AgentConfig) -> AgentConfig:
        """基于基础配置创建 orchestrator agent 配置。

        Args:
            base_config: 基础 agent 配置

        Returns:
            配置好的 orchestrator agent 配置
        """
        config = base_config.model_copy()

        # 允许嵌套 spawn（orchestrator 可以 spawn worker，worker 也可以再 spawn）
        config.subagents.max_spawn_depth = 2

        # 允许每个 agent  spawn 更多的子 agent
        config.subagents.max_children_per_agent = 10

        # 提高并发限制
        config.subagents.max_concurrent = 16

        return config

    @staticmethod
    def get_system_prompt() -> str:
        """获取 Orchestrator 系统提示词。

        Returns:
            Orchestrator 系统提示词
        """
        return ORCHESTRATOR_SYSTEM_PROMPT

    @staticmethod
    def apply_to_agent(agent_config: AgentConfig) -> AgentConfig:
        """将 Orchestrator 模板应用到 agent 配置。

        这是 create_config 的别名，为了 API 一致性。
        """
        return OrchestratorTemplate.create_config(agent_config)
