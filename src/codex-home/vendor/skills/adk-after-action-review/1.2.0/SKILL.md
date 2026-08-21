---
name: adk-after-action-review
description: 任务复盘与经验记忆候选治理，提取 lessons、风险分级和写入路由
version: 1.2.0
last_updated: 2026-07-07
triggers:
  - "任务复盘"
  - "经验沉淀"
  - "After Action Review"
  - "避免重复犯错"
  - "复盘 lessons"
non_triggers:
  - 线上事故需要做根因分析复盘
  - 仅做方案讨论且没有执行结果
  - 只保存完整聊天记录
inputs:
  - 任务目标、执行结果、错误与修复、验证结果、现有 AGENTS/runbook 约束
outputs:
  - AAR 复盘、memory candidate、Codify Decision、风险分级、写入位置路由、人工确认项
constraints:
  - 不保存完整聊天记录、密钥、隐私原文或一次性噪声
  - 不自动写入运行时 memories、AGENTS.md、生产规则或高风险策略
  - 每条候选必须包含 evidence、last_verified、confidence、risk、write_route
  - 每个完成后沉淀决策必须包含 reusable_pattern、promotion_candidate、next_task_friction_reduced、reduced_by、reduction_evidence、do_not_promote_reason、owner_review、rollback_path、verification_evidence
  - 高风险规则必须由用户确认后才能落地
---

# adk-after-action-review

## Goal
- 把任务后的可复用经验沉淀为可审查的候选规则，避免同类任务重复踩坑。
- 区分会话状态、用户偏好、项目规则和经验教训，防止 memory 噪声污染长期上下文。

## Prerequisites
- 已完成或阶段性完成一个任务，并有结果、错误、修复和验证信息。
- 已识别本次任务所属项目、工作流或运行边界。

## Workflow
1. 复原目标：用 1-3 句记录本次目标、非目标、最终结果和验证状态。
2. 提取事实：分开列出成功步骤、失败/返工、根因、修复动作和剩余风险。
3. 判断可复用性：只保留下次同类任务会用到的偏好、项目规则、工作流、工具限制和踩坑教训；单次 trace 只能作为候选，不能直接推广。
4. 记忆分层：
   - `session`: 本次任务状态，默认不长期保存。
   - `user`: 稳定个人偏好，需避免过度推断。
   - `project`: 项目结构、命令、门禁和工作流约束。
   - `lesson`: 从错误、负结果或成功路径中提取的经验。
5. 风险分级：
   - `low`: 检查要求、模板偏好、验证步骤、已证实工具限制。
   - `medium`: 项目默认流程、跨文件约定、可能影响多人协作的规则。
   - `high`: 自动发布、删除文件、生产数据库、支付动作、凭据保存、权限扩大。
6. 写入路由：为每条候选选择 `none/session-summary/project-runbook/project-AGENTS/user-memory/archive/skill-template`。
7. 生成候选：使用 `templates/memory/memory-candidate.md`，补齐 `evidence`、`last_verified`、`confidence`、`next_review_by`。
8. Codify Decision：若任务已交付或阶段性完成，使用 `templates/governance/codify-decision.md` 记录 `delivery_goal`、`reusable_pattern`、`affected_asset`、`promotion_candidate`、`next_task_friction_reduced`、`reduced_by`、`reduction_evidence`、`do_not_promote_reason`、`owner_review`、`rollback_path`、`verification_evidence`。
9. 推广判定：`promotion_candidate` 只能用于确有复用价值的约定、组件、runbook、manifest 或 skill/template；若不推广，必须填写 `do_not_promote_reason`，避免把一次性会话噪声沉淀为长期规则。若推广，必须说明 `next_task_friction_reduced` 是否为 true、由哪些 `reduced_by` 资产降低后续成本，并给出 `reduction_evidence`。
10. 审批控制：`high` 必须输出为待确认项；`medium` 至少说明影响范围和回退位置；`low` 可作为候选自动写入审计材料。涉及持久指导规则推广时，`owner_review`、`rollback_path` 和 `verification_evidence` 不得为空。
11. 过期处理：若规则依赖 API、路径、平台策略或用户偏好，设置复验日期；若与旧规则冲突，标记 `supersedes` 或 `conflicts_with`。
12. Improvement Loop：若建议修改 prompt、skill、workflow 或 agent，必须形成 trace-feedback-eval-handoff：sanitized trace、feedback summary、eval candidate、validation result、ranked recommendation、ADK handoff 和 human approval。
13. Trace Eval Regression Case：若复盘发现可重复的失败或回归风险，生成 `trace_eval_regression_case` 候选，至少包含 dataset_id、case_id、source_trace_id、prompt_version、candidate_prompt_version、expected_regression_signal、grader、score_threshold、regression_link、retention_policy、redaction_status 和 owner_approval；不得保存 raw session。
14. 门禁校验：新增或修改模板、runbook、候选格式后运行 `rtk bash scripts/check-memory-governance.sh`；涉及 Codify Decision 时运行 `rtk bash scripts/check-codify-governance.sh`。

## Commands
```bash
rtk bash scripts/check-memory-governance.sh
rtk bash scripts/check-codify-governance.sh
rtk bash scripts/validate-assets.sh --strict
```

## AAR Template
使用 `templates/memory/after-action-review.md` 输出任务复盘。

## Memory Candidate Template
使用 `templates/memory/memory-candidate.md` 输出可审查候选，不直接改长期记忆。

## Codify Decision Template
使用 `templates/governance/codify-decision.md` 输出完成后沉淀决策；即使结论是不推广，也要记录 `do_not_promote_reason` 和验证依据。

## Quality Gate
- AAR 必须包含目标、成功项、失败/返工、根因、lesson、验证和剩余风险。
- 每条 memory candidate 必须能说明“下次同类任务为何会用到”。
- 候选必须包含 scope、risk、confidence、evidence、last_verified、write_route。
- Codify Decision 必须包含 reusable_pattern、promotion_candidate、next_task_friction_reduced、reduced_by、reduction_evidence、do_not_promote_reason、owner_review、rollback_path、verification_evidence。
- Guidance promotion 必须有 trace-feedback-eval-handoff；缺 sanitized trace、eval candidate、validation result 或 human approval 时不得推广。
- trace_eval_regression_case 必须脱敏、可链接到 eval dataset，并有 grader、score_threshold、regression_link、retention_policy 和 owner_approval。
- `promotion_candidate: true` 时必须说明 affected_asset、owner_review、rollback_path 和 verification_evidence。
- 高风险候选必须标记 `requires_user_confirmation: true`，不得自动落地。
- 不得把完整聊天记录、临时草稿、过期价格、未经确认推测、密钥或隐私原文写入长期记忆。
- 若无可复用经验，输出 `memory_candidates: []` 并说明原因。
- 与线上事故 RCA 重叠时，事故根因报告优先使用 `adk-incident-rca-report`。
