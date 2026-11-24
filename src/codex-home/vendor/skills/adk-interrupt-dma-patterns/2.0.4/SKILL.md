---
name: adk-interrupt-dma-patterns
description: "用于中断、DMA、缓存一致性、共享缓冲所有权的实现模式与实时性检查；不用于无中断参与的普通应用逻辑或免证据修改寄存器。"
version: 2.0.4
last_updated: 2026-11-20
triggers:
  - "中断处理"
  - "DMA处理"
  - "中断DMA"
  - "缓存一致性"
  - "DMA丢数据"
  - "DMA读到旧数据"
  - "FromISR断言"
  - "DMA cache coherency"
non_triggers:
  - 无中断且无 DMA 的纯轮询任务
inputs:
  - 外设速率与 burst、latency/jitter budget、buffer ownership、DMA/cache 特性、错误恢复约束
outputs:
  - IRQ/DMA 模式、ownership 状态机、cache policy、预算证据和恢复路径
constraints:
  - 不使用固定数据速率或固定 ISR 百分比作为跨平台判据
  - ISR/DMA callback 必须有明确时间预算、ownership 和错误恢复
  - non-coherent DMA 必须显式处理 cache clean/invalidate 或平台等价机制
---

# adk-interrupt-dma-patterns

## Goal
- 在 Linux、RTOS 与 bare-metal 平台上建立可验证的 IRQ + DMA 数据通路。
- 用目标系统的吞吐、latency、jitter、CPU、buffer 和 cache 约束选择模式，而不是使用通用经验阈值。

## Prerequisites
- 锁定 CPU/SoC/MCU、DMA controller、cache/coherency model、bus 与外设速率。
- 明确 sustained/burst rate、允许丢包、latency/jitter budget、buffer depth 和 backpressure 策略。
- 明确 DMA memory ownership 在 CPU/device 之间如何转移。

## Workflow
1. **预算建模**：记录 event rate、burst、latency/jitter budget、CPU budget、buffer drain/fill rate。
2. **模式选择**：比较 polling / IRQ / DMA / IRQ+DMA，按目标约束和实测数据决策，不按固定速率分界。
3. **Ownership 状态机**：定义 `free -> cpu-owned -> device-owned -> completed -> cpu-owned` 或平台等价状态，并规定每次 transition 的唯一 owner。
4. **ISR/callback 边界**：只执行 bounded work；记录 WCET/最大观测时间和允许预算，复杂处理下沉 task/thread/bottom-half。
5. **Cache/coherency**：区分 coherent/non-coherent；non-coherent 路径明确 clean/invalidate、barrier、mapping/sync API 和方向。
6. **Buffer/backpressure**：设计 single/double/ring/descriptor queue，覆盖 overrun、underrun、wrap、partial transfer 和 producer/consumer 失速。
7. **DMA completion/error**：处理 complete/error/timeout/cancel/reset/late completion，确保 descriptor/channel/buffer 只释放一次。
8. **并发验证**：检查 IRQ masking、nested interrupt、priority inversion、memory ordering、multi-core ownership 和 teardown race；FreeRTOS 的 `FromISR` 断言先核对 port、实际 NVIC 优先级位数、ISR API 允许范围和逻辑优先级与数值方向，不套用其他 CPU 的 NVIC 寄存器。详见 `references/rtos-isr-dma-diagnostics.md`。
9. **压力验证**：在代表性 burst/并发/错误注入下采集 throughput、latency、jitter、CPU、IRQ rate、drop/error count 和 recovery time。

## Platform Mapping
| Platform | Typical primitives | Required evidence |
|---|---|---|
| Linux | dma_map/sync/coherent API, threaded IRQ, NAPI/tasklet/workqueue | mapping direction, lifetime, cache/coherency, teardown |
| RTOS | vendor DMA HAL, ISR notification, queue/event | ISR budget, ownership, cache maintenance, task wake latency |
| Bare-metal | DMA registers/descriptors, IRQ flags, barriers | register sequence, ownership, cache/barrier, timeout/reset |

## Commands
```bash
cat /proc/interrupts
rg -n "dma_map|dma_unmap|dma_sync|dma_alloc_coherent|request_irq|free_irq" <linux-src>
rg -n "DMA|cache.*clean|cache.*invalidate|barrier|ring|descriptor" <rtos-or-baremetal-src>
<irq-latency-trace-command>
<dma-throughput-and-error-counter-command>
```

## Evidence Template
```md
- Platform / DMA / Cache Identity:
- Workload: sustained / burst / event rate
- Budget: latency / jitter / CPU / drop tolerance
- Mode Decision: polling | IRQ | DMA | IRQ+DMA + evidence
- Buffer Ownership State Machine:
- Cache / Memory Ordering Policy:
- ISR/Callback WCET: observed/estimated + budget
- Throughput / Latency / Jitter / CPU:
- Overrun/Underrun/Error/Timeout Evidence:
- Cancel/Reset/Teardown Evidence:
- Result: pass | needs-runtime-evidence | needs-fix
```

## Failure Handling
- IRQ storm/loss：先冻结事件率、mask/unmask 顺序和 pending/ack 证据，再调整优先级或合并策略。
- DMA 数据错乱：先核 ownership、mapping direction、cache maintenance、barrier 和 descriptor lifetime。
- overrun/underrun：核 producer/consumer rate、burst、buffer depth 与 backpressure，不只扩大 buffer。
- teardown race：停止新提交，等待/取消 in-flight descriptor，并证明 late completion 不会二次释放。

## Quality Gate
- 必须有目标系统 latency/jitter/throughput 或 CPU budget，不能以固定 `<N KB/s` 判定模式。
- ISR/callback 必须给 bounded-work 证据，并以目标 budget 判定，不使用固定百分比门槛。
- 必须定义 CPU/device buffer ownership 与 DMA descriptor/channel lifecycle。
- non-coherent 平台必须有 cache maintenance 与 memory-order evidence；coherent 平台必须说明依据。
- 至少覆盖正常完成、错误/超时和 cancel/reset/teardown 三类路径。
- 压测必须同时报告吞吐、时延/抖动和 error/drop/recovery 指标。
