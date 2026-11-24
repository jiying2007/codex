---
name: adk-fault-injection-recovery
description: "用于已授权的故障注入、失败路径与恢复能力验证，并记录可重放的回滚证据；不用于未经隔离的生产设备破坏性实验。"
version: 1.0.5
last_updated: 2026-11-20
triggers:
  - "故障注入"
  - "故障恢复"
  - "容错测试"
non_triggers:
  - 无状态纯计算脚本
inputs:
  - 故障模型、恢复目标
outputs:
  - 注入方案与恢复结果
constraints:
  - 根据项目风险选择故障模型；未经许可不得强制掉电和资源耗尽
---

# adk-fault-injection-recovery

## Goal
验证检测、恢复、回归及 SLA。

## Prerequisites
定义故障模型、恢复 SLA 和数据损失边界，核项目注入器与恢复通道。

## Workflow
1. **选择注入点**：按影响范围和可复现性排序。
   - 软件注入：内存分配失败、I/O 返回错误、信号模拟。
   - 硬件注入：断电、信号干扰、温度异常。
2. 同输入先跑无故障对照；失败先排环境/基线。一次一种故障，保存前置状态、命令和原输出。
3. 配置成功不等于触发；用目标路径的计数/事件证明命中。未命中或证据不可用记 `not_evaluated`，不能凭错误返回或健康 follow-up 反推命中。
4. 确认命中后，以实际事件和时钟来源核检测、隔离、重试、降级、恢复；缺时间证据不填零时延，不判 SLA 通过。
5. 撤销故障后核功能、数据一致性和资源恢复，交恢复盲点、告警/监控改进与真实回执。

仅作 host 观察分流，非 SLA/设备资格判定；`hits=None` 表示无命中证据，后续仍须检查检测和全部恢复后置条件：
<!-- adk-example: fault-observation -->
```python
def next_check(control_ok, hits):
    if not control_ok or hits is None or hits <= 0:
        return "not_evaluated"
    return "待核检测与恢复"
```

## Commands
默认只读。此 Skill 不直接写入 `/sys/kernel/debug`、`/dev/watchdog`，也不启动资源耗尽负载。

```bash
cat /proc/interrupts
dmesg | tail -n 120
journalctl -p err --since "10 min ago"
```

## 故障注入授权边界
仅在已明确授权的隔离 SIL/HIL/lab 目标上，由独立设备操作者使用经审查的项目注入器。必须先冻结目标身份、注入类型、资源预算、恢复命令、回滚方案与停止条件，并保留真实注入/恢复回执；否则保持 `not_evaluated`。

## Evidence Template
```md
- Fault Model: [掉电/超时/资源耗尽/链路中断]
- Method / Point / Preconditions:
- Normal Control / Activation Count-or-event / Raw Evidence:
- Watchdog Config (if applicable):
- Detection / Recovery Time + Clock: measured ms / unknown
- Recovery Strategy / Data Loss / Resource / Functional Result:
- Commands / Logs / Receipts / SLA Result:
```

## Failure Handling
- 出现不可逆破坏风险时立即停止注入并回滚环境。
- 恢复失败先保留 coredump/日志，再最小化复现；panic 先保存串口日志与 coredump 再重启。
- 看门狗未触发时，检查喂狗逻辑是否在异常路径中被错误调用。

## Quality Gate
- 必须覆盖项目风险分析要求的故障类型；掉电、超时和资源耗尽是候选，不为凑两类而开展无关或危险实验。
- 记录命中、检测/恢复及 SLA 依据；未测时间保持 unknown，风险升高立即停止。
- 仅当 watchdog 属于本次目标且已授权隔离实验时，验证 timeout/reset/recovery；缺条件标记 not-evaluated。
- 恢复后必须通过功能回归测试。
