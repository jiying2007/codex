# Parallel / Worktree Task Package

## Parallel Suitability

- Suitability: yes | no
- Reason:
- Shared boundaries:

## Task Package

```md
[parallel-task]
id:
goal:
owner:
scope_write:
scope_read:
must_not_touch:
dependencies:
verification_commands:
blocked_conditions:
expected_output:
handoff_summary_required: yes
```

## Conflict Matrix

| Task | scope_write | Shared Touchpoint | Conflict Risk | Decision |
|---|---|---|---|---|
| T1 |  |  | low | parallel |

## Worktree Decision

- Need worktree: yes | no
- Branch:
- Worktree path:
- Cleanup requires confirmation: yes

## Final Integration Verification

- Command:
- Expected:
- Evidence path:
