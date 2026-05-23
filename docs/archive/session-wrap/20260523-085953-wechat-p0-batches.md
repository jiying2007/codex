# Session Wrap: WeChat P0 Absorption Batches

- Date: 2026-05-23
- Project: `/home/leiwenjun/bin/llm_agent`
- Scope: continuation session for `wechat-articles/` P0 absorption, covering batch `wechat-p0-001` and `wechat-p0-002`.
- Source ledger: `reports/wechat-article-intake.jsonl`
- Decision overlay: `reports/wechat-article-decisions.tsv`

## Completed Work

### Batch 1: `wechat-p0-001`

- Processed the first 10 next-batch rows from `reports/wechat-absorb-next-batch.md`.
- Absorbed 9 P0 articles and deferred the single P1 multi-agent item.
- Decisions:
  - `MERGE / absorbed-method-only`: 7
  - `REFERENCE_ONLY`: 2
  - `DEFER`: `wechat-0012`, because it belongs to `P1-multi-agent-review`.
- Created `reports/wechat-absorb-batch-2026-05-23-p0-001.md`.
- Added `reports/wechat-article-decisions.tsv` as the reviewed decision overlay.
- Regenerated `reports/wechat-article-intake.jsonl` and `reports/wechat-absorb-next-batch.md`.

### Batch 2: `wechat-p0-002`

- Processed the next 10 queued P0 candidates:
  - `wechat-0026`, `wechat-0027`, `wechat-0037`, `wechat-0038`, `wechat-0040`, `wechat-0045`, `wechat-0046`, `wechat-0051`, `wechat-0052`, `wechat-0054`.
- Decisions:
  - `MERGE / absorbed-method-only`: 8
  - `REFERENCE_ONLY`: 2
- Created `reports/wechat-absorb-batch-2026-05-23-p0-002.md`.
- Regenerated the ledger and next-batch report; the next queue now starts at `wechat-0055`.

## Key Decisions

- `wechat-articles/` remains a temporary reference pool, not an authoritative ADK source.
- Absorption remains method-only: copy durable rules, gates, templates, and failure handling; do not copy article prose, tutorial code, install commands, project names, or marketplace claims into ADK core.
- Existing ADK assets are enhanced instead of creating parallel skills:
  - Skill/SOP guidance goes to `skill-curation-delivery.md` and `adk-skill-lifecycle.md`.
  - Context and memory guidance goes to `token-context-governance.md`, `memory-governance.md`, and `planning-execution-loop.md`.
  - MCP/plugin/autonomous trigger guidance goes to `mcp-governance.md` and `security-supply-chain.md`.
  - Project rule guidance goes to `workspace-maintenance-guide.md`.
- External GitHub repos, skill marketplaces, MCP recommendations, automation commands, and visual/IP skill examples remain `report-only-until-security-review`.
- No `manifest.yaml` or routing changes were made.
- No subrepo adoption matrix update was made because `wechat-articles/` is temporary reference material, not a governed source repo.

## Changed Files

### Root workspace

- `docs/absorption-governance.md`
- `docs/runbooks/wechat-article-absorption.md`
- `scripts/README.md`
- `scripts/check-doc-sync.sh`
- `scripts/generate-wechat-intake-ledger.sh`
- `scripts/check-wechat-intake-ledger.sh`
- `reports/wechat-article-intake.jsonl`
- `reports/wechat-article-decisions.tsv`
- `reports/wechat-absorb-next-batch.md`
- `reports/wechat-absorb-batch.template.md`
- `reports/wechat-absorb-batch-2026-05-23-p0-001.md`
- `reports/wechat-absorb-batch-2026-05-23-p0-002.md`

### `agent-dev-kit`

- `docs/runbooks/mcp-governance.md`
- `docs/runbooks/memory-governance.md`
- `docs/runbooks/planning-execution-loop.md`
- `docs/runbooks/security-supply-chain.md`
- `docs/runbooks/skill-curation-delivery.md`
- `docs/runbooks/token-context-governance.md`
- `docs/runbooks/workspace-maintenance-guide.md`
- `docs/skill-agent-runtime-model.md`
- `optional-skills/adk-skill-composition-governance/references/adk-skill-lifecycle.md`

## Validation Evidence

- `rtk scripts/check-wechat-intake-ledger.sh .`: PASS, `articles=313`
- `rtk agent-dev-kit/scripts/check-token-budget.sh`: PASS
- `rtk agent-dev-kit/scripts/check-memory-governance.sh`: PASS
- `rtk agent-dev-kit/scripts/validate-assets.sh --strict`: PASS
- `rtk agent-dev-kit/tests/run_all.sh`: PASS, `37/37`
- `rtk scripts/check-doc-sync.sh .`: PASS
- `rtk scripts/check-skill-routing-conflicts.sh .`: PASS
- `rtk bash -lc "git diff --check"`: PASS
- `rtk scripts/check-all.sh --quick`: NEEDS-FIX, `26/28`
  - Failed: `check-subrepo-state.sh`, `check-evidence-bundle.sh`
  - Root cause: `agent-dev-kit` is a strict subrepo and is dirty until its local changes are committed.
  - `rtk scripts/check-subrepo-state.sh . --summary-json`: `known_dirty=20`, `unexpected_dirty=1`, where the unexpected dirty repo is `agent-dev-kit`.

## Current Worktree Notes

- `agent-dev-kit` is intentionally dirty from this session's ADK runbook updates.
- 20 observe-mode reference subrepos remain known dirty baseline.
- `wechat-articles/` is still untracked input material.
- No commit or push was performed in this session.

## Next Actions

1. New session should start from `reports/wechat-absorb-next-batch.md`; the next P0 batch begins with `wechat-0055`.
2. Continue using `reports/wechat-article-decisions.tsv` as the only reviewed decision input; do not hand-edit `reports/wechat-article-intake.jsonl`.
3. Keep external code and MCP/tool recommendations report-only until per-asset supply-chain review.
4. Before claiming full repository gate pass, commit `agent-dev-kit` changes or otherwise resolve the strict subrepo dirty state, then rerun:
   - `rtk scripts/check-subrepo-state.sh . --summary-json`
   - `rtk scripts/check-all.sh --quick`
5. Given session-coach `CRITICAL / THREAD_LONG / CTX_PRESSURE`, resume in a new conversation rather than continuing this thread.

## Memory Candidates

- Durable project rule: WeChat article absorption must be decision-overlay driven. `reports/wechat-article-decisions.tsv` is the reviewed state input; `reports/wechat-article-intake.jsonl` is generated and should not be edited manually.
- Durable project rule: P0 article absorption is method-only unless a candidate passes security/supply-chain review; external repos, MCP recommendations, install commands, marketplace claims, and tutorial code remain `report-only`.
- Durable ADK rule: New Skill creation requires a reuse threshold, atomicity, pattern classification, dependency boundary, and proof that existing skills cannot be enhanced instead.
