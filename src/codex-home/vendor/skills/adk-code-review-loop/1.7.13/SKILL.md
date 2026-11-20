---
name: adk-code-review-loop
description: "用于独立代码审查、问题复核与反馈闭环；不用于自动批准或代替提交前门禁。"
version: 1.7.13
last_updated: 2026-11-20
triggers:
  - "独立代码审查"
  - "代码评审"
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
  - 发现问题不授权扩大修复范围
  - 不得把机械门禁通过表述为语义审查通过或最终可交付
  - staged 文件存在 unstaged overlay 时不得声称最新修复已被审查
---

# adk-code-review-loop

## Goal
冻结对象、验证发现、复核修复；机械、语义及 readiness 分别裁决。

## 输出语言

按用户请求或项目 locale 输出，统一分级；表达提示见 `references/review-communication-guidance.md`。

## Prerequisites

- 完整审查冻结目标、diff、测试、HEAD/index 与 `staged/working-tree/whole-branch` overlay；单条反馈仅绑定来源快照和相关证据。
- 生命周期变更需 Requirement Baseline，不适用时标 `not_applicable`。

## Workflow
1. **按意图分流**：`feedback-triage` 仅核单条/有限条反馈。只读来源快照、相关代码/测试/契约和反证；判 `valid / false-positive / question / cannot-verify-from-diff`。不强制 whole-diff/全量 CI/额外 reviewer，不修改文件或发 SCM comment，**不得**给 `Final Verdict: pass`、`Final Readiness: true`。跨文件、共享状态、生命周期、安全/权限及无界影响升级完整审查；缺证据不猜。
2. **定向复核**：`targeted-finding-review` 只核已知 finding 修复；更新目标 Snapshot ID、overlay、reopened；**不能**替代最终 `whole-diff-review` 或适用的 `whole-lifecycle-review`。
3. **最终完整审查**：`whole-diff-review` 冻结 HEAD/index/diff 和 Requirement/Domain Model/Verification Baseline；核机械 build/test/format 与语义，同轮输出 Spec/Quality 双 verdict；共享生命周期追加 whole-lifecycle 和独立 reviewer；大范围/高风险记录 `Review Coverage Ledger`。
4. **设计变更分流与收敛**：按 blocker/major/minor/question/cannot-verify-from-diff 分类并附证据；owner/state/event/resource/termination 或取消/超时/恢复变更标 `design-change` 并 replan；记录 new/reopened/clean rounds，不顺带重构。
5. **门禁交接**：最终 review 交 `adk-commit-pr-quality-gate` 或 `adk-verification-before-completion`；不自动批准；重复模式经 trace-feedback-eval-handoff/AAR 才成为 durable rule。

执行投入 `execution_effort` E2/E3 对冻结合同的关键前提提出可复现证伪；不表示评测证据已达到 E2/E3。优先减法，CI 绿不等于真实有效。

连续两轮出现新的 blocker 或 major finding class，任一 finding 为 `design-change`，或同一逻辑任务 `author-self-review` 超过两轮时，必须停止局部补丁循环并 `replan`。

完整分级、收敛例外及 CI/PR 边界见 `references/review-governance-details.md`；反馈样例见 `references/review-feedback-fixtures.md`。

## Failure Handling
- 反馈不清楚：改写成可验证命题；仍不清楚则 `question`。
- 不能从 diff 判定：`cannot-verify-from-diff`，交主 Agent/owner 补证据。
- 与需求无关：记录 out-of-scope，不混入本次修复。
- 修复后验证失败：切换 `adk-systematic-debugging`。
- shared contract/schema 或生命周期语义变更：回到 `adk-requirements-triage` + `adk-interface-contract-design`。

## Commands

按目标取证见 `references/review-evidence-template.md`；不扩大权限。

## Evidence Template
完整字段见 `references/review-evidence-template.md`；未覆盖范围显式标记。

```md
- Snapshot ID: <所选目标的 head + index/diff；分支另记 base/merge-base>
- Working Tree Overlay: none | <paths>
- Reviewer Independence: independent | author-self-review
- Review Round / Mode: <n> / <mode>; New Finding Class Count: <n>
- Mechanical Gate: pass | fail | not-run
- Contract Change Decision: none | design-change
```

## Quality Gate
- blocker=0 且 major=0 才可 pass；每个 blocker/major 必须是 fixed、accepted-risk 或 not-applicable。
- 不得把机械门禁通过表述为语义审查通过；语义无发现也不得自动推导 `Final Readiness: true`。
- staged 目标存在 `MM` 时必须列出 overlay，并设 `latest_worktree_reviewed: false`；修复后未重新 stage/更新 Snapshot ID，不得声称已复审。
- `author-self-review` 不是 independent；高风险共享逻辑需要 owner 或独立审查证据。
- `cannot-verify-from-diff` 必须补证据、owner 接受风险或明确不适用；高风险必需范围若为 `uninspected` 且无 owner 风险决策不得 pass。
- 缺需求基线或 Spec↔Code 双向核对证据时，不得给完整 spec-compliance pass；细节见按需 reference。
- 受控生命周期操作缺 owner/state/event baseline，或 `design-change` 未回设计阶段时，spec-compliance 固定不通过。
- reviewer 只读：不得修改工作树、切分支、执行破坏性操作，也不得被要求忽略发现或预设严重级别。
- Owner 显式委派时，独立 AI 可完成授权范围的 Spec/Quality 最终裁决；须记录 AI 身份、委派来源、快照与证据，不冒充人类。未委派的高风险或责任裁决仍交 owner。
- 机器发布 review comment 前必须有 schema-backed findings；不能从自由文本直接生成 SCM 写 payload；untrusted PR/fork/public PR 默认不接收 protected secrets，缺 trusted-trigger 决策时只允许只读分析；inline comment 位置无法验证时，必须降级为 summary finding。
- 重复 review 模式升为规则须有 sanitized trace、eval candidate、validation result 及 owner 或其明确委派的独立审核证据。
