# ADK Skill Lifecycle

## Scope

- Skill name:
- Intended profile: core | optional | reject
- Embedded full-stack layer: silicon/board | boot chain | BSP/rootfs | OS/runtime | driver | middleware/protocol | device application | host/production tool | diagnostics | OTA/field | safety/reliability
- Primary scenario:
- Non-goals:

## Creation Gate

| Gate | Decision | Evidence |
|---|---|---|
| Duplicate skill checked | pass |  |
| Trigger overlap checked | pass |  |
| Profile ownership decided | pass |  |
| Reuse threshold met | pass |  |
| Pilot requirement declared | pass |  |
| Fallback / replaced_by declared | pass |  |
| Output contract declared | pass |  |
| Deterministic guard declared | pass |  |
| Evolution evidence declared | pass |  |
| Distribution channel reviewed | pass |  |

## Pattern Classification

| Pattern | Fit | Required hard gate |
|---|---|---|
| Tool Wrapper | wraps CLI/API/MCP | command allowlist, input validation, rollback |
| Generator | creates code/docs/assets | schema or template, overwrite policy, verification |
| Reviewer | evaluates existing work | severity rubric, evidence paths, false-positive handling |
| Inversion | user gives goal, agent controls workflow | explicit stop/ask conditions, state file, owner |
| Pipeline | multi-stage orchestration | code-level state check, checkpoints, resume and abort path |

Pipeline and Inversion skills must not rely only on prose such as "do not proceed". They need executable state checks, structured output validation, or an external workflow gate.

## Reuse Threshold

- First occurrence: solve directly and record only if there is evidence.
- Second occurrence: draft a reusable checklist, template, or reference.
- Third occurrence: consider a Skill only if the workflow has stable inputs, outputs, done criteria, and failure handling.

Reject or keep as `REFERENCE_ONLY` when the candidate is a one-off tutorial, domain showcase, trend list, external marketplace entry, or requires unreviewed tools. Prefer enhancing an existing Skill over creating a parallel one.

## Evolution Evidence Gate

Skill evolution must be evidence-driven and monotonic:

- Group evidence by existing Skill and repeated failure mode before changing the Skill.
- Preserve success invariants from tasks that already pass; a fix that breaks verified paths is rejected.
- Encode only reusable lessons, not one user's local workaround, temporary path, token, tool ranking, or provider promotion.
- Validate candidate updates against representative success and failure examples before promotion.
- Keep rejected updates as review records; do not silently overwrite the active Skill.
- Treat public marketplaces, private registries and shared folders as distribution channels only. They do not prove safety, quality, license compatibility or production readiness.

## Atomicity Rule

Do not embed one Skill inside another Skill as an implicit dependency. Use Agent routing, workflow stages, or `adk-skill-composition-governance` to connect atomic skills. Each Skill must remain useful and testable on its own.

## Output Contract

- Expected artifact:
- Schema/template:
- Pass condition:
- Needs-fix condition:
- Deny-path example:

## Metadata

- version:
- last_updated:
- quality_tier:
- owner:
- review_by:

## Validation

- `bash scripts/devkit.sh validate --strict`
- `bash tests/test_skill_trigger_matrix.sh`
- `bash scripts/pilot-readiness.sh --summary-json`
- `bash tests/run_all.sh`
