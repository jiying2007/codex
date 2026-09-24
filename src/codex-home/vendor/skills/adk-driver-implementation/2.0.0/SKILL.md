---
name: adk-driver-implementation
description: Linux、RTOS 与 bare-metal 驱动实现、验证和资源生命周期收口
version: 2.0.0
last_updated: 2026-09-17
triggers:
  - 驱动开发
  - 编写驱动
  - 实现驱动
non_triggers:
  - BSP 分析
  - live 硬件调试
  - 仅做 bring-up checklist
inputs:
  - datasheet/TRM、硬件规格、runtime 模型、接口契约、构建和测试入口
outputs:
  - 驱动代码、测试、runtime-specific lifecycle evidence、未验证项
constraints:
  - 先声明 linux-kernel / rtos / bare-metal runtime model
  - 外设访问必须有超时/错误路径或明确不适用依据
  - IRQ/DMA/并发/资源生命周期必须按目标 runtime 使用正确原语
  - 本 Skill 只授权 workspace 实现；live-device register/flash 操作必须独立显式授权
---

# adk-driver-implementation

## Goal
- 用统一的资源生命周期约束实现嵌入式驱动，同时避免把 Linux kernel 习惯错误套到 RTOS 或 bare-metal。
- 代码实现与 live-device mutation 分权：实现者可以修改源码和测试，但不能因“驱动开发”自动获得寄存器写、烧录或设备发布权限。

## Prerequisites
- 锁定 target/runtime：`linux-kernel | rtos | bare-metal`，记录版本、toolchain、SoC/MCU/board identity。
- 已有寄存器/协议定义、接口契约和验证入口。
- 已明确本次支持范围：IRQ、DMA、PM、cache/coherency、userspace/debug、boot-order 等。

## Workflow
1. **Runtime contract**：先写 runtime model、入口、资源 owner、init/start/stop/remove/reset/error transitions。
2. **接口固化**：定义消费者可见 API、状态、错误码、并发和兼容边界。
3. **最小实现**：先做可编译、可测试的最小路径；真实设备 mutation 只生成 handoff request。
4. **IRQ/DMA**：按 `adk-interrupt-dma-patterns` 管理 ISR bounded work、descriptor/buffer ownership、cache/coherency 和 teardown。
5. **错误与终止**：覆盖 timeout、partial init、cancel/reset、late completion、double-free/double-disable 防护。
6. **并发与生命周期**：明确 lock/critical-section/atomic/queue/event 的 owner 和 lock order。
7. **测试**：覆盖正常、边界、失败、重复 init/stop、资源回收和适用的 cancel/reset。
8. **交付**：输出 build/test evidence、未上板项和 live-device verification handoff；未授权时不得执行 register/flash/write。

## Runtime Mapping
| Runtime | Init/lifecycle examples | IRQ/concurrency examples | Memory/DMA focus |
|---|---|---|---|
| Linux kernel | probe/remove, devm/resource unwind, PM | spinlock/mutex/completion/threaded IRQ | dma_map/sync/coherent, teardown |
| RTOS | BSP/device init, task/service start-stop | ISR notify, mutex/semaphore/queue/event | vendor DMA + cache maintenance |
| Bare-metal | ordered init/deinit/reset | IRQ disable window, atomics/flags/ring | descriptor/register ownership + barriers |

## Commands
```bash
# Common source/lifecycle scan
rg -n "init|deinit|start|stop|reset|timeout|error|irq|dma|cache|lock|queue" <driver-path>

# Linux-specific checks (only when runtime=linux-kernel)
rg -n "probe|remove|devm_|request_irq|free_irq|dma_map|dma_unmap|mutex_lock|spin_lock" <driver-path>

# RTOS/bare-metal-specific checks
rg -n "critical|semaphore|mutex|queue|event|NVIC|IRQ|DMA|cache.*clean|cache.*invalidate|barrier" <driver-path>

<cross-build-command>
<unit-or-host-test-command>
```

## Evidence Template
```md
- Runtime Identity: linux-kernel | rtos | bare-metal + version/toolchain/target
- Scope / Non-goals:
- Interface Contract:
- Resource Lifecycle: owner + init/start/stop/reset/error/termination
- IRQ/DMA/Cache Decision:
- Concurrency / Lock Order:
- Error / Timeout / Cancel / Late-completion Paths:
- Files Changed:
- Build/Test Evidence:
- Live-device Mutation Required: yes/no
- Live-device Handoff: target / operation / recovery / post-write verification / authorization=pending|not-applicable
- Known Gaps:
- Gate Result: pass | needs-runtime-evidence | needs-fix
```

## Failure Handling
- runtime model 未声明：`needs-fix`，禁止套用默认 Linux 语义。
- shared contract/binding/public header 变化：回 `adk-interface-contract-design` 并升级 review。
- DMA/cache/lifecycle 不明确：交 `adk-interrupt-dma-patterns` 或 `adk-systematic-debugging` 补证据。
- 必须上板才能验证：输出 live-device handoff，不在本 Skill 隐式执行设备写操作。

## Quality Gate
- Runtime Identity 与适用原语必须一致；不得在 RTOS/bare-metal 强制 Linux API，也不得把裸机状态机当 Linux lifecycle。
- IRQ、DMA、并发、资源释放和错误终止路径必须显式处理或说明不适用。
- 新行为必须有 build/test/smoke 中至少一种可复跑证据；缺目标板证据时不得声称硬件路径通过。
- `live-device` escalation 不得由 `workspace-write` 隐式授权；需要独立 target identity、explicit authorization、recovery/rollback 和 post-write verification。
