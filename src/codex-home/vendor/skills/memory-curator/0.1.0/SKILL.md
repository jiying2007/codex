---
name: memory-curator
description: Use when the user asks to curate, consolidate, audit, or periodically整理 Codex memory sources including ~/.codex/memories, project AGENTS.md, session summaries, daily reports, research notes, troubleshooting conclusions, and decision records. Produces an auditable memory curation report and optional memory candidate without silently rewriting memories or AGENTS.
version: 0.1.0
last_updated: 2026-05-10
---

# Memory Curator

Use this skill to periodically organize durable Codex knowledge sources.

## Scope

Inputs:

- `~/.codex/memories`
- Project and global `AGENTS.md`
- `~/codex/docs/archive/**`
- Optional `codex-agent-mem` exports, context packs, and snapshots when present
- Session summaries, daily reports, troubleshooting notes, research notes, and decision records

Outputs:

- Default report: `~/codex/docs/archive/memory-curation/<timestamp>-memory-curation.md`
- Optional candidate memory: `~/.codex/memories/.codex/curation-inbox/<timestamp>-memory-candidate.md`

## Core Rules

- Default mode is report-only.
- Do not silently rewrite `~/.codex/memories` or any `AGENTS.md`.
- Promote only stable, reusable, validated knowledge.
- Keep memory concise: durable preferences, repeated decisions, constraints, and validated practices.
- Put longer context into `docs/archive/<topic>/`, not memory.
- Remove secrets, tokens, private endpoints, one-off process logs, and stale TODOs before proposing memory updates.
- Treat generated candidates as review drafts, not authoritative memory.
- Prefer source-linked curation: every proposed memory or AGENTS update should cite the report path or source file.

## Workflow

1. Run a dry-run first:

```bash
rtk bash ~/codex/scripts/curate-memory.sh --dry-run
```

2. Generate the curation report:

```bash
rtk bash ~/codex/scripts/curate-memory.sh
```

3. If the user asks for a memory candidate, generate one:

```bash
rtk bash ~/codex/scripts/curate-memory.sh --write-memory-candidate
```

4. Review the report manually. For each finding choose one action:
   - `promote-to-agents`
   - `write-to-codex-agent-mem`
   - `archive-only`
   - `drop-or-review`

5. When applying changes after review, keep edits small:
   - One memory file per durable topic
   - One AGENTS rule per repeated behavior
   - Long evidence remains in `docs/archive/`

## Promotion Guidance

Promote to `AGENTS.md` when a rule changes future agent behavior across sessions.

Promote to `~/.codex/memories` when it is a durable personal preference, stable project fact, or repeated workflow constraint.

Write to `codex-agent-mem` only after manual review, and only for short structured project state such as current goal, blocker, open work, snapshot, or stable project fact.

Keep in `docs/archive/` when it is long-form evidence, a full daily report, a research note, or a troubleshooting narrative.

## codex-agent-mem Compatibility

The curator may read text exports from:

```text
~/.codex_agent_mem/
~/.codex/memories/.codex-agent-mem/
~/codex/docs/archive/codex-agent-mem/
```

If these paths do not exist, skip them. Do not require `codex-agent-mem` to be installed.

Use a three-phase memory model:

- Phase 1 report archive: default mode; generate `docs/archive/` artifacts and curation reports only.
- Phase 2 manual write: generate candidates, review them, then write `~/.codex/memories` or codex-agent-mem notes/snapshots only after explicit user approval.
- Phase 3 task loop: bootstrap context at session start, then run `knowledge-archive + memory-curator` at session end.

Do not automatically write into `codex-agent-mem`.

## Output

Report:

- Report path
- Source counts
- High-signal excerpts
- Candidate actions
- Whether any memory candidate was written
