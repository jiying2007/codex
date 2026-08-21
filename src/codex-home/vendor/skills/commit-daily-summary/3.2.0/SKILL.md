---
name: commit-daily-summary
description: Generate commit-only summaries for one day or an explicit date range across one or more Git repositories. Use when the user asks for 提交总结, commit 日报, Git 周期总结, or wants only Git history. Prefer project-activity-report when Hub records, Codex receipts, memories, uncommitted work, or a full daily/weekly report are required.
version: 3.2.0
last_updated: 2026-08-02
---

# Commit Daily Summary

Turn bounded Git history into a Chinese workstream summary. Preserve the compatibility name while supporting daily and explicit custom periods.

## Workflow

1. Resolve the inclusive local date range and explicit repository set.
2. Collect each repository with:

   ```bash
   rtk git -C <repo> log --since="YYYY-MM-DD 00:00" --until="YYYY-MM-DD 23:59:59" --pretty=format:"%h%x09%ad%x09%s" --date=iso-strict
   ```

3. Deduplicate equivalent repositories and group related commits by project and workstream.
4. Treat merge commits, rebuild-only commits, dependency bumps, and formatting as supporting evidence unless they carry an independent outcome.
5. Rewrite commit subjects into concise action/result statements. Do not claim a commit was authored by Codex without session evidence.
6. State repositories with no matching commits and any truncation or access gap.

## Output

Include the period, repository coverage, grouped workstreams, bounded commit identifiers when useful, and source limitations.

Do not read sessions or memory, inspect unrelated diffs, or infer validation/completion beyond commit evidence.
