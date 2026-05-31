---
name: adk-memory-curator
description: 记忆整理与候选治理，审计 memories、AGENTS、归档、session 总结和决策记录，生成可审查 memory candidate
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "记忆整理"
  - "memory curator"
  - "整理 memory"
  - "记忆审计"
  - "长期记忆候选"
  - "memory candidate"
  - "清理记忆"
non_triggers:
  - "只做任务复盘"
  - "直接写入 memory"
inputs:
  - memories、AGENTS、归档、session wrap、日报、研究笔记、排障结论、决策记录
outputs:
  - 记忆整理报告、候选列表、提升/归档/丢弃建议、风险和人工确认项
constraints:
  - 默认 report-only
  - 不静默改写 memories、AGENTS 或长期规则
  - 候选必须引用证据并脱敏
---

# adk-memory-curator

## Goal
- 周期性整理可持久化知识源，区分 stable memory、project rule、archive-only 和 noise。
- 生成可审查候选，而不是直接写长期记忆。

## Prerequisites
- 用户要求整理、审计、清理或提升记忆。
- 已确认读取范围和禁止路径。
- 已明确输出是报告、候选，还是后续人工确认后的写入任务。

## Workflow
1. 盘点来源：memories、AGENTS、archive、session wrap、daily summary、research note、decision record。
2. 去噪脱敏：移除 secrets、完整聊天、临时日志、一次性 TODO 和过期状态。
3. 分类：personal preference、project fact、workflow rule、lesson、archive-only、drop。
4. 冲突检查：标记 stale、duplicate、supersedes、conflicts_with。
5. 生成候选：每条含 scope、risk、confidence、evidence、last_verified、write_route。
6. 人工门禁：高风险候选必须 requires_user_confirmation。
7. 输出报告：只给建议和候选，不直接写 memory。

## Commands
```bash
rtk rg -n "memory|candidate|AGENTS|archive|decision|lesson" <repo>
rtk rg -n "api[_-]?key|token|secret|password|PRIVATE KEY" <candidate-path>
```

## Evidence Template
```md
- Source Scope:
- Source Counts:
- High Signal Findings:
- Duplicate/Stale Findings:
- Memory Candidates:
  | Scope | Candidate | Evidence | Risk | Confidence | Write Route |
  |---|---|---|---|---|---|
- Archive-only Items:
- Drop/Review Items:
- Gate Result: pass / needs-fix
```

## Quality Gate
- 候选必须说明“下次同类任务为何会用到”。
- 不得保存完整聊天记录、密钥、隐私原文或一次性噪声。
- 写入长期 memory 前必须有人工确认和回滚路径。
