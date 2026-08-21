---
name: adk-driver-implementation
description: 嵌入式驱动实现、联调验证与风险收口
version: 1.0.0
last_updated: 2026-05-16
triggers:
  - 驱动开发
  - 编写驱动
  - 实现驱动
non_triggers:
  - BSP 分析
  - 硬件调试
inputs:
  - datasheet 文档
  - 硬件规格
  - 驱动框架
outputs:
  - 驱动代码
  - 单元测试
  - 编码报告
constraints:
  - 中断处理函数禁止 mutex_lock 和 GFP_KERNEL 分配
  - 外设访问必须设置超时和错误路径
  - DMA 路径必须处理映射、同步和回收
---

# adk-driver-implementation

## Goal
- 基于设计文档、datasheet 和目标框架实现嵌入式驱动，并交付可验证代码与测试。

## Prerequisites
- 已有明确的寄存器定义、接口契约和目标平台约束。
- 已确认内核/RTOS 版本、编译入口和最小测试方式。
- 已明确本次支持范围和非目标，例如 DMA、PM、debugfs 是否纳入。

## Workflow
1. 输入核对：确认 spec/design/tasks、寄存器表、设备树或板级配置齐全。
2. 接口固化：定义 probe/remove、irq、DMA、pm、userspace/debug 入口和资源生命周期。
3. 最小实现：按任务切片实现，优先复用现有驱动模式。
4. 错误路径：补齐超时、资源释放、并发保护和日志。
5. 测试补充：覆盖正常路径、边界路径、失败路径和资源回收。
6. 交付报告：列出改动文件、验证命令、未验证项和回退方式。

## Commands
```bash
rg -n "mutex_lock|kmalloc\\(.*GFP_KERNEL|msleep|schedule" <driver-file>
rg -n "readl|writel|regmap|dma_map|dma_unmap|request_irq" <driver-file>
<cross-build-cmd>
<unit-or-smoke-test-cmd>
```

## Evidence Template
```md
- Scope:
- Files Changed:
- Interface Contract:
- Error Paths:
- Tests:
- Build Result:
- Known Gaps:
- Gate Result: pass|needs-fix
```

## Quality Gate
- 中断、DMA、并发和资源释放路径均被显式处理。
- 新行为有测试或 smoke 验证证据。
- 输出必须包含 `pass` 或 `needs-fix`，未验证项不得伪装成通过。
- shared contract、binding 或公共头文件变更必须升级评审。
