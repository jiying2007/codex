---
name: adk-code-review-loop
description: 独立代码审查与反馈修复闭环，覆盖发现分级、真实性核验、修复验证和复审
version: 1.7.0
last_updated: 2026-09-14
triggers:
  - "独立代码审查"
  - "code review loop"
  - "review 闭环"
  - "审查反馈"
  - "复审"
  - "收到 review"
  - "修复 review"
  - "review 反馈"
  - "反馈真实性核验"
non_triggers:
  - 纯格式化且已有自动格式检查
  - 提交前只需要校验 commit message
inputs:
  - 审查目标、快照身份、diff、需求目标、测试结果、review 发现、修复范围
outputs:
  - 快照边界、分级发现、真实性判定、机械门禁、修复任务、复审结论和剩余风险
constraints:
  - 不得盲目接受 review 结论
  - blocker 和 major 未闭环不得给 pass
  - 审查者发现问题不等于修复者可以扩大范围
  - 不得把机械门禁通过表述为语义审查通过或最终可交付
  - staged 文件存在 unstaged overlay 时不得声称最新修复已被审查
---

# adk-code-review-loop

## Goal
- 将代码审查从一次性意见列表变成可验证闭环。
- 区分真实缺陷、误报、超范围建议与仅凭 diff 无法验证的问题。
- 保持机械门禁、语义审查、最终 readiness 三类结论相互独立。

## Prerequisites
- 有明确 diff/文件清单、目标与非目标、相关测试结果。
- 声明 Review Target：`staged`、`working-tree` 或 `whole-branch`，并记录 HEAD 与 index/diff 身份。
- staged 目标存在 unstaged overlay 时，明确该 working tree 内容不在本轮审查范围。
- 标记 Reviewer Independence：`independent` 或 `author-self-review`；自审不得冒充独立审查。
- 受控生命周期操作需有 Requirement Baseline；不适用时显式标记 `not_applicable`。
- CI/AI review 若要写 SCM comment，需有结构化 findings、trusted-trigger/secret 隔离和发布边界。

## Workflow
1. **冻结快照**：记录 Review Target、HEAD、index/diff 指纹、目标文件和 Working Tree Overlay。
2. **重述目标**：对齐 Requirement/Domain Model/Verification Baseline；缺失时标记 `question` 或 `cannot-verify-from-diff`。
3. **双通道审查**：机械门禁检查 build/test/format/`diff --check`；语义审查检查需求、并发、生命周期、权限、安全、兼容性和数据正确性。
4. **列出发现并核真**：按 blocker/major/minor/question/cannot-verify-from-diff 分类，每条给出文件、证据、影响、范围与建议。
5. **双 verdict**：同一轮同时输出 spec-compliance verdict 与 quality verdict，避免重复派发多个局部 reviewer。
6. **设计变更分流**：finding 若改变唯一 owner、状态转换、可见性、取消、超时、恢复或迟到完成语义，标记 `design-change`，停止普通补丁并回到契约设计。
7. **生成最小修复任务**：blocker/major 对应最小修复和验证命令；不得顺带重构。
8. **重新暂存并复审**：staged 目标修复后重新 stage 并生成新 Snapshot ID；旧快照不得覆盖新 index。
9. **整体验证**：targeted-finding-review 之后仍需 whole-diff；共享状态/异步完成/资源生命周期适用时做 whole-lifecycle-review。
10. **收敛判定**：记录 review round、finding classes、New Finding Class Count、reopened count、clean rounds、independence 和 replan reason。
11. **独立性裁决**：优先 fresh independent review；高风险共享逻辑最终由 owner 或独立 reviewer 确认。
12. **门禁交接**：交给 `adk-commit-pr-quality-gate` 或 `adk-verification-before-completion`；重复模式只能经 trace-feedback-eval-handoff/AAR 提升为 durable rule。

连续两轮出现新的 blocker 或 major finding class，任一 finding 为 `design-change`，或同一逻辑任务 `author-self-review` 超过两轮时，必须停止局部补丁循环并 `replan`。

完整分级表、18-step 解释、收敛例外、CI/PR 发布边界见 `references/review-governance-details.md`；完整报告见 `references/review-evidence-template.md`；反馈样例见 `references/review-feedback-fixtures.md`。

## Failure Handling
- 反馈不清楚：改写成可验证命题；仍不清楚则 `question`。
- 不能从 diff 判定：`cannot-verify-from-diff`，交主 Agent/owner 补证据。
- 与需求无关：记录 out-of-scope，不混入本次修复。
- 修复后验证失败：切换 `adk-systematic-debugging`。
- shared contract/schema 或生命周期语义变更：回到 `adk-requirements-triage` + `adk-interface-contract-design`。

## Commands
```bash
rtk git rev-parse HEAD
rtk git status --short
rtk git diff --check
<project-lint-cmd> && <project-test-cmd>
```

## Evidence Template
```md
- Review Target: staged | working-tree | whole-branch
- Snapshot ID: <head + index_or_diff identity>
- Working Tree Overlay: <none | paths>
- latest_worktree_reviewed: true | false
- Reviewer Independence: independent | author-self-review
- Review Round / Mode: <n> / targeted-finding-review | whole-diff-review | whole-lifecycle-review
- Finding Classes / New Finding Class Count / Reopened Finding Count / Consecutive Clean Reviews:
- Lifecycle Operation Baseline: not_applicable | <path + digest>
- Contract Change Decision: none | design-change
- Replan Reason: <none | reason>
- Mechanical Gate: pass | fail | not-run
- Spec Verdict / Quality Verdict:
- Final Verdict: pass | needs-fix
```

## Quality Gate
- blocker=0 且 major=0 才可 pass；每个 blocker/major 必须是 fixed、accepted-risk 或 not-applicable。
- 不得把机械门禁通过表述为语义审查通过；语义无发现也不得自动推导 `Final Readiness: true`。
- staged 目标存在 `MM` 时必须列出 overlay，并设 `latest_worktree_reviewed: false`；修复后未重新 stage/更新 Snapshot ID，不得声称已复审。
- `author-self-review` 不是 independent；高风险共享逻辑需要 owner 或独立审查证据。
- `cannot-verify-from-diff` 必须补证据、owner 接受风险或明确不适用。
- 缺 Requirement/Domain Model/Verification Baseline 时不得给 spec-compliance pass。
- 受控生命周期操作缺 owner/state/event baseline，或 `design-change` 未回设计阶段时，spec-compliance 固定不通过。
- `targeted-finding-review` 不得替代 whole-diff 或适用的 whole-lifecycle review。
- reviewer 只读：不得修改工作树、切分支、执行破坏性操作，也不得被要求忽略发现或预设严重级别。
- AI review 只作第一轮风险扫描；高风险、业务语义或 owner 责任由人类 reviewer/owner 最终确认。
- 机器发布 review comment 前必须有 schema-backed findings；不能从自由文本直接生成 SCM 写 payload；untrusted PR/fork/public PR 默认不接收 protected secrets，缺 trusted-trigger 决策时只允许只读分析；inline comment 位置无法验证时，必须降级为 summary finding。
- 重复 review 模式提升为规则前，必须有 sanitized trace、eval candidate、validation result 和 human approval。
