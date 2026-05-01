# .codex 全局目录

本目录采用四层架构：

1. 运行时层：`sessions/`、`logs_*`、`state_*`、`cache/`。
2. 控制层：`control/`（catalog、roles、workflows、scripts）。
3. 激活层：`skills/`、`agents/`、`config.toml`。
4. 供应层：`vendor/`（第三方能力实体与版本）。

## 快速导航

1. 设计方案与使用说明：[control/knowledge/codex-design-and-usage.md](control/knowledge/codex-design-and-usage.md)
2. 开发与协作指南：[control/knowledge/codex-dev-collab-guide.md](control/knowledge/codex-dev-collab-guide.md)
3. 最新归档快照：[control/archives/guidance/latest.md](control/archives/guidance/latest.md)

## Git 使用

```bash
git -C ~/.codex status
git -C ~/.codex add -A
git -C ~/.codex commit -m "chore(codex): 更新全局配置"
```

## 快速命令

```bash
# 同步 vendor 实体与激活层，并执行体检
~/.codex/control/scripts/sync-vendor.sh ~/.codex solo-dev

# 仅切换 profile（重建 skills/agents 软链接并渲染 config）
~/.codex/control/scripts/activate-profile.sh ~/.codex team-collab

# 体检
~/.codex/control/scripts/doctor.sh ~/.codex team-collab
```

## 关键约束

1. 第三方实体内容仅放 `vendor/`。
2. `.codex` 根目录不保留第三方入口链接。
3. `skills/` 与 `agents/` 仅作为激活层软链接入口。
4. profile/capability 以 `control/catalog/*.csv` 为 SSOT。
