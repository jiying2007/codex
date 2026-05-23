---
name: adk-code-review-loop
description: 独立代码审查与反馈修复闭环，覆盖发现分级、真实性核验、修复验证和复审
version: 1.0.0
last_updated: 2026-05-18
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
  - diff、需求目标、测试结果、review 发现、修复范围
outputs:
  - 分级发现、真实性判定、修复任务、复审结论和剩余风险
constraints:
  - 不得盲目接受 review 结论
  - blocker 和 major 未闭环不得给 pass
  - 审查者发现问题不等于修复者可以扩大范围
---

# adk-code-review-loop

## Goal
- 将代码审查从一次性意见列表变成可验证闭环。
- 对标 Superpowers 的 requesting/receiving review 能力，但保持 adk-first 的证据和门禁格式。
- 区分真实缺陷、风格建议、误报和超范围建议，避免盲修。

## Prerequisites
- 已有明确 diff 或变更文件清单。
- 已知道本次变更目标和非目标。
- 已收集基本验证结果，至少知道相关测试是否可运行。

## 发现分级

| 级别 | 定义 | 处理 |
|---|---|---|
| blocker | 会导致错误、安全问题、数据损坏或发布阻断 | 必须修复或明确接受风险 |
| major | 明显质量风险、边界遗漏、可复现回归 | 默认修复 |
| minor | 可读性、命名、局部风格或后续优化 | 可延期但需记录 |
| question | 信息不足或假设不明 | 先澄清，不直接改 |

## Workflow
1. **重述变更目标**：确认 review 对照的是正确需求，而不是泛泛挑刺。
2. **读取 diff 与测试**：按文件查看实际改动和验证证据。
3. **列出发现**：每条发现包含文件、位置、现象、影响和建议；检查异常分支、边界条件、权限/安全、兼容性、数据正确性、测试缺口和复杂度。
4. **真实性核验**：判断问题是否可复现、是否有代码证据、是否属于本次范围。
5. **分级裁决**：按 blocker/major/minor/question 分类。
6. **生成修复任务**：每个 blocker/major 对应一个最小修复动作和验证命令。
7. **执行或交接修复**：修复不得顺带重构无关文件。
8. **复审**：修复后重新检查原发现是否闭环，新增风险是否出现。
9. **门禁交接**：将结论交给 `adk-commit-pr-quality-gate` 或 `adk-verification-before-completion`。

## Review Report Template
```md
- Review Scope:
- Requirement Baseline:
- Verification Baseline:
- Findings:
  | ID | Severity | File | Evidence | Required Action | Status |
  |---|---|---|---|---|---|
- False Positives:
- Out-of-scope Suggestions:
- Fix Plan:
- Re-review Result:
- Final Verdict: pass | needs-fix
```

补充样例模板：`references/review-feedback-fixtures.md`，用于记录误报、越界建议和复审证据。

## Commands
```bash
# 查看变更范围
git diff --stat
git diff --name-only

# 查看指定文件 diff
git diff -- <path>

# 运行相关验证
<project-test-command>
```

## Failure Handling
- review 反馈不清楚时，先重写为可验证命题；仍不清楚则标记 question。
- 发现与需求无关时，记录为 out-of-scope，不混入本次修复。
- 修复后验证失败时，切换到 `adk-systematic-debugging` 定位。
- 若 review 要求改 shared contract/schema，先回到 `adk-requirements-triage` 和 `adk-task-breakdown`。

## Quality Gate
- 每个 blocker/major 必须有状态：fixed、accepted-risk、not-applicable。
- pass 结论必须满足 blocker=0 且 major=0。
- 误报必须说明证据，不得只写“不认同”。
- 复审必须引用修复后的验证命令或代码证据。
- 提交/PR 前必须再过 `adk-commit-pr-quality-gate`。
- AI review 只能作为第一轮风险扫描；高风险、业务语义或 owner 责任结论必须由人类 reviewer 或明确 owner 最终确认。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "review 说了就改" | review 也可能误判或越界 | 先做真实性和范围核验 |
| "都是 minor 不用记" | minor 多了会形成技术债 | 记录可延期项和 owner |
| "修一个顺手重构一片" | 容易制造新风险 | 每条发现对应最小修复 |
