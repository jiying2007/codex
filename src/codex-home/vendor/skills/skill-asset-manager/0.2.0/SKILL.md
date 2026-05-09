---
name: skill-asset-manager
description: Use only for Codex skill asset governance: discovering live skills, importing third-party skills, reviewing candidates, promoting versions, updating manifests, applying assets to ~/.codex, rollback, and checking skill inventory health.
version: 0.2.0
last_updated: 2026-05-09
---

# Skill Asset Manager

Use this skill when the user asks to:

- 接入新的第三方 skill。
- 扫描 `~/.codex/skills` 中运行过程中生成或手工添加的真实 skill。
- 把候选 skill 归档到 `~/codex/src/codex-home/vendor/skills`。
- 更新 `manifests/skills.json`。
- 构建、体检并注入 v2 Codex 资产。

## Routing Boundary

Use this skill only for **skill asset lifecycle management**.

Prefer another skill when:

- Current session closeout: use `session-wrap`.
- Same-day project report: use `project-daily-summary`.
- Commit-only daily report: use `commit-daily-summary`.
- Research/analysis note: use `research-note-wrap`.
- Branch/worktree closeout: use `worktree-closeout`.

## Workflow

1. Locate the asset repo root. Prefer the current workspace if it contains `manifests/skills.json` and `src/codex-home`.
2. Discover live skills:

```bash
rtk bash scripts/scan-skills.sh --dry-run
rtk bash scripts/scan-skills.sh
```

3. Review candidates under `inbox/skills/<name>/<timestamp>/`. Never promote `skills/.system`.
4. Promote an approved skill with an explicit semantic version:

```bash
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
```

When promoting third-party skills, record provenance metadata in `manifests/skills.json`:

- `owner`
- `source_repo`
- `source_ref`
- `source_path`
- `imported_at`
- `review_status`

5. Build, verify, and apply:

```bash
rtk bash scripts/build.sh --profile team-collab
rtk bash scripts/doctor.sh --scope all
rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json
rtk bash scripts/apply.sh --dry-run --no-build
rtk bash scripts/apply.sh --profile team-collab
rtk bash scripts/check.sh
```

For a skill-only health check, run:

```bash
rtk bash scripts/check-skills.sh
```

## Rules

- Treat `manifests/*.json` as the SSOT for activation and versioning.
- Treat `src/codex-home/` as the hand-maintained source.
- Treat `build/codex-home/` as generated output; do not edit it manually.
- Store official promoted skills under `src/codex-home/vendor/skills/<name>/<version>/`.
- Treat `source_repo`, `source_ref`, and `source_path` as required for third-party skills when known.
- Set `review_status` to `accepted`, `pending`, or `rejected`; only `accepted` skills should be enabled by default.
- Never archive or overwrite `skills/.system`.
- Do not promote symlink activation entries; promote real skill directories only.
- Run `--dry-run` first when the target or version is uncertain.
- Prefer `scripts/plan.sh` before applying to produce an auditable apply plan.
- Use `scripts/drift.sh` to detect live managed-file drift.
- Use `scripts/rollback.sh --plan <apply-plan.json>` to restore files touched by a specific apply plan.
- If validation reports suspected secrets, stop and ask the user to clean or confirm a safe source.
