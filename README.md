# Codex 全局资产仓库

本仓库用于长期管理本机 Codex CLI 使用的有效资产。推荐模式是：

- `~/codex`：独立 git 仓库，作为可版本化的资产源与维护入口。
- `~/codex/assets/codex`：实际要注入到 `~/.codex` 的资产目录树。
- `~/.codex`：Codex 本机运行目录，保存运行时状态、系统技能和本机私有信息。
- 通过 `scripts/apply-to-codex.sh` 将仓库资产安全注入到 `~/.codex`，不要求 `~/.codex` 是软链接。

目标是：

1. 统一第三方能力管理（`vendor/`）。
2. 统一能力编排与启停（`control/catalog/*.csv` + profile）。
3. 统一执行流程与质量门禁（roles/workflows/scripts）。
4. 降低多人协作和跨机器迁移成本。

## 仓库介绍

仓库采用四层结构：

1. 运行时层：`sessions/`、`logs_*`、`state_*`、`cache/`（运行数据，不做长期协作资产）。
2. 控制层：`control/`（目录清单、流程、脚本、知识文档、归档）。
3. 激活层：`skills/`、`agents/`、`config.toml`（Codex 直接读取）。
4. 供应层：`vendor/`（第三方实体与版本）。

当前仓库采用隔离资产源结构：

```text
assets/codex/        # 希望注入到 ~/.codex 的可管理资产
scripts/             # 同步、备份、检查脚本
docs/                # 设计与维护说明
AGENTS.md            # 当前仓库工作规则
README.md            # 使用说明
```

## 推荐注入方式

```bash
# 预览将要注入的资产
rtk bash scripts/apply-to-codex.sh --dry-run

# 安全注入到 ~/.codex，已存在文件默认保留
rtk bash scripts/apply-to-codex.sh

# 注入后在 ~/.codex 内应用 profile
rtk bash scripts/apply-to-codex.sh --activate-profile team-collab

# 覆盖已有文件，覆盖前自动备份
rtk bash scripts/apply-to-codex.sh --overwrite

# 对比源仓库与 ~/.codex
rtk bash scripts/diff-codex.sh

# 备份当前 ~/.codex
rtk bash scripts/backup-codex.sh

# 仓库结构与脚本体检
rtk bash scripts/doctor-assets.sh

# 深度体检：额外检查 assets/codex 内 profile 激活状态
rtk bash scripts/doctor-assets.sh --deep
```

默认注入源是 `assets/codex/`，注入清单位于 `assets/codex/control/catalog/assets.txt`。脚本会始终跳过 `skills/.system/`，该目录以 `~/.codex` 中已有内容为准，本仓库不跟踪、不复制、不覆盖。脚本也会跳过 symlink；需要让目标环境生成 profile 激活链接时，使用 `--activate-profile <profile>`。

## Skill 接入与归档

```bash
# 扫描 ~/.codex/skills 中未归档的 skill
rtk bash scripts/scan-codex-skills.sh --dry-run
rtk bash scripts/scan-codex-skills.sh

# 审核后提升为正式资产
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0

# 接入第三方 skill
rtk bash scripts/promote-skill.sh /path/to/skill --version 1.0.0 --tags third-party
```

正式 skill 源统一归档到 `assets/codex/vendor/skills/<name>/<version>/`，并由 catalog/profile 生成激活入口。`inbox/` 是未审核候选区，默认不纳入 git。本仓库内置 `skill-asset-manager`，AI 遇到 skill 接入、扫描和归档任务时应使用它。

## 新机器安装（首次上手）

```bash
# clone 到本地（路径可自定义）
git clone <repo-url> ~/codex

# 推荐：安全注入资产到已有或新建的 ~/.codex
rtk bash ~/codex/scripts/apply-to-codex.sh --dry-run
rtk bash ~/codex/scripts/apply-to-codex.sh --activate-profile team-collab

# 可选：在资产源内直接激活 profile、渲染 config、体检
rtk bash ~/codex/assets/codex/control/scripts/install.sh ~/codex/assets/codex team-collab
```

> **说明：** `install.sh` 自动完成以下工作：
> - 同步 `skills/registry.csv`（从 catalog 生成）。
> - 激活指定 profile 的 skills / agents 软链接（指向本地 vendor/）。
> - 渲染 `config.toml` 的 MCP 托管区块。
> - 运行 `doctor.sh` 体检。
> - 旧模式会尝试把 `~/.codex` 链接到仓库；若 `~/.codex` 已是实际目录则跳过。长期管理优先使用 `scripts/apply-to-codex.sh`。

## 日常使用指南

```bash
# 切 profile（会重建 assets/codex 内的 skills/agents 软链接并渲染 config）
rtk bash ~/codex/assets/codex/control/scripts/activate-profile.sh ~/codex/assets/codex solo-dev

# 一致性体检
rtk bash ~/codex/assets/codex/control/scripts/doctor.sh ~/codex/assets/codex

# 重新生成 skills/registry.csv（skills.csv 变更后执行）
rtk bash ~/codex/assets/codex/control/scripts/gen-registry.sh ~/codex/assets/codex

# 归档当前知识文档快照
rtk bash ~/codex/assets/codex/control/scripts/archive-guidance.sh ~/codex/assets/codex

# 归档 bwrap 运行时信息
rtk bash ~/codex/assets/codex/control/scripts/archive-bwrap.sh ~/codex/assets/codex
```

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `install.sh` | 新机器首次安装 |
| `activate-profile.sh` | 切换 profile |
| `sync-vendor.sh` | 同步 vendor + 激活 + 体检（组合命令）|
| `render-config.sh` | 渲染 config.toml 的 MCP 区块 |
| `gen-registry.sh` | 从 catalog 生成 skills/registry.csv |
| `doctor.sh` | 一致性体检 |
| `archive-guidance.sh` | 归档知识文档快照 |
| `archive-bwrap.sh` | 归档 bwrap 运行时信息 |
| `git-codex.sh` | 在仓库根执行 git 命令的快捷方式 |

根目录额外提供维护脚本：

| 脚本 | 用途 |
|------|------|
| `scripts/apply-to-codex.sh` | 从 `assets/codex/` 安全注入到 `~/.codex` |
| `scripts/diff-codex.sh` | 对比资产源与目标目录 |
| `scripts/backup-codex.sh` | 备份当前 `~/.codex` |
| `scripts/scan-codex-skills.sh` | 扫描运行目录中未归档 skill |
| `scripts/promote-skill.sh` | 将候选/第三方 skill 提升为 vendor 资产 |
| `scripts/doctor-assets.sh` | 检查仓库结构与脚本语法；`--deep` 额外检查资产源 profile |

## Profile 说明

| Profile | 能力集 | 适用场景 |
|---------|--------|----------|
| `minimal` | caveman + daily summary | 轻量单人任务 |
| `solo-dev` | minimal + 个人日报 skills | 个人深度开发 |
| `team-collab` | solo-dev + superpowers 全套 + 协作代理 | 团队协作 |

## 关键约束

1. 第三方实体内容仅放 `vendor/`。
2. `.codex` 根目录不保留第三方入口链接。
3. `skills/` 与 `agents/` 中的激活软链接不纳入 git（见 .gitignore）——在本地由 `activate-profile.sh` 生成。
4. profile/capability 以 `control/catalog/*.csv` 为 SSOT。
5. 变更 skills.csv 后执行 `gen-registry.sh` 同步 registry.csv。
6. 任何变更完成后建议执行一次 `doctor.sh` 体检。
7. `skills/.system/` 以 `~/.codex` 中现有系统技能为准，本仓库不跟踪。

更多设计细节见 `docs/design.md` 与 `docs/codex-asset-management.md`。
