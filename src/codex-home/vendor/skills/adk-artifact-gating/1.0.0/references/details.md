---
name: adk-artifact-gating
description: 跨仓库 Artifact 门禁协议——统一标签、状态机与交接规范
version: 1.0.0
last_updated: 2026-05-08
triggers:
  - "artifact 门禁"
  - "跨角色交接"
  - "变更工件"
  - "标签化交付"
non_triggers:
  - 单文件低风险修复且无需跨角色交接
  - 纯探索性代码阅读
inputs:
  - 变更需求、实现范围、验证命令结果、评审结论
outputs:
  - 标签化 artifact 块（ImplementationPlan / ReviewReport / TestReport）
  - 门禁结论（pass / needs-fix / BLOCKED）
  - 交接签收记录
constraints:
  - 所有 artifact 必须包含 status 字段和验证证据
  - 缺少验证证据时结论固定为 needs-fix 或 BLOCKED
  - ReviewReport 与 TestReport 结论不允许矛盾
  - 状态机转换必须经过校验，禁止跳过中间状态
---

# adk-artifact-gating

## Goal

在跨仓库、跨角色交付场景中，用统一的 artifact 标签体系和状态机门禁，消灭"口头完成"和"结论无证据"问题。

## Prerequisites

- 理解 artifact 门禁的基本概念
- 熟悉跨角色协作流程
- 了解状态机转换规则
- 具备基本的文档编写能力

## 来源说明

- **本地实现**：`adk-artifact-gating` 是唯一 artifact 门禁入口
- **Runbook 参考**：`docs/runbooks/artifact-gated-delivery.md`
- **门禁机制**：`adk-verification-before-completion` 的证据核验体系
- **评审标准**：`adk-commit-pr-quality-gate` 的分级评审（blocker/major/minor）

## 模式描述

### 1. 统一 Artifact 标签规范

每个交付物必须使用三类标准标签：

| 标签 | 用途 | 必填字段 |
|------|------|----------|
| `[artifact:ImplementationPlan]` | 实现计划 | status, owner, scope, handoff_to |
| `[artifact:ReviewReport]` | 评审报告 | status, owner, verdict, findings |
| `[artifact:TestReport]` | 测试报告 | status, owner, tests_run |

### 2. 状态机

```
DRAFT → READY → VERIFIED → PASS
                 ↓            ↓
              BLOCKED     NEEDS-FIX → DRAFT（修复后重新进入）
```

**硬约束**：
- `DRAFT → READY`：所有必填字段已填写
- `READY → VERIFIED`：验证命令已执行且结果已记录
- `VERIFIED → PASS`：ReviewReport 和 TestReport 均为 PASS 且结论一致
- 任何阶段发现证据缺失 → 固定为 `BLOCKED` 或 `NEEDS-FIX`

### 3. 交接协议

```md
[handoff]
from: <current-owner>
to: <next-owner>
artifacts:
  - ImplementationPlan: <path> | status: READY
  - ReviewReport: <path> | status: PASS
  - TestReport: <path> | status: PASS
gate_result: pass
signoff: <next-owner> 确认签收
```

### 4. 最小标签模板

```md
[artifact:ImplementationPlan]
status: READY
owner: <agent>
scope:
- <范围>
handoff_to:
- <next-owner>

[artifact:ReviewReport]
status: PASS
verdict: pass | needs-fix

[artifact:TestReport]
status: PASS
tests_run:
- <command + result>
```

### 5. 跨仓库场景适配

- **子仓 → adk**：子仓变更必须产出 TestReport，adk 侧做 ReviewReport
- **adk → explicit tool target**：adk 变更必须先通过 `check-adk-harden-readiness.sh` 与 `runtime-boundary` 门禁，再进入目标运行时适配层
- **多仓联动**：每个仓独立 artifact，汇总为 change-set 后统一门禁

## Commands

```bash
# 检查 artifact 完整性
rg -n "ImplementationPlan|ReviewReport|TestReport" docs/changes/<change-id>/

# 验证状态字段完整性
rg -n "status:" docs/changes/<change-id>/ | grep -v "PASS\|READY\|BLOCKED"

# 门禁检查
bash scripts/devkit.sh verify --change <change-id>

# 签收归档
bash scripts/devkit.sh archive --change <change-id> --evidence docs/changes/<change-id>/
```

## Evidence Template

```md
[gate-summary]
change_id: <change-id>
total_artifacts: 3
passed: 3
blocked: 0
needs_fix: 0
final_decision: pass | needs-fix
handoff_complete: true | false
```

## Quality Gate

1. 三类 artifact 均存在且字段完整
2. ReviewReport 与 TestReport 结论一致
3. 所有验证命令可复现
4. 状态机转换经脚本校验
5. 交接签收记录完整

## Workflow

1. 识别变更范围与影响角色
2. 为每个 artifact 生成统一标签（ImplementationPlan / ReviewReport / TestReport）
3. 填充状态字段（draft → in-review → approved / needs-fix / BLOCKED）
4. 执行验证命令并附加证据
5. 交接签收：接收方确认 artifact 完整性
6. 门禁结论：全部 artifact approved 且无矛盾 → pass

## 待完善事项

- [ ] 跨仓库 artifact 路径标准化（当前各仓路径约定不统一）
- [ ] artifact 自动发现与校验脚本（当前依赖手动检查）
- [ ] 多仓联动时的依赖图自动推导
- [ ] artifact 版本追踪（同一变更的 artifact 演进历史）
- [ ] 与 OpenSpec 变更单元的桥接映射
