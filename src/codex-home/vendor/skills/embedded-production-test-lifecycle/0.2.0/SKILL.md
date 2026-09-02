---
name: embedded-production-test-lifecycle
description: "Use when the user asks Codex to analyze or change an embedded factory/product-test application's aging, calibration, PCBA/factory test, health bitmap, stale timeout, station handoff, restart persistence, calibration false/unknown state, failure latches, repeated tool connections, asynchronous idempotency, or resource quiescing. Use for lifecycle and production-flow behavior rather than only diagnostic CLI return-code validation."
version: 0.2.0
last_updated: 2026-08-22
origin: local-chronicle-derived
lifecycle: iterative-local
triggers:
  - "厂测异常"
  - "老化 TOF"
  - "健康位图"
  - "电机校准 false"
  - "PCBA 标定"
  - "标定重复触发"
non_triggers:
  - "仅校验 diag 返回码"
  - "普通驱动 bring-up 且没有产测或生命周期状态"
---

# Embedded Production Test Lifecycle

Audit production-test behavior as a stateful station workflow, not as isolated test functions.

## Inputs

Accept any combination of:

- product-test, aging, calibration, or factory-test application source;
- INI/profile configuration, stage definitions, state files, failure bitmaps, and station requirements;
- device, operator-tool, serial, storage, health, restart, and resource-lifecycle logs;
- expected transitions, completion rules, persistence constraints, and allowed operator actions;
- module health sources such as battery, motor, IR, ToF, IMU, microphone, camera, storage, or network.
- health-frame cadence, stale thresholds, failure bitmaps, calibration cache fields, and calibration precondition transactions.

## Workflow

1. Fix the lifecycle contract:
   - draw stages, entry/exit conditions, owners, allowed transitions, terminal states, and station handoff;
   - distinguish production behavior, debug shortcuts, recovery behavior, and operator-tool behavior.
2. Audit transition idempotency:
   - trace duplicate connections, repeated commands, interrupted tools, timeouts, reconnects, cancellation, and asynchronous completion;
   - define whether a repeated request resumes, reports current status, safely restarts, or is rejected without marking a good unit failed.
3. Audit persistence and restart semantics:
   - classify state as transient, session-scoped, station-scoped, or durable;
   - verify atomic writes, versioning, corruption handling, monotonic versus wall-clock time, and storage-unavailable behavior;
   - state exactly when success, failure, first-failure evidence, elapsed time, and session identity are retained or cleared.
4. Audit health aggregation:
   - map each module to freshness, unknown, pass, fail, recovery, and timeout semantics;
   - never treat missing or stale data as pass;
   - separate current health from latched evidence and define when a new run may clear prior failure state.
   - align producer cadence with consumer stale timeout; retain `read_ok` separately from a false/zero status value so a successful read is not retried as an error.
   - make bitmap bit ownership, freshness, unknown, special-item, and clear-on-new-session rules explicit.
5. Audit calibration transactions:
   - define preconditions, ordered actions, per-step diagnostics, idempotency, and the point at which a failed precondition blocks or merely annotates calibration;
   - distinguish cached static calibration state from live calibration progress and result.
6. Audit resource ownership and shutdown:
   - trace audio, laser, camera, display, DVR, files, mounts, workers, and device handles across every transition;
   - stop producers before consumers, flush or close writers before unmount or format, and prevent the next stage from racing cleanup;
   - preserve operator-visible progress when safe without hiding a failed transition.
7. Audit contract compatibility:
   - compare device state, upper-computer commands, progress reports, return codes, and persisted schema;
   - flag old/new tool or firmware compatibility explicitly instead of silently changing wire or state formats.
8. Build a failure-oriented validation matrix:
   - cover success, explicit failure, incomplete run, power loss, restart, missing or read-only storage, corrupted state, duplicate connection, repeated command, module timeout, cleanup failure, and station handoff;
   - separate host/SIL evidence from real-board/HIL and operator-flow evidence.
   - bind every operator-flow result to station identity, tested firmware/application revision, profile/config digest, and tool version; stale device binaries or profile drift invalidate a product-flow claim until rechecked.
9. Produce the smallest safe change:
   - prefer local state-machine, persistence, health, or cleanup fixes over unrelated module refactors;
   - hand validation evidence to the normal test and completion gates.

## Decision Rules

- Preserve a qualified-success latch across restart only when the station contract requires later consumption of that result.
- Do not clear failure evidence merely because the process restarted; clear it only at an explicit new-session boundary.
- Treat unavailable persistence as an explicit degraded or blocked state, not as a fresh pass.
- Keep debug auto-complete or shortened-duration paths disabled in production profiles.
- Make resource cleanup bounded and observable; a stage transition is incomplete until required resources are quiesced.
- Treat a calibration, aging, or health success as product evidence only when the tested station, device build, profile, and operator-tool contract are identified; a Host simulation is source/SIL evidence only.

## Output

Return:

- a lifecycle and ownership model;
- persistence and health-field semantics;
- findings ranked by safety, false-pass, false-fail, and operability risk;
- a minimal patch plan or implementation;
- a restart/failure/station validation matrix;
- a gate result: `stable`, `needs-more-data`, `needs-fix`, or `unsafe-to-ship`.

## Guardrails

- Do not encode one product's station names, paths, or private protocol into the reusable procedure.
- Do not treat a build-only result as production-flow validation.
- Do not format storage, clear state, reset hardware, or trigger calibration on a live device without explicit authorization.
- Do not promote raw production logs, device identifiers, or operator data into long-term skill content.
