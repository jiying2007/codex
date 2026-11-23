# IRQ/DMA 观测工具（按需参考）

本文件不授予任何实时设备权限；主流程以 `../SKILL.md`、Manifest、目标项目和 operator gate 为准。示例按平台分离。

## Linux
- `/proc/interrupts` 可作为 IRQ 计数观察；内核版本/模块/统计语义需确认。
- `cyclictest` 测的是实时线程调度／唤醒延迟，**不是直接测 IRQ entry latency**；内核支持时可使用 timerlat/osnoise 区分 IRQ 与 thread，仍需测量时间基准和干扰。
- `/sys/class/dma` 的路径不保证任何 Linux BSP 都存在，缺失标为 unavailable。
- `perf`、tracefs、debugfs、stress-ng 等可能改变负载或内核状态，先核权限与隔离；不能把固定 4 CPU/4 IO、60 秒当作所有目标默认负载。

## MCU / RTOS / bare-metal
- 使用目标设备实际提供的 DWT/ETM、GPIO toggle、timer capture、逻辑分析仪或厂商 trace；并非所有 Cortex-M 都具有同一组 DWT/ETM。
- NVIC/SCB 寄存器地址与读取副作用由该芯片的 CMSIS device header/TRM 验证，**禁止把 Linux devmem2 + Cortex-M NVIC 地址当成通用读命令**。
- FromISR、ISR 优先级位数和 DMA cache/buffer 详细分支见 `rtos-isr-dma-diagnostics.md`；没有 cache 的 MCU 不需要虚构 invalidate 步骤。

## 证据与预算
记录 CPU/MCU/board/kernel/RTOS、toolchain、source/firmware hash、采样点、事件率与 burst、latency/jitter/CPU 预算、p50/p95/p99/max、原始 trace、观察动作副作用分类及恢复方案。缺真机数据只报告 needs-runtime-evidence。

来源：https://wiki.linuxfoundation.org/realtime/documentation/howto/tools/cyclictest/start ; https://docs.kernel.org/trace/timerlat-tracer.html
