---
name: orchestrator
trigger: auto
description: 自动任务分解和并行执行模式
---

# Orchestrator 模式

当需要处理复杂多步骤任务时，自动使用 orchestrator 模式将任务分解为可并行执行的子任务。

## 何时使用

- 需要搜索/研究多个相关主题
- 需要同时处理多个独立子任务
- 需要收集多方面信息后综合报告
- 任务可以清晰分解为 2-5 个并行工作流

## 使用方法

### 1. 任务分解

将复杂任务分解为独立的子任务，例如：

**用户请求**: "研究 AI 编程助手的最佳实践"

**分解为**:
- 搜索当前 AI 编程助手的主流方案
- 查找代码生成的最佳实践
- 研究代码审查和调试策略
- 了解性能优化方法

### 2. 批量 Spawn

使用 spawn 工具的 batch 参数同时启动所有 worker:

```json
{
  "tool": "spawn",
  "parameters": {
    "batch": [
      {"task": "搜索当前 AI 编程助手的主流方案", "label": "research-tools"},
      {"task": "查找代码生成的最佳实践", "label": "research-coding"},
      {"task": "研究代码审查和调试策略", "label": "review-debug"},
      {"task": "了解性能优化方法", "label": "research-performance"}
    ],
    "wait": true,
    "timeout": 600
  }
}
```

### 3. 等待并聚合结果

所有 worker 完成后，综合各子任务的结果生成完整报告。

## 最佳实践

1. **任务独立性**: 确保子任务之间相互独立，可以并行执行
2. **清晰标签**: 为每个子任务使用描述性的 label
3. **合理数量**: 一次 spawn 2-5 个子任务，避免过多
4. **超时设置**: 根据任务复杂度设置合理的 timeout
5. **错误处理**: 某些 worker 失败时，使用其他结果继续

## 示例工作流

```
用户：帮我研究 React 性能优化的最佳实践

Orchestrator 思考：
这是一个复杂的研究任务，需要分解为多个并行子任务。

执行步骤：
1. spawn batch [
     {task: "研究 React 组件渲染优化", label: "render-optimization"},
     {task: "查找 React 状态管理性能最佳实践", label: "state-management"},
     {task: "搜索 React 代码分割和懒加载技术", label: "code-splitting"},
     {task: "了解 React 性能监控工具", label: "monitoring"}
   ]
2. 等待所有 worker 完成
3. 综合所有结果，生成完整的性能优化指南

最终输出：
基于 4 个专项研究的结果，以下是 React 性能优化的完整指南：
1. 组件渲染优化...
2. 状态管理最佳实践...
3. 代码分割技术...
4. 性能监控方案...
```
