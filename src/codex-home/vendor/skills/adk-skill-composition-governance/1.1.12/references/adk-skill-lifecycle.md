# ADK Skill Lifecycle

## Scope

- Skill name:
- Intended profile: core | optional | reject
- Embedded full-stack layer: silicon/board | boot chain | BSP/rootfs | OS/runtime | driver | middleware/protocol | device application | host/production tool | diagnostics | OTA/field | safety/reliability
- Primary scenario:
- Non-goals:

## Creation Gate

Initialize with known Scope, the complete Creation Gate and a next review entry. Expand other sections only when the current stage and evidence require them; do not fill the whole template at once. Blank rows are pending; set decisions only from actual review results and link their evidence.

| Gate | Decision | Evidence |
|---|---|---|
| Duplicate skill checked | pending |  |
| Trigger overlap checked | pending |  |
| Profile ownership decided | pending |  |
| Reuse threshold met | pending |  |
| Pilot requirement declared | pending |  |
| Fallback / replaced_by declared | pending |  |
| Output contract declared | pending |  |
| Deterministic guard declared | pending |  |
| Evolution evidence declared | pending |  |
| Distribution channel reviewed | pending |  |

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

For a one-off tutorial, domain showcase, trend list, marketplace entry or unreviewed tool, retain only justified reference evidence. Root intake decisions remain `ADOPT/MERGE/ENHANCE/OBSERVE/REJECT`; reference-only retention is not another decision enum. Prefer enhancing an existing Skill over creating a parallel one.

## Evolution Evidence Gate

Skill evolution must preserve verified behavior and use evidence:

- Group evidence by existing Skill and repeated failure mode before changing the Skill.
- Preserve success invariants from tasks that already pass; a fix that breaks verified paths is rejected.
- Encode only reusable lessons, not one user's local workaround, temporary path, token, tool ranking, or provider promotion.
- Validate candidate updates against representative success and failure examples before promotion.
- Keep rejected updates as review records; do not silently overwrite the active Skill.
- Treat public marketplaces, private registries and shared folders as distribution channels only. They do not prove safety, quality, license compatibility or production readiness.

## Skill Behavior RED → GREEN → REFACTOR

- **RED**：常规改版以现行 Skill（champion/baseline）为基线，复用可信失败；首次价值或负收益调查才另设 no-skill。没有运行证据则为 `not-measured`。
- **GREEN / REFACTOR**：只改一个机制，复验失败与旧成功，删除无收益规则并保留否决原因；质量/权限不退化后才比较实际成本。
- **验收**：开发与选型案例不作最终留出集；冻结候选、grader、样本和重复门槛，独立盲评后分别判断静态、真实行为、原生 discovery/load 与端到端结果。评测证据 E2–E4 不是执行投入 `execution_effort` 的编号，缺测只可声明已验证的源码范围。

完整协议与七字段方法记录见 [skill-behavior-evaluation.md](skill-behavior-evaluation.md)；沿用现有 change/effect 证据，不复制新台账或启用付费/后台调用。

## Failure Feedback → Deterministic Regression (conditional)
- First freeze an actual, redacted `failure_trace_ref`, `source_sha`, expected/observed, error class and affected Skill; if evidence is only a hypothetical example, label it `design-case`, not a reproduced failure.
- Classify whether the correction is stable and testable: use the **existing** trigger matrix for misrouting, an existing fixture/contract test for schema or permission mistakes, and an approved real-host trial only for semantic task-quality failures. Do not add tests that simply search for the new slogan while missing the behavior.
- Write the smallest positive/negative case with an explicit forbidden outcome; show the deterministic RED if runnable, apply the minimal Skill change, then show GREEN and check previously passing examples. When RED cannot run, record `not-run` and keep the effect `not-measured`.
- Train-case failures can guide edits; reserve frozen holdout cases for final comparison. Do not contaminate holdout, auto-approve rules, rewrite global instructions or leak raw transcripts/credentials.
- Avoid a universal "one correction = one new rule" policy: consolidate repeats by failure cause; retire ineffective instructions after observed regression and owner review.

## Lifecycle Review (report-only)
- Stop a candidate at its registered budget or when another retry has no new evidence; retain the failed attempt and a specific resume condition. Missing runtime access is not a reason to create recurring inspection or claim success.
- Review operational states as `active / deprecation-candidate / deprecated / retired` **only as analyst labels** unless the canonical ADK Manifest explicitly supports that value; never silently add unsupported lifecycle enums or a second state registry.
- Consider verified use, true route overlap, actual task outcomes, target profile footprint, replacement availability, consumer compatibility and rollback evidence. Inactivity or directory age alone is not a reason to delete a Skill.
- For proposed retirement, record `candidate / evidence / owner_decision / replacement / affected_profiles / fallback / required_and_forbidden_footprint / rollback`. Without consent, native evidence or verified replacement, leave the active asset unchanged.

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
