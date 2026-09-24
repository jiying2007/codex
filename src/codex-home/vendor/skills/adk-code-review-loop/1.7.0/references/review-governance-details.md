# Code Review Governance Details

按 progressive disclosure 使用：只有在严重级别存在争议、生命周期语义复杂、review 多轮不收敛、或需要向 CI/PR 发布结构化 finding 时读取本文件。日常审查先使用 `../SKILL.md` 的核心流程。

## Finding Classification

| 级别 | 定义 | 处理 |
|---|---|---|
| blocker | 会导致错误、安全问题、数据损坏或发布阻断 | 必须修复或明确接受风险 |
| major | 明显质量风险、边界遗漏、可复现回归 | 默认修复 |
| minor | 可读性、命名、局部风格或后续优化 | 可延期但需记录 |
| question | 信息不足或假设不明 | 先澄清，不直接改 |
| cannot-verify-from-diff | 需求依赖未改动代码、外部行为或运行态证据，仅凭 diff 无法判定 | 由主 Agent 或 owner 补查，不得默认为通过 |

真实性核验至少回答：问题能否由代码/运行证据支持、是否属于本次变更范围、是否需要外部 owner/运行态证据。误报必须记录反证；out-of-scope 建议不能混成 blocker/major。

## Detailed Review Workflow

1. **冻结审查快照**：记录 Review Target、HEAD、index/diff 指纹、目标文件和 unstaged overlay；没有快照身份就不输出“已复审最新修复”。
2. **重述变更目标**：确认 review 对照的是正确需求、非目标与验收，而不是泛泛挑刺。
3. **分离机械与语义证据**：构建、测试、格式、`diff --check` 属于机械门禁；需求符合性、并发、生命周期、安全和边界属于语义审查；两者互不替代。
4. **读取 diff 与测试**：按文件查看实际改动和验证证据，不以 implementer rationale 代替代码事实。
5. **列出发现**：每条包含文件、位置、现象、影响、证据、范围和建议。
6. **双 verdict 审查**：同一次阅读输出 spec-compliance verdict 与 quality verdict，避免重复派发多个局部 reviewer。
7. **固定 Review Context**：记录需求包、领域模型、非目标、验证基线、生命周期操作契约（如适用）和变更范围；缺失时降级为 `question`/`cannot-verify-from-diff`。
8. **真实性核验**：判断 finding 是否可复现、有证据、在范围内；不能从 diff 判定时显式标记。
9. **分级裁决**：按 blocker/major/minor/question/cannot-verify-from-diff 分类。
10. **设计变更分流**：finding 若改变唯一 owner、状态转换、可见性、取消、超时、恢复或迟到完成语义，标记 `design-change`，停止普通补丁闭环并回到契约设计。
11. **生成修复任务**：每个 blocker/major 对应最小修复动作和验证命令。
12. **执行或交接修复**：不得顺带重构无关文件。
13. **重新暂存并复审**：staged 目标修复后先重新 stage，再生成新的快照身份；旧快照结论不得覆盖新 index。
14. **整体验证**：任务级 review 通过后仍需 whole-diff/whole-branch 视角；共享状态、异步完成或资源生命周期适用时做 whole-lifecycle-review。
15. **独立性裁决**：优先 fresh independent review；只有自审时标记 `author-self-review`，高风险结论交 owner 或独立 reviewer 最终确认。
16. **门禁交接**：将机械门禁和语义审查的独立结论交给 `adk-commit-pr-quality-gate` 或 `adk-verification-before-completion`。
17. **CI/PR 发布核验**：机器发布 SCM comment 前，按 `manifests/pr_review_governance_contracts.json` 核验 schema-backed findings、untrusted PR 隔离和 inline anchoring。
18. **Review 改进闭环**：重复失败模式只能作为 trace-feedback-eval-handoff/AAR 候选，不得直接修改 durable guidance。

## Convergence Protocol

每轮至少记录：
- `review_round`
- `review_mode`
- `finding_classes`
- `new_finding_class_count`
- `reopened_finding_count`
- `consecutive_clean_reviews`
- `reviewer_independence`
- `contract_change_decision`
- `replan_reason`

Review mode 边界：
- `targeted-finding-review`：只验证已知 finding 的修复。
- `whole-diff-review`：检查完整 diff 和跨文件影响。
- `whole-lifecycle-review`：对 owner × state × event × resource × termination × invariant 做生命周期审查。

强制 `replan`：
- 连续两轮出现新的 blocker 或 major finding class。
- 任一 finding 被判定为 `design-change`。
- 同一逻辑任务的 `author-self-review` 超过两轮；此时至少执行 whole-lifecycle review，并交 owner 或 fresh independent reviewer。

`locally-clean` 只表示自审快照内无 blocker/major，不是 independent final pass。生命周期最终 pass 还要求最后快照未变化、`new_finding_class_count=0`、至少一轮适用的整体审查以及 owner/独立审查证据。

## CI and PR Publication Boundary

AI/CI review 默认只是风险扫描，写入 SCM 属于独立的发布动作：
- 自由文本不能直接转换成 comment payload；先产出 schema-backed findings。
- fork/public PR 默认不得暴露 protected secrets；缺 trusted-trigger 决策时只允许只读分析。
- inline comment 必须能验证到目标 commit/diff 的合法位置；无法锚定时降级为 summary finding。
- 发布前记录 `trusted_trigger`、`protected_secret_exposure`、`structured_output_valid`、`inline_anchor_valid`。
- 机器 comment 不替代人类/owner 对高风险、业务语义或责任边界的最终裁决。

## Snapshot and Evidence Details

完整字段模板见 `review-evidence-template.md`。完整反馈/误报/out-of-scope/re-review 样例见 `review-feedback-fixtures.md`。

快照至少绑定：
- HEAD。
- index 或 diff identity。
- Review Target。
- Working Tree Overlay。
- `latest_worktree_reviewed`。
- reviewer independence。

staged 文件出现 `MM` 时，必须显式列出 unstaged overlay。修复未重新 stage、Snapshot ID 未更新时，不得声称最新修复已复审。
