---
name: adk-planning-execution-loop
description: 长任务计划审查、分阶段执行、恢复与收口闭环
version: 1.0.0
last_updated: 2026-05-20
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
  - 长任务必须定义 retry budget、staleness threshold 和停止条件
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
1. 计划审查：检查依赖顺序、验证命令、隐含环境假设和阻塞条件。
2. 任务切片：每个阶段输出目标、scope、done criteria、验证命令。
3. 状态外化：建立或更新 `PROJECT/REQUIREMENTS/STATE/PLAN/SUMMARY` 等同类 planning 工件。
4. 执行检查点：每完成一个阶段，更新状态、证据和风险。
5. 恢复记录：维护 `session-state`、`next-actions`、`risk-ledger`、`resume-prompt`。
6. 偏离处理：发现计划错误、共享契约冲突或验证失败时，暂停并回到计划审查。
7. 目标闭环检查：核对原始目标、当前声明、证据、剩余未闭环项和停止条件。
8. 卡死保护：检查 retry budget、heartbeat、staleness threshold 和连续无信息增量轮次。
9. 收口验证：进入完成声明前，执行 completion gate 并核对证据支持结论。
10. 复盘归档：任务完成后输出复盘记录，沉淀经验与改进项。

## Templates
- 长任务恢复与中途改范围处理模板：`references/long-task-recovery.md`。
- 检查点、偏差记录、恢复 prompt 和失败回退锚点都应写入可复用工件，不依赖会话记忆。
- 检查点默认存放在当前 change 或任务目录下；临时材料只能进入 session 级状态，不得进入长期 knowledge。

## Goal Closure / Anti-stall

长任务不能只依赖“执行者认为完成”。必须显式记录目标闭环状态，并把完成声明交给独立验证步骤核对。

- 必填字段：`goal_statement`、`completion_claim`、`required_evidence`、`claimant`、`verifier`、`open_items`。
- 防卡死字段：`retry_budget`、`staleness_threshold`、`heartbeat`、`stop_condition`。
- `verifier` 必须核对证据本身，不能只复述 claimant 结论。
- `stop_condition` 只能是 pass / replan / split / blocked / abort。

## Checkpoint Hygiene
- 每个 checkpoint 必须声明 owner、阶段状态、验证命令、证据路径和下一步。
- checkpoint 连续失败两次时，先更新假设和风险，不继续堆叠同类尝试。
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
- Planning Artifacts:
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
- completion claim 找不到对应证据时，结论固定为 `needs-fix`，并记录缺失证据。

## Quality Gate
- 每个阶段必须有验证证据，禁止无证据的阶段推进。
- 恢复摘要必须能让新会话继续执行，包含完整上下文。
- 目标闭环记录必须能从原始目标追溯到完成声明、证据和剩余风险。
- Anti-stall 检查必须包含 retry budget、staleness threshold、heartbeat 和停止条件。
- 完成结论必须经过 `adk-verification-before-completion`。
- 偏差记录必须完整，包含根因、影响和处理决策。
- 复盘必须在任务完成后 48 小时内完成。
- orphan checkpoint 和过期临时状态必须有保留或删除决策。
