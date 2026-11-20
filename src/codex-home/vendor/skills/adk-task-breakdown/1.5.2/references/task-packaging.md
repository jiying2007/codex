# Machine task package（按需）

v2 仅允许下例19个顶层字段；按真实任务替换值，不构成授权或执行证据。

<!-- adk-example: task-package-v2 -->
```json
{
  "structured_output_schema": "adk-task-package-schema-v2",
  "strict_schema_decision": true,
  "refusal_handling": "blocked or replan",
  "goal": "Check the retry deadline",
  "context": "Frozen source and authorized read scope",
  "constraints": ["scope_read: src/retry.py", "scope_write: []", "global_constraints: read-only", "interfaces: retry deadline"],
  "done_when": ["Boundary evidence reviewed"],
  "primary_action": "inspect",
  "action_mode": "read-only",
  "verification": ["Read the boundary assertion"],
  "artifacts": ["review.md"],
  "blockers": [],
  "work_item_kind": "research",
  "question_to_resolve": "Is equality at the deadline allowed?",
  "evidence_required": ["Condition and boundary test"],
  "implementation_permission": "forbidden",
  "exit_gate": "evidence-reviewed",
  "handoff_target": "task-owner",
  "retention_decision": "keep-final"
}
```

## Types / rejection

`strict_schema_decision` 为 boolean true；其余如例为非空字符串或字符串数组。`constraints/blockers` 可空，其余数组非空，元素均非空。`retention_decision` 仅 `keep-final/archive-negative-result/delete-orphan/expire`。

| work_item_kind | implementation_permission | exit_gate |
|---|---|---|
| decision | forbidden | owner-decision |
| research | forbidden | evidence-reviewed |
| prototype | forbidden | prototype-reviewed |
| implementation | approved | implementation-verified |

prototype 的 `artifacts` 另须 `prototype_evidence:<非空路径>`；非 implementation 不写产品代码。缺/多字段、错误类型或上述组合失败须 blocked/replan，不强转、不放宽 schema。使用接收方真实 validator；不可用时标未验证。

## Scope / scheduling

`scope_read/scope_write/global_constraints/interfaces` 在 v2 映射为 `constraints` 字符串条目，不丢弃边界。owner、DAG、`ready_to_handoff` 和 worker/report 设置属于外层派工信封，不加进 v2。信封有独立接收合同，不能替代 v2 校验或成为授权来源。

Worker attempt 不改 owner/授权；仅证据或冲突变化重算 Ready Frontier。
