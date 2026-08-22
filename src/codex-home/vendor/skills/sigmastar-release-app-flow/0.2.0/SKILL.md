---
name: sigmastar-release-app-flow
description: Use for PCR02/SigmaStar build-flow or release-evidence diagnosis around `build.sh`, compile/app/image/OTA ordering, NAS package audit, dirty-source candidate artifacts, customer partition layout, UBIFS/SquashFS, toolchain PATH, `SStarOtaLayout.txt`, rollback evidence, and lightweight app-build dependencies. Use `adk-embedded-release-orchestration` as primary for generic release orchestration.
version: 0.2.0
last_updated: 2026-08-22
origin: local-chronicle-derived
lifecycle: iterative-local
---

# SigmaStar Release App Flow

Use this skill for PCR02/SigmaStar release-chain problems where build order, partition selection, or SDK library preparation determines whether artifacts actually contain the intended app or filesystem.

## ADK Composition

- Primary when the task names PCR02/SigmaStar build-flow details such as `build.sh app`, `compile`, `image`, `SStarOtaLayout.txt`, `customer`, UBIFS/SquashFS, or SDK wrapper libraries.
- Supporting skill under `adk-embedded-release-orchestration` when the task is a full release with publish/tag/rollback evidence.
- Supporting skill under `adk-systematic-debugging` when the issue starts as a failing build, missing toolchain, or target-side behavior with unclear root cause.
- Mutually exclusive as primary with `mcu-firmware-release-closure`; this skill is for SigmaStar/PCR02 SoC release flow, not MCU firmware bundles.
- Fallback to `adk-embedded-release-orchestration` when the request is only generic OTA/NAS/release planning and does not depend on PCR02/SigmaStar layout details.

## Inputs

Accept any combination of:

- PCR02 release workspace paths such as `/vsdata/leiwenjun/pcr02_ssc305_release`;
- `build.sh` mode, release flow, defconfig, toolchain path, or compile logs;
- OTA layout files such as `SStarOtaLayout.txt`, release manifests, or version metadata;
- customer filesystem mode, UBIFS/SquashFS decision, partition preserve requirements, or boot logs;
- app link failures involving `cam_fs_wrapper`, `cam_os_wrapper`, or SDK-side library prep.

## Workflow

1. Identify the artifact chain:
   - distinguish `compile`, `full`, `release`, `image`, and `app` mode;
   - note whether the user needs regenerated image/OTA artifacts or only local app compilation.
2. Check authoritative layout evidence:
   - inspect `SStarOtaLayout.txt`, release metadata, and package manifests before changing policy;
   - treat release-flow names as hints, not proof of upgraded partitions.
3. Respect partition preserve constraints:
   - explicitly track `/factory`, `/data`, `/ota`, and customer partition preservation requirements;
   - avoid whole-`ubia` rewrites when the task is regular OTA or customer-only update.
4. Fix environment at the right layer:
   - compare top-level `build.sh` environment setup with direct lower-level `make`;
   - keep lightweight `app` mode light, and move SDK library preparation to `compile`, `full`, or `release` when needed.
5. Reason about build order:
   - if app is rebuilt after image/OTA generation, state that the new app is not inside existing image/OTA artifacts;
   - regenerate artifacts when the requested output must include new app or filesystem content.
6. Trace evidence layers:
   - keep `source -> build -> package -> published -> installed -> device/rollback` separate;
   - a dirty-source build can identify a candidate package by hash but cannot prove a clean source commit;
   - manifest/checksum evidence proves package integrity, not installation, boot, business smoke, or rollback.
7. Validate with artifacts and boot evidence:
   - check layout, version files, release manifest, and boot log mount path;
   - state residual risk when no target upgrade or boot evidence exists.

## Output

Return:

- mode and artifact-chain diagnosis;
- authoritative layout and metadata evidence;
- patch or command plan by layer;
- validation commands and results;
- whether generated image/OTA includes the latest app;
- evidence-layer table and any dirty-source binding;
- remaining target-side evidence gaps.

## Guardrails

- Do not make `app` mode heavier to fix system-level SDK preparation unless the user explicitly accepts it.
- Do not assume an app rebuild changed already-generated image or OTA packages.
- Do not overwrite preserved partitions unless explicitly requested and validated.
- Do not rely on release-flow names without checking concrete layout output.
- Do not claim boot success from repository config alone; require boot log or target evidence.
