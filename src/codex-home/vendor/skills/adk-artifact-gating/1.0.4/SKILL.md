---
name: adk-artifact-gating
description: "用于跨仓交付物需要标签、状态与验收交接协议时定义 Artifact 门禁；不用于单仓常规测试、直接上传制品或发布批准。"
version: 1.0.4
last_updated: 2026-11-20
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
  - 报告结论不得与最终门禁结果冲突
  - Artifact status 与 workflow stage 分开，沿用已有 workflow 校验
---

# adk-artifact-gating

## Goal

在跨仓、跨角色交付中，用标签、owner 和真实验证证据形成可复核结论。

## Prerequisites

确认变更目录、交付 owner、验证入口与接收方；按项目已有 workflow 推进，不另建状态机。

## Workflow

1. 核范围、owner、接收方；生成 ImplementationPlan / ReviewReport / TestReport 标签。
2. 计划就绪填 READY；评审/测试按实证填 PASS、NEEDS-FIX 或 BLOCKED，approved 不等于 PASS。
3. 执行验证，附命令、退出码和证据，由接收方签收完整性。
4. verify 通过后，ReviewReport/TestReport=PASS、verdict=pass 且与 review 结果一致才给门禁 pass；签收不代替验证。

## Quality Gate

三类标签、owner/证据/签收完整，命令可复现，报告与门禁一致；阶段校验沿用 workflow。

## Evidence Template

```md
status: pass | needs-fix | BLOCKED
owner: <gate-owner>
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
```

## References
- 状态语义、完整模板与交接见 `references/details.md`。
