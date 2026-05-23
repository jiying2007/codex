---
name: adk-after-action-review
description: 任务复盘与经验记忆候选治理，提取 lessons、风险分级和写入路由
version: 1.0.0
last_updated: 2026-05-21
triggers:
  - "任务复盘"
  - "经验沉淀"
  - "memory candidate"
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
  - AAR 复盘、memory candidate、风险分级、写入位置路由、人工确认项
constraints:
  - 不保存完整聊天记录、密钥、隐私原文或一次性噪声
  - 不自动写入 ~/.codex/memories、AGENTS.md、生产规则或高风险策略
  - 每条候选必须包含 evidence、last_verified、confidence、risk、write_route
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
3. 判断可复用性：只保留下次同类任务会用到的偏好、项目规则、工作流、工具限制和踩坑教训。
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
8. 审批控制：`high` 必须输出为待确认项；`medium` 至少说明影响范围和回退位置；`low` 可作为候选自动写入审计材料。
9. 过期处理：若规则依赖 API、路径、平台策略或用户偏好，设置复验日期；若与旧规则冲突，标记 `supersedes` 或 `conflicts_with`。
10. 门禁校验：新增或修改模板、runbook、候选格式后运行 `rtk bash scripts/check-memory-governance.sh`。

## Commands
```bash
rtk bash scripts/check-memory-governance.sh
rtk bash scripts/validate-assets.sh --strict
```

## AAR Template
使用 `templates/memory/after-action-review.md` 输出任务复盘。

## Memory Candidate Template
使用 `templates/memory/memory-candidate.md` 输出可审查候选，不直接改长期记忆。

## Quality Gate
- AAR 必须包含目标、成功项、失败/返工、根因、lesson、验证和剩余风险。
- 每条 memory candidate 必须能说明“下次同类任务为何会用到”。
- 候选必须包含 scope、risk、confidence、evidence、last_verified、write_route。
- 高风险候选必须标记 `requires_user_confirmation: true`，不得自动落地。
- 不得把完整聊天记录、临时草稿、过期价格、未经确认推测、密钥或隐私原文写入长期记忆。
- 若无可复用经验，输出 `memory_candidates: []` 并说明原因。
- 与线上事故 RCA 重叠时，事故根因报告优先使用 `adk-incident-rca-report`。
