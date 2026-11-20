---
name: adk-after-action-review
description: "用于任务交付后复盘问题、修复成本与可复用经验并形成候选记录；不用于替代交付前验证或直接发布未经审核的长期记忆。"
version: 1.3.1
last_updated: 2026-11-20
triggers:
  - "任务复盘"
  - "经验沉淀"
  - "After Action Review"
  - "避免重复犯错"
  - "复盘 lessons"
non_triggers:
  - 线上事故需要做根因分析复盘
  - 仅做方案讨论且没有执行结果
  - 只保存完整聊天记录
inputs:
  - 任务目标、执行结果、错误与修复、验证结果、现有 AGENTS/runbook 约束
outputs:
  - AAR 复盘、memory candidate、Codify Decision、风险分级、写入位置路由、人工确认项
constraints:
  - 不得保存原始会话、密钥或隐私内容，不能直接写入长期 memory、AGENTS
  - 普通复盘不强制资产晋级字段；真正 guidance promotion 仍执行原有审核与证据门禁
---

# adk-after-action-review

## Goal
复盘实际任务，提炼能减少下次返工的经验；普通 AAR 与长期规则/Skill 晋级分离，避免把一次性噪声包装成长期资产。

## Depth
- **lite（默认）**：目标、结果与证据、遇到的失败/返工、下一次有用的做法、剩余风险。无可复用经验则 `memory_candidates: []`。
- **standard**：重复出现的技术问题，补复现条件、例外和复验信号。
- **promotion**：用户或正式交付流程明确要求沉淀到长周期规则、Skill、AGENTS 或 memory 时，才使用 `Codify Decision` 和完整审查合同。此模式的证据、owner、权限及回退不能简化。

## Workflow
1. 读取目标、最新执行和真实验证结果；区分事实、推断、负结果，不编造根因和节约成本。
2. 只提下一次可用的经验；无推广价值时输出极简 AAR 后结束。
3. lite 不强迫填写 `reduction_evidence`、owner review、trace-eval 或完整 promotion 模板。
4. promotion 对每条候选记录 `evidence`、`last_verified`、`confidence`、`risk`、`write_route`。正式 `Codify Decision` 需有 `delivery_goal`、`affected_asset`，并包含 `reusable_pattern`、`promotion_candidate`、`next_task_friction_reduced`、`reduced_by`、`reduction_evidence`、`do_not_promote_reason`、`owner_review`、`rollback_path`、`verification_evidence`。
5. 只有正式指导规则晋级时才需要 `trace-feedback-eval-handoff`、`sanitized trace` 和 `trace_eval_regression_case` 及回归评测；缺真实模型证据标 `not-measured`，不伪造效果。
6. 生产事故分析交给 `adk-incident-rca-report`，本 Skill 复用其结论不生成第二份 RCA。

## References (only on demand)
- 复盘/诊断：`references/after-action-review.md`
- 候选存储：`references/memory-candidate.md`，与 `templates/memory/memory-candidate.md` 语义一致
- 长期资产晋级：`references/codify-decision.md`，正式执行使用原有 `templates/governance/codify-decision.md` 合同

## Quality Gate
- 不保存完整聊天记录，尤其不得外传密钥、原始会话与未脱敏日志。
- 只有经验证可推广且获独立批准的正式候选才可设置 `promotion_candidate: true`；高风险/持久写入应标记 `requires_user_confirmation: true`，未批准只能保留候选。
- 正式规则晋级与高风险持久写入必须经过独立的 human approval；lite AAR 不因此等待审批。
- lite 只要求结果真实、证据可回读、改进可执行、不泄露隐私；不用空白晋级字段阻止普通复盘。
- promotion 必须维持完整审批、评测与回退；用户沉默和静态门禁不等于批准/实际效果。
- 文档保真：不得编造已节省的 Token、时间或人力，以及不存在的实验、负责人和来源。
