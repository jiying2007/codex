---
name: adk-artifact-gating
description: 跨仓库 Artifact 门禁协议——统一标签、状态机与交接规范
version: 1.0.0
last_updated: 2026-05-08
triggers:
  - "artifact 门禁"
  - "跨角色交接"
  - "变更工件"
  - "标签化交付"
non_triggers:
  - 单文件低风险修复且无需跨角色交接
  - 纯探索性代码阅读
inputs:
  - 变更需求、实现范围、验证命令结果、评审结论
outputs:
  - 标签化 artifact 块（ImplementationPlan / ReviewReport / TestReport）
  - 门禁结论（pass / needs-fix / BLOCKED）
  - 交接签收记录
constraints:
  - 所有 artifact 必须包含 status 字段和验证证据
  - 缺少验证证据时结论固定为 needs-fix 或 BLOCKED
  - ReviewReport 与 TestReport 结论不允许矛盾
  - 状态机转换必须经过校验，禁止跳过中间状态
---

# adk-artifact-gating

## Goal

在跨仓库、跨角色交付场景中，用统一的 artifact 标签体系和状态机门禁，消灭"口头完成"和"结论无证据"问题。


## Prerequisites

- 理解 artifact 门禁的基本概念
- 熟悉跨角色协作流程
- 了解状态机转换规则
- 具备基本的文档编写能力


## Workflow

1. 识别变更范围与影响角色
2. 为每个 artifact 生成统一标签（ImplementationPlan / ReviewReport / TestReport）
3. 填充状态字段（draft → in-review → approved / needs-fix / BLOCKED）
4. 执行验证命令并附加证据
5. 交接签收：接收方确认 artifact 完整性
6. 门禁结论：全部 artifact approved 且无矛盾 → pass


## Quality Gate

1. 三类 artifact 均存在且字段完整
2. ReviewReport 与 TestReport 结论一致
3. 所有验证命令可复现
4. 状态机转换经脚本校验
5. 交接签收记录完整


## Evidence Template

```md
status: pass | needs-fix | BLOCKED
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
```

## References
- 详细背景、命令、模板、示例和扩展检查项保存在 `references/details.md`。
- 入口文件只保留触发和执行所需的最小上下文，避免默认加载过多 token。
