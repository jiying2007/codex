# Local Skill Lifecycle

This document defines how local and Chronicle-derived Codex skills are used, iterated, and maintained in `~/codex`.

## Scope

This lifecycle applies by default only to local workflow skills whose source is this repository, especially Chronicle-derived skills created from repeated real work.

In-scope examples:

```text
chronicle-workflow-miner
archive-governance
repo-drift-remediation
embedded-release-orchestration
embedded-diagnostic-harness
knowledge-archive
memory-curator
context-compress-handoff
skill-asset-manager
```

Out of scope for local iteration:

- `adk-*` skills imported from `llm_agent/agent-dev-kit`;
- Superpowers plugin skills under `src/codex-home/vendor/plugins/**/skills/`;
- OpenAI, Composio, Anthropic, or other third-party imported skills.

External skills are version-pinned mirrors. Update them by importing a new upstream version and changing `manifests/skills.json`; do not edit their skill body locally unless doing a documented emergency compatibility patch.

## Identification

Use metadata for ownership and lifecycle identification. Do not rename a skill just to show provenance.

Manifest signals:

- local maintained skill: `owner=local`, `source_repo=local/codex`, and `tags` contains `local`;
- Chronicle-derived skill: local maintained skill whose `tags` also contains `chronicle-derived`;
- ADK import: `owner=agent-dev-kit` or `tags` contains `adk`;
- Superpowers fallback: `tags` contains `superpowers` and `fallback`;
- third-party import: `owner` and `source_repo` point to the upstream source.

Chronicle-derived `SKILL.md` frontmatter should include:

```yaml
origin: local-chronicle-derived
lifecycle: iterative-local
```

README should mirror the same human-readable fields:

```text
Origin: local-chronicle-derived
Lifecycle: iterative-local
```

Keep task-oriented names such as `archive-governance` and `embedded-diagnostic-harness`; use tags and metadata for provenance.

## Usage Model

Use a skill in one of three ways:

1. Natural trigger: describe the task normally. `AGENTS.md` and `manifests/workflows.json` route common phrases to the right skill.
2. Explicit trigger: name the skill directly, for example `使用 archive-governance 检查 ~/knowledge-hub/domains/codex/archive/codex-archive`.
3. Supporting trigger: use a domain skill together with an existing gate, for example `embedded-release-orchestration` plus `adk-verification-before-completion`.

Do not force every task through every related skill. Select the smallest set that covers the work:

- one domain skill for the main work;
- one governance or verification skill when risk warrants it;
- one commit or final gate only when preparing delivery.

After new skills are applied to `~/.codex`, a new Codex session may be needed before the runtime skill list shows them.

## Chinese Trigger Policy

Chinese triggers should optimize for the user's natural phrasing without becoming a broad keyword net.

- Prefer phrase-level triggers with object and action, such as `归档元数据修复`, not generic nouns such as `元数据`.
- Keep workflow triggers representative, not exhaustive. Add a phrase only when repeated real usage or a clear routing miss justifies it.
- Avoid ambiguous standalone phrases that belong to several skills. Put disambiguation rules in `AGENTS.md` or the skill body instead.
- Keep command names such as `archive-check` and `archive-search` as compatibility aliases, not as the primary route.
- For local and Chronicle-derived skills, false positives should remove or narrow triggers; false negatives should add one precise phrase or improve the skill `description`.
- After changing triggers, run governance checks and source-to-live apply before relying on the new route.

Archive-related routing follows this split:

- Save, create, or persist a note: `knowledge-archive`.
- Audit, repair, migrate, or enforce archive structure: `archive-governance`.
- Curate, promote, or clean memory: `memory-curator`.
- Handoff, resume prompt, or context compression: `context-compress-handoff`.
- Query historical archive content only: use the archive search entrypoint; do not escalate to `archive-governance` unless index, metadata, status, or naming is broken.

## Iteration Signals

Update an in-scope local skill when there is evidence of repeated friction:

- the user repeats the same workflow three or more times;
- a task routes to the wrong skill;
- a skill triggers too often or too late;
- the skill body lacks a decision rule, output contract, or safety rule;
- the workflow repeatedly needs the same script, template, or validation command;
- the skill causes avoidable token cost;
- a project-specific rule leaks into global behavior;
- verification or secret-handling gaps are found.

Do not update an external imported skill for local workflow friction. Either fix the upstream source and re-import, or create a local companion skill that composes with the external skill.

Do not update a global local skill for one-off project state. Put one-off evidence into `~/knowledge-hub/domains/codex/archive/codex-archive/` or project memory instead.

## Versioning Policy

Use versioned directories as the release boundary.

- `patch`: wording, trigger precision, output template, small safety clarification.
- `minor`: new workflow step, new validation requirement, new reference, broader supported scenario.
- `major`: changed scope, incompatible workflow, renamed responsibility, or migration from project-specific to general use.

For local draft work before commit, editing the current version is acceptable. Once a local skill has been committed and used, prefer creating a new version directory and updating `manifests/skills.json`.

For external imported skills, version bumps must reflect the upstream source version or import reference. Local patch versions should be exceptional and documented in the manifest.

Keep only the active version enabled unless a migration test requires parallel versions. Mark old versions inactive or superseded through manifest governance; do not leave stale active copies.

## Maintenance Workflow

1. Mine evidence:

```bash
rtk rg -n "<trigger or workflow>" ~/.codex/history.jsonl ~/.codex/memories ~/knowledge-hub/domains/codex/archive
```

2. Decide the ownership first:

- local or Chronicle-derived skill: iterate in this repository;
- `adk-*`: update `llm_agent/agent-dev-kit` first, then re-import;
- Superpowers: update the plugin version or fallback mapping, not the copied plugin body;
- other third-party skill: import a new reviewed upstream revision or keep a local companion skill.

3. Decide the change target:

- routing issue: update `description` or `manifests/workflows.json`;
- procedure issue: update `SKILL.md`;
- deterministic repeated operation: add or update a script;
- detailed domain guidance: add a `references/` file;
- long narrative evidence: archive it, do not load it by default.

4. Edit only source assets under `src/codex-home/` and manifests.
5. Run skill and asset validation:

```bash
rtk bash scripts/check-skills.sh
rtk bash scripts/build.sh
rtk bash scripts/doctor.sh --scope all
rtk bash scripts/plan.sh --target ~/.codex --prune-stale --output build/apply-plan.json
rtk bash scripts/apply.sh --plan build/apply-plan.json --dry-run
rtk bash scripts/apply.sh --plan build/apply-plan.json
rtk bash scripts/check-routing-precedence.sh
rtk bash scripts/check.sh
```

6. Record what changed in the final response or commit message.

## Acceptance Criteria

A local skill update is ready when:

- `SKILL.md` frontmatter has `name`, `description`, `version`, and `last_updated`;
- local maintained skills are identifiable by manifest `tags=["local", ...]`;
- Chronicle-derived skills also have `origin: local-chronicle-derived` and `lifecycle: iterative-local`;
- `description` clearly says when to use the skill and when not to;
- `README.md`, `LICENSE`, and `agents/openai.yaml` exist for managed local skills;
- `manifests/skills.json` points to the active version;
- workflow triggers reference registered skills and agents only;
- `check-skills`, `doctor`, source-to-live apply, and `check` pass;
- no secrets, raw sessions, logs, or private runtime state were copied into the skill.

An external skill update is ready when:

- the upstream source, version, reference, and path are recorded in `manifests/skills.json`;
- local changes do not silently fork the upstream skill body;
- build, doctor, apply dry-run, apply, and check pass.

An imported candidate may remain under `src/codex-home/vendor/skills/` only when it is also registered in `manifests/skills.json` with `enabled=false`, an empty profile list, and `review_status=pending`. Candidates with unresolved command context, missing local wrappers, or unverified upstream scripts must not be activated.

## Invocation Metadata Contract

`agents/openai.yaml` uses the current nested metadata shape only:

```yaml
interface:
  display_name: Example
  short_description: Example skill
```

- Required `display_name`/`short_description` and optional `default_prompt`/`icon_small`/`icon_large`/`brand_color` belong under `interface`; legacy top-level interface fields are rejected.
- Implicit invocation is the default and must omit `policy`. Redundant `allow_implicit_invocation: true` is rejected.
- An explicit-only skill must declare `policy.allow_implicit_invocation: false`. No current managed skill is explicit-only without a reviewed routing decision.
- The source checker fails closed on malformed or unknown metadata. There is no compatibility reader for the retired shape.
- Repository-wide metadata normalization is a packaging compatibility migration; it must not alter an imported skill's `SKILL.md` body.

## Command Compatibility

- Local maintained skills must route executable shell examples through `rtk`.
- A local skill's `scripts/...` references must resolve either from the Codex asset repository root or from the skill directory.
- External mirrors are not silently patched to satisfy local command policy; fix them upstream and import a new version.
- If an external skill references repository-specific commands such as `scripts/devkit.sh`, its activation review must identify the required execution repository and a verified fallback. Until then, keep it disabled or treat the command block as unavailable.

## Chronicle-Derived Skills

Chronicle-derived skills must retain an evidence trail:

- source class: history, memory, archive, or repeated current-session workflow;
- repeated workflow summary;
- reason this belongs in a reusable skill instead of archive-only memory;
- validation evidence after registration.

Keep this evidence in a session summary or archive note, not in the loaded `SKILL.md` body.

Current Chronicle-derived local skill set:

- `chronicle-workflow-miner`
- `codex-usage-telemetry`
- `embedded-audio-stream-triage`
- `embedded-app-doc-handoff`
- `embedded-core-dump-triage`
- `embedded-log-triage`
- `embedded-production-test-lifecycle`
- `external-practice-absorption`
- `mcu-firmware-release-closure`
- `patent-disclosure-normalization`
- `protocol-implementation-audit`
- `sigmastar-release-app-flow`
- `windows-gui-release-orchestration`

Review them whenever similar user requests repeat, or when routing behavior becomes noisy.
