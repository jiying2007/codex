---
name: adk-artifact-gated-lite
description: 高风险变更时使用轻量 artifact 标签与门禁模板固定交付证据
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "高风险变更"
  - "产物门禁"
  - "追溯证据"
non_triggers:
  - 单文件低风险修复且无需跨团队交接
inputs:
  - 需求说明、实现范围、验证命令
outputs:
  - 标签化交付块、评审结论、测试结论
constraints:
  - 必须包含 artifact 标签和 status 字段
  - 缺少验证证据时必须输出 BLOCKED 或 needs-fix
---

# adk-artifact-gated-lite

## Goal
- 用最小标签集合统一跨角色交付物，避免"结论存在但证据缺失"。
- 提供轻量级门禁流程，区别于全量 artifact-gated 的完整审批链。

## Prerequisites
- 已有明确的变更范围、影响面和验收方式。
- 已准备至少一条可执行验证命令。

## 与全量版的区别
- 全量版：完整审批链（propose → apply → verify → review → archive），适用于跨团队重大变更。
- 轻量版：三步门禁（prepare → verify → decide），适用于单团队高风险变更。
- 轻量版省略 archive 阶段与多级评审，但仍保留证据强制要求。

## Workflow
1. 选择最小 artifact 集合：`ImplementationPlan`、`ReviewReport`、`TestReport`。
2. 每个 artifact 必须写清 `status`、`owner`、`scope`、`inputs`、`handoff_to`。
3. 执行验证命令并记录真实结果，禁止补写或猜测。
4. 形成门禁结论：`pass` 或 `needs-fix`。
5. 若结论为 `needs-fix`，生成修复清单并绑定责任人。
6. 修复完成后重新执行步骤 3-4，直到门禁通过。
7. 输出最终签收记录，包含 artifact 标签与验证证据。

## 状态机
```
DRAFT → READY → VERIFIED → PASS
                 ↓            ↓
              BLOCKED     NEEDS-FIX → DRAFT（修复后重新进入）
```

## 审批模板
```md
[approval-request]
change_id: <change-id>
title: <变更标题>
risk_level: high | medium | low
artifacts:
  - ImplementationPlan: <path>
  - ReviewReport: <path>
  - TestReport: <path>
gate_result: pass | needs-fix | BLOCKED
approvers:
  - <role>: <name> | <status>
decision: APPROVED | REJECTED | PENDING
```

## Commands
```bash
# 检查 artifact 完整性
rg -n "ImplementationPlan|ReviewReport|TestReport" docs/changes/<change-id>/

# 验证变更
bash scripts/devkit.sh verify --change <change-id>

# 提交评审结论
bash scripts/devkit.sh review --change <change-id> --result pass --blockers 0 --majors 0 --minors 0

# 检查状态字段完整性
rg -n "status:" docs/changes/<change-id>/ | grep -v "PASS\|READY\|BLOCKED"

# 列出未完成 artifact
rg -c "status:" docs/changes/<change-id>/ && echo "OK" || echo "INCOMPLETE"

# 生成签收记录
bash scripts/devkit.sh archive --change <change-id> --evidence docs/changes/<change-id>/
```

## Evidence Template
```md
[artifact:ImplementationPlan]
status: READY
owner: <agent>
scope:
- <实现范围>
inputs:
- <上游输入>
handoff_to:
- <next-owner>

[artifact:ReviewReport]
status: PASS
owner: <reviewer>
verdict: pass | needs-fix
findings:
- [severity:high] <问题或 None>

[artifact:TestReport]
status: PASS
owner: <tester>
tests_run:
- <命令与结果>

[gate-summary]
total_artifacts: 3
passed: 3
blocked: 0
needs_fix: 0
final_decision: pass | needs-fix
```

## Failure Handling
- 任一 artifact 缺少 `status` 或验证证据时，结论固定为 `needs-fix`。
- 若发现共享契约变更未标注影响面，立即升级到架构评审。
- 若验证命令执行失败且无法定位根因，切换至 `adk-systematic-debugging`。
- 若修复引入新 artifact，必须重新走完整门禁流程。

## Quality Gate
- 三类 artifact 均存在且字段完整。
- `ReviewReport` 与 `TestReport` 的结论一致，不允许相互矛盾。
- 所有验证命令可复现，失败项必须列出修复责任人。
- 状态机转换必须经过脚本校验，禁止跳过中间状态。
- 最终签收记录必须包含完整证据链。
