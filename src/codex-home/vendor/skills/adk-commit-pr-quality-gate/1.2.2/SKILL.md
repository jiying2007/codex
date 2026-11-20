---
name: adk-commit-pr-quality-gate
description: "用于提交 PR 前核对测试证据、差异范围与质量门禁；不能替代独立代码审查，也不用于未授权的合并或发布。"
version: 1.2.2
last_updated: 2026-11-20
triggers:
  - "提交代码"
  - "中文提交信息"
  - "提交信息格式"
  - "commit message"
  - "发起PR"
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
在提交信息检查或 PR 准入时，只检查**当前操作真正涉及的风险和证据**。这是证据与质量门禁 Skill，不授予 git commit / push / merge / release 权限，也不替代独立 code review。

## Select the path
- **message-only**：用户只要求起草/校验提交信息时，读取目标仓 Commit Policy，检查类型、scope、BREAKING CHANGE 和语言；无需重新跑 build、创建 PR 或填发布矩阵。
- **PR-readiness**：有实际提交/PR 请求时，绑定本次工作树、HEAD、diff 与现有可信验证回执；检查问题聚焦、阻塞 findings、适用的 lint/test/build/smoke 证据。缺证据标 `needs-fix`，不伪报 pass。
- **high-risk**：公共 API、DB/schema、配置、生产/CI、权限、安全、发布、自动 review 或运行控制面变更，才按需读 `references/pr-risk-gates.md` 并执行相应专项证据门禁；低风险文稿不得被强制填写所有高风险字段。

## Workflow
1. 确定用户本次只要 message 文本、只读质量结论，还是明确授权的 SCM 操作。仅 message-only 可直接交付短文本，不扩展成代码审查或发布流程。
2. PR-readiness 冻结目标 diff 和真实测试身份，复用同快照仍有效的回执；**不得为了凑模板重复执行不受影响的验证**。必要时让 `adk-verification-before-completion` 核验真实 completion。
3. 核对问题、变更、受影响验证和 review blocker/major 是否一一对应；缺少 human owner / 独立复审责任时不能对受保护分支宣称完成。
4. **按影响选择专项门禁**：只有配置变更才要求 Config Drift Decision；Skill 资产变更才检查 core/optional；DB/API 删除才要求消费者/迁移/approval；发布/CI 变更才校验相应发布门禁。
5. 只有运行控制面变更才执行 `Runtime Control Plane` 专项，包含 `permission_profile_decision`、`deny-path test`、approval boundary、`runtime_config_diff` 和恢复验证。SCM review payload 来自受信 trigger 与结构化 findings，绝不在不可信 PR 中透传密钥。
6. `git commit`、`--amend`、`push`、`merge`、删除或发布仅由宿主现有授权和真实门禁执行；Skill 不能从“已通过评审”推断写权限。

## Minimal result
- **message-only**：建议消息 + 符合/不符合目标 Commit Policy 的理由；不构造虚假 Issue 编号。
- **PR-readiness**：`scope / source HEAD / evidence refs / relevant gates / blocker status / pass|needs-fix / next action`。
- **high-risk**：额外列真实专项证据、未知项、拒绝理由和回退，不生成空的 N/A 清单。

## Quality Gate
- 没有测试证据、未关闭 blocker/major、来源身份不匹配时不得 pass；用户明确要提交也不能绕过保护规则。
- 按实际影响 fail-closed：不把低风险无关项当阻塞，也不因为篇幅短而忽略真实 API/schema/配置/权限/发布风险。
- 所有 SCM 副作用需独立授权；完成结论可追溯原始差异、CI 和评审证据。
