---
name: adk-commit-pr-quality-gate
description: "用于提交 PR 前核对测试证据、差异范围与质量门禁；不能替代独立代码审查，也不用于未授权的合并或发布。"
version: 1.1.2
last_updated: 2026-11-03
triggers:
  - "提交代码"
  - "中文提交信息"
  - "提交信息格式"
  - "commit message"
  - "发起PR"
  - "代码评审"
non_triggers:
  - 纯探索性代码阅读
inputs:
  - 改动集合、验证结果、评审记录
outputs:
  - 分级门禁结论（pass/needs-fix）与整改项
constraints:
  - 缺少适用于当前风险的验证证据不得给通过结论
  - blocker 或 major 未闭环不得给 pass
  - 问题陈述不清或单次改动包含多个不相关问题时不得放行
---

# adk-commit-pr-quality-gate

## Goal
- 核对提交证据、结论与范围。

## 提交信息与授权边界

- 提交格式以目标仓库的 Commit Policy（例如 `AGENTS.md`）为准；默认采用 `type(scope): 摘要`，不按中文/英文另建 Skill。
- 文本语言遵守用户明确要求与项目 locale，类型、scope 和 `BREAKING CHANGE` 标识保持机器可解析；没有 Issue 的 bugfix 不得被强制要求捏造 Issue 编号。
- 此 Skill 只分析、生成或校验提交信息；`git commit`、`--amend`、`push`、`merge` 与发布必须受独立的操作授权和当前工作树证据约束。
- 格式校验示例：`python3 -m agent_dev_kit.commit_message_policy --message "fix(runtime): 修复回退判断"`。该工具仅返回验证结论，绝不执行 SCM 写入。

## Prerequisites
- 汇总改动、验证及评审分级。
- 明确本次改动是否涉及 breaking change 与迁移影响。
- 若包含配置文件改动，先给出配置摘要（变更键、行为影响、回退方式）。

## Workflow
1. 真实性核验：确认问题可复现，证据与改动目标一一对应。
2. 范围核验：确认单次改动是否聚焦一个问题，避免捆绑无关变更。
3. 证据核验：逐项核对 lint/test/build/smoke 命令与执行结果。
4. 证据索引：为关键验证命令记录退出码、结果摘要、证据路径、层级（Evidence Index）。
5. 分级评审：按 blocker/major/minor 输出问题清单与闭环状态。
6. 配置漂移核验：若触及配置文件，必须输出配置摘要与行为影响结论（Config Drift Decision）。
7. 技能候选核验：若触及技能资产，必须声明 `global-ready/project-bound` 与 `core/optional/reject`。
8. 兼容性核验：显式声明 breaking change、迁移与回退路径。
9. 所有权核验：AI-assisted output 必须有明确 human owner；草稿态、未复审或未验证的 AI 输出不得进入受保护分支。
10. 结构变更核验：DB schema 变更必须带迁移/回滚证据；删除较大代码、公共 API 或 shared contract 前必须列调用点和 approval gate。
11. 发布链路核验：若触及 `scripts/` 或关键构建入口，追加 release gate 专项验证。
12. Core/Optional 核验：确认能力归属是否应进 core，场景化能力应进入 optional。
13. CI/PR review 核验：若使用 AI runner 生成 PR review，必须核对 trusted-trigger、secret 隔离、结构化 findings、SCM payload review 和 inline anchoring。
14. Runtime Control Plane 核验：若改动 slash command、MCP/tool server、hook、permission profile、approval policy 或 sandbox，必须核对 `slash_command_runtime_audit`、`mcp_runtime_contract`、`permission_profile_decision`、`approval_boundary`、`deny_path_test`、`runtime_config_diff` 和 rollback。

## Commands
```bash
git diff --stat <base>...HEAD
<project-lint-cmd> && <project-test-cmd>
git diff --name-only <base>...HEAD
```

## Evidence Template
```md
- Scope Check:
- Verification Commands + Results:
- Evidence Index (command/exit_code/result_summary/evidence_path/layer):
- Review Findings (B/M/m):
- Config Drift Decision:
- Skill Intake Decision:
- Human Owner / Review Responsibility:
- Breaking Change Decision:
- Release Gate Decision:
- Core/Optional Decision:
- CI/PR Review Decision:
- Runtime Control Plane Decision:
- Final Gate Result:
```

## Failure Handling
- 任一 blocker 未闭环，直接输出 `needs-fix` 并阻断合并。
- 若证据缺失或命令不可复现，退回补证，不得先给通过结论。

## 与 adk-verification-before-completion 的区别
- adk-commit-pr-quality-gate: 提交/PR 门禁（格式规范、评审闭环）
- adk-verification-before-completion: 完成前自检（验证命令、证据完整性）

## 按风险适用的证据门禁

- E0/E1 或局部可逆小改：仅要求变更范围、适用的定向验证、失败路径（适用时）和结果；无关的 DB、发布、MCP、设备或 AI review 材料标为 `not_applicable`，不能为了填模板制造假证据。
- E2/E3、公共 API、schema/数据库、CI、外部权限、发布和受控生命周期：保留相应专项测试、审查、回滚与授权证据，真实风险不因语言或低 Token 设置而降低。
- `cannot-verify`、缺失适用证据和真实 blocker 仍 fail-closed；禁止将“未执行”写成通过。
- Issue 链接由真实任务关系和仓库策略决定，不为无 Issue 的普通修复创建虚假链接。

## Quality Gate
- 输出必须可执行、可验证、可追溯。
- 结论必须与分级统计一致，且可复核。
- 若存在"多问题捆绑"或"证据缺失"，结论必须为 `needs-fix`。
- 若触及发布链路但无专项验证证据，结论必须为 `needs-fix`。
- 若触及配置但无配置摘要或无行为影响结论，结论必须为 `needs-fix`。
- 若触及技能资产但无安装范围或归属结论，结论必须为 `needs-fix`。
- 若 AI-assisted output 缺少 human owner、复审责任或冲突修复证据，结论必须为 `needs-fix`。
- 若 DB/schema/API 删除或迁移缺少调用点、迁移或 approval 证据，结论必须为 `needs-fix`。
- 缺陷诊断、假设调查或高风险变更若缺少适用的负结果/证伪记录，结论为 `needs-fix`；无此路径的小改标记 `not_applicable`。
- 若 AI/CI review 缺少结构化 findings、trusted-trigger 或 untrusted PR secret 隔离证据，结论必须为 `needs-fix`。
- 若 SCM review comment 来自自由文本或 inline anchoring 未验证，结论必须为 `needs-fix`。
- 若运行控制面变更缺少 slash/MCP/permission 审计、deny-path test、approval boundary 或 rollback 证据，结论必须为 `needs-fix`。

---

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "改动很小不用检查" | 小改动也会引入回归，蝴蝶效应真实存在 | 跑完质量门禁再提交，无例外 |
| "就改了一行配置" | 配置变更的影响面可能比代码更大 | 按 SKILL.md 附配置摘要与行为影响结论 |
| "测试在本地跑过了" | 本地环境不可审计不可复现 | PR 必须包含验证证据，结论基于 Evidence Index |
