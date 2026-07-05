---
name: mcu-firmware-release-closure
description: Use only for local `/home/leiwenjun/work/mcu` release closure around gd32l235, hc32f072, firmware-release-tools, flash headroom guards, NAS publish, version bumps, release tags, and subrepo/root gitlink sync. Use `adk-embedded-release-orchestration` as primary for generic embedded release planning.
version: 0.1.0
last_updated: 2026-06-28
origin: local-chronicle-derived
lifecycle: iterative-local
---

# MCU Firmware Release Closure

Use this skill as a local companion for `/home/leiwenjun/work/mcu` release work where the expected output is not just a build, but a verified package, publish, tag, and repository state for the known gd32l235/hc32f072 release chain.

## ADK Composition

- Primary only when the task explicitly targets `/home/leiwenjun/work/mcu`, `gd32l235`, `hc32f072`, or the local `firmware-release-tools` release wrapper.
- Supporting skill under `adk-embedded-release-orchestration` for generic "MCU 发布", "NAS 发布", release graph, factory handoff, rollback, or cross-device release planning.
- Supporting skill under `adk-verification-before-completion` when the work is already implemented and only final evidence needs to be checked.
- Mutually exclusive as primary with `adk-embedded-release-orchestration` for broad embedded release requests that do not name the local MCU repositories.
- Fallback to `adk-embedded-release-orchestration` when the target MCU, release root, tag policy, or artifact chain is not one of the local known flows.

## Inputs

Accept any combination of:

- target MCU repositories `gd32l235` and `hc32f072`;
- root repository paths under `/home/leiwenjun/work/mcu`;
- requested version, tag, batch, NAS root, or flash headroom target;
- release tool output, guard reports, package manifests, or checksum files;
- user instructions such as "完整发布", "保留4k余量", "提交并推送", or "会影响 IAP 吗".

## Workflow

1. Establish release scope:
   - identify targets, root repo versus subrepo boundary, current branch, dirty state, remotes, and whether publish/tag/push was explicitly requested;
   - check target-specific `AGENTS.md` and release wrappers before changing files.
2. Preflight versions and guards:
   - locate the version truth, usually target `App/bsp.h` macros;
   - inspect `build_guard_baseline.json`, `build_guard_report.json`, and `build_budget_summary.json` when flash budget blocks release.
3. Respect guard versus runtime boundaries:
   - if changing `app.minFlashHeadroom`, state that it changes release threshold only unless code or layout files also changed;
   - do not imply IAP layout, CRC, metadata, or upgrade behavior changed without evidence.
4. Build and package through stable release tools:
   - prefer `firmware-release-tools` or repo wrapper scripts over ad hoc build commands;
   - keep target release, NAS publish, tag creation, and tag push as separate evidence points.
5. Verify artifacts:
   - check package manifest, checksum verification, output directory, version metadata, and tag target;
   - distinguish release-chain validation from board flash/readback validation.
6. Close repository state:
   - commit subrepos first when requested and only stage intended files;
   - sync parent gitlink/lock after subrepo commits;
   - push only when explicitly requested or when the user asked for full release including remote publication.

## Output

Return:

- release scope and target table;
- version and flash-headroom decision;
- commands run and validation evidence;
- NAS artifact paths or publish identifiers when available;
- tag and push status;
- remaining hardware or field-validation gaps.

## Guardrails

- Do not stop at local build when the user asked for "完整发布".
- Do not call a dry-run or missing debug transport warning a hardware validation pass.
- Do not mix unrelated debug cleanup into a release commit.
- Do not change IAP layout or partition metadata unless that is the explicit task.
- Do not force push, rewrite tags, or publish destructive artifacts without explicit approval.
