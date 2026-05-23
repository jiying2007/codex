# Session Wrap: WeChat Article Absorption Foundation

## Source

- Project: `llm_agent`
- Date: 2026-05-23
- Scope: current Codex session
- Archive intent: session-summary, archive-only

## Completed Work

- Established a governed absorption plan for `wechat-articles/` so every archived article can be processed gradually without drifting from `llm_agent` and `agent-dev-kit` boundaries.
- Added article-level intake infrastructure:
  - `scripts/generate-wechat-intake-ledger.sh`
  - `scripts/check-wechat-intake-ledger.sh`
  - `reports/wechat-article-intake.jsonl`
  - `reports/wechat-absorb-next-batch.md`
  - `reports/wechat-absorb-batch.template.md`
  - `docs/runbooks/wechat-article-absorption.md`
- Updated governance docs:
  - `docs/absorption-governance.md`
  - `scripts/README.md`
  - `scripts/check-doc-sync.sh`
- Generated the first intake ledger:
  - total articles: 313
  - external code mentions: 99
  - external code policy: `report-only-until-security-review`

## Key Decisions

- Treat `wechat-articles/` as a temporary reference material pool, not as an authoritative ADK source.
- Do not copy article prose into core `agent-dev-kit` assets.
- Use a ledger-first process before any content absorption.
- External GitHub/source-code/install-command references remain report-only until supply-chain review.
- Existing ADK capabilities should be enhanced rather than duplicated; new skills/workflows require proof that existing assets cannot be reused.
- P0/P1 prioritization uses high-signal title/path terms; broad content-level terms such as generic `Agent` are recorded as topics but do not automatically raise priority.

## Validation Evidence

- `rtk scripts/check-wechat-intake-ledger.sh .`: pass, `articles=313`
- `rtk scripts/check-doc-sync.sh .`: pass
- `rtk scripts/check-token-budget.sh .`: pass, `scripts/README.md` kept at 520 line budget
- `rtk scripts/check-workspace-entrypoints.sh .`: pass
- `rtk scripts/check-all.sh --quick`: pass, 28/28
- `rtk agent-dev-kit/tests/run_all.sh`: pass, 37/37
- `rtk bash -lc "git diff --check"`: pass
- `rtk scripts/check-subrepo-state.sh . --summary-json`: pass, 20 known dirty observe subrepos, 0 unexpected dirty

## Current Worktree Notes

- Main tracked changes are in governance docs and new WeChat intake scripts/reports.
- `wechat-articles/` is currently untracked input material.
- Existing dirty observe subrepos remain known baseline noise and were not modified as part of this work.

## Next Actions

1. Start the first absorption batch from `reports/wechat-absorb-next-batch.md`.
2. For each candidate, fill `reports/wechat-absorb-batch.template.md` before modifying ADK assets.
3. Keep external code candidates in report-only state until supply-chain review is complete.
4. After each batch, rerun `rtk scripts/check-wechat-intake-ledger.sh .`, `rtk scripts/check-all.sh --quick`, and relevant `agent-dev-kit` gates.

## Memory Candidate

- Durable project rule: `wechat-articles/` absorption must be ledger-first and batch-gated; external code references are report-only until security/supply-chain review.
- Recommended action: archive-only for this full note; promote only the durable rule above after manual review.
