# Activity Facts Contract

Use `knowledge-hub.activity-report` facts as the default machine-readable input.

## Required fields

- `schema_version`
- `report_kind`: `daily` or `weekly`
- `timezone`
- `period.start` and `period.end`
- `summary`
- `registry_activity[]`
- `git_activity[]`
- `session_receipts[]`
- `memory_cues[]`
- `source_coverage`
- `privacy`
- `warnings[]`

## Authority

Apply this order: Hub registry/current facts, local Git evidence, Codex archive provenance, auxiliary memory cues. A lower lane may add context but cannot override a higher lane.

## Privacy gate

Require these flags to remain false before rendering:

- `raw_sessions_stored`
- `raw_logs_stored`
- `raw_memory_stored`
- `credentials_stored`
- `absolute_workspace_paths_stored`
- `memory_write`
- `external_write`

Stop and report `needs-fix` when a required privacy flag is true or missing. Do not repair a sensitive facts package by echoing its contents.

## Completion evidence

Git commits and registry activity prove activity, not completion. Treat an item as completed only when the facts or a structured session receipt includes validation or an explicit final outcome. Otherwise classify it as progress or pending review.

## Structured session receipt

Accept a receipt with these bounded fields:

```json
{
  "schema_version": 1,
  "kind": "codex-session-receipt",
  "project": "repo-id",
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

Reject receipts that embed raw transcript text, secrets, authentication state, or unrestricted absolute paths.

When persistence is explicitly authorized, write one receipt per session below
`~/knowledge-hub/.tmp/session-receipts/YYYY-MM-DD/<receipt-id>.json`. The report collector
validates the schema, period, privacy flag, and size before accepting it. Never create this
file merely because a session ends.
