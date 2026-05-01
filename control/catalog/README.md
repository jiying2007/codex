# Catalog 说明

本目录是 `~/.codex` 的单一事实源（SSOT），用于驱动以下自动化：

1. `activate-profile.sh`：按 profile 激活 skills / agents 软链接。
2. `render-config.sh`：按 profile 渲染并写回 `config.toml` 的 managed 区块。
3. `doctor.sh`：检查目录结构、软链接、catalog 一致性。

## 文件清单

- `profiles.csv`：场景配置与并行策略。
- `skills.csv`：技能来源、版本、目标链接、适用 profile。
- `agents.csv`：自定义 agent 定义来源、目标链接、适用 profile。
- `subagents.csv`：并行协作中的角色边界与阻塞条件。
- `mcp.csv`：MCP 服务器配置与 profile 绑定。
- `plugins.csv`：第三方插件与镜像来源登记。

## CSV 约定

1. 逗号分隔，第一行为表头。
2. 多值字段使用 `|` 分隔。
3. 布尔字段使用 `1` / `0`。
4. 相对路径均相对 `~/.codex` 根目录。
