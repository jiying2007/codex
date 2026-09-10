---
name: adk-planning-execution-loop
description: 长任务计划审查、分阶段执行、恢复与收口闭环
version: 1.3.0
last_updated: 2026-09-10
triggers:
  - "执行计划"
  - "多阶段任务"
  - "计划审查"
  - "长任务"
  - "分阶段执行"
  - "恢复摘要"
  - "中途改范围"
  - "失败阶段回退"
non_triggers:
  - 单文件低风险修改
  - 仅做只读分析且无需执行计划
inputs:
  - 计划文件、任务边界、验证命令、阻塞条件、恢复上下文
outputs:
  - 执行检查点、目标闭环记录、恢复摘要、风险台账、完成前验证结论
constraints:
  - 每个阶段必须有明确完成标准和验证证据
  - 阻塞条件不清时不得继续执行
  - 长任务必须定义 retry budget、staleness threshold、计划完整性判定、attestation readback、逻辑任务边界和停止条件
---

# adk-planning-execution-loop

## Goal
- 把长任务从"靠会话记忆推进"改为可恢复、可验证、可审查的执行闭环。
- 通过检查点机制确保每个阶段的产出可独立验证。
- 覆盖嵌入式全栈长任务：芯片/板级 bring-up、启动链/rootfs、Linux BSP 迁移、RTOS 应用联调、驱动到应用链路、上位机产测工具交付、OTA/回滚和现场维护闭环。

## Prerequisites
- 已有需求或计划来源。
- 已明确任务边界、验证命令和停止条件。

## Workflow
1. 计划审查：检查依赖顺序、验证命令、隐含环境假设和阻塞条件；受控生命周期操作先冻结 owner × state × event × resource × termination × invariant 基线。
2. 任务切片：每阶段输出 task-package v2 kind/question/evidence/permission/exit/handoff/retention、scope、done criteria 和验证命令。
3. 状态外化：建立或更新 `PROJECT/REQUIREMENTS/STATE/PLAN/SUMMARY` 等同类 planning 工件。
4. 连续性证明：长任务必须记录 active plan、findings、progress、attestation 和 excluded context。
5. 执行检查点：每完成一个阶段，更新状态、证据和风险。
6. 恢复记录：维护 `session-state`、`next-actions`、`risk-ledger`、`resume-prompt`。
7. 偏离处理：发现计划错误、共享契约冲突、验证失败或 research/prototype 请求实现权限时，暂停并回到计划审查；`design-change` 或连续两轮新 blocker/major finding class 必须 replan。
8. 目标闭环检查：核对原始目标、当前声明、证据、剩余未闭环项和停止条件。
9. 计划完整性检查：无 phase heading 不得报告 `0/0 complete`；混合状态格式按字段核对；stop gate 只有 explicit opt-in、in_progress 和 ledger progress 同时满足才可阻断。
10. 卡死保护：检查 retry budget、heartbeat、staleness threshold 和连续无信息增量轮次。
11. 收口验证：进入完成声明前，执行 completion gate 并核对证据支持结论。
12. 复盘归档：任务完成后输出复盘记录，沉淀经验与改进项；仅在逻辑任务完成、跨会话交接、用户要求归档/提交前检查或 scope/owner 重大变化时执行完整 session-wrap/final gate。

## Templates
- 长任务恢复与中途改范围处理模板：`references/long-task-recovery.md`。
- 连续性证明模板：`templates/context/continuity-attestation.md`。
- 检查点、偏差记录、恢复 prompt 和失败回退锚点都应写入可复用工件，不依赖会话记忆。
- 检查点默认存放在当前 change 或任务目录下；临时材料只能进入 session 级状态，不得进入长期 knowledge。

## Goal Closure / Anti-stall

长任务不能只依赖“执行者认为完成”。必须显式记录目标闭环状态，并把完成声明交给独立验证步骤核对。

- 必填字段：`goal_statement`、`completion_claim`、`required_evidence`、`claimant`、`verifier`、`open_items`。
- 防卡死字段：`retry_budget`、`staleness_threshold`、`heartbeat`、`stop_condition`、`plan_completeness`、`attestation_readback`。
- 收敛字段：`logical_task_open`、`milestone_close`、`session_handoff_required`、`review_round`、`review_mode`、`finding_classes`、`new_finding_class_count`、`consecutive_clean_reviews`、`contract_change_decision`、`replan_reason`。
- `verifier` 必须核对证据本身，不能只复述 claimant 结论。
- `stop_condition` 只能是 pass / replan / split / blocked / abort。

## Checkpoint Hygiene
- 每个 checkpoint 必须声明 owner、阶段状态、验证命令、证据路径和下一步。
- checkpoint 必须保留 work_item_kind、implementation_permission、exit_gate 和 handoff_target；非 implementation 完成后不得直达代码实现。
- checkpoint 连续失败两次时，先更新假设和风险，不继续堆叠同类尝试。
- 验证并行前必须记录资源矩阵；共享输出目录、二进制、缓存、端口或设备的验证串行执行。
- 任务完成或中止后清理 orphan checkpoint，只保留最终摘要、负结果和可复用决策。
- 写入 checkpoint 后运行适用的 lint/test/dry-run，避免半截恢复状态误导下一会话。

## Commands
```bash
# 创建变更提案
bash scripts/devkit.sh propose --change <change-id> --title "<目标>"

# 验证阶段完成
bash scripts/devkit.sh verify --change <change-id>

# 提交评审
bash scripts/devkit.sh review --change <change-id> --result pass --blockers 0 --majors 0 --minors 0

# 检查当前阶段状态
rg -n "status:" docs/changes/<change-id>/checkpoint-*.md

# 导出恢复上下文
cat docs/changes/<change-id>/session-state.md

# 生成复盘报告
bash scripts/devkit.sh archive --change <change-id>
```

## Evidence Template
```md
- Plan Review:
- Stage Checklist:
- Work Item Contract (kind/question/evidence/permission/exit/handoff/retention):
- Planning Artifacts:
- Continuity Attestation:
- Goal Closure:
- Anti-stall Check:
- Session State:
- Next Actions:
- Risk Ledger:
- Resume Prompt:
- Verification Evidence:
- Final Gate:
- Deviation Records:
- Retrospective:
```

## Failure Handling
- 同一验证失败两次仍无根因时，回到假设矩阵并更新风险台账。
- 缺少恢复摘要时，不得声明长任务可交接。
- 若计划偏差超过 30%，必须触发完整计划重审。
- 若检查点连续 3 次阻塞，必须升级到管理层并考虑任务拆分。
- retry budget 用尽或 heartbeat 连续过期时，禁止继续盲目推进，必须 replan、split 或 blocked。
- Runtime Control 的 `idle` 或 required artifact 缺失按 `not_applicable` 单列，不得覆盖已有构建、审查或 source-to-live 证据。
- attestation 写入后必须回读校验；校验失败或计划格式不可判定时，不得作为完成证据。
- completion claim 找不到对应证据时，结论固定为 `needs-fix`，并记录缺失证据。

## Quality Gate
- 每个阶段必须有验证证据，禁止无证据的阶段推进。
- 所有阶段只接受 task-package v2；prototype 必须附 prototype_evidence，v1 或权限冲突固定 needs-fix。
- 恢复摘要必须能让新会话继续执行，包含完整上下文。
- 目标闭环记录必须能从原始目标追溯到完成声明、证据和剩余风险。
- Anti-stall 检查必须包含 retry budget、staleness threshold、heartbeat 和停止条件。
- `targeted-finding-review` 只能关闭对应 finding；受控生命周期任务整体通过前必须有适用的 whole-lifecycle review。
- 完成结论必须经过 `adk-verification-before-completion`。
- 偏差记录必须完整，包含根因、影响和处理决策。
- 复盘必须在任务完成后 48 小时内完成。
- orphan checkpoint 和过期临时状态必须有保留或删除决策。
