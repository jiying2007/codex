---
name: adk-plan-lite
description: 轻量只读计划生成能力，用于用户明确要求先给计划但尚未要求执行或写文件的编码任务
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "给我一个计划"
  - "制定计划"
  - "实现计划"
  - "只要计划"
  - "先给计划"
  - "create plan"
  - "plan only"
  - "轻量计划"
non_triggers:
  - "执行计划"
  - "分阶段执行"
  - "任务太大需要拆解"
  - "并行施工"
  - "直接实现"
inputs:
  - 用户目标、仓库上下文、显式约束、可用验证命令
outputs:
  - 轻量计划、范围边界、行动项、验证项、风险与未决问题
constraints:
  - 默认只读，不创建、不修改、不删除文件
  - 用户明确要求执行或实现时，退出本 skill 并路由到对应实现流程
  - 计划必须简洁、可执行、可验证，不输出代码实现
---

# adk-plan-lite

## Goal
- 把用户的编码任务请求转成一份轻量、可执行、可验证的计划。
- 覆盖 Codex/通用开发场景中“先别动代码，先给计划”的需求，替代外部 `create-plan` 类 skill。

## Prerequisites
- 用户明确要求计划，或上下文显示当前阶段只需要计划。
- 已读取最小必要上下文：README、明显文档、相关入口文件或已有约束。
- 已判断该任务不需要进入长任务执行闭环、并行治理或 spec 级拆解。

## Workflow
1. 快速扫描：读取 README、docs、架构说明、测试入口和最可能被触达的文件。
2. 识别约束：记录语言、框架、目录边界、验证命令、部署或回滚限制。
3. 问题门禁：只有在无法负责任地产生计划时，最多提出 1-2 个阻塞问题；否则说明假设并继续。
4. 范围声明：明确 `In`、`Out`，避免计划默默扩大到实现、重构或清理。
5. 行动项生成：按 discovery -> change -> validation -> rollout 顺序列出 4-10 个动作。
6. 验证绑定：至少包含一条测试、lint、build、smoke 或人工验收项。
7. 风险标注：列出边界条件、兼容性、数据迁移、权限或回滚风险。
8. 退出判断：如果用户继续要求执行，切换到 `adk-requirements-triage`、`adk-task-breakdown`、`adk-planning-execution-loop` 或对应实现流程。

## Output Template
```md
# Plan

<1-3 句说明目标、方法和关键约束。>

## Scope
- In:
- Out:

## Action Items
- [ ] <Step 1>
- [ ] <Step 2>
- [ ] <Step 3>
- [ ] <Step 4>
- [ ] <Validation step>
- [ ] <Risk or rollout step>

## Open Questions
- <Question 1, only if blocking or materially affects the plan>
```

## Quality Gate
- 输出必须包含 Scope、Action Items 和验证项。
- 每个行动项必须是动词开头、可执行、可检查。
- 不得把“调查一下”“处理后端”“完善逻辑”这类模糊动作当作计划项。
- 不得在只读计划阶段修改文件、运行 destructive 命令或启动发布动作。
- 若任务明显超过轻量计划范围，结论必须说明转交到更重的 ADK 流程。

## Evidence Template
```md
- Plan Mode: read-only
- Context Read: <files or docs scanned>
- Assumptions:
- Scope:
- Validation Items:
- Risk Items:
- Escalation Decision: stay-lite / route-to-task-breakdown / route-to-planning-execution-loop
```
