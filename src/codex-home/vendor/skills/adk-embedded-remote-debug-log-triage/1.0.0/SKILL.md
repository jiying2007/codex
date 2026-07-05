---
name: adk-embedded-remote-debug-log-triage
description: 嵌入式设备端远程调试与日志取证，覆盖 SSH、ADB/logcat、串口、GDB remote、调试探针、boot/dmesg/应用/OTA/prog 日志、core dump 线索、知识库历史召回和下一步探针
version: 1.0.0
last_updated: 2026-07-04
triggers:
  - "远程调试"
  - "设备端调试"
  - "嵌入式日志分析"
  - "串口日志"
  - "boot log"
  - "dmesg"
  - "设备日志"
  - "ADB日志"
  - "adb logcat日志"
  - "GDB远程"
  - "带日志远程GDB"
  - "现场日志"
  - "core和日志"
  - "OTA日志"
  - "prog日志"
non_triggers:
  - "纯离线core且没有设备日志或远程上下文"
  - "只校验diag suite返回码语义"
  - "普通单元测试失败"
inputs:
  - 设备型号、硬件版本、固件/镜像版本、复现步骤、远程访问方式、串口/ADB/boot/dmesg/应用/OTA/prog日志、core线索、符号文件、Knowledge Hub或历史会话证据
outputs:
  - 证据边界、日志时间线、异常表、远程调试安全分级、假设矩阵、历史知识召回、下一步探针、gate结果
constraints:
  - 默认只读取证，不执行重启、烧录、擦除、OTA、写寄存器或写配置
  - 不得把单条模糊日志或缺符号backtrace包装成已确认根因
  - raw log、raw session、core dump和私有路径只作证据引用，输出必须脱敏和摘要化
  - Codex历史记录只能作为候选证据源；Hub当前事实和项目文档优先
---

# adk-embedded-remote-debug-log-triage

## Goal
- 把嵌入式设备端远程调试、日志分析、core线索和历史知识召回收敛成可复核的诊断闭环。
- 先确定证据可信度和最小失败阶段，再决定是否转入 `adk-systematic-debugging`、`adk-offline-core-dump-triage`、`adk-embedded-diagnostic-harness` 或实现修复。

## Prerequisites
- 已知道目标设备、软件版本和问题现象，或至少有一段可定位来源的日志。
- 已明确远程通道类型：SSH、ADB/logcat、串口、GDB remote、调试探针、产测机、日志包、离线 artifact 或人工转储。
- 已确认本轮是否只读。默认只读；任何设备状态改变都必须先有用户明确授权、回滚锚点和风险说明。

## Evidence Boundaries
| Evidence | Required Handling |
|---|---|
| serial / boot / dmesg / app log | 记录来源、时间窗、是否完整、版本线索；只摘关键行 |
| core dump / crash artifact | 转交或叠加 `adk-offline-core-dump-triage`，先做 BuildID/符号/GDB 匹配 |
| remote shell / SSH | 默认只跑查询命令；写操作、重启和服务变更升级审批 |
| debug transport | 默认 attach/read-only；写内存、写寄存器、continue/reset 需审批；连接边界转 `adk-embedded-debug-transport` |
| Codex history / Knowledge Hub | 作为候选上下文；必须保留 source path/id、last_verified 和冲突状态 |
| raw session / raw log | 不复制进长期正文；只输出摘要、哈希/路径和脱敏证据引用 |

## Workflow
1. 固定边界：记录设备、板级版本、固件/镜像、复现步骤、通道、采集时间窗和只读/可写状态。
2. 做安全分级：把候选命令分为 `read-only`、`state-changing`、`destructive`；默认只执行或建议 read-only。
3. 建时间线：按 bootloader、kernel、driver、daemon/app、OTA/prog、diag、stress/HIL 分段，标出 reset、watchdog、mount、CRC、timeout、retry、signal、core 生成点和长间隔。
4. 识别异常：把日志事实、推断和缺失证据分开；每个异常映射到阶段、影响、证据强度和可证伪探针。
5. 召回历史：查询 Knowledge Hub、项目 runbook、session wrap 或 memory candidate；冲突或过期结论不得直接注入为事实。
6. 排假设矩阵：按证据强度、影响面和验证成本排序；硬件/电源/时序假设必须有日志、测量或复现实验支持。
7. 分流专项：有 core 时叠加 `adk-offline-core-dump-triage`；诊断 CLI 语义问题叠加 `adk-embedded-diagnostic-harness`；协议字段不一致叠加接口/协议审计能力。
8. 给下一步探针：优先选择最小日志点、寄存器 dump、counter、GDB 只读命令、符号补齐、复现输入或对照 known-good 日志。
9. 输出 gate：`stable`、`needs-more-data`、`needs-fix`、`unsafe-to-release` 或 `blocked`，并说明剩余风险。

## Command Risk Model
| Class | Examples | Rule |
|---|---|---|
| read-only | `dmesg`, `journalctl`, `cat /proc/*`, `readelf`, `info threads`, `bt`, `md5sum` | 可作为建议或验证命令 |
| state-changing | `systemctl restart`, `kill`, `gdb continue`, `devmem write`, `fw_setenv` | 需要明确授权和回滚锚点 |
| destructive | flash erase, partition wipe, OTA apply, factory reset, NAS publish | 必须单独审批；本 skill 不默认执行 |

## PCR02/SigmaStar Pilot Note
- PCR02/SigmaStar 的 core/GDB/串口日志历史可作为首个 pilot 证据来源。
- 将具体进程名、工具链路径和板卡路径写入 pilot 证据或项目归档，不写成 skill 前提。
- 若遇到 SigmaStar ARM Linux core，GDB/BuildID/rootfs 匹配经验只能作为示例优先级；其他平台必须重新验证工具链可信度。

## Evidence Template
```md
- Device Context:
  - model / board_rev / firmware / image / commit:
  - access_channel: ssh | adb | serial | gdb-remote | debug-probe | log-package | offline-artifact
  - readonly_boundary:
- Source Evidence:
  | Artifact | Source | Time Window | Complete | Sanitized | Trust |
  |---|---|---|---|---|---|
- Timeline:
  | Phase | Marker | Evidence | Anomaly | Confidence |
  |---|---|---|---|---|
- Remote Command Risk:
  | Command | Class | Purpose | Approval Needed | Rollback |
  |---|---|---|---|---|
- Historical Recall:
  | Source | Claim | Status | Conflict | Use |
  |---|---|---|---|---|
- Hypothesis Matrix:
  | # | Hypothesis | Evidence | Probe | Result |
  |---|---|---|---|---|
- Specialist Handoff:
  - core_dump:
  - diagnostic_harness:
  - protocol_contract:
- Next Probes:
- Gate Result: stable | needs-more-data | needs-fix | unsafe-to-release | blocked
```

## Quality Gate
- 必须说明日志/远程证据来源、完整性和脱敏状态。
- 必须区分事实、推断、历史召回和缺失证据。
- 必须给出至少一个可证伪的下一步探针，除非结论为 `blocked`。
- 缺 core/symbol/BuildID 匹配时，不得给源码级崩溃根因定论。
- 涉及设备写操作、重启、烧录、擦除、OTA 或发布时，必须停止并要求显式授权。
- 结论影响发布或现场维护时，必须说明 residual risk 和需要补齐的真实设备证据。
