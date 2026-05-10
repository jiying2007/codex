---
name: knowledge-archive
description: Use when the user asks to archive, persist, or沉淀 high-value Codex knowledge such as daily reports, session summaries, research notes, troubleshooting conclusions, decisions, reusable lessons, or asks for "知识归档", "长期沉淀", "日报归档", "会话总结归档", "排障结论归档", or "保存到 docs/archive". Generate or collect a sanitized Markdown artifact and archive it into ~/codex/docs/archive/<topic>/ using the repository archive-note entrypoint.
version: 0.1.0
last_updated: 2026-05-10
---

# Knowledge Archive

Use this skill to persist reusable knowledge into the long-term Codex asset repository.

## Fixed Destination

Archive durable knowledge to:

```text
~/codex/docs/archive/<topic>/
```

Do not archive knowledge into `~/.codex`, `src/codex-home/`, `build/`, or `control/`.

## Routing

When the user asks for an artifact and archive in one request, first create the artifact with the most specific skill, then archive it:

- Daily/project report: `project-daily-summary`, then `knowledge-archive`
- Current session summary: `session-wrap`, then `knowledge-archive`
- Research/architecture/diagnosis note: `research-note-wrap`, then `knowledge-archive`
- Commit-only summary: `commit-daily-summary`, then `knowledge-archive`

If the user only says "知识归档" without a source path, infer the current conversation or the latest generated summary as the source when safe. If no source or content can be identified, ask for the file path or content.

## Workflow

1. Identify source content:
   - Existing file or directory path supplied by the user
   - A newly generated Markdown summary/note
   - A concise note derived from the current session, only when the user clearly asked to archive it
2. Choose topic:
   - `daily-summary` for 日报/今日总结
   - `session-wrap` for current session closeout
   - `external-articles` for articles, webpages, newsletters, and public posts
   - `research-notes` for research or architecture notes
   - `debug-notes` for troubleshooting conclusions
   - Otherwise use a short kebab-case topic from the subject
3. Sanitize before archiving:
   - Remove secrets, tokens, auth material, private endpoints, and one-off process noise
   - Keep reusable facts: background, constraints, decisions, evidence, validation, next actions
   - Preserve provenance: source path, date, project, command/test evidence when available
   - Avoid duplicate archive entries when an equivalent note already exists in the topic index
4. Archive using the repository entrypoint:

```bash
rtk bash ~/codex/scripts/archive-note.sh <source> --topic <topic> --title "<title>"
```

Use `--dry-run` first when the source is outside the repository, large, or user-provided.

## External Article Template

Use this structure for webpages, public posts, newsletters, WeChat articles, and other external material:

```markdown
# <Title>

## Source

- URL:
- Publisher / Author:
- Published At:
- Captured At:
- Access Method: web | browser-reader | user-provided
- Verification Status: visible-content | manual-verified | blocked | partial
- Copyright Note: summary only

## Summary

- 3 to 7 concise points

## Key Decisions / Claims

- Claim or decision
- Why it matters locally

## Action Items

- Concrete follow-up
- Promote to AGENTS.md: yes/no
- Candidate for memory-curator: yes/no

## Evidence

- Short excerpts or location notes only
```

For `mp.weixin.qq.com`, record whether the page was read through `browser-reader`, whether user/manual verification was needed, and whether only visible content was available.

## Safety Rules

- Never archive `~/.codex/auth.json`, sessions, logs, cache, tmp, `mcp/secrets`, private keys, or runtime databases.
- Never use `--move` unless the user explicitly asks to move the source.
- Do not commit automatically unless the user asks for a commit.
- If `~/codex/scripts/archive-note.sh` is missing, report the blocker and do not invent an alternate archive path.
- If the archived note should affect future behavior, propose a separate `memory-curator` or `AGENTS.md` promotion step instead of hiding rules in archive content.

## Output

After archiving, report:

- Archive path
- Topic
- Whether it was generated, copied, or moved
- Source URL or source path when applicable
- Any verification run
