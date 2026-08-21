---
name: adk-adr-writer
description: 产出 Architecture Decision Record 并固化技术决策
version: 1.1.0
last_updated: 2026-05-06
triggers:
  - "写ADR"
  - "架构决策"
  - "决策记录"
non_triggers:
  - 临时性小修补
inputs:
  - 候选方案、约束、风险
outputs:
  - ADR 文档草稿
constraints:
  - 必须包含 trade-off 和 rejected options
---

# adk-adr-writer

## Goal
- 形成可追溯的架构决策记录，避免"口头拍板"。
- 每个 ADR 解决一个核心问题，提供决策上下文、备选方案和后果分析。

## Prerequisites
- 明确决策范围（一个 ADR 只解决一个核心问题）。
- 收集至少 2 个可行候选方案与现实约束。
- 确认决策参与方和最终拍板人。

## ADR 编号规则
- 格式：`ADR-NNN`，三位数字，零填充，全局递增。
- 存放路径：`docs/adr/ADR-NNN-<slug>.md`
- Slug 规则：小写英文短横线连接，如 `ADR-001-rtos-selection.md`
- 查询已有编号：
```bash
ls docs/adr/ADR-*.md 2>/dev/null | sort -t'-' -k2 -n | tail -5
```
- 新 ADR 编号 = 已有最大编号 + 1。

## Workflow
1. **定义问题陈述**：背景、目标、非目标、成功标准。
2. **收集候选方案**：至少 2 个方案，明确每个方案的技术栈、依赖与约束。
3. **构建决策矩阵**：按维度（复杂度、性能、成本、迁移难度、团队熟悉度）逐项对比打分。
4. **记录 rejected options**：说明不选原因与适用边界。
5. **写明决策后果**：短期收益、长期债务、触发重评条件。
6. **绑定验证计划**：如何证明该决策成立，验证指标与时间窗。
7. **输出 ADR 文档**：按模板填充，确保四段核心内容完整。

## Commands
```bash
# 查看已有 ADR 编号
ls docs/adr/ADR-*.md 2>/dev/null | sort -t'-' -k2 -n | tail -5

# 创建新 ADR
next_num=$(printf "%03d" $(($(ls docs/adr/ADR-*.md 2>/dev/null | wc -l) + 1)))
echo "Next ADR number: ADR-${next_num}"

# 校验 ADR 完整性
grep -c "## Context\|## Decision\|## Alternatives\|## Consequences" docs/adr/ADR-*.md
```

## Decision Matrix Template
```md
| 维度 | 权重 | 方案A | 方案B | 方案C |
|------|------|-------|-------|-------|
| 实现复杂度 | 20% | 低(3) | 中(2) | 高(1) |
| 运行性能 | 25% | 中(2) | 高(3) | 高(3) |
| 团队熟悉度 | 15% | 高(3) | 低(1) | 中(2) |
| 维护成本 | 20% | 低(3) | 中(2) | 高(1) |
| 迁移难度 | 20% | N/A | 低(3) | 高(1) |
| **加权总分** | 100% | **2.8** | **2.2** | **1.6** |
```

## Evidence Template
```md
# ADR-NNN: <title>
- Status: proposed / accepted / deprecated / superseded
- Date: YYYY-MM-DD
- Deciders: <name list>
- Context:
  - 业务背景：
  - 技术约束：
  - 非目标：
- Decision: <选择的方案>
- Decision Matrix: <上表>
- Alternatives Considered:
  - 方案A: <描述> — 优势/劣势
  - 方案B: <描述> — 优势/劣势
- Rejected Options + Reasons:
  - 方案B rejected: <具体原因>
- Consequences:
  - 短期收益：
  - 长期债务：
  - 重评触发条件：
- Verification Plan:
  - 验证指标：
  - 验证时间窗：
- Rollback Trigger: <条件描述>
```

## Failure Handling
- 信息不足时输出 `needs-fix`，列出缺失字段，不进入拍板。
- 方案收益无法量化时，回退到最小可行方案并标注风险。
- 决策矩阵维度缺失时，补充维度后再继续。
- 若候选方案不足 2 个，必须补充至少一个备选方案。

## Quality Gate
- ADR 必须包含 Context/Decision/Alternatives/Consequences 四段。
- 必须有至少一个 rejected option 与对应理由。
- 验证计划与回退触发条件不可为空。
- 决策矩阵必须有至少 3 个维度和加权总分。
- 编号必须全局唯一且递增。
- Status 字段必须为 proposed/accepted/deprecated/superseded 之一。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "方案已经定了不用写" | 口头决策无法追溯，新人无法理解 why | 按模板补写 ADR，至少记录 Context/Decision/Consequences |
| "这个决策很简单" | 简单决策也可能被推翻，没有 ADR 就没有讨论基础 | 即使简单也写 ADR-简版，10 分钟即可 |
| "写了也没人看" | ADR 的读者是未来的你和新同事 | 写入 docs/adr/ 并在 PR 中引用 |

---

## 健壮性规范

- **输入验证**: 执行前校验所有必要输入是否存在且格式正确
- **重试策略**: 外部命令失败时最多重试 3 次，指数退避（1s, 2s, 4s）
- **超时控制**: 单步操作超时 30 秒，整体流程超时 300 秒
- **异常隔离**: 单个步骤失败不阻塞其他独立步骤
- **日志记录**: 关键操作记录命令、退出码、耗时
