---
name: adk-parallel-agent-governance
description: 并行子代理治理，定义任务分片、scope_write、冲突矩阵、等待和整合验证
version: 1.0.0
last_updated: 2026-05-18
triggers:
  - "并行 agent"
  - "多 agent"
  - "子代理"
  - "并行施工"
  - "并行调度"
  - "parallel"
  - "多任务并行"
non_triggers:
  - 单文件小修
  - 根因未明且任务无法独立拆分
inputs:
  - 任务包、读写范围、依赖关系、共享文件、验证命令
outputs:
  - 并行准入结论、子代理任务包、冲突矩阵、整合顺序和最终验证
constraints:
  - 禁止两个子代理修改同一文件或同一 shared contract
  - 子代理越界必须停止并上报
  - 子任务完成不等于整体完成
---

# adk-parallel-agent-governance

## Goal
- 将并行子代理从临时调度变成可审计、可整合、可验证的 adk 原生流程。
- 降低对 Superpowers `dispatching-parallel-agents` 和 `subagent-driven-development` 的默认依赖。
- 通过明确 ownership 和冲突矩阵防止并行写入造成返工。

## Prerequisites
- 已有 `adk-task-breakdown` 输出的任务包。
- 每个候选任务都有独立目标、scope_write、scope_read 和验证命令。
- 已识别 shared contract、schema、根配置、CI、依赖文件和应用总入口。

## 并行准入

| 条件 | 结论 |
|---|---|
| 2 到 4 个任务、写入范围不重叠、验证可独立运行 | 可并行 |
| 涉及同一 shared contract/schema/root config | 默认串行 |
| 根因未明或修复可能互相影响 | 先调试收敛 |
| 任务需要不同 worktree 隔离 | 先切到 `adk-worktree-governance` |

## Workflow
1. **准入判断**：给出 Parallel Suitability: yes/no 和理由。
2. **冻结共享边界**：列出禁止并行写入的文件、contract、schema 和根配置。
3. **显式调度门禁**：高风险、写入型、安全、发布或生产相关子代理不得只靠自动触发；必须声明目标、权限/写入边界、`must_not_touch`、停止条件和报告格式。
4. **生成任务包**：每个子任务包含目标、scope_write、scope_read、验证命令、停止条件。
5. **定义子代理提示**：使用 `templates/planning/worker-contract.md` 或等价结构，提示必须自包含，说明不独占代码库且不得回滚他人改动。父 Agent 只能补充 scope、evidence、output 和 integration 约束，不得改写用户原始任务意图。
6. **调度执行**：优先并发运行独立任务；阻塞任务保留在主线程。
7. **等待与收集**：使用平台子代理等待语义，收集 DONE/BLOCKED/NEEDS_CONTEXT。
8. **整合审查**：检查文件冲突、逻辑依赖、测试覆盖和文档一致性。
9. **最终验证**：运行整体验证，不能只依赖子任务验证。
10. **收口报告**：输出 merge order、剩余风险和 fallback 使用情况。

## Task Package Template
```md
[parallel-task]
id:
goal:
owner:
scope_write:
scope_read:
must_not_touch:
dependencies:
verification_commands:
blocked_conditions:
expected_output:
handoff_summary_required: yes
report_schema: DONE|BLOCKED|NEEDS_CONTEXT + verified_facts + inferences + evidence + changed_files + verification + risks
```

完整嵌入式全栈任务包模板：`references/parallel-worktree-task-package.md`。
通用 worker 契约模板：`templates/planning/worker-contract.md`。
子任务完成后使用 `references/subagent-review-checklist.md` 做 scope、验证和整合审查。

## Commands
```bash
# 查看候选任务写入范围
git diff --name-only

# 扫描共享触点
rg -n "contract|schema|shared|router|entry|package.json|lockfile" .

# 最终整体验证
<project-test-command>
```

## Failure Handling
- 子代理需要修改 scope_write 外文件时，暂停整合并重新拆分任务。
- 出现同文件冲突时，停止并行写入，转为主线程整合。
- 子代理 BLOCKED 时，先判断是上下文不足、计划错误还是任务过大。
- 最终验证失败时，不得把责任外包给子任务，主线程负责收敛。

## Quality Gate
- 必须输出并行适用性结论。
- 每个子任务必须有独立验证命令和明确 `must_not_touch`。
- 每个子任务必须声明 primary_skill、report_schema 和冲突处理策略。
- 高风险子代理必须通过显式调度门禁，不能只依赖自动触发或隐式权限。
- 所有子任务结束后必须有统一整合验证。
- 任何越界写入、共享契约变更或根配置变更都必须重新审批。
- 最终报告必须区分子任务完成和整体完成。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "多 agent 会更快" | 冲突会抵消并行收益 | 先做准入和冲突矩阵 |
| "子代理已经完成了" | 子任务完成不是集成完成 | 主线程必须最终验证 |
| "大家都可以改测试" | 测试也是共享契约的一部分 | 明确测试文件 ownership |
