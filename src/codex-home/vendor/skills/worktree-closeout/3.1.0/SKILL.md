---
name: worktree-closeout
description: "Use only for read-only branch/worktree closeout triage across sessions or repos: date/scope scan, status classification, merge/prune order, and handoff prompts. Prefer session-wrap for one current session, project-daily-summary for daily project reports, and commit-daily-summary for commit-only summaries."
version: 3.1.0
last_updated: 2026-04-27
---

# worktree-closeout

## Overview

Read-only closeout triage for Codex work that spans multiple sessions, branches, or worktrees.

This skill does **not** auto-merge, auto-delete, auto-push, or auto-prune. It asks for a date and scope, runs the scanner, reads the generated artifact, then turns that artifact into a chat summary, a suggested closeout order, and prompt-ready handoff instructions.

## When to Use

- User wants to know which worktrees or branches still need 收口
- Work was split across multiple sessions and the current status is unclear
- You need a date-based scan before deciding merge / keep / prune actions
- You want a controller prompt plus per-item prompts for closeout follow-up

## When Not to Use

- **Single current session wrap-up:** use `session-wrap`
- **Same-day project report:** use `project-daily-summary`
- **Single branch is already chosen for final handling:** use `finishing-a-development-branch`
- **Dangerous branch actions:** do not use this skill as permission to merge, delete, prune, or push automatically
- **Skill asset import or governance:** use `skill-asset-manager`

`project-daily-summary` may optionally call this skill when the user wants a **same-day all-repo summary with a closeout appendix**.

## Routing Boundary

Use this skill only when the user asks about **branches, worktrees, closeout, prune, merge order, or parallel closeout**.

Do not use it for generic "日报" or "总结今天"; those should route to `project-daily-summary` or `commit-daily-summary` depending on evidence source.

## Required Flow

### 1. Ask for the date first

Always resolve the date before asking anything else.

- Accept `YYYY-MM-DD` or a relative day such as “昨天”
- Restate the resolved **exact date**
- If the user already supplied a clear date, confirm it instead of inventing a different one

### 2. Ask for the scope second

Ask whether to scan:

- `当前 repo` / `current repo` → scanner scope `repo`
- `所有 repo` / `all repos touched that day` → scanner scope `all`

Do not assume the scope.

If scope is `repo`, pass the absolute repo root with `--repo`.

### 3. Run the scanner

```bash
rtk python3 -X utf8 ./scripts/scan_closeout.py --date <YYYY-MM-DD> --scope <repo|all> [--repo <ABSOLUTE_REPO_PATH>]
```

Notes:

- `scan_closeout.py` is the source of truth for classification and artifact rendering
- Run the command from the skill root directory, or adapt the script path to your local install path
- Read the artifact path from the script output (`Wrote closeout artifact: ...`)
- Keep the run read-only; do not chain cleanup commands after the scan

### 3.1 Fallback when scanner is unavailable

If the script cannot run (Python missing, path error, permission issue), do not stop silently.

Use this read-only fallback and label the result as `manual-triage`:

1. collect repo/worktree baseline:
   - `git worktree list --porcelain`
   - `git branch --all --verbose --verbose`
2. collect per-worktree dirtiness:
   - `git -C <worktree_path> status --short`
3. collect merge relation for candidate branches:
   - `git -C <repo_root> branch --merged <base>`
   - `git -C <repo_root> branch --no-merged <base>`
4. output closeout phases with explicit uncertainty tags:
   - `safe_prune?`
   - `ready_to_merge?`
   - `blocked`
   - `orphaned`

In fallback mode, always include:

- why scanner mode failed
- which commands were executed
- which conclusions are uncertain and need rerun with scanner

### 4. Read the artifact

Open the generated Markdown artifact and use `references/artifact-format.md` if you need a quick schema reminder.

Pay attention to:

- frontmatter counts and `status`
- `## 建议收口顺序`
- per-repo category sections
- `## 建议总控 Prompt`
- `## 建议子 Prompt`

### 5. Output the chat summary

Summarize the artifact in chat, in Chinese by default:

- scan date and scope
- repo/worktree totals
- which repos or branches need attention first
- any uncertain or orphaned items that need manual re-triage

If the artifact is effectively empty, say so explicitly instead of pretending there is work to close out.

### 6. Output the suggested parallel order

Use the artifact’s closeout phases directly:

- `Phase 1: 可并行 -> safe_prune`
- `Phase 2: 条件并行 -> ready_to_merge`
- `Phase 3: 串行收尾 -> blocked, orphaned`

Do not promote `blocked` or `orphaned` items into a broad parallel merge wave.

### 7. Output the prompts

Always output:

1. the controller prompt
2. each closeout item prompt

When presenting per-item prompts, preserve the artifact’s label context:

- classification
- repo
- branch or fallback worktree label

## Classification Guide

### `safe_prune`

- Branch is already merged into the base branch
- Worktree is clean
- Suitable for **manual** cleanup confirmation

### `ready_to_merge`

- Branch is not merged
- Worktree is clean
- Branch is ahead of base
- Recent session evidence suggests it is an active, real candidate

Hand these to `finishing-a-development-branch` when the user wants to actually complete one branch.

### `blocked`

- Dirty worktree, behind-base state, base-branch worktree with active changes, or another signal that the item is not ready for final closeout

These need the smallest safe unblock step first.

### `orphaned`

- Missing or weak git/session evidence
- Cannot justify merge/prune confidently from current facts

These need re-triage, not aggressive cleanup.

## Output Contract

Your final closeout response should contain, in this order:

1. short chat summary
2. suggested parallel order
3. controller prompt
4. per-item prompts
5. artifact path

Do not hide uncertainty. If the artifact and current chat context disagree, call that out.

## Relationship to Other Skills

### `session-wrap`

- `session-wrap` closes **one current session**
- `worktree-closeout` scans **across sessions/worktrees for a chosen date**

### `project-daily-summary`

- `project-daily-summary` is still the primary same-day, by-project summary skill
- Use `worktree-closeout` only when the user also needs a date-based branch/worktree closeout appendix
- For “当天所有 repo closeout appendix” scenarios, `project-daily-summary` may choose to call this skill

### `finishing-a-development-branch`

- `worktree-closeout` identifies which items are candidates
- `finishing-a-development-branch` performs the single-branch finish flow after a candidate is chosen

## Guardrails

- No automatic merge
- No automatic branch deletion
- No automatic worktree removal
- No automatic push or PR creation
- No fabricated status if the scan comes back empty or ambiguous

Use this skill to organize closeout work, not to silently execute risky git actions.
