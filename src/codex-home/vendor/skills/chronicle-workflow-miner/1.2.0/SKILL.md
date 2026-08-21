---
name: chronicle-workflow-miner
description: Inspect governed activity reports, structured Codex session receipts, curated memories, archive records, and only when necessary bounded raw history to find repeated workflows and decide whether to extend a Skill, Automation, routing rule, archive note, or skip. Use for 回顾工作记录, Chronicle 记忆, 找重复流程, 工作流沉淀, skill 优化, or automation candidates.
version: 1.2.0
last_updated: 2026-08-02
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Chronicle Workflow Miner

Mine reusable patterns while minimizing raw-history access and duplicate assets.

## Source Priority

1. Governed daily/weekly activity facts and reports.
2. Structured `session-wrap` receipts and curated task summaries.
3. Knowledge Hub Codex archive and reviewed memory summaries.
4. Existing skill, workflow, automation, agent, and routing manifests.
5. Raw Codex history/session transcripts only as an explicit, bounded fallback when aggregate evidence cannot resolve recurrence or procedure.

State the time window and source coverage. Never persist raw history in a skill or archive note.

## Creation Gate

Create or extend an asset only when all conditions hold:

- recurrence: at least two independent sessions in one project, or three sessions across at least two projects;
- stable input and recognizable trigger;
- repeatable procedure and bounded output;
- measurable improvement in quality, speed, safety, or consistency;
- existing coverage is absent or materially incomplete;
- privacy and permission boundaries are explicit.

Otherwise mark `needs-more-evidence` or `skip`.

## Decision Order

Prefer improving an existing route or local skill before adding scripts, report-only automations, or new skills. Use archive-only or skip for contextual conclusions.

## Workflow

1. Inventory current coverage before proposing assets.
2. Cluster evidence by intent, input, procedure, and output, not wording.
3. Record recurrence count, session/day/project spread, privacy boundary, current coverage, and expected gain.
4. Decide `extend-existing`, `create`, `automation-candidate`, `archive-only`, `needs-more-evidence`, or `skip` before editing.
5. Keep `SKILL.md` concise; put mechanics in scripts, detailed contracts in references, and evidence in a session report or Hub archive.
6. Register and validate approved assets through manifests and the Codex source-to-live chain.

## Output

Provide a candidate table, existing-coverage mapping, decisions, skipped items, validation evidence, and remaining risks. Never write memory, enable external automation, publish, or modify live `~/.codex` directly.
