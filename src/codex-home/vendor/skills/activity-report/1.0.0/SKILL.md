---
name: activity-report
description: Generate evidence-bounded personal, project, or portfolio daily, weekly, and custom-period reports from Knowledge Hub activity facts v2. Use for 日报、周报、个人工作总结、项目进展、跨项目汇总、本周事项, or management briefs. Require explicit scope or a configured default; use git-activity-summary for Git-only output and session-wrap for the current session.
version: 1.0.0
last_updated: 2026-08-21
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Activity Report

Generate a result-first Chinese report from `knowledge-hub.activity-facts-v2`.

## Resolve the request

1. Resolve `period`: `daily`, `weekly`, or `custom`.
2. Resolve `scope`: `personal`, `project`, or `portfolio`. Use local `default_scope` only when the user omits it; return `needs-input` when both are absent.
3. Resolve `detail`: `brief`, `normal`, or `full`.
4. Require `subject_id` for personal scope and `project_id` for a bounded project request. Never infer identity from Git, paths, memory, or conversation history.

## Run the deterministic collector

```bash
rtk bash ~/knowledge-hub/tools/knowledge-activity.sh report --period weekly --scope personal --summary-json
```

Validate schema, period, hashes, source coverage, privacy flags, and warnings before summarizing. Read [facts-contract.md](references/facts-contract.md) and [authority-policy.md](references/authority-policy.md) when interpreting evidence. Read [routing-matrix.md](references/routing-matrix.md) for ambiguous prompts and [output-contract.md](references/output-contract.md) for the selected scope.

## Classify evidence

- Render `done + verified` as 已完成.
- Render `done + reported/missing` as 已完成待验证.
- Keep `in_progress`, `blocked`, and `planned` distinct.
- Git activity, dirty state, Hub reviewing records, memory, and plans do not prove completion or personal ownership.

## Safety gate

- Accept only facts schema v2; do not read or convert older inputs.
- Do not read raw sessions, logs, auth, cache, secrets, raw memory, customer identifiers, or device identifiers.
- Do not write memory, promote facts, commit, push, publish, send, or delete.
- Keep empty reports actionable: state missing subject/config/items/receipts and the bounded capture action.
