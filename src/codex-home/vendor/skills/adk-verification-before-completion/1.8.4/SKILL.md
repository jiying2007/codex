---
name: adk-verification-before-completion
description: "用于完成前核对测试、审查和真实证据；不用于把自述、静态检查或过期收据当作完成证明。"
version: 1.8.4
last_updated: 2026-11-20
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
独立核验同快照交付声明；阶段结果与完整 Goal 分开，不以预算降低门禁。

## Modes / Applicability
- **checkpoint（阶段验收）**：核冻结子项、受影响接口、真实检查/Review 和依赖；不重复无关验证，不能关闭父 Goal。
- **goal-final（整个目标完成）**：核原验收分母、全部交付/依赖、最终快照、open items、独立验证和必要回归。
- **风险与阶段正交**：low 用最小充分证据；medium/high 的 checkpoint 仍须专项门禁，未知风险不降级。

## Workflow
1. 冻结 scope/mode/risk、HEAD/source snapshot、验收 IDs、claimant/verifier 和非目标。
2. 核实际命令、exit code、环境/时间、raw pointer；自述、旧 CI、源码推断不等于独立证据。新建/修改/可疑 checker 才校准正常/违规/阈值内/执行或覆盖失败；同身份配置范围的有效校准可复用，exit 0 不等于业务 PASS。
3. 按影响面读取 `references/verification-governance-details.md` 的 Applicability Matrix、25步、checker 示例和完整字段。高风险/争议/缺证据必须回读原文。
4. 核需求/契约、Review、required artifacts、权限、新鲜度、open items 和未查范围。checkpoint 保留剩余验收分母；goal-final 才按适用性处理 Codify。
5. 输出 `pass | needs-fix`、资格边界、风险和下一步；不适用项说明原因，低风险不填空表。

## Evidence Template（类别入口；字段见 reference）
- Scope / Mode / Risk / Claimant / Verifier / Snapshot / Acceptance IDs:
- Applicable Checks: command / exit_code / verified_at / raw_evidence
- Review / Open Items / Missing Evidence / Unchecked Scope:
- UI: Subjective Feature Proof (independent_verifier) + Appshots / UI Evidence Boundary
- Runner Smoke Contract / Runtime Control Plane Audit: runtime_config_diff / allow-deny / rollback
- Trace Eval Regression Evidence: not_applicable_reason
- Replayable Evidence Bundle / Tool / Skill Evidence Plan: skipped skills / fallback_evidence
- Lifecycle Operation Evidence: contract / owner / runtime_evidence
- Review Convergence Evidence: independence / replan
- Completion Guard Payload: required / passed / stale / verifier
- Codify Decision: （适用的 goal-final/复用晋级；checkpoint 用 checkpoint-deferred）按 `templates/governance/codify-decision.md` 记录 delivery_goal / reusable_pattern / affected_asset / promotion_candidate: true | false / next_task_friction_reduced / reduced_by / reduction_evidence / do_not_promote_reason / owner_review / rollback_path / verification_evidence
- Final Gate Result: pass | needs-fix / qualification_boundary / next_action

## Failure Handling / Quality Gate
- 必需项失败/缺失/过期、无有效理由跳过、Review blocker/major 或独立 verifier 缺失 → needs-fix。
- 状态/资源/异步核 owner/state/event/resource/termination/invariant、取消/超时/恢复/晚到及 generation；缺 whole-lifecycle review、高风险范围 `uninspected`、design-change 未 replan 或重大 Review 未独立闭环不得通过。
- 运行资产核 source-to-live、加载/健康/失败；权限/MCP/UI/发布/设备缺宿主证据写未验证，`completion_coverage` 静态 pass 不替代运行认证。breaking change 必须迁移/回退。
- 无真实效果、owner review 或回退，不得晋升 Codify。预算、组件发布、产品/现场资格分开；阶段通过不赋予 commit/merge/release 权限。
