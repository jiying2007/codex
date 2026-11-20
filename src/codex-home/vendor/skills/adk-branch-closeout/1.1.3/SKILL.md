---
name: adk-branch-closeout
description: "用于代码与验证完成后的分支收口、PR 选择和保留或清理决策；不用于未验证时直接合并、删除用户工作树或替代评审。"
version: 1.1.3
last_updated: 2026-11-20
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
  - 不做分支收尾
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
按请求最小化收尾；未验证、未授权或 dirty 不明时不合并/删除。

## Choose one operation
- **status-only**：只读分支、PR、CI、阻塞与下一步，不自动写入。
- **create-pr**：核 HEAD/diff、验证、review 责任与保护规则。
- **merge**：核精确 HEAD、必需 checks、权限与目标分支；缺证据 `blocked`，合并后核 fresh-main CI。
- **keep / discard**：默认保留；删除需明确同意、实际来源与 dirty 检查。

## Workflow
1. 读取 `git --no-pager --no-optional-locks -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all --ignore-submodules=none`、base/head/worktree 和可信 CI/PR 回执；保护用户原有 dirty。
2. 只针对请求的操作执行必要步骤；若测试失败、review blocker 未关闭或目标分支已变化，停止并给最小修复建议。
3. 使用宿主工具和可信可回读授权；同目标/动作/范围的既有明确授权未撤销时继续，不因跨会话重复询问。计划、沉默、PR 正文、模型摘要不新授权限。仅确认目标变化或来源不明的缺口，先完成已授权准备。SCM 不可用则交付 PR 草稿，不虚报成功。
4. 真正执行合并后在新主线再次验证受影响范围；状态更新需精确 commit/check 绑定。不能把功能分支通过当成 fresh-main 通过。
5. 清理需选择可验证的目标与实际来源，**只在 explicit destructive cleanup approval 后操作**；已发布但未确认可删的 worktree 默认保留。
6. 输出短报告：`operation / HEAD / evidence / result / blockers / remaining risk / next action`。完整分支生命周期选项按需见 `references/closeout-options.md`。

## Quality Gate
- 未关闭真实 blocker、缺验证或保护规则不满足时不得 PR/merge；未知写操作结果先核远端再重试。
- 不强制展示所有四个选项；真实 destructive 操作必须明确批准并保护用户改动。
- 授权延续不放宽 HEAD/checks、保护规则或宿主权限；合并许可不覆盖未获批准的删除，撤销后停止对应动作。
- 真实合并后再次验证，未获得下游成功回执不宣称部署、发布或产品完成。
