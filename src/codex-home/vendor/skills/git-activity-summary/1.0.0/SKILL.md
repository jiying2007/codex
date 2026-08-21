---
name: git-activity-summary
description: Summarize bounded Git history for a daily, weekly, or custom period across an explicit repository set. Use for 提交总结、Git 日报、Git 周报、commit-only reports, or repository activity summaries. Do not use for personal ownership, completion claims, Hub facts, or current-session handoff.
version: 1.0.0
last_updated: 2026-08-21
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Git Activity Summary

1. Resolve an inclusive local period and explicit repository set.
2. Collect bounded `git log` evidence and report missing repositories or truncation.
3. Group commits by repository and workstream. Treat merge, rebuild, dependency, and formatting commits as supporting evidence unless independently meaningful.
4. Do not infer author identity, validation, completion, business outcome, or personal ownership from commits.
5. Do not read sessions, Hub records, memory, unrelated diffs, auth, or secrets.

Output the period, repository coverage, grouped workstreams, bounded commit ids when useful, and limitations.
