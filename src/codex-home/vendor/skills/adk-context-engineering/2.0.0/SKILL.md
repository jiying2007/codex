---
name: adk-context-engineering
description: 规划和裁剪 Agent 任务上下文，决定稳定规则、动态证据、按需 references、摘要与 raw pointer 的加载边界。用于上下文膨胀、跨阶段/跨会话恢复、并行 Agent 隔离、信息缺失或错误上下文导致理解偏差的场景；不用于替代任务规划、代码实现或 token 治理门禁。
version: 2.0.0
last_updated: 2026-09-15
triggers:
  - 上下文工程
  - 上下文膨胀
  - 跨会话恢复
  - Agent 理解偏差
  - 并行上下文隔离
  - context planning
non_triggers:
  - 直接写代码
  - 单纯运行测试
  - 只做 token 配额治理
inputs:
  - 当前任务目标和阶段
  - 稳定规则与动态证据来源
  - 可用 Skill/reference/tool surface
outputs:
  - 上下文加载计划
  - 摘要与 raw pointer 策略
  - 缺失/噪音/隔离风险
constraints:
  - progressive disclosure 优先
  - 稳定身份规则与动态证据分离
  - 不因压缩丢失高风险原始证据的可追溯 pointer
  - 不把临时 references 固化为长期事实
---

# adk-context-engineering

## Goal
为当前任务生成最小充分、可恢复、可追溯的 context policy，而不是把所有可用信息一次性装入模型。

## Use When
- 当前上下文过大、互相冲突或含大量无关历史。
- 长任务需要 checkpoint / resume / handoff。
- 并行 Agent 需要共享 contract 与私有工作上下文隔离。
- 模型因缺失关键事实、加载错误 reference 或过度压缩而反复误解任务。

若任务只是“执行既有计划”“写代码”“跑测试”，且没有 context 边界问题，本 Skill 只作为 supporting capability，不抢 primary。

## Prerequisites
- 明确当前 objective、phase、risk level 与候选 primary Skill。
- 知道哪些输入是 authoritative facts，哪些只是假设、历史摘要或按需 reference。

## Context Policy
1. **Stable core**：只保留长期稳定的 role/rules/contract；优先 cache-friendly 内容。
2. **Task state**：目标、当前阶段、done/open/blocker、candidate identity。
3. **Evidence**：先摘要与 evidence ref；高风险/争议结论保留 L3/raw pointer，不默认复制全文。
4. **On-demand capability**：只有触发后才加载 Skill body、reference、tool schema。
5. **Handoff isolation**：子任务只接收 objective、必要 facts/contract、scope、evidence refs；不默认继承完整聊天历史。

## Workflow
1. 识别当前决策真正需要的事实、contract 和 evidence。
2. 将信息标记为 `always | phase | on-demand | raw-pointer | exclude`。
3. 删除重复、过期、低价值动态输出；冲突信息保留来源与 freshness，不静默覆盖。
4. 为长任务写 summary-first checkpoint；raw output 仅保留 opaque/path pointer 和 retention decision。
5. 并行/跨 Agent 时使用 `schemas/agent-handoff-v1.schema.json`，限制 scope 与 permission，不传播无关 history。
6. 验证恢复能力：新执行者只读取摘要和 refs 应能知道目标、已确认事实、未决问题和下一步；若不能，补缺失信息而不是扩大所有上下文。

## Failure / Abstain
- 权威来源不明确：输出 `needs-evidence`，不要用历史摘要替代事实。
- 压缩会让 blocker、permission、candidate identity 或原始证据不可追溯：保留 pointer 并拒绝继续压缩。
- 问题实质是 routing/token-policy：分别交给 `adk-runtime-router` / `adk-token-context-governance`。

## Quality Gate
- 关键信息均有 provenance 或明确 assumption 标记。
- dynamic/raw 内容不进入 always-loaded core。
- handoff 不扩大权限，不复制无关完整历史。
- 恢复摘要包含 objective、state、blockers、evidence refs、next action。
- “质量提升”必须由具体误解/缺失样例或 eval 证明，不接受主观描述。

## Evidence Template
```md
- Objective / Phase:
- Context decisions:
  - always:
  - phase:
  - on-demand:
  - raw-pointer:
  - excluded:
- Missing / conflicting evidence:
- Handoff boundary:
- Recovery check: pass | needs-evidence
- Efficiency observation: <optional; not a quality KPI>
```
