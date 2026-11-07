# ADK 10.x retired language-Skill migration (Codex consumer)

The 8.2.0 Codex source set included `adk-chinese-code-review` and
`adk-chinese-commit-conventions`. ADK v10 removes both distinct Skill identities:
output language is policy, not an independent method.

This change removes the **two** obsolete Codex manifest entries and their vendored
copies. Their method coverage remains under `adk-code-review-loop` and
`adk-commit-pr-quality-gate`, which are already present.

## Source and live boundary

- This is a **source-only** change. It does not write `~/.codex` or alter user sessions.
- Existing Codex provider lock remains at exact ADK 8.2.0 for the other reviewed assets.
  No source hash, immutable release, or promotion receipt is relabeled as v10.
- Later upgrade to ADK 10.0.5 (or its current verified successor) must use the
  exact-source importer, signed provenance, full source-set review and a new lock.
- Applying this source to a live Codex installation requires a reviewed
  `build -> doctor -> plan --prune-stale -> dry-run -> apply -> drift` path.
  The retirements must affect only unchanged manifest-owned assets; custom user files
  must be preserved and any drift must fail closed.
- No duplicate aliases or Chinese-vs-English parallel Skill classes are introduced.

## Acceptance

- Retired names are absent from active Codex `manifests/skills.json`.
- Retired vendored directories are absent.
- Surviving review/commit primary Skills remain enabled for supported profiles.
- CI source and governance contracts pass on this exact branch head.
- Runtime deployment and native model behavior require separate, real evidence.
