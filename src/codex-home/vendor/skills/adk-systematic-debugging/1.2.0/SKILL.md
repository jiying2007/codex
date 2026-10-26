---
name: adk-systematic-debugging
description: 系统化调试流程，面向根因未明的问题定位与修复验证
version: 1.2.0
last_updated: 2026-10-26
triggers:
  - "调试"
  - "排查问题"
  - "故障定位"
  - "代码有问题"
  - "诊断循环"
  - "根因排查"
  - "问题排查"
  - "定位根因"
  - "真实问题排查"
  - "根因未明"
  - "失败定位"
non_triggers:
  - 已有明确根因且只需执行已确认修复
  - 纯文档或命名修改
inputs:
  - 现象描述、触发条件、日志与监控证据
outputs:
  - 假设矩阵、实验记录、repair note、根因结论与修复验证证据
constraints:
  - 先做只读诊断，未经确认不做破坏性操作
  - 单轮仅验证一个假设并记录正负结果
  - 没有证据链不得给出根因结论
  - 禁止在未缩小失败范围时盲目重试或扩大改动
---

# adk-systematic-debugging

## Goal
- 用最小实验成本定位根因，并输出可复现、可验证、可回归的修复路径。

## Prerequisites
- 固定问题复现条件（版本、环境、输入、时间窗）。
- 预先定义观测指标与日志采集方式。

## 方法选择
- 先按不确定性选择最少必要方法。确定性错误与源码已形成直接因果链时，记录复现、原因及修复验证即可，不为模板补齐5层Why、虚构竞争假设或制造负结果。
- 5-Why：用于已有强现象链的问题；每层 Why 必须有证据。
- 二分法：用于范围过大或回归引入点未知的问题，覆盖代码、配置、模块和输入数据。
- 假设矩阵：用于多根因并存场景，按概率、影响和验证成本排序。

## Workflow
1. **边界**：现象、影响及触发条件。
2. **基线**：记录可复现输入、日志与环境。
3. **假设**：按影响和证伪成本排序。
4. **因果**：有证据才逐层追问。
5. **单变量实验**：每轮只变更一个变量，记录命令、输入、结果。
6. **二分法定位**：若假设矩阵穷尽仍未定位，切换到二分法。
7. **负结果**：记录反例与不可重复路径。
8. **收缩**：定位最小复现单元。
9. **Repair Note**：修复前记录要保留的通过项、要重跑的最小失败项、回退锚点和风险。
10. **根因收敛与复验**：给出根因证据链，执行修复前后对比验证。
11. **升级**：无信息增量则回到假设。

E2/E3 对影响正确性或安全边界的关键前提，以冻结输入和复现命令做适用的反例验证；已有有效反例可复用并核身份。方法不适用时说明直接因果证据，不强制加 Agent；连续两轮无新信息则重审。

## Repair, Not Blind Retry

失败后的默认动作是缩小和修复，不是重复跑同一条命令或扩大改动面。

| 场景 | 正确动作 |
|---|---|
| schema/格式失败 | 修 schema 或模板，重跑格式校验，不重跑无关语义测试 |
| 语义/行为失败 | 固定最小输入和断言，保留已通过格式产物 |
| 并行子任务失败 | reopen 失败子任务，禁止重写已通过子任务输出 |
| 设备/环境不稳定 | 先固化环境和观测，再判断是否进入重试 |
| 连续失败无信息增量 | 停止重试，回到假设矩阵或拆分任务 |

```md
[repair-note]
failed_scope:
passing_scope_to_preserve:
minimal_rerun:
rollback_anchor:
root_cause_status: known | suspected | unknown
repair_action:
semantic_verification:
do_not_repeat:
```

## Commands
```bash
rtk rg -n "error|fatal|panic|timeout|reset" <log-or-src>
<debug-transport-readonly-cmd>
<target-debugger> <elf-or-process> --readonly
```

## Evidence Template
```md
- Repro Baseline: 环境 / 输入 / 复现率
- Selected Method / Applicability: 直接因果 | Hypothesis Matrix | 5-Why Chain | 二分
- Experiment / Negative Findings: 变量 / 命令 / 观察 / 结论
- Repair Note:
- Root Cause Chain: 根因 + 证据列表
- Fix Verification: 修复前 / 修复后 / 回归测试
```

## Failure Handling
- 连续两轮实验无信息增量时，必须重排假设矩阵。
- 复现不稳定时先固化环境，不继续追加修复改动。
- 5-Why 链中断时，补充证据后再继续，不跳层。
- 二分法结果矛盾时，检查测试用例是否正确。
- 最小失败范围不清时，不得进行大范围修复或重复执行同类重试。

## Quality Gate
- 调试记录必须包含时间线、实验步骤、观察结果和结论映射。
- 存在竞争假设或高风险关键前提时记录实际证伪结果；直接根因路径说明方法适用性，不要求人为增加实验。
- 修复记录必须包含 failed scope、preserved passing scope、minimal rerun 和 rollback anchor。
- 修复结论必须包含"复现 -> 修复 -> 回归"三段证据。
- 若根因仍不确定，必须显式标记为 `needs-fix`，禁止"疑似已修复"式结论。
- 使用5-Why时每层有证据支撑，因果链到达可验证根因即可停止，不固定层数。
- 使用二分法时必须记录每步 good/bad 判定依据。
- AI 工具/CLI 行为异常不得先归因实现 bug；必须固定复现、对照文档版本、追到源码或配置决策点，并用 git log/blame 建时间线。

## 合理化借口拦截
直觉不构成根因证据；偶现先固化触发条件，保持`needs-fix`直至完成复现、修复与回归。
