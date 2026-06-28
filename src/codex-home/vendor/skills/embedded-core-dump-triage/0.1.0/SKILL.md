---
name: embedded-core-dump-triage
description: Use when the user asks Codex to analyze embedded Linux core dumps, SIGSEGV crashes, BuildID or symbol matching, cross-GDB output, corrupted backtraces, shared-library offsets, or PCR02/SigmaStar `prog_pcr02` crash artifacts.
version: 0.1.0
last_updated: 2026-06-28
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded Core Dump Triage

Use this skill for read-only embedded core dump analysis where the main risk is trusting the wrong binary, symbols, GDB, or stack.

## ADK Composition

- Primary when the user provides or names a core dump, crash artifact, SIGSEGV, BuildID, cross-GDB path, corrupted backtrace, or symbol-matching problem.
- Supporting skill under `adk-systematic-debugging` after core evidence identifies a likely code path and the task moves into root-cause repair.
- Supporting skill under `embedded-log-triage` when the only input is a serial, boot, or dmesg log and no core artifact is available yet.
- Mutually exclusive as primary with `adk-embedded-diagnostic-harness`; harness validation and diag suite semantics stay there.
- Fallback to `adk-systematic-debugging` when there is no core, no symbol artifact, and the root cause remains a general debug problem.

## Inputs

Accept any combination of:

- core file paths or handles such as `core-prog_pcr02-*`, `core-sensor_in0-*`, or `core-nav.*`;
- executable, `.debug.full`, stripped binary, release bundle, or board filesystem paths;
- serial logs, `dmesg`, crash timestamps, signal numbers, process names, and thread names;
- runbooks such as `gdb-debug-guide.md` or project debug scripts;
- user-specified cross-GDB path or toolchain constraints.

## Workflow

1. Preserve evidence boundaries:
   - identify the core, executable, symbol file, source checkout, log window, and whether analysis is read-only;
   - if the user gave a specific GDB path, treat it as a hard constraint before trying alternatives.
2. Match artifacts before interpreting frames:
   - compare BuildID or equivalent note data between runtime binary, debug file, and core context;
   - record when symbols are missing, old, or mismatched, and downgrade line-level claims accordingly.
3. Check debugger trust:
   - verify the selected cross-GDB starts and can read the core;
   - treat startup dependency failures, unreadable register notes, and "core file may not match" warnings as blockers or confidence reducers.
4. Build a crash chain:
   - extract signal, crashing thread/LWP, PC, LR/backtrace, mapped library, offset, and nearby function or source line when reliable;
   - separate the crash site from the likely root cause when the PC lands in a library or logging path.
5. Cross-check with logs and code:
   - align the last strong log events with the crash timestamp;
   - inspect the narrow source path only after artifact matching is acceptable.
6. State confidence and next probes:
   - mark conclusions as `confirmed`, `partial`, or `blocked`;
   - propose the smallest missing artifact, debug symbol, board library, or instrumentation needed next.

## Output

Return:

- artifact matching table;
- debugger trust status;
- crash timeline and crash chain;
- root-cause hypothesis with confidence;
- blocked or missing evidence;
- next commands or probes, without overclaiming from bad symbols.

## Guardrails

- Do not claim a source line or function as root cause when BuildID or symbols do not match.
- Do not treat `??` frames, corrupted stacks, or unreadable registers as valid backtraces.
- Do not switch away from a user-specified GDB path without saying why.
- Do not modify code unless the user explicitly asks for a fix after diagnosis.
- Keep raw core paths and logs concise; avoid echoing long private paths or logs in the final answer.
