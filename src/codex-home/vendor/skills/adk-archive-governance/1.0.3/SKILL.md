---
name: adk-archive-governance
description: "用于检查和修复现有归档的元数据、topic、hash 与安全问题；不负责新建知识笔记或代替知识候选的正式审核。"
version: 1.0.3
last_updated: 2026-11-04
triggers:
  - "归档治理"
  - "归档检查"
  - "归档修复"
  - "archive-check"
  - "meta v2"
  - "topic 未登记"
  - "归档不合规"
  - "归档元数据"
non_triggers:
  - "新建一篇归档笔记"
  - "只查询历史归档"
inputs:
  - archive 根目录、registry、meta、归档检查输出、目标 topic、敏感信息规则
outputs:
  - 归档问题分类、修复计划、变更清单、验证命令和剩余风险
constraints:
  - 不删除历史材料，除非用户明确要求或已有安全替代
  - 不把项目特定事实提升为全局规则
  - 不归档 secrets、raw sessions、cache、runtime state
---

# adk-archive-governance

## Goal
- 治理 `docs/archive` 的可检索性、可审计性和安全边界。
- 修复 meta、topic、hash、重复与敏感信息问题。

## Prerequisites
- 已定位归档入口。
- 已有归档检查输入或问题文件。
- 仅治理已有归档。

## Workflow
1. 读取 archive README、registry/schema 和检查脚本说明。
2. 运行或规划 archive check，收集错误列表。
3. 分类问题：missing meta、bad filename、topic missing、hash mismatch、duplicate、sensitive、stale open item。
4. 最小修复：补 meta、登记 topic、更新 hash、规范文件名、标记 superseded。
5. 安全审查：排除 raw sessions、auth、cache、logs、private endpoints 和 secrets。
6. 查询验证：对受影响 topic 做 targeted archive search。
7. 最终运行 archive check 和项目总检查。

## Commands
```bash
rtk rg -n "archive|meta|topic|registry|content_sha256" docs/archive scripts
rtk bash scripts/check-memory-governance.sh
# 归档专用检查器由目标项目声明；缺失则 blocked。
```

## Evidence Template
```md
status: pass | needs-fix | blocked
issues:
- path:
  class:
  action:
changed:
- path:
checks:
- archive-check:
- archive-search:
remaining:
```

## Quality Gate
- 每个归档 Markdown 必须有合规 meta 或明确不归档决策。
- superseded 条目必须有 `superseded_by`。
- topic registry 必须能解释新增 topic。
- 修复后必须跑 archive check 或说明无法执行的原因。
