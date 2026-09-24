---
name: adk-driver-bringup-checklist
description: 驱动 bring-up 标准检查清单；默认只读诊断，寄存器或设备写操作必须经过 live-device 显式授权门禁
version: 2.0.0
last_updated: 2026-09-17
triggers:
  - "驱动开发"
  - "驱动调试"
  - "外设联调"
non_triggers:
  - 稳定量产驱动小改
inputs:
  - 芯片型号、总线类型、板卡 identity、目标 bring-up 阶段
outputs:
  - bring-up checklist、阶段结论、设备写操作授权与验证证据
constraints:
  - 必须覆盖时钟、复位、中断、DMA
  - 默认只读诊断；寄存器写或设备状态改变不得由 workspace-write 权限隐式授权
  - live-device 写操作必须具备 target identity、explicit authorization、rollback/recovery 和 post-write verification
---

# adk-driver-bringup-checklist

## Goal
- 通过清单化流程快速收敛驱动首板联调问题。
- 把源码修改权限与真实设备写权限分离，确保 bring-up 每一步可回退、可验证。

## Prerequisites
- 确认硬件版本、板卡序列/工位 identity、pinmux、供电和时钟配置一致。
- 准备串口日志、调试通道和寄存器只读工具。
- 获取芯片参考手册（TRM）与外设寄存器映射表。

## Bring-up Stages
- `minimal`: 上电、时钟/复位、总线探测和最小收发闭环。
- `functional`: IRQ/DMA、错误路径和业务所需功能通过。
- `soak`: 循环收发、重启恢复和目标时长稳定性验证。
- `production`: 量产条件下的长稳、边界样本和产测证据；由 field readiness 决定是否放行。

## Workflow
1. **冻结目标 identity**：记录 board revision、设备 identity、SoC/MCU、固件/内核版本和本轮 stage。
2. **上电与只读检查**：电源、时钟、复位、pinmux、设备存在性和只读寄存器状态。
3. **最小闭环**：I2C/SPI/UART/CAN/USB/Ethernet 先完成无破坏性的最小收发。
4. **设备写升级门禁**：只有目标问题确实需要寄存器写、reset、模式切换或其他 live-device mutation 时，先记录目标地址/操作、预期状态、显式授权、rollback/recovery 和 readback/行为验证；缺任一项则保持只读，并 handoff 到受控 live-device operator，而不是在本 Skill 给出可执行写命令。
5. **初始化与资源路径**：验证 probe/init、设备节点、资源申请、错误退出和生命周期。
6. **中断/DMA 验证**：先轮询最小闭环，再逐步开启 IRQ、DMA、cache/coherency 和低功耗路径。
7. **异常分支**：覆盖超时、CRC、设备不存在、总线错误、IRQ 丢失/DMA 错误和恢复路径。
8. **阶段收口**：按 minimal/functional/soak/production 分别记录证据；不得用尚未执行的 24h soak 阻断 minimal bring-up，也不得用 minimal 通过冒充 production-ready。

## Commands
```bash
# 这里只保留只读诊断命令；任何寄存器写/reset/模式切换均由受控 live-device operator 执行。
devmem2 <phys_addr>
dmesg | tail -n 200
ls -la /dev/<device>*
cat /sys/class/<class>/<device>/uevent
cat /proc/interrupts
i2cdetect -y <bus>
<driver-selftest-cmd> --smoke
```

## Evidence Template
```md
- Bring-up Stage: minimal | functional | soak | production
- Hardware Identity: board_rev / device_id / SoC-or-MCU / software_commit
- Read-only Baseline:
- Bus Probe Result:
- Init Sequence Result:
- Interrupt/DMA Result:
- Live-device Mutation:
  - required: yes | no
  - target_identity:
  - operation:
  - explicit_authorization:
  - rollback_or_recovery:
  - post_write_verification:
- Error Path Result:
- Soak Result: duration / error_count / restart_count / not-run
- Gate Result: pass | needs-fix | blocked
```

## Failure Handling
- 总线基础通信失败时先回到硬件基线，不先写寄存器碰运气。
- 中断异常时先禁 DMA 做最小闭环验证再逐项开启。
- 只读寄存器异常时先核时钟、地址映射和电源；未授权不得用写操作试探。
- live-device 写后 readback/行为验证失败时立即执行预先声明的 recovery，并停止继续写。

## Quality Gate
- minimal 阶段必须覆盖时钟、复位、总线和最小收发证据；functional 阶段再要求 IRQ/DMA 与错误恢复。
- 每个阶段只对已执行证据给结论，`not-run` 不得写成 pass。
- 所有 live-device 写操作必须记录 target identity、操作、授权、恢复路径和写后验证。
- 24h 或更长 soak 是 production/field readiness 证据，不是所有 bring-up 的统一完成门槛。

## 健壮性规范
- 执行前校验输入、工具、板卡状态和权限。
- 外部命令记录命令、退出码、耗时和失败日志。
- 单步失败不阻塞独立只读检查，但不得隐藏未验证项。
