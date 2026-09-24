# Code Review Evidence Template

## Snapshot commands

```bash
rtk git rev-parse HEAD
rtk git status --short
rtk git diff --check
rtk git diff --cached
rtk git diff --check --cached
<project-lint-cmd> && <project-test-cmd>
```

## Full report

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
- Review Round:
- Review Mode: targeted-finding-review | whole-diff-review | whole-lifecycle-review
- Finding Classes:
- New Finding Class Count:
- Reopened Finding Count:
- Consecutive Clean Reviews:
- Requirement Baseline:
- Domain Model Baseline:
- Verification Baseline:
- Lifecycle Operation Baseline: not_applicable | <path + digest>
- Contract Change Decision: none | design-change
- Replan Reason:
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
- Quality Verdict: locally-clean | independent-final-pass | needs-fix
- Final Readiness: true | false
```
