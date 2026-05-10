---
name: context-compress-handoff
description: Use when the user asks for proactive context compression, session handoff, resume context, "压缩前处理", "会话接力", "恢复提示", or "90秒模板". Produce a compact preflight artifact, archive a session summary, and prepare resume-ready context without silently writing long-term memory.
version: 0.1.0
last_updated: 2026-05-10
---

# Context Compress Handoff

Use this skill to standardize pre-compression closeout and next-session handoff.

## Scope

Good fits:

- Long session before context compression
- User asks for "会话接力", "恢复上下文", "压缩前收口"
- Need a deterministic handoff artifact with commands and next actions

Poor fits:

- Pure daily report requests (use `project-daily-summary`)
- Commit-only summary (use `commit-daily-summary`)
- Memory write requests that skip review (use `memory-curator` with manual review)

## Workflow

1. Generate preflight artifact:

```bash
rtk bash ~/codex/scripts/context-preflight.sh
```

2. Create or refresh session summary:

- Prefer `session-wrap` structure for current session
- Keep only reusable decisions, constraints, validation, and next actions

3. Archive handoff materials:

```bash
rtk bash ~/codex/scripts/archive-note.sh <session-summary.md> --topic session-wrap --title "<title>"
```

4. Curate memory in report-only mode:

```bash
rtk bash ~/codex/scripts/curate-memory.sh --dry-run
```

5. If context is very large or noisy, optionally delegate extraction to `local-context-curator` and keep final decisions in the main agent.

## Output

Always report:

- Preflight artifact path
- Archived session summary path
- Memory-curation report or dry-run result
- Resume prompt block with first command and top 3 next actions

## Safety

- Do not silently write `~/.codex/memories` or codex-agent-mem.
- Do not auto-commit unless the user asks.
- Do not archive runtime/secrets/session/log/cache paths.
