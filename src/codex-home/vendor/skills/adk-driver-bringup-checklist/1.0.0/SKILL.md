---
name: adk-driver-bringup-checklist
description: 驱动 bring-up 标准检查清单
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "驱动开发"
  - "驱动调试"
  - "外设联调"
non_triggers:
  - 稳定量产驱动小改
inputs:
  - 芯片型号、总线类型
outputs:
  - bring-up checklist
constraints:
  - 必须覆盖时钟、复位、中断、DMA
---

# adk-driver-bringup-checklist

## Goal
- 通过清单化流程快速收敛驱动首板联调问题。
- 确保每个外设从上电到稳定运行的完整路径可验证。

## Prerequisites
- 确认硬件版本、引脚复用（pinmux）、供电和时钟配置一致。
- 准备串口日志、调试通道和寄存器读写工具（例如 devmem 或厂商 CLI）。
- 获取芯片参考手册（TRM）与外设寄存器映射表。

## Workflow
1. **上电前检查**：电源电压、时钟源、复位信号、pinmux 配置。
2. **驱动框架确认**：核对 Linux platform_driver、RTOS 设备模型或 bare-metal init 顺序。
3. **总线连通性验证**：I2C/SPI/UART/CAN/USB/Ethernet 先完成最小收发。
4. **初始化路径验证**：probe/init、设备节点、日志、资源申请和错误退出路径。
5. **中断/DMA 验证**：先轮询最小闭环，再逐步开启 IRQ、DMA 和低功耗路径。
5. **异常分支验证**：超时、CRC 错误、设备不存在、总线错误。
6. **稳定性检查**：循环收发、长稳运行（>= 24h）、重启恢复。

## Commands
```bash
devmem2 <phys_addr> w <value>
devmem2 <phys_addr>
dmesg | tail -n 200
ls -la /dev/<device>*
cat /sys/class/<class>/<device>/uevent
cat /proc/interrupts
i2cdetect -y <bus>
spidev_test -D /dev/spidev<b>.<c> -p "test"
cansend can0 123#DEADBEEF
<driver-selftest-cmd> --smoke
```

## Evidence Template
```md
- Hardware Baseline:
  - Board Rev / SoC / Power Rail / Clock Source:
- Pinmux Config: [link to dts/pinctrl diff]
- Bus Probe Result:
  | Bus | Device | Address | Status |
  |-----|--------|---------|--------|
  | I2C0 | sensor | 0x68 | PASS/FAIL |
- Init Sequence Result: [dmesg log link]
- Interrupt/DMA Result:
  - IRQ registered: YES/NO
  - DMA channel: ____
  - Latency: ____ us
- Error Path Result: [timeout/CRC/missing device]
- Long-run Result: [duration, error count, restart count]
```

## Failure Handling
- 若总线基础通信失败，先回滚到硬件基线排查（万用表量电压、示波器看波形）。
- 若中断异常，先禁 DMA 做最小闭环验证再逐项开启。
- 若 devmem 读回全 0 或全 F，检查时钟使能与地址映射。
- 若驱动 probe 失败，检查设备树 compatible 字符串与驱动 of_match_table 一致性。

## Quality Gate
- 清单需覆盖时钟、复位、中断、DMA 四类检查。
- 每类至少给一个通过证据或失败日志。
- 未完成最小闭环前，不得声明"驱动已完成 bring-up"。
- 所有寄存器读写操作必须记录物理地址与预期值。
- 长稳测试需 >= 24h 且零异常计数。

---

## 健壮性规范
- 执行前校验输入、工具、板卡状态和权限。
- 外部命令记录命令、退出码、耗时和失败日志。
- 单步失败不阻塞独立检查，但不得隐藏未验证项。
