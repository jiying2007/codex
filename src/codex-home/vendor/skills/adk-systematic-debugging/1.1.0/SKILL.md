---
name: adk-systematic-debugging
description: 系统化调试流程，面向根因未明的问题定位与修复验证
version: 1.1.0
last_updated: 2026-05-06
triggers:
  - "调试"
  - "排查问题"
  - "故障定位"
  - "代码有问题"
  - "诊断循环"
  - "根因排查"
non_triggers:
  - 已有明确根因且只需执行已确认修复
  - 纯文档或命名修改
inputs:
  - 现象描述、触发条件、日志与监控证据
outputs:
  - 假设矩阵、实验记录、根因结论与修复验证证据
constraints:
  - 先做只读诊断，未经确认不做破坏性操作
  - 单轮仅验证一个假设并记录正负结果
  - 没有证据链不得给出根因结论
---

# adk-systematic-debugging

## Goal
- 用最小实验成本定位根因，并输出可复现、可验证、可回归的修复路径。

## Prerequisites
- 固定问题复现条件（版本、环境、输入、时间窗）。
- 预先定义观测指标与日志采集方式。

## 调试方法论

### 5-Why 分析法
逐层追问"为什么"，从表象挖到根因：
```
现象: 设备启动后 30 秒死机
Why 1: 看门狗超时 → 为什么超时？
Why 2: 主循环阻塞 → 为什么阻塞？
Why 3: SPI 传输卡死 → 为什么卡死？
Why 4: DMA 通道被占用 → 为什么被占用？
Why 5: 中断优先级配置错误 → 根因
```
规则：每层 Why 必须有证据支撑，不能凭猜测。

### 二分法定位
将问题空间对半缩小，快速收敛：
- **代码二分**：`git bisect` 定位引入问题的 commit
- **配置二分**：逐步禁用配置项，定位问题配置
- **模块二分**：逐步注释/绕过模块，定位问题模块
- **数据二分**：缩小输入范围，定位问题数据

## Workflow
1. **固定问题边界**：明确现象、影响范围、触发条件与不受影响范围。
2. **收集基线证据**：复现一次，记录完整日志、时间线和环境信息。
3. **构建假设矩阵**：按概率和影响排序，先验证高价值假设。
4. **5-Why 分析**：对最可能的假设做 5 层追问，形成因果链。
5. **单变量实验**：每轮只变更一个变量，记录命令、输入、结果。
6. **二分法定位**：若假设矩阵穷尽仍未定位，切换到二分法。
7. **负结果留痕**：对被证伪假设记录"为何不成立"，避免重复试错。
8. **根因收敛与复验**：给出根因证据链，执行修复前后对比验证。
9. **失败升级策略**：同类实验连续失败时，回到假设矩阵重排优先级。

## Commands
```bash
# Git bisect 二分定位
git bisect start
git bisect bad HEAD
git bisect good <last_good_commit>
# 测试当前 commit，然后 git bisect good/bad

# 日志分析
tail -f /var/log/syslog | grep -i "error\|fatal\|panic"
journalctl --since "1 hour ago" --priority=err

# 进程/资源排查
top -b -n 1 | head -20
strace -p <pid> -e trace=write 2>&1 | head -50
lsof -p <pid> | head -20

# 网络排查
ss -tlnp | grep <port>
tcpdump -i any port <port> -c 100 -w /tmp/capture.pcap

# 嵌入式调试
openocd -f <interface.cfg> -f <target.cfg> &
arm-none-eabi-gdb <elf> -ex "target remote :3333"
```

## Evidence Template
```md
- Repro Baseline:
  - 环境: OS/版本/硬件
  - 复现步骤: 1. ... 2. ...
  - 复现率: X/Y 次
- Hypothesis Matrix:
  | # | 假设 | 概率 | 验证方式 | 结果 |
  |---|------|------|---------|------|
  | 1 | ... | 高 | ... | ✅/❌ |
- 5-Why Chain:
  - Why 1: ... → 证据: ...
  - Why 2: ... → 证据: ...
  - Why 5: ... → 根因
- Experiment #n (single variable):
  - 变量: ...
  - 命令: ...
  - 结果: ...
- Negative Findings:
  - ❌ 假设 X 不成立，因为...
- Root Cause Chain:
  - 根因: ...
  - 证据: [e1, e2, e3]
- Fix Verification:
  - 修复前: <现象>
  - 修复后: <现象消失>
  - 回归测试: pass/fail
```

## Failure Handling
- 连续两轮实验无信息增量时，必须重排假设矩阵。
- 复现不稳定时先固化环境，不继续追加修复改动。
- 5-Why 链中断时，补充证据后再继续，不跳层。
- 二分法结果矛盾时，检查测试用例是否正确。

## Quality Gate
- 调试记录必须包含时间线、实验步骤、观察结果和结论映射。
- 至少有一条被证伪假设的记录。
- 修复结论必须包含"复现 -> 修复 -> 回归"三段证据。
- 若根因仍不确定，必须显式标记为 `needs-fix`，禁止"疑似已修复"式结论。
- 5-Why 链必须每层有证据支撑。
- 使用二分法时必须记录每步 good/bad 判定依据。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "我大概知道问题在哪" | "大概"是调试最大的敌人，直觉需要实验验证 | 按 SKILL.md 流程假设-实验-证伪，记录完整时间线 |
| "改了一处就好了不用深究" | 表面修复掩盖根因，问题必然复发 | 必须完成"复现 -> 修复 -> 回归"三段证据链 |
| "这个问题偶现不好复现" | 偶现不代表不存在，放过的 bug 会在最坏时机爆发 | 标记为 `needs-fix` 并记录触发条件，禁止"疑似已修复" |
