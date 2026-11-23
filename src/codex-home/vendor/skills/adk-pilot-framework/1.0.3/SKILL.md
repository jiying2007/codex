---
name: adk-pilot-framework
description: "用于跨仓新能力的有界 Pilot 试跑、证据采集、失败门禁和回退判定；不用于替代正式产品资格认证或自动将试验结果发布。"
version: 1.0.3
last_updated: 2026-11-20
triggers:
  - "试跑"
  - "pilot"
  - "真实场景验证"
  - "运行目录验证"
  - "运行时试跑"
non_triggers:
  - 纯本地单元测试（无需运行目录验证）
  - 文档编写或方案讨论
inputs:
  - 待验证能力清单、目标运行目录、场景定义、预期行为
outputs:
  - 试跑报告（场景+证据+结论）
  - 任务结果与环境状态（pilot-pass / pilot-fail / blocked / inconclusive）
  - 回灌建议（采纳/改进/淘汰）
constraints:
  - 无真实运行证据不得声明 pilot 通过
  - 目标项目声明的必需健康与试跑检查必须通过；检查通过不代替任务验收
  - 失败项保留实际原因或未知，不以缺少运行环境推断能力无效
---

# adk-pilot-framework

## Goal
用真实、有界的任务判断能力在目标环境是否可用，交付实际结果、观察证据和可执行改进。仅验证一次可用性时做 smoke；要宣称优于现状时才做固定条件的对照。

## Prerequisites
- 已有任务输入、可观察的成功/失败条件、目标版本和真实运行入口。
- 明确已授权的执行环境、数据、成本与停止条件；不因试跑自动安装或调用付费模型。
- 需要改动的环境有隔离、恢复办法；先复用已有安装和通过证据。

## Workflow

1. 固定一个实际任务、输入、输出判定和目标环境；先确认是 smoke 还是收益比较，不用工具连通代替业务成功。
2. 查现有加载与健康证据，核对版本和初始工作状态。目标不可用时记录 `blocked` 与恢复条件，完成仍可执行的只读准备，不制造试跑结果。
3. 在既有权限与预算内执行任务，保留真实命令/工具事件、产物、失败、重试和用量。只重复有明确样本目的的试验；不能挑成功轮或重跑到绿。
4. 按预定标准检查最终产物和失败路径，再核目标项目声明的必需检查。只有项目确实规定 health-check / global-health / pilot-gate 时才执行三联，不要求普通目标提供 ADK 内部脚本。
5. 比较能力收益时冻结输入、初始状态、模型/工具、预算和判定标准，重复对照并保留逐例退化；缺真实测量就记 `not-measured`。单次 smoke 不证明稳定成功率或节省成本。
6. 给出可用结果、已发现问题和下一次最小改进；根因不明则保留假设与取证路径。采纳、长期矩阵更新和发布仍分别遵循已有授权，不由本次通过自动触发。


## Quality Gate

1. 真实任务产物符合预定验收且目标必需检查通过，才记 `pilot-pass`；静态结构通过不是原生执行证据。
2. 已执行的任务不满足验收记 `pilot-fail`，环境阻塞记 `blocked`，有效性或判定证据不足记 `inconclusive`。
3. 失败、重试和未运行项完整保留；未知根因不得编造，已有负结果记录继续复用。
4. 结论限定在实际输入、版本和环境；性能、成本与稳定性结论需要对应观测。


## Evidence Template

```md
status: pilot-pass | pilot-fail | blocked | inconclusive
task / target / source:
acceptance / observed output:
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
next experiment / recovery condition:
```

## References
- 详细背景、命令、模板、示例和扩展检查项保存在 `references/details.md`。
- 入口文件只保留触发和执行所需的最小上下文，避免默认加载过多 token。
