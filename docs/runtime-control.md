# Runtime Control

Runtime Control 是 Codex 任务执行、实时 Token/上下文观察、长任务连续性和阶段门禁的唯一控制面。旧任务表、用量面板、会话教练和 ready wrapper 已移除，不提供别名、双读、双写或状态迁移。

## 唯一架构

```text
state_5.sqlite + session rollout + Runtime Control Journal
                         |
                         v
          tools.codex_assets.runtime_control
                         |
                         v
       agent_dev_kit.runtime_control Engine 4.0.0
                         |
                         v
       state/v1 + decision/v1 + gate exit code
```

- `manifests/runtime_control.json`：唯一策略和 ADK wheel 版本/SHA-256 绑定。
- `vendor/wheels/agent_dev_kit-4.0.0-py3-none-any.whl`：唯一归约与决策实现。
- `~/.codex/runtime-control/<thread-hash>.jsonl`：唯一任务 Journal。
- `scripts/runtime-control.sh`：唯一用户入口。

CLI 默认绑定当前 Codex 进程提供的 `CODEX_THREAD_ID`；自动化或外部终端可显式传 `--thread-id <id>`。只有两者都不存在时才选择最近活动线程。多会话环境不得依赖“最近活动”来执行写事件或阶段门禁。

Codex adapter 只采集和规范化数据，不拥有阈值、优先级或完成判定。wheel 缺失、版本不符、摘要不符、事件冲突、累计用量回退或 schema 不符都会 fail closed。

## 数据边界

Journal 只允许版本化结构事件：目标生命周期、累计用量快照、进度、心跳、重试、证据、checkpoint 和制品验证。它不保存 prompt、messages、content、目标原文、命令输出或真实 cwd；cwd 只保存 SHA-256。

用量来自当前线程的最新 rollout `token_count`，线程和 rollout 定位来自 `~/.codex/state_5.sqlite` 与 `~/.codex/sessions`。任务状态不读取第二张目标表。

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

`snapshot` 与 `watch` 都输出同一个 `runtime_control.decision/v1`；`goal status` 输出完整 `runtime_control.state/v1`。多项成功标准、必需证据或 checkpoint 证据通过重复对应参数表达。`watch --iterations <n>` 可用于有界自动化；省略时持续刷新，直到用户中断。

若实测消耗或外部时限变化，使用 `goal update --token-budget <n>` 或 `--time-budget-seconds <n>` 显式修订预算。修订本身是 `goal.updated` 事件并保留在同一 Journal；不得改写旧事件或直接编辑状态。

## 决策和退出码

Engine 使用固定优先级综合 Token 比例、上下文比例、时间预算、心跳新鲜度、重试预算、无进展次数、checkpoint、证据和制品：

- `continue`：继续执行。
- `checkpoint`：先固化当前进度和证据。
- `compact`：先压缩上下文，再恢复执行。
- `replan`：状态陈旧、重试/无进展超限或门禁前提不足。
- `stop`：Token 或时间预算耗尽。
- `pass`：指定阶段门禁通过。

`gate --event apply` 允许活动任务在 repo/build/plan/dry-run 证据齐全且运行状态健康时通过。`final`、`commit`、`release` 必须先完成目标，并满足当前 checkpoint、必需证据和相应制品契约。

门禁通过返回 0，门禁不通过返回 3，配置、制品、Journal 或采集错误返回 2。调用方必须消费退出码，不得根据输出文本另建判断。
