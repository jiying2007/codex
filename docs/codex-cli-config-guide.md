# Codex CLI 默认配置指南

维护状态：仅维护 `src/codex-home/config/base.toml`，通过受管构建与同步链路生成 `~/.codex/config.toml`。最近核验：2026-10-07，Codex CLI `0.159.2`。

## 日常使用

日常直接运行 `rtk codex`。用户确认基本不切换配置模式，因此移除旧的 `dev/debug/embedded/max` 表，不部署对应独立模式文件。

临时需要更深推理时使用命令行覆盖，只影响本次启动：

```bash
rtk codex -c model_reasoning_effort=xhigh
rtk codex -c model_verbosity=low
```

CLI 配置模式与资产 profile 分属不同边界：删除四个 CLI 模式不切换当前 `team-collab` 资产 profile，也不删除技能或代理。

## 默认配置优化

2026-10-07 按用户使用习惯统一落地以下设置：

- 删除 `model_context_window` 和 `model_auto_compact_token_limit` 手动覆盖，使用模型目录与 CLI 默认策略；手动填写大窗口不会扩大服务端能力。
- 日常 `model_reasoning_effort = "medium"`，计划模式 `plan_mode_reasoning_effort = "high"`；计划模式设置不自动进入 Plan 模式。
- `[agents] max_concurrent_threads_per_session = 3`，最多三个并行子代理，不含主代理；不因此获得自动派发权限。
- `[tui] raw_output_mode = true`，默认便于复制日志；用 `/raw` 或默认 `Alt+R` 切换。`resume_cwd` 保持未设置，目录不一致时继续询问。
- `[features] memories = true`，`[memories] use_memories = true`、`generate_memories = false`：使用既有记忆，新线程不进入自动记忆生成输入。该设置不删除已有记忆，也不承诺停止旧输入的所有后台处理；人工记忆更新仍须用户明确要求。

保留 20,000 token 工具输出预算、既有低噪音通知和状态栏，以及 `on-request`、`workspace-write`、默认关闭 sandbox network 的权限边界。运行中的会话不热加载完整配置，下一次启动读取新的默认值。

验证须覆盖源码模板、保留本机设置的构建候选和实际用户配置；CLI doctor 的 config 状态应为 `ok`、启动配置警告为 0。记录真实 effective 上下文元数据与 raw 输出模式，不能只凭 TOML 字段存在声明生效。

## 当前字段与权限

模型、推理强度、上下文与工具输出预算使用官方配置键。源码模板的模型是可复用默认值；本机用户配置允许保留其实际模型，不能在修复警告时无意覆盖。

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
web_search = "cached"
hide_agent_reasoning = true

[sandbox_workspace_write]
network_access = false
writable_roots = ["/home/leiwenjun/.codex/memories"]

[shell_environment_policy]
inherit = "core"

[history]
persistence = "save-all"
max_bytes = 52428800
```

命令按 AGENTS 约定经 `rtk` 执行。不要使用不支持的 `auto_execute`、`[shell]`、`[workspace]`；这些设置不会提供命令确认或文件写保护。审批与访问边界由官方 approval 和 sandbox 设置控制。不同时启用 beta `default_permissions`。

TUI 状态栏、通知、终端标题继续使用官方内置配置；保留本机 notice、screen reader 与项目 trust。认证、session、日志和数据库不进入配置源或公开归档。

## CLI 升级兼容性

从 Codex `0.134.0` 起，`--profile <name>` 读取同目录 `<name>.config.toml`，不再读取主配置中的 `[profiles.<name>]`。本仓当前不维护这些可选文件。将来确需模式时使用文件顶层键，登记到资产清单，再按受管链路同步。

本次 43 项 ignored settings 来自无效控制项与旧 profile 表中的不支持字段；删除这两类内容后，默认配置应无启动配置警告。已被忽略的 profile 参数不能当作之前实际生效的运行参数。

官方来源：

- [Configuration reference](https://developers.openai.com/codex/config-reference)
- [Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)

## 构建与同步验证

修改配置源后依次执行 build、doctor、plan、apply dry-run、Execution Policy apply gate、apply 和 check。构建使用当前 live 的资产 profile；本机配置有允许漂移时，用明确的临时 source 快照保留本机设置，不把私人 trust 等写入公共配置源。最终构建 receipt 必须绑定实际 source、build 与 target。

默认 plan 保留已有本机配置；需要替换时使用 `--overwrite` 并审阅全部动作。不得借配置修复删除无关资产或覆盖用户其他修改。完整检查中的 smoke 可能重建 build，故检查后若构建身份发生变化，必须重新构建、doctor、plan 和 dry-run。

验证实际用户配置：

```bash
rtk codex --strict-config doctor --json
```

检查 `config.load`：status 为 `ok`，解析为 `ok`，startup warnings 为 0（无警告时该字段可能省略）。doctor 的安装、更新、终端或会话历史诊断独立判断，不能据此误判配置修复失败。当前 CLI 的 `doctor` 不支持 `--profile`，不能用该入口验证独立模式。

运行中的会话不热加载完整配置；修复供下一次启动读取，无需主动中断当前会话。
