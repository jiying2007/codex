---
name: adk-knowledge-archive
description: 知识归档与长期沉淀，将高价值总结、研究、排障、决策和会话材料写成脱敏、可检索、可治理的归档候选
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "知识归档"
  - "长期沉淀"
  - "保存到 archive"
  - "保存到 docs/archive"
  - "日报归档"
  - "会话总结归档"
  - "排障结论归档"
  - "研究笔记归档"
non_triggers:
  - "归档治理"
  - "归档检查失败"
inputs:
  - 源文件、当前会话摘要、日报、研究笔记、排障结论、决策记录、外部材料摘要
outputs:
  - 脱敏 Markdown 归档候选、topic、source provenance、验证记录、后续 memory/AGENTS 候选
constraints:
  - 不归档 secrets、auth、cache、runtime state、完整聊天记录
  - 不把归档内容静默提升为规则或 memory
  - 归档路径必须避开 build/control/runtime 产物
---

# adk-knowledge-archive

## Goal
- 把可复用工程知识沉淀为可检索、可审计、脱敏的归档材料。
- 与 `adk-archive-governance` 分工：本 skill 创建归档候选；归档治理处理 meta、registry、hash 和不合规修复。

## Prerequisites
- 用户明确要求归档、保存、沉淀，或交付流程要求生成可审查 note。
- 已识别源内容和目标 topic。
- 已确认不包含敏感材料或已经脱敏。

## Workflow
1. 识别来源：已有文件、当前会话、日报、session wrap、research note、debug note、外部文章摘要。
2. 选择 topic：session-wrap、daily-summary、research-notes、debug-notes、external-articles 或 kebab-case 主题。
3. 脱敏和去噪：删除 secrets、token、私有端点、完整原始日志、临时过程噪声。
4. 保留可复用信息：背景、约束、决策、验证、风险、下一步和 provenance。
5. 生成归档候选：Markdown 内容必须可单独阅读。
6. 交给归档入口或项目约定；没有入口时报告 blocker，不自造长期路径。
7. 若应影响未来行为，只输出 memory/AGENTS 候选，转交 `adk-memory-curator`。
8. 若源材料来自外部网页、论文或第三方仓库，记录 source URL、retrieved_at 和版权边界。
9. 若归档会替代旧笔记，先标注 supersedes 候选，不直接删除旧归档。

## Evidence Template
```md
- Source:
- Topic:
- Archive Candidate Path:
- Sanitization:
- Provenance:
- Verification:
- Memory Candidate: yes / no
- Gate Result: pass / needs-fix / blocked
```

## Quality Gate
- 归档必须有 source、captured_at 或 last_verified。
- 内容必须脱敏且可复用。
- 不得写入 build、control、runtime、cache 或 credential 路径。
- 归档后应能被 archive governance 检查。
