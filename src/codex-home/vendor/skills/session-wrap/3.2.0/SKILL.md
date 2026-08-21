---
name: session-wrap
description: Wrap up the current Codex session with completed work, decisions, validation, risks, next actions, and an optional machine-readable receipt for daily/weekly reporting. Use only for the current conversation/session. Prefer project-activity-report for cross-session periods, project-daily-summary for a same-day project report, and commit-daily-summary for commit-only output.
version: 3.2.0
last_updated: 2026-08-02
---

# Session Wrap

Close the current session with evidence-backed outcomes and a resumable handoff. Avoid chronological narration.

## Workflow

1. Confirm the current-session scope.
2. Inspect the minimum relevant Git status, diff stat, and recent commits when available.
3. Group completed work by workstream and separate decisions, validation, risks, and next actions.
4. Distinguish `complete`, `partial`, and `blocked`; do not equate implementation with verification.
5. When the user requests machine-readable output, the session feeds an activity report, or the session is a durable handoff, append a bounded receipt.
6. Do not auto-archive, write memory, commit, push, or publish.

## Human Output

```markdown
## 本次会话总结
- 已完成：
- 关键决策：
- 验证：
- 风险/未完成：
- 下一步：
- 涉及工件：
```

## Structured Receipt

Emit JSON only when requested or needed by the reporting/handoff workflow:

```json
{
  "schema_version": 1,
  "kind": "codex-session-receipt",
  "project": "repo-id-or-folder",
  "period_date": "YYYY-MM-DD",
  "goal": "sanitized objective",
  "outcomes": [],
  "validation": [],
  "risks": [],
  "next_actions": [],
  "artifacts": [],
  "completion_status": "complete|partial|blocked",
  "raw_content_stored": false
}
```

Keep fields bounded and sanitized. Do not include raw transcript text, reasoning, secrets, auth state, private endpoints, customer/device identifiers, or unrestricted absolute paths. If evidence is missing, preserve the gap instead of filling it from memory.

When the user explicitly authorizes persistence for automatic reporting, write one receipt to
`~/knowledge-hub/.tmp/session-receipts/YYYY-MM-DD/<receipt-id>.json`. Use a stable,
collision-resistant receipt id and one file per session. Do not write the receipt automatically
at ordinary session close, and do not treat `.tmp` persistence as knowledge archival or memory.
