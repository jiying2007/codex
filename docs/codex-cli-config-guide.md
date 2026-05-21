# Codex CLI 官方配置指南

维护状态：本指南用于维护 `~/codex/src/codex-home/config/base.toml`，并通过声明式资产链路生成和同步 `~/.codex/config.toml`。

最近核验：2026-05-21，Codex CLI `0.132.0`。

官方来源：

- [Config basics](https://developers.openai.com/codex/config-basic)
- [Advanced configuration](https://developers.openai.com/codex/config-advanced)
- [Configuration reference](https://developers.openai.com/codex/config-reference)
- [Sample configuration](https://developers.openai.com/codex/config-sample)

## 维护原则

1. 只把稳定、当前 CLI 可识别的字段写入 source 配置。
2. `src/codex-home/config/base.toml` 是默认日常配置，优先低噪音、可验证、成本可控。
3. 长期模式切换使用官方 `[profiles.<name>]` 和 `codex --profile <name>`。
4. 不再维护 `config.dev.toml`、`config.debug.toml`、`config.embedded.toml`、`config.max.toml` 独立模板。
5. `~/.codex/config.toml` 不直接手改；从 source 构建、plan、dry-run、apply。
6. 每次升级 Codex CLI 后，用官方文档和 `codex --strict-config doctor` 双重验证字段。

## 配置优先级

官方规则按优先级从高到低：

1. CLI flags 和 `--config`
2. `--profile <name>` 选择的 profile
3. trusted project 下的 `.codex/config.toml`
4. 用户级 `~/.codex/config.toml`
5. 系统级 `/etc/codex/config.toml`
6. Codex 内置默认值

本仓当前把 `dev`、`debug`、`embedded`、`max` 写入 `src/codex-home/config/base.toml` 的官方 `[profiles.<name>]`。多个窗口、多个会话需要不同配置时，直接使用 `codex --profile <name>`；不要通过覆盖全局 `~/.codex/config.toml` 来并发切换。

## 推荐字段

### 模型与输出

```toml
model = "gpt-5.5"
model_reasoning_effort = "high"
model_reasoning_summary = "concise"
model_verbosity = "medium"
hide_agent_reasoning = true
```

策略：

- 默认使用 `high`，需要更深推理时用 `codex --profile max`。
- `model_reasoning_summary = "concise"` 和 `hide_agent_reasoning = true` 用于减少 TUI 噪音。
- `model_verbosity` 按 profile 调整：日常 `medium`，省 token profile 使用 `low`。

### 上下文与工具输出

```toml
model_context_window = 160000
model_auto_compact_token_limit = 100000
tool_output_token_limit = 16000
project_doc_max_bytes = 32768
project_doc_fallback_filenames = []
```

策略：

- 默认窗口不要盲目放到模型最大值；大窗口会鼓励读取无关文件并增加成本。
- `tool_output_token_limit` 保持定向验证足够，不复述大日志。
- `project_doc_max_bytes` 显式固定，避免超长 `AGENTS.md` 注入持续膨胀。

### 权限、沙箱和网络

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
web_search = "cached"

[sandbox_workspace_write]
network_access = false
writable_roots = [
  "/home/leiwenjun/.codex/memories",
]
```

策略：

- 默认保留 human approval，不使用 `never`。
- 默认不开放 sandbox network；需要联网时由任务显式请求或使用 CLI override。
- 默认 `web_search = "cached"`，实时信息再临时开启 live search。

### Shell 环境

```toml
[shell_environment_policy]
inherit = "core"

[shell]
program = "rtk"
args = ["bash", "-lc"]
```

策略：

- 所有 shell 命令仍通过 `rtk`。
- 日常 profile 使用 `core`，极省 token / 隔离 profile 可用 `none`。

### TUI

```toml
[tui]
notifications = false
animations = false
show_tooltips = false
status_line = [
  "model-with-reasoning",
  "current-dir",
  "git-branch",
  "context-remaining",
  "five-hour-limit",
  "weekly-limit",
  "fast-mode",
]
terminal_title = ["spinner", "project", "git-branch"]
```

策略：

- 状态栏只使用 Codex 内置 item。
- 当前 Codex CLI 不等价支持 Claude `statusLine.command` 式外部脚本渲染；不要把外部命令写进 `status_line`。

### History

```toml
[history]
persistence = "save-all"
max_bytes = 52428800
```

策略：

- 默认保存历史，便于会话接力和本地检索。
- 设置 `max_bytes`，避免长期无限增长。

## Profile 策略

| Profile | 启动命令 | 用途 | 核心策略 |
| --- | --- | --- |
| 默认 | `codex` | 日常 | `high` reasoning，16 万上下文，低噪音 TUI |
| `dev` | `codex --profile dev` | 轻量开发 | `low` reasoning，少并行，小工具输出 |
| `embedded` | `codex --profile embedded` | 嵌入式低成本路径 | `low` reasoning，禁自动命令，低 verbosity |
| `debug` | `codex --profile debug` | 排障 | `medium` reasoning，保留较大工具输出 |
| `max` | `codex --profile max` | 深水任务 | `xhigh` reasoning，1M context，高历史上限 |

## 多窗口与运行中切换

运行中的 Codex TUI 不热切换完整配置。切换模式时应退出或另开窗口，以新 profile 启动：

```bash
rtk codex --profile dev
rtk codex --profile debug
rtk codex --profile embedded
rtk codex --profile max
```

恢复旧会话时也在启动命令上指定 profile：

```bash
rtk codex resume --profile debug --last
rtk codex resume --profile max <SESSION_ID>
```

多个窗口并发不同配置时，每个窗口显式指定 profile：

```bash
# 窗口 A
rtk codex --profile dev

# 窗口 B
rtk codex --profile max

# 窗口 C
rtk codex resume --profile debug --all
```

不要在多个窗口运行期间反复覆盖 `~/.codex/config.toml`。覆盖全局配置只影响后续启动，并且容易让窗口模式来源变得不可追踪。

旧模板覆盖方式已移除。需要新增模式时，直接在 `src/codex-home/config/base.toml` 增加 `[profiles.<name>]`，并同步更新本指南。

## 更新流程

每次调整配置后执行：

```bash
rtk bash ~/codex/scripts/build.sh
rtk bash ~/codex/scripts/doctor.sh --scope all
rtk bash ~/codex/scripts/plan.sh --target ~/.codex --prune-stale --output ~/codex/build/apply-plan.json
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json --dry-run
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json
rtk codex --strict-config doctor --summary --ascii
```

如果默认 `~/.codex/config.toml` 已发生允许漂移，且确需同步 source 的默认配置，再单独执行覆盖预演：

```bash
rtk bash ~/codex/scripts/plan.sh --target ~/.codex --overwrite --prune-stale --output ~/codex/build/apply-plan-overwrite.json
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan-overwrite.json --dry-run
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan-overwrite.json
```

发布或 final 前补：

```bash
rtk bash ~/codex/scripts/apply-ready.sh
rtk bash ~/codex/scripts/final-ready.sh
```

## 升级 Codex CLI 后的核验

1. 运行 `rtk codex --version` 记录版本。
2. 打开官方配置文档，核对新增、弃用和默认值变化。
3. 运行 `rtk codex --strict-config doctor --summary --ascii`。
4. 运行 `rtk codex features list`，不要默认启用 under-development flag。
5. 若官方字段变化影响本指南，同步修改本文件和 `src/codex-home/config/base.toml`。
