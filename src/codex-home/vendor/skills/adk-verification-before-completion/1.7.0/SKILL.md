---
name: adk-verification-before-completion
description: 完成前验证门禁，确保交付声明与证据一致
version: 1.7.0
last_updated: 2026-09-14
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
- 在交付前统一核对验证证据、评审状态、运行边界和风险闭环，避免“未验先结论”。

## Prerequisites
- 已整理改动范围，并收集 lint/test/build/smoke、评审状态、风险和回退证据。
- 已区分 claimant 的完成声明与 verifier 的独立核验；主观或用户可见功能不能由实现者自证。

## Workflow
1. **冻结范围与声明**：记录改动边界、影响面、非目标和 claimant 声明；verifier 逐条对照证据，不采信结论文本本身。
2. **基础验证与评审闭环**：核对 lint/test/build/smoke、执行环境、blocker/major/minor；关键命令进入 Evidence Index。
3. **生命周期与 review 收敛**：状态/异步/共享资源变更核对 owner/state/event/resource/termination/invariant、取消/超时/恢复/迟到完成、generation 隔离和真实环境边界；同时核对 review mode、finding class、reopen、clean-review、独立性与 replan。
4. **运行资产与配置**：运行时目录需显式 tool target + 健康验证；配置变更需比较 `声明配置 vs 运行态加载`；runner/CLI/adapter/noninteractive/source-to-live 需 Runner Smoke Contract。
5. **用户可见与回放证据**：主观/UI 行为记录 Subjective Feature Proof 与 Appshots / UI Evidence Boundary；中高风险任务记录 Replayable Evidence Bundle。
6. **工具、技能与跨层披露**：核对 Tool / Skill Evidence Plan、required artifacts、skipped skills、tool fallback、fallback evidence、standards/architecture/ship disclosure、canonical resolution parity、browser evidence 或 not-applicable。
7. **模型/上下文/控制面**：模型、上下文、工具权限变更补本地回归和 approval/deny 未放宽证据；slash command、MCP/tool server、hook、permission/approval/sandbox 变更补 Runtime Control Plane Audit。
8. **Trace eval**：prompt、policy、skill routing、completion gate、agent guidance 变更补 Trace Eval Regression Evidence 或 `not_applicable_reason`。
9. **兼容性与长任务完整性**：显式判断 breaking change、迁移/回退；长任务核 retry budget、heartbeat、staleness threshold、plan completeness、attestation readback、失败路径、已排除方案和 open items。
10. **Codify Decision**：使用 `templates/governance/codify-decision.md` 记录复用价值、后续摩擦下降、owner review、rollback 与 verification evidence；不满足推广条件则写 `do_not_promote_reason`。
11. **Completion Guard Payload**：中高风险任务对 build/lint/test/smoke/security/release 中适用项记录 status、exit_code、command、evidence_path、verified_at、verifier；缺失/失败/过期不得进入完成态。
12. **反向核验并输出**：逐项证明“结论被证据支持”，输出 `pass` 或 `needs-fix`，列出未闭环项、下一步和责任人。

详细适用性矩阵、原 25-step 解释、门禁细则与合理化借口拦截见 `references/verification-governance-details.md`。入口只保留每次完成前验证都需要的决策面和机器证据字段。

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
- Appshots / UI Evidence Boundary: visible_text_boundary / permission_scope / sensitive_content_review / runtime_evidence_or_not_applicable
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
- 关键命令无法执行、claimant 声明缺证据、证据过期、verifier 未独立核对或主观功能缺 verifier verdict 时，必须说明原因并输出 `needs-fix`。
- blocker 未闭环、retry budget 用尽、heartbeat 过期或 open items 未解释时，不得给 `pass`。
- required artifact、skipped skill 原因、tool fallback/fallback evidence 或必要运行态证据缺失时，不得放行。

## 与 adk-commit-pr-quality-gate 的区别
- `adk-verification-before-completion`：完成前自检，证明完成声明、验证命令、运行证据和风险边界一致。
- `adk-commit-pr-quality-gate`：提交/PR 质量门禁，聚焦格式、规范、评审与 SCM 交付质量。

## Quality Gate
- 输出必须包含验证命令、关键结果、风险项和处理状态；完成声明必须区分 claimant、verifier、证据列表、缺失证据和 open items。
- 未闭环 blocker、缺独立 Subjective Feature Proof、证据过期或 completion guard 必需项失败时，结论固定 `needs-fix`。
- Runtime Control Plane Audit 缺 deny-path test、loaded_tools 或 rollback_path 不得放行；Trace Eval Regression Evidence 缺 regression case 且无 not_applicable_reason 不得放行。
- 跨模块/协议/数据/发布/存储/资源/UI 变更必须有 standards/architecture/ship disclosure/canonical resolution parity/browser evidence 或 not-applicable；运行目录、配置、runner 与 UI 证据不得用源码推断替代。
- Evidence Index 字段必须完整且至少包含一条负结果或被证伪路径；中高风险任务还必须有 Replayable Evidence Bundle、Tool / Skill Evidence Plan 和 Completion Guard Payload。
- Codify Decision 必须记录 reusable_pattern、promotion_candidate、next_task_friction_reduced、reduced_by、reduction_evidence、do_not_promote_reason、owner_review、rollback_path、verification_evidence；`promotion_candidate: true` 缺 owner_review、rollback_path、verification_evidence 或摩擦下降证据时固定 `needs-fix`。
- 受控生命周期操作缺契约、owner、终止路径或真实环境边界不得完成；生命周期变更缺 whole-lifecycle review，或 design-change/新增 blocker-major/超自审预算未 replan 时不得 `pass`。
- breaking change 必须有迁移与回退；模型/上下文/工具权限变化必须证明 approval/deny gate 未放宽。
- 禁止使用“应该可以/理论上通过”等无证据措辞。
