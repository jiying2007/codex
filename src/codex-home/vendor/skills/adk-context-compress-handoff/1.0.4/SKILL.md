---
name: adk-context-compress-handoff
description: "用于长任务上下文压缩、跨会话恢复及交接时保存目标、证据指针和下一动作；不用于替代原始高风险证据或任务执行。"
version: 1.0.4
last_updated: 2026-11-20
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
生成可恢复、可审计的 handoff。

## Prerequisites
确认最新目标、验证状态与可回读证据；排除过期计划、错误事实、失败假设及敏感原文。

## Workflow
1. 写 latest goal / invalidated goals，分开 stable、dynamic、evidence、excluded。
2. 默认使用下方模板记录 active plan/findings/progress/attestation；仅在 ADK 源码根已确认且文件可读时，可选 `templates/context/continuity-attestation.md`。
3. 证据含命令、路径、结果与回退条件；保留 blockers、residual risks、manual approval points，不扩大权限。
4. 列仍需 Skill 的来源、内容身份（可核版本/hash；未知注明）、必要 refs、正文状态。恢复先核目标/权限；仅同来源同内容且正文完整仍在当前上下文才去重；正文被摘要/丢失或来源/内容变化则按需重读，缺必要内容记 `needs-fix`。历史“已加载”不证明有效。
5. 给出最多 3 个优先动作、第一条建议命令及可粘贴的 resume prompt；不再适用的 Skill 留在 excluded。
6. 长期规则只作 candidate，交 memory/archive 治理；不写 memory/AGENTS。

## Evidence Template
```md
- Latest Goal:
- Invalidated Goals:
- Stable Context:
- Confirmed Facts:
- State / Blockers:
- Scope / Permission:
- Active Skills: source / content identity / required refs / intact|summarized|missing|changed
- Evidence / Fallback:
- Continuity Attestation:
- Excluded Context:
- Next Actions:
- Resume Prompt:
- Memory Candidates:
- Archive Candidates:
- Gate Result: pass / needs-fix
```

## Quality Gate
- latest goal、next actions、raw evidence、fallback condition 可追溯；摘要不证明完成。
- excluded context 不进入 active instructions；只恢复当前仍需的正文和 refs。
