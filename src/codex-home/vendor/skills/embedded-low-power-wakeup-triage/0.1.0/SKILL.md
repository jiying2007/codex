---
name: embedded-low-power-wakeup-triage
description: "Use for embedded suspend, deep sleep, unexpected wakeup, sleep refusal, shutdown-to-sleep failure, wakeup source, RTC/TCP keepalive/WiFi IRQ investigation, or cold-boot versus suspend/resume diagnosis. Use when the question crosses app quiescing, kernel or firmware suspend, wake source, boot identity, or HIL cycling; use adk-embedded-remote-debug-log-triage first only when device reachability or read-only transport evidence is still unknown."
version: 0.1.0
last_updated: 2026-08-22
origin: local-chronicle-derived
lifecycle: iterative-local
triggers:
  - "休眠后自动唤醒"
  - "无法进入深度休眠"
  - "wakeup source"
  - "sleeping=0"
  - "RTC 唤醒变冷启动"
  - "shutdown 后未休眠"
  - "TCPKA 唤醒"
  - "WiFi IRQ 唤醒"
non_triggers:
  - "只有离线普通日志且不涉及低功耗状态"
  - "仅连接设备或采集日志，尚未确认低功耗问题"
  - "普通系统重启且没有 suspend/resume 或 wakeup 语义"
---

# Embedded Low-Power and Wakeup Triage

Diagnose a power transition as one staged state machine; never infer root cause from a single wake marker.

## Inputs

Accept app, kernel, firmware, driver, MCU, and boot logs; source paths; board/image identity; wake configuration; test medium; and an explicit read-only versus mutation boundary.

## Workflow

1. Freeze the transition contract: request, participant ACKs, producer quiesce, firmware/driver prepare, kernel `wakeup_count`, suspend entry, wake source, resume, and normal-service restoration.
2. Capture identity before and after the attempt: `boot_id`, uptime, PID, image/version, suspend return value, and relevant wake counters. Classify the result as refusal, early wake, resume, watchdog reset, or cold boot.
3. Separate layers: app/MCU transaction failure, active producer or resource cleanup, driver/firmware wake lock, kernel wake source, external IRQ, and boot-medium/environment interference.
4. Build a time-aligned evidence table. Mark observed facts, inferred causes, competing mutators, and missing probes separately.
5. Check quiescing and restore symmetry: producers stop before consumer teardown; every failure path reopens gates safely; no stale wake lock or bus-suspend state survives an aborted transition.
6. Compare controlled environments before changing code: no SD versus bootable debug SD, WiFi shadow or isolated peripheral, RTC versus external wake source, and a known-good image when available.
7. Propose the smallest probe or patch. Route device reachability work to `adk-embedded-remote-debug-log-triage`; route broad unknown failures to `adk-systematic-debugging`.
8. Expand HIL only after each gate passes: one smoke, 5–20 short cycles, long cycle/soak, then restore a healthy normal profile.

## Output

Return a transition table, identity comparison, wake-source hypothesis matrix, smallest next probes or patch plan, HIL matrix, and gate result: `stable`, `needs-more-data`, `needs-fix`, or `unsafe-to-release`.

## Guardrails

- Do not equate a user-space ACK with kernel suspend success.
- Do not call a reboot a wakeup without comparing `boot_id`, uptime, and boot markers.
- Do not treat a bootable debug medium as product-equivalent test evidence.
- Do not reset, flash, alter wake configuration, or disable protection without explicit authorization and a restore plan.
- Keep endpoints, raw logs, binaries, and credentials out of long-lived evidence.

Read `references/evidence-contract.md` for the minimum evidence and HIL matrix.
