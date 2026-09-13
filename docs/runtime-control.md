# Runtime Control

Runtime Control 是 Codex 任务执行、Token/上下文观察、长任务连续性和阶段门禁的唯一运行控制面。旧任务表、用量面板、会话教练、ready wrapper 以及 ADK 4.0 wheel bridge 均已退役；active path 不提供别名、双读、双写或旧 engine fallback。

## 唯一架构

```text
state_5.sqlite + session rollout + Runtime Control Journal
                         |
                         v
          tools.codex_assets.runtime_control
                         |
                         v
           tools.codex_assets.runtime_kernel
                         |
                         v
       state/v1 + decision/v1 + gate exit code
```

- `manifests/runtime_control.json`：唯一策略、native engine 声明和行为基线 provenance。
- `tools/codex_assets/runtime_kernel.py`：stdlib-only 的 v1 reducer/decision kernel；不运行时依赖 `agent_dev_kit`、PyYAML 或 jsonschema。
- 行为基线固定到 ADK 5.1.0 exact source：commit `59cbd5cb40ca7077ee5407636bfc617e295ec7e5`，engine blob `c01f71f2d8518266f947d696b8828cb102859ce1`，support blob `4dbb0d10c0733f8cc7a897d5325cf819a34872f0`。
- `~/.codex/runtime-control/<thread-hash>.jsonl`：唯一任务 Journal。
- `scripts/runtime-control.sh`：唯一用户入口。

ADK 提供 reusable asset/control-plane 规范与行为基线；Codex 拥有 Codex-specific runtime distribution、journal、host observation 和本地 gate 实现。行为 provenance 不等于运行时包依赖。

CLI 默认绑定当前 Codex 进程提供的 `CODEX_THREAD_ID`；自动化或外部终端可显式传 `--thread-id <id>`。只有两者都不存在时才选择最近活动线程。多会话环境不得依赖“最近活动”执行写事件或阶段门禁。

配置 schema、行为基线、事件顺序、累计用量、证据或 gate contract 不一致时全部 fail closed。

## 数据边界

Journal 只允许版本化结构事件：目标生命周期、累计用量快照、进度、心跳、重试、证据、checkpoint 和制品验证。它不保存 prompt、messages、content、目标原文、命令输出或真实 cwd；cwd 只保存 SHA-256。

用量来自当前线程最新 rollout 的 `token_count`；线程和 rollout 定位来自 `~/.codex/state_5.sqlite` 与 `~/.codex/sessions`。任务状态不读取第二张目标表。

## 基本流程

```bash
rtk bash scripts/runtime-control.sh goal start \
  --goal-id runtime-control-cutover \
  --token-budget 200000 \
  --time-budget-seconds 14400 \
  --success-criterion tests-pass \
  --required-evidence tests-pass \
  --open-items 4

rtk bash scripts/runtime-control.sh snapshot
rtk bash scripts/runtime-control.sh goal status
rtk bash scripts/runtime-control.sh watch --interval 3
rtk bash scripts/runtime-control.sh progress --revision 1
rtk bash scripts/runtime-control.sh heartbeat
rtk bash scripts/runtime-control.sh evidence --evidence-id tests-pass --sha256 <sha256>
rtk bash scripts/runtime-control.sh checkpoint --revision 1 --evidence-id tests-pass
rtk bash scripts/runtime-control.sh artifact --artifact-type repo --evidence-id tests-pass
rtk bash scripts/runtime-control.sh goal update --open-items 0
rtk bash scripts/runtime-control.sh goal complete
rtk bash scripts/runtime-control.sh gate --event final
```

`snapshot` 与 `watch` 输出 `runtime_control.decision/v1`；`goal status` 输出 `runtime_control.state/v1`。预算修订通过 `goal update` 形成不可改写的 `goal.updated` Journal 事件。

## 决策和退出码

Kernel 按固定优先级综合 Token 比例、上下文比例、时间预算、心跳新鲜度、重试预算、无进展次数、checkpoint、证据和制品，输出 `continue / checkpoint / compact / replan / stop / pass`。

`apply` 可在活动任务满足 repo/build/plan/dry-run 证据且运行状态健康时通过；`final / commit / release` 必须先完成目标，并满足当前 checkpoint、必需证据和相应制品契约。

门禁通过返回 0，门禁不通过返回 3，配置、Journal 或采集错误返回 2。调用方必须消费退出码，不得根据输出文本另建判断。
