---
name: adk-systematic-debugging
description: "用于根因不明问题的复现、单变量实验、sanitizer 取证与回归；不用于跳过取证猜修复或替代性能基准。"
version: 1.2.7
last_updated: 2026-11-20
triggers:
  - "调试"
  - "排查问题"
  - "故障定位"
  - "代码有问题"
  - "诊断"
  - "根因排查"
  - "问题排查"
  - "定位根因"
  - "真实问题排查"
  - "根因未明"
  - "失败定位"
  - "sanitizer 取证"
  - "UBSan 取证"
non_triggers:
  - 已有明确根因且只需执行已确认修复
  - 纯文档或命名修改
inputs:
  - 现象描述、触发条件、日志与监控证据
outputs:
  - 假设矩阵、实验记录、repair note、根因结论与修复验证证据
constraints:
  - 先只读，破坏性操作须获准
  - 每轮一假设，记正负结果
  - 无证据链不下根因结论
  - 未缩小失败范围不盲重试/扩改
---

# adk-systematic-debugging

固定版本/环境/输入/时间窗、指标/日志/命令/输出/期望红。

## Workflow
1. 固定现象/影响/触发，建最小红信号；困难/偶现、二分或重跑先读 `references/tight-feedback-loop.md`。无安全复现记 blocker；替代信号标 `proxy evidence`。
2. 因果明确记复现/原因/修复，不虚构假设/负结果；多根因按概率/影响/证伪成本排序。强现象链用 5-Why，逐层有证据，到可验证根因即停；范围大、回归点未知或假设穷尽时二分代码/配置/模块/输入，记 good/bad，矛盾先核信号。
3. 单变量实验缩范围，留时间线、命令/输入、观察/反例/不可重复路径。E2/E3 正确性/安全关键前提证伪，同身份证据可复用，无需增 Agent。
4. **Repair Note**：failed scope、preserved passing scope、minimal rerun、rollback anchor、风险、root cause status。格式失败修 schema/模板；语义失败固定断言；并行只 reopen 失败项；设备不稳固化环境，保留通过产物。
5. 映射观察与根因，同条件旧版红→新版绿并补回归，核受影响通过路径。两轮无新信息则停，核信号覆盖/测量失真与假设；5-Why 断链补证，未收敛记 `needs-fix`。

## 取证
- 内存/UB/竞争：`references/sanitizer-validation.md` 核目标/runtime、已知缺陷对照；UBSan 报警即使 exit 0 也失败。
- UBIFS/SquashFS、Buildroot/Autotools、Wi-Fi/DNS/MQTT、SPI/QSPI、FOC：`references/embedded-diagnosis-branches.md` 选证据，不替代 BSP/TRM/现场。
- AI 工具/CLI：核文档版本，追源码/配置决策点，以 git log/blame 建时间线归因。

## Commands
```bash
rg -n "error|fatal|panic|timeout|reset" <log-or-src>
```
transport/debugger 只用已核实只读入口；交付适用性、原始证据/结果，未跑记 `not-run`。
