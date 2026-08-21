---
name: project-daily-summary
description: Generate a same-day project report from a governed Knowledge Hub activity facts package, structured Codex session receipts, registered Git activity, and sanitized memory cues. Use only for 日报, 今天做了什么, or same-day all-project summaries. Prefer project-activity-report for weekly/custom periods, commit-daily-summary for commit-only output, and session-wrap for the current session only.
version: 3.2.0
last_updated: 2026-08-02
---

# Project Daily Summary

Produce a Chinese same-day report grouped by project and workstream. This is the compatibility daily entry; use the same evidence and privacy contract as `project-activity-report`.

## Workflow

1. Resolve the local date and timezone.
2. Prefer `.tmp/reports/daily/YYYY-MM-DD.json` from Knowledge Hub. Generate it report-only when absent:

   ```bash
   rtk bash ~/knowledge-hub/tools/knowledge-metrics.sh --activity-report daily --as-of YYYY-MM-DD --summary-json
   ```

3. Validate the period, coverage, warnings, and privacy flags.
4. Merge Hub records, Git commits/dirty state, and structured `session-wrap` receipts by project.
5. Group each project into 1–5 workstreams. Separate completed, progressing, and pending items.
6. State validation evidence and coverage gaps. Do not infer completion from a commit, dirty worktree, plan, or memory cue alone.

## Source Policy

Use: governed facts JSON → structured receipts → Git evidence → sanitized memory cues. Raw session transcripts are excluded by default. Read them only for an explicitly authorized `full` report, extract bounded signals, and never copy raw content.

## Output

Include date/timezone/source coverage; project objective, completed work, progress, validation, commits/dirty state, risks, and next action; cross-project highlights; and privacy limitations.

Write in concise Chinese and avoid chronological process narration. Do not write memory, archive, commit, push, publish, or send.
