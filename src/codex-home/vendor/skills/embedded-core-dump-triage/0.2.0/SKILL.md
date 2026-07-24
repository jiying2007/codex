---
name: embedded-core-dump-triage
description: "Use only for PCR02/SigmaStar/SSC305 embedded Linux core-dump analysis that depends on local prog_pcr02 artifacts, the SigmaStar glibc ARM toolchain, or project-specific release/rootfs evidence. Use adk-offline-core-dump-triage as primary for generic embedded Linux core, BuildID, symbol, or GDB analysis."
version: 0.2.0
last_updated: 2026-07-15
origin: local-chronicle-derived
lifecycle: iterative-local
triggers:
  - "PCR02 core"
  - "SigmaStar core"
  - "SSC305 core"
  - "prog_pcr02 core"
non_triggers:
  - "未指定 PCR02、SigmaStar、SSC305 或 prog_pcr02 的通用 core dump"
  - "只有普通日志而没有 core artifact"
  - "在线 GDB remote 或设备调试通道联调"
---

# PCR02 / SigmaStar Core Dump Triage

Use this local companion when generic core-dump evidence handling must be specialized for the PCR02/SigmaStar release and toolchain environment.

## ADK Composition

- Primary only when the request explicitly names PCR02, SigmaStar, SSC305, `prog_pcr02`, or the known SigmaStar glibc ARM toolchain/rootfs chain.
- Supporting skill under `adk-offline-core-dump-triage` when generic artifact matching has established that the crash belongs to this project-specific environment.
- Mutually exclusive as primary with `adk-offline-core-dump-triage` for generic embedded Linux core requests without project markers.
- Fallback to `adk-offline-core-dump-triage` when the target, toolchain, release bundle, or rootfs is not the known PCR02/SigmaStar flow.

## Inputs

Accept any combination of:

- PCR02/SigmaStar core artifacts such as `core-prog_pcr02-*`;
- matching executable, `.debug.full`, release bundle, board rootfs, or shared libraries;
- crash logs, timestamps, signal, process, thread, and release/version evidence;
- a user-specified cross-GDB path or local PCR02 debugging runbook.

## Workflow

1. Preserve the project evidence boundary: core, executable, symbols, rootfs/libs, source checkout, release version, log window, and requested GDB path.
2. Apply the generic artifact gate from `adk-offline-core-dump-triage`: BuildID/version match, symbol match, debugger startup, register-note readability, and shared-library availability.
3. Apply the PCR02 toolchain specialization:
   - for SSC305 glibc ARM Linux artifacts, prefer `/tools/toolchain/gcc-11.1.0-20210608-sigmastar-glibc-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gdb` when available or explicitly required;
   - downgrade generic host GDB, `arm-none-eabi-gdb`, or stale `/opt` toolchains when ABI, DWARF, register notes, or runtime dependencies do not match;
   - never silently replace a user-specified debugger.
4. Build the crash chain: signal, LWP, PC/LR/SP, trusted frames, mapped library/offset, and the last strong project log marker.
5. Separate crash site, trigger, likely root cause, and blocked evidence; only matched frames may support line-level claims.
6. Request the smallest missing release artifact, board library, symbol file, or instrumentation needed to close the diagnosis.

## Output

Return:

- PCR02/SigmaStar artifact-matching table;
- debugger and rootfs trust status;
- crash timeline and trusted crash chain;
- root-cause boundary with confidence;
- missing evidence and next commands/probes;
- `confirmed`, `partial`, or `blocked` gate result.

## Guardrails

- Do not use this skill as primary for generic core dumps without PCR02/SigmaStar markers.
- Do not claim a source line when BuildID, symbols, GDB, or shared libraries do not match.
- Do not treat `??` frames, corrupt stacks, or unreadable registers as a valid backtrace.
- Do not change code until the user requests a fix after diagnosis.
- Keep private paths and raw crash logs summarized and sanitized.
