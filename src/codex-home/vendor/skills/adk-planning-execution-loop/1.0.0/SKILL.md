---
name: adk-planning-execution-loop
description: 长任务计划审查、分阶段执行、恢复与收口闭环
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "执行计划"
  - "多阶段任务"
  - "计划审查"
non_triggers:
  - 单文件低风险修改
  - 仅做只读分析且无需执行计划
inputs:
  - 计划文件、任务边界、验证命令、阻塞条件、恢复上下文
outputs:
  - 执行检查点、恢复摘要、风险台账、完成前验证结论
constraints:
  - 每个阶段必须有明确完成标准和验证证据
  - 阻塞条件不清时不得继续执行
---

# adk-planning-execution-loop

## Goal
- 把长任务从"靠会话记忆推进"改为可恢复、可验证、可审查的执行闭环。
- 通过检查点机制确保每个阶段的产出可独立验证。

## Prerequisites
- 已有需求或计划来源。
- 已明确任务边界、验证命令和停止条件。

## Workflow
1. 计划审查：检查依赖顺序、验证命令、隐含环境假设和阻塞条件。
2. 任务切片：每个阶段输出目标、scope、done criteria、验证命令。
3. 执行检查点：每完成一个阶段，更新状态、证据和风险。
4. 恢复记录：维护 `session-state`、`next-actions`、`risk-ledger`、`resume-prompt`。
5. 偏离处理：发现计划错误、共享契约冲突或验证失败时，暂停并回到计划审查。
6. 收口验证：进入完成声明前，执行 completion gate 并核对证据支持结论。
7. 复盘归档：任务完成后输出复盘记录，沉淀经验与改进项。

## 计划-执行循环状态机
```
PLAN → READY → EXECUTING → CHECKPOINT → CONTINUE
  ↑       ↓        ↓            ↓
  └── BLOCKED    DEVIATE → PLAN (重新审查)
                   ↓
              NEEDS-FIX → PLAN
```

## 检查点设计模板
```md
[checkpoint]
stage_id: <阶段编号>
stage_name: <阶段名称>
status: pending | executing | done | blocked | deviate
started_at: <时间>
completed_at: <时间>
done_criteria:
- <验收条件 1>
- <验收条件 2>
verification_commands:
- <命令 1>: <结果>
- <命令 2>: <结果>
evidence:
- <证据路径或描述>
risks_identified:
- <风险描述 + 影响>
next_actions:
- <下一步动作>
```

## 偏差处理流程
```md
[deviation-record]
detected_at: <时间>
stage_id: <阶段编号>
deviation_type: plan_error | contract_conflict | verification_failure | resource_unavailable
description: <偏差描述>
impact: <影响范围>
decision: replan | skip | abort | workaround
resolution: <处理方式>
```

## 复盘模板
```md
[retrospective]
task_id: <任务ID>
total_stages: <阶段数>
completed_stages: <完成数>
blocked_stages: <阻塞数>
deviation_count: <偏差次数>

what_went_well:
- <做得好的方面>

what_could_improve:
- <改进点>

action_items:
- <改进动作 + owner + due>
```

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

## Quality Gate
- 每个阶段必须有验证证据，禁止无证据的阶段推进。
- 恢复摘要必须能让新会话继续执行，包含完整上下文。
- 完成结论必须经过 `adk-verification-before-completion`。
- 偏差记录必须完整，包含根因、影响和处理决策。
- 复盘必须在任务完成后 48 小时内完成。
