---
name: adk-embedded-remote-debug-log-triage
description: 嵌入式设备端远程调试、分层连通性与日志取证，覆盖 SSH、ADB/logcat、串口、GDB remote、调试探针、设备 IP/失联恢复、远程部署前置证据、boot/dmesg/应用/OTA/prog 日志、core 线索和 HIL 分阶段门禁
version: 1.1.0
last_updated: 2026-07-26
triggers:
  - "远程调试"
  - "设备 IP"
  - "ADB连接"
  - "adb connect"
  - "No route to host"
  - "device offline"
  - "设备失联"
  - "设备恢复"
  - "远程部署"
  - "板端复测"
  - "HIL板测"
  - "设备日志"
  - "GDB远程"
  - "core和日志"
non_triggers:
  - "纯离线core且没有设备日志或远程上下文"
  - "只分析粘贴或本地日志文本且不连接设备"
  - "只校验diag suite返回码语义"
  - "只构建本地二进制且不部署或连接设备"
  - "普通单元测试失败"
inputs:
  - 设备型号、硬件/固件/镜像/制品身份、复现步骤、远程通道、授权边界、设备日志、core/符号线索和历史证据
outputs:
  - 分层健康、失联熔断、证据时间线、制品与mutation gate、HIL扩大门禁、恢复后置条件、下一步探针和gate结果
constraints:
  - 默认只读取证，不执行push、kill、restart、remount、覆盖、回滚、烧录、擦除、OTA、写寄存器或写配置
  - 端点、凭证、raw log/session、core和私有路径不得写入长期正文
  - 不用ping短路transport，不只凭adb connect退出码判断成功
  - 失联后停止写操作和无界重试，不自动归因于当前补丁
  - 不把模糊日志、缺符号backtrace或被干扰的HIL包装成根因
---

# adk-embedded-remote-debug-log-triage

## Goal

- 收敛远程设备发现、只读取证、失联恢复和日志/core 线索。
- 先判定最小失败层，再把 artifact、mutation、diag、stress、core 或修复交给对应 primary skill。

## Prerequisites

- 已记录目标设备、硬件/固件/镜像或制品身份，以及可复现的问题现象；未知字段显式标为 `unknown`。
- 已明确 SSH、ADB、串口、GDB remote、调试探针或人工转储中的可用通道，并确认端点和凭证不进入长期资产。
- 已确认本轮授权等级。默认只读；任何 state-changing 或 destructive 动作均需独立授权、回滚锚点和 postcondition。
- 已定义 timeout、最多 3 次的重试预算、失联恢复手段和停止条件；缺少恢复手段时不得进入 mutation/HIL。

## Primary Boundary

本 skill 只对 `DISCOVER`、`READONLY_PREFLIGHT`、`UNREACHABLE` 和远程证据解释负责。阶段切换时更换 primary：

- identity：`adk-artifact-gating`
- smoke/diag：`adk-embedded-diagnostic-harness`
- stress/soak：`adk-test-strategy`
- unknown failure：`adk-systematic-debugging`
- release/deploy：`adk-embedded-release-orchestration`
- completion/core：`adk-verification-before-completion` / `adk-offline-core-dump-triage`

每阶段只能有一个 primary；supporting skill 不越权写设备。

## State Machine

```text
DISCOVER -> READONLY_PREFLIGHT -> ARTIFACT_GATE -> AUTHORIZED_MUTATION
 -> SINGLE_SMOKE -> SHORT_CYCLE -> LONG_STRESS
 -> RESTORE_HEALTHY_STATE -> EVIDENCE_ARCHIVE

connectivity loss -> UNREACHABLE -> stop writes/retries
 -> serial/power/onsite handoff -> recovery -> READONLY_PREFLIGHT
```

不得从失联、identity mismatch 或 shell/app 未就绪直接跳到 mutation/HIL。

## Workflow

1. 记录设备/board、固件/image/commit、通道、复现、端点来源、时间窗、只读/写授权和恢复手段；端点不写入通用资产。
2. 命令分 `read-only`、`state-changing`、`destructive`。后两类需要明确授权；erase/flash/OTA 等破坏动作不由本 skill 执行。
3. 独立探测 host route/network hint、transport、remote shell、app/diag；每层记录 timeout、elapsed、结果和证据。
4. ping 只作提示，不能短路 transport。ADB 同时解析 `adb connect` 输出和 `adb devices -l`；`offline`、`unauthorized`、`missing`、`No route to host`、refused、timeout 均非就绪。
5. 默认一次探测，扩大重试必须有不超过 3 的 budget。失败后打开 circuit breaker，停止 push/kill/restart/remount/覆盖/回滚/flash/OTA/HIL。
6. 失联时保存最后成功层、boot/artifact identity、日志窗口和失败输出；转串口、受控电源或现场恢复。恢复后重新只读 preflight。
7. 可达后先读 boot_id、uptime、PID、core/fatal dmesg、installed identity、backup anchor、watchdog/standby/supervisor 和分层时延。
8. 构建时间线和假设矩阵，分开事实、推断、历史召回和缺失证据；并发 mutator 未隔离时标为 `confounded`。
9. HIL 只能按 single smoke -> 5～10 short cycle -> long stress -> soak -> restore 扩大；失联、core、fatal log、泄漏、身份漂移、输出停滞或恢复失败立即停止。
10. 输出脱敏 manifest/evidence index：层级结果、boot/artifact identity、raw evidence path+SHA256、授权、gate、breaker、restore/postcondition 和 residual risk。

## Command Risk

| Class | Examples | Rule |
|---|---|---|
| read-only | route、`adb devices -l`、dmesg、`/proc`、hash、GDB `bt` | 默认允许 |
| state-changing | connect、push、kill、restart、remount、覆盖/回滚 | 授权+identity+backup+postcondition |
| destructive | erase、factory reset、flash/OTA apply | 单独审批；本 skill 不执行 |

## Quality Gate

- 各健康层来源、timeout、结果和证据完整；不得把一层失败扩散为全部失败。
- transport 必须解析输出语义并二次确认状态。
- 失联必须停止写操作和无界重试，并给外部恢复 handoff。
- 写操作必须有授权、artifact identity、backup/rollback anchor 和 postcondition。
- HIL 必须逐级扩大，有 mutator 隔离、停止条件和最终健康恢复。
- 缺 core/symbol/BuildID 匹配时，不给源码级崩溃根因。
- 发布/现场结论说明 residual risk 和仍缺的真实设备证据。

## Evidence Template

- target：脱敏设备/board 引用、硬件/固件/镜像/commit 身份。
- authorization：`read-only | state-changing-approved | destructive-out-of-scope`。
- health_layers：route/network hint、transport、remote shell、app/diag 的 timeout、elapsed、结果与证据引用。
- timeline：boot_id、uptime、PID、artifact identity、关键日志窗口，以及事实/推断/confounded 标记。
- control：retry budget、circuit breaker、mutation/HIL gate、stop condition、rollback anchor。
- outcome：gate result、restore/postcondition、raw evidence path+SHA256、residual risk 和下一 primary skill。

## Detailed Contract

需要探测矩阵、HIL gate、Evidence Template 和 timeout 说明时，读取 `references/remote-adb-hil-contract.md`。
