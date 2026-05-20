---
name: chronicle-workflow-miner
description: "Use when the user asks to inspect Chronicle, Codex history, memories, or archive records to find repeated workflows and convert them into skills, AGENTS routing rules, archive notes, or asset-governance updates."
version: 1.0.0
last_updated: 2026-05-20
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Chronicle Workflow Miner

Use this skill to mine repeated working patterns from local Chronicle-like memory sources and turn stable patterns into reusable Codex assets.

## Sources

Read only the sources needed for the task:

- `~/.codex/history.jsonl`
- `~/.codex/memories/**`
- `~/codex/docs/archive/**`
- `~/codex/AGENTS.md` and project `AGENTS.md`
- Optional Codex sqlite/log stores, only for aggregate metadata when needed

## Workflow

1. Identify the memory source. If no Chronicle server is exposed, treat Codex history, memories, and archive reports as the local Chronicle corpus.
2. Cluster user requests by recurring intent, not by identical wording.
3. Report aggregate counts, session spread, and sanitized examples. Do not paste raw long logs.
4. Map each cluster to one action:
   - use an existing skill;
   - update an existing skill or routing rule;
   - create a new skill;
   - keep as archive-only if the pattern is too project-specific.
5. For new skills, keep `SKILL.md` concise and move only durable procedure into the skill.
6. Register new skills in `manifests/skills.json`; add workflow routing only when it improves automatic selection.
7. Run the source-to-live validation chain before claiming the skills are usable.

## Safety

- Never echo secrets, credentials, tokens, private keys, cookies, or auth files.
- Sanitize internal endpoints and credentials in examples unless they are essential and user-approved.
- Do not write directly into `~/.codex` memories or live skills.
- Do not convert one-off project state into global rules.

## Output

Include:

- source summary;
- repeated workflow clusters;
- skill mapping decisions;
- files changed;
- validation evidence;
- unresolved patterns that should remain archive-only.
