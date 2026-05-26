# OpenAI Local Runtime Boundary Governance Session Wrap

## Scope

- Project: `/home/leiwenjun/codex`
- Date: 2026-05-24
- Session focus: absorb OpenAI official Developers guidance into local-only Codex governance.
- Explicit non-goal: no Cloud, GitHub, Slack or Linear integration.

## Completed Work

- Reviewed OpenAI official Developers sources for Codex permissions, rules, hooks, automations, app commands, governance/observability, structured outputs, function calling, tools, conversation state and Codex safety.
- Added local runtime boundary manifests:
  - `manifests/permission_profiles.json`
  - `manifests/exec_rules.json`
  - `manifests/hook_contracts.json`
- Extended governance validation/reporting in `tools/codex_assets/governance.py`.
- Added governance tests for permission profiles, exec rules and hook contracts in `tests/test_governance.py`.
- Extended local governance assets:
  - `automations`: added local runtime boundary review as disabled/report-only.
  - `cli_command_contracts`: added `/plan`, `/status` and `/mcp`.
  - `slash_command_runtime_audits`: added `/mcp` and `/status`.
  - `context_state_contracts`: added official conversation-state layering.
  - `eval_suites`, `trace_eval_contracts`, `prompt_experiments`, `workflow_recipes`: added local runtime boundary coverage.
  - `official_docs_freshness_gates`: added second-batch official OpenAI source URLs with retrieved/expiry metadata.
- Updated docs:
  - `docs/codex-asset-management.md`
  - `docs/codex-cli-config-guide.md`
  - `docs/codex-operating-model.md`
  - `docs/design.md`
- Committed and pushed the change:
  - `dd0ba05 feat(codex): 落地本地运行边界治理`
  - pushed to `origin/main`

## Key Decisions

- Keep runtime configuration on legacy `sandbox_mode`; do not mix beta `default_permissions` with existing sandbox settings.
- Treat hook support as a reviewed contract, not a complete enforcement boundary.
- Keep all new automation candidates disabled or report-only.
- Keep OpenAI Docs MCP read-only; do not upload private code, secrets or unredacted logs.
- Preserve local-only scope and avoid external SaaS integration.

## Validation Evidence

- `rtk python3 -m unittest tests.test_governance tests.test_agent_routing_eval`: 35 tests OK.
- `rtk bash scripts/doctor.sh --scope all`: 0 errors, 0 warnings.
- `rtk git diff --check`: pass.
- `rtk bash scripts/check-routing-precedence.sh`: default profile has no active Superpowers skills.
- `rtk bash scripts/check.sh`: pass, including multi-profile smoke.
- `rtk bash scripts/final-ready.sh`: pass; HOT status was context pressure and dirty worktree warning, not validation failure.
- `rtk codex --strict-config doctor --summary --ascii`: no failures; only update note for newer Codex version.
- `rtk codex mcp list`: `openaiDeveloperDocs` enabled; `github` and `figma` disabled.

## Durable Lessons

- OpenAI official guidance should be promoted through freshness gates and small manifest contracts before expanding `AGENTS.md`.
- Permissions, command rules and hooks need negative tests; otherwise they become policy prose instead of enforceable governance.
- Hook contracts must state unsupported coverage explicitly before any runner is installed.
- For this repository, source-to-live health must include build, doctor, plan/dry-run, apply, diff/drift, check and final-ready evidence.

## Memory Curation Notes

- Candidate for long-term rule: keep OpenAI official guidance promotions behind source URL, retrieved_at, review_status, expires_at, rollback and governance eval evidence.
- Candidate for long-term rule: local runtime boundary changes must not broaden sandbox, network or approval defaults without strict-config doctor and rollback evidence.
- Keep this session as archive evidence; do not write directly to `~/.codex/memories` without a separate reviewed memory-candidate step.

## Current Repository State At Closeout

- Branch: `main`
- Remote sync: `main...origin/main`
- Worktree before this archive step: clean.

