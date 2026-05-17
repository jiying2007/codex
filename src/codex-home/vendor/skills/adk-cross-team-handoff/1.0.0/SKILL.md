---
name: adk-cross-team-handoff
description: 跨团队交接时统一目标、边界和验收责任
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "团队交接"
  - "模块移交"
  - "跨团队"
non_triggers:
  - 同团队内小范围任务流转
inputs:
  - 当前方案、风险列表、待办事项
outputs:
  - 交接清单、责任矩阵、验收计划
constraints:
  - 必须明确 owner、截止时间与验收条件
---

# adk-cross-team-handoff

## Goal
- 在交接窗口内冻结边界、责任与验收口径，避免"交接后才发现缺口"。
- 确保交接完成后双方对状态、风险和后续行动有共同认知。

## Prerequisites
- 已明确交接对象、窗口时间与系统边界。
- 已汇总当前版本、风险清单与未决事项。

## Workflow
1. 盘点范围内资产、接口和运行约束。
2. 输出责任矩阵（RACI）与关键时间点。
3. 切分 section ownership：每个模块/文档只允许一个主负责人，其他人只评审不并行改写。
4. 对未决风险给出处置策略：继续推进、延期、降级或冻结。
5. 约定验收证据、回退路径和升级通道。
6. 执行签收流程：交接方签字 → 接收方确认 → 批准方备案。
7. 若签收后发现问题，触发回滚方案并重新评估。

## RACI 责任矩阵模板
```md
| 模块/任务        | Responsible | Accountable | Consulted | Informed |
|------------------|-------------|-------------|-----------|----------|
| <module-1>       | <team-A>    | <lead>      | <team-B>  | <stakeholder> |
| <module-2>       | <team-B>    | <lead>      | <team-A>  | <stakeholder> |
| 验收测试         | <team-B>    | <lead>      | <team-A>  | <all>    |
| 文档移交         | <team-A>    | <lead>      | <team-B>  | <all>    |
```

## 交接清单模板
```md
[handoff-checklist]
change_id: <handoff-id>
from_team: <团队A>
to_team: <团队B>
window: <开始时间> ~ <结束时间>

# 资产清单
- [ ] 源代码仓库权限移交
- [ ] 文档链接与访问权限
- [ ] 配置文件与环境变量清单
- [ ] 监控告警配置说明
- [ ] 运维手册与应急联系人

# 风险清单
- [ ] 已知风险 + 处置策略
- [ ] 未决事项 + owner + 截止时间

# 验收条件
- [ ] 冒烟测试通过
- [ ] 接收方确认功能正常
- [ ] 文档完整性检查通过
```

## 签收流程
```
交接方准备 → 接收方审核 → 试运行（可选） → 双方签字 → 批准方备案 → 交接完成
     ↓                ↓
  needs-fix        needs-fix → 回到交接方准备
```

## 回滚方案
```md
[rollback-plan]
trigger_condition: <触发回滚的条件>
rollback_steps:
  1. 通知双方团队
  2. 恢复原负责人权限
  3. 回退配置变更
  4. 验证回退后系统状态
rollback_deadline: <回滚截止时间>
escalation: <升级通道>
```

## Commands
```bash
# 检查遗留问题
rg -n "@deprecated|TODO|FIXME|HACK" <module_path>

# 查看变更文件清单
git diff --name-status <handoff-base>...HEAD

# 检查权限配置
ls -la <module_path>/.access

# 验证文档完整性
find docs/ -name "*.md" | xargs wc -l | sort -n

# 生成交接报告
bash scripts/devkit.sh verify --change <handoff-id>

# 检查签收状态
rg -n "sign-off|签字|确认" docs/changes/<handoff-id>/
```

## Evidence Template
```md
- Scope and Exclusions:
- Owner Matrix (R/A/C):
- Section Ownership:
- Open Risks + Decisions:
- Acceptance Evidence:
- Rollback Path:
- Escalation Channel:
- Sign-off (handoff / receiver / approver):
- Handoff Checklist Status:
- Post-handoff Issues:
```

## Failure Handling
- 若 owner 或验收条件未明确，结论必须为 `needs-fix`，禁止进入交接完成态。
- 若发现共享契约未冻结，必须升级到架构评审后再继续交接。
- 若签收后 48 小时内出现阻塞问题，自动触发回滚方案。
- 若接收方无法在窗口期内完成验收，必须延期并通知所有相关方。

## Quality Gate
- 交接文档必须覆盖范围、风险、验收、回退与升级通道。
- 每个关键模块必须有唯一主负责人，禁止责任重叠。
- RACI 矩阵必须覆盖所有交接模块与关键任务。
- 签收记录必须包含三方签字（交接方、接收方、批准方）。
- 回滚方案必须经过至少一次 dry-run 验证。
