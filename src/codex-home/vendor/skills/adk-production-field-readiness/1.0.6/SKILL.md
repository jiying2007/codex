---
name: adk-production-field-readiness
description: "用于嵌入式产测、OTA、诊断及现场维护的量产准备状态和证据审查；不用于仅凭桌面测试宣称量产就绪或直接刷写设备。"
version: 1.0.6
last_updated: 2026-11-20
triggers:
  - "量产"
  - "产测"
  - "烧录"
  - "现场诊断"
  - "现场维护"
  - "OTA"
  - "回滚"
  - "RMA"
  - "设备健康检查"
  - "production-field"
  - "field readiness"
  - "embedded-production-field-readiness"
implicit_context: ["量产/产测/产线/生产现场/烧录/OTA/RMA/现场维护/现场诊断/设备交付/设备健康检查/production-field/field readiness"]
non_triggers:
  - 通用 Web 发布
  - 纯版本号整理且不涉及设备交付
inputs:
  - 设备型号、硬件版本、固件/镜像版本、生产线流程、现场维护约束
outputs:
  - 量产/现场 readiness 清单、验证矩阵、回滚策略、诊断包与残留风险
constraints:
  - 不得把构建成功等同于可量产
  - OTA 或现场升级必须声明回滚路径
  - 产测和现场诊断必须有可审计证据
---

# adk-production-field-readiness

## Goal
- 审查设备交付 readiness；普通诊断、回滚或状态机设计不因用词相同进入量产流程。
- 版本策略交 `adk-release-versioning`；本 Skill 不提供设备写入授权。

## Prerequisites
- 确认目标设备、硬件版本、BOM/板级差异、固件/镜像版本和生产批次约束。
- 确认烧录、产测、日志/诊断和现场升级入口。
- 区分自动验证与必须由 HIL、工装或人工板级证据补足的项目。

## Workflow
1. **范围确认**：记录设备型号、硬件版本、固件版本、生产线/现场约束和非目标。
2. **制品清单**：列出 bootloader、kernel、rootfs、RTOS image、配置、签名、校验和、上位机工具版本。
3. **烧录链路**：确认 flashing 命令、工装、分区、失败重试、掉电保护和烧录日志留存。
4. **产测矩阵**：覆盖电源、时钟、外设、通信、传感器/执行器、校准、唯一标识和边界样本。
5. **诊断能力**：确认串口、日志、dump、健康状态、错误码、现场包导出和隐私/密钥处理。
6. **OTA 与回滚**：声明升级入口、兼容性、断电场景、双分区/恢复分区、回滚触发和验收证据。
7. **RMA/现场维护**：定义现场复现信息、最小日志包、恢复步骤、版本判定和不可恢复条件。
8. **验证证据**：记录命令、退出码、产测报告、boot log、OTA 演练、回滚演练和残留缺口。
9. **试点测量**：涉及 Agent/自动化生产率结论时，按 `references/pilot-measurement-evidence.md` 记录任务选择、人类基线、分离时间和并发证据。
10. **签署结论**：输出 `ready | needs-fix | blocked`，并列出 go/no-go 条件。

## Readiness Matrix
```md
| Area | Item | Evidence | Owner | Status |
|---|---|---|---|---|
| artifact | bootloader/kernel/rootfs/image checksum |  |  | pending |
| flashing | flash command + failure retry |  |  | pending |
| production-test | factory test report |  |  | pending |
| diagnostics | log/dump/error-code package |  |  | pending |
| ota | upgrade + rollback drill |  |  | pending |
| field | RMA/field recovery runbook |  |  | pending |
```

## Commands
本 Skill 不提供 `scripts/firmware-release.sh`、目标项目 `build.sh` 或刷写脚本。先审查目标工程真实入口与证据。

```bash
git -C <target-repo> status --short
rg -n 'firmware|ota|rollback|flash|partition|self-test|checksum' <target-repo>
sha256sum <reviewed-firmware-artifact>
```
构建/烧录/readback/OTA 由授权操作者按受审项目命令、先行 dry-run 执行；缺实机证据不得宣称 ready。

## Evidence Promotion
- `planned -> evidence-ready`: 至少一项真实工程输入、可复跑命令、制品清单、正负路径证据和缺口。
- `evidence-ready -> regression-ready`: 必须补实机烧录/readback、boot log、HIL/SIL 或产测报告、OTA/rollback 演练和现场诊断包。
- `production-ready`: 不是 pilot 状态；必须由项目 release gate 另行签署。

## Evidence Template
```md
- Device / HW Revision:
- Firmware / Image Version:
- Artifact List:
- Flashing Evidence:
- Production Test Matrix:
- Diagnostics Package:
- OTA / Rollback Evidence:
- Field Maintenance Runbook:
- Gaps / Not Tested:
- Final Readiness: ready | needs-fix | blocked
```

## Failure Handling
- 缺硬件/工装时为 `blocked` 或 `needs-fix`，不得声明 ready。
- 烧录/启动失败切 `adk-systematic-debugging`，先定位 boot log、分区、签名和电源状态。
- OTA 成功但回滚未验证时，不能发布现场可升级结论。
- 产测脚本不稳定时，先归类为测试波动或工装问题，不得把失败静默忽略。

## Quality Gate
- 制品、烧录、产测、诊断、升级、回滚须有证据或明确缺口。
- 明确硬件/固件版本，不写“当前版本”。
- 发布到现场前必须有回滚或恢复路径。
- 诊断包不得包含未脱敏密钥、凭证或用户隐私。
- ready 须可由命令、日志或报告复核。
