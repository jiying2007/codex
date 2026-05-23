# Long Task Recovery Template

## Task State

- Task:
- Current stage:
- Last completed checkpoint:
- Current blocker:
- Changed scope:
- Retry budget:
- Staleness threshold:
- Heartbeat:

## Checkpoints

| Stage | Status | Done Criteria | Verification | Evidence |
|---|---|---|---|---|
| S1 | pending |  |  |  |

## Goal Closure

- Goal statement:
- Completion claim:
- Claimant:
- Verifier:
- Required evidence:
- Open items:
- Stop condition: pass | replan | split | blocked | abort
- Decision: pass | needs-fix | blocked

## Repair Ledger

- Failed scope:
- Passing scope to preserve:
- Minimal rerun:
- Rollback anchor:
- Repair action:
- Semantic verification:
- Do not repeat:

## Scope Change Handling

- Change:
- Impact:
- Decision: continue | replan | split | abort
- Owner:

## Recovery Prompt

```md
Goal:
Completed:
Current state:
Do not repeat:
Next action:
Required verification:
Retry budget:
Staleness threshold:
Open items:
```

## Failure Rollback

- Failed stage:
- Rollback anchor:
- Verification after rollback:
