---
name: skill-asset-manager
description: Use when discovering, importing, reviewing, promoting, or archiving Codex skills between ~/.codex and the ~/codex asset repository, including third-party skill intake and generated skill preservation.
version: 0.1.0
last_updated: 2026-05-09
---

# Skill Asset Manager

Use this skill when the user asks to:

- 接入新的第三方 skill。
- 扫描 `~/.codex/skills` 中运行过程中生成或手工添加的 skill。
- 把候选 skill 归档到 `~/codex/assets/codex/vendor/skills`。
- 更新 skill catalog、registry 或执行注入前后的 skill 资产检查。

## Workflow

1. Locate the asset repo root. Prefer the current workspace if it contains `assets/codex/control/catalog/skills.csv`; otherwise ask for the repo path.
2. For discovery from the live Codex home, run:

```bash
rtk bash scripts/scan-codex-skills.sh
```

3. Review candidates under `inbox/skills/<name>/<timestamp>/`. Never promote `skills/.system`.
4. Promote an approved skill with an explicit semantic version:

```bash
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
```

5. If the skill should be immediately available in `~/.codex`, apply assets and activate the intended profile:

```bash
rtk bash scripts/apply-to-codex.sh --activate-profile team-collab
```

## Rules

- Treat `assets/codex/` as the source of truth for managed Codex assets.
- Store official promoted skills under `assets/codex/vendor/skills/<name>/<version>/`.
- Keep `assets/codex/skills/` as the activation layer and registry area, not as the canonical third-party source.
- Never archive or overwrite `skills/.system`.
- Do not promote symlink activation entries; promote real skill directories only.
- Run `--dry-run` first when the target or version is uncertain.
- If validation reports suspected secrets, stop and ask the user to clean or confirm a safe source.

## Commands

Discover new live skills:

```bash
rtk bash scripts/scan-codex-skills.sh --dry-run
rtk bash scripts/scan-codex-skills.sh
```

Promote a third-party skill directory:

```bash
rtk bash scripts/promote-skill.sh /path/to/skill --version 1.0.0 --profiles 'solo-dev|team-collab' --tags third-party
```

Replace an existing catalog entry with a new version:

```bash
rtk bash scripts/promote-skill.sh inbox/skills/foo/20260509-120000 --version 1.1.0 --replace
```

Verify and apply:

```bash
rtk bash scripts/doctor-assets.sh
rtk bash scripts/apply-to-codex.sh --dry-run
rtk bash scripts/apply-to-codex.sh --dry-run --activate-profile team-collab
```
