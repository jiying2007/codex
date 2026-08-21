---
name: adk-repo-drift-remediation
description: 仓库漂移治理，面向全仓偏离、冗余、残留、边界不清、文档代码不一致和提交前质量收口
version: 1.1.0
last_updated: 2026-07-07
triggers:
  - "仓库漂移"
  - "全仓漂移"
  - "repo drift"
  - "全面检查"
  - "残留清理"
  - "边界不清"
  - "文档代码不一致"
  - "全仓治理"
  - "提交前质量收口"
non_triggers:
  - "单点 bug 修复"
  - "单文件小改"
inputs:
  - AGENTS、README、manifest、docs、测试入口、dirty worktree、check 输出、用户目标
outputs:
  - 源事实总结、问题地图、风险排序、修复建议、验证结果和剩余风险
constraints:
  - 不回退或删除用户改动，除非用户明确要求
  - 先建立 issue map，再做修复
  - 避免无关格式化和大范围 churn
---

# adk-repo-drift-remediation

## Goal
- 对全仓漂移、冗余、残留、边界不清和文档/行为不一致做系统化治理。
- 在修复前先明确源事实和风险排序，避免“清理”变成破坏性重构。

## Prerequisites
- 用户请求的是仓库级检查、治理、清理、收口或质量整顿，而不是单点修复。
- 已读取当前 AGENTS、README、manifest、docs 和主要检查入口。
- 已确认工作区已有改动归属，不能覆盖用户改动。

## Workflow
1. 建立源事实：当前目标、非目标、成功标准、检查命令和维护约定。
2. 扫描漂移：目标漂移、架构边界、重复文档、残留脚本、生成物、source/live drift、测试缺口和 overview freshness。
3. 风险分级：按 blocker/major/minor 或 P0/P1/P2 排序。
4. 制定修复包：只修本轮范围内、证据明确、可验证的问题。
5. 串行处理共享触点：manifest、root config、lockfile、CI、schema、发布脚本。
6. 定向验证：先跑相关检查，再跑总门禁。
7. 收口：列出已修、未修、保留原因、剩余风险和下一步。

## Commands
```bash
rtk git status --short
rtk rg -n "TODO|FIXME|deprecated|legacy|stale|archive|manifest|registry" <repo>
rtk bash scripts/check.sh
rtk bash scripts/doctor.sh --scope all
```

## Evidence Template
```md
- Declared Target:
- Sources of Truth:
- Issue Map:
  | ID | Finding | Severity | Evidence | Action |
  |---|---|---|---|---|
- Fixed:
- Intentionally Left:
- Validation:
- Residual Risk:
- Gate Result: pass / needs-fix
```

## Quality Gate
- 必须先输出问题地图，再进入大范围修复。
- 项目 overview 若作为长期上下文，必须记录 source_hash、generated_block_hashes、stale_reasons 和 raw_fallback；不得用过期 overview 替代原始证据。
- 不得删除历史材料或用户改动，除非有明确授权和替代证据。
- 共享配置/manifest/lockfile 修改必须升级验证。
- 完成声明必须说明剩余风险和未处理项。
