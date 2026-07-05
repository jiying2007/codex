---
name: adk-embedded-debug-transport
description: 嵌入式设备调试通道治理，覆盖 ADB/logcat、SSH、串口控制台、GDB remote、硬件调试探针和厂商 CLI 的连接边界、命令风险、证据采集和回滚锚点
version: 1.0.0
last_updated: 2026-07-04
triggers:
  - "调试通道"
  - "设备调试通道"
  - "设备连接调试"
  - "ADB调试"
  - "adb logcat"
  - "SSH调试"
  - "串口调试"
  - "串口控制台"
  - "GDB remote"
  - "调试探针"
  - "厂商调试CLI"
non_triggers:
  - "只有设备日志需要分析"
  - "纯离线core"
  - "只需要诊断suite返回码语义"
inputs:
  - 设备型号、硬件版本、固件/镜像版本、目标OS/runtime、可用连接方式、权限边界、候选命令、日志/core/符号路径、回滚或断电恢复方式
outputs:
  - 调试通道矩阵、命令风险分级、连接验证、证据采集计划、回滚锚点、handoff到日志/core/系统化调试的边界
constraints:
  - 默认只做连接识别、只读命令和证据采集
  - 不把任一具体工具、探针、厂商CLI或OS作为ADK默认前提
  - 写寄存器、写内存、重启服务、重刷镜像、擦除分区、OTA和出厂复位必须显式审批
---

# adk-embedded-debug-transport

## Goal
- 为嵌入式设备选择和治理调试通道，而不是绑定某个工具链。
- 先确认连接方式、权限、命令风险和证据边界，再进入日志分析、core triage、诊断 harness 或根因排查。

## Prerequisites
- 已确认目标设备、固件/镜像版本和 OS/runtime 类型。
- 已列出至少一种可用调试通道，或已说明当前没有可用通道。
- 已明确本轮是只读取证、连接验证，还是需要申请更高风险操作。

## Channel Matrix
| Channel | Typical Use | Read-only Evidence | Risk Boundary |
|---|---|---|---|
| serial console | boot、kernel、RTOS、早期启动和恢复 | boot log、panic/oops、shell prompt、版本banner | break/bootloader写入、环境变量修改、刷写升级需审批 |
| SSH shell | Linux设备运行态、daemon、系统服务 | `dmesg`、`journalctl`、`ps`、`ip`、`cat /proc/*` | restart/kill/config write/package install需审批 |
| ADB/logcat | Android或ADB暴露设备 | `adb devices`、`adb logcat -d`、`adb shell getprop` | remount、push、setprop、reboot、root需审批 |
| GDB remote | 用户态/RTOS/bare-metal断点和状态读取 | attach、threads、bt、registers、memory read | continue、set variable、write memory、reset需审批 |
| hardware debug probe | MCU/SoC低层 halt、寄存器和内存观察 | probe detect、halt status、register read、memory read | erase/program/fuse/lock/unlock需审批 |
| vendor debug CLI | 厂商产测、烧录、诊断、trace工具 | version、status、dry-run、readback摘要 | flash、calibration write、factory reset、publish需审批 |

## Workflow
1. 固定上下文：设备、板级版本、固件/镜像、OS/runtime、复现步骤、当前供电/网络/串口/探针状态。
2. 列通道矩阵：记录每个通道是否可用、凭证来源、权限级别、所需物理接触和失败回退方式。
3. 做命令分级：把候选命令分为 `read-only`、`state-changing`、`destructive`。
4. 先跑连接验证：只确认设备可见、版本一致、符号/镜像匹配和日志窗口可采集。
5. 采集最小证据：优先拿 boot/runtime 日志、进程状态、寄存器只读快照、core线索、版本banner和时间线锚点。
6. 分流下一步：
   - 日志和现场时间线：转 `adk-embedded-remote-debug-log-triage`。
   - 离线 core 和符号匹配：转 `adk-offline-core-dump-triage`。
   - 诊断 CLI/suite 语义：转 `adk-embedded-diagnostic-harness`。
   - 根因仍不明：转 `adk-systematic-debugging`。
7. 输出回滚锚点：任何 state-changing/destructive 操作前必须有恢复路径、备份或人工确认。

## Command Risk Model
| Class | Rule | Examples |
|---|---|---|
| read-only | 可建议执行；仍需脱敏输出 | version/status/log dump/register read/backtrace |
| state-changing | 需要明确授权、影响面和回滚锚点 | restart/kill/continue/set variable/write config |
| destructive | 本 skill 不默认执行；必须单独审批 | erase/program/OTA apply/factory reset/fuse/partition wipe |

## Evidence Template
```md
- Device Context:
  - model / board_rev / firmware / os_runtime / commit:
- Debug Channel Matrix:
  | Channel | Available | Auth Source | Access Level | Evidence | Risk |
  |---|---|---|---|---|---|
- Command Risk:
  | Command | Class | Purpose | Approval | Rollback |
  |---|---|---|---|---|
- Connection Check:
  - device_visible:
  - version_match:
  - symbol_or_image_match:
- Evidence Collected:
- Handoff:
  - log_triage:
  - core_triage:
  - diagnostic_harness:
  - systematic_debugging:
- Gate Result: ready | needs-more-data | blocked | unsafe
```

## Quality Gate
- 必须覆盖至少两类可选通道，或说明为什么只有一种通道可用。
- 必须显式标记命令风险等级。
- 任何写操作、重启、刷写、擦除、OTA或出厂复位都不能作为默认动作。
- 调试通道结论不得替代根因结论；根因仍需证据链和专项 skill 验证。
