---
name: adk-code-review-loop
description: 独立代码审查与反馈修复闭环，覆盖发现分级、真实性核验、修复验证和复审
version: 1.4.0
last_updated: 2026-08-21
triggers:
  - "独立代码审查"
  - "code review loop"
  - "review 闭环"
  - "审查反馈"
  - "复审"
  - "收到 review"
  - "修复 review"
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
- 区分真实缺陷、风格建议、误报和超范围建议，避免盲修。
- 让外部扫描器与本地审查各司其职：前者发现风险，后者结合完整上下文核验事实并执行门禁。

## Prerequisites
- 已有明确 diff 或变更文件清单。
- 已知道本次变更目标和非目标。
- 已收集基本验证结果，至少知道相关测试是否可运行。
- 已声明审查目标是 `staged`、`working-tree` 还是 `whole-branch`，并记录 HEAD 与 index/diff 指纹等价物。
- 审查 staged 内容时，已识别目标文件是否存在 unstaged overlay；存在时明确最新 working tree 不在本轮审查范围。
- 已标记 reviewer independence：`independent` 或 `author-self-review`；后者不能冒充独立审查证据。
- 若 review 来自 CI/AI runner，必须有结构化 findings、trusted-trigger/secret 隔离决策和 SCM 发布边界。

## 发现分级

| 级别 | 定义 | 处理 |
|---|---|---|
| blocker | 会导致错误、安全问题、数据损坏或发布阻断 | 必须修复或明确接受风险 |
| major | 明显质量风险、边界遗漏、可复现回归 | 默认修复 |
| minor | 可读性、命名、局部风格或后续优化 | 可延期但需记录 |
| question | 信息不足或假设不明 | 先澄清，不直接改 |
| cannot-verify-from-diff | 需求依赖未改动代码、外部行为或运行态证据，仅凭 diff 无法判定 | 由主 Agent 或 owner 补查，不得默认为通过 |

## Workflow
1. **冻结审查快照**：记录 Review Target、HEAD、index/diff 指纹、目标文件和 unstaged overlay；没有快照身份就不输出“已复审最新修复”。
2. **重述变更目标**：确认 review 对照的是正确需求，而不是泛泛挑刺。
3. **分离两类证据**：机械门禁记录构建、测试、格式、`diff --check`；语义审查单独记录需求符合性、并发、生命周期和边界风险，任何一类通过都不能替代另一类。
4. **读取 diff 与测试**：按文件查看实际改动和验证证据。
5. **列出发现**：每条发现包含文件、位置、现象、影响和建议；检查异常分支、边界条件、权限/安全、兼容性、数据正确性、测试缺口和复杂度。
6. **双 verdict 审查**：同时给出 spec-compliance verdict 与 quality verdict；同一次阅读 diff 覆盖需求符合性和代码质量，不重复派发多个局部 reviewer。
7. **Review context 固定**：记录 review 对照的需求包、领域模型、非目标、验证基线和变更范围；缺少这些上下文时先标记 `question` 或 `cannot-verify-from-diff`，不得补脑通过。
8. **真实性核验**：判断问题是否可复现、是否有代码证据、是否属于本次范围；不能从 diff 判定的项标记为 `cannot-verify-from-diff`。
9. **分级裁决**：按 blocker/major/minor/question/cannot-verify-from-diff 分类。
10. **生成修复任务**：每个 blocker/major 对应一个最小修复动作和验证命令。
11. **执行或交接修复**：修复不得顺带重构无关文件。
12. **重新暂存并复审**：修复后若目标为 staged，先 stage 预期修复，再生成新的快照身份；复查原发现和新增风险。旧快照结论不得覆盖新 index。
13. **整体验证**：任务级 review 通过后，仍需一次 whole-diff/whole-branch 视角检查跨任务集成问题。
14. **独立性裁决**：优先使用 fresh independent review；只有自审时标记 `author-self-review`，高风险结论交 owner 或独立 reviewer 最终确认。
15. **门禁交接**：将机械门禁和语义审查的独立结论交给 `adk-commit-pr-quality-gate` 或 `adk-verification-before-completion`。
16. **CI/PR 发布核验**：若要发布 SCM comment，必须按 `manifests/pr_review_governance_contracts.json` 验证 schema-backed findings、untrusted PR 隔离和 inline anchoring。
17. **Review 改进闭环**：重复 review 失败模式只能作为 trace-feedback-eval-handoff 候选进入 AAR，不得直接改 durable guidance。

## Review Report Template
```md
- Review Scope:
- Review Target: staged | working-tree | whole-branch
- Snapshot ID:
  - head:
  - index_or_diff:
- Working Tree Overlay:
  - target_paths_with_unstaged_changes:
  - latest_worktree_reviewed: true | false
- Reviewer Independence: independent | author-self-review
- Requirement Baseline:
- Domain Model Baseline:
- Verification Baseline:
- Mechanical Gate: pass | fail | not-run
- Review Mode: task-level | whole-diff | whole-branch
- Spec Verdict:
- Quality Verdict:
- Semantic Review: no-finding | findings-open | needs-context
- Findings:
  | ID | Severity | File | Evidence | Required Action | Status |
  |---|---|---|---|---|---|
- Cannot Verify From Diff:
- False Positives:
- Out-of-scope Suggestions:
- CI/PR Review Boundary:
  - trusted_trigger:
  - protected_secret_exposure:
  - structured_output_valid:
  - inline_anchor_valid:
- Fix Plan:
- Re-review Result:
- Final Verdict: pass | needs-fix
- Final Readiness: true | false
```

补充样例、命令和合理化拦截见 `references/review-feedback-fixtures.md`。

## Failure Handling
- review 反馈不清楚时，先重写为可验证命题；仍不清楚则标记 question。
- 发现与需求无关时，记录为 out-of-scope，不混入本次修复。
- 修复后验证失败时，切换到 `adk-systematic-debugging` 定位。
- 若 review 要求改 shared contract/schema，先回到 `adk-requirements-triage` 和 `adk-task-breakdown`。

## Quality Gate
- 每个 blocker/major 必须有状态：fixed、accepted-risk、not-applicable。
- pass 结论必须满足 blocker=0 且 major=0。
- 机械门禁通过不得表述为语义审查通过；语义无发现也不得自动推导 `Final Readiness: true`。
- staged 目标中存在 `MM` 文件时，必须列出 unstaged overlay，并将 `latest_worktree_reviewed` 设为 false。
- 修复后未重新 stage 或快照身份未更新时，不得声称该修复已复审。
- `author-self-review` 可作为本地质量核验，但不得标记为 independent；高风险共享逻辑需要 owner 或独立审查证据。
- pass 结论还必须处理 `cannot-verify-from-diff`：补验证证据、owner 接受风险或明确不适用。
- 缺少 Requirement Baseline、Domain Model Baseline 或 Verification Baseline 时，不得给出 spec-compliance pass；必须先补上下文或降级为 `cannot-verify-from-diff`。
- reviewer 不得修改工作树、切换分支或执行破坏性操作；审查默认只读。
- reviewer 不得被要求忽略发现、预设严重级别或接受 implementer rationale 作为证据。
- 误报必须说明证据，不得只写“不认同”。
- 复审必须引用修复后的验证命令或代码证据。
- 提交/PR 前必须再过 `adk-commit-pr-quality-gate`。
- AI review 只能作为第一轮风险扫描；高风险、业务语义或 owner 责任结论必须由人类 reviewer 或明确 owner 最终确认。
- 机器发布 review comment 前必须有 schema-backed findings；不能从自由文本直接生成 SCM 写 payload。
- fork/public PR 默认不接收 protected secrets；没有 trusted-trigger 决策时只允许只读分析。
- inline comment 位置无法验证时，必须降级为 summary finding。
- 重复 review 模式若要提升为规则，必须有 sanitized trace、eval candidate、validation result 和 human approval。
