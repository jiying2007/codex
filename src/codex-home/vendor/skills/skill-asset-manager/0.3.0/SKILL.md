---
name: skill-asset-manager
description: "Use only for Codex skill asset governance: discovering live skills, importing third-party skills, reviewing candidates, promoting versions, updating manifests, applying assets to ~/.codex, rollback, and checking skill inventory health."
version: 0.3.0
last_updated: 2026-11-03
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
- Personal/project/portfolio period report: use `activity-report`.
- Git-only period report: use `git-activity-summary`.
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
rtk bash scripts/build.sh --profile default --reuse-context-input --reuse-machine-inputs
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope governance
rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json
rtk bash scripts/apply.sh --plan build/apply-plan.json --dry-run
rtk bash scripts/apply.sh --plan build/apply-plan.json
rtk bash scripts/check.sh --no-build --plan build/apply-plan.json
```

Use absolute script/plan paths from a different cwd. Reuse flags require a
previous receipt with unchanged approved inputs; on first build choose explicit
inputs under the current source-to-live contract, never guess or discard local
model/trust/notice/permission settings. Review every copy/overwrite/delete before
apply. A dirty source is not permission to ship unrelated edits. Dry-run and apply
must use the same frozen plan; source/build/target drift requires a new plan.
Keep the backup and receipt for rollback, then read back exact versions/hashes.
Separate installed asset health from model behavior, product or board acceptance.

Discovery checks include both the managed catalog and configured team sources.
Use `skill-search`'s explicit `source_id` and `load_path`; a zero-hit is not proof
of absence. Same-name managed skills take precedence in this CLI; team alternatives
are inventoried without overwriting or merging either source. Do not enable an
external path by copying its text into the managed vendor tree.

For a skill-only health check, run:

```bash
rtk bash scripts/check-skills.sh
```

## Iteration Policy

- Only local and Chronicle-derived skills are iterated directly in this repository.
- Local skills must be identifiable with manifest `owner=local`, `source_repo=local/codex`, and `tags` containing `local`.
- Chronicle-derived skills must also use the `chronicle-derived` tag plus `origin: local-chronicle-derived` and `lifecycle: iterative-local` metadata.
- For local draft changes before commit, editing the current skill version is acceptable.
- Once a local skill has been committed and used, prefer a new version directory and update `manifests/skills.json`.
- External imported skills such as `adk-*`, Superpowers, OpenAI, Composio, or Anthropic skills should be updated by importing a new upstream version, not by silently editing the local mirror.
- Routing misses for local skills should usually update `description` or `manifests/workflows.json`.
- Chinese routing phrases should be precise object-action phrases; avoid broad standalone words and document cross-skill ambiguity in `docs/skill-lifecycle.md` or `AGENTS.md`.
- Procedural misses for local skills should update `SKILL.md`; detailed references belong in `references/`.
- Long evidence and usage history go through the public Knowledge Provider as sanitized reviewing candidates, not into the loaded skill body or Hub internal paths.
- See `docs/skill-lifecycle.md` for the full lifecycle and acceptance criteria.

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
