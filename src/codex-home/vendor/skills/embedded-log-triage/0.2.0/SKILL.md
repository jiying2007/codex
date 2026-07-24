---
name: embedded-log-triage
description: "Use only for lightweight read-only analysis of pasted embedded logs or offline log files when there is no live device access, remote debug channel, core dump, diagnostic-harness question, protocol audit, audio-stream problem, or production-test lifecycle issue. Use adk-embedded-remote-debug-log-triage for device-side, field, SSH, ADB, serial-session, GDB-remote, or multi-artifact investigations."
version: 0.2.0
last_updated: 2026-07-15
origin: local-chronicle-derived
lifecycle: iterative-local
triggers:
  - "粘贴串口日志"
  - "离线日志包"
  - "仅分析日志文本"
  - "本地日志文件"
non_triggers:
  - "远程设备调试、SSH、ADB、实时串口会话或 GDB remote"
  - "core dump、BuildID、符号或 backtrace 分析"
  - "diag/prog_tool 返回码、音频流、产测生命周期或协议实现审计"
---

# Embedded Log Triage

Turn a bounded offline or pasted log sample into a compact timeline, hypothesis list, and next-probe plan.

## ADK Composition

- Primary only when the evidence is a pasted log excerpt or offline log file and the task does not require live-device access or another specialist skill.
- Supporting under `adk-embedded-remote-debug-log-triage` only when that primary skill needs a compact timeline from an attached offline log bundle.
- Mutually exclusive as primary with `adk-embedded-remote-debug-log-triage` for device-side, field, SSH, ADB, live serial, GDB-remote, history-recall, or multi-artifact investigations.
- Fallback to `adk-embedded-remote-debug-log-triage` when the evidence boundary expands beyond offline text.

## Inputs

Accept any combination of:

- pasted bootloader, kernel, driver, app, watchdog, OTA, prog, or stress-test log text;
- local log file paths or a bounded offline log package;
- known-good logs for comparison;
- test conditions, loop count, reset count, firmware version, board, or power-cycle method;
- narrow source or protocol context needed to interpret a specific marker.

## Workflow

1. Preserve evidence boundaries:
   - record source, time range, version hints, completeness, truncation, and sanitization state;
   - stop and reroute if the task requires remote commands, live device state, core analysis, or a specialist lifecycle/protocol/audio workflow.
2. Build a timeline:
   - separate bootloader, kernel, driver, app, OTA/prog, and test-harness phases;
   - mark resets, retries, long gaps, repeated markers, CRC/hash changes, watchdog events, mount errors, and state transitions.
3. Compare against expectations:
   - use a known-good log, project runbook, source, or protocol excerpt when available;
   - keep observed facts separate from inference.
4. Rank hypotheses:
   - prioritize by evidence strength, impact, and falsifiability;
   - do not elevate hardware, power, or timing explanations without supporting evidence.
5. Produce the smallest next probes:
   - request the minimum missing log window, counter, marker, register dump, or reproduction condition;
   - avoid code changes until the failing phase is bounded.
6. Close with `stable`, `needs-more-data`, `needs-fix`, or `unsafe-to-release` and state residual risk.

## Output

Return:

- source and completeness summary;
- timeline and anomaly table;
- hypotheses with confidence and counter-evidence;
- next probes or a narrowly scoped patch plan;
- gate result and missing evidence.

## Guardrails

- Do not claim root cause from a single ambiguous marker.
- Do not paste long raw logs back to the user.
- Do not use this skill as primary for remote debugging, core dumps, diagnostic CLI semantics, protocol audits, audio streams, or production-test lifecycle behavior.
- Do not modify firmware or production scripts unless the user explicitly asks after the failing phase is identified.
- Require explicit authorization for reset, erase, flash, OTA, partition, or publish operations.
