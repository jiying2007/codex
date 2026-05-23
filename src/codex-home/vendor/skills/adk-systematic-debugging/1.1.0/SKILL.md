---
name: adk-systematic-debugging
description: 系统化调试流程，面向根因未明的问题定位与修复验证
version: 1.1.0
last_updated: 2026-05-20
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
- 5-Why：用于已有强现象链的问题；每层 Why 必须有证据。
- 二分法：用于范围过大或回归引入点未知的问题，覆盖代码、配置、模块和输入数据。
- 假设矩阵：用于多根因并存场景，按概率、影响和验证成本排序。

## Workflow
1. **固定问题边界**：明确现象、影响范围、触发条件与不受影响范围。
2. **收集基线证据**：复现一次，记录完整日志、时间线和环境信息。
3. **构建假设矩阵**：按概率和影响排序，先验证高价值假设。
4. **5-Why 分析**：对最可能的假设做 5 层追问，形成因果链。
5. **单变量实验**：每轮只变更一个变量，记录命令、输入、结果。
6. **二分法定位**：若假设矩阵穷尽仍未定位，切换到二分法。
7. **负结果留痕**：对被证伪假设记录"为何不成立"，避免重复试错。
8. **最小失败范围**：把失败定位到最小可复现输入、模块、文件、测试或设备阶段。
9. **Repair Note**：修复前记录要保留的通过项、要重跑的最小失败项、回退锚点和风险。
10. **根因收敛与复验**：给出根因证据链，执行修复前后对比验证。
11. **失败升级策略**：同类实验连续失败时，回到假设矩阵重排优先级。

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
git bisect start
git bisect bad HEAD
git bisect good <last_good_commit>
rg -n "error|fatal|panic|timeout|reset" <log-or-src>
journalctl --since "1 hour ago" --priority=err
ss -tlnp | grep <port>
openocd -f <interface.cfg> -f <target.cfg>
arm-none-eabi-gdb <elf> -ex "target remote :3333"
```

## Evidence Template
```md
- Repro Baseline:
  - 环境 / 复现步骤 / 复现率:
- Hypothesis Matrix:
  | # | 假设 | 概率 | 验证方式 | 结果 |
  |---|------|------|---------|------|
  | 1 | ... | 高 | ... | pass/fail |
- 5-Why Chain: Why -> 证据 -> 下一层 Why -> 根因
- Experiment #n: 变量 / 命令 / 结果
- Negative Findings:
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
- 至少有一条被证伪假设的记录。
- 修复记录必须包含 failed scope、preserved passing scope、minimal rerun 和 rollback anchor。
- 修复结论必须包含"复现 -> 修复 -> 回归"三段证据。
- 若根因仍不确定，必须显式标记为 `needs-fix`，禁止"疑似已修复"式结论。
- 5-Why 链必须每层有证据支撑。
- 使用二分法时必须记录每步 good/bad 判定依据。
- AI 工具/CLI 行为异常不得先归因实现 bug；必须固定复现、对照文档版本、追到源码或配置决策点，并用 git log/blame 建时间线。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "大概知道问题在哪" | 直觉需要实验验证 | 按假设-实验-证伪记录时间线 |
| "改一处好了不用深究" | 表面修复会复发 | 完成复现、修复、回归三段证据 |
| "偶现不好复现" | 偶现仍是缺陷 | 标记 `needs-fix` 并固化触发条件 |
