# adk-artifact-gating — 补充参考资料

按需加载；示例不增加写权限。

## 来源说明

Runbook：`docs/runbooks/artifact-gated-delivery.md`；证据核验与分级评审分别沿用 `adk-verification-before-completion`、`adk-commit-pr-quality-gate`。

## 模式描述

### 1. 统一 Artifact 标签规范

交付包包含以下标签：

| 标签 | 用途 | 必填字段 |
|------|------|----------|
| `[artifact:ImplementationPlan]` | 实现计划 | status, owner, scope, handoff_to |
| `[artifact:ReviewReport]` | 评审报告 | status, owner, verdict, findings |
| `[artifact:TestReport]` | 测试报告 | status, owner, tests_run |

### 2. 报告与 workflow 状态

`scripts/workflow.sh` 管理 `propose → apply → verify → review → archive`；其 `stage` 不等于 artifact 的 `status`，不强制逐 artifact 状态迁移。

- 计划完整标 READY；报告按实证标 PASS、NEEDS-FIX 或 BLOCKED。
- `review --result pass` 消费 verified 入口和 PASS/PASS 报告；verdict 若有须为 pass，模板要求填写。approved 不是 PASS。
- `review --result needs-fix` 拒绝 PASS/PASS 且 verdict=pass。缺证据保持 NEEDS-FIX/BLOCKED；状态/签收不替代验证或适用的独立 review evidence。

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

以下为真实通过记录；NEEDS-FIX/BLOCKED 配 `verdict: needs-fix`，未验证不预填 PASS。

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
owner: <reviewer>
verdict: pass
findings:
- <finding or none>

[artifact:TestReport]
status: PASS
owner: <test-owner>
tests_run:
- <command + result>
```

### 5. 跨仓库场景适配

- **子仓 → adk**：子仓变更必须产出 TestReport，adk 侧做 ReviewReport
- **adk → tool target**：沿用已核验项目门禁；仅在 llm_agent Root 接入时核实并运行 `check-adk-harden-readiness.sh`/`runtime-boundary`；适用门禁缺失 BLOCKED。
- **多仓联动**：每个仓独立 artifact，汇总为 change-set 后统一门禁
