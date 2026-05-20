---
name: embedded-release-orchestration
description: "Use for embedded full-stack release workflows involving SoC, MCU, bootloader, SD upgrade, OTA, firmware-release-tools, ota-packager, build.sh, production/NAS publishing, version tags, release bundles, factory/test guides, and non-overwrite release gates."
version: 1.0.0
last_updated: 2026-05-20
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded Release Orchestration

Use this skill for embedded release flows that cross build, packaging, verification, publication, and production handoff.

## Release Graph

Identify all applicable nodes before editing:

- SoC image, bootloader, partition artifacts, SD upgrade package, OTA image.
- MCU firmware bundles, merged images, flash-full images, checksums, tag state.
- Vehicle or system OTA package that consumes SoC and MCU artifacts.
- Release roots such as NAS, factory share, local release directory, or CI artifacts.
- Audience docs for developers, test, production, and field service.

## Workflow

1. Confirm the release source-of-truth repositories and whether tools must run from source or standalone binaries.
2. Define the release gates:
   - source sync policy;
   - clean/no-clean behavior;
   - build;
   - package;
   - check;
   - dry-run flash/verify;
   - optional real HIL verification;
   - tag creation and tag conflict checks;
   - publish dry-run and publish.
3. Enforce non-destructive publication:
   - stage first;
   - refuse to overwrite existing version directories by default;
   - generate manifest, checksums, and release notes;
   - keep rollback or recovery instructions.
4. For NAS or shared release roots, avoid storing credentials in code, memory, or archive. Use mounted paths or environment variables.
5. Produce shallow, production-readable directories and guides. Avoid requiring production users to understand source tree internals.
6. Validate with the project scripts and record artifact paths, versions, tags, and publish results.

## Safety

- Do not auto-run destructive source cleanup unless the user explicitly approves the flag and scope.
- Do not auto-overwrite published release artifacts.
- Do not echo or persist NAS passwords, private registry credentials, signing secrets, or certificate material.
- Treat missing hardware verification as a residual risk, not as pass.

## Evidence Template

```md
status: pass | needs-fix | BLOCKED
versions:
- soc: <version or n/a>
- mainboard_mcu: <version or n/a>
- motor_mcu: <version or n/a>
artifacts:
- <path>
checks:
- build: <result>
- package: <result>
- check: <result>
- dry-run: <result>
- publish: <result>
risks:
- <remaining risk or none>
```
