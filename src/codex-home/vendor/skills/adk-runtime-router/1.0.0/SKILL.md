---
name: adk-runtime-router
description: adk-first 运行时技能路由入口，统一判定 primary/supporting/fallback 与跳过条件
version: 1.0.0
last_updated: 2026-05-18
triggers:
  - "技能路由"
  - "选择技能"
  - "任务分流"
  - "adk 路由"
  - "adk-first"
  - "判断使用哪个技能"
  - "运行时路由"
  - "开始任务前"
non_triggers:
  - 子代理已收到明确任务包
  - 已有完整计划且只需按计划执行
  - 纯背景知识问答且不需要工具或文件操作
inputs:
  - 用户请求、仓库规则、任务类型、风险等级、可用 skill 清单
outputs:
  - primary skill、supporting skills、fallback 条件、跳过理由与下一步动作
constraints:
  - 已有 adk 等价能力时不得优先调用 Superpowers fallback
  - 任何 fallback 必须说明触发原因和退出条件
  - 不得用“任务很简单”作为跳过路由的理由
---

# adk-runtime-router

## Goal
- 在任务开始前统一完成 adk-first 路由判断，避免多个 skill 抢占入口或无纪律 fallback。
- 将用户请求映射到一个 primary skill、若干 supporting skills 和明确的验证路径。
- 对 Superpowers 兼容能力设置显式 fallback 条件，而不是默认启用。

## Prerequisites
- 已读取当前仓库 `AGENTS.md`、项目级规则和用户最新指令。
- 已确认任务是否只读、是否会修改文件、是否涉及公共契约或运行态资产。
- 可访问当前安装的 adk skill 元数据或 `manifest.yaml` routing 表。

## 路由分层

| 任务类型 | Primary Skill | Supporting Skills | Fallback 条件 |
|---|---|---|---|
| 需求不清、边界不明 | `adk-requirements-triage` | `adk-task-breakdown` | 用户明确要求 Superpowers brainstorming |
| 测试策略、TDD、回归 | `adk-test-strategy` | `adk-unit-test-embedded` | 项目已有专用测试 workflow |
| 多模块拆分、并行判断 | `adk-task-breakdown` | `adk-parallel-agent-governance` | 平台子代理不可用时降级串行 |
| worktree 隔离 | `adk-worktree-governance` | `adk-task-breakdown` | 用户要求手动管理分支 |
| 根因未明 bug / 测试失败 | `adk-systematic-debugging` | `adk-verification-before-completion` | adk 调试流程缺少领域覆盖 |
| 代码审查或 review 反馈 | `adk-code-review-loop` | `adk-commit-pr-quality-gate` | 需要外部审查系统专用流程 |
| 完成/提交/PR 前 | `adk-verification-before-completion` | `adk-commit-pr-quality-gate` | 仅用户点名时 fallback |
| 分支收尾 | `adk-branch-closeout` | `adk-verification-before-completion` | 远端权限或 PR 工具不可用时输出手动步骤 |
| 发布、版本、回退 | `adk-release-versioning` | `adk-commit-pr-quality-gate` | 需要非 adk 发布系统专用流程 |
| 多 skill 冲突 | `adk-runtime-router` | `adk-skill-composition-governance` | governance skill 未安装时在 AGENTS 中显式裁决 |

## Workflow
1. **识别任务模式**：判定只读分析、实现、debug、review、release、并行/worktree、会话收口。
2. **判定风险等级**：检查是否涉及 shared contract、schema、根配置、CI、依赖、运行态 `~/.codex` 或发布链路。
3. **选择 primary skill**：每个任务只能有一个 primary skill；其他 skill 只能补充检查项。
4. **声明 supporting skills**：列出辅助 skill 的用途，避免辅助 skill 抢占入口。
5. **检查 fallback**：只有 adk 缺失等价能力、用户明确点名、迁移期对照验证或平台约束时才 fallback。
6. **输出路由裁决**：写明 primary/supporting/fallback/skip reason/verification path。
7. **进入执行 skill**：加载 primary skill，并按其 workflow 推进。
8. **完成前复核**：若产生改动，最终必须经过 `adk-verification-before-completion`。

## Route Decision Template
```md
- Task Mode: readonly | implementation | debugging | review | release | parallel | closeout
- Risk Level: low | medium | high
- Primary Skill:
- Supporting Skills:
- Fallback:
  - enabled: yes/no
  - reason:
  - exit_condition:
- Skip Reasons:
- Verification Path:
- Next Action:
```

## Commands
```bash
# 自动匹配任务文本
bash scripts/devkit.sh match --text "<用户请求>"

# 检查指定 skill 是否适合
bash scripts/devkit.sh match --skill <skill-name> --text "<用户请求>"

# 检查 profile 与 routing 是否一致
bash scripts/check-profile-coherence.sh
bash ../scripts/check-runtime-routing.sh ..
```

## Failure Handling
- 若多个 primary skill 同时命中，暂停并按“更靠前流程优先”裁决：triage/debug > task-breakdown > implementation > verification > release。
- 若 adk 与 Superpowers 都可处理，优先 adk；只有 fallback 条件成立才调用 Superpowers。
- 若路由表无法覆盖自然语言请求，记录触发语料缺口，并补充 `skill_trigger_cases.tsv`。
- 若 supporting skill 未安装，降级为内联检查项，不得阻塞低风险任务。

## Quality Gate
- 输出必须包含 primary skill、supporting skills、fallback 与验证路径。
- fallback 必须有明确原因，不能只写“更熟悉”或“更方便”。
- 不得同时声明两个 primary skill。
- 修改 skill、manifest、workflow 或 routing 后必须运行匹配测试与严格校验。
- 触发失败样例必须进入回归语料，防止同类请求再次漏匹配。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "这只是小任务，不需要路由" | 小任务也需要确认是否只读、是否改文件、是否要验证 | 输出轻量路由裁决，可简短但不可省略关键判断 |
| "Superpowers 更完整，直接用它" | adk-first 的目标是默认主链，Superpowers 只是 fallback | 先检查 adk 等价能力，再说明 fallback 条件 |
| "多个 skill 都有用，一起上" | 多入口会导致职责混乱和过重流程 | 只选一个 primary，其余作为 supporting |
| "自然语言没命中就算了" | 漏匹配会持续削弱 adk 默认地位 | 补 triggers、routing intent 和回归测试 |
