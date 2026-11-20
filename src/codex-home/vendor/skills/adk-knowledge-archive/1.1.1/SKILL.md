---
name: adk-knowledge-archive
description: "用于新建脱敏的研究、排障与决策归档候选并登记证据指针；不处理已有归档的元数据修复，也不替代发布审核。"
version: 1.1.1
last_updated: 2026-11-20
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
  - 不归档 secrets、raw session、auth、runtime state、cache 或完整聊天内容
  - 不自动发布长期规则，也不得编造来源、验证或目标路径
---

# adk-knowledge-archive

## Goal
把有实际复用价值的排障、研究与决定整理为可检索的脱敏记录。已有归档的 meta、topic 和 hash 修复由 `adk-archive-governance` 负责。

## Workflow
1. 定位来源和真实 topic，按读者需要提炼已核实背景、结论、证据指针及适用边界。
2. 排除敏感原文、凭据、完整会话、临时日志和一次性噪声。没有可复用经验时不生成凑数文档。
3. 目标目录和 registry 遵循受管项目约定；路径不明标 `blocked`，不编造文件、topic 或更新时间。
4. 仅在用户或已有流程明确要求时输出可写入 Markdown；后续指导规则只生成 memory/AGENTS 候选，不自动提升为全局规则。
5. 如取自外部材料，记录确切 source、获取日期和版权边界；已有归档使用链接/注明 supersedes，不自行删除。

## Minimal Evidence
`Source / Topic / Finding / Validation Pointer / Boundaries / Sanitization / Candidate Path / Status`

## Quality Gate
- 归档内容能独立阅读且保留事实来源；没有证据写“未核实”，不编造 `last_verified`。
- 不写入 build、runtime、cache、control、credential 路径。
- 文档保真：保留数字、技术术语、否定和条件、原始证据指针，不为自然度误改结论。
