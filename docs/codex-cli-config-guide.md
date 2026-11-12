# Codex CLI 默认配置指南

维护状态：共享默认值维护于 `src/codex-home/config/base.toml`，本机偏好通过显式、哈希绑定的部分覆盖输入合并，经受管链路生成 `~/.codex/config.toml`。最近核验：2026-11-10，Codex CLI `0.165.0`。

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
- 日常 `model_reasoning_effort = "medium"`，计划模式现统一为 `plan_mode_reasoning_effort = "xhigh"`；计划模式设置不自动进入 Plan 模式。
- `[agents] max_concurrent_threads_per_session = 3`，最多三个并行子代理，不含主代理；不因此获得自动派发权限。
- `[tui] raw_output_mode = true`，默认便于复制日志；用 `/raw` 或默认 `Alt+R` 切换。模板不设置 `resume_cwd`；本机显式覆盖 `current` 时，恢复会话使用当前目录而不弹出目录选择。
- `[features] memories = true`，`[memories] use_memories = true`、`generate_memories = false`：使用既有记忆，新线程不进入自动记忆生成输入。该设置不删除已有记忆，也不承诺停止旧输入的所有后台处理；人工记忆更新仍须用户明确要求。

保留 20,000 token 工具输出预算、既有低噪音通知和状态栏，以及 `on-request`、`workspace-write`、默认关闭 sandbox network 的权限边界。运行中的会话不热加载完整配置，下一次启动读取新的默认值。

2026-10-14 移除后续加入的 100,000 tokens 自动压缩覆盖及其 scope，恢复上述模型默认策略。本机 GPT-6.1 Sol 模型目录报告窗口 500,000、有效窗口比例 95%；未设置字段不等于已实测压缩触发点。Execution Policy 的本地 50% 上下文维护门禁继续独立执行，可能先于原生压缩触发。

验证须覆盖源码模板、保留本机设置的构建候选和实际用户配置；CLI doctor 的 config 状态应为 `ok`、启动配置警告为 0。记录真实 effective 上下文元数据与 raw 输出模式，不能只凭 TOML 字段存在声明生效。

## 官方账号与局域网中转站

共享模板的默认 provider 使用 `openai`；本机部分覆盖可以显式选择 `relay`。
本机已按用户要求选择 `openai`，无参数启动使用官方账号；`relay` 保留为临时选择。

| 使用方式 | 启动命令 |
|---|---|
| 使用本机默认 provider | `rtk codex` |
| 显式使用官方 ChatGPT 账号 | `rtk codex -c model_provider=openai` |
| 临时使用中转站 | `rtk codex -c model_provider=relay` |

官方账号尚未登录时，先执行一次 `rtk codex -c model_provider=openai login`，
完成登录后使用显式的官方 provider 命令，或在本机覆盖中选择 `openai` 后重新构建同步。

中转站地址为 `http://192.168.2.109:3000/v1`，协议为
`responses`，认证读取独立环境变量 `CODEX_RELAY_API_KEY`。
本机 `~/.bashrc` 设置该变量；初次迁移沿用现有有效令牌，之后可独立轮换。
密钥不进入配置源、本机偏好 JSON 或受管构建收据。

使用中转站时，从终端启动前执行 `source ~/.bashrc`，再运行
`rtk codex -c model_provider=relay`。VS Code 或其他宿主
也必须继承该变量；若修改 `.bashrc` 后宿主仍持有旧环境，需从加载了变量的终端
重新启动宿主。运行中的 Codex 会话不会因配置文件变化而切换 provider。

2026-11-07 已用本机当前模型 `gpt-6.1-sol` 验证 `/v1/models` 和
`/v1/responses`，后者实际完成最小请求并返回 `OK`。这仅证明当时的接口可用性。
本机应用时保留既有模型、trust、notice 和权限配置，经 source-to-live 同步。
2026-11-10 共享模板默认 provider 改为官方 `openai`，本机部分覆盖保留实际现场选择。
`-c` 仅覆盖本次启动，不改变默认配置。
切换 provider 需重新启动会话。撤销受管同步使用对应 apply plan 的备份。

本轮探测 HTTPS 同端口返回 TLS 协议错误；`/v1/models` 为普通模型列表，
候选 `/codex/models` 返回 HTML，`/v1/codex/models` 返回 404。未配置猜测的
`model_catalog_url`，也未将窗口手工放大。客户端目录中 relay 为 272000、官方为
500000，仅代表该客户端目录元数据差异；后续需要中转站提供原生目录和 HTTPS
接入信息才能对齐。已禁用 MCP 的声明保留为显式禁用策略，不启动进程；
不将删除禁用声明当作性能优化或默认继承行为等价的变更。

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

修改配置源后依次执行 build、doctor、plan、apply dry-run、Execution Policy apply gate、apply 和 check。
构建使用当前 live 的资产 profile；本机偏好使用持久化部分输入 `local/config-overrides.json`
（Git 忽略），不再依赖 `/tmp` 全量配置快照。共享模型默认值为 `gpt-6.1-sol`。

输入为 `schema_version=1`、`profile`、`target="config.toml"`、`overrides`。
只允许模型偏好、projects、notice、apps 以及两个本机 TUI 状态字段；不允许覆盖
sandbox/命令审批、shell 环境、指令、凭据或 MCP。仅有意选择的字段放入 overrides，未覆盖字段
始终使用当前模板和 manifest。机器输入路径和 SHA256 进入 build receipt/fingerprint，
输入缺失、哈希变化或 profile 不匹配时 fail closed。

```bash
rtk sha256sum ~/codex/local/config-overrides.json
rtk bash ~/codex/scripts/build.sh --profile team-collab \
  --local-config ~/codex/local/config-overrides.json \
  --expected-local-config-sha256 <上一步核验的SHA256>
```

后续已批准且未变的输入可用 `build --reuse-machine-inputs` 复用，隐式 apply rebuild
和 smoke 恢复也校验并保留该输入。旧 `--context-config-from` 仍仅用于压缩字段专项迁移，
不能与部分本机配置同时使用，也不应作为长期配置来源。最终 receipt 绑定 source/build/target。

默认 plan 保留已有本机配置；需要替换时使用 `--overwrite` 并审阅全部动作。不得借配置修复删除无关资产或覆盖用户其他修改。完整检查中的 smoke 可能重建 build，故检查后若构建身份发生变化，必须重新构建、doctor、plan 和 dry-run。

验证实际用户配置：

```bash
rtk codex --strict-config doctor --json
```

检查 `config.load`：status 为 `ok`，解析为 `ok`，startup warnings 为 0（无警告时该字段可能省略）。doctor 的安装、更新、终端或会话历史诊断独立判断，不能据此误判配置修复失败。当前 CLI 的 `doctor` 不支持 `--profile`，不能用该入口验证独立模式。

运行中的会话不热加载完整配置；修复供下一次启动读取，无需主动中断当前会话。
