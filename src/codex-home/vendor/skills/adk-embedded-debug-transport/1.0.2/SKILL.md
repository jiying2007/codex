---
name: adk-embedded-debug-transport
description: "用于管理串口、SSH、ADB、远程 GDB 等调试通道的连接与权限证据；不用于隐式远程部署、修改设备配置或替代故障根因分析。"
version: 1.0.2
last_updated: 2026-11-09
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
| GDB remote | 用户态/RTOS/bare-metal断点和状态读取 | 已暂停目标上的 threads、bt；经手册确认的非破坏性状态读取 | attach/halt 会暂停目标，resume/continue 会改变目标执行；均须评估授权与恢复 |
| hardware debug probe | MCU/SoC低层 halt、寄存器和内存观察 | probe detect、halt status；已确认不清状态的读取 | halt/attach 以及有读副作用的 MMIO 不是被动采集；erase/program/fuse 等须单独审批 |
| vendor debug CLI | 厂商产测、烧录、诊断、trace工具 | version、status、dry-run、readback摘要 | flash、calibration write、factory reset、publish需审批 |

## Workflow
1. 固定上下文：设备、板级版本、固件/镜像、OS/runtime、复现步骤、当前供电/网络/串口/探针状态。
2. 列通道矩阵：记录每个通道是否可用、凭证来源、权限级别、所需物理接触和失败回退方式。
3. 做命令分级：候选命令区分 `passive-observation`、`active-probe`、`state-changing`、`destructive`，并记录是否会暂停进程、触发 I/O 或清除寄存器状态。
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
| passive-observation | 已确认不会扰动目标；仍需脱敏输出 | version/status/log dump/现有 core 的离线 backtrace |
| active-probe | 需要明确探测范围和许可；不得称为纯只读 | i2cdetect、动态 selftest、主动访问设备总线 |
| state-changing | 需要明确授权、影响面和回滚锚点 | GDB attach/halt/continue、restart/kill/set variable/write config、可能有副作用的 MMIO read |
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
- 必须显式标记命令风险等级；GDB attach/halt 和有读副作用的 MMIO 不能归为纯只读。
- 任何写操作、重启、刷写、擦除、OTA或出厂复位都不能作为默认动作。
- 调试通道结论不得替代根因结论；根因仍需证据链和专项 skill 验证。
