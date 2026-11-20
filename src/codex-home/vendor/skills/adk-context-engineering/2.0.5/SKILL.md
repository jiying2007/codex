---
name: adk-context-engineering
description: "用于上下文膨胀、跨会话恢复或并行 Agent 隔离时规划稳定规则、按需引用及证据指针；不用于直接替代任务计划、代码实现或 Token 配额门禁。"
version: 2.0.5
last_updated: 2026-11-20
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
有上下文边界问题才生成可恢复 context policy；Token 预算和专门交接分别交 `adk-token-context-governance` 与 `adk-context-compress-handoff`，避免重复总结。

## Prerequisites
明确 objective、phase、risk 与候选 primary；区分权威事实、假设、历史摘要和按需 reference。

## Context Policy
1. **Stable core**：稳定 role/rules/contract，优先 cache-friendly。
2. **Task state**：目标、phase、done/open/blocker、candidate identity。
3. **Evidence**：摘要与 refs；高风险/争议保留 L3/raw pointer。
4. **On-demand capability**：命中后加载 Skill、reference、tool schema。
5. **Handoff isolation**：只交 objective、必要 facts/contract、scope、refs，不复制完整历史。

## Workflow
1. 按当前决策将事实/contract/evidence 标为 `always | phase | on-demand | raw-pointer | exclude`；去重、去过期输出，冲突保留来源与 freshness。
2. 长任务写 summary-first checkpoint；raw output 留 pointer 与 retention decision。
3. 记录仍需 Skill 的来源、内容身份（可核版本/hash；未知注明）、必要 refs、正文状态 `intact | summarized | missing | changed`。
4. 恢复核目标/权限/内容身份；仅正文完整且身份一致才复用，summary/missing/changed 则重读；不可读记 `needs-evidence`。
5. 交接默认使用下方模板，保留目标、状态、权限、证据和下一步，不扩大权限；仅在 ADK 源码根已确认且文件可读时可选 `schemas/agent-handoff-v1.schema.json`，未校验须标明。
6. 接力核事实、未决项与 refs，只补缺项不重载历史。

## Failure / Abstain
- 来源不明记 `needs-evidence`；历史摘要不替代事实。
- 压缩丢失 blocker、permission、candidate identity 或原始证据指针时停止。
- routing/token-policy 交 `adk-runtime-router` / `adk-token-context-governance`。

## Quality Gate
- 事实有 provenance，假设明示；dynamic/raw 不进入 always-loaded core。
- 恢复摘要覆盖目标、状态、阻塞、证据与下一步；Skill 有效性按当前内容核验，不扩大权限。
- 质量提升须由误解/缺失样例或 eval 证明；本方法不证明宿主已实现自动恢复。

## Evidence Template
```md
- Objective / Phase:
- Confirmed Facts:
- State / Blockers:
- Scope / Permission:
- Active Skills: source / content identity / required refs / content state
- Evidence / Fallback:
- Next Actions:
- Context decisions: always / phase / on-demand / raw-pointer / excluded
- Missing / conflicting evidence:
- Recovery check: pass | needs-evidence
- Efficiency observation: <optional; not a quality KPI>
```
