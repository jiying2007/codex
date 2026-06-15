---
name: chronicle-workflow-miner
description: "Use when the user asks to inspect Chronicle, Codex history, recent sessions, task summaries, memories, archive records, or work logs to find repeated manual workflows and convert only high-confidence reusable patterns into Skills, Custom subagents, Automations, routing updates, archive notes, or Skip decisions. Especially use for requests like: 回顾过去30天工作记录, 查看Chronicle记忆, 找出值得打包的重复流程, 转化为技能, 工作流沉淀, or identify repeated coding/research/writing/planning/communication/operations/analysis/personal workflows."
version: 1.1.0
last_updated: 2026-06-15
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Chronicle Workflow Miner

Use this skill to mine repeated working patterns from local Chronicle-like memory sources and turn only stable, high-value patterns into reusable Codex assets.

## Source Priority

Read only the sources needed for the task, in this priority order:

1. Recent Codex sessions and task summaries:
   - `~/.codex/history.jsonl`
   - `~/.codex/sessions/**`
   - `~/codex/docs/archive/_registry/**`
   - recent `session-wrap`, `project-daily-summary`, and `commit-daily-summary` archive notes.
2. Codex memories and curated summaries:
   - `~/.codex/memories/**`
   - `~/codex/docs/archive/memory-curation/**`
   - project-level `AGENTS.md`, `README.md`, and durable runbooks when referenced by memories.
3. Chronicle, if exposed:
   - use Chronicle only for discovery outside Codex;
   - confirm important details back in the original system, file, repo, ticket, or message before creating assets.
4. Existing assets:
   - `manifests/skills.json`
   - `manifests/agents.json`
   - `manifests/automations.json`
   - `manifests/workflows.json`
   - `src/codex-home/vendor/skills/**`
   - `src/codex-home/control/agents-local/**`

If no Chronicle server or resource is exposed, treat Codex history, memories, and archive reports as the local Chronicle corpus.

## Discovery Scope

Cast a wide net. Include repeated manual workflows from:

- coding, debugging, reviewing, refactoring, release, testing, and repo governance;
- research, external article absorption, browser reading, patent drafting, and technical analysis;
- writing, summaries, archive notes, planning, handoff, and communication drafts;
- operations, reporting, dashboards, token/usage checks, publishing, packaging, and local automation;
- personal or administrative workflows only when local evidence exists and privacy boundaries are clear.

Cluster by recurring intent, input shape, procedure, and output, not by identical wording.

## Creation Gate

Create or update an asset only when all conditions are met:

- recurrence: happened at least twice, or is clearly likely to recur and costly to redo;
- stable input: the workflow starts from recognizable artifacts such as logs, repos, docs, tickets, messages, reports, or URLs;
- repeatable procedure: the steps can be described without relying on one-off context;
- clear output: the result is a report, patch, plan, checklist, artifact, draft, command sequence, or decision;
- real improvement: packaging it improves speed, quality, consistency, safety, or reliability;
- coverage gap: existing skills, custom agents, automations, scripts, or workflow routes do not already cover it well.

If any condition is missing, mark the candidate as `needs-more-evidence` or `skip`.

## Decision Matrix

Choose the smallest applicable form:

- `Skill`: use for judgment-heavy but repeatable workflows with stable inputs and reusable output contracts.
- `Custom subagent`: use when the workflow is an ongoing role with a distinct review surface, can run independently, and has clear read/write boundaries.
- `Automation`: use when the workflow is periodic or event-driven, can run report-only or with explicit approval gates, and has defined data sources, cadence, stop condition, and retention.
- `Routing/update`: use when an existing skill already covers the procedure but triggers too late, too often, or not at all.
- `Archive-only`: use when the conclusion is useful but project-specific or too contextual for a global skill.
- `Skip`: use when evidence is weak, output is unclear, privacy risk is high, or existing tooling already covers it.

Prefer reusing or extending existing assets over creating new ones.

## Workflow

1. Identify sources:
   - state whether Chronicle was available;
   - state the effective corpus and time window;
   - avoid reading raw long logs when aggregate metadata and summaries suffice.
2. Inventory existing coverage:
   - list relevant skills, custom agents, automations, workflows, and scripts before proposing new assets.
3. Mine candidates:
   - report candidate name, evidence count, session/day spread, input, procedure, output, likely form, and current coverage;
   - include sanitized examples only, never long raw logs or secrets.
4. Decide before creating:
   - output the candidate list first when the user asks for it;
   - mark each candidate as `create`, `extend-existing`, `automation-candidate`, `custom-subagent-candidate`, `needs-more-evidence`, or `skip`.
5. Create high-confidence assets:
   - keep `SKILL.md` concise and put only durable procedure into the skill;
   - keep evidence trail in final response, session summary, or archive note, not in the loaded skill body;
   - register new or updated skills in `manifests/skills.json`;
   - update workflow routing only when it improves automatic selection.
6. Apply source-to-live governance:
   - do not edit live `~/.codex` directly;
   - use the `~/codex` source-to-live build, plan, dry-run, apply, and check chain before claiming usability.

## Output

Include:

- source summary and whether Chronicle was available;
- repeated workflow candidate table;
- existing-coverage and decision mapping;
- created or updated assets with file paths;
- skipped candidates and why;
- candidates needing more evidence;
- validation evidence and remaining risks.

## Safety

- Never echo secrets, credentials, tokens, private keys, cookies, auth files, or private build-machine identity.
- Sanitize internal endpoints and credentials in examples unless they are essential and user-approved.
- Do not write directly into `~/.codex` memories or live skills.
- Do not convert one-off project state into global rules.
- Do not create background automations that send, submit, publish, delete, merge, or overwrite without explicit user approval.
- Do not rely on Chronicle-only details for important facts; confirm them in original sources before creating assets.
