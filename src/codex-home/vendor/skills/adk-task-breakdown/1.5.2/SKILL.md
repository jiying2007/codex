---
name: adk-task-breakdown
description: "用于复杂任务拆解、公共契约迁移及并行边界；单点小修无需拆包，不替代已批准计划的执行。"
version: 1.5.2
last_updated: 2026-11-20
triggers:
  - "拆解任务"
  - "任务拆分"
  - "任务太大"
  - "公共契约迁移拆分"
non_triggers:
  - 单点微调任务
  - 单文件小修且无共享依赖变更
inputs:
  - 需求范围、里程碑、模块边界与依赖关系
outputs:
  - 任务、依赖、owner、冲突与验证
constraints:
  - 每项有可执行验证，批次不代表最终集成通过
  - 同一 shared contract/schema 不并行写
  - 机器包仅 adk-task-package-schema-v2；structured_output_schema、strict_schema_decision 及跨字段规则须校验
---

# adk-task-breakdown

## Goal
为复杂任务划清交付边界；小修或已有任务包直接退出。

## Choose the smallest useful plan
- **single-slice**：最小可观察纵向交付，不强制拆包、估时或并行。
- **multi-slice**：按真实依赖拆分，每项有产物、owner 和验证；共享 schema/root config/接口只设一个 writer。
- **machine-dispatched**：交执行器时按随包 `references/task-packaging.md` 的完整 v2 示例、类型及 `refusal_handling` 校验；不依赖未分发的源仓 schema。
- 已批准计划交 `adk-planning-execution-loop`；不得降低风险对应的验证和授权。

## Workflow
1. **Spec-to-slice**：按原验收 `REQ-NNN/ACC-NNN`、行为 delta、`VERIFY-NNN` 切 tracer-bullet。公共契约迁移见 `references/vertical-slice-planning.md`，保留退出/集成证据；阶段不代表最终通过。
2. 明确 `scope_read/scope_write/global_constraints/interfaces`、共享文件及权限。v2 将这些约束写入 `constraints` 字符串条目；worker 信封另存，同文件/shared contract 不并行写。
3. 依赖图无环；前置证据通过、写冲突解除、权限足够才进 Ready Frontier。`ready_to_handoff` 是调度判定，不是 v2 顶层字段；阻塞项不反复派发。
4. `work_item_kind` 与 `implementation_permission/exit_gate` 按 reference 校验；decision/research/prototype 禁止产品写入，prototype 附 `prototype_evidence`；只有已批准 implementation 可写，模型不能补造授权。
5. 人工计划仅需任务、依赖、验收、风险、下一步；**不硬套 0.5–8h**，未知 `not-estimated`；收益明确才并行。

## Quality Gate
- 每项有 owner、可执行 verify；未知路径/命令标待查。状态、权限和接口来自实际计划。
- 机器包拒绝缺字段、未知字段及错误类型/权限；未实际校验标未验证，不冒充 ready。
- 最终整合须验证；任务数量、估时或填表不证明成功。
