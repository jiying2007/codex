---
name: session-wrap
description: Close the current Codex session with evidence-backed outcomes, decisions, validation, risks, next actions, and optional activity-session-receipt v2 work items. Use only for the current conversation/session or a resumable handoff. Use activity-report for cross-session daily/weekly reports and git-activity-summary for Git-only history.
version: 4.0.0
last_updated: 2026-08-21
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Session Wrap

1. Confirm current-session scope.
2. Inspect only the minimum relevant status, diff stat, validation, and artifacts.
3. Separate outcomes, decisions, validation, risks, open work, and next actions.
4. Keep `status` and `verification` distinct. Do not equate implementation with verified completion.
5. Emit a v2 receipt only when requested, required for a durable handoff, or local receipt persistence is explicitly enabled.
6. Do not archive, write memory, commit, push, publish, or send.

## Receipt v2

```json
{
  "schema_version": 2,
  "kind": "activity-session-receipt",
  "session_date": "YYYY-MM-DD",
  "work_items": [{
    "schema_version": 2,
    "kind": "work-activity-item",
    "item_id": "stable-id",
    "subject_id": "explicit-subject",
    "project_id": "project-id",
    "activity_date": "YYYY-MM-DD",
    "title": "sanitized item",
    "status": "planned|in_progress|done|blocked",
    "verification": "verified|reported|missing",
    "outcomes": [],
    "evidence_refs": [],
    "blockers": [],
    "next_actions": [],
    "raw_content_stored": false
  }],
  "raw_content_stored": false
}
```

Require explicit `subject_id`; never infer it from Git, paths, memory, or chat identity. A verified done item requires evidence. Persist only under `~/knowledge-hub/.tmp/activity/receipts/YYYY-MM-DD/<receipt-id>.json` when authorized by local v2 configuration.
