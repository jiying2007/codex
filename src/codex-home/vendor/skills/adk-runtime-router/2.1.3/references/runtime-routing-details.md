# Runtime Routing Details

Load this reference only when routing is ambiguous, a fallback must be justified, or detailed evidence/rationalization handling is required. Do not load it for routine low-risk routing.

## Task Routing

| Task type | Primary Skill | Supporting Skills | Internal fallback |
|---|---|---|---|
| Requirements unclear | `adk-requirements-triage` | `adk-task-breakdown` | Stay in triage until boundaries are testable |
| Test strategy / TDD / regression | `adk-test-strategy` | `adk-unit-test-embedded` | Project-declared test workflow |
| Multi-module / parallel planning | `adk-task-breakdown` | `adk-parallel-agent-governance` | Serial execution when sub-agents are unavailable |
| Worktree isolation | `adk-worktree-governance` | `adk-task-breakdown` | User-managed branch only when explicitly requested |
| Unknown-root-cause bug / failing test | `adk-systematic-debugging` | `adk-verification-before-completion` | Domain-specific declared workflow |
| Code review / review feedback | `adk-code-review-loop` | `adk-commit-pr-quality-gate` | Dedicated review system only when required |
| Completion / commit / PR | `adk-verification-before-completion` | `adk-commit-pr-quality-gate` | Explicit user-requested path |
| Branch closeout | `adk-branch-closeout` | `adk-verification-before-completion` | Manual steps if remote PR tooling is unavailable |
| Release / version / rollback | `adk-release-versioning` | `adk-commit-pr-quality-gate` | Project-declared release workflow |
| Multiple skill conflict | `adk-runtime-router` | `adk-skill-composition-governance` | Explicit AGENTS.md arbitration if governance skill is unavailable |

## Tool Routing

Use progressive disclosure rather than loading a whole tool or skill catalog:

1. Read `namespace_summary` and trigger/boundary metadata.
2. Rank likely candidates without fetching full schemas.
3. Load only the selected `deferred_surface`.
4. Record `loaded_tools` and `schema_review` before mutation.
5. Prefer the Best Tool for Task, not the most familiar tool.
6. Keep discovery/retrieval errors distinct from execution or verification success.

For Code Intelligence, preserve the `code_intelligence_provider_contract` evidence tuple: provider, tool, query, repo_ref, hit_summary, decision impact. For Tool Search, preserve namespace, query, selected surface, loaded tools and schema review.

## Fallback and Failure Semantics

- `no match`: do not invent a skill. Use triage or no-skill/needs-input and record the gap.
- `ambiguous`: compare boundaries and lifecycle order; keep one primary only.
- `retrieval failed`: record the failed retrieval and use only a declared fallback with evidence.
- Missing supporting skill: low-risk tasks may use an inline check; medium/high-risk tasks retain an evidence gap until resolved.
- External reference repository: never becomes runtime fallback, install source or implicit dependency.
- Any fallback must include reason, exit condition and verification path.

## Evidence Depth

- L1: bounded routing summary for routine low-risk work.
- L2: targeted source/schema evidence when a decision needs disambiguation.
- L3/raw: high-risk, low-confidence, safety-sensitive, missing-raw-evidence or mutation-critical decisions.
- Compression and summaries reduce active context; they never replace retained raw evidence or mutation review.

## Rationalization Guard

| Rationalization | Why it is unsafe | Required response |
|---|---|---|
| “This is a small task, routing is unnecessary.” | Small tasks can still mutate files or require verification. | Emit a lightweight route decision. |
| “The user named an external Skill, so load it.” | Naming does not expand the runtime trust boundary. | Map intent to native ADK; otherwise no-skill/needs-input. |
| “Several skills are useful, use all as primary.” | Multiple entry owners create conflicting control flow. | Choose one primary; keep others supporting. |
| “Natural language did not match, skip routing.” | Silent misses repeatedly weaken routing reliability. | Add trigger/routing regression coverage. |
| “The fallback is familiar, so it is good enough.” | Familiarity is not evidence. | Record fallback reason, evidence and exit condition. |

## Verification Checklist

- Exactly one primary skill.
- Supporting skills have explicit roles.
- Tool/Skill Evidence Plan exists for medium/high risk.
- `namespace_summary` precedes `deferred_surface` for large catalogs.
- `loaded_tools` and `schema_review` are recorded when applicable.
- `no match`, `ambiguous`, `retrieval failed` remain fail-closed states.
- High-risk decisions retain L3/raw evidence.
- Any changed trigger, routing rule, threshold or classifier receives positive and negative regression coverage.
