# Specialized PR readiness checks — load only for relevant risk

This is supporting guidance; it never authorizes SCM writes.

| Change surface | Required checks when applicable |
|---|---|
| Config/runtime behavior | Config Drift Decision: changed keys, loaded config, behavior impact, rollback |
| Skill assets | source provenance, `global-ready/project-bound`, `core/optional/reject`, runtime install scope |
| DB/API/schema removal | consumers, migration, compatible window, explicit approval, rollback |
| CI/build/release | protected contexts, exact HEAD, CI identity, artifact/provenance, signed release requirements |
| AI-generated PR review | trusted trigger, secret isolation, schema-backed findings, valid inline anchoring; no untrusted SCM payload execution |
| Runtime control plane | Runtime Control Plane Decision, `permission_profile_decision`, `deny-path test`, `approval_boundary`, `runtime_config_diff`, rollback and deny-path observation |
| High-risk field/device operation | device owner, target identity, human authorization, no reliance on source-only CI as hardware evidence |

A small reversible documentation or comment change does not need fake entries for unrelated rows. A missing *applicable* row fails closed; this file does not relax the targeted project Release/Review policy. `adk-verification-before-completion` still owns final task verification and independent reviewer remains separate.
