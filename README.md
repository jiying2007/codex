# .codex 全局工程仓库

本仓库用于管理本机 Codex 的全局工程能力，目标是：

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

## 新机器安装（首次上手）

```bash
# clone 到本地（路径可自定义）
git clone <repo-url> ~/codex

# 一键安装：激活 skills/agents 软链接、渲染 config、体检
~/codex/control/scripts/install.sh ~/codex team-collab

# 如需将仓库目录链接为 ~/.codex
ln -sfn ~/codex ~/.codex
```

> **说明：** `install.sh` 自动完成以下工作：
> - 同步 `skills/registry.csv`（从 catalog 生成）
> - 激活指定 profile 的 skills / agents 软链接（指向本地 vendor/）
> - 渲染 `config.toml` 的 MCP 托管区块
> - 运行 `doctor.sh` 体检

## 日常使用指南

```bash
# 切 profile（会重建 skills/agents 软链接并渲染 config）
~/codex/control/scripts/activate-profile.sh ~/codex solo-dev

# 一致性体检
~/codex/control/scripts/doctor.sh ~/codex

# 重新生成 skills/registry.csv（skills.csv 变更后执行）
~/codex/control/scripts/gen-registry.sh ~/codex

# 归档当前知识文档快照
~/codex/control/scripts/archive-guidance.sh ~/codex

# 归档 bwrap 运行时信息
~/codex/control/scripts/archive-bwrap.sh ~/codex
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
