---
name: embedded-app-doc-handoff
description: "Use when the user asks Codex to prepare embedded independent app repositories for handoff: README/AGENTS/docs restructuring, Chinese agent or skill text, `.codex/skills/<app>` creation, submit-range cleanup, quick validation, or pre-commit checks for apps such as app_ota and app_product_test."
version: 0.1.0
last_updated: 2026-06-28
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded App Doc Handoff

Use this skill for independent embedded app repositories that need durable onboarding docs, local app skills, and clean pre-commit boundaries.

## ADK Composition

- Primary when the task targets independent embedded app repo handoff, README/AGENTS/docs restructuring, app-local `.codex/skills/<app>`, Chinese operator guidance, or official submit-range cleanup.
- Supporting skill under `adk-commit-pr-quality-gate` when the user explicitly asks to commit, push, open a PR, or run final commit gates.
- Supporting skill under `adk-verification-before-completion` when the docs and skill structure are already changed and only evidence needs to be checked.
- Mutually exclusive as primary with `adk-embedded-release-orchestration`; documentation handoff is not a firmware release.
- Fallback to `adk-repo-drift-remediation` when the task is broad whole-repo drift cleanup rather than app-specific handoff.

## Inputs

Accept any combination of:

- app repository paths such as `app_ota`, `app_product_test`, or other independent SDK app trees;
- current README, AGENTS, docs, scripts, example files, patches, PDFs, or temporary notes;
- user requests for Chinese agent/skill text, handoff prep, PCBA/semifinished production context, or submit checks;
- app validators such as `quick_validate.py`, shell syntax checks, or project-specific grep gates.

## Workflow

1. Establish repository boundary:
   - identify whether the target is an independent app repo, parent SDK tree, or untracked material;
   - use `git status --short -- <path>` to distinguish tracked submit range from temporary inputs.
2. Normalize documentation structure:
   - keep root `README.md` and `AGENTS.md` as entry and boundary docs;
   - move detailed design, operation, production, and plan material under `docs/`;
   - keep app-local skills under `.codex/skills/<app-name>/`.
3. Prefer Chinese operational text:
   - write agent and skill guidance in Chinese when the audience is local operators or handoff engineers;
   - keep command names, identifiers, and protocol symbols in English.
4. Separate official handoff material from temporary evidence:
   - exclude PDFs, raw examples, backup files, patches, and external source material unless the user explicitly approves including them;
   - avoid moving one-off scratch files into durable docs.
5. Run app-specific gates:
   - run skill validation, `git diff --check`, conflict-marker/whitespace checks, and script syntax checks where relevant;
   - report temporary files and official staging suggestions separately.
6. Stop at the requested boundary:
   - for "提交前检查" tasks, do not commit unless the user explicitly asks;
   - for "提交并推送" tasks, continue through normal commit/push gates.

## Output

Return:

- repository boundary and tracked/untracked assessment;
- created or updated doc/skill structure;
- official submit range versus excluded temporary material;
- validation evidence;
- commit or no-commit decision based on user instruction;
- remaining handoff gaps.

## Guardrails

- Do not change template or validator frontmatter fields without checking local validator behavior.
- Do not add temporary PDFs, examples, backups, or patches to the formal submit set by default.
- Do not infer tracked status from `git diff` alone; check path status explicitly.
- Do not commit during check-only handoff tasks.
- Do not bury repository boundaries in long prose; make them explicit.
