---
name: adk-verification-before-completion
description: 完成前验证门禁，确保交付声明与证据一致
version: 1.6.0
last_updated: 2026-09-10
triggers:
  - "准备完成"
  - "准备提交"
  - "完成前检查"
non_triggers:
  - 仅做方案讨论且尚未产生实现改动
  - 纯背景知识问答
inputs:
  - 改动清单、测试结果、评审结论、风险与回退信息
outputs:
  - 完成声明核对、Codify Decision、完成前核对清单、门禁结论、未闭环项与处理建议
constraints:
  - 没有验证证据不得给出完成或通过结论
  - 评审 blocker 未关闭时不得给通过结论
  - breaking change 必须显式声明与迁移/回退方案
  - 交付后沉淀决策必须记录 reusable_pattern、promotion_candidate、next_task_friction_reduced、reduced_by、reduction_evidence、do_not_promote_reason、owner_review、rollback_path、verification_evidence
---
# adk-verification-before-completion
## Goal
- 在交付前统一核对验证证据、评审状态和风险闭环，避免“未验先结论”。
## Prerequisites
- 已整理改动范围，并收集 lint/test/build/smoke 与评审状态证据。
## Workflow
1. 收敛改动范围：确认本次改动边界、影响面与非目标。
2. 完成声明分离：记录 claimant 的完成声明，再由 verifier 逐条核验证据，不直接采信声明文本。
3. 证据核验：核对 lint/test/build/smoke 等结果与执行环境；主观或用户可见功能必须有独立 verifier 的 Subjective Feature Proof，不能由实现者自证。
4. 评审闭环：按 blocker/major/minor 分级，检查必须项是否关闭。
5. 生命周期操作核验：若变更涉及状态、异步完成或共享资源，核对 owner/state/event/resource/termination/invariant 矩阵、取消/超时/恢复/迟到完成、generation 隔离和真实环境验证；不适用时记录理由。
6. Review 收敛核验：核对 review mode、finding class、reopen、clean-review 计数、独立性和 replan 决策；targeted finding 修复不得被当作整体生命周期通过。
7. 运行目标检查：若目标是运行时目录，必须补显式 tool target 适配证据与运行目录健康验证证据。
8. 配置加载核验：若涉及运行时配置变更，补 `声明配置 vs 运行态加载` 对比证据。
9. prompt 回归核验：若改动提示词或策略文本，补 before/after 行为对比与失败样例。
10. 证据索引化：关键命令必须记录命令、退出码、结果摘要、证据路径、层级（Agent/Skill/Workflow）与关联工件。
11. Replayable Evidence Bundle 核验：中高风险交付必须记录 input snapshot、environment snapshot、tool transcript digest、artifact hashes、expected assertions、sensitive-data review 和不可回放原因。
12. Appshots / UI Evidence Boundary 核验：UI 或用户可见行为必须记录可见窗口/可见文本边界、permission scope、sensitive-content review；不得把 source-only inspection 当作 runtime UI 证据。
13. Runner Smoke Contract 核验：涉及 runner、CLI、adapter、noninteractive 或运行资产链路时，必须记录 schema/JSONL 输出、sandbox、approval、cwd、thread/turn、resume/reply、失败/取消路径。
14. Tool / Skill Evidence Plan 核验：检查 primary/supporting skills、required artifacts、skipped skills、tool fallback、fallback evidence 和 evidence paths 是否完整；required artifact 缺失或 skipped skill 无原因时不得放行。
15. 标准/架构/发布披露核验：跨模块、协议、数据、发布、存储、资源或 UI/UX 变更必须附 standards impact、architecture review、ship disclosure、canonical resolution parity、browser evidence 或 not-applicable 证据。
16. 兼容性检查：显式判断是否存在 breaking change，并给出迁移与回退方案。
17. 模型/上下文变更核验：若切换模型、扩大上下文或提升工具能力，必须补本地回归和权限/approval 未放宽证据。
18. Runtime Control Plane Audit：若改动 slash command、MCP/tool server、hook、permission profile、approval policy 或 sandbox，必须记录 `slash_command_runtime_audit`、`mcp_runtime_contract`、`permission_profile_decision`、`loaded_tools`、`approval_boundary`、`deny_path_test`、`runtime_config_diff` 和 `rollback_path`；确认权限未放宽或说明审批依据。
19. Trace Eval Regression Evidence：若改动 prompt、policy、skill routing、completion gate 或 agent guidance，必须记录 `trace_eval_regression_case` 或 `not_applicable_reason`；候选必须包含 dataset_id、case_id、source_trace_id、prompt_version、candidate_prompt_version、expected_regression_signal、grader、score_threshold、regression_link、retention_policy、redaction_status 和 owner_approval。
20. 反向核验：逐条检查“结论是否被证据支持”，避免先给结论后补证据。
21. 卡死/重试核验：长任务必须核对 retry budget、heartbeat、staleness threshold、plan completeness、attestation readback、失败路径、已排除方案和 open items。
22. Codify Decision：交付前确认是否存在可复用模式，使用 `templates/governance/codify-decision.md` 记录 `delivery_goal`、`reusable_pattern`、`affected_asset`、`promotion_candidate`、`next_task_friction_reduced`、`reduced_by`、`reduction_evidence`、`do_not_promote_reason`、`owner_review`、`rollback_path`、`verification_evidence`。
23. 推广门禁：只有当 `verification_evidence` 支持复用价值、`owner_review` 明确、`rollback_path` 可执行，且 `next_task_friction_reduced` / `reduced_by` / `reduction_evidence` 说明后续成本如何下降时，才允许把 `promotion_candidate` 标记为 true；否则必须填写 `do_not_promote_reason`。
24. Completion Guard Payload 核验：中高风险任务必须有结构化 guard payload，至少记录 build/lint/test/smoke/security/release 中适用项的 `status`、`exit_code`、`command`、`evidence_path`、`verified_at` 和 `verifier`；缺失、失败或过期时不得进入完成态。
25. 结论输出：给出 pass/needs-fix，并列出下一步动作与责任人。
## Commands
```bash
rtk git diff --name-only <base>...HEAD
rtk <project-lint-cmd>
rtk <project-test-cmd>
rtk bash scripts/devkit.sh runtime-boundary
rtk bash scripts/check-codify-governance.sh
```
## Evidence Template
```md
- Scope Summary:
- Completion Claim Audit:
- Verification Command Results:
- Runtime Config Audit:
- Prompt Regression Evidence:
- Model / Context Regression Evidence:
- Runtime Control Plane Audit: slash_command_runtime_audit / mcp_runtime_contract / permission_profile_decision / loaded_tools / approval_boundary / deny_path_test / runtime_config_diff / rollback_path
- Trace Eval Regression Evidence: trace_eval_regression_case / dataset_id / case_id / source_trace_id / prompt_version / candidate_prompt_version / expected_regression_signal / grader / score_threshold / regression_link / retention_policy / redaction_status / owner_approval / not_applicable_reason
- Standards / Architecture / Ship Disclosure / Resolution Parity / Browser Evidence:
- Evidence Index:
- Replayable Evidence Bundle: input_snapshot / environment_snapshot / tool_transcript_digest / artifact_hashes / expected_assertions / sensitive_data_review / non_replayable_reason
- UI / Appshots Evidence Boundary: visible_text_boundary / permission_scope / sensitive_content_review / runtime_evidence_or_not_applicable
- Runner Smoke Contract: event_stream_schema / sandbox_approval_cwd / thread_turn_or_resume_reply / failure_cancel_path
- Tool / Skill Evidence Plan: primary_skill / supporting_skills / required_artifacts / skipped skills / tool_fallback / fallback_evidence / evidence_paths
- Codify Decision: delivery_goal / reusable_pattern / affected_asset / promotion_candidate / next_task_friction_reduced / reduced_by / reduction_evidence / do_not_promote_reason / owner_review / rollback_path / verification_evidence
- Completion Guard Payload: required_checks / passed_checks / failed_checks / skipped_with_reason / stale_checks / verifier / completion_allowed
- Lifecycle Operation Evidence: not_applicable_reason | contract / owner / state-events / termination / runtime-evidence
- Review Convergence Evidence: review_round / review_mode / finding_classes / new_finding_class_count / reopened_finding_count / consecutive_clean_reviews / reviewer_independence / contract_change_decision / replan_reason
- Subjective Feature Proof: feature / independent_verifier / expected / observed / evidence / verdict
- Review Status (B/M/m):
- Breaking Change Decision:
- Risk + Rollback:
- Final Gate Result:
```

```md
Evidence Index（命令级）:
| Command | Exit Code | Result Summary | Evidence Path | Layer | Related Artifact |
|---|---|---|---|---|---|
| <cmd> | 0 | <summary> | <path> | Workflow | verify-report |
```

## Failure Handling
- 关键命令无法执行时，必须说明原因并降级完成度表述。
- 若 blocker 未闭环，结论固定为 `needs-fix`，不得放行。
- claimant 声明缺少对应证据、证据过期、verifier 未独立核对，或主观/用户可见功能缺少 verifier verdict 时，结论固定为 `needs-fix`。
- retry budget 用尽、heartbeat 过期或 open items 未解释时，不得给出 `pass`。

## 与 adk-commit-pr-quality-gate 的区别
- adk-verification-before-completion: 完成前自检（验证命令、证据、边界）
- adk-commit-pr-quality-gate: 提交/PR 质量门禁（格式、规范、评审）

## Quality Gate
- 输出必须包含验证命令、关键结果、风险项和处理状态。
- 完成声明必须区分 claimant、verifier、证据列表、缺失证据和 open items；主观/用户可见功能还必须区分 expected/observed/verdict。
- 若存在未闭环 blocker，结论必须为 `needs-fix`。
- 完成声明需与实际证据逐项可追溯。
- 若声明目标可在运行时目录放行，必须附显式 tool target 适配证据和运行目录健康验证结果。
- 若涉及运行时配置变更，必须附声明配置与运行态加载一致性结论。
- 若涉及 prompt/policy 文本变更，必须附 before/after 行为对比与失败样例。
- 若涉及模型切换、上下文扩容或工具权限变化，必须附本地回归和 approval/deny gate 未放宽证据。
- 若涉及 slash command、MCP/tool server、hook、permission profile、approval policy 或 sandbox，必须附 Runtime Control Plane Audit；缺少 deny-path test、loaded_tools 或 rollback_path 时不得放行。
- 若涉及 prompt、policy、routing、completion gate 或 guidance 变更，必须附 Trace Eval Regression Evidence；缺少 regression case 且无 not_applicable_reason 时不得放行。
- 跨模块、协议、数据、发布、存储、资源或 UI/UX 变更必须有 standards/architecture/ship disclosure/canonical resolution parity/browser evidence 或 not-applicable 证据，不得隐藏兼容性、回滚或用户可见影响。
- 关键验证命令必须存在 Evidence Index 记录，且字段完整（命令/退出码/结果摘要/证据路径/层级）。
- 中高风险任务必须存在 Replayable Evidence Bundle；无法回放时必须填写不可回放原因和替代证据。
- UI 或用户可见行为必须存在 Appshots/UI 证据边界或 not-applicable 说明；不得用源码推断替代运行时证据。
- runner、CLI、adapter、noninteractive 或 source-to-live 变更必须存在 Runner Smoke Contract 证据。
- 中高风险任务必须核对 Tool / Skill Evidence Plan；required artifacts、skipped skills、tool fallback 或 fallback evidence 缺失时结论固定为 `needs-fix`。
- Evidence Index 至少包含一条负结果或被证伪路径记录。
- Codify Decision 必须记录 reusable_pattern、promotion_candidate、next_task_friction_reduced、reduced_by、reduction_evidence、do_not_promote_reason、owner_review、rollback_path、verification_evidence。
- `promotion_candidate: true` 缺少 owner_review、rollback_path 或 verification_evidence 时，结论固定为 `needs-fix`。
- `promotion_candidate: true` 缺少 next_task_friction_reduced、reduced_by 或 reduction_evidence 时，结论固定为 `needs-fix`。
- 中高风险任务缺少 Completion Guard Payload，或 payload 显示必需 build/lint/test/smoke/security/release 检查未通过、无 evidence_path、无 verifier、结果过期时，结论固定为 `needs-fix`。
- 受控生命周期操作缺少契约、owner 结论、终止路径证据或所需真实环境验证边界时，不得声明功能完成或产品就绪。
- 生命周期变更若没有适用的 whole-lifecycle review，或 `design-change`、新增 blocker/major finding class、超出自审轮次预算未触发 replan，则不得给出完成 pass。
- 禁止使用"应该可以/理论上通过"等无证据措辞。

---

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "我验证过了" | 口头验证不是证据，无法复现无法审计 | 按 SKILL.md 写入 Evidence Index，附命令/退出码/结果摘要 |
| "跑了一遍应该没问题" | "应该"是被禁止的措辞，一次性通过不等于可靠 | 关键验证命令必须可复跑，且记录负结果 |
| "这次改动很安全不需要全量验证" | 安全感不等于安全性，局部验证遗漏全局回归 | 按验收标准逐项验证，Evidence Index 至少含一条负结果 |
