# Codex V2 资产管理手册

## 日常维护

1. 修改 `src/codex-home/` 中的人工资产，或修改 `manifests/*.json`。
2. 运行 `rtk bash scripts/build.sh --profile team-collab`。
3. 运行 `rtk bash scripts/doctor.sh --scope all`。
4. 运行 `rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json` 生成审计计划。
5. 运行 `rtk bash scripts/apply.sh --dry-run --no-build` 预览。
6. 确认后运行 `rtk bash scripts/apply.sh --profile team-collab`。
7. 发布前运行 `rtk bash tests/smoke.sh`。

## 新增普通资产

普通资产放入 `src/codex-home/` 对应目录。如果是新的顶层目录，需要加入 `manifests/assets.json` 的 `copy_roots`。

不要把以下内容放入源资产：

- `skills/.system/`
- `auth.json`
- `sessions/`
- `log/` 或 `logs_*.sqlite*`
- `state_*.sqlite*`
- `cache/`
- `tmp/`
- `mcp/secrets/`
- `config.local.*`
- `*.secret`、`*.key`、`*.pem`

## Skill 接入

扫描运行目录：

```bash
rtk bash scripts/scan-skills.sh --dry-run
rtk bash scripts/scan-skills.sh
```

审核候选目录：

```text
inbox/skills/<name>/<timestamp>/
```

归档：

```bash
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
```

第三方目录也用同一入口：

```bash
rtk bash scripts/promote-skill.sh /path/to/third-party-skill --version 1.0.0 --tags third-party
```

归档脚本会更新 `manifests/skills.json`，下一次 build 会生成 `skills/registry.csv` 与激活 symlink。

## 发布到运行目录

默认注入不会覆盖已有普通文件：

```bash
rtk bash scripts/apply.sh --profile team-collab
```

需要覆盖时：

```bash
rtk bash scripts/apply.sh --profile team-collab --overwrite
```

覆盖备份位于 `.backups/apply/<timestamp>/`。

## 排障

```bash
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope live
rtk bash scripts/diff.sh
rtk bash scripts/drift.sh
```

若 `diff.sh` 报告普通文件不同，先判断目标文件是否为本机私有修改；若需要仓库版本覆盖，再使用 `apply.sh --overwrite`。

若 `drift.sh` 报告 changed，表示 live 中受管理文件偏离了上次 apply 时的 managed state；先确认是否为人工修改，再决定重新 apply 或将修改提升回源资产。
