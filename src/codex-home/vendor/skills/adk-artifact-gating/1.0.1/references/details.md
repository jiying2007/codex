# adk-artifact-gating — 补充参考资料

此参考文件只提供可选背景、示例和检查提示；当前能力流程、权限、回退与放行结论以 `../SKILL.md`、Manifest 及运行时门禁为准。示例命令不得被解释为写权限授权。

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
