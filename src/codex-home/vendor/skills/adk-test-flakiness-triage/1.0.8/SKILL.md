---
name: adk-test-flakiness-triage
description: "用于非确定性测试故障的复现、波动归因和消除不稳定方案验证；不用于把失败盲目重跑到绿或降低测试门禁。"
version: 1.0.8
last_updated: 2026-11-20
triggers:
  - "测试波动"
  - "flaky test"
  - "测试不稳定"
non_triggers:
  - 测试稳定失败且根因明确
inputs:
  - 失败日志、执行环境、历史通过率
outputs:
  - 波动根因假设、验证实验、修复建议
constraints:
  - 必须区分环境噪声与真实缺陷
  - 调查阶段默认只读优先，不先行改动生产配置
---

# adk-test-flakiness-triage

## Goal
- 定位测试波动根因并给出稳定化方案。

## Prerequisites
- 获取可比失败/成功样本及环境、依赖、资源；不足记样本数/采样偏差，不伪造基线。

## Workflow
1. 从CI历史识别不稳定测试。
2. 按错误、阶段、环境聚类。
3. 列根因假设，单轮只验证一个。
4. 按 `references/details.md` 比较环境/时序；有证据时定位顺序污染或 readiness 竞争，保留 seed、worker、进程与时序契约。
5. 按证据确定重试次数/退避；需隔离则验证边界、保留原失败。
6. 优先证伪可复现假设；跨系统因果需要时才5-Why，不凑层数。
7. 验证修复后的稳定性与原成功路径。

## Quality Gate
- 交付可复现实验/回归计划；至少记录一条被排除假设。
- 记录失败率基线、样本/失败数、环境与统计假设；目标按风险确定。
- 隔离需验证对其他测试的影响。
- 20 次有界重复可作为 smoke，但零失败不代表达成低失败率目标；独立同分布下 20 次零失败，单侧 95% 失败率上界仍约 13.9%，更严格目标须另行设计统计证据。

## Failure Handling
- 难复现先固化环境，不改生产配置；疑似真实缺陷转 `adk-systematic-debugging` 并升级优先级。
- 重试仍不稳定则 `quarantine` 或保持原失败开放；保留 owner、解除条件、原状态和 CI 证据，不能把被隔离测试计为 PASS。
- 外部依赖可按需stub/mock稳定离线用例；不替代真实集成，注明实测边界。

## Evidence Template

```md
status: pass | needs-fix | BLOCKED
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
```

## References
- 按需命令与示例：`references/details.md`。
