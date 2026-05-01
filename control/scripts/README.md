# Scripts 使用手册

本目录脚本用于管理 `~/.codex` 的同步、激活、渲染、体检、归档闭环。

## 脚本索引

| 脚本 | 用途 | 典型用法 |
| --- | --- | --- |
| `sync-vendor.sh` | 组合执行同步+激活+体检 | `~/.codex/control/scripts/sync-vendor.sh ~/.codex team-collab` |
| `sync-skills-vendor.sh` | 同步 `skills/` 到 `vendor/skills/...` 并清理根入口 | `~/.codex/control/scripts/sync-skills-vendor.sh ~/.codex` |
| `activate-profile.sh` | 按 profile 重建 `skills/` 与 `agents/` 软链接 | `~/.codex/control/scripts/activate-profile.sh ~/.codex solo-dev` |
| `render-config.sh` | 按 profile 渲染 `config.toml` 的 MCP 托管区块 | `~/.codex/control/scripts/render-config.sh ~/.codex solo-dev` |
| `doctor.sh` | 执行一致性体检 | `~/.codex/control/scripts/doctor.sh ~/.codex solo-dev` |
| `archive-guidance.sh` | 归档知识文档快照并更新索引 | `~/.codex/control/scripts/archive-guidance.sh ~/.codex <source> <archive_dir> <index_file> <slug>` |
| `archive-bwrap.sh` | 归档 bwrap 版本/能力/风险结论知识快照并更新索引 | `~/.codex/control/scripts/archive-bwrap.sh ~/.codex` |
| `git-codex.sh` | 在仓库根目录执行 git 命令的轻量包装 | `~/.codex/control/scripts/git-codex.sh status` |

## 推荐执行顺序

1. 修改 `control/catalog/*.csv`、`vendor/`、`control/agents-local/` 等资产。
2. 执行 `activate-profile.sh` 或 `sync-vendor.sh`。
3. 执行 `doctor.sh`，确认 `errors=0`。
4. 需要留痕时执行 `archive-guidance.sh`。

## 关键产物

1. `control/state/active-profile.env`：当前激活 profile。
2. `control/generated/config-managed.toml`：MCP 托管片段。
3. `control/state/backup/sync-<timestamp>/`：同步过程备份目录。

## 常见问题

1. `profile 不存在`：检查 `control/catalog/profiles.csv` 是否包含目标 profile。
2. `缺少源路径(skill/agent)`：检查 `skills.csv` / `agents.csv` 的 `vendor_rel` 是否可达。
3. `插件 source_path 未落在 vendor/`：检查 `control/catalog/plugins.csv` 路径字段并统一到 `vendor/`。
