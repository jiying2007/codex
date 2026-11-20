---
name: adk-worktree-governance
description: "用于 git worktree 并行开发前的隔离、基线锁定、同步与安全清理；不用于擅自删除脏工作树或替代多 Agent 任务拆分。"
version: 1.3.2
last_updated: 2026-11-20
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
  - 不创建工作树
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
仅在确有**隔离开发价值**时规划和操作 worktree，保护用户 dirty 状态，不把每个任务都变成额外分支、环境、清理与模型巡检。

## Admission
- **stay-current**：单文件修复、普通文档或无需独立环境的任务，在当前分支完成；输出“无需 worktree”和原因，不创建目录或分支。
- **isolated**：确有冲突、独立长分支、并行资源/测试隔离或受控实验时，先核基线分支、工作区状态、共享写范围及真实验证入口。创建任何 worktree 前遵守现有授权。
- **automation**：只有实际无人值守执行才增加 owner、停止条件、`Automation Risk Decision` 与 `Heartbeat / Staleness Threshold`。普通只读规划不必生成伪心跳或周期巡检。

## Workflow
1. 只读 `git --no-pager --no-optional-locks -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all --ignore-submodules=none`、当前分支及 `git worktree list`，区分用户修改与本任务。形成 `Dirty Worktree Decision`：继续、隔离或等用户处理；**不得自动 commit、stash、reset 或清理用户工作**。
2. 判断 worktree 是否提供实际冲突/复验收益；没有收益立即退出，避免安装依赖、生成额外环境或反复扫描。
3. 如需创建，记录真实 base commit、new branch、受控隔离路径、`scope_write`、`must_not_touch`、验证和停止条件；不存在的目录不凭空声称已建立。
4. 暂存/交接素材必须保留 provenance 和 source identity，禁止写入 `.git/`，必须位于忽略区域或显式排除提交。共享 contract、schema、root config 由单一 owner 收口。
5. **操作需要宿主授权**。仅在被授权且基线一致时创建；setup、依赖安装和外部写入也各遵从实际权限。unattended automation 需要明确 owner approval、首轮证据、停止/恢复路径，不基于陈旧 heartbeat 继续跑模型。
6. 交接前核 whole-diff 和目标验证；worktree 内测试通过不等于主线通过。真实合并由 SCM/PR 门禁负责。
7. 清理只针对本流程真实创建且来源已确认的目录/分支；任何 destructive cleanup 都要求单独确认，未知/dirty 默认保留。详细创建与清理检查按需读 `references/worktree-operation-boundaries.md`。

## Quality Gate
- 是否需要 worktree 与 `Dirty Worktree Decision` 有可追溯依据；未授权不可创建、写入或删除。
- 有 automation 才强制 `Automation Risk Decision`、`Heartbeat / Staleness Threshold`；真实自动化必须有 stop/rollback/owner，不得用空字段伪造通过。
- 共享资源独占、scratch provenance、最终整合验证和真实审批是硬门禁，不因低 Token 模式降低。
