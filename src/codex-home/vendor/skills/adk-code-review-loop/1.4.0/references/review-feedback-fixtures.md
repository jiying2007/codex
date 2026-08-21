# Review Feedback Fixtures

## Finding Template

| ID | Severity | Evidence | Scope Decision | Required Action | Status |
|---|---|---|---|---|---|
| R1 | blocker |  | in-scope |  | open |

## False Positive Fixture

- Claim:
- Evidence checked:
- Why not applicable:
- Follow-up:

## Out-of-scope Fixture

- Suggestion:
- Why outside current goal:
- Risk if ignored:
- Proposed backlog item:

## Re-review Fixture

- Original finding:
- Review target: staged | working-tree | whole-branch
- Old snapshot ID:
- New snapshot ID:
- Target paths with unstaged changes:
- Latest working tree reviewed: true | false
- Reviewer independence: independent | author-self-review
- Fix evidence:
- Verification command:
- Mechanical gate: pass | fail | not-run
- Semantic review: no-finding | findings-open | needs-context
- Result: pass | needs-fix

## Snapshot Commands

```bash
rtk git status --short
rtk git rev-parse HEAD
rtk git write-tree
rtk git diff --stat
rtk git diff --name-only
rtk git diff -- <path>
rtk git diff --cached --check
<project-test-command>
```

`diff --cached --check` 是机械门禁，不能替代语义审查。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|---|---|---|
| "review 说了就改" | review 也可能误判或越界 | 先做真实性和范围核验 |
| "都是 minor 不用记" | minor 多了会形成技术债 | 记录可延期项和 owner |
| "修一个顺手重构一片" | 容易制造新风险 | 每条发现对应最小修复 |
| "构建和测试过了就是审查通过" | 机械门禁不验证业务语义和生命周期不变量 | 单独完成语义审查并保留双结论 |
| "代码已修，旧 staged review 也算复审" | 未 stage 的修复不在旧快照中 | 重新 stage、生成新快照身份再复审 |
