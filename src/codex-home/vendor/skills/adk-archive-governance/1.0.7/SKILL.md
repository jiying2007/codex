---
name: adk-archive-governance
description: "用于只读检查现有归档的元数据、topic、hash 与安全问题，提出修复计划并交接既有实施者；不负责新建知识笔记或代替知识候选的正式审核。"
version: 1.0.7
last_updated: 2026-11-20
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
只读定位 `docs/archive` 的 meta、topic、hash、重复与安全问题，提出最小修复并核验实施回执。

## Prerequisites
- 已定位归档入口。
- 已有归档检查输入或问题文件。
- 仅治理已有归档。

## Workflow
1. 读取 archive README、registry/schema 和检查脚本说明。
2. 运行或规划 archive check，收集错误列表。
3. 分类问题：missing meta、bad filename、topic missing、hash mismatch、duplicate、sensitive、stale open item。
4. 提出候选 patch/修复 task：补 meta/topic、规范文件名、标记 superseded。hash mismatch 先保留旧 hash、实测 hash 和当前内容，核对可信原件及已批准变更；仅确认授权编辑后交实施者重算，未知差异保持 needs-fix。
5. 安全审查：排除 raw sessions、auth、cache、logs、private endpoints 和 secrets。
6. 交接既有已授权的实施 owner/步骤，带范围、候选、原任务授权引用和验证；不重复索取已有授权。本 Skill 只读，不直接写入；缺实施权限/owner 则保留候选并标 blocked。
7. 收回实施回执，核受影响 topic 的 targeted archive search、archive check 和项目总检查；未执行项如实记录。

## Commands
先核实目标仓路径与检查脚本；没有对应目录/脚本则记录 unavailable 并用已声明的目标项目入口，不假定纯 Skill 导出包包含 ADK 源码。
```bash
rg -n "archive|meta|topic|registry|content_sha256" docs/archive scripts
bash scripts/check-memory-governance.sh
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
handoff:
  implementation_owner:
  authorized_task_ref:
  candidate_patch_or_task:
  verification:
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
