---
name: adk-hardware-debugging
description: "用于板级电源、时钟、复位和硬件异常的假设验证与证据定位；不用于把 Linux oops 直接归咎硬件或未经许可执行带风险的硬件操作。"
version: 1.0.4
last_updated: 2026-11-20
triggers:
  - 硬件调试
  - oops 分析
  - panic 分析
  - 问题定位
  - HardFault
  - 随机复位
  - 低功耗后无法唤醒
non_triggers:
  - BSP 分析
  - 驱动开发
inputs:
  - kernel oops/panic 信息
  - 硬件现象描述
  - datasheet 文档
outputs:
  - 问题分析报告
  - 排查方向
  - 解决方案
constraints:
  - 必须说明排查方向的置信度
  - 必须提供验证方法
  - 不能假设应该可以工作
---

# adk-hardware-debugging

## Goal
以可复核证据定位故障，保留验证边界。

## Prerequisites
确认硬件/软件身份、日志、符号与调试通道；MMIO 读副作用和现场权限先核实。

## Workflow
1. 记录触发、频率、环境/变更及 fault type、PC/LR、栈、寄存器和 taint。
2. 先据 Oops 模块标记/可信映射判定 PC 或函数所属内核、具体模块及段，再核架构与对应 `vmlinux/.ko`（MCU 用对应 ELF）。`function+offset/size` 用匹配内核 helper；runtime PC 按可信 KASLR/模块映射换算。缺所属/映射或 `??:0` 记 `partial`；行号不证明选对 ELF，不猜偏移或关闭 KASLR。
3. 按实际 Cortex-M/SDK 核 CFSR/HFSR/BFAR 能力，Cortex-M0/M0+/M23 不套 M3/M4 流程；HardFault、复位或唤醒按需读 `references/mcu-fault-reset-wakeup.md`。
4. 反追状态来源、调用者与硬件事件；列假设、置信度、单变量验证及修复/回归范围。

## Commands
```bash
rg -n "dev_err|WARN_ON|BUG_ON|panic|timeout|ETIMEDOUT" <target-dir>
rg -n "request_irq|spin_lock|mutex_lock|dma_|completion|wait_event" <target-dir>
dmesg
# Linux function+offset/size
"$kernel_src/scripts/faddr2line" "$matched_elf" "$function_offset"
# 已按映射归一化或已证明无需重定位的链接地址
"$target_addr2line" -f -i -e "$matched_elf" "$pc_link"
```
依据：[Linux 解码脚本](https://github.com/torvalds/linux/blob/master/scripts/faddr2line)。退出 0 不证明解析成功。

## Evidence Template
```md
- Symptom / Reproduction / HW-SW Identity:
- Matched ELF / Address Mapping / Logs / Registers:
- Hypotheses: confidence + evidence + single-variable validation
- Root Cause / Regression / Residual Risk:
- Gate Result: pass|needs-fix
```

## Quality Gate
- 根因须有匹配日志、源码或硬件测量支撑；假设附置信度与验证动作。
- 输出 `pass` 或 `needs-fix`；缺复现、符号或映射证据不得通过，修复建议须带回归范围。
