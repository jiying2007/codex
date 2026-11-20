---
name: adk-requirements-triage
description: "用于需求不清时澄清目标、范围边界和可验证验收标准；已明确的开发任务无需重复访谈，也不用于代替实际实现。"
version: 1.4.1
last_updated: 2026-11-20
triggers:
  - "需求不清楚"
  - "需求模糊"
  - "需求不明确"
  - "跨团队需求"
  - "新功能"
  - "实现新功能"
  - "目标边界"
  - "验收标准"
  - "需求梳理"
  - "帮我理清需求"
  - "边界和验收"
  - "SDD驱动"
  - "规格驱动开发"
non_triggers:
  - 头脑风暴
  - brainstorming
  - grill me
  - gill me
  - 方案拷问
  - 挑战方案
  - 纯代码风格调整
  - 已有完整计划且只需按计划执行
  - 仅执行已有明确任务包
inputs:
  - 需求描述、上下文约束、现有代码入口
outputs:
  - 结构化需求清单、验收标准、非目标与风险清单
  - skill 路由建议（core/optional）与触发优先级
constraints:
  - 交付实际执行前必须明确 done-when、required evidence、artifact paths、blocker policy
  - 仅给读者的需求摘要可以精简；高风险权限与恢复条件不允许降级
---

# adk-requirements-triage

## Goal
将模糊需求整理到能够决定下一步的程度。不把普通讨论硬塞进交付模板，也不重新访谈已确认的需求。

## Document modes
- **brief**：只需讨论或给管理者阅读的摘要。写目标、现状、范围与非目标、关键约束、开放决策和下一步；不强迫生成不存在的代码路径、测试结果或 blocker。
- **execution-handoff**：将需求交给编码、测试或 Goal 执行。必须包含 `done-when`、`required evidence`、`artifact paths`（未知则明确 TBD 与查证方法）、`blocker policy`。
- **high-risk**：接口协议、设备、权限、安全、数据迁移或跨资源状态机。除 execution-handoff 外还需 Domain Model、异常、授权和恢复。不可把高风险任务降为 brief 以绕过门禁。

## Workflow
1. 核用户确认事实、当前代码与真实需求来源（含飞书项目/TAPD），不强制转 GitHub Issue。
2. 只问影响风险/设计的未知；可逆假设标建议，不默认为确认。
3. 给目标、范围、非目标及正负验收。行为变化复用 `Canonical Change Contract` 记录 REQ/Delta/ACC，不复制已有规格。
4. 跨模块/协议才补状态、异常和回退；小修不强制 Domain Model。
5. brief 简短；执行交接仍须 done-when/证据/路径/blocker policy，缺关键项 `needs-fix`。
6. 已批准直接实施；复杂任务才交 `adk-task-breakdown`，本 Skill 不代替实现。

## Output
`brief: Goal / Scope / Constraints / Open Decisions / Next Step`
`execution-handoff: Goal / Non-goal / Done-when / Required Evidence / Artifact Paths / Blocker Policy / Acceptance`
`high-risk: Domain Model / Authorization / Recovery / Compatibility / Negative Cases`

## Quality Gate
- 执行交接仍严格要求 done-when、required evidence、artifact paths、blocker policy；设备、权限和不可逆副作用没有批准不得执行。
- 不因缺少适用于实现的字段而把 brief 判为失败，也不凭空补证据或路径。
- 文档保真：保留原始技术前提、数字、限制词与来源，明确事实/建议/未知的区别。
