---
name: adk-worktree-governance
description: git worktree 隔离开发治理，规范创建准入、目录、基线验证、同步、清理和禁止操作
version: 1.2.1
last_updated: 2026-08-31
triggers:
  - "worktree"
  - "工作树"
  - "隔离分支"
  - "多分支并行"
  - "外部并行规划"
  - "创建 worktree"
non_triggers:
  - 当前分支内单点小改
  - 用户明确要求不创建新工作树
inputs:
  - 基础分支、任务包、隔离原因、验证命令、清理策略
outputs:
  - worktree 方案、创建命令、基线验证、同步规则、清理与回退计划
constraints:
  - 未经用户确认不得删除 worktree 或强制删除分支
  - 不得在 worktree 间共享未提交临时状态
  - 根配置和 shared contract 默认不并行修改
  - dirty worktree、unattended automation 和 stale heartbeat 必须先做风险决策再继续
---

# adk-worktree-governance

## Goal
- 在确实需要隔离开发时，提供 adk 原生 worktree 治理流程。
- 用 ADK 原生边界覆盖 worktree 创建、验证、清理和 provenance 场景。
- 保护当前工作区的未提交改动，降低多分支并行冲突。

## Prerequisites
- 已确认当前工作区状态和是否存在用户未提交改动。
- 已明确基础分支、目标分支名、任务范围和验证命令。
- 已判断普通当前分支开发不足以满足隔离需求。
- 若由外部 planner 或子代理创建 worktree，计划 schema 已通过校验：必填字段完整、依赖合法、无环、预算和 retry budget 明确。

## 准入条件

| 场景 | 是否建议 worktree |
|---|---|
| 多个长期分支并行推进 | 是 |
| 高风险重构需要隔离验证 | 是 |
| 用户要求外部多 agent 协作 | 是 |
| 单文件修复或文档调整 | 否 |
| 依赖/lockfile/root config 变更 | 通常串行，谨慎使用 |

## Workflow
1. **检查当前状态**：记录 `git status --short`，识别未提交改动，并给出 dirty worktree decision（commit/stash/continue/defer）。
2. **确认隔离理由**：说明为什么当前分支不足以完成任务。
3. **规划目录和分支**：优先使用项目内已存在的 `.worktrees/` 或 `worktrees/`；没有时创建 `.worktrees/`。避免使用全局共享 worktree 目录，除非用户明确指定。
4. **创建前基线验证**：在当前仓库确认基础分支和测试入口。
5. **创建 worktree**：只在用户同意或任务明确要求时执行。
6. **scratch 目录隔离**：子代理 brief、review package、进度 ledger 和临时报告不得写入 `.git/`；优先使用项目内自忽略目录（例如 `.adk/tmp/`、`.worktrees/` 下任务目录或工具专属 scratch），并确认不会进入提交。
7. **最小初始化**：安装依赖或运行 setup 时记录命令和结果。
8. **执行任务**：遵守 scope_write，不修改共享 contract/root config，除非重新审批。
   - unattended automation 不得默认写入、提交、推送、发布或清理；必须有 owner approval、stop condition、rollback path 和 first-run evidence。
   - heartbeat 超过 staleness threshold 时必须 stop/replan/split，不得继续堆叠自动运行。
9. **同步和整合**：合并前回到主工作区审查 diff 和验证。
10. **清理决策**：合并、保留、创建 PR 或删除必须显式选择。

## Worktree Plan Template
```md
- Base Branch:
- Feature Branch:
- Worktree Path:
- Isolation Reason:
- Existing Dirty State:
- Dirty Worktree Decision:
- Scope Write:
- Shared Files Forbidden:
- Scratch / Ledger Path:
- Gitignore Coverage:
- Baseline Verification:
- Setup Commands:
- Merge / PR / Keep / Discard Decision:
- Cleanup Conditions:
- Automation Risk Decision:
- Heartbeat / Staleness Threshold:
```

若 worktree 与子代理并行同时出现，优先使用 `references/parallel-worktree-task-package.md` 固化 `scope_write`、`must_not_touch` 和最终整合验证。

## Commands
```bash
# 只读检查
git status --short
git branch --show-current
git worktree list

# 创建示例
git worktree add ../<repo>-<topic> -b <branch> <base-branch>

# 清理示例，必须先确认
git worktree remove <path>
```

## Failure Handling
- 当前工作区有未提交改动且会影响创建基线时，先暂停并让用户选择提交、stash 或继续当前分支。
- dirty worktree 没有明确决策、automation 缺少停止条件或 heartbeat 过期时，必须停止并重新规划。
- worktree 创建失败时，检查路径、分支名和基础分支是否存在。
- setup 失败时记录环境缺口，不得继续声明 worktree 可用。
- 合并前验证失败时，回到 `adk-systematic-debugging` 或 `adk-code-review-loop`。

## Quality Gate
- 必须记录 base branch、worktree path、feature branch 和隔离理由。
- 删除 worktree 或分支前必须有用户明确确认。
- worktree 内验证通过不代表主工作区可合并，必须回主线整体验证。
- 根配置、依赖和 shared contract 变更必须串行收口。
- 未通过计划 schema gate 的 worker/worktree 不得创建或继续执行。
- dirty worktree decision、automation risk decision 和 heartbeat/staleness threshold 缺失时，不得创建或继续执行。
- 子代理 scratch、review package 和进度 ledger 不得写入 `.git/`；若存放于工作区，必须被 `.gitignore` 覆盖或在收尾前显式排除。
- 只清理本流程创建且 provenance 明确的 worktree/scratch；无法确认来源时默认保留。
- 最终必须给出保留或清理决策。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "先建一个再说" | worktree 会增加状态面 | 先说明隔离理由 |
| "删掉临时工作树就行" | 可能删除未保存工作 | 删除前必须确认 |
| "worktree 测过就能合" | 主线可能已变化 | 回主线再验证 |
