---
name: adk-context-compress-handoff
description: 上下文压缩与会话接力，区分 stable/dynamic/evidence/excluded context，生成可恢复摘要、下一步和风险边界
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "上下文压缩"
  - "会话接力"
  - "恢复提示"
  - "压缩前处理"
  - "context preflight"
  - "resume prompt"
  - "90秒模板"
non_triggers:
  - "只做当前会话总结"
  - "只写日报"
  - "直接写长期 memory"
inputs:
  - 当前目标、已完成动作、证据路径、未决阻塞、风险、下一步、无效旧目标
outputs:
  - 恢复摘要、resume prompt、证据索引、下一步、excluded context 和 memory/archive 候选
constraints:
  - 不保存完整聊天记录或敏感原文
  - 不静默写入长期 memory
  - 压缩结果不能替代原始证据路径
---

# adk-context-compress-handoff

## Goal
- 在长会话、上下文压力或目标切换前生成可恢复、可审计、低噪音的 handoff。
- 防止过期目标、失败假设和敏感材料混入下一轮 active context。

## Prerequisites
- 当前任务已有可陈述的最新目标、验证状态和下一步。
- 已知道哪些原始证据路径可回读。
- 已识别需要排除的旧计划、错误事实或敏感内容。

## Workflow
1. 确认最新目标：记录 latest goal，列出 invalidated goals。
2. 分层压缩：stable、dynamic、evidence、excluded 分开写。
3. 证据索引：命令、路径、结果摘要和回退条件必须可追溯。
4. 风险与阻塞：列出 unresolved blockers、residual risks、manual approval points。
5. 下一步：给出最多 3 个优先动作和第一条建议命令。
6. 记忆边界：长期规则只输出 candidate，不直接写 memory 或 AGENTS。
7. 恢复提示：生成新会话可直接粘贴的 resume prompt。

## Evidence Template
```md
- Latest Goal:
- Invalidated Goals:
- Stable Context:
- Dynamic Context:
- Evidence:
- Excluded Context:
- Open Blockers:
- Next Actions:
- Resume Prompt:
- Memory Candidates:
- Archive Candidates:
- Gate Result: pass / needs-fix
```

## Quality Gate
- 必须包含 latest goal、next actions、raw evidence 和 fallback condition。
- excluded context 不得重新进入 active instructions。
- 不能把压缩摘要当成完成证据；必须保留原始路径或命令。
- 涉及长期提升时必须转交 memory/archive 治理。
