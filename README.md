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

## 快速开始

```bash
# 1) 首次同步 vendor 与激活层（默认 profile=minimal）
~/.codex/control/scripts/sync-vendor.sh ~/.codex

# 2) 切换到团队协作配置
~/.codex/control/scripts/activate-profile.sh ~/.codex team-collab

# 3) 执行一致性体检
~/.codex/control/scripts/doctor.sh ~/.codex team-collab
```

如果体检输出 `errors=0 warnings=0`，说明当前配置可用。

## 日常使用指南

```bash
# 查看当前状态
git -C ~/.codex status

# 切 profile（会重建 skills/agents 软链接并渲染 config）
~/.codex/control/scripts/activate-profile.sh ~/.codex solo-dev

# 仅渲染 config.toml 的 MCP 托管区块
~/.codex/control/scripts/render-config.sh ~/.codex solo-dev

# 同步 vendor + 激活 + 体检（组合命令）
~/.codex/control/scripts/sync-vendor.sh ~/.codex solo-dev
```

## 流程说明

1. feature 开发流程：`control/workflows/feature-flow.md`
2. bug 修复流程：`control/workflows/bugfix-flow.md`
3. refactor 流程：`control/workflows/refactor-flow.md`
4. 流程总览与何时选用：`control/workflows/README.md`

## 文档导航

1. 设计方案与使用说明：`control/knowledge/codex-design-and-usage.md`
2. 开发与协作指南：`control/knowledge/codex-dev-collab-guide.md`
3. catalog 规范：`control/catalog/README.md`
4. 脚本说明：`control/scripts/README.md`
5. 最新归档快照：`control/archives/guidance/latest.md`

## 关键约束

1. 第三方实体内容仅放 `vendor/`。
2. `.codex` 根目录不保留第三方入口链接。
3. `skills/` 与 `agents/` 仅作为激活层软链接入口。
4. profile/capability 以 `control/catalog/*.csv` 为 SSOT。
5. 任何变更完成后建议执行一次 `doctor.sh` 体检。
