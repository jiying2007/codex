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

### 局部误报：零值与缺省值

当 finding 声称“`limit=0` 因 falsy 被当成无限制”，先读实际分支：`if limit is None` 与 `if not limit` 的语义不同。核对契约中 None/0/正数各自的结果及对应快照，再给 `confirmed / false-positive / needs-context`。实际代码已区分零值时，保留实现、记录该 finding 的反证和 `no-change`；不为了回应审查而改正确代码、引入全库重构或自动发出远端评论。这个局部结论只覆盖该 finding，不能写成 whole-diff 已通过。

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

只使用 [Snapshot commands](review-evidence-template.md#snapshot-commands) 的目标选择与命令，不复制快照流程。机械检查不替代语义审查。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|---|---|---|
| "review 说了就改" | review 也可能误判或越界 | 先做真实性和范围核验 |
| "都是 minor 不用记" | minor 多了会形成技术债 | 记录可延期项和 owner |
| "修一个顺手重构一片" | 容易制造新风险 | 每条发现对应最小修复 |
| "构建和测试过了就是审查通过" | 机械门禁不验证业务语义和生命周期不变量 | 单独完成语义审查并保留双结论 |
| "代码已修，旧 staged review 也算复审" | 未 stage 的修复不在旧快照中 | 重新 stage、生成新快照身份再复审 |
