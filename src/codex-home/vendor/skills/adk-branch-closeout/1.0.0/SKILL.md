---
name: adk-branch-closeout
description: 开发分支收尾治理，验证完成后选择本地合并、创建 PR、保留或丢弃并执行清理
version: 1.0.0
last_updated: 2026-05-18
triggers:
  - "分支收尾"
  - "开发完成"
  - "创建 PR"
  - "合并分支"
  - "收尾"
  - "结束开发分支"
  - "branch closeout"
non_triggers:
  - 仍有测试失败且未定位根因
  - 只是询问 git 概念
inputs:
  - 当前分支、基础分支、验证命令、测试结果、PR/合并目标
outputs:
  - 收尾选项、验证结论、合并或 PR 计划、清理决策与残留风险
constraints:
  - 测试或关键验证失败时不得进入合并或 PR
  - 丢弃工作必须要求明确确认
  - 不得自动删除用户未确认的分支或 worktree
---

# adk-branch-closeout

## Goal
- 在开发完成后提供结构化收尾流程，补齐 Superpowers `finishing-a-development-branch` 的 adk 等价能力。
- 先验证，再给选项，最后按用户选择执行合并、PR、保留或丢弃。
- 确保清理动作可审计、可回退，不误删用户工作。

## Prerequisites
- 已完成实现，并收集相关验证结果。
- 已知道当前分支、基础分支和是否处于 worktree。
- 已确认工作区没有未解释的无关改动。

## 收尾选项

| 选项 | 动作 | 何时使用 |
|---|---|---|
| local-merge | 合并回基础分支并清理分支 | 本地集成即可 |
| create-pr | 推送并创建 PR | 需要远端审查 |
| keep | 保留分支和 worktree | 用户稍后处理 |
| discard | 丢弃分支和 worktree | 用户明确确认废弃 |

## Workflow
1. **验证状态**：运行或确认关键测试、lint、build、smoke。失败则停止。
2. **读取分支信息**：记录 current branch、base branch、worktree path。
3. **检查未提交改动**：区分本次改动、用户既有改动和临时产物。
4. **展示四个选项**：local-merge、create-pr、keep、discard。
5. **执行选择**：只执行用户明确选择的路径。
6. **合并后复验**：local-merge 后在基础分支上重新运行关键验证。
7. **PR 记录**：create-pr 时输出摘要、测试计划和风险说明。
8. **清理决策**：只在 local-merge 或 discard 且确认后清理分支/worktree。
9. **收尾报告**：输出最终状态、命令证据、残留风险和下一步。

## Closeout Report Template
```md
- Current Branch:
- Base Branch:
- Worktree Path:
- Dirty State:
- Verification Before Closeout:
- Selected Option: local-merge | create-pr | keep | discard
- Commands Run:
- Post-merge Verification:
- Cleanup:
- Residual Risk:
- Final Status:
```

## Commands
```bash
# 只读检查
git status --short
git branch --show-current
git worktree list
git merge-base HEAD main

# PR 场景示例
git push -u origin <branch>
gh pr create --title "<title>" --body "<summary>"
```

## Failure Handling
- 验证失败时停止收尾，切回 `adk-systematic-debugging` 或修复任务。
- base branch 不明确时，先询问或根据 `main/master` merge-base 推断并声明假设。
- PR 工具不可用时，输出 PR body 草案和手动步骤，不伪造已创建 PR。
- discard 未收到精确确认时，不删除任何分支或 worktree。

## Quality Gate
- 合并或 PR 前必须有验证证据。
- 必须给出四个收尾选项或说明为何某项不可用。
- destructive cleanup 必须明确确认。
- 合并后必须重新验证，不能只使用功能分支验证结果。
- 最终状态必须可由命令复核。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "测试刚才过了" | 合并目标可能不同 | 收尾前重新核对验证 |
| "直接帮用户删掉分支" | 可能删除重要工作 | 明确选择和确认 |
| "PR 创建失败但差不多" | 失败不是完成 | 输出失败原因和手动步骤 |
