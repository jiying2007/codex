---
name: adk-rtos-task-design
description: "用于 RTOS 任务优先级、周期唤醒、同步资源与调度风险设计；不用于裸机单循环或未经测量声称实时性达标。"
version: 2.0.5
last_updated: 2026-11-20
triggers:
  - "RTOS任务"
  - "任务设计"
  - "实时任务"
  - "调度分析"
implicit_context: ["RTOS/Zephyr/ThreadX/RT-Thread/VxWorks"]
non_triggers:
  - 无 RTOS/没有 RTOS
  - 普通线程划分且无实时约束
inputs:
  - 任务周期、deadline、WCET/样本、中断负载、共享资源、栈与队列约束
outputs:
  - 任务模型、优先级与周期策略、response-time/trace 证据、残留风险
constraints:
  - 不用固定经验阈值替代目标 deadline/latency budget
  - 区分测量、估算和未知值；优先级、栈与共享资源策略须有依据
---

# adk-rtos-task-design

## Workflow
1. 冻结 RTOS/MCU/clock、tick/tickless、调度策略与真实 API/port；每个 task/ISR 列 period 或最小到达间隔、deadline、WCET 状态、priority、stack、blocking resource。
2. 核 RM/DM/既有优先级策略的适用条件；按下式或目标分析器迭代 response-time。WCET 缺上界记 estimated/unknown，不以观测最大值冒充。
3. 纳入 ISR interference、critical section、scheduler lock、关中断与调度开销；明确 PIP/PCP/lock-order/message-passing/lock-free 的 owner 和最坏 blocking。
4. 按下节核周期执行；栈用静态估算与 high-water，队列用 burst/backpressure 定容量，不能只提高优先级或扩容。
5. 用目标 trace 记录 release/start/finish、response-time、jitter、deadline miss、队列/栈 high-water、CPU load。trace 超模型上界先查漏项；低于上界不证明可降低 WCET。缺板端证据 `needs-runtime-evidence`。

## 固定优先级计算（仅适用时）
单核、抢占式、任务优先级固定且互异、独立周期/有界 sporadic 任务、deadline 不大于 period、无未建模 release jitter 或自挂起时，使用同一时间单位：
```text
R0 = Ci + Bi
Rnext = Ci + Bi + sum(ceil(R / Tj) * Cj, j in higher-priority tasks) + Ii(R)
```
`C` 为有依据的 WCET 上界，`B` 为一次作业最坏阻塞，`T` 为周期/最小到达间隔，`Ii(R)` 为窗口内 IRQ 干扰。中断与调度开销不重复计数。收敛且 `R <= deadline` 只证明该模型/上界下可调度；超过 deadline 停止，缺上界/不收敛记未知。同优先级、SMP、jitter、自挂起、任意 deadline 或动态优先级另选模型；RMA 指 Rate Monotonic Analysis。

例：`Ci=2, Bi=1, Di=5`、高优先级 `Cj=1,Tj=4`：`3→4→4`；加 `Cirq=0.5,Tirq=3` 得 `3→4.5→6`，超 deadline。这是计算示例，非板测。背景：https://www.cs.york.ac.uk/rts/publications/Davis2008a.html 。

## 周期与回调执行
- 核 API 的 tick 单位、频率、位宽/回绕及转换宏；`pdMS_TO_TICKS` 可被项目覆盖。默认整数除法会量化，转换为零或超范围不得当合法周期；核有效周期能否满足需求，不擅改 tick 频率。
- 固定相位任务用项目绝对周期入口：FreeRTOS `xTaskDelayUntil(&last, period_ticks)` 更新 last；CMSIS-RTOS2 `osDelayUntil(next_tick)` 只有一个绝对 tick 参数，调用者推进 next。相对 `vTaskDelay`/`osDelay` 从调用时计时，含 work 耗时后会漂移；按业务需要选择，非一律替换。
- FreeRTOS `pdFALSE` 只表示未阻塞，到点也可能返回，不能直接记 deadline miss。以实际 release/finish 与 deadline 核超期；明确有界 catch-up、跳过过期周期或降级及计数；无界追赶会饿死其他任务。回绕/长时间停顿须依 port 的比较范围，不能用裸 `now > deadline`。
- FreeRTOS software timer callbacks 共用 daemon task：不得阻塞它；只做有界处理并检查非阻塞投递的失败。`xTimerStop`/`xTimerDelete` 的 `pdPASS` 仅表示命令入队，非回调已静止；核目标取消/完成协议，确认无在途使用后才释放 callback context。其他 RTOS 核其实际语义。

### 量化反例（host 算术，不是 RTOS 实现）
存为 `period.c`，以 host C99 核默认向下取整及 16/32-bit 范围；有效周期另核需求，实际工程仍核其宏/port。
<!-- adk-example: period-ticks -->
```c
#include <stdint.h>
int period_ticks(uint64_t ms, uint32_t hz, uint32_t tick_max, uint32_t *out) {
    if (!ms || !hz || !out || ms > UINT64_MAX / hz) return 0;
    uint64_t n = ms * hz / 1000u;
    if (!n || n > tick_max) return 0;
    *out = (uint32_t)n;
    return 1;
}
```
100 Hz：1 ms 拒绝、10 ms 得 1；16-bit/1000 Hz：65535 ms 合法、65536 ms 拒绝。溢出/拒绝不改写输出；host 证据不证明调度或 HIL。

## 验证与交付
```bash
<rtos-trace-cmd> --duration <representative-window>
rg -n "xTaskCreate|thread_create|osThread|mutex|semaphore|critical|irq" <src_path>
rg -n "priority|PRIO|stack|queue|tickless|watchdog" <src_path>
<stack-high-water-command>
<deadline-or-latency-report-command>
```
交付 Runtime Identity、任务/ISR 表、优先级/栈/队列依据、`C/B/interference/R/deadline` 迭代、周期 API/量化/超期策略、callback owner/取消后置状态、命令/trace/未测边界。确无共享资源或干扰才给有依据的 `B=0/I=0`。

验证正常周期、到点未阻塞、超期/有界恢复、零/越界转换、回绕及 timer 投递失败/取消。超 deadline 先定位 `C/B/interference`；未知仍保留，不把 host 算术、短期 trace 或缺目标板当硬实时达标。分析不授予设备写权限。

依据：[FreeRTOS task.h/timers.h/projdefs.h](https://github.com/FreeRTOS/FreeRTOS-Kernel/tree/ca759444e9ca59cfa3a9faa6cb8b49e0772ca520/include)、[CMSIS-RTOS2](https://arm-software.github.io/CMSIS_6/main/RTOS2/group__CMSIS__RTOS__Wait.html)。
