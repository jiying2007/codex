---
name: embedded-runtime-performance-triage
description: "Use for embedded runtime high CPU/load, thread blocking, latency spikes, frame-rate failure, callback stalls, high context-switch rate, queue buildup, or suspected scheduling/IO pressure. Use when a bounded runtime capture and source-mapped probes are needed; use embedded-audio-stream-triage for a clearly audio-stream-specific failure and adk-embedded-remote-debug-log-triage when device reachability or transport evidence is still unknown."
version: 0.1.0
last_updated: 2026-08-22
origin: local-chronicle-derived
lifecycle: iterative-local
triggers:
  - "prog_pcr02 高负载"
  - "线程 CPU 高"
  - "耗时尖峰"
  - "回调阻塞"
  - "帧率失败"
  - "高上下文切换"
  - "队列积压"
  - "进程高占用"
non_triggers:
  - "单次离线日志且没有性能或时延问题"
  - "已确认的音频流乱序或丢帧"
  - "无运行态证据的纯编译性能讨论"
---

# Embedded Runtime Performance Triage

Bound runtime-performance diagnosis with low-overhead measurements before changing priorities, buffers, or timing constants.

## Inputs

Accept a process/service identity, image/version, reproduction window, load or latency symptom, bounded logs, source ownership hints, and authorized read-only access information.

## Workflow

1. Fix the symptom and budget: CPU, latency, frame rate, queue depth, missed deadline, I/O wait, or memory pressure. Record expected cadence and the observation window.
2. Capture low-overhead baselines: wall-clock anchors, load, CPU busy, memory/IO trend, process state, thread CPU deltas, voluntary/nonvoluntary context switches, state, `wchan`, and queue/drop counters when available.
3. Rank hot threads by CPU delta, scheduling contention, and blocked state; do not mistake thread names for source ownership until verified.
4. Classify the limiting resource: CPU/scheduler, blocking wait, queue/backpressure, I/O, memory, or unproven hardware bandwidth. Keep unknown separate from excluded.
5. Map only confirmed thread entry points to source. Add rate-limited aggregate probes—count, duration distribution, queue depth, drop/timeout reason—rather than per-event logging.
6. Compare a known-good window or focused reproduction. Change one bounded hypothesis at a time and quantify latency, memory, CPU, and compatibility cost.
7. Validate with a focused regression matrix and preserve the evidence identity; hand off audio-stream-specific behavior or device transport failures to their specialist skills.

## Output

Return a capture-completeness summary, thread/resource ranking, observed-versus-inferred table, smallest probes or patch plan, focused regression matrix, and gate result: `stable`, `needs-more-data`, `needs-fix`, or `unsafe-to-release`.

## Guardrails

- Do not raise thread priority, enlarge buffers, or add verbose logging before identifying the limiting boundary.
- Do not claim DDR/bus saturation from generic memory statistics alone.
- Do not claim a source owner from a truncated or stale thread name.
- Do not run destructive load tests, restart services, or alter real-time policy without explicit authorization and a restore condition.

Read `references/capture-contract.md` for a minimal capture schema.
