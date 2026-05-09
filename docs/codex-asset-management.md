# Codex 资产长期管理方案

## 目标

`~/codex` 是可版本化的 Codex 资产管理仓库，`~/codex/assets/codex` 是实际资产源，`~/.codex` 是本机运行目录。仓库通过脚本把有效资产注入到 `~/.codex`，但不接管运行时状态、不覆盖系统技能、不保存密钥。

## 边界

仓库管理：

- `AGENTS.md`
- `config*.toml`
- `control/`
- `mcp/` 中的非密钥配置
- `prompts/`
- `rules/`
- `skills/` 中的自定义技能、注册表与自检脚本
- `vendor/`
- `agents/`

仓库不管理：

- `skills/.system/`
- `auth.json`
- `sessions/`
- `log/`
- `logs_*.sqlite*`
- `state_*.sqlite*`
- `cache/`
- `tmp/`
- `mcp/secrets/`
- 机器私有配置与密钥
- profile 激活生成的 symlink

## 注入模型

资产清单位于 `assets/codex/control/catalog/assets.txt`。脚本只处理清单中的路径，并对内置排除规则做二次保护。

默认注入命令：

```bash
rtk bash scripts/apply-to-codex.sh
```

注入并应用 profile：

```bash
rtk bash scripts/apply-to-codex.sh --activate-profile team-collab
```

预览：

```bash
rtk bash scripts/apply-to-codex.sh --dry-run
```

覆盖已有文件：

```bash
rtk bash scripts/apply-to-codex.sh --overwrite
```

覆盖模式会先把目标文件备份到 `.backups/apply-to-codex/<timestamp>/`。目录采用合并复制，不整体替换。

脚本默认跳过 symlink。`skills/` 与 `agents/` 里的 profile 激活链接属于机器态入口，应通过 `control/scripts/activate-profile.sh` 在目标环境生成。

## 差异与备份

对比源仓库与运行目录：

```bash
rtk bash scripts/diff-codex.sh
```

备份当前运行目录：

```bash
rtk bash scripts/backup-codex.sh
```

仓库结构体检：

```bash
rtk bash scripts/doctor-assets.sh
rtk bash scripts/doctor-assets.sh --deep
```

默认体检只检查资产仓库结构与脚本语法。`--deep` 会额外检查 `assets/codex` 内 profile 状态，适合排查激活层问题。

## `skills/.system/` 规则

`skills/.system/` 由 Codex 本机环境提供，优先级高于本仓库。本仓库不得跟踪、复制或覆盖该目录。若未来需要观察系统技能变化，只做只读记录，不把内容纳入资产清单。

## 维护流程

1. 新增长期资产时，先放入合适目录。
2. 如果是新的顶层资产路径，同步登记到 `assets/codex/control/catalog/assets.txt`。
3. 运行 `rtk bash scripts/apply-to-codex.sh --dry-run` 预览。
4. 确认后运行 `rtk bash scripts/apply-to-codex.sh`。
5. 修改 skills 后运行 `rtk bash scripts/apply-to-codex.sh --dry-run --activate-profile team-collab` 做注入与激活预检。

## Skill 接入与归档

扫描运行目录中的未知 skill：

```bash
rtk bash scripts/scan-codex-skills.sh --dry-run
rtk bash scripts/scan-codex-skills.sh
```

审核后提升为正式资产：

```bash
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
```

`inbox/` 是未审核候选区，默认不进入 git；只有通过审核并执行 promote 后，才成为正式可版本化资产。

第三方 skill 也使用同一入口：

```bash
rtk bash scripts/promote-skill.sh /path/to/third-party-skill --version 1.0.0 --tags third-party
```

正式归档位置是 `assets/codex/vendor/skills/<name>/<version>/`。`assets/codex/skills/` 只作为 registry、脚本和 profile 激活层。

本仓库提供 `skill-asset-manager`，用于让 AI 自动执行 discovery、intake、promote、验证和注入流程。
