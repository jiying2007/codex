# Parallel / Worktree Task Package

Actual workers/worktrees/handoff only; else `Parallel Suitability: no` and serial.

```md
[parallel-task]
id:
goal:
owner:
primary_skill:
work_item_kind: decision | research | prototype | implementation
question_to_resolve:
evidence_required:
implementation_permission:
exit_gate:
handoff_target:
retention_decision:
scope_read:
scope_write:
global_constraints:
interfaces:
must_not_touch:
dependencies:
model_or_capability_tier:
verification_commands:
blocked_conditions:
expected_output:
ready_to_handoff:
report_schema: DONE|BLOCKED|NEEDS_CONTEXT + verified facts/inferences + source refs + changes + tests
context_noise_budget: summary cap + evidence refs + raw retention + redaction + parent merge policy
handoff_artifact_policy: data-only; no same-command generated-script execution; provenance required
```

## Canonical v2 mapping

人类信封不能直接转为 v2 JSON；保留同名合法字段，其余按表映射、补齐 canonical 必填项并校验。ready_to_handoff 写完成条件，实际状态留报告；身份/策略可保留宿主外层，scope 不丢、权限不扩。

| 信封字段 | v2 字段 |
|---|---|
| scope_read / scope_write / must_not_touch / global_constraints / interfaces | constraints |
| id / owner / primary_skill / dependencies / model_or_capability_tier / report_schema / context_noise_budget / handoff_artifact_policy | context |
| verification_commands | verification |
| blocked_conditions | blockers |
| expected_output | artifacts |
| ready_to_handoff | done_when |

## Checks
- Shared files/contracts/devices: one writer or serialize. Reviewer stays read-only; report spec/quality and `cannot-verify-from-diff`.
- Artifact: producer, task, timestamp, hash/provenance; commands remain data. Parent owns whole-diff/integration; cleanup needs user/host authorization.
- `templates/planning/worker-contract.md` is optional at a verified ADK source root where the file exists; scope checks: `subagent-review-checklist.md`.
