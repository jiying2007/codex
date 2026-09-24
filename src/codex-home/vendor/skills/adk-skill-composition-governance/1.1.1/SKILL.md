---
name: adk-skill-composition-governance
description: 治理技能组合、触发优先级、fallback 与弃用关系
version: 1.1.1
last_updated: 2026-08-31
triggers:
  - "技能组合"
  - "触发冲突"
  - "技能治理"
  - "创建 skill"
  - "skill 生命周期"
  - "内部降级治理"
  - "弃用治理"
non_triggers:
  - 单个 skill 文案微调且不影响触发规则
  - 仅安装已有 profile 且不改变组合关系
inputs:
  - skill 清单、触发词、non_trigger、profile、候选任务场景
outputs:
  - 主技能、辅助技能、fallback、互斥关系、模式分类和弃用决策
constraints:
  - 一个场景只能有一个主技能
  - 辅助技能不得抢占主技能触发
  - Pipeline/Inversion 类 skill 必须有可执行门禁或结构化状态检查
  - 组合治理必须先比较 skill namespace summary 和 initial_surface，再按命中候选加载 deferred_surface
---

# adk-skill-composition-governance

## Goal
- 用小技能组合提高覆盖面，同时避免运行时目录中触发噪音和职责重叠。
- 建立技能组合规则、冲突检测机制和治理矩阵。
- 建立 adk 原生 skill 创作、profile 归属、pilot 证据和弃用下线流程。

## Prerequisites
- 已列出涉及的 skill、optional skill 和目标 profile。
- 已有至少一条代表性任务输入。

## Workflow
1. 确定主技能：每个场景只能有一个 primary skill。
2. 标注辅助技能：supporting skill 只在 primary 明确需要时激活。
3. 定义 fallback：主技能不适用时给出后备 skill、触发条件和退出条件。
4. 定义互斥关系：职责冲突或触发重叠时写明优先级。
5. 模式分类：标注 Tool Wrapper、Generator、Reviewer、Inversion 或 Pipeline。
6. 输出契约审查：Generator/Reviewer 必须有 schema、失败条件和复验方式。
7. 硬门禁审查：Pipeline/Inversion 必须有状态文件、callback、脚本 gate 或外部编排，不得只靠自然语言约束。
8. 渐进披露审查：按 `skill-catalog-lazy-loading-v1` 记录 `namespace_summary`、`initial_surface`、`deferred_surface`、`loaded_tools`、`schema_review` 和相邻 skill 拒绝理由；不得全量加载所有 skill 正文后再裁决。
9. 冲突检测：检查 triggers、non_triggers、profile 和实际 match 样例。
10. 弃用治理：旧 skill 必须给 `deprecated_by` 或 `replaced_by`。
11. 回归样例：为 primary/supporting/fallback 各补代表输入。
12. 更新治理矩阵：记录场景、主技能、辅助技能、fallback、互斥和优先级。

## 组合规则
- 一个场景一个 primary；supporting 不抢占触发。
- fallback 必须在目标 profile 或可选安装范围内可用。
- deprecated skill 必须有替代方案，禁止无替代删除。
- 运行能力退役必须有 ready pilot、路由回归和 required/forbidden footprint 证据。

adk 原生 skill 创作和弃用生命周期模板：`references/adk-skill-lifecycle.md`。

## Skill Pattern Rules
- Tool Wrapper：必须声明命令/API/MCP 边界、输入校验、失败回滚。
- Generator：必须声明产物路径、覆盖策略、格式化/测试命令。
- Reviewer：必须声明严重级别、证据路径和误报处理方式。
- Inversion：必须声明 stop/ask 条件、owner 和状态恢复入口。
- Pipeline：必须声明阶段状态、检查点、resume/abort 路径和最终整合验证。

## Commands
```bash
bash scripts/devkit.sh catalog build
bash scripts/devkit.sh match --skill <skill> --text "<task text>"
bash ../scripts/check-runtime-routing.sh ..
rg -n "triggers:" skills/*/SKILL.md optional-skills/*/SKILL.md
bash scripts/check_profile_coherence.sh
bash tests/test_skill_trigger_matrix.sh
bash scripts/pilot-readiness.sh --summary-json
```

## Evidence Template
```md
- Scenario:
- Primary Skill:
- Supporting Skills:
- Fallback Skill:
- Mutually Exclusive Skills:
- Pattern Classification:
- Output Contract:
- Hard Gate:
- Deprecated/Replaced Decision:
- Trigger Regression:
- Composition Rules:
- Governance Matrix:
- Conflict Detection Results:
- Progressive Disclosure:
  - contract: skill-catalog-lazy-loading-v1
  - namespace_summary:
  - initial_surface:
  - deferred_surface:
  - loaded_tools:
  - schema_review:
  - adjacent_rejection:
```

## Failure Handling
- 若一个场景出现多个主技能，结论固定为 `needs-fix`。
- 若 fallback 不可安装或不在 profile 中，退回 profile 设计。
- 若冲突检测发现触发词重叠但无优先级定义，必须补充治理矩阵。
- 若弃用技能无替代方案，必须冻结而非删除。

## Quality Gate
- 组合规则必须能被脚本检查。
- 触发样例必须覆盖正例、反例和 fallback。
- 治理矩阵必须覆盖所有已知场景。
- 冲突检测必须在每次 profile 变更后重新执行。
- 依赖图必须可视化展示技能间关系，禁止隐式依赖。
- Generator/Reviewer/Pipeline/Inversion 的输出契约和硬门禁必须可验证。
- 组合裁决必须保留 progressive disclosure 证据，证明未因全量上下文噪音导致 primary/supporting/fallback 误判。
